"""Unit tests do BridgeStatsAdapter (Fase E.1 PARTE C')."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional
from unittest.mock import AsyncMock, MagicMock

import pytest

from data.odds_provider import CanonicalFixture
from data.providers.betano.bridge_stats_adapter import BridgeStatsAdapter


def _fixture(fid: int = 999) -> CanonicalFixture:
    return CanonicalFixture(
        fixture_id=fid,
        home_team="Home FC",
        away_team="Away FC",
        league_id=1,
        starts_at_utc=datetime(2026, 5, 16, 20, 0, 0, tzinfo=timezone.utc),
        score_home=0,
        score_away=0,
    )


def _bridge_payload(
    version: int = 1367,
    corners_h: int = 3,
    corners_a: int = 1,
    yellow_h: int = 1,
    yellow_a: int = 0,
    seconds: int = 1800,
) -> dict:
    return {
        "captured_at": 1778869885,
        "event_id": 84220231,
        "version": version,
        "from_cache": False,
        "data": {
            "version": version,
            "event": {
                "liveData": {
                    "score": {"home": "1", "away": "0"},
                    "clock": {"secondsSinceStart": seconds},
                    "results": {
                        "corners": {"home": str(corners_h), "away": str(corners_a)},
                        "yellow": {"home": str(yellow_h), "away": str(yellow_a)},
                        "shots": {"home": "7", "away": "4"},
                        "xGoals": {"home": "0.38", "away": "0.13"},
                    },
                },
            },
        },
    }


class _FakeRepo:
    """fixture_repo.get_betano_event_id -> int|None."""

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
    """Stub minimalista de aiohttp.ClientSession."""

    def __init__(self, responses_by_url: list[_FakeResponse]):
        self._responses = list(responses_by_url)
        self.requests: list[tuple[str, dict]] = []
        self.closed = False

    def get(self, url: str, params: Optional[dict] = None):
        self.requests.append((url, dict(params or {})))
        return self._responses.pop(0)

    async def close(self):
        self.closed = True


@pytest.mark.asyncio
async def test_get_stats_returns_canonical_stats_on_200():
    payload = _bridge_payload()
    session = _FakeSession([_FakeResponse(200, payload)])
    adapter = BridgeStatsAdapter(
        bridge_url="http://bridge:8080",
        fixture_repo=_FakeRepo(event_id=84220231),
        session=session,
    )

    stats = await adapter.get_stats(_fixture(999))
    assert stats is not None
    assert stats.source == "bridge_betano"
    assert stats.fixture_id == 999
    assert stats.corners_home == 3
    assert stats.corners_away == 1
    assert stats.yellow_cards_home == 1
    assert stats.version == 1367
    assert stats.second_since_start == 1800
    assert stats.minute == 30  # 1800//60
    # Janelas vêm None do adapter (calculator preenche depois).
    assert stats.corners_last_5min is None


@pytest.mark.asyncio
async def test_get_stats_returns_none_on_304():
    """304 = sem novo dado → None (caller pula persistência)."""
    session = _FakeSession([_FakeResponse(304)])
    adapter = BridgeStatsAdapter(
        bridge_url="http://bridge:8080",
        fixture_repo=_FakeRepo(event_id=42),
        session=session,
    )
    # Pre-populate version cache pra adapter mandar if_version.
    adapter._version_cache[999] = 1367

    stats = await adapter.get_stats(_fixture(999))
    assert stats is None
    # Confirma que mandou if_version no params.
    url, params = session.requests[0]
    assert params == {"if_version": 1367}


@pytest.mark.asyncio
async def test_get_stats_returns_none_when_repo_has_no_mapping():
    session = _FakeSession([])
    adapter = BridgeStatsAdapter(
        bridge_url="http://bridge:8080",
        fixture_repo=_FakeRepo(event_id=None),
        session=session,
    )
    stats = await adapter.get_stats(_fixture(999))
    assert stats is None
    assert session.requests == []  # nem chegou a fazer HTTP


@pytest.mark.asyncio
async def test_get_stats_returns_none_on_http_5xx():
    session = _FakeSession([_FakeResponse(503)])
    adapter = BridgeStatsAdapter(
        bridge_url="http://bridge:8080",
        fixture_repo=_FakeRepo(event_id=42),
        session=session,
    )
    stats = await adapter.get_stats(_fixture(999))
    assert stats is None


@pytest.mark.asyncio
async def test_get_stats_parses_missing_results_keys_as_zero():
    """Cobertura varia por liga: results pode ter só corners + sportId. Não crashar."""
    payload = {
        "captured_at": 0,
        "event_id": 42,
        "version": 1,
        "from_cache": False,
        "data": {
            "version": 1,
            "event": {
                "liveData": {
                    "score": {"home": "0", "away": "0"},
                    "clock": {"secondsSinceStart": 600},
                    "results": {
                        "corners": {"home": "2", "away": "1"},
                        # sem yellow, shots, xGoals
                    },
                },
            },
        },
    }
    session = _FakeSession([_FakeResponse(200, payload)])
    adapter = BridgeStatsAdapter(
        bridge_url="http://bridge:8080",
        fixture_repo=_FakeRepo(event_id=42),
        session=session,
    )
    stats = await adapter.get_stats(_fixture(999))
    assert stats is not None
    assert stats.corners_home == 2
    assert stats.yellow_cards_home == 0
    assert stats.shots_on_target_home == 0
    assert stats.x_goals_home == 0.0


@pytest.mark.asyncio
async def test_get_stats_updates_version_cache_after_200():
    payload = _bridge_payload(version=999)
    session = _FakeSession([_FakeResponse(200, payload)])
    adapter = BridgeStatsAdapter(
        bridge_url="http://bridge:8080",
        fixture_repo=_FakeRepo(event_id=42),
        session=session,
    )
    await adapter.get_stats(_fixture(123))
    assert adapter._version_cache[123] == 999
