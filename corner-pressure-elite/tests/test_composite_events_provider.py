"""Unit tests do CompositeEventsProvider (Fase F PARTE B)."""
from __future__ import annotations

import logging
from typing import Optional

import pytest

from data.events_provider import CanonicalEvent, CompositeEventsProvider


class _FakeProvider:
    def __init__(
        self,
        name: str,
        result: Optional[list[CanonicalEvent]] = None,
        raises: bool = False,
    ):
        self.name = name
        self._result = result
        self._raises = raises
        self.calls: list[tuple] = []

    async def get_events(
        self,
        fixture_id: int,
        *,
        betano_event_id=None,
        home_team_id=None,
    ):
        self.calls.append((fixture_id, betano_event_id, home_team_id))
        if self._raises:
            raise RuntimeError(f"{self.name} simulated failure")
        return self._result

    async def healthcheck(self) -> bool:
        return not self._raises


def _evt(source: str) -> CanonicalEvent:
    return CanonicalEvent(
        fixture_id=999, source=source, event_type="CRNR", event_minute=30
    )


@pytest.mark.asyncio
async def test_prefers_primary_when_available():
    """Primary devolve lista → composite retorna sem chamar fallback."""
    primary = _FakeProvider("bridge_betano", result=[_evt("bridge_betano")])
    fallback = _FakeProvider("apifootball", result=[_evt("apifootball")])
    composite = CompositeEventsProvider([primary, fallback])

    out = await composite.get_events(999)
    assert out is not None and len(out) == 1
    assert out[0].source == "bridge_betano"
    assert fallback.calls == []  # fallback NÃO chamado


@pytest.mark.asyncio
async def test_falls_back_to_secondary_when_primary_returns_none():
    """Primary None → fallback chamado."""
    primary = _FakeProvider("bridge_betano", result=None)
    fallback = _FakeProvider("apifootball", result=[_evt("apifootball")])
    composite = CompositeEventsProvider([primary, fallback])

    out = await composite.get_events(999)
    assert out is not None and out[0].source == "apifootball"
    assert len(fallback.calls) == 1


@pytest.mark.asyncio
async def test_falls_back_when_primary_raises():
    """Primary lança exceção → log warning + fallback chamado."""
    primary = _FakeProvider("bridge_betano", raises=True)
    fallback = _FakeProvider("apifootball", result=[_evt("apifootball")])
    composite = CompositeEventsProvider([primary, fallback])

    out = await composite.get_events(999)
    assert out is not None and out[0].source == "apifootball"


@pytest.mark.asyncio
async def test_betano_empty_does_not_trigger_af_fallback(caplog):
    """[] do primary = sucesso (sem novos eventos). NÃO cai pra fallback.
    Log INFO 'composite_events.empty' emitido."""
    primary = _FakeProvider("bridge_betano", result=[])
    fallback = _FakeProvider("apifootball", result=[_evt("apifootball")])
    composite = CompositeEventsProvider([primary, fallback])

    with caplog.at_level(logging.INFO, logger="cpes.providers.events"):
        out = await composite.get_events(999)
    assert out == []
    assert fallback.calls == []  # fallback NÃO chamado
    assert any("composite_events.empty" in r.message for r in caplog.records)


@pytest.mark.asyncio
async def test_returns_none_when_all_fail():
    primary = _FakeProvider("bridge_betano", result=None)
    secondary = _FakeProvider("apifootball", result=None)
    composite = CompositeEventsProvider([primary, secondary])

    out = await composite.get_events(999)
    assert out is None


@pytest.mark.asyncio
async def test_init_requires_at_least_one_provider():
    with pytest.raises(ValueError):
        CompositeEventsProvider([])


@pytest.mark.asyncio
async def test_passes_betano_event_id_and_home_team_id_hints_to_providers():
    """Composite repassa hints betano_event_id + home_team_id pros adapters."""
    primary = _FakeProvider("bridge_betano", result=[_evt("bridge_betano")])
    composite = CompositeEventsProvider([primary])

    await composite.get_events(999, betano_event_id=12345, home_team_id=33)
    assert primary.calls == [(999, 12345, 33)]
