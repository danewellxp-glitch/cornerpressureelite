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
async def test_get_stats_returns_cached_with_is_cached_true_on_304_hit():
    """304 + cache interno HIT → retorna stats cached com is_cached=True."""
    fresh_payload = _bridge_payload(version=1367, corners_h=3, corners_a=1)
    session = _FakeSession([
        _FakeResponse(200, fresh_payload),  # 1º poll: 200 fresh, popula cache
        _FakeResponse(304),                 # 2º poll: 304 bate cache
    ])
    adapter = BridgeStatsAdapter(
        bridge_url="http://bridge:8080",
        fixture_repo=_FakeRepo(event_id=42),
        session=session,
    )

    first = await adapter.get_stats(_fixture(999))
    assert first is not None and first.is_cached is False

    second = await adapter.get_stats(_fixture(999))
    assert second is not None
    assert second.is_cached is True
    # Mesmo conteúdo do fresh (cache devolve a referência via replace).
    assert second.corners_home == first.corners_home
    assert second.version == first.version
    # 2º request mandou if_version=cached.version.
    _, params2 = session.requests[1]
    assert params2 == {"if_version": 1367}


@pytest.mark.asyncio
async def test_get_stats_refetch_when_304_with_cache_miss():
    """304 + cache interno MISS (pós-restart) → re-fetch sem if_version → 200."""
    payload = _bridge_payload(version=42)
    session = _FakeSession([
        _FakeResponse(304),           # 304 mas cache interno vazio
        _FakeResponse(200, payload),  # re-fetch traz fresh
    ])
    adapter = BridgeStatsAdapter(
        bridge_url="http://bridge:8080",
        fixture_repo=_FakeRepo(event_id=42),
        session=session,
    )
    adapter._version_cache[999] = 99  # simula version stale sem stats cache

    stats = await adapter.get_stats(_fixture(999))
    assert stats is not None
    assert stats.is_cached is False
    assert stats.version == 42
    # 2 requests feitas (1 com if_version=99, 1 sem).
    assert len(session.requests) == 2
    assert session.requests[0][1] == {"if_version": 99}
    assert session.requests[1][1] == {}


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


@pytest.mark.asyncio
async def test_get_stats_populates_captured_at_ts_from_payload():
    """captured_at_ts vem de payload.captured_at (unix seconds)."""
    payload = _bridge_payload(version=1)
    payload["captured_at"] = 1778900000
    session = _FakeSession([_FakeResponse(200, payload)])
    adapter = BridgeStatsAdapter(
        bridge_url="http://bridge:8080",
        fixture_repo=_FakeRepo(event_id=42),
        session=session,
    )
    stats = await adapter.get_stats(_fixture(123))
    assert stats is not None
    assert stats.captured_at_ts == 1778900000.0
    assert stats.is_cached is False  # default
