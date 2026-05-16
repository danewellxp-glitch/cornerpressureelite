"""Unit tests do BetanoFixtureDiscovery worker.

Testa _tick() isoladamente (1 ciclo) — start/stop do loop infinito é coberto
implicitamente, mas o caminho de IO é mockado pra evitar polling real.
"""
from __future__ import annotations

from typing import Any, Optional

import httpx
import pytest

from data.discovery.fixture_matcher import MatchResult
from workers.betano_discovery import BetanoFixtureDiscovery


# ============================================================
# Fakes
# ============================================================


class _FakeApiClient:
    def __init__(self, fixtures: list[dict]):
        self.fixtures = fixtures
        self.calls = 0

    async def get_today_schedule(self, league_ids, date):
        self.calls += 1
        return list(self.fixtures)


class _FakeMatcher:
    def __init__(self, results: list[Optional[MatchResult]]):
        self.results = list(results)
        self.calls: list[dict] = []

    async def match_event(self, event, fixtures, tolerance_minutes=30):
        self.calls.append(event)
        if not self.results:
            return None
        return self.results.pop(0)


class _FakeFixtureRepo:
    def __init__(self, fail: bool = False):
        self.upserts: list[dict] = []
        self.fail = fail

    async def upsert(self, **kwargs):
        if self.fail:
            raise RuntimeError("simulated DB failure")
        self.upserts.append(kwargs)


class _FakeTeamRepo:
    pass


def _patch_bridge_response(monkeypatch, events: list[dict], status_code: int = 200, raise_error: bool = False):
    """Mock httpx.AsyncClient.get → response controlado."""
    class _Resp:
        def __init__(self, payload, status):
            self._payload = payload
            self.status_code = status

        def raise_for_status(self):
            if raise_error or self.status_code >= 400:
                raise httpx.HTTPStatusError(
                    "x", request=None, response=httpx.Response(status_code=self.status_code),
                )

        def json(self):
            return self._payload

    class _FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return None

        async def get(self, url, params=None):
            return _Resp({"events": events, "count": len(events)}, status_code)

    monkeypatch.setattr(httpx, "AsyncClient", _FakeClient)


def _make_event(event_id="100", home_id=1, away_id=2):
    return {
        "event_id": event_id,
        "name": "X vs Y",
        "participants": [
            {"name": "X", "is_home": True, "team_id": home_id},
            {"name": "Y", "is_home": None, "team_id": away_id},
        ],
        "start_time_ms": 1778896800000,
    }


# ============================================================
# _tick — happy path
# ============================================================


@pytest.mark.asyncio
async def test_worker_upserts_fixture_map_on_match(monkeypatch):
    """Evento bate no matcher → UPSERT no fixture_repo."""
    events = [_make_event("100"), _make_event("200", 3, 4)]
    _patch_bridge_response(monkeypatch, events)

    matcher = _FakeMatcher([
        MatchResult(fixture_id=9001, betano_event_id=100, confidence=1.0,
                    method="team_id_lookup", home_team="X", away_team="Y",
                    league_id=215, kickoff_utc=None),
        MatchResult(fixture_id=9002, betano_event_id=200, confidence=0.91,
                    method="fuzzy", home_team="A", away_team="B",
                    league_id=216, kickoff_utc=None),
    ])
    fixture_repo = _FakeFixtureRepo()
    api_client = _FakeApiClient([{"fixture": {"id": 9001}}])

    worker = BetanoFixtureDiscovery(
        bridge_url="http://test-bridge",
        api_client=api_client,
        matcher=matcher,
        fixture_repo=fixture_repo,
        team_repo=_FakeTeamRepo(),
        league_ids=[215, 216],
    )
    await worker._tick()

    assert len(fixture_repo.upserts) == 2
    assert fixture_repo.upserts[0]["fixture_id"] == 9001
    assert fixture_repo.upserts[0]["betano_event_id"] == 100
    assert fixture_repo.upserts[0]["resolved_via"] == "discovery_team_id_lookup"
    assert fixture_repo.upserts[1]["resolved_via"] == "discovery_fuzzy"


# ============================================================
# _tick — match None
# ============================================================


@pytest.mark.asyncio
async def test_worker_skips_when_match_returns_none(monkeypatch):
    """Matcher retorna None pra todos eventos → 0 UPSERTs."""
    _patch_bridge_response(monkeypatch, [_make_event(), _make_event("200")])
    matcher = _FakeMatcher([None, None])
    fixture_repo = _FakeFixtureRepo()
    api_client = _FakeApiClient([{"fixture": {"id": 1}}])

    worker = BetanoFixtureDiscovery(
        bridge_url="http://test-bridge",
        api_client=api_client, matcher=matcher,
        fixture_repo=fixture_repo, team_repo=_FakeTeamRepo(),
        league_ids=[1],
    )
    await worker._tick()
    assert fixture_repo.upserts == []
    assert len(matcher.calls) == 2  # tentou ambos


# ============================================================
# _tick — bridge down
# ============================================================


@pytest.mark.asyncio
async def test_worker_handles_bridge_503_gracefully(monkeypatch):
    """Bridge retorna erro → loop não para, 0 UPSERTs."""
    _patch_bridge_response(monkeypatch, [], status_code=503, raise_error=True)
    matcher = _FakeMatcher([])
    fixture_repo = _FakeFixtureRepo()
    api_client = _FakeApiClient([])

    worker = BetanoFixtureDiscovery(
        bridge_url="http://test-bridge",
        api_client=api_client, matcher=matcher,
        fixture_repo=fixture_repo, team_repo=_FakeTeamRepo(),
        league_ids=[1],
    )
    # Não deve raise
    await worker._tick()
    assert fixture_repo.upserts == []
    assert matcher.calls == []  # nem chegou no matcher


# ============================================================
# _tick — schedule cache
# ============================================================


@pytest.mark.asyncio
async def test_worker_caches_schedule_per_day(monkeypatch):
    """get_today_schedule é chamado 1x mesmo com múltiplos ticks no mesmo dia."""
    _patch_bridge_response(monkeypatch, [_make_event()])
    matcher = _FakeMatcher([None] * 10)
    fixture_repo = _FakeFixtureRepo()
    api_client = _FakeApiClient([{"fixture": {"id": 1}}])

    worker = BetanoFixtureDiscovery(
        bridge_url="http://test-bridge",
        api_client=api_client, matcher=matcher,
        fixture_repo=fixture_repo, team_repo=_FakeTeamRepo(),
        league_ids=[1],
    )
    await worker._tick()
    await worker._tick()
    await worker._tick()
    # api_client foi chamado apenas 1x (cache do mesmo dia)
    assert api_client.calls == 1


# ============================================================
# _tick — fail-soft no UPSERT
# ============================================================


@pytest.mark.asyncio
async def test_worker_continues_when_upsert_fails(monkeypatch):
    """Erro no UPSERT de 1 fixture não para processamento dos demais."""
    events = [_make_event("100"), _make_event("200", 3, 4)]
    _patch_bridge_response(monkeypatch, events)
    matcher = _FakeMatcher([
        MatchResult(fixture_id=9001, betano_event_id=100, confidence=1.0,
                    method="team_id_lookup", home_team="X", away_team="Y",
                    league_id=215, kickoff_utc=None),
        MatchResult(fixture_id=9002, betano_event_id=200, confidence=1.0,
                    method="team_id_lookup", home_team="A", away_team="B",
                    league_id=216, kickoff_utc=None),
    ])
    fixture_repo = _FakeFixtureRepo(fail=True)  # SEMPRE falha
    api_client = _FakeApiClient([{"fixture": {"id": 1}}])

    worker = BetanoFixtureDiscovery(
        bridge_url="http://test-bridge",
        api_client=api_client, matcher=matcher,
        fixture_repo=fixture_repo, team_repo=_FakeTeamRepo(),
        league_ids=[1],
    )
    await worker._tick()  # não deve raise
    # 2 eventos tentados (matcher chamado 2x), nenhum UPSERT sucedeu
    assert len(matcher.calls) == 2


# ============================================================
# start/stop lifecycle
# ============================================================


@pytest.mark.asyncio
async def test_worker_start_creates_task_stop_cancels(monkeypatch):
    """start() cria task, stop() cancela com gracioso."""
    import asyncio
    _patch_bridge_response(monkeypatch, [])
    matcher = _FakeMatcher([])
    fixture_repo = _FakeFixtureRepo()
    api_client = _FakeApiClient([])

    worker = BetanoFixtureDiscovery(
        bridge_url="http://test-bridge",
        api_client=api_client, matcher=matcher,
        fixture_repo=fixture_repo, team_repo=_FakeTeamRepo(),
        league_ids=[1],
        poll_sec=3600,  # longo pra não rodar tick adicional
    )
    await worker.start()
    assert worker._task is not None
    assert not worker._task.done()
    await asyncio.sleep(0.01)  # deixa 1 tick rodar
    await worker.stop()
    assert worker._task is None
