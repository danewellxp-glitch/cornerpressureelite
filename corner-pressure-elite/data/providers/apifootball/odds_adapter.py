"""Adapter `OddsProvider` para `data.api_client.APIFootballClient`.

Wrapper fino: chama `get_live_odds` (corners) e `get_live_odds_cards` (cards),
normaliza o dict `{linha, odd_over, odd_under, ...}` em `CanonicalOverUnder`.
"""
from __future__ import annotations

import logging
from typing import Optional

from data.odds_provider import CanonicalFixture, CanonicalOverUnder

log = logging.getLogger("cpes.providers.apifootball.odds")


class APIFootballOddsProvider:
    name = "apifootball"

    def __init__(self, api_client):
        self._c = api_client

    async def get_corners(
        self, fixture: CanonicalFixture, current_score: int, line: float
    ) -> Optional[CanonicalOverUnder]:
        raw = await self._c.get_live_odds(fixture.fixture_id)
        return self._to_canonical(raw, market_kind="corners", requested_line=line)

    async def get_cards(
        self, fixture: CanonicalFixture, current_score: int, line: float
    ) -> Optional[CanonicalOverUnder]:
        raw = await self._c.get_live_odds_cards(fixture.fixture_id)
        return self._to_canonical(raw, market_kind="cards", requested_line=line)

    def _to_canonical(
        self, raw: Optional[dict], market_kind: str, requested_line: float
    ) -> Optional[CanonicalOverUnder]:
        if not raw:
            return None
        try:
            linha = float(raw["linha"])
            odd_over = float(raw["odd_over"])
            odd_under = float(raw["odd_under"])
        except (KeyError, TypeError, ValueError):
            log.warning(
                "apifootball.odds.parse_error market=%s keys=%s",
                market_kind, list(raw.keys()),
            )
            return None
        if linha <= 0 or odd_over <= 0 or odd_under <= 0:
            return None
        # API-Football retorna 1 linha "principal" por fixture; não dá pra
        # filtrar entre múltiplas. Devolve o que veio. Se diferir do que a
        # engine pediu, loga aviso — engine recalcula edge com a `linha` real.
        if requested_line and abs(linha - requested_line) >= 0.5:
            log.info(
                "apifootball.odds.line_mismatch market=%s requested=%.1f returned=%.1f",
                market_kind, requested_line, linha,
            )
        return CanonicalOverUnder(
            source=self.name,
            market_kind=market_kind,
            market_code="",
            linha=linha,
            odd_over=odd_over,
            odd_under=odd_under,
        )

    async def healthcheck(self) -> bool:
        try:
            status = await self._c.check_status()
        except Exception as e:
            log.warning("apifootball.healthcheck.error err=%s", e)
            return False
        # `check_status` retorna dict; vazio = falha
        return bool(status)
