"""Unit tests dos workers de persistência + helper event_uid (Fase D).

Sem Postgres real — workers recebem um repo fake que coleta os batches.
"""
from __future__ import annotations

import asyncio

import pytest

from data.persistence import (
    IncidentsPersistenceWorker,
    OddsPersistenceWorker,
)
from data.persistence.cleanup_worker import _parse_delete_status
from data.repositories.incidents_history import (
    IncidentHistoryEntry,
    event_uid,
)
from data.repositories.odds_history import OddsHistoryEntry


class _FakeOddsRepo:
    def __init__(self, raise_on_n: int | None = None):
        self.batches: list[list[OddsHistoryEntry]] = []
        self._raise_on_n = raise_on_n
        self._calls = 0

    async def bulk_insert(self, entries):
        # incrementa antes — o N-ésimo call (0-indexed) é o que raises
        n = self._calls
        self._calls += 1
        if self._raise_on_n is not None and n == self._raise_on_n:
            raise RuntimeError("simulated db error")
        self.batches.append(list(entries))


class _FakeIncidentsRepo:
    def __init__(self):
        self.batches: list[list[IncidentHistoryEntry]] = []

    async def bulk_insert(self, entries):
        self.batches.append(list(entries))


def _odds_entry(fid: int = 1) -> OddsHistoryEntry:
    return OddsHistoryEntry(
        fixture_id=fid, source="betano", market_kind="corners",
        market_code="CNOU", linha=9.5, odd_over=1.85, odd_under=1.95,
        raw={"x": fid},
    )


def _incident_entry(eu: str = "abc") -> IncidentHistoryEntry:
    return IncidentHistoryEntry(
        fixture_id=1, opta_match_id="opta-1", event_uid=eu, event_type=0,
        period_id=1, minute=10, seconds=0,
        team_id="t1", player_id="p1",
        x=50.0, y=50.0, x_end=None, y_end=None,
        is_attack=True, is_dangerous_attack=False,
        is_possession=True, is_dangerous=False,
        raw={},
    )


# ============================================================
# OddsPersistenceWorker
# ============================================================


@pytest.mark.asyncio
async def test_odds_worker_drains_queue_in_batches():
    repo = _FakeOddsRepo()
    worker = OddsPersistenceWorker(repo, batch_size=3, batch_timeout_s=0.05)
    await worker.start()
    try:
        for i in range(5):
            worker.enqueue(_odds_entry(fid=i))
        # espera tempo suficiente para esvaziar
        await asyncio.sleep(0.5)
    finally:
        await worker.stop()
    flat = [e for batch in repo.batches for e in batch]
    assert len(flat) == 5
    fids = sorted(e.fixture_id for e in flat)
    assert fids == [0, 1, 2, 3, 4]


@pytest.mark.asyncio
async def test_odds_worker_drops_when_full():
    repo = _FakeOddsRepo()
    worker = OddsPersistenceWorker(repo, queue_size=2, batch_size=10, batch_timeout_s=10)
    # NÃO inicia: força fila a encher
    worker.enqueue(_odds_entry(0))
    worker.enqueue(_odds_entry(1))
    worker.enqueue(_odds_entry(2))  # esse deve ser descartado
    assert worker.queue_size == 2


@pytest.mark.asyncio
async def test_odds_worker_continues_after_flush_error():
    repo = _FakeOddsRepo(raise_on_n=0)
    worker = OddsPersistenceWorker(repo, batch_size=1, batch_timeout_s=0.05)
    await worker.start()
    try:
        worker.enqueue(_odds_entry(0))  # 1º batch → erro
        await asyncio.sleep(0.2)
        worker.enqueue(_odds_entry(1))  # 2º batch → OK
        await asyncio.sleep(0.3)
    finally:
        await worker.stop()
    # 2º batch foi processado mesmo após o erro
    assert any(e.fixture_id == 1 for batch in repo.batches for e in batch)


@pytest.mark.asyncio
async def test_odds_worker_enqueue_from_dispatch_serializes_canonical():
    repo = _FakeOddsRepo()
    worker = OddsPersistenceWorker(repo, batch_size=1, batch_timeout_s=0.05)

    from data.odds_provider import CanonicalFixture, CanonicalOverUnder
    from datetime import datetime, timezone

    fx = CanonicalFixture(
        fixture_id=42, home_team="A", away_team="B", league_id=1,
        starts_at_utc=datetime(2026, 5, 13, tzinfo=timezone.utc),
        score_home=1, score_away=0,
    )
    primary = CanonicalOverUnder(
        source="betano", market_kind="corners", market_code="CNOU",
        linha=9.5, odd_over=1.85, odd_under=1.95,
    )
    worker.enqueue_from_dispatch(
        fixture=fx, market_kind="corners",
        primary=primary, all_results=[("betano", primary)],
    )
    assert worker.queue_size == 1
    await worker.start()
    try:
        await asyncio.sleep(0.2)
    finally:
        await worker.stop()
    flat = [e for batch in repo.batches for e in batch]
    assert flat
    e = flat[0]
    assert e.fixture_id == 42
    assert e.source == "betano"
    assert e.market_code == "CNOU"
    assert e.score_home == 1


# ============================================================
# IncidentsPersistenceWorker + event_uid
# ============================================================


def test_event_uid_is_deterministic():
    uid1 = event_uid("opta1", "t1", "p1", 10, 0, 0, 50.0, 50.0)
    uid2 = event_uid("opta1", "t1", "p1", 10, 0, 0, 50.0, 50.0)
    assert uid1 == uid2
    assert len(uid1) == 24


def test_event_uid_differs_when_seconds_differ():
    uid1 = event_uid("opta1", "t1", "p1", 10, 0, 0, 50.0, 50.0)
    uid2 = event_uid("opta1", "t1", "p1", 10, 1, 0, 50.0, 50.0)
    assert uid1 != uid2


def test_event_uid_handles_none_team_player():
    uid1 = event_uid("opta1", None, None, 5, 0, 1, None, None)
    uid2 = event_uid("opta1", "", "", 5, 0, 1, 0.0, 0.0)
    # ambos os None devem mapear para "" / 0.0 → mesmo hash
    assert uid1 == uid2


@pytest.mark.asyncio
async def test_incidents_worker_drains_queue():
    repo = _FakeIncidentsRepo()
    worker = IncidentsPersistenceWorker(repo, batch_size=2, batch_timeout_s=0.05)
    await worker.start()
    try:
        worker.enqueue(_incident_entry("uid-a"))
        worker.enqueue(_incident_entry("uid-b"))
        await asyncio.sleep(0.3)
    finally:
        await worker.stop()
    flat = [e for batch in repo.batches for e in batch]
    uids = {e.event_uid for e in flat}
    assert uids == {"uid-a", "uid-b"}


@pytest.mark.asyncio
async def test_incidents_worker_make_ws_callback_enqueues_match_event():
    repo = _FakeIncidentsRepo()
    worker = IncidentsPersistenceWorker(repo, batch_size=1, batch_timeout_s=0.05)

    from data.providers.betano import MatchEvent

    me = MatchEvent(
        opta_match_id="opta-xx",
        sportsbook_match_id=999,
        event_type=0,
        period_id=1,
        minute=12,
        seconds=34,
        team_id="t",
        player_id="p",
        x=10.0, y=20.0, x_end=11.0, y_end=21.0,
        is_attack=True,
        is_dangerous_attack=True,
        is_possession=False,
        is_dangerous=True,
        provider_type="Opta",
        raw={"foo": "bar"},
    )

    cb = worker.make_ws_callback(fixture_id_for=lambda opta: 777)
    await cb(me)
    assert worker.queue_size == 1
    await worker.start()
    try:
        await asyncio.sleep(0.2)
    finally:
        await worker.stop()
    entry = repo.batches[0][0]
    assert entry.fixture_id == 777
    assert entry.opta_match_id == "opta-xx"
    assert entry.is_dangerous_attack is True
    assert len(entry.event_uid) == 24


# ============================================================
# CleanupWorker helper
# ============================================================


def test_parse_delete_status_extracts_count():
    assert _parse_delete_status("DELETE 42") == 42
    assert _parse_delete_status("DELETE 0") == 0
    assert _parse_delete_status("BLAH") == 0
    assert _parse_delete_status("") == 0
