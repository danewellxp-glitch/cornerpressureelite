"""Unit tests do CompositeOddsProvider / CompositeStatsProvider + drift log.

Mocka os providers via fakes assíncronos simples — sem dependências externas.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import pytest

from data.odds_provider import (
    CanonicalFixture,
    CanonicalOverUnder,
    CompositeOddsProvider,
    DRIFT_LOG_PATH,
)
from data.stats_provider import CanonicalStats, CompositeStatsProvider


def _fixture(fixture_id: int = 1) -> CanonicalFixture:
    return CanonicalFixture(
        fixture_id=fixture_id,
        home_team="Cruzeiro",
        away_team="Goiás",
        league_id=10008,
        starts_at_utc=datetime(2026, 5, 13, 0, 30, tzinfo=timezone.utc),
    )


def _ou(source: str, linha: float = 9.5, over: float = 1.85, under: float = 1.95) -> CanonicalOverUnder:
    return CanonicalOverUnder(
        source=source, market_kind="corners", market_code="CNOU",
        linha=linha, odd_over=over, odd_under=under,
    )


class _FakeOdds:
    def __init__(self, name: str, corners: Optional[CanonicalOverUnder] = None,
                 cards: Optional[CanonicalOverUnder] = None,
                 health: bool = True, raises: bool = False):
        self.name = name
        self._corners = corners
        self._cards = cards
        self._health = health
        self._raises = raises
        self.corners_calls = 0
        self.cards_calls = 0

    async def get_corners(self, fixture, current_score):
        self.corners_calls += 1
        if self._raises:
            raise RuntimeError("boom")
        return self._corners

    async def get_cards(self, fixture, current_score):
        self.cards_calls += 1
        if self._raises:
            raise RuntimeError("boom")
        return self._cards

    async def healthcheck(self):
        return self._health


@pytest.mark.asyncio
async def test_composite_returns_primary_when_available():
    p1 = _FakeOdds("p1", corners=_ou("p1", linha=9.5))
    p2 = _FakeOdds("p2", corners=_ou("p2", linha=10.5))
    comp = CompositeOddsProvider([p1, p2])
    res = await comp.get_corners(_fixture(), current_score=0)
    assert res is not None
    assert res.source == "p1"
    assert p1.corners_calls == 1
    # short-circuit: p2 não foi chamado
    assert p2.corners_calls == 0


@pytest.mark.asyncio
async def test_composite_falls_back_when_primary_returns_none():
    p1 = _FakeOdds("p1", corners=None)
    p2 = _FakeOdds("p2", corners=_ou("p2"))
    comp = CompositeOddsProvider([p1, p2])
    res = await comp.get_corners(_fixture(), current_score=0)
    assert res is not None
    assert res.source == "p2"
    assert p1.corners_calls == 1
    assert p2.corners_calls == 1


@pytest.mark.asyncio
async def test_composite_falls_back_when_primary_raises():
    p1 = _FakeOdds("p1", raises=True)
    p2 = _FakeOdds("p2", corners=_ou("p2"))
    comp = CompositeOddsProvider([p1, p2])
    res = await comp.get_corners(_fixture(), current_score=0)
    assert res is not None
    assert res.source == "p2"


@pytest.mark.asyncio
async def test_composite_returns_none_when_all_fail():
    p1 = _FakeOdds("p1", corners=None)
    p2 = _FakeOdds("p2", corners=None)
    comp = CompositeOddsProvider([p1, p2])
    assert await comp.get_corners(_fixture(), current_score=0) is None


@pytest.mark.asyncio
async def test_composite_drift_check_calls_all_providers_and_writes_jsonl(tmp_path, monkeypatch):
    drift_log = tmp_path / "provider_drift.jsonl"
    monkeypatch.setattr("data.odds_provider.DRIFT_LOG_PATH", drift_log)

    p1 = _FakeOdds("betano", corners=_ou("betano", linha=9.5, over=1.85))
    p2 = _FakeOdds("apifootball", corners=_ou("apifootball", linha=9.5, over=1.90))
    comp = CompositeOddsProvider([p1, p2], drift_check=True)

    res = await comp.get_corners(_fixture(7), current_score=0)
    assert res is not None
    assert res.source == "betano"
    assert p1.corners_calls == 1
    assert p2.corners_calls == 1  # drift_check chama os dois
    assert drift_log.exists()
    lines = drift_log.read_text().splitlines()
    assert len(lines) == 1
    entry = json.loads(lines[0])
    assert entry["fixture_id"] == 7
    assert {p["name"] for p in entry["providers"]} == {"betano", "apifootball"}


@pytest.mark.asyncio
async def test_composite_drift_check_skips_jsonl_when_only_one_responds(tmp_path, monkeypatch):
    drift_log = tmp_path / "provider_drift.jsonl"
    monkeypatch.setattr("data.odds_provider.DRIFT_LOG_PATH", drift_log)
    p1 = _FakeOdds("betano", corners=_ou("betano"))
    p2 = _FakeOdds("apifootball", corners=None)
    comp = CompositeOddsProvider([p1, p2], drift_check=True)
    res = await comp.get_corners(_fixture(), current_score=0)
    assert res is not None
    assert not drift_log.exists()


@pytest.mark.asyncio
async def test_composite_healthcheck_returns_true_if_any_healthy():
    p1 = _FakeOdds("p1", health=False)
    p2 = _FakeOdds("p2", health=True)
    comp = CompositeOddsProvider([p1, p2])
    assert await comp.healthcheck() is True


@pytest.mark.asyncio
async def test_composite_healthcheck_returns_false_if_all_unhealthy():
    p1 = _FakeOdds("p1", health=False)
    p2 = _FakeOdds("p2", health=False)
    comp = CompositeOddsProvider([p1, p2])
    assert await comp.healthcheck() is False


@pytest.mark.asyncio
async def test_composite_persistence_worker_receives_primary(monkeypatch):
    """Worker injetado é chamado com `enqueue_from_dispatch`."""
    calls: list[dict] = []

    class _FakeWorker:
        def enqueue_from_dispatch(self, *, fixture, market_kind, primary, all_results):
            calls.append({
                "fixture_id": fixture.fixture_id,
                "market_kind": market_kind,
                "source": primary.source,
                "n_results": len(all_results),
            })

    p1 = _FakeOdds("betano", corners=_ou("betano"))
    comp = CompositeOddsProvider([p1], persistence_worker=_FakeWorker())
    res = await comp.get_corners(_fixture(99), current_score=0)
    assert res is not None
    assert calls == [{"fixture_id": 99, "market_kind": "corners",
                       "source": "betano", "n_results": 1}]


# ============================================================
# CompositeStatsProvider
# ============================================================


def _stats(source: str, corners_h: int = 3, corners_a: int = 2) -> CanonicalStats:
    return CanonicalStats(
        fixture_id=1, source=source, minute=55,
        score_home=0, score_away=0,
        corners_home=corners_h, corners_away=corners_a,
        yellow_cards_home=2, yellow_cards_away=1,
        red_cards_home=0, red_cards_away=0,
        shots_on_target_home=5, shots_on_target_away=2,
        dangerous_attacks_home=20, dangerous_attacks_away=10,
        possession_home=60, possession_away=40,
        x_goals_home=0.5, x_goals_away=0.1,
    )


class _FakeStats:
    def __init__(self, name: str, result: Optional[CanonicalStats] = None, raises: bool = False):
        self.name = name
        self._result = result
        self._raises = raises
        self.calls = 0

    async def get_stats(self, fixture):
        self.calls += 1
        if self._raises:
            raise RuntimeError("boom")
        return self._result

    async def healthcheck(self):
        return True


@pytest.mark.asyncio
async def test_composite_stats_returns_primary_when_available():
    p1 = _FakeStats("p1", result=_stats("p1"))
    p2 = _FakeStats("p2", result=_stats("p2"))
    comp = CompositeStatsProvider([p1, p2])
    res = await comp.get_stats(_fixture())
    assert res is not None and res.source == "p1"
    assert p2.calls == 0


@pytest.mark.asyncio
async def test_composite_stats_falls_back_on_none_and_exception():
    p1 = _FakeStats("p1", result=None)
    p2 = _FakeStats("p2", raises=True)
    p3 = _FakeStats("p3", result=_stats("p3"))
    comp = CompositeStatsProvider([p1, p2, p3])
    res = await comp.get_stats(_fixture())
    assert res is not None and res.source == "p3"
