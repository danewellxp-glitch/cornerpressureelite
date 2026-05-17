"""Unit tests do SofaScoreEventsAdapter (Fase K.1 PARTE B.3)."""
from __future__ import annotations

import logging

import pytest

from data.providers.sofascore.events_adapter import (
    SofaScoreEventsAdapter,
    _map_incident_type,
    _player_name,
    _team_side,
)


class _FakeClient:
    def __init__(self, incidents=None):
        self._incidents = incidents
        self.calls: list[int] = []

    async def get_incidents(self, event_id):
        self.calls.append(event_id)
        return self._incidents

    async def health(self):
        return True


def test_map_incident_type_known():
    assert _map_incident_type("goal", None) == "GOAL"
    assert _map_incident_type("card", "yellow") == "YELL"
    assert _map_incident_type("card", "red") == "RCRD"
    assert _map_incident_type("card", "yellowRed") == "RCRD"
    assert _map_incident_type("substitution", None) == "SUBS"
    assert _map_incident_type("injuryTime", None) == "StoppageTime"
    assert _map_incident_type("varDecision", None) == "VAR"
    assert _map_incident_type("corner", None) == "CRNR"
    assert _map_incident_type("penalty", None) == "PENL"


def test_map_incident_type_period_by_text():
    assert _map_incident_type("period", None, "First half") == "PBEG"
    assert _map_incident_type("period", None, "Half time") == "PEND"


def test_map_incident_type_unmapped_logs_warning(caplog):
    with caplog.at_level(logging.WARNING, logger="cpes.providers.sofascore.events"):
        out = _map_incident_type("comeback", None)
    assert out == "COMEBACK"
    assert any("unmapped_type" in r.message for r in caplog.records)


def test_team_side_via_isHome():
    assert _team_side({"isHome": True}) == "home"
    assert _team_side({"isHome": False}) == "away"
    assert _team_side({"other": 1}) is None


def test_player_name_from_player_or_playerIn():
    assert _player_name({"player": {"name": "X"}}) == "X"
    assert _player_name({"playerIn": {"name": "Y"}}) == "Y"
    assert _player_name({"playerOut": {"name": "Z"}}) is None  # só player/playerIn


@pytest.mark.asyncio
async def test_no_resolver_returns_none():
    adapter = SofaScoreEventsAdapter(_FakeClient(), event_id_resolver=None)
    out = await adapter.get_events(999)
    assert out is None


@pytest.mark.asyncio
async def test_normalize_basic_incidents():
    incidents = [
        {"incidentType": "goal", "incidentClass": "regular", "time": 23,
         "isHome": True, "player": {"name": "Goalscorer", "id": 1}},
        {"incidentType": "card", "incidentClass": "yellow", "time": 45,
         "isHome": False, "player": {"name": "Carded"}},
    ]
    client = _FakeClient(incidents=incidents)

    async def resolver(_): return 12345

    adapter = SofaScoreEventsAdapter(client, event_id_resolver=resolver)
    out = await adapter.get_events(999)
    assert out is not None and len(out) == 2
    g, c = out
    assert g.event_type == "GOAL" and g.team_side == "home" and g.event_minute == 23
    assert g.player_name == "Goalscorer" and g.source == "sofascore"
    assert c.event_type == "YELL" and c.team_side == "away" and c.event_minute == 45


@pytest.mark.asyncio
async def test_incident_without_time_is_dropped():
    incidents = [
        {"incidentType": "goal", "time": 10, "isHome": True, "player": {"name": "OK"}},
        {"incidentType": "goal", "isHome": True},  # sem time → dropado
    ]
    client = _FakeClient(incidents=incidents)

    async def resolver(_): return 1

    adapter = SofaScoreEventsAdapter(client, event_id_resolver=resolver)
    out = await adapter.get_events(999)
    assert out is not None and len(out) == 1


@pytest.mark.asyncio
async def test_empty_incidents_returns_empty_list():
    client = _FakeClient(incidents=[])

    async def resolver(_): return 1

    adapter = SofaScoreEventsAdapter(client, event_id_resolver=resolver)
    out = await adapter.get_events(999)
    assert out == []
