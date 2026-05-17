"""Unit tests do BetanoEventsWorker (Fase F PARTE C)."""
from __future__ import annotations

from typing import Optional

import pytest

from data.events_provider import CanonicalEvent
from data.repositories.events_history import EventsHistoryRepo
from workers.betano_events_worker import BetanoEventsWorker


def _evt(*, minute=10, source="bridge_betano") -> CanonicalEvent:
    return CanonicalEvent(
        fixture_id=999,
        source=source,
        event_type="CRNR",
        event_minute=minute,
        team_side="home",
    )


class _FakeProvider:
    def __init__(self, result: Optional[list[CanonicalEvent]] = None):
        self._result = result
        self.calls: list[tuple] = []

    async def get_events(
        self, fixture_id, *, betano_event_id=None, home_team_id=None
    ):
        self.calls.append((fixture_id, betano_event_id, home_team_id))
        return self._result


class _FakeRepo:
    def __init__(self, inserted_count: int = 0, skipped_count: int = 0):
        self._inserted = inserted_count
        self._skipped = skipped_count
        self.batches: list[list[CanonicalEvent]] = []
        self.raises: Optional[Exception] = None

    async def upsert_batch(self, events: list[CanonicalEvent]):
        if self.raises is not None:
            raise self.raises
        self.batches.append(list(events))
        return self._inserted, self._skipped


@pytest.mark.asyncio
async def test_capture_persists_when_provider_returns_events():
    provider = _FakeProvider(result=[_evt(minute=10), _evt(minute=20)])
    repo = _FakeRepo(inserted_count=2, skipped_count=0)
    worker = BetanoEventsWorker(provider, repo)  # type: ignore[arg-type]

    inserted, skipped = await worker.capture(999, home_team_id=33)
    assert (inserted, skipped) == (2, 0)
    assert len(repo.batches) == 1
    assert len(repo.batches[0]) == 2
    # Hints passados ao provider
    assert provider.calls == [(999, None, 33)]


@pytest.mark.asyncio
async def test_capture_returns_0_0_when_provider_returns_none():
    """Provider None (erro/sem mapping) → (0,0), repo NÃO chamado."""
    provider = _FakeProvider(result=None)
    repo = _FakeRepo()
    worker = BetanoEventsWorker(provider, repo)  # type: ignore[arg-type]

    out = await worker.capture(999)
    assert out == (0, 0)
    assert repo.batches == []


@pytest.mark.asyncio
async def test_capture_returns_0_0_when_provider_returns_empty():
    """Provider [] (sem novos eventos) → (0,0), repo NÃO chamado."""
    provider = _FakeProvider(result=[])
    repo = _FakeRepo()
    worker = BetanoEventsWorker(provider, repo)  # type: ignore[arg-type]

    out = await worker.capture(999)
    assert out == (0, 0)
    assert repo.batches == []


@pytest.mark.asyncio
async def test_capture_handles_persist_error_gracefully():
    """Erro de persistência (UNIQUE, IO) → WARN log, retorna (0, len(events))."""
    provider = _FakeProvider(result=[_evt(minute=10), _evt(minute=20), _evt(minute=30)])
    repo = _FakeRepo()
    repo.raises = RuntimeError("DB connection lost")
    worker = BetanoEventsWorker(provider, repo)  # type: ignore[arg-type]

    inserted, skipped = await worker.capture(999)
    assert inserted == 0
    assert skipped == 3  # todos consideramos skipped por falha de persist


@pytest.mark.asyncio
async def test_capture_passes_betano_event_id_hint_to_provider():
    """Worker repassa betano_event_id ao provider quando passado."""
    provider = _FakeProvider(result=[])
    repo = _FakeRepo()
    worker = BetanoEventsWorker(provider, repo)  # type: ignore[arg-type]

    await worker.capture(999, betano_event_id=42, home_team_id=33)
    assert provider.calls == [(999, 42, 33)]
