"""Unit tests do BetanoStatsWorker (Fase E.1 PARTE E')."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

import pytest

from data.odds_provider import CanonicalFixture
from data.repositories.stats_history import StatsHistoryEntry
from data.services.stats_window_calculator import StatsWindowCalculator
from data.stats_provider import CanonicalStats
from workers.betano_stats_worker import BetanoStatsWorker


def _fixture(fid: int = 999) -> CanonicalFixture:
    return CanonicalFixture(
        fixture_id=fid,
        home_team="Home",
        away_team="Away",
        league_id=1,
        starts_at_utc=datetime(2026, 5, 16, 20, 0, 0, tzinfo=timezone.utc),
    )


def _stats(
    fid: int = 999,
    version: int = 1,
    corners_h: int = 2,
    corners_a: int = 1,
    yellow_h: int = 1,
    yellow_a: int = 0,
    captured_at_ts: float = 1778869885.0,
) -> CanonicalStats:
    return CanonicalStats(
        fixture_id=fid,
        source="bridge_betano",
        minute=30,
        score_home=1,
        score_away=0,
        corners_home=corners_h,
        corners_away=corners_a,
        yellow_cards_home=yellow_h,
        yellow_cards_away=yellow_a,
        red_cards_home=0,
        red_cards_away=0,
        shots_on_target_home=7,
        shots_on_target_away=4,
        dangerous_attacks_home=0,
        dangerous_attacks_away=0,
        possession_home=0,
        possession_away=0,
        x_goals_home=0.38,
        x_goals_away=0.13,
        version=version,
        second_since_start=1800,
        raw={"event_id": 42, "captured_at": captured_at_ts},
    )


class _FakeAdapter:
    def __init__(self, results: list[Optional[CanonicalStats]]):
        self._results = list(results)
        self.calls: list[int] = []

    async def get_stats(self, fixture: CanonicalFixture):
        self.calls.append(fixture.fixture_id)
        return self._results.pop(0) if self._results else None


class _FakeRepo:
    def __init__(self, history_rows: Optional[list[dict]] = None):
        self.inserts: list[StatsHistoryEntry] = []
        self.list_calls: list[tuple] = []
        self._history = history_rows or []
        self.insert_raises: Optional[Exception] = None

    async def insert(self, entry: StatsHistoryEntry):
        if self.insert_raises is not None:
            raise self.insert_raises
        self.inserts.append(entry)
        return len(self.inserts)

    async def list_recent_for_fixture(self, fixture_id, since=None, limit=200):
        self.list_calls.append((fixture_id, since, limit))
        return self._history


@pytest.mark.asyncio
async def test_poll_happy_path_returns_enriched_stats_and_persists():
    """Snapshot → calc.add_snapshot → repo.insert (1 insert, sem janelas no 1º)."""
    snap = _stats()
    adapter = _FakeAdapter([snap])
    repo = _FakeRepo(history_rows=[])
    calc = StatsWindowCalculator(history_size=10)
    worker = BetanoStatsWorker(adapter, repo, calc, bootstrap_lookback_min=20)

    out = await worker.poll(_fixture(999))

    assert out is not None
    assert out.fixture_id == 999
    # 1º snapshot → sem janelas (só 1 elemento no deque).
    assert out.corners_last_5min is None
    assert out.yellow_last_5min is None
    # Persistiu 1.
    assert len(repo.inserts) == 1
    assert repo.inserts[0].source == "bridge_betano"
    assert repo.inserts[0].version == 1
    # Bootstrap foi feito.
    assert repo.list_calls and repo.list_calls[0][0] == 999


@pytest.mark.asyncio
async def test_poll_returns_none_when_adapter_returns_none():
    """304/erro/no-mapping → None do adapter → worker NÃO persiste."""
    adapter = _FakeAdapter([None])
    repo = _FakeRepo()
    calc = StatsWindowCalculator(history_size=10)
    worker = BetanoStatsWorker(adapter, repo, calc)

    out = await worker.poll(_fixture(999))
    assert out is None
    assert repo.inserts == []


@pytest.mark.asyncio
async def test_poll_second_call_fills_windows_from_first_snapshot():
    """2 polls em sequência: 2º snapshot enriquece janelas com delta vs 1º."""
    snap_t0 = _stats(version=1, corners_h=2, corners_a=1, yellow_h=1, yellow_a=0,
                     captured_at_ts=1778869800.0)  # T+0s
    snap_t180 = _stats(version=2, corners_h=4, corners_a=2, yellow_h=2, yellow_a=1,
                       captured_at_ts=1778869980.0)  # T+180s = T+3min
    adapter = _FakeAdapter([snap_t0, snap_t180])
    repo = _FakeRepo(history_rows=[])
    calc = StatsWindowCalculator(history_size=10)
    worker = BetanoStatsWorker(adapter, repo, calc)

    fix = _fixture(999)
    await worker.poll(fix)
    out2 = await worker.poll(fix)

    assert out2 is not None
    # corners_total: 3 -> 6, delta = 3. Janela 5min cobre os 3 min.
    assert out2.corners_last_5min == 3
    assert out2.corners_last_10min == 3
    # yellow_total: 1 -> 3, delta = 2.
    assert out2.yellow_last_5min == 2
    assert out2.yellow_last_10min == 2
    # 2 inserts no repo (idempotência via UNIQUE version é checada no DB).
    assert len(repo.inserts) == 2


@pytest.mark.asyncio
async def test_poll_swallows_repo_insert_error_but_still_returns_stats():
    """Erro de persistência (UNIQUE/IO) é log WARN, não-fatal — caller recebe stats."""
    snap = _stats()
    adapter = _FakeAdapter([snap])
    repo = _FakeRepo()
    repo.insert_raises = RuntimeError("simulated unique violation")
    calc = StatsWindowCalculator(history_size=10)
    worker = BetanoStatsWorker(adapter, repo, calc)

    out = await worker.poll(_fixture(999))
    assert out is not None  # stats devolvido mesmo com erro de persist
    assert out.fixture_id == 999


@pytest.mark.asyncio
async def test_poll_with_is_cached_does_not_add_to_calculator_but_persists_with_cached_freshness():
    """is_cached=True → calculator NÃO ganha snapshot novo; repo recebe freshness=cached."""
    snap_fresh = _stats(version=1, corners_h=2, corners_a=1, captured_at_ts=1778869800.0)
    snap_cached = CanonicalStats(
        **{
            **{
                k: getattr(snap_fresh, k)
                for k in snap_fresh.__dataclass_fields__.keys()
            },
            "is_cached": True,
        }
    )
    adapter = _FakeAdapter([snap_fresh, snap_cached])
    repo = _FakeRepo(history_rows=[])
    calc = StatsWindowCalculator(history_size=10)
    worker = BetanoStatsWorker(adapter, repo, calc)

    fix = _fixture(999)
    await worker.poll(fix)  # 1º: fresh entra no deque
    await worker.poll(fix)  # 2º: cached NÃO entra

    assert len(repo.inserts) == 2
    assert repo.inserts[0].raw["freshness"] == "fresh"
    assert repo.inserts[1].raw["freshness"] == "cached"
    # Deque tem só 1 snapshot (do fresh) — cached não duplicou.
    assert len(calc._windows[999]) == 1


@pytest.mark.asyncio
async def test_poll_freshness_fresh_when_not_cached():
    """is_cached=False (default) → freshness=fresh."""
    adapter = _FakeAdapter([_stats()])
    repo = _FakeRepo()
    calc = StatsWindowCalculator(history_size=10)
    worker = BetanoStatsWorker(adapter, repo, calc)
    await worker.poll(_fixture(999))
    assert repo.inserts[0].raw["freshness"] == "fresh"


@pytest.mark.asyncio
async def test_forget_fixture_clears_calculator_and_marks_for_rebootstrap():
    snap = _stats()
    adapter = _FakeAdapter([snap, snap])
    repo = _FakeRepo(history_rows=[])
    calc = StatsWindowCalculator(history_size=10)
    worker = BetanoStatsWorker(adapter, repo, calc)

    fix = _fixture(999)
    await worker.poll(fix)
    assert 999 in worker._bootstrapped
    worker.forget_fixture(999)
    assert 999 not in worker._bootstrapped
    # Próximo poll re-bootstrapa (list_recent é chamado novamente).
    repo.list_calls.clear()
    await worker.poll(fix)
    assert any(call[0] == 999 for call in repo.list_calls)
