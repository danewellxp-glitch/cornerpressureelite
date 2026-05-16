"""Unit tests do StatsHistoryRepo (Fase E.1 PARTE D) com pool fake."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import pytest

from data.repositories.stats_history import StatsHistoryEntry, StatsHistoryRepo


class _FakeConn:
    def __init__(self, fetchrow_returns: Any = None, fetch_returns: list | None = None):
        self.fetchrow_calls: list[tuple[str, tuple]] = []
        self.fetch_calls: list[tuple[str, tuple]] = []
        self._fetchrow_returns = fetchrow_returns
        self._fetch_returns = fetch_returns or []

    async def fetchrow(self, sql: str, *args):
        self.fetchrow_calls.append((sql, args))
        return self._fetchrow_returns

    async def fetch(self, sql: str, *args):
        self.fetch_calls.append((sql, args))
        return self._fetch_returns


class _FakePool:
    def __init__(self, conn: _FakeConn):
        self._conn = conn

    def acquire(self):
        conn = self._conn

        class _Ctx:
            async def __aenter__(self):
                return conn

            async def __aexit__(self, *a):
                return False

        return _Ctx()


@pytest.mark.asyncio
async def test_insert_emits_sql_with_on_conflict_do_nothing():
    """INSERT é idempotente via ON CONFLICT (fixture, source, version) DO NOTHING."""
    conn = _FakeConn(fetchrow_returns={"id": 42})
    repo = StatsHistoryRepo(_FakePool(conn))

    entry = StatsHistoryEntry(
        fixture_id=999,
        source="bridge_betano",
        version=1367,
        corners_home=3,
        corners_away=1,
        yellow_cards_home=1,
        yellow_cards_away=0,
    )
    result = await repo.insert(entry)
    assert result == 42

    sql, args = conn.fetchrow_calls[0]
    assert "INSERT INTO stats_history" in sql
    assert "ON CONFLICT (fixture_id, source, version)" in sql
    assert "DO NOTHING" in sql
    assert "RETURNING id" in sql
    # fixture_id e source vêm como 1º e 2º params.
    assert args[0] == 999
    assert args[1] == "bridge_betano"


@pytest.mark.asyncio
async def test_insert_returns_none_on_duplicate_version():
    """ON CONFLICT DO NOTHING + RETURNING devolve None quando duplica."""
    conn = _FakeConn(fetchrow_returns=None)  # Postgres devolve None no skip.
    repo = StatsHistoryRepo(_FakePool(conn))

    entry = StatsHistoryEntry(
        fixture_id=1, source="bridge_betano", version=42,
    )
    result = await repo.insert(entry)
    assert result is None


@pytest.mark.asyncio
async def test_list_recent_for_fixture_no_since_filter():
    """Sem `since`, query é SELECT … WHERE fixture_id=$1 ORDER BY captured_at DESC LIMIT $2."""
    conn = _FakeConn(fetch_returns=[{"id": 1, "fixture_id": 999}])
    repo = StatsHistoryRepo(_FakePool(conn))

    rows = await repo.list_recent_for_fixture(999, limit=50)
    assert rows == [{"id": 1, "fixture_id": 999}]
    sql, args = conn.fetch_calls[0]
    assert "WHERE fixture_id = $1" in sql
    assert "captured_at >= $2" not in sql  # sem `since`
    assert args == (999, 50)


@pytest.mark.asyncio
async def test_list_recent_for_fixture_with_since():
    conn = _FakeConn(fetch_returns=[])
    repo = StatsHistoryRepo(_FakePool(conn))

    since = datetime(2026, 5, 16, 19, 0, 0, tzinfo=timezone.utc)
    await repo.list_recent_for_fixture(999, since=since, limit=100)
    sql, args = conn.fetch_calls[0]
    assert "captured_at >= $2" in sql
    assert args == (999, since, 100)


@pytest.mark.asyncio
async def test_latest_version_for_fixture_returns_int():
    conn = _FakeConn(fetchrow_returns={"v": 1367})
    repo = StatsHistoryRepo(_FakePool(conn))
    v = await repo.latest_version_for_fixture(999, "bridge_betano")
    assert v == 1367


@pytest.mark.asyncio
async def test_latest_version_for_fixture_returns_none_when_empty():
    conn = _FakeConn(fetchrow_returns={"v": None})
    repo = StatsHistoryRepo(_FakePool(conn))
    v = await repo.latest_version_for_fixture(999, "bridge_betano")
    assert v is None
