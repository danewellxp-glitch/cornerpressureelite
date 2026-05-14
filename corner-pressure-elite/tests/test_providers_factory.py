"""Unit tests do factory de providers (Fase C).

Verifica que feature flag escolhe a stack correta sem precisar de cookies
Betano / Postgres.
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from data.odds_provider import CompositeOddsProvider
from data.providers.factory import build_providers
from data.stats_provider import CompositeStatsProvider


class _FakeAPIClient:
    """Quack like APIFootballClient — apenas para o factory."""

    async def get_live_odds(self, fixture_id): return {}
    async def get_live_odds_cards(self, fixture_id): return {}
    async def get_fixture_by_id(self, fixture_id): return None
    async def get_statistics(self, fixture_id): return []
    async def check_status(self): return {"requests": 1}
    async def close(self): pass


def _settings(**overrides):
    base = SimpleNamespace(
        USE_NEW_PROVIDERS=False,
        DRIFT_CHECK_PROVIDERS=False,
        MIN_SCORE_TO_FETCH_ODDS=0,
        BETANO_COOKIES_PATH="/nonexistent.json",
        WEBSHARE_PROXIES="",
    )
    for k, v in overrides.items():
        setattr(base, k, v)
    return base


@pytest.mark.asyncio
async def test_factory_returns_legacy_stack_when_flag_off():
    odds, stats, shutdown = await build_providers(_settings(), _FakeAPIClient())
    try:
        assert isinstance(odds, CompositeOddsProvider)
        assert isinstance(stats, CompositeStatsProvider)
        # apenas 1 provider (AF)
        assert len(odds._providers) == 1  # type: ignore[attr-defined]
        assert odds._providers[0].name == "apifootball"  # type: ignore[attr-defined]
        assert stats._providers[0].name == "apifootball"  # type: ignore[attr-defined]
    finally:
        await shutdown()


@pytest.mark.asyncio
async def test_factory_returns_new_stack_when_flag_on(tmp_path):
    cookies = tmp_path / "cookies.json"
    cookies.write_text('{"cookies": {"cf_clearance": "x"}, "kbversion": "3.41.0"}')
    settings = _settings(
        USE_NEW_PROVIDERS=True,
        DRIFT_CHECK_PROVIDERS=True,
        BETANO_COOKIES_PATH=str(cookies),
    )
    odds, stats, shutdown = await build_providers(settings, _FakeAPIClient())
    try:
        assert len(odds._providers) == 2  # type: ignore[attr-defined]
        names = [p.name for p in odds._providers]  # type: ignore[attr-defined]
        assert names == ["betano", "apifootball"]
        assert odds._drift_check is True  # type: ignore[attr-defined]
    finally:
        await shutdown()


@pytest.mark.asyncio
async def test_factory_propagates_persistence_worker_to_composite():
    """O worker injetado é guardado no CompositeOddsProvider."""
    class _W:
        def enqueue_from_dispatch(self, **kw): pass

    w = _W()
    odds, _stats, shutdown = await build_providers(
        _settings(), _FakeAPIClient(), odds_persistence_worker=w,
    )
    try:
        assert odds._persistence is w  # type: ignore[attr-defined]
    finally:
        await shutdown()
