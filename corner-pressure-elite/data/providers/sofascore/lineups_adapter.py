"""SofaScoreLineupsAdapter — lineups + coach + missing_players (Fase K.1 B.4).

Resolve gap Betano via:
- `/event/{id}/managers` — `coach_name` (BETANO_GAPS_LINEUPS).
- `/event/{id}/lineups.missingPlayers[]` — lesões/suspensões.

# Schema /lineups
```json
{
  "confirmed": bool|null,
  "home": {"formation", "players[]", "supportStaff[]", "missingPlayers[]"},
  "away": {...análogo...}
}
```

Player schema (outer): `{player: {name,id,position,...}, teamId, shirtNumber,
jerseyNumber, position, substitute, captain, statistics}`.

MissingPlayer schema: `{player: {...}, type: 'missing'|'doubtful',
reason: int (1=injury observado em MLS), expectedEndDate: ISO str}`.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import date, datetime
from typing import Any, Awaitable, Callable, Optional

from data.lineups_provider import (
    BETANO_GAPS_LINEUPS,
    CanonicalLineup,
    MissingPlayer,
    PlayerEntry,
)
from data.odds_provider import CanonicalFixture

from .client import SofaScoreClient

log = logging.getLogger("cpes.providers.sofascore.lineups")


# SofaScore reason codes → categoria humana.
# 1 = injury (validado em MLS, expectedEndDate típica de lesão).
# Demais a descobrir via logs WARNING.
_SOFA_REASON_CODE_MAP: dict[int, str] = {
    1: "injury",
    2: "suspension",  # assumido — validar via logs
}


# Mesmo mapping do AF adapter (G/D/M/F → GK/DF/MF/FW).
_POSITION_MAP: dict[str, str] = {
    "G": "GK",
    "D": "DF",
    "M": "MF",
    "F": "FW",
}


EventIdResolver = Callable[[CanonicalFixture], Awaitable[Optional[int]]]


def _map_position(raw_pos: Any) -> Optional[str]:
    if not isinstance(raw_pos, str) or not raw_pos:
        return None
    mapped = _POSITION_MAP.get(raw_pos.upper())
    if mapped:
        return mapped
    log.warning(
        "sofascore_lineups.unmapped_position pos=%r — using upper() fallback", raw_pos
    )
    return raw_pos.upper()


def _parse_expected_end(value: Any) -> Optional[date]:
    if not isinstance(value, str) or not value:
        return None
    try:
        # ISO format com timezone, ex: "2026-11-09T00:00:00+00:00"
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return dt.date()
    except (TypeError, ValueError):
        return None


def _missing_reason(raw_type: Any, raw_code: Any) -> tuple[Optional[str], Optional[int]]:
    """Resolve (reason_str, reason_code) a partir de type + code SofaScore."""
    code = raw_code if isinstance(raw_code, int) else None
    rtype = raw_type.lower() if isinstance(raw_type, str) else None

    if rtype == "doubtful":
        return ("doubtful", code)
    if rtype == "missing":
        if code in _SOFA_REASON_CODE_MAP:
            return (_SOFA_REASON_CODE_MAP[code], code)
        log.warning(
            "sofascore_lineups.unmapped_reason_code code=%s type=%r — using 'unknown'",
            code, rtype,
        )
        return ("unknown", code)
    log.warning(
        "sofascore_lineups.unmapped_type type=%r — using 'unknown'", rtype
    )
    return ("unknown", code)


class SofaScoreLineupsAdapter:
    """Provider lineups via SofaScore. Implementa `LineupsProvider` Protocol.

    Faz `/lineups` + `/managers` em paralelo (asyncio.gather) pra evitar latência
    serial. Coach name vem do `/managers` (gap Betano resolvido).
    """

    name = "sofascore"

    def __init__(
        self,
        client: SofaScoreClient,
        event_id_resolver: Optional[EventIdResolver] = None,
    ):
        self._client = client
        self._resolver = event_id_resolver

    async def get_lineups(
        self,
        fixture_id: int,
        *,
        betano_event_id: Optional[int] = None,
        home_team_id: Optional[int] = None,
    ) -> Optional[list[CanonicalLineup]]:
        if self._resolver is None:
            log.debug("sofascore_lineups.no_resolver fixture=%d", fixture_id)
            return None

        from datetime import datetime, timezone
        synth = CanonicalFixture(
            fixture_id=fixture_id,
            home_team="?",
            away_team="?",
            league_id=0,
            starts_at_utc=datetime.now(timezone.utc),
        )
        sofa_event_id = await self._resolver(synth)
        if sofa_event_id is None:
            log.debug("sofascore_lineups.no_sofa_event_id fixture=%d", fixture_id)
            return None

        # Paralelo: lineups + managers (coach vem só de /managers).
        lineups_task = self._client.get_lineups(sofa_event_id)
        managers_task = self._client.get_managers(sofa_event_id)
        raw_lineups, raw_managers = await asyncio.gather(
            lineups_task, managers_task, return_exceptions=True,
        )

        if isinstance(raw_lineups, Exception):
            log.warning(
                "sofascore_lineups.client_error fixture=%d sofa=%d err=%s",
                fixture_id, sofa_event_id, raw_lineups,
            )
            return None
        if not raw_lineups or not isinstance(raw_lineups, dict):
            return None

        coach_home = None
        coach_away = None
        if isinstance(raw_managers, dict):
            hm = (raw_managers.get("homeManager") or {})
            am = (raw_managers.get("awayManager") or {})
            coach_home = hm.get("name") if isinstance(hm, dict) else None
            coach_away = am.get("name") if isinstance(am, dict) else None

        return [
            self._normalize_team(
                raw_lineups.get("home") or {}, "home", coach_home, fixture_id,
            ),
            self._normalize_team(
                raw_lineups.get("away") or {}, "away", coach_away, fixture_id,
            ),
        ]

    async def healthcheck(self) -> bool:
        return await self._client.health()

    def _normalize_team(
        self,
        raw_team: dict,
        team_side: str,
        coach_name: Optional[str],
        fixture_id: int,
    ) -> CanonicalLineup:
        players = raw_team.get("players") or []
        starting: list[PlayerEntry] = []
        subs: list[PlayerEntry] = []
        for p in players:
            entry = self._normalize_player(p)
            if entry is None:
                continue
            if entry.is_substitute:
                subs.append(entry)
            else:
                starting.append(entry)

        missing_raw = raw_team.get("missingPlayers") or []
        missing: list[MissingPlayer] = []
        for m in missing_raw:
            mp = self._normalize_missing(m)
            if mp is not None:
                missing.append(mp)

        return CanonicalLineup(
            fixture_id=fixture_id,
            source=self.name,
            team_side=team_side,
            formation=raw_team.get("formation") if isinstance(raw_team.get("formation"), str) else None,
            coach_name=coach_name,
            starting_eleven=starting,
            substitutes=subs,
            tactical_grid=None,            # SofaScore não tem (Betano sim)
            version=None,
            missing_players=missing,
            raw=raw_team,
        )

    def _normalize_player(self, raw: dict) -> Optional[PlayerEntry]:
        if not isinstance(raw, dict):
            return None
        player_obj = raw.get("player") or {}
        if not isinstance(player_obj, dict):
            return None
        name = player_obj.get("name")
        if not isinstance(name, str) or not name:
            return None
        # shirtNumber pode ser int OR string OR None
        shirt = raw.get("shirtNumber")
        if isinstance(shirt, str):
            try:
                shirt = int(shirt)
            except (TypeError, ValueError):
                shirt = None
        if not isinstance(shirt, int):
            shirt = None

        return PlayerEntry(
            name=name,
            player_id=player_obj.get("id") if isinstance(player_obj.get("id"), int) else None,
            position=_map_position(raw.get("position") or player_obj.get("position")),
            position_display=None,         # SofaScore não traz localizado pt-BR
            shirt_number=shirt,
            is_substitute=bool(raw.get("substitute", False)),
        )

    def _normalize_missing(self, raw: dict) -> Optional[MissingPlayer]:
        if not isinstance(raw, dict):
            return None
        player_obj = raw.get("player") or {}
        name = player_obj.get("name") if isinstance(player_obj, dict) else None
        if not isinstance(name, str) or not name:
            name = "<unknown>"
        reason, reason_code = _missing_reason(raw.get("type"), raw.get("reason"))
        return MissingPlayer(
            player_id=player_obj.get("id") if isinstance(player_obj.get("id"), int) else None,
            name=name,
            reason=reason,
            reason_code=reason_code,
            expected_return=_parse_expected_end(raw.get("expectedEndDate")),
            source=self.name,
        )
