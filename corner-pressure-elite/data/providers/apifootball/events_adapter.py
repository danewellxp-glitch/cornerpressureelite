"""APIFootballEventsAdapter — fallback de eventos via API-Football (Fase F).

Refactor do `api_client.get_events()` legado encapsulado como `EventsProvider`.
Mapeia tipos AF (`Goal`, `Card`+`Yellow Card`, `subst`, etc) pra tipos
canônicos (`GOAL`, `YELL`, `SUBS`).

# Schema response AF (`GET /fixtures/events?fixture=ID`)

```json
{
  "response": [
    {
      "time": {"elapsed": 50, "extra": null},
      "team": {"id": 33, "name": "Manchester United"},
      "player": {"id": 909, "name": "C. Eriksen"},
      "assist": {"id": null, "name": null},
      "type": "Card",
      "detail": "Yellow Card",
      "comments": null
    }
  ]
}
```

# Mapeamento type+detail → canônico

| AF type | AF detail            | Canonical |
|---------|----------------------|-----------|
| Goal    | Normal Goal          | GOAL      |
| Goal    | Penalty              | GOAL      |
| Goal    | Own Goal             | GOAL      |
| Card    | Yellow Card          | YELL      |
| Card    | Second Yellow card   | RCRD      |
| Card    | Red Card             | RCRD      |
| subst   | (qualquer)           | SUBS      |
| Var     | (qualquer)           | VAR       |
| (outros)| (qualquer)           | type literal uppercase |

# Resolução team_side

AF traz `team.id` não `home/away`. Adapter precisa do `home_team_id` (hint
do caller) pra decidir side. Quando hint ausente, deixa `team_side=None`
(perde info mas não erra).
"""
from __future__ import annotations

import logging
from typing import Any, Optional

from data.events_provider import CanonicalEvent

log = logging.getLogger("cpes.providers.apifootball.events")


# Mapping AF (type, detail) → canonical event_type.
# Manter sincronizado com event_type canônico documentado em
# data/events_provider.py (tabela de tipos).
_AF_TYPE_MAP: dict[tuple[str, str], str] = {
    ("Goal", "Normal Goal"): "GOAL",
    ("Goal", "Penalty"): "GOAL",
    ("Goal", "Own Goal"): "GOAL",
    ("Goal", "Cancelled Goal"): "CGOL",     # gol anulado (frequente em prod)
    ("Goal", "Missed Penalty"): "PENL",
    ("Card", "Yellow Card"): "YELL",
    ("Card", "Second Yellow card"): "RCRD",  # 2º amarelo = expulso
    ("Card", "Red Card"): "RCRD",
    ("subst", ""): "SUBS",
    ("Var", ""): "VAR",
    ("Var", "Goal cancelled"): "CGOL",       # alias do CGOL acima
    ("Var", "Penalty awarded"): "VAR",
    ("Var", "Penalty confirmed"): "VAR",
}


def _map_af_to_canonical(
    af_type: str, af_detail: str, *, fixture_id: Optional[int] = None
) -> str:
    """Resolve type+detail AF → tipo canônico. Fallback: af_type uppercase.

    Quando cai em fallback (combinação não mapeada), emite WARNING — review
    de logs semanal revela mappings faltantes vs Postgres pollution silenciosa.
    """
    key = (af_type, af_detail)
    if key in _AF_TYPE_MAP:
        return _AF_TYPE_MAP[key]
    # Fallback type literal (substring match pra "subst" e "Var" sem detail conhecido)
    if af_type == "subst":
        return "SUBS"
    if af_type == "Var":
        # Var com detail desconhecido — preserva como VAR mas alerta
        log.warning(
            "events_adapter.af.unmapped_var detail=%r fixture=%s — usando VAR",
            af_detail, fixture_id,
        )
        return "VAR"
    fallback = af_type.upper() if af_type else "UNKNOWN"
    log.warning(
        "events_adapter.af.unmapped_type type=%r detail=%r fixture=%s — "
        "caindo em fallback %r",
        af_type, af_detail, fixture_id, fallback,
    )
    return fallback


class APIFootballEventsAdapter:
    """Provider AF via APIFootballClient existente. Implementa `EventsProvider`."""

    name = "apifootball"

    def __init__(self, api_client: Any):
        self._client = api_client

    async def get_events(
        self,
        fixture_id: int,
        *,
        betano_event_id: Optional[int] = None,
        home_team_id: Optional[int] = None,
    ) -> Optional[list[CanonicalEvent]]:
        """Busca eventos via AF. `betano_event_id` é ignorado (compat Protocol).

        `home_team_id`: hint pra resolver `team_side` ('home'/'away') a partir
        do `team.id` no response AF. Quando ausente, side fica None
        (degradação graceful — dataset persiste sem perder evento). Log debug
        emitido pra rastreabilidade.
        """
        if home_team_id is None:
            log.debug(
                "apifootball_events.side_unresolved fixture=%d — home_team_id ausente",
                fixture_id,
            )
        try:
            raw_events = await self._client.get_events(fixture_id)
        except Exception as e:
            log.warning(
                "apifootball_events.client_error fixture=%d err=%s",
                fixture_id, e,
            )
            return None
        if not isinstance(raw_events, list):
            return None
        return [
            ce
            for ce in (
                self._normalize(fixture_id, e, home_team_id) for e in raw_events
            )
            if ce is not None
        ]

    async def healthcheck(self) -> bool:
        try:
            status = await self._client.check_status()
            return isinstance(status, dict) and status.get("requests") is not None
        except Exception as e:
            log.warning("apifootball_events.healthcheck.error err=%s", e)
            return False

    def _normalize(
        self, fixture_id: int, e: Any, home_team_id: Optional[int]
    ) -> Optional[CanonicalEvent]:
        if not isinstance(e, dict):
            return None

        time = e.get("time") or {}
        elapsed = time.get("elapsed")
        extra = time.get("extra") or 0
        if not isinstance(elapsed, int):
            return None
        try:
            event_minute = int(elapsed) + int(extra)
        except (TypeError, ValueError):
            event_minute = int(elapsed)

        af_type = e.get("type") or ""
        af_detail = e.get("detail") or ""
        canonical_type = _map_af_to_canonical(
            af_type if isinstance(af_type, str) else "",
            af_detail if isinstance(af_detail, str) else "",
            fixture_id=fixture_id,
        )

        team = e.get("team") or {}
        team_id = team.get("id") if isinstance(team, dict) else None
        team_side: Optional[str] = None
        if home_team_id is not None and isinstance(team_id, int):
            team_side = "home" if team_id == home_team_id else "away"

        player = e.get("player") or {}
        player_name = player.get("name") if isinstance(player, dict) else None

        return CanonicalEvent(
            fixture_id=fixture_id,
            source=self.name,
            event_type=canonical_type,
            event_minute=event_minute,
            event_second=None,
            team_side=team_side,
            player_name=player_name if isinstance(player_name, str) else None,
            props={
                "af_type": af_type,
                "af_detail": af_detail,
                "comments": e.get("comments"),
                "assist": (e.get("assist") or {}).get("name"),
            },
            raw=dict(e),
        )
