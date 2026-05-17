"""Unit tests do CachedBetanoOddsProvider (Fase K — P4-B, 2026-05-17)."""
from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Optional

import pytest

from data.odds_provider import CanonicalFixture, CanonicalOverUnder
from data.providers.betano_bridge.cached_odds_provider import CachedBetanoOddsProvider
from data.providers.betano_bridge.odds_cache import OddsCache


def _fixture(fid: int = 100) -> CanonicalFixture:
    return CanonicalFixture(
        fixture_id=fid,
        home_team="Sevilla",
        away_team="Real Madrid",
        league_id=140,
        starts_at_utc=datetime(2026, 5, 17, 18, 0, tzinfo=timezone.utc),
    )


def _odds(linha: float = 9.5) -> CanonicalOverUnder:
    return CanonicalOverUnder(
        source="betano_bridge", market_kind="corners",
        market_code="CNOU", linha=linha, odd_over=1.62, odd_under=2.15,
    )


class _FakeAdapter:
    name = "betano_bridge"

    def __init__(self, corners_result=None, cards_result=None, raises: Optional[Exception] = None):
        self._corners = corners_result
        self._cards = cards_result
        self._raises = raises
        self.calls = []

    async def get_corners(self, fixture, current_score, line, **ctx):
        self.calls.append(("corners", fixture.fixture_id))
        if self._raises:
            raise self._raises
        return self._corners

    async def get_cards(self, fixture, current_score, line, **ctx):
        self.calls.append(("cards", fixture.fixture_id))
        if self._raises:
            raise self._raises
        return self._cards

    async def healthcheck(self):
        return True


@pytest.mark.asyncio
async def test_returns_fresh_from_bridge_and_caches():
    cache = OddsCache()
    adapter = _FakeAdapter(corners_result=_odds(9.5))
    provider = CachedBetanoOddsProvider(adapter, cache)
    result = await provider.get_corners(_fixture(), current_score=0)
    assert result is not None
    assert result.source == "betano_bridge"
    assert not result.is_stale
    assert result.age_seconds == 0
    # cacheado
    assert cache.get(100, "corners") is not None


@pytest.mark.asyncio
async def test_returns_cache_when_bridge_returns_none():
    cache = OddsCache()
    cache.put(100, "corners", _odds(9.5))
    adapter = _FakeAdapter(corners_result=None)  # bridge falhou
    provider = CachedBetanoOddsProvider(adapter, cache)
    result = await provider.get_corners(_fixture(), current_score=0)
    assert result is not None
    assert result.source == "betano_cache"  # fresh ainda
    assert not result.is_stale


@pytest.mark.asyncio
async def test_returns_stale_when_bridge_fails_and_cache_aged(monkeypatch):
    cache = OddsCache()
    cache.put(100, "corners", _odds(9.5))
    # avança 35s (TTL corners=30 → stale entre 30 e 60)
    real_time = time.time
    monkeypatch.setattr(time, "time", lambda: real_time() + 35)
    adapter = _FakeAdapter(corners_result=None)
    provider = CachedBetanoOddsProvider(adapter, cache)
    result = await provider.get_corners(_fixture(), current_score=0)
    assert result is not None
    assert result.source == "betano_cache_stale"
    assert result.is_stale is True
    assert result.age_seconds >= 35


@pytest.mark.asyncio
async def test_returns_none_when_cache_expired(monkeypatch):
    cache = OddsCache()
    cache.put(100, "corners", _odds(9.5))
    # avança 70s — > 2× TTL → expired
    real_time = time.time
    monkeypatch.setattr(time, "time", lambda: real_time() + 70)
    adapter = _FakeAdapter(corners_result=None)
    provider = CachedBetanoOddsProvider(adapter, cache)
    result = await provider.get_corners(_fixture(), current_score=0)
    assert result is None  # sem AF fallback


@pytest.mark.asyncio
async def test_returns_none_when_bridge_fails_and_no_cache():
    cache = OddsCache()  # vazio
    adapter = _FakeAdapter(corners_result=None)
    provider = CachedBetanoOddsProvider(adapter, cache)
    result = await provider.get_corners(_fixture(), current_score=0)
    assert result is None


@pytest.mark.asyncio
async def test_adapter_exception_treated_as_failure():
    cache = OddsCache()
    cache.put(100, "corners", _odds(9.5))
    adapter = _FakeAdapter(raises=RuntimeError("connect fail"))
    provider = CachedBetanoOddsProvider(adapter, cache)
    result = await provider.get_corners(_fixture(), current_score=0)
    # Exceção do bridge cai pra cache, retorna fresh
    assert result is not None
    assert result.source == "betano_cache"


@pytest.mark.asyncio
async def test_cards_path_independent_of_corners():
    cache = OddsCache()
    adapter = _FakeAdapter(
        corners_result=_odds(9.5),
        cards_result=CanonicalOverUnder(
            source="betano_bridge", market_kind="cards", market_code="TCOU",
            linha=3.5, odd_over=1.70, odd_under=2.10,
        ),
    )
    provider = CachedBetanoOddsProvider(adapter, cache)
    res_corners = await provider.get_corners(_fixture(), current_score=0)
    res_cards = await provider.get_cards(_fixture(), current_score=0)
    assert res_corners.market_kind == "corners"
    assert res_cards.market_kind == "cards"
    assert cache.stats()["total"] == 2


@pytest.mark.asyncio
async def test_healthcheck_delegates_to_adapter():
    cache = OddsCache()
    adapter = _FakeAdapter()
    provider = CachedBetanoOddsProvider(adapter, cache)
    assert await provider.healthcheck() is True


@pytest.mark.asyncio
async def test_fresh_overwrites_stale_cache(monkeypatch):
    cache = OddsCache()
    cache.put(100, "corners", _odds(9.5))
    real_time = time.time
    monkeypatch.setattr(time, "time", lambda: real_time() + 35)
    # bridge volta — retorna fresh, cacheia novo
    new = _odds(10.5)
    adapter = _FakeAdapter(corners_result=new)
    provider = CachedBetanoOddsProvider(adapter, cache)
    result = await provider.get_corners(_fixture(), current_score=0)
    assert result.source == "betano_bridge"
    assert result.linha == 10.5
    assert not result.is_stale
