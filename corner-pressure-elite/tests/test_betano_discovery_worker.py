"""Unit tests do BetanoFixtureDiscovery worker.

Testa _tick() isoladamente (1 ciclo) — start/stop do loop infinito é coberto
implicitamente, mas o caminho de IO é mockado pra evitar polling real.
"""
from __future__ import annotations

from typing import Any, Optional

import httpx
import pytest

from data.discovery.fixture_matcher import MatchResult
from data.repositories.betano_team_map import BetanoTeamEntry
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
    def __init__(self):
        self.bulk_upsert_calls: list[list[BetanoTeamEntry]] = []

    async def bulk_upsert(self, entries):
        entries_list = list(entries) if not isinstance(entries, list) else entries
        self.bulk_upsert_calls.append(entries_list)
        return len(entries_list)


def _patch_bridge_multi(monkeypatch, *, events=None, teams_payload=None, teams_status=200, teams_raise=False):
    """Patch httpx.AsyncClient com handler por URL path.

    `events`: dict ou list pro /events/live (default {events: []})
    `teams_payload`: dict pro /teams (default {teams: []})
    `teams_status` + `teams_raise`: simular erro no /teams
    """
    class _Resp:
        def __init__(self, payload, status=200, raise_on_status=False):
            self._payload = payload
            self.status_code = status
            self._raise = raise_on_status

        def raise_for_status(self):
            if self._raise or self.status_code >= 400:
                raise httpx.HTTPStatusError(
                    "x", request=None,
                    response=httpx.Response(status_code=self.status_code),
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
            if "/events/live" in url:
                ev_list = events if isinstance(events, list) else (events or [])
                return _Resp({"events": ev_list, "count": len(ev_list)})
            if "/teams" in url:
                return _Resp(
                    teams_payload or {"teams": [], "count": 0},
                    status=teams_status,
                    raise_on_status=teams_raise,
                )
            return _Resp({})

    monkeypatch.setattr(httpx, "AsyncClient", _FakeClient)


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


# ============================================================
# _refresh_teams_catalog — PARTE A da Fase D.2
# ============================================================


@pytest.mark.asyncio
async def test_refresh_teams_catalog_upserts_entries(monkeypatch):
    """Bridge retorna teams → bulk_upsert chamado com BetanoTeamEntry(static_catalog)."""
    teams_payload = {
        "captured_at": 1778000000,
        "count": 3,
        "teams": [
            {"team_id": 106973, "name": "Shonan Bellmare", "source": "upcoming"},
            {"team_id": 108644, "name": "Universitario de Deportes", "source": "live"},
            {"team_id": 109423, "name": "Derry City", "source": "upcoming"},
        ],
    }
    _patch_bridge_multi(monkeypatch, teams_payload=teams_payload)

    team_repo = _FakeTeamRepo()
    worker = BetanoFixtureDiscovery(
        bridge_url="http://test-bridge",
        api_client=_FakeApiClient([]), matcher=_FakeMatcher([]),
        fixture_repo=_FakeFixtureRepo(), team_repo=team_repo,
        league_ids=[1],
    )
    await worker._refresh_teams_catalog()

    assert len(team_repo.bulk_upsert_calls) == 1
    upserted = team_repo.bulk_upsert_calls[0]
    assert len(upserted) == 3
    # Todos com match_method='static_catalog', api_football_team_id=None
    for entry in upserted:
        assert entry.match_method == "static_catalog"
        assert entry.api_football_team_id is None
        assert entry.match_confidence is None
        assert isinstance(entry.betano_team_id, int)
    # Conteúdo
    names = {e.betano_team_name for e in upserted}
    assert names == {"Shonan Bellmare", "Universitario de Deportes", "Derry City"}


@pytest.mark.asyncio
async def test_refresh_teams_catalog_skips_when_empty(monkeypatch):
    """Bridge retorna teams=[] → não chama bulk_upsert."""
    _patch_bridge_multi(monkeypatch, teams_payload={"teams": [], "count": 0})

    team_repo = _FakeTeamRepo()
    worker = BetanoFixtureDiscovery(
        bridge_url="http://test-bridge",
        api_client=_FakeApiClient([]), matcher=_FakeMatcher([]),
        fixture_repo=_FakeFixtureRepo(), team_repo=team_repo,
        league_ids=[1],
    )
    await worker._refresh_teams_catalog()

    assert team_repo.bulk_upsert_calls == []


@pytest.mark.asyncio
async def test_refresh_teams_catalog_handles_bridge_failure(monkeypatch):
    """Bridge retorna 503 → log warning, não levanta exception, não upserta."""
    _patch_bridge_multi(monkeypatch, teams_status=503, teams_raise=True)

    team_repo = _FakeTeamRepo()
    worker = BetanoFixtureDiscovery(
        bridge_url="http://test-bridge",
        api_client=_FakeApiClient([]), matcher=_FakeMatcher([]),
        fixture_repo=_FakeFixtureRepo(), team_repo=team_repo,
        league_ids=[1],
    )
    # Não deve raise
    await worker._refresh_teams_catalog()
    assert team_repo.bulk_upsert_calls == []


@pytest.mark.asyncio
async def test_refresh_teams_catalog_skips_entries_with_missing_fields(monkeypatch):
    """Entries sem team_id ou name são descartadas."""
    teams_payload = {
        "teams": [
            {"team_id": 100, "name": "OK Team", "source": "live"},
            {"team_id": None, "name": "Sem ID", "source": "live"},  # descarta
            {"team_id": 101, "name": "", "source": "live"},          # descarta
            {"team_id": 102, "name": "Outro OK", "source": "live"},
        ],
    }
    _patch_bridge_multi(monkeypatch, teams_payload=teams_payload)

    team_repo = _FakeTeamRepo()
    worker = BetanoFixtureDiscovery(
        bridge_url="http://test-bridge",
        api_client=_FakeApiClient([]), matcher=_FakeMatcher([]),
        fixture_repo=_FakeFixtureRepo(), team_repo=team_repo,
        league_ids=[1],
    )
    await worker._refresh_teams_catalog()

    assert len(team_repo.bulk_upsert_calls) == 1
    upserted = team_repo.bulk_upsert_calls[0]
    assert len(upserted) == 2  # só os 2 válidos
    assert {e.betano_team_id for e in upserted} == {100, 102}


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
