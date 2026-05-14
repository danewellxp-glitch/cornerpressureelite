"""Adapter `OddsProvider` para a stack Betano (Markets + Catalog).

Resolve `event_id` por:
1. Cache em memória local.
2. `fixture_repo` (Fase D — `betano_fixture_map` no Postgres).
3. Fuzzy match via `BetanoCatalog`.

`min_score` é um gatilho opcional: se o placar atual < min_score, devolve
None e o `CompositeOddsProvider` cai para o próximo provider sem custar uma
chamada de markets (281KB).
"""
from __future__ import annotations

import logging
from typing import Optional

from data.odds_provider import CanonicalFixture, CanonicalOverUnder

from .catalog import BetanoCatalog
from .markets import BetanoMarkets
from .session import BetanoSession

log = logging.getLogger("cpes.providers.betano.odds")


class BetanoOddsProvider:
    name = "betano"

    def __init__(
        self,
        session: BetanoSession,
        markets: BetanoMarkets,
        catalog: BetanoCatalog,
        min_score: int = 0,
        fixture_repo=None,
    ):
        self._session = session
        self._markets = markets
        self._catalog = catalog
        self._min_score = min_score
        self._fixture_repo = fixture_repo
        self._event_id_cache: dict[int, int] = {}

    async def get_corners(
        self, fixture: CanonicalFixture, current_score: int, line: float
    ) -> Optional[CanonicalOverUnder]:
        if current_score < self._min_score:
            return None
        event_id = await self._resolve_event_id(fixture)
        if not event_id:
            return None
        ou = await self._markets.fetch_corners(event_id)
        return self._to_canonical(ou, "corners", line) if ou else None

    async def get_cards(
        self, fixture: CanonicalFixture, current_score: int, line: float
    ) -> Optional[CanonicalOverUnder]:
        if current_score < self._min_score:
            return None
        event_id = await self._resolve_event_id(fixture)
        if not event_id:
            return None
        ou = await self._markets.fetch_cards(event_id)
        return self._to_canonical(ou, "cards", line) if ou else None

    async def healthcheck(self) -> bool:
        try:
            events = await self._catalog.list_live_events()
        except Exception as e:
            log.warning("betano.odds.healthcheck.error err=%s", e)
            return False
        return len(events) > 0

    # ---- helpers ----

    def _to_canonical(self, ou, market_kind: str, requested_line: float) -> CanonicalOverUnder:
        # `markets.fetch_*` devolve a linha "principal" oferecida pela Betano;
        # honrar `requested_line` exigiria endpoint diferente (catálogo). Por
        # ora, devolve o que veio e loga aviso se não bater.
        linha_real = float(ou.handicap)
        if requested_line and abs(linha_real - requested_line) >= 0.5:
            log.info(
                "betano.odds.line_mismatch market=%s requested=%.1f returned=%.1f",
                market_kind, requested_line, linha_real,
            )
        return CanonicalOverUnder(
            source=self.name,
            market_kind=market_kind,
            market_code=ou.market_code,
            linha=linha_real,
            odd_over=float(ou.odd_over),
            odd_under=float(ou.odd_under),
        )

    async def _resolve_event_id(self, fixture: CanonicalFixture) -> Optional[int]:
        # 1) cache local
        cached = self._event_id_cache.get(fixture.fixture_id)
        if cached:
            return cached
        # 2) repo (Fase D)
        if self._fixture_repo is not None:
            try:
                ev = await self._fixture_repo.get_betano_event_id(fixture.fixture_id)
            except Exception as e:
                log.warning("betano.fixture_repo.get_error fixture=%d err=%s", fixture.fixture_id, e)
                ev = None
            if ev:
                self._event_id_cache[fixture.fixture_id] = ev
                # prime catalog cache também — Fase B previu prime_fixture_map
                try:
                    self._catalog.prime_fixture_map(fixture.fixture_id, ev)
                except Exception:
                    pass
                return ev
        # 3) fuzzy match via catalog
        try:
            ev = await self._catalog.find_event_by_fixture(
                fixture_id=fixture.fixture_id,
                team_home=fixture.home_team,
                team_away=fixture.away_team,
                kickoff_at=fixture.starts_at_utc,
                league_id_hint=fixture.league_id,
            )
        except Exception as e:
            log.warning("betano.catalog.find_error fixture=%d err=%s", fixture.fixture_id, e)
            return None
        if not ev:
            return None
        self._event_id_cache[fixture.fixture_id] = ev
        if self._fixture_repo is not None:
            try:
                await self._fixture_repo.upsert(
                    fixture_id=fixture.fixture_id,
                    betano_event_id=ev,
                    home_team=fixture.home_team,
                    away_team=fixture.away_team,
                    league_id=fixture.league_id,
                    kickoff_utc=fixture.starts_at_utc,
                    resolved_via="fuzzy_match",
                )
            except Exception as e:
                log.warning("betano.fixture_repo.upsert_error fixture=%d err=%s", fixture.fixture_id, e)
        return ev
