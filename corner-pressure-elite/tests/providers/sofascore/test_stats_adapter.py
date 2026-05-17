"""Unit tests do SofaScoreStatsAdapter (Fase K.1 PARTE B.2)."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

import pytest

from data.odds_provider import CanonicalFixture
from data.providers.sofascore.stats_adapter import (
    SofaScoreStatsAdapter,
    _flatten_period,
    _parse_float,
    _parse_int,
    _parse_pct,
)


class _FakeClient:
    def __init__(self, stats=None, raises=False):
        self._stats = stats
        self._raises = raises
        self.calls: list[int] = []

    async def get_statistics(self, event_id):
        self.calls.append(event_id)
        if self._raises:
            raise RuntimeError("boom")
        return self._stats

    async def health(self):
        return True


def _fix(fixture_id=999) -> CanonicalFixture:
    return CanonicalFixture(
        fixture_id=fixture_id,
        home_team="A", away_team="B",
        league_id=325,
        starts_at_utc=datetime.now(timezone.utc),
        score_home=1, score_away=2,
    )


def _sample_period(name="ALL"):
    return {
        "period": name,
        "groups": [
            {
                "groupName": "Match overview",
                "statisticsItems": [
                    {"name": "Corner kicks", "home": "5", "away": "2"},
                    {"name": "Yellow cards", "home": 1, "away": 3},
                    {"name": "Ball possession", "home": "55%", "away": "45%"},
                    {"name": "Expected goals", "home": "1.42", "away": "0.61"},
                ],
            },
            {
                "groupName": "Shots",
                "statisticsItems": [
                    {"name": "Shots on target", "home": 4, "away": 2},
                    {"name": "Shots off target", "home": 3, "away": 1},
                    {"name": "Blocked shots", "home": 2, "away": 0},
                ],
            },
            {
                "groupName": "Attack",
                "statisticsItems": [
                    {"name": "Big chances", "home": 2, "away": 1},
                    {"name": "Big chances missed", "home": 1, "away": 0},
                ],
            },
        ],
    }


def test_parsers_robust():
    assert _parse_int("17") == 17 and _parse_int(17) == 17
    assert _parse_int(None) == 0 and _parse_int("abc") == 0
    assert _parse_pct("49%") == 49 and _parse_pct(50) == 50
    assert _parse_pct(None) == 0
    assert _parse_float("1.38") == 1.38 and _parse_float(0.5) == 0.5
    assert _parse_float(None) == 0.0


def test_flatten_period_collects_all_groups():
    p = _sample_period()
    flat = _flatten_period(p)
    assert flat["Corner kicks"] == {"home": "5", "away": "2"}
    assert flat["Yellow cards"]["home"] == 1
    assert flat["Big chances"]["away"] == 1


@pytest.mark.asyncio
async def test_no_resolver_returns_none():
    """Sem resolver injetado, adapter devolve None silencioso."""
    adapter = SofaScoreStatsAdapter(_FakeClient(), event_id_resolver=None)
    out = await adapter.get_stats(_fix())
    assert out is None


@pytest.mark.asyncio
async def test_resolver_returns_none_skips_client():
    """Resolver devolve None → adapter retorna None sem chamar client."""
    client = _FakeClient(stats=[_sample_period()])

    async def resolver(_): return None

    adapter = SofaScoreStatsAdapter(client, event_id_resolver=resolver)
    out = await adapter.get_stats(_fix())
    assert out is None
    assert client.calls == []


@pytest.mark.asyncio
async def test_normalize_extracts_all_period():
    client = _FakeClient(stats=[_sample_period("ALL"), _sample_period("1ST")])

    async def resolver(_): return 12345

    adapter = SofaScoreStatsAdapter(client, event_id_resolver=resolver)
    stats = await adapter.get_stats(_fix(fixture_id=999))
    assert stats is not None
    assert stats.source == "sofascore"
    assert stats.fixture_id == 999
    assert stats.corners_home == 5 and stats.corners_away == 2
    assert stats.yellow_cards_home == 1 and stats.yellow_cards_away == 3
    assert stats.possession_home == 55 and stats.possession_away == 45
    assert stats.x_goals_home == 1.42 and stats.x_goals_away == 0.61
    assert stats.shots_on_target_home == 4
    # K.1 PARTE B campos novos (enrichment SOFA_ONLY)
    assert stats.shots_off_target_home == 3
    assert stats.blocked_shots_home == 2
    assert stats.big_chances_home == 2
    assert stats.big_chances_missed_home == 1
    # GAPs SofaScore
    assert stats.red_cards_home == 0 and stats.dangerous_attacks_home == 0
    # stats_1h presente (porque sample tem 1ST)
    assert stats.stats_1h is not None
    assert stats.stats_1h["corners_home"] == 5


@pytest.mark.asyncio
async def test_no_all_period_returns_none():
    client = _FakeClient(stats=[_sample_period("1ST")])  # sem ALL

    async def resolver(_): return 12345

    adapter = SofaScoreStatsAdapter(client, event_id_resolver=resolver)
    out = await adapter.get_stats(_fix())
    assert out is None


@pytest.mark.asyncio
async def test_client_error_returns_none():
    client = _FakeClient(raises=True)

    async def resolver(_): return 12345

    adapter = SofaScoreStatsAdapter(client, event_id_resolver=resolver)
    out = await adapter.get_stats(_fix())
    assert out is None
