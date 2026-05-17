"""BridgeEventsAdapter — provider de eventos Betano via bridge HTTP (Fase F).

Reusa endpoint `/event/<id>/state` do bridge (mesmo do `BridgeStatsAdapter`
da Fase E.1). Extrai `event.incidents[]` do payload e normaliza pra
`list[CanonicalEvent]`.

# Schema do incident Betano (do doc E.0 §1.4)

```json
{
  "description": "1-3 ASK Voitsberg (com Penálti)",
  "time": "50'",
  "type": "GOAL",
  "teamSide": 1,
  "props": {
    "scoreHome": 1, "scoreAway": 3,
    "minute": 50,
    "filterIds": [5, 10]
  }
}
```

- `teamSide`: 0=home, 1=away. NULL pra eventos sem lado (PBEG, PEND, etc).
- `time`: string `"M'"` ou `"M'+N'"` (acréscimo).
- `props.minute`: int redundante com `time`, mais confiável quando presente.

# Otimização futura (não implementada agora)

Adapter chama bridge separadamente do `BridgeStatsAdapter`. Bridge tem
cache TTL=3s então duas chamadas próximas pra mesmo event_id pegam mesma
versão (304 ou hit interno). Pra eliminar até esse round-trip duplicado,
worker poderia compartilhar o payload já fetched. Deixar pra Fase F.1 se
volume justificar.
"""
from __future__ import annotations

import logging
import re
from typing import Any, Optional

import aiohttp

from data.events_provider import CanonicalEvent

log = logging.getLogger("cpes.providers.betano.bridge_events")

_TIME_RE = re.compile(r"^(\d+)'(?:\+(\d+)')?$")


class BridgeEventsAdapter:
    """Provider Betano via bridge HTTP. Implementa `EventsProvider` Protocol."""

    name = "bridge_betano"

    def __init__(
        self,
        bridge_url: str,
        fixture_repo: Any = None,
        timeout_seconds: float = 30.0,
        session: Optional[aiohttp.ClientSession] = None,
    ):
        self._bridge_url = bridge_url.rstrip("/")
        self._fixture_repo = fixture_repo
        self._timeout = aiohttp.ClientTimeout(total=timeout_seconds)
        self._injected_session = session
        self._owned_session: Optional[aiohttp.ClientSession] = None
        self._event_id_cache: dict[int, int] = {}

    async def _session_instance(self) -> aiohttp.ClientSession:
        if self._injected_session is not None:
            return self._injected_session
        if self._owned_session is None or self._owned_session.closed:
            self._owned_session = aiohttp.ClientSession(timeout=self._timeout)
        return self._owned_session

    async def close(self) -> None:
        if self._owned_session is not None and not self._owned_session.closed:
            await self._owned_session.close()

    async def get_events(
        self,
        fixture_id: int,
        *,
        betano_event_id: Optional[int] = None,
        home_team_id: Optional[int] = None,
    ) -> Optional[list[CanonicalEvent]]:
        """Retorna lista de eventos do fixture.

        `home_team_id` é ignorado (Betano fornece `teamSide` 0/1 direto no
        incident). `betano_event_id` é hint pré-resolvido — quando passado,
        evita lookup no `fixture_repo`.

        Cenários:
        - 200 com `data.event.incidents` válido → `list[CanonicalEvent]`
        - 200 sem incidents (cobertura zero da liga) → `[]`
        - 304 (cache version match) → `[]` (sem novos eventos)
        - fixture sem mapping no fixture_repo → `None`
        - 4xx/5xx / timeout → `None`
        """
        event_id = betano_event_id or await self._resolve_event_id(fixture_id)
        if not event_id:
            log.debug("bridge_events.no_event_id fixture=%d", fixture_id)
            return None

        url = f"{self._bridge_url}/event/{event_id}/state"
        try:
            session = await self._session_instance()
            async with session.get(url) as resp:
                if resp.status == 304:
                    return []
                if resp.status >= 400:
                    log.warning(
                        "bridge_events.http_error fixture=%d event=%d status=%s",
                        fixture_id, event_id, resp.status,
                    )
                    return None
                payload = await resp.json()
        except aiohttp.ClientError as e:
            log.warning(
                "bridge_events.client_error fixture=%d event=%d err=%s",
                fixture_id, event_id, e,
            )
            return None

        return self._parse(fixture_id, event_id, payload)

    async def healthcheck(self) -> bool:
        url = f"{self._bridge_url}/health"
        try:
            session = await self._session_instance()
            async with session.get(url) as resp:
                return resp.status == 200
        except aiohttp.ClientError as e:
            log.warning("bridge_events.healthcheck.error err=%s", e)
            return False

    async def _resolve_event_id(self, fixture_id: int) -> Optional[int]:
        cached = self._event_id_cache.get(fixture_id)
        if cached:
            return cached
        if self._fixture_repo is None:
            return None
        try:
            ev = await self._fixture_repo.get_betano_event_id(fixture_id)
        except Exception as e:
            log.warning(
                "bridge_events.repo_lookup_error fixture=%d err=%s", fixture_id, e
            )
            return None
        if ev:
            self._event_id_cache[fixture_id] = int(ev)
            return int(ev)
        return None

    def _parse(
        self, fixture_id: int, event_id: int, payload: dict
    ) -> list[CanonicalEvent]:
        """Extrai `data.event.incidents[]` e normaliza pra CanonicalEvent[].

        Robusto contra payloads incompletos (cobertura varia por liga —
        ver `docs/architecture/betano-stats-api.md §5.2`).
        """
        data = payload.get("data") or {}
        event = data.get("event") or {}
        incidents = event.get("incidents") or []
        if not isinstance(incidents, list):
            return []

        out: list[CanonicalEvent] = []
        for inc in incidents:
            if not isinstance(inc, dict):
                continue
            normalized = self._normalize_incident(fixture_id, event_id, inc)
            if normalized is not None:
                out.append(normalized)
        return out

    def _normalize_incident(
        self, fixture_id: int, event_id: int, inc: dict
    ) -> Optional[CanonicalEvent]:
        event_type = inc.get("type")
        if not isinstance(event_type, str) or not event_type:
            return None

        props = inc.get("props") if isinstance(inc.get("props"), dict) else {}

        # Minuto: preferir props.minute (int direto); fallback ao parse de time.
        event_minute: Optional[int] = None
        prop_min = props.get("minute")
        if isinstance(prop_min, int):
            event_minute = prop_min
        elif isinstance(prop_min, str):
            try:
                event_minute = int(prop_min)
            except ValueError:
                pass
        if event_minute is None:
            time_str = inc.get("time")
            if isinstance(time_str, str):
                m = _TIME_RE.match(time_str.strip())
                if m:
                    base = int(m.group(1))
                    extra = int(m.group(2)) if m.group(2) else 0
                    event_minute = base + extra
        if event_minute is None:
            # Incidentes Aggregated podem não ter minute específico;
            # se for o caso, descarta (não persistível sem minute).
            return None

        # teamSide: 0=home, 1=away. Qualquer outro = None.
        side_raw = inc.get("teamSide")
        if side_raw == 0:
            team_side: Optional[str] = "home"
        elif side_raw == 1:
            team_side = "away"
        else:
            team_side = None

        return CanonicalEvent(
            fixture_id=fixture_id,
            source=self.name,
            event_type=event_type,
            event_minute=event_minute,
            event_second=None,            # Betano incidents não trazem segundo
            team_side=team_side,
            player_name=None,             # incidents agregados não nomeiam player
            props=dict(props),
            raw=dict(inc),
        )
