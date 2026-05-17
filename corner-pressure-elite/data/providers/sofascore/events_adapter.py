"""SofaScoreEventsAdapter — eventos via SofaScore /incidents (Fase K.1 PARTE B).

Substitui `APIFootballEventsAdapter` no Composite como fallback intermediário.

# Schema response `/event/{id}/incidents`

```json
{
  "incidents": [
    {
      "incidentType": "goal" | "card" | "substitution" | "period" | "varDecision" | "injuryTime",
      "incidentClass": "regular" | "yellow" | "red" | "yellowRed" | None,
      "time": int,                        # minuto
      "addedTime": int (999 = sem stoppage),
      "isHome": bool (em incidents com time),
      "player": {name, id, ...} (goal/card),
      "playerIn"/"playerOut": {name, id, ...} (substitution),
      "text": str (description),
      ...
    }
  ]
}
```

# Mapping SofaScore → CanonicalEvent

| SofaScore (incidentType, incidentClass)       | event_type canonical |
|-----------------------------------------------|----------------------|
| ('goal', *)                                   | GOAL                 |
| ('card', 'yellow')                            | YELL                 |
| ('card', 'red') / ('card', 'yellowRed')       | RCRD                 |
| ('substitution', *)                           | SUBS                 |
| ('period', *) — começo                        | PBEG                 |
| ('period', *) — fim                           | PEND (heurística por texto) |
| ('injuryTime', *)                             | StoppageTime         |
| ('varDecision', *)                            | VAR                  |
| ('corner', *)                                 | CRNR                 |
| ('penalty', *)                                | PENL                 |
| outros                                        | upper() + log WARNING|

`team_side`: derivado de `isHome` (True → 'home', False → 'away', ausente → None).
`event_minute`: `time` (int). Se ausente, descarta.
`player_name`: `player.name` (goal/card) ou `playerIn.name` (subst).
"""
from __future__ import annotations

import logging
from typing import Any, Awaitable, Callable, Optional

from data.events_provider import CanonicalEvent
from data.odds_provider import CanonicalFixture

from .client import SofaScoreClient

log = logging.getLogger("cpes.providers.sofascore.events")


EventIdResolver = Callable[[CanonicalFixture], Awaitable[Optional[int]]]


def _map_incident_type(
    incident_type: Optional[str],
    incident_class: Optional[str],
    text: Optional[str] = None,
) -> str:
    """Mapeia (type, class) → canonical. Loga WARNING quando cai em fallback."""
    if not incident_type:
        return "UNKNOWN"
    t = incident_type.lower()
    c = (incident_class or "").lower()

    if t == "goal":
        return "GOAL"
    if t == "card":
        if c in ("red", "yellowred", "yellow_red"):
            return "RCRD"
        if c == "yellow":
            return "YELL"
        log.warning(
            "sofascore_events.unmapped_card_class class=%r — defaulting YELL", c
        )
        return "YELL"
    if t == "substitution":
        return "SUBS"
    if t == "period":
        # 'Half time', 'Full time' → PEND. 'First half', 'Second half' → PBEG.
        tx = (text or "").lower()
        if any(k in tx for k in ("first half", "second half", "started", "start")):
            return "PBEG"
        if any(k in tx for k in ("half time", "full time", "ended", "ftd", "ended")):
            return "PEND"
        # Default conservador.
        return "PBEG"
    if t == "injurytime":
        return "StoppageTime"
    if t == "vardecision":
        return "VAR"
    if t == "corner":
        return "CRNR"
    if t == "penalty":
        return "PENL"
    if t == "offside":
        return "OFFS"

    log.warning(
        "sofascore_events.unmapped_type type=%r class=%r — using upper()",
        incident_type, incident_class,
    )
    return incident_type.upper()


def _team_side(incident: dict) -> Optional[str]:
    """Resolve team_side via campos prováveis. None se ausente."""
    if "isHome" in incident:
        return "home" if incident["isHome"] else "away"
    # Goal sometimes uses `homeScore`/`awayScore` no incident — não tem `isHome`.
    # Heurística secundária: `player.team` se existir.
    pl = incident.get("player") or incident.get("playerIn") or {}
    if isinstance(pl, dict):
        team = pl.get("team") or {}
        if isinstance(team, dict):
            tid_label = team.get("name")
            if tid_label:
                # Sem fixture context aqui — caller decide se quer fazer match.
                pass
    return None


def _player_name(incident: dict) -> Optional[str]:
    for key in ("player", "playerIn"):
        p = incident.get(key)
        if isinstance(p, dict):
            name = p.get("name")
            if isinstance(name, str) and name:
                return name
    return None


class SofaScoreEventsAdapter:
    """Provider events via SofaScore. Implementa `EventsProvider` Protocol."""

    name = "sofascore"

    def __init__(
        self,
        client: SofaScoreClient,
        event_id_resolver: Optional[EventIdResolver] = None,
    ):
        self._client = client
        self._resolver = event_id_resolver

    async def get_events(
        self,
        fixture_id: int,
        *,
        betano_event_id: Optional[int] = None,
        home_team_id: Optional[int] = None,
    ) -> Optional[list[CanonicalEvent]]:
        # SofaScore aceita `fixture_id` direto se já vier resolvido externamente
        # via betano_event_id (não é o caso) — precisa do resolver pra mapear
        # fixture_id (AF) → sofa_event_id. Composite pode passar
        # CanonicalFixture, mas EventsProvider Protocol só dá fixture_id —
        # adapter precisa do resolver registrado.
        if self._resolver is None:
            log.debug("sofascore_events.no_resolver fixture=%d", fixture_id)
            return None

        # Resolver foi tipado pra receber CanonicalFixture, mas EventsProvider
        # Protocol só passa fixture_id. Pragmatismo K.1: callable aceita só
        # fixture_id pro caso events (caller no Composite K.1 PARTE B.6
        # injeta resolver adequado).
        sofa_event_id = await self._resolve(fixture_id)
        if sofa_event_id is None:
            log.debug("sofascore_events.no_sofa_event_id fixture=%d", fixture_id)
            return None

        try:
            raw_incidents = await self._client.get_incidents(sofa_event_id)
        except Exception as e:
            log.warning(
                "sofascore_events.client_error fixture=%d sofa=%d err=%s",
                fixture_id, sofa_event_id, e,
            )
            return None
        if raw_incidents is None:
            return None

        out: list[CanonicalEvent] = []
        for inc in raw_incidents:
            normalized = self._normalize_incident(fixture_id, inc)
            if normalized is not None:
                out.append(normalized)
        return out

    async def healthcheck(self) -> bool:
        return await self._client.health()

    async def _resolve(self, fixture_id: int) -> Optional[int]:
        """Resolve fixture_id → sofa_event_id via resolver injetado."""
        if self._resolver is None:
            return None
        # Resolver assina (CanonicalFixture)→Optional[int]. Pra events, só temos
        # fixture_id, então passa CanonicalFixture mínimo (sem starts_at_utc).
        # Estratégia: criar fixture sintético — resolver deve só usar fixture_id.
        from datetime import datetime, timezone
        synth = CanonicalFixture(
            fixture_id=fixture_id,
            home_team="?",
            away_team="?",
            league_id=0,
            starts_at_utc=datetime.now(timezone.utc),
        )
        return await self._resolver(synth)

    def _normalize_incident(
        self, fixture_id: int, inc: dict
    ) -> Optional[CanonicalEvent]:
        if not isinstance(inc, dict):
            return None

        # Minuto obrigatório.
        time_val = inc.get("time")
        if not isinstance(time_val, int):
            log.debug(
                "sofascore_events.no_minute fixture=%d type=%r",
                fixture_id, inc.get("incidentType"),
            )
            return None

        event_type = _map_incident_type(
            inc.get("incidentType"),
            inc.get("incidentClass"),
            inc.get("text"),
        )

        return CanonicalEvent(
            fixture_id=fixture_id,
            source=self.name,
            event_type=event_type,
            event_minute=time_val,
            event_second=inc.get("timeSeconds") if isinstance(inc.get("timeSeconds"), int) else None,
            team_side=_team_side(inc),
            player_name=_player_name(inc),
            props={
                "incident_type": inc.get("incidentType"),
                "incident_class": inc.get("incidentClass"),
                "added_time": inc.get("addedTime"),
                "text": inc.get("text"),
            },
            raw=inc,
        )
