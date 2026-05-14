"""Unit tests dos adapters Betano (odds + stats) — Fase C.

Verifica:
- `min_score` bloqueia chamada quando placar < limiar.
- `event_id` cache evita 2ª chamada ao catalog.
- Conversão para CanonicalOverUnder preserva `market_code`.
- Fluxo com fixture_repo (mock): get → cache hit → upsert.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

import pytest

from data.odds_provider import CanonicalFixture
from data.providers.betano import BetanoOverUnder
from data.providers.betano.odds_adapter import BetanoOddsProvider


def _fixture(fid: int = 1) -> CanonicalFixture:
    return CanonicalFixture(
        fixture_id=fid,
        home_team="Cruzeiro",
        away_team="Goiás",
        league_id=10008,
        starts_at_utc=datetime(2026, 5, 13, 0, 30, tzinfo=timezone.utc),
        score_home=0, score_away=0,
    )


def _bou(linha: float = 9.5, over: float = 1.85, under: float = 1.95) -> BetanoOverUnder:
    return BetanoOverUnder(
        event_id=84586925,
        market_code="CNOU",
        handicap=linha,
        odd_over=over,
        odd_under=under,
    )


class _MarketsStub:
    def __init__(self):
        self.corners_calls = 0
        self.cards_calls = 0
        self.corners_result: Optional[BetanoOverUnder] = _bou()
        self.cards_result: Optional[BetanoOverUnder] = _bou(linha=5.5)

    async def fetch_corners(self, event_id, linha=None):
        self.corners_calls += 1
        return self.corners_result

    async def fetch_cards(self, event_id, linha=None):
        self.cards_calls += 1
        return self.cards_result


class _CatalogStub:
    def __init__(self, found_event_id: Optional[int] = 84586925):
        self.find_calls = 0
        self.list_calls = 0
        self._found = found_event_id

    async def find_event_by_fixture(self, fixture_id, team_home, team_away,
                                     kickoff_at, league_id_hint=None):
        self.find_calls += 1
        return self._found

    def prime_fixture_map(self, fixture_id, event_id):
        pass

    async def list_live_events(self):
        self.list_calls += 1
        return [object()] if self._found else []


class _RepoStub:
    def __init__(self, stored: Optional[int] = None):
        self.get_calls = 0
        self.upsert_calls = 0
        self._stored = stored
        self.last_upsert: Optional[dict] = None

    async def get_betano_event_id(self, fixture_id):
        self.get_calls += 1
        return self._stored

    async def upsert(self, **kwargs):
        self.upsert_calls += 1
        self.last_upsert = kwargs


@pytest.mark.asyncio
async def test_betano_odds_respects_min_score_threshold():
    markets = _MarketsStub()
    catalog = _CatalogStub()
    prov = BetanoOddsProvider(session=None, markets=markets, catalog=catalog, min_score=2)
    res = await prov.get_corners(_fixture(), current_score=1, line=9.5)
    assert res is None
    assert markets.corners_calls == 0
    assert catalog.find_calls == 0


@pytest.mark.asyncio
async def test_betano_odds_caches_event_id_after_first_resolve():
    markets = _MarketsStub()
    catalog = _CatalogStub(found_event_id=999)
    prov = BetanoOddsProvider(session=None, markets=markets, catalog=catalog)
    fx = _fixture()
    r1 = await prov.get_corners(fx, current_score=0, line=9.5)
    r2 = await prov.get_corners(fx, current_score=0, line=9.5)
    assert r1 is not None and r2 is not None
    assert catalog.find_calls == 1  # cache hit na 2ª
    assert markets.corners_calls == 2


@pytest.mark.asyncio
async def test_betano_odds_to_canonical_preserves_market_code():
    markets = _MarketsStub()
    markets.corners_result = _bou(linha=10.5, over=1.62, under=2.30)
    catalog = _CatalogStub()
    prov = BetanoOddsProvider(session=None, markets=markets, catalog=catalog)
    res = await prov.get_corners(_fixture(), current_score=0, line=9.5)
    assert res is not None
    assert res.source == "betano"
    assert res.market_code == "CNOU"
    assert res.linha == 10.5
    assert res.odd_over == 1.62


@pytest.mark.asyncio
async def test_betano_odds_uses_repo_before_catalog():
    markets = _MarketsStub()
    catalog = _CatalogStub(found_event_id=None)  # se catalog for chamado, falha
    repo = _RepoStub(stored=42)
    prov = BetanoOddsProvider(session=None, markets=markets, catalog=catalog,
                               fixture_repo=repo)
    res = await prov.get_corners(_fixture(), current_score=0, line=9.5)
    assert res is not None
    assert catalog.find_calls == 0
    assert repo.get_calls == 1


@pytest.mark.asyncio
async def test_betano_odds_upserts_repo_after_fuzzy_match():
    markets = _MarketsStub()
    catalog = _CatalogStub(found_event_id=84586925)
    repo = _RepoStub(stored=None)
    prov = BetanoOddsProvider(session=None, markets=markets, catalog=catalog,
                               fixture_repo=repo)
    await prov.get_corners(_fixture(fid=123), current_score=0, line=9.5)
    assert repo.upsert_calls == 1
    assert repo.last_upsert["fixture_id"] == 123
    assert repo.last_upsert["betano_event_id"] == 84586925


@pytest.mark.asyncio
async def test_betano_odds_returns_none_when_catalog_misses_and_no_repo():
    markets = _MarketsStub()
    catalog = _CatalogStub(found_event_id=None)
    prov = BetanoOddsProvider(session=None, markets=markets, catalog=catalog)
    res = await prov.get_corners(_fixture(), current_score=0, line=9.5)
    assert res is None
    assert markets.corners_calls == 0
