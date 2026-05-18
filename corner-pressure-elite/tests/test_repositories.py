"""Unit tests dos repositories (Fase D) com mocks de pool.

Verifica que o SQL emitido contém as cláusulas chave (ON CONFLICT, etc.) e que
os repos não vazam conexão.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import pytest

from data.repositories.fixture_map import FixtureMapRepo
from data.repositories.incidents_history import (
    IncidentHistoryEntry,
    IncidentsHistoryRepo,
)
from data.repositories.odds_history import OddsHistoryEntry, OddsHistoryRepo


class _FakeConn:
    def __init__(self):
        self.executes: list[tuple[str, tuple]] = []
        self.execute_many: list[tuple[str, list]] = []
        self.next_row: Any = None
        self.next_rows: list = []

    async def execute(self, sql: str, *args):
        self.executes.append((sql, args))

    async def executemany(self, sql: str, rows):
        self.execute_many.append((sql, list(rows)))

    async def fetchrow(self, sql: str, *args):
        return self.next_row

    async def fetch(self, sql: str, *args):
        return self.next_rows


class _FakePool:
    def __init__(self):
        self.conn = _FakeConn()

    def acquire(self):
        pool = self

        class _Ctx:
            async def __aenter__(self_inner):
                return pool.conn

            async def __aexit__(self_inner, exc_type, exc, tb):
                return None

        return _Ctx()


# ============================================================
# FixtureMapRepo
# ============================================================


@pytest.mark.asyncio
async def test_fixture_map_repo_upsert_uses_on_conflict():
    pool = _FakePool()
    repo = FixtureMapRepo(pool)
    await repo.upsert(
        fixture_id=1,
        betano_event_id=84586925,
        home_team="A", away_team="B", league_id=1,
        kickoff_utc=datetime(2026, 5, 13, tzinfo=timezone.utc),
        resolved_via="fuzzy_match",
    )
    sql, args = pool.conn.executes[0]
    assert "INSERT INTO betano_fixture_map" in sql
    assert "ON CONFLICT (fixture_id) DO UPDATE" in sql
    assert args[0] == 1
    assert args[1] == 84586925


@pytest.mark.asyncio
async def test_fixture_map_repo_get_returns_int_or_none():
    pool = _FakePool()
    pool.conn.next_row = {"betano_event_id": 42}
    repo = FixtureMapRepo(pool)
    assert await repo.get_betano_event_id(1) == 42
    pool.conn.next_row = None
    assert await repo.get_betano_event_id(2) is None


# ============================================================
# OddsHistoryRepo
# ============================================================


@pytest.mark.asyncio
async def test_odds_history_bulk_insert_sends_all_rows():
    pool = _FakePool()
    repo = OddsHistoryRepo(pool)
    entries = [
        OddsHistoryEntry(
            fixture_id=i, source="betano", market_kind="corners",
            market_code="CNOU", linha=9.5, odd_over=1.85, odd_under=1.95,
            raw={"i": i},
        )
        for i in range(3)
    ]
    n = await repo.bulk_insert(entries)
    assert n == 3
    sql, rows = pool.conn.execute_many[0]
    assert "INSERT INTO odds_history" in sql
    assert len(rows) == 3
    # 18 colunas: 15 originais + is_stale + source_age_seconds (P4-B) + sofa_event_id (Fase H A1.3)
    assert all(len(r) == 18 for r in rows)


@pytest.mark.asyncio
async def test_odds_history_bulk_insert_noop_on_empty():
    pool = _FakePool()
    repo = OddsHistoryRepo(pool)
    assert await repo.bulk_insert([]) == 0
    assert pool.conn.execute_many == []


# ============================================================
# IncidentsHistoryRepo
# ============================================================


@pytest.mark.asyncio
async def test_incidents_history_bulk_insert_has_on_conflict_do_nothing():
    pool = _FakePool()
    repo = IncidentsHistoryRepo(pool)
    entries = [
        IncidentHistoryEntry(
            fixture_id=1, opta_match_id="opta-1", event_uid="u1", event_type=0,
            period_id=1, minute=10, seconds=0,
            team_id="t", player_id="p",
            x=10.0, y=20.0, x_end=None, y_end=None,
            is_attack=True, is_dangerous_attack=False,
            is_possession=True, is_dangerous=False,
        )
    ]
    await repo.bulk_insert(entries)
    sql, rows = pool.conn.execute_many[0]
    assert "INSERT INTO incidents_history" in sql
    assert "ON CONFLICT (opta_match_id, event_uid) DO NOTHING" in sql
    assert len(rows[0]) == 18  # 17 colunas + raw
