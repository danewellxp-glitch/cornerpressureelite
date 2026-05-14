"""Cliente REST para /api/statsstream/{eventId}/* da Betano (Opta-backed).

Wrapper fino sobre `BetanoSession.get_json` + parsers.
"""
from __future__ import annotations

import logging
from typing import Optional

from . import parsers
from .schemas import (
    DetailedStats,
    H2H,
    Lineups,
    MatchConfig,
    MatchInfo,
    Momentum,
    PlayerStats,
)
from .session import BetanoSession

log = logging.getLogger("cpes.betano.statsstream")

# Evento que aparece no .mitm golden de 2026-05-12; usado pelo healthcheck.
_HEALTHCHECK_EVENT_ID = 84586925


class BetanoStatsStream:
    def __init__(self, session: BetanoSession):
        self._s = session

    def _referer(self, event_id: int) -> str:
        # Path canônico seria `/live/<slug>/<eventId>/`. A Betano aceita o
        # prefixo curto que conhecemos para origin checks de fetch.
        return f"https://www.betano.bet.br/live/_/{event_id}/"

    async def get_info_aggregated(
        self, event_id: int, lang: str = "pt_BR"
    ) -> Optional[MatchInfo]:
        raw = await self._s.get_json(
            f"/api/statsstream/{event_id}/info/aggregated/?lang={lang}",
            referer=self._referer(event_id),
        )
        return parsers.parse_info_aggregated(raw) if raw else None

    async def get_config(self, event_id: int) -> Optional[MatchConfig]:
        raw = await self._s.get_json(
            f"/api/statsstream/{event_id}/config/",
            referer=self._referer(event_id),
        )
        return parsers.parse_config(raw) if raw else None

    async def get_stats_detailed(self, event_id: int) -> Optional[DetailedStats]:
        raw = await self._s.get_json(
            f"/api/statsstream/{event_id}/stats/detailed/",
            referer=self._referer(event_id),
        )
        return parsers.parse_stats_detailed(raw, event_id=event_id) if raw else None

    async def get_stats_players(self, event_id: int) -> Optional[PlayerStats]:
        raw = await self._s.get_json(
            f"/api/statsstream/{event_id}/stats/players/",
            referer=self._referer(event_id),
        )
        return parsers.parse_stats_players(raw, event_id=event_id) if raw else None

    async def get_momentum(self, event_id: int) -> Optional[Momentum]:
        raw = await self._s.get_json(
            f"/api/statsstream/{event_id}/momentum/",
            referer=self._referer(event_id),
        )
        return parsers.parse_momentum(raw, event_id=event_id) if raw else None

    async def get_lineups(self, event_id: int) -> Optional[Lineups]:
        raw = await self._s.get_json(
            f"/api/statsstream/{event_id}/lineups/",
            referer=self._referer(event_id),
        )
        return parsers.parse_lineups(raw, event_id=event_id) if raw else None

    async def get_h2h(self, event_id: int) -> Optional[H2H]:
        raw = await self._s.get_json(
            f"/api/statsstream/{event_id}/h2h/",
            referer=self._referer(event_id),
        )
        return parsers.parse_h2h(raw, event_id=event_id) if raw else None

    async def healthcheck(self, event_id: int = _HEALTHCHECK_EVENT_ID) -> bool:
        """True quando `config/` retorna 200 + JSON parseável."""
        try:
            cfg = await self.get_config(event_id)
        except Exception as e:  # fronteira: log para diagnóstico, não propaga
            log.warning("healthcheck.error event_id=%d err=%s", event_id, e)
            return False
        return cfg is not None
