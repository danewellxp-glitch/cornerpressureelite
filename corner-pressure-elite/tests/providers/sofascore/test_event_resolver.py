"""Tests do SofaScoreEventResolver (Fase K.1 PARTE B.5)."""
from __future__ import annotations

import logging
import time as time_mod
from datetime import datetime, timedelta, timezone

import pytest

from data.odds_provider import CanonicalFixture
from data.providers.sofascore.event_resolver import (
    SofaScoreEventResolver,
    _fuzzy_match,
)


class _FakeClient:
    def __init__(self, live_events=None, raises=False):
        self._events = live_events
        self._raises = raises
        self.live_calls = 0

    async def get_live_events(self):
        self.live_calls += 1
        if self._raises:
            raise RuntimeError("live boom")
        return self._events


class _FakeFixtureMapRepo:
    def __init__(self, rows=None):
        # rows: {fixture_id: {home_team, away_team}}
        self._rows = rows or {}

    async def get_by_fixture_id(self, fid: int):
        return self._rows.get(fid)


def _fix(fixture_id=42, home="Manchester United", away="Liverpool",
         kickoff: datetime | None = None) -> CanonicalFixture:
    return CanonicalFixture(
        fixture_id=fixture_id,
        home_team=home, away_team=away, league_id=39,
        starts_at_utc=kickoff or datetime.now(timezone.utc),
    )


def _live_event(id_=100, home="Manchester United", away="Liverpool",
                 start_ts: int | None = None) -> dict:
    return {
        "id": id_,
        "homeTeam": {"name": home},
        "awayTeam": {"name": away},
        "startTimestamp": start_ts,
    }


def test_fuzzy_match_exact_names_passes_threshold():
    events = [_live_event(100, "Manchester United", "Liverpool")]
    sid = _fuzzy_match(events, "Manchester United", "Liverpool", None)
    assert sid == 100


def test_fuzzy_match_minor_typo_passes():
    events = [_live_event(100, "Manchester Utd", "Liverpool FC")]
    sid = _fuzzy_match(events, "Manchester United", "Liverpool", None)
    assert sid == 100


def test_fuzzy_match_below_threshold_returns_none():
    events = [_live_event(100, "Real Madrid", "Barcelona")]
    sid = _fuzzy_match(events, "Manchester United", "Liverpool", None)
    assert sid is None


def test_fuzzy_match_no_events_returns_none():
    assert _fuzzy_match([], "X", "Y", None) is None


def test_fuzzy_match_kickoff_tiebreaker_excludes_wrong_time():
    """2 jogos mesmos nomes; horário muito diferente exclui."""
    kickoff_target = datetime(2026, 5, 17, 20, 0, tzinfo=timezone.utc)
    ts_target = int(kickoff_target.timestamp())
    ts_far = ts_target + 3600 * 4  # +4h fora da janela 30min
    events = [
        _live_event(100, "Manchester United", "Liverpool", start_ts=ts_far),
        _live_event(200, "Manchester United", "Liverpool", start_ts=ts_target),
    ]
    sid = _fuzzy_match(events, "Manchester United", "Liverpool", kickoff_target)
    assert sid == 200  # somente target dentro da janela


def test_fuzzy_match_ambiguous_warns(caplog):
    """2 candidates com scores muito próximos (delta<5): WARNING + aceita maior."""
    # Construído pra ter scores muito próximos:
    # cand1: home 100% + away 100% = 100
    # cand2: home 100% + away ~97% (1 char diff) = ~98.5, delta=1.5 < 5
    events = [
        _live_event(100, "Manchester United", "Liverpool"),
        _live_event(200, "Manchester United", "Liverpoo"),   # 1 char a menos (delta~3)
    ]
    with caplog.at_level(
        logging.WARNING, logger="cpes.providers.sofascore.event_resolver"
    ):
        sid = _fuzzy_match(events, "Manchester United", "Liverpool", None)
    assert sid == 100  # aceita maior (exact match)
    assert any("ambiguous" in r.message for r in caplog.records)


@pytest.mark.asyncio
async def test_resolver_returns_event_id_when_match():
    client = _FakeClient(live_events=[
        _live_event(15171563, "Real Salt Lake", "Colorado Rapids"),
    ])
    resolver = SofaScoreEventResolver(client)
    fixture = _fix(home="Real Salt Lake", away="Colorado Rapids")
    sid = await resolver.resolve(fixture)
    assert sid == 15171563
    assert client.live_calls == 1


@pytest.mark.asyncio
async def test_resolver_uses_fixture_map_names():
    """fixture_map_repo dá names canônicos — usados no fuzzy match."""
    repo = _FakeFixtureMapRepo(rows={
        42: {"home_team": "Manchester United", "away_team": "Liverpool"},
    })
    client = _FakeClient(live_events=[
        _live_event(100, "Manchester United", "Liverpool"),
    ])
    resolver = SofaScoreEventResolver(client, fixture_map_repo=repo)
    fixture = _fix(fixture_id=42, home="Man Utd", away="LFC")  # names diferentes
    sid = await resolver.resolve(fixture)
    assert sid == 100  # fuzzy passou via canon names do map


@pytest.mark.asyncio
async def test_resolver_caches_positive_hit():
    """2 chamadas seguidas → só 1 chamada ao client."""
    client = _FakeClient(live_events=[
        _live_event(100, "X", "Y"),
    ])
    resolver = SofaScoreEventResolver(client)
    fixture = _fix(home="X", away="Y")
    sid1 = await resolver.resolve(fixture)
    sid2 = await resolver.resolve(fixture)
    assert sid1 == sid2 == 100
    assert client.live_calls == 1  # cache hit


@pytest.mark.asyncio
async def test_resolver_caches_negative_hit():
    """Match miss → cacheia None (TTL menor)."""
    client = _FakeClient(live_events=[
        _live_event(100, "Other", "Match"),
    ])
    resolver = SofaScoreEventResolver(client)
    fixture = _fix(home="X", away="Y")
    sid1 = await resolver.resolve(fixture)
    sid2 = await resolver.resolve(fixture)
    assert sid1 is None and sid2 is None
    assert client.live_calls == 1  # negative cache evita 2ª chamada


@pytest.mark.asyncio
async def test_resolver_handles_client_error_returns_none():
    client = _FakeClient(raises=True)
    resolver = SofaScoreEventResolver(client)
    sid = await resolver.resolve(_fix())
    assert sid is None


@pytest.mark.asyncio
async def test_resolver_skips_events_without_id():
    client = _FakeClient(live_events=[
        {"homeTeam": {"name": "A"}, "awayTeam": {"name": "B"}},  # sem id
        _live_event(99, "A", "B"),
    ])
    resolver = SofaScoreEventResolver(client)
    sid = await resolver.resolve(_fix(home="A", away="B"))
    assert sid == 99


@pytest.mark.asyncio
async def test_resolver_invalidate_clears_cache():
    client = _FakeClient(live_events=[_live_event(100, "X", "Y")])
    resolver = SofaScoreEventResolver(client)
    fixture = _fix(home="X", away="Y")
    await resolver.resolve(fixture)
    resolver.invalidate(fixture.fixture_id)
    await resolver.resolve(fixture)
    assert client.live_calls == 2
