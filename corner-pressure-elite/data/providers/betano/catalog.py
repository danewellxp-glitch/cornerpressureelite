"""Catálogo de eventos ao vivo + fuzzy match `fixture_id → event_id`.

REST `/danae-webapi/api/live/overview/latest` retorna ~96 eventos. Fazemos
match local por (nome normalizado, kickoff ±15min, sport=FOOT).
"""
from __future__ import annotations

import logging
import unicodedata
from datetime import datetime
from typing import Optional

from . import parsers
from .schemas import BetanoLiveEvent, BetanoStatsPlayerMapping
from .session import BetanoSession

log = logging.getLogger("cpes.betano.catalog")


def _norm(s: str) -> str:
    s = unicodedata.normalize("NFD", s or "")
    s = "".join(c for c in s if not unicodedata.combining(c))
    return s.lower().strip()


class BetanoCatalog:
    def __init__(self, session: BetanoSession):
        self._s = session
        self._events_cache: list[BetanoLiveEvent] = []
        self._fixture_map: dict[int, int] = {}

    async def list_live_events(self) -> list[BetanoLiveEvent]:
        raw = await self._s.get_json(
            "/danae-webapi/api/live/overview/latest",
            referer="https://www.betano.bet.br/live/futebol/",
        )
        if not raw:
            return []
        self._events_cache = parsers.parse_live_overview_events(raw)
        log.info("betano.catalog.loaded events=%d", len(self._events_cache))
        return self._events_cache

    async def find_event_by_fixture(
        self,
        fixture_id: int,
        team_home: str,
        team_away: str,
        kickoff_at: datetime,
        league_id_hint: Optional[int] = None,
    ) -> Optional[int]:
        if fixture_id in self._fixture_map:
            return self._fixture_map[fixture_id]
        if not self._events_cache:
            await self.list_live_events()

        nh = _norm(team_home)
        na = _norm(team_away)
        candidates: list[tuple[float, BetanoLiveEvent]] = []

        for ev in self._events_cache:
            if ev.sport_id != "FOOT":
                continue
            participants = [_norm(p.name) for p in ev.participants]
            home_match = any(nh and (nh in p or p in nh) for p in participants)
            away_match = any(na and (na in p or p in na) for p in participants)
            if not (home_match and away_match):
                continue
            delta_min = abs((ev.start_time - kickoff_at).total_seconds() / 60)
            if delta_min > 15:
                continue
            score = 100.0 - delta_min
            if league_id_hint and ev.league_id == league_id_hint:
                score += 5.0
            candidates.append((score, ev))

        if not candidates:
            log.info(
                "betano.catalog.no_match fixture=%d %s vs %s",
                fixture_id, team_home, team_away,
            )
            return None

        candidates.sort(key=lambda x: -x[0])
        best = candidates[0][1]
        self._fixture_map[fixture_id] = best.event_id
        log.info(
            "betano.catalog.matched fixture=%d -> event=%d score=%.2f",
            fixture_id, best.event_id, candidates[0][0],
        )
        return best.event_id

    def fixture_map_snapshot(self) -> dict[int, int]:
        return dict(self._fixture_map)

    def prime_fixture_map(self, fixture_id: int, event_id: int) -> None:
        """Permite à Fase D popular o cache a partir do DB."""
        self._fixture_map[fixture_id] = event_id

    async def resolve_event_full(
        self, event_id: int
    ) -> Optional[BetanoStatsPlayerMapping]:
        """Mapping Sportradar (statType=4) + Opta (statType=6)."""
        raw = await self._s.get_json(
            f"/api/liveevent/statsplayer?id={event_id}",
            referer=f"https://www.betano.bet.br/live/_/{event_id}/",
        )
        return parsers.parse_statsplayer(raw, event_id) if raw else None
