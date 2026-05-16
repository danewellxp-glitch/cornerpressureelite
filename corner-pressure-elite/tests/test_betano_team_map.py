"""Unit tests do BetanoTeamMapRepo com mocks de pool.

Padrão consistente com test_repositories.py — checa SQL emitido + retorno
sem precisar de Postgres real.
"""
from __future__ import annotations

from typing import Any

import pytest

from data.repositories.betano_team_map import BetanoTeamEntry, BetanoTeamMapRepo


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
# bulk_upsert
# ============================================================

@pytest.mark.asyncio
async def test_bulk_upsert_inserts_new_entries():
    pool = _FakePool()
    repo = BetanoTeamMapRepo(pool)

    entries = [
        BetanoTeamEntry(
            betano_team_id=2050542,
            betano_team_name="Bay FC (F)",
            api_football_team_id=None,
            api_football_team_name=None,
            match_method="static_catalog",
            match_confidence=None,
        ),
        BetanoTeamEntry(
            betano_team_id=2096271,
            betano_team_name="Boston Legacy (F)",
            api_football_team_id=42,
            api_football_team_name="Boston Legacy",
            match_method="fuzzy",
            match_confidence=0.92,
        ),
    ]

    n = await repo.bulk_upsert(entries)
    assert n == 2
    assert len(pool.conn.execute_many) == 1

    sql, rows = pool.conn.execute_many[0]
    assert "INSERT INTO betano_team_map" in sql
    assert "ON CONFLICT (betano_team_id)" in sql
    assert "COALESCE(EXCLUDED.api_football_team_id" in sql  # preserva resolvido
    assert len(rows) == 2
    assert rows[0][0] == 2050542
    assert rows[1][2] == 42  # api_football_team_id


@pytest.mark.asyncio
async def test_bulk_upsert_empty_list_returns_zero_no_sql():
    pool = _FakePool()
    repo = BetanoTeamMapRepo(pool)

    n = await repo.bulk_upsert([])
    assert n == 0
    assert pool.conn.execute_many == []


# ============================================================
# get_by_betano_id
# ============================================================

@pytest.mark.asyncio
async def test_get_by_betano_id_found_returns_entry():
    pool = _FakePool()
    pool.conn.next_row = {
        "betano_team_id": 2050542,
        "betano_team_name": "Bay FC (F)",
        "api_football_team_id": 42,
        "api_football_team_name": "Bay FC",
        "match_method": "fuzzy",
        "match_confidence": 0.91,
    }
    repo = BetanoTeamMapRepo(pool)

    entry = await repo.get_by_betano_id(2050542)
    assert entry is not None
    assert entry.betano_team_id == 2050542
    assert entry.api_football_team_id == 42
    assert entry.match_confidence == pytest.approx(0.91)


@pytest.mark.asyncio
async def test_get_by_betano_id_not_found_returns_none():
    pool = _FakePool()
    pool.conn.next_row = None
    repo = BetanoTeamMapRepo(pool)

    entry = await repo.get_by_betano_id(99999999)
    assert entry is None


# ============================================================
# get_by_api_football_id
# ============================================================

@pytest.mark.asyncio
async def test_get_by_api_football_id_found_returns_entry():
    pool = _FakePool()
    pool.conn.next_row = {
        "betano_team_id": 2050542,
        "betano_team_name": "Bay FC (F)",
        "api_football_team_id": 42,
        "api_football_team_name": "Bay FC",
        "match_method": "fuzzy",
        "match_confidence": 0.91,
    }
    repo = BetanoTeamMapRepo(pool)

    entry = await repo.get_by_api_football_id(42)
    assert entry is not None
    assert entry.api_football_team_id == 42

    # Verifica SQL usou api_football_team_id na WHERE
    sql = pool.conn.executes  # fetchrow não vai em executes; checa via fetchrow signature
    # noop: fetchrow não persiste em mocks. Apenas asserte que retornou.


# ============================================================
# find_by_fuzzy_name (pg_trgm)
# ============================================================

@pytest.mark.asyncio
async def test_find_by_fuzzy_name_returns_top_matches_with_scores():
    pool = _FakePool()
    pool.conn.next_rows = [
        {
            "betano_team_id": 2050542,
            "betano_team_name": "Bay FC (F)",
            "api_football_team_id": 42,
            "api_football_team_name": "Bay FC",
            "match_method": "fuzzy",
            "match_confidence": 0.91,
            "sim": 0.93,
        },
        {
            "betano_team_id": 2050543,
            "betano_team_name": "Bay United",
            "api_football_team_id": None,
            "api_football_team_name": None,
            "match_method": "static_catalog",
            "match_confidence": None,
            "sim": 0.87,
        },
    ]
    repo = BetanoTeamMapRepo(pool)

    results = await repo.find_by_fuzzy_name("Bay FC", threshold=0.85, limit=3)
    assert len(results) == 2
    assert results[0][0].betano_team_name == "Bay FC (F)"
    assert results[0][1] == pytest.approx(0.93)
    assert results[1][1] == pytest.approx(0.87)
    # 2º resultado sem api_football_team_id resolvido
    assert results[1][0].api_football_team_id is None


@pytest.mark.asyncio
async def test_find_by_fuzzy_name_empty_result_when_no_match():
    pool = _FakePool()
    pool.conn.next_rows = []
    repo = BetanoTeamMapRepo(pool)

    results = await repo.find_by_fuzzy_name("Nome Que Nao Existe", threshold=0.99)
    assert results == []
