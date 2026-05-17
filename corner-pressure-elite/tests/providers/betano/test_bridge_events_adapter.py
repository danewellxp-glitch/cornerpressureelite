"""Unit tests do BridgeEventsAdapter (Fase F PARTE B)."""
from __future__ import annotations

from typing import Optional

import pytest

from data.providers.betano.bridge_events_adapter import BridgeEventsAdapter


def _payload(incidents: list[dict]) -> dict:
    return {
        "captured_at": 1778900000,
        "event_id": 84220231,
        "version": 1367,
        "from_cache": False,
        "data": {
            "version": 1367,
            "event": {"incidents": incidents},
        },
    }


class _FakeRepo:
    def __init__(self, event_id: Optional[int]):
        self._event_id = event_id

    async def get_betano_event_id(self, fixture_id: int) -> Optional[int]:
        return self._event_id


class _FakeResponse:
    def __init__(self, status: int, payload: Optional[dict] = None):
        self.status = status
        self._payload = payload

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False

    async def json(self):
        return self._payload


class _FakeSession:
    def __init__(self, responses: list[_FakeResponse]):
        self._responses = list(responses)
        self.requests: list[tuple[str, dict]] = []
        self.closed = False

    def get(self, url: str, params: Optional[dict] = None):
        self.requests.append((url, dict(params or {})))
        return self._responses.pop(0)

    async def close(self):
        self.closed = True


@pytest.mark.asyncio
async def test_get_events_returns_canonical_list_on_200():
    incidents = [
        {"type": "CRNR", "time": "23'", "teamSide": 0, "props": {"minute": 23}},
        {"type": "YELL", "time": "45'+2'", "teamSide": 1, "props": {"minute": 47, "overtimeMinute": 2}},
    ]
    session = _FakeSession([_FakeResponse(200, _payload(incidents))])
    adapter = BridgeEventsAdapter("http://bridge:8080", fixture_repo=_FakeRepo(42), session=session)

    events = await adapter.get_events(999)
    assert events is not None
    assert len(events) == 2
    assert events[0].event_type == "CRNR"
    assert events[0].source == "bridge_betano"
    assert events[0].team_side == "home"
    assert events[0].event_minute == 23
    assert events[1].event_type == "YELL"
    assert events[1].team_side == "away"
    assert events[1].event_minute == 47


@pytest.mark.asyncio
async def test_normalize_incident_with_team_side_none():
    """teamSide ausente OR fora de 0/1 → team_side=None (eventos sem lado tipo EBEG, PBEG)."""
    incidents = [
        {"type": "EBEG", "time": "0'", "props": {"minute": 0}},  # sem teamSide
        {"type": "PEND", "time": "45'", "teamSide": "weird", "props": {"minute": 45}},
    ]
    session = _FakeSession([_FakeResponse(200, _payload(incidents))])
    adapter = BridgeEventsAdapter("http://b:8080", fixture_repo=_FakeRepo(42), session=session)
    events = await adapter.get_events(999)
    assert events is not None and len(events) == 2
    assert events[0].team_side is None
    assert events[1].team_side is None


@pytest.mark.asyncio
async def test_normalize_incident_parses_minute_from_time_when_no_props():
    """time="50'+3'" → minute=53 quando props.minute ausente."""
    incidents = [{"type": "GOAL", "time": "50'+3'", "teamSide": 0, "props": {}}]
    session = _FakeSession([_FakeResponse(200, _payload(incidents))])
    adapter = BridgeEventsAdapter("http://b:8080", fixture_repo=_FakeRepo(42), session=session)
    events = await adapter.get_events(999)
    assert events is not None and len(events) == 1
    assert events[0].event_minute == 53


@pytest.mark.asyncio
async def test_normalize_incident_drops_when_no_minute():
    """Incident sem minute em props E time inválido → descarta (não persistível)."""
    incidents = [
        {"type": "Aggregated", "time": None, "props": {}},  # sem minute
        {"type": "CRNR", "time": "30'", "props": {"minute": 30}, "teamSide": 0},
    ]
    session = _FakeSession([_FakeResponse(200, _payload(incidents))])
    adapter = BridgeEventsAdapter("http://b:8080", fixture_repo=_FakeRepo(42), session=session)
    events = await adapter.get_events(999)
    assert events is not None
    assert len(events) == 1  # Aggregated dropado
    assert events[0].event_type == "CRNR"


@pytest.mark.asyncio
async def test_get_events_returns_none_when_no_event_id_in_repo():
    session = _FakeSession([])  # nem deve chegar a HTTP
    adapter = BridgeEventsAdapter("http://b:8080", fixture_repo=_FakeRepo(None), session=session)
    events = await adapter.get_events(999)
    assert events is None
    assert session.requests == []


@pytest.mark.asyncio
async def test_get_events_returns_none_on_5xx():
    session = _FakeSession([_FakeResponse(503)])
    adapter = BridgeEventsAdapter("http://b:8080", fixture_repo=_FakeRepo(42), session=session)
    events = await adapter.get_events(999)
    assert events is None


@pytest.mark.asyncio
async def test_get_events_returns_empty_on_304():
    """304 = cache match → [] (sem novos eventos, mas provider respondeu OK)."""
    session = _FakeSession([_FakeResponse(304)])
    adapter = BridgeEventsAdapter("http://b:8080", fixture_repo=_FakeRepo(42), session=session)
    events = await adapter.get_events(999)
    assert events == []


@pytest.mark.asyncio
async def test_get_events_uses_betano_event_id_hint_skipping_repo_lookup():
    """Quando caller passa betano_event_id, adapter pula o lookup no repo."""
    # Repo retorna None mas hint deve evitar usar repo.
    payload = _payload([{"type": "CRNR", "time": "30'", "props": {"minute": 30}, "teamSide": 0}])
    session = _FakeSession([_FakeResponse(200, payload)])
    adapter = BridgeEventsAdapter("http://b:8080", fixture_repo=_FakeRepo(None), session=session)

    events = await adapter.get_events(999, betano_event_id=12345)
    assert events is not None and len(events) == 1
    url, _ = session.requests[0]
    assert "/event/12345/state" in url


@pytest.mark.asyncio
async def test_get_events_returns_empty_when_payload_has_no_incidents():
    """data.event.incidents ausente ou não-lista → []"""
    payload = {"data": {"event": {}}}  # sem incidents
    session = _FakeSession([_FakeResponse(200, payload)])
    adapter = BridgeEventsAdapter("http://b:8080", fixture_repo=_FakeRepo(42), session=session)
    events = await adapter.get_events(999)
    assert events == []
