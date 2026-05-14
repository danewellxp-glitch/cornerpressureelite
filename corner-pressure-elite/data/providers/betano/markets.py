"""Cliente REST para `/danae-webapi/api/live/events/{eventId}/latest`.

Snapshot de 281KB contém 279 mercados + 1153 selections. Filtragem por code
(CNOU, TCOU, etc) fica nos helpers de `parsers.extract_over_under`.
"""
from __future__ import annotations

import logging
from typing import Optional

from . import parsers
from .codes import MARKET_CODES_CARDS_MAIN, MARKET_CODES_CORNERS_MAIN
from .schemas import BetanoOverUnder, EventSnapshot
from .session import BetanoSession

log = logging.getLogger("cpes.betano.markets")


class BetanoMarkets:
    def __init__(self, session: BetanoSession):
        self._s = session

    def _referer(self, event_id: int) -> str:
        return f"https://www.betano.bet.br/live/_/{event_id}/"

    async def get_event_latest(self, event_id: int) -> Optional[EventSnapshot]:
        raw = await self._s.get_json(
            f"/danae-webapi/api/live/events/{event_id}/latest",
            referer=self._referer(event_id),
        )
        return parsers.parse_event_snapshot(raw) if raw else None

    async def fetch_corners(
        self, event_id: int, linha: Optional[float] = None
    ) -> Optional[BetanoOverUnder]:
        snap = await self.get_event_latest(event_id)
        if not snap:
            return None
        return parsers.extract_over_under(snap, type_code=MARKET_CODES_CORNERS_MAIN, linha=linha)

    async def fetch_cards(
        self, event_id: int, linha: Optional[float] = None
    ) -> Optional[BetanoOverUnder]:
        snap = await self.get_event_latest(event_id)
        if not snap:
            return None
        return parsers.extract_over_under(snap, type_code=MARKET_CODES_CARDS_MAIN, linha=linha)

    async def fetch_market_by_code(
        self, event_id: int, type_code: str, linha: Optional[float] = None
    ) -> Optional[BetanoOverUnder]:
        snap = await self.get_event_latest(event_id)
        if not snap:
            return None
        return parsers.extract_over_under(snap, type_code=type_code, linha=linha)
