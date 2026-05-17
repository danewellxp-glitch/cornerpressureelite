"""Unit tests do BridgeLineupsAdapter (Fase G.1 PARTE D)."""
from __future__ import annotations

import logging
from typing import Optional

import pytest

from data.providers.betano.bridge_lineups_adapter import BridgeLineupsAdapter


def _payload(roster: dict, version: int = 100) -> dict:
    return {
        "captured_at": 1778900000,
        "event_id": 84220231,
        "version": version,
        "from_cache": False,
        "data": {
            "version": version,
            "event": {"roster": roster},
        },
    }


def _roster(
    *,
    home_players: dict | None = None,
    away_players: dict | None = None,
    home_lineup: dict | None = None,
    away_lineup: dict | None = None,
    unknown_players: dict | None = None,
) -> dict:
    return {
        "homeRoster": {"id": 1, "name": "Home FC", "players": home_players or {}},
        "awayRoster": {"id": 2, "name": "Away FC", "players": away_players or {}},
        "unknownPlayers": unknown_players or {},
        "lineups": {
            "homeLineup": home_lineup or {},
            "awayLineup": away_lineup or {},
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
        self.requests: list[str] = []

    def get(self, url: str):
        self.requests.append(url)
        return self._responses.pop(0)

    async def close(self):
        pass


@pytest.mark.asyncio
async def test_normalize_roster_with_lineup():
    """Roster com homeLineup completo → CanonicalLineup home com starting_eleven."""
    home_players = {
        "100": {"name": "GK Hero", "shirtNumber": 1, "position": "GK",
                "positionDisplayName": "Goleiro"},
        "101": {"name": "Defender", "shirtNumber": 4, "position": "DF",
                "positionDisplayName": "Zagueiro"},
    }
    home_lineup = {
        "formation": "4-3-3",
        "lineup": [
            [{"playerId": 100}],
            [{"playerId": 101}],
        ],
        "benchPlayers": [],
    }
    roster = _roster(home_players=home_players, home_lineup=home_lineup)
    session = _FakeSession([_FakeResponse(200, _payload(roster))])
    adapter = BridgeLineupsAdapter(
        "http://b:8080", fixture_repo=_FakeRepo(42), session=session
    )

    lineups = await adapter.get_lineups(999)
    assert lineups is not None and len(lineups) == 2
    home = lineups[0]
    assert home.team_side == "home"
    assert home.source == "bridge_betano"
    assert home.formation == "4-3-3"
    assert home.coach_name is None  # gap Betano
    assert len(home.starting_eleven) == 2
    assert home.starting_eleven[0].name == "GK Hero"
    assert home.starting_eleven[0].player_id == 100
    assert home.starting_eleven[0].shirt_number == 1
    assert home.starting_eleven[0].position == "GK"
    assert home.starting_eleven[0].position_display == "Goleiro"
    assert home.tactical_grid == [[100], [101]]
    assert home.version == 100


@pytest.mark.asyncio
async def test_normalize_handles_unknown_players():
    """Player com unknownPlayerId UUID → preservado com player_id=None + nome do entry."""
    home_lineup = {
        "formation": "4-4-2",
        "lineup": [[
            {"unknownPlayerId": "abc-123-uuid", "name": "Surprise Sub"},
        ]],
        "benchPlayers": [],
    }
    roster = _roster(home_lineup=home_lineup)
    session = _FakeSession([_FakeResponse(200, _payload(roster))])
    adapter = BridgeLineupsAdapter(
        "http://b:8080", fixture_repo=_FakeRepo(42), session=session
    )

    lineups = await adapter.get_lineups(999)
    assert lineups is not None
    home = lineups[0]
    assert len(home.starting_eleven) == 1
    p = home.starting_eleven[0]
    assert p.player_id is None
    assert p.name == "Surprise Sub"
    assert p.shirt_number is None  # sem details no roster


@pytest.mark.asyncio
async def test_normalize_player_no_id_persists_anonymous(caplog):
    """AJUSTE 1: entry sem playerId E sem unknownPlayerId → preserva como
    PlayerEntry(name='<unknown>') + log WARNING. Nunca descartar."""
    home_lineup = {
        "formation": "4-3-3",
        "lineup": [[
            {"weirdField": "value"},  # nem playerId nem unknownPlayerId
        ]],
        "benchPlayers": [],
    }
    roster = _roster(home_lineup=home_lineup)
    session = _FakeSession([_FakeResponse(200, _payload(roster))])
    adapter = BridgeLineupsAdapter(
        "http://b:8080", fixture_repo=_FakeRepo(42), session=session
    )

    with caplog.at_level(logging.WARNING,
                        logger="cpes.providers.betano.bridge_lineups"):
        lineups = await adapter.get_lineups(999)
    assert lineups is not None
    home = lineups[0]
    assert len(home.starting_eleven) == 1
    p = home.starting_eleven[0]
    assert p.name == "<unknown>"
    assert p.player_id is None
    assert any("lineups.player_no_id" in r.message for r in caplog.records)


@pytest.mark.asyncio
async def test_normalize_handles_missing_roster():
    """Payload sem `event.roster` → CanonicalLineup com starting_eleven=[]."""
    payload = {"data": {"event": {}}}
    session = _FakeSession([_FakeResponse(200, payload)])
    adapter = BridgeLineupsAdapter(
        "http://b:8080", fixture_repo=_FakeRepo(42), session=session
    )

    lineups = await adapter.get_lineups(999)
    assert lineups is not None and len(lineups) == 2
    for ln in lineups:
        assert ln.formation is None
        assert ln.starting_eleven == []
        assert ln.has_starting_eleven is False


@pytest.mark.asyncio
async def test_position_displayName_preserved_pt_br():
    """positionDisplayName do roster.players[id] preserva localização Betano (pt-BR)."""
    home_players = {
        "200": {"name": "X", "position": "MF", "positionDisplayName": "Meio-campo"},
    }
    home_lineup = {
        "formation": "4-3-3",
        "lineup": [[{"playerId": 200}]],
        "benchPlayers": [],
    }
    roster = _roster(home_players=home_players, home_lineup=home_lineup)
    session = _FakeSession([_FakeResponse(200, _payload(roster))])
    adapter = BridgeLineupsAdapter(
        "http://b:8080", fixture_repo=_FakeRepo(42), session=session
    )

    lineups = await adapter.get_lineups(999)
    assert lineups[0].starting_eleven[0].position_display == "Meio-campo"


@pytest.mark.asyncio
async def test_coach_always_none_for_betano(caplog):
    """Gap conhecido: BETANO_GAPS_LINEUPS={'coach_name'}. Bridge sempre None.
    Log DEBUG `lineups_betano.coach_missing` emitido (AJUSTE 4c)."""
    roster = _roster(home_lineup={"formation": "3-5-2", "lineup": [], "benchPlayers": []})
    session = _FakeSession([_FakeResponse(200, _payload(roster))])
    adapter = BridgeLineupsAdapter(
        "http://b:8080", fixture_repo=_FakeRepo(42), session=session
    )

    with caplog.at_level(logging.DEBUG,
                        logger="cpes.providers.betano.bridge_lineups"):
        lineups = await adapter.get_lineups(999)
    assert all(ln.coach_name is None for ln in lineups)
    assert any("coach_missing" in r.message for r in caplog.records)


@pytest.mark.asyncio
async def test_returns_none_when_no_event_id():
    session = _FakeSession([])
    adapter = BridgeLineupsAdapter(
        "http://b:8080", fixture_repo=_FakeRepo(None), session=session
    )
    out = await adapter.get_lineups(999)
    assert out is None
    assert session.requests == []


@pytest.mark.asyncio
async def test_betano_event_id_hint_skips_repo_lookup():
    """Quando caller passa betano_event_id, adapter usa direto sem repo."""
    payload = _payload(_roster())
    session = _FakeSession([_FakeResponse(200, payload)])
    adapter = BridgeLineupsAdapter(
        "http://b:8080", fixture_repo=_FakeRepo(None), session=session
    )

    out = await adapter.get_lineups(999, betano_event_id=12345)
    assert out is not None
    assert "/event/12345/state" in session.requests[0]


@pytest.mark.asyncio
async def test_home_team_id_kwarg_accepted_but_ignored():
    """Bridge ignora `home_team_id` (compat Protocol). homeRoster/awayRoster
    já vem rotulado pelo payload."""
    payload = _payload(_roster())
    session = _FakeSession([_FakeResponse(200, payload)])
    adapter = BridgeLineupsAdapter(
        "http://b:8080", fixture_repo=_FakeRepo(42), session=session
    )

    # Passa hint absurdo — bridge ignora.
    out = await adapter.get_lineups(999, home_team_id=99999)
    assert out is not None and len(out) == 2
