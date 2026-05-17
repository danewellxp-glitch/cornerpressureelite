"""Unit tests do EventsHistoryRepo (Fase F PARTE A)."""
from __future__ import annotations

from typing import Any

import pytest

from data.events_provider import CanonicalEvent
from data.repositories.events_history import EventsHistoryRepo


class _FakeConn:
    def __init__(self):
        self.fetchrow_calls: list[tuple[str, tuple]] = []
        self.fetch_calls: list[tuple[str, tuple]] = []
        self.fetchrow_queue: list[Any] = []
        self.fetch_returns: list[dict] = []

    async def fetchrow(self, sql: str, *args):
        self.fetchrow_calls.append((sql, args))
        if self.fetchrow_queue:
            return self.fetchrow_queue.pop(0)
        return None

    async def fetch(self, sql: str, *args):
        self.fetch_calls.append((sql, args))
        return self.fetch_returns

    async def execute(self, sql: str, *args):
        return None

    def transaction(self):
        return _FakeTx()


class _FakeTx:
    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False


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


def _evt(**overrides) -> CanonicalEvent:
    base = dict(
        fixture_id=999,
        source="bridge_betano",
        event_type="CRNR",
        event_minute=67,
        team_side="home",
    )
    base.update(overrides)
    return CanonicalEvent(**base)


@pytest.mark.asyncio
async def test_upsert_event_inserts_new_returns_true():
    """INSERT bem-sucedido devolve True (row com id)."""
    conn = _FakeConn()
    conn.fetchrow_queue = [{"id": 42}]
    repo = EventsHistoryRepo(_FakePool(conn))

    result = await repo.upsert_event(_evt())
    assert result is True
    sql, args = conn.fetchrow_calls[0]
    assert "INSERT INTO events_history" in sql
    assert "ON CONFLICT" in sql
    assert "DO NOTHING" in sql
    assert "RETURNING id" in sql


@pytest.mark.asyncio
async def test_upsert_event_returns_false_on_duplicate():
    """ON CONFLICT DO NOTHING → fetchrow devolve None → caller recebe False."""
    conn = _FakeConn()
    conn.fetchrow_queue = [None]
    repo = EventsHistoryRepo(_FakePool(conn))
    result = await repo.upsert_event(_evt())
    assert result is False


@pytest.mark.asyncio
async def test_upsert_batch_returns_counts():
    """upsert_batch: 2 inseridos, 1 duplicate → (2, 1)."""
    conn = _FakeConn()
    conn.fetchrow_queue = [{"id": 1}, None, {"id": 3}]
    repo = EventsHistoryRepo(_FakePool(conn))

    events = [_evt(event_minute=10), _evt(event_minute=20), _evt(event_minute=30)]
    inserted, skipped = await repo.upsert_batch(events)
    assert inserted == 2
    assert skipped == 1


@pytest.mark.asyncio
async def test_upsert_batch_empty_returns_zero_zero():
    conn = _FakeConn()
    repo = EventsHistoryRepo(_FakePool(conn))
    inserted, skipped = await repo.upsert_batch([])
    assert (inserted, skipped) == (0, 0)
    assert conn.fetchrow_calls == []


@pytest.mark.asyncio
async def test_get_recent_by_fixture_emits_correct_sql():
    conn = _FakeConn()
    conn.fetch_returns = [{"id": 1, "event_type": "CRNR"}]
    repo = EventsHistoryRepo(_FakePool(conn))

    rows = await repo.get_recent_by_fixture(999, limit=50)
    assert rows == [{"id": 1, "event_type": "CRNR"}]
    sql, args = conn.fetch_calls[0]
    assert "WHERE fixture_id = $1" in sql
    assert "ORDER BY event_minute ASC" in sql
    assert args == (999, 50)


@pytest.mark.asyncio
async def test_get_by_type_in_window_filters_correctly():
    conn = _FakeConn()
    conn.fetch_returns = []
    repo = EventsHistoryRepo(_FakePool(conn))

    await repo.get_by_type_in_window(999, "CRNR", since_minute=60)
    sql, args = conn.fetch_calls[0]
    assert "WHERE fixture_id = $1" in sql
    assert "event_type = $2" in sql
    assert "event_minute >= $3" in sql
    assert args == (999, "CRNR", 60)
