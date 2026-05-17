"""Unit tests do BetanoLineupsWorker (Fase G.1 PARTE D).

Cobertura: 5 cenários da tabela VAL 4 + outros edge cases.
"""
from __future__ import annotations

from typing import Optional

import pytest

from data.lineups_provider import CanonicalLineup, PlayerEntry
from workers.betano_lineups_worker import BetanoLineupsWorker


def _lineup(*, team_side="home", has_starters=True) -> CanonicalLineup:
    return CanonicalLineup(
        fixture_id=999,
        source="bridge_betano",
        team_side=team_side,
        formation="4-3-3" if has_starters else None,
        starting_eleven=(
            [PlayerEntry(name="X", player_id=1)] if has_starters else []
        ),
    )


class _FakeProvider:
    def __init__(self, result: Optional[list[CanonicalLineup]] = None):
        self._result = result
        self.calls: list[tuple] = []

    async def get_lineups(
        self, fixture_id, *, betano_event_id=None, home_team_id=None
    ):
        self.calls.append((fixture_id, betano_event_id, home_team_id))
        return self._result


class _FakeRepo:
    def __init__(self, exists=False, inserted=0, skipped=0,
                 raises_upsert: Optional[Exception] = None,
                 raises_exists: Optional[Exception] = None):
        self._exists = exists
        self._inserted = inserted
        self._skipped = skipped
        self._raises_upsert = raises_upsert
        self._raises_exists = raises_exists
        self.batches: list[list[CanonicalLineup]] = []

    async def exists_for_fixture(self, fixture_id: int) -> bool:
        if self._raises_exists is not None:
            raise self._raises_exists
        return self._exists

    async def upsert_batch(self, lineups: list[CanonicalLineup]):
        if self._raises_upsert is not None:
            raise self._raises_upsert
        self.batches.append(list(lineups))
        return self._inserted, self._skipped


@pytest.mark.asyncio
async def test_skips_when_minute_greater_than_max():
    """minute=10 > max_minute=5 → (0,0), provider NÃO chamado."""
    prov = _FakeProvider(result=[_lineup()])
    repo = _FakeRepo()
    w = BetanoLineupsWorker(prov, repo, max_minute=5)

    out = await w.capture_if_needed(999, minute=10)
    assert out == (0, 0)
    assert prov.calls == []
    assert repo.batches == []


@pytest.mark.asyncio
async def test_does_NOT_cache_when_gate_blocks():
    """VAL 4.1: minute > max → NÃO marca cache (deixa retry futuro possível)."""
    prov = _FakeProvider(result=[_lineup()])
    repo = _FakeRepo()
    w = BetanoLineupsWorker(prov, repo, max_minute=5)

    await w.capture_if_needed(999, minute=10)
    assert 999 not in w._captured


@pytest.mark.asyncio
async def test_does_NOT_cache_when_provider_returns_none():
    """VAL 4.2: provider None → NÃO marca cache (retry transparente)."""
    prov = _FakeProvider(result=None)
    repo = _FakeRepo()
    w = BetanoLineupsWorker(prov, repo, max_minute=5)

    out = await w.capture_if_needed(999, minute=3)
    assert out == (0, 0)
    assert 999 not in w._captured


@pytest.mark.asyncio
async def test_does_NOT_cache_when_lineups_empty():
    """VAL 4.3: lineups [] → NÃO marca cache (edge case raro)."""
    prov = _FakeProvider(result=[])
    repo = _FakeRepo()
    w = BetanoLineupsWorker(prov, repo, max_minute=5)

    out = await w.capture_if_needed(999, minute=3)
    assert out == (0, 0)
    assert 999 not in w._captured


@pytest.mark.asyncio
async def test_caches_when_repo_already_exists():
    """VAL 4.4: repo.exists_for_fixture True → MARCA cache + (0,0).
    Provider NÃO chamado."""
    prov = _FakeProvider(result=[_lineup()])
    repo = _FakeRepo(exists=True)
    w = BetanoLineupsWorker(prov, repo, max_minute=5)

    out = await w.capture_if_needed(999, minute=3)
    assert out == (0, 0)
    assert 999 in w._captured
    assert prov.calls == []  # short-circuit antes do provider


@pytest.mark.asyncio
async def test_caches_when_insert_succeeds():
    """VAL 4.5: insert sucesso (inserted>0) → MARCA cache."""
    prov = _FakeProvider(result=[
        _lineup(team_side="home"), _lineup(team_side="away"),
    ])
    repo = _FakeRepo(inserted=2, skipped=0)
    w = BetanoLineupsWorker(prov, repo, max_minute=5)

    out = await w.capture_if_needed(999, minute=3)
    assert out == (2, 0)
    assert 999 in w._captured


@pytest.mark.asyncio
async def test_does_NOT_cache_when_all_skipped_as_duplicates():
    """Edge: provider devolveu lineups mas todos foram dup (inserted=0).
    NÃO marca cache — próxima rodada usa repo.exists_for_fixture pra short-circuit."""
    prov = _FakeProvider(result=[_lineup()])
    repo = _FakeRepo(inserted=0, skipped=1)
    w = BetanoLineupsWorker(prov, repo, max_minute=5)

    out = await w.capture_if_needed(999, minute=3)
    assert out == (0, 1)
    assert 999 not in w._captured


@pytest.mark.asyncio
async def test_cache_hit_short_circuits():
    """Cache hit (manual add) → (0,0) sem nem checar repo nem provider."""
    prov = _FakeProvider(result=[_lineup()])
    repo = _FakeRepo()
    w = BetanoLineupsWorker(prov, repo, max_minute=5)
    w._captured.add(999)  # simula captura anterior

    out = await w.capture_if_needed(999, minute=3)
    assert out == (0, 0)
    assert prov.calls == []


@pytest.mark.asyncio
async def test_passes_hints_to_provider():
    """Worker repassa betano_event_id + home_team_id."""
    prov = _FakeProvider(result=[_lineup()])
    repo = _FakeRepo(inserted=1, skipped=0)
    w = BetanoLineupsWorker(prov, repo, max_minute=5)

    await w.capture_if_needed(
        999, minute=3, betano_event_id=42, home_team_id=33,
    )
    assert prov.calls == [(999, 42, 33)]


@pytest.mark.asyncio
async def test_handles_persist_error_gracefully():
    """Erro no upsert_batch → log warning, retorna (0, len(lineups))."""
    prov = _FakeProvider(result=[
        _lineup(team_side="home"), _lineup(team_side="away"),
    ])
    repo = _FakeRepo(raises_upsert=RuntimeError("DB down"))
    w = BetanoLineupsWorker(prov, repo, max_minute=5)

    inserted, skipped = await w.capture_if_needed(999, minute=3)
    assert inserted == 0
    assert skipped == 2  # todos considerados não-persistidos


@pytest.mark.asyncio
async def test_exists_check_error_falls_through_to_provider(caplog):
    """exists_for_fixture lança → assume `already=False`, segue pro provider."""
    import logging
    prov = _FakeProvider(result=[_lineup()])
    repo = _FakeRepo(
        raises_exists=RuntimeError("connection refused"),
        inserted=1, skipped=0,
    )
    w = BetanoLineupsWorker(prov, repo, max_minute=5)

    with caplog.at_level(logging.WARNING, logger="cpes.workers.betano_lineups"):
        out = await w.capture_if_needed(999, minute=3)
    assert out == (1, 0)
    assert prov.calls != []  # bateu provider mesmo com erro no exists
    assert any("exists_check_error" in r.message for r in caplog.records)


@pytest.mark.asyncio
async def test_forget_fixture_removes_from_cache():
    repo = _FakeRepo()
    prov = _FakeProvider(result=[])
    w = BetanoLineupsWorker(prov, repo, max_minute=5)
    w._captured.add(999)

    w.forget_fixture(999)
    assert 999 not in w._captured

    # Idempotente — forget de fixture inexistente não levanta.
    w.forget_fixture(7777)


@pytest.mark.asyncio
async def test_minute_none_does_not_trigger_gate():
    """minute=None (worker chamado fora de polling com minuto) → não bloqueia."""
    prov = _FakeProvider(result=[_lineup()])
    repo = _FakeRepo(inserted=1, skipped=0)
    w = BetanoLineupsWorker(prov, repo, max_minute=5)

    out = await w.capture_if_needed(999, minute=None)
    assert out == (1, 0)
    assert prov.calls != []
