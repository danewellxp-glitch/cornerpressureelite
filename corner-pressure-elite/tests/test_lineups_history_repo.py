"""Unit tests do LineupsHistoryRepo (Fase G.1 PARTE D)."""
from __future__ import annotations

import json
from typing import Any

import pytest

from data.lineups_provider import CanonicalLineup, PlayerEntry
from data.repositories.lineups_history import LineupsHistoryRepo


class _FakeConn:
    def __init__(self):
        self.fetchrow_calls: list[tuple[str, tuple]] = []
        self.fetchrow_queue: list[Any] = []
        self.fetch_returns: list[dict] = []

    async def fetchrow(self, sql: str, *args):
        self.fetchrow_calls.append((sql, args))
        if self.fetchrow_queue:
            return self.fetchrow_queue.pop(0)
        return None

    async def fetch(self, sql: str, *args):
        return self.fetch_returns

    def transaction(self):
        class _Tx:
            async def __aenter__(self_inner):
                return self_inner

            async def __aexit__(self_inner, *a):
                return False
        return _Tx()


class _FakePool:
    def __init__(self, conn: _FakeConn):
        self._conn = conn

    def acquire(self):
        conn = self._conn

        class _Ctx:
            async def __aenter__(self_inner):
                return conn

            async def __aexit__(self_inner, *a):
                return False

        return _Ctx()


def _lineup(
    *,
    fixture_id=999,
    source="bridge_betano",
    team_side="home",
    starters: list[PlayerEntry] | None = None,
    subs: list[PlayerEntry] | None = None,
) -> CanonicalLineup:
    return CanonicalLineup(
        fixture_id=fixture_id,
        source=source,
        team_side=team_side,
        formation="4-3-3",
        coach_name=None,
        starting_eleven=starters or [PlayerEntry(name="X", player_id=1)],
        substitutes=subs or [],
        tactical_grid=[[1]],
        version=100,
        raw={"foo": "bar"},
    )


@pytest.mark.asyncio
async def test_upsert_inserts_new_returns_true():
    """INSERT bem-sucedido devolve True (RETURNING id retornou row)."""
    conn = _FakeConn()
    conn.fetchrow_queue = [{"id": 42}]
    repo = LineupsHistoryRepo(_FakePool(conn))

    out = await repo.upsert_lineup(_lineup())
    assert out is True
    sql, _ = conn.fetchrow_calls[0]
    assert "INSERT INTO lineups_history" in sql
    assert "ON CONFLICT (fixture_id, source, team_side)" in sql
    assert "DO NOTHING" in sql
    assert "RETURNING id" in sql


@pytest.mark.asyncio
async def test_upsert_returns_false_on_duplicate():
    """UNIQUE constraint dispara → fetchrow devolve None → caller recebe False."""
    conn = _FakeConn()
    conn.fetchrow_queue = [None]
    repo = LineupsHistoryRepo(_FakePool(conn))
    out = await repo.upsert_lineup(_lineup())
    assert out is False


@pytest.mark.asyncio
async def test_upsert_batch_returns_counts():
    """3 lineups, 2 inseridas + 1 dup → (2, 1)."""
    conn = _FakeConn()
    conn.fetchrow_queue = [{"id": 1}, None, {"id": 3}]
    repo = LineupsHistoryRepo(_FakePool(conn))

    out = await repo.upsert_batch([
        _lineup(team_side="home"),
        _lineup(team_side="away"),
        _lineup(team_side="home"),  # dup
    ])
    assert out == (2, 1)


@pytest.mark.asyncio
async def test_upsert_batch_empty_returns_zero_zero():
    conn = _FakeConn()
    repo = LineupsHistoryRepo(_FakePool(conn))
    out = await repo.upsert_batch([])
    assert out == (0, 0)
    assert conn.fetchrow_calls == []


@pytest.mark.asyncio
async def test_exists_for_fixture():
    conn = _FakeConn()
    conn.fetchrow_queue = [{"?column?": 1}]
    repo = LineupsHistoryRepo(_FakePool(conn))

    assert await repo.exists_for_fixture(999) is True
    sql, args = conn.fetchrow_calls[0]
    assert "SELECT 1 FROM lineups_history" in sql
    assert "WHERE fixture_id = $1" in sql
    assert args == (999,)


@pytest.mark.asyncio
async def test_exists_for_fixture_returns_false_when_no_row():
    conn = _FakeConn()
    conn.fetchrow_queue = [None]
    repo = LineupsHistoryRepo(_FakePool(conn))
    assert await repo.exists_for_fixture(999) is False


@pytest.mark.asyncio
async def test_upsert_serializes_players_as_jsonb():
    """Players (PlayerEntry) viram JSON via _serialize_players."""
    conn = _FakeConn()
    conn.fetchrow_queue = [{"id": 1}]
    repo = LineupsHistoryRepo(_FakePool(conn))

    lineup = _lineup(starters=[
        PlayerEntry(name="GK", player_id=100, position="GK",
                    position_display="Goleiro", shirt_number=1),
    ])
    await repo.upsert_lineup(lineup)

    _, args = conn.fetchrow_calls[0]
    # args[5] = starting_eleven JSON. Deve parse-ar.
    parsed = json.loads(args[5])
    assert isinstance(parsed, list) and len(parsed) == 1
    assert parsed[0]["name"] == "GK"
    assert parsed[0]["player_id"] == 100
    assert parsed[0]["position"] == "GK"
    assert parsed[0]["position_display"] == "Goleiro"
    assert parsed[0]["shirt_number"] == 1
    assert parsed[0]["is_substitute"] is False
