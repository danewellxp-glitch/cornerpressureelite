"""Unit tests do APIFootballEventsAdapter (Fase F PARTE B)."""
from __future__ import annotations

import logging
from typing import Any

import pytest

from data.providers.apifootball.events_adapter import (
    APIFootballEventsAdapter,
    _map_af_to_canonical,
)


class _FakeAPIClient:
    def __init__(self, events: list[dict] | None = None, raises: bool = False):
        self._events = events or []
        self._raises = raises

    async def get_events(self, fixture_id: int) -> list[dict]:
        if self._raises:
            raise RuntimeError("simulated AF failure")
        return self._events

    async def check_status(self) -> dict:
        return {"requests": 1}


def _af_event(
    *, minute=10, extra=0, type_="Card", detail="Yellow Card", team_id=33, player="X"
) -> dict:
    return {
        "time": {"elapsed": minute, "extra": extra},
        "team": {"id": team_id, "name": "Team"},
        "player": {"id": 1, "name": player},
        "assist": {"id": None, "name": None},
        "type": type_,
        "detail": detail,
        "comments": None,
    }


@pytest.mark.asyncio
async def test_normalize_af_yellow_with_home_side_via_hint():
    adapter = APIFootballEventsAdapter(_FakeAPIClient([_af_event(team_id=33)]))
    events = await adapter.get_events(999, home_team_id=33)
    assert events is not None and len(events) == 1
    e = events[0]
    assert e.event_type == "YELL"
    assert e.team_side == "home"
    assert e.event_minute == 10
    assert e.player_name == "X"
    assert e.source == "apifootball"


@pytest.mark.asyncio
async def test_normalize_af_goal_normal_to_canonical():
    adapter = APIFootballEventsAdapter(_FakeAPIClient([
        _af_event(type_="Goal", detail="Normal Goal", team_id=99)
    ]))
    events = await adapter.get_events(999, home_team_id=33)
    assert events is not None and len(events) == 1
    assert events[0].event_type == "GOAL"
    assert events[0].team_side == "away"  # team_id=99 != home_team_id=33


@pytest.mark.asyncio
async def test_normalize_af_second_yellow_and_red_card_both_become_rcrd():
    adapter = APIFootballEventsAdapter(_FakeAPIClient([
        _af_event(type_="Card", detail="Second Yellow card"),
        _af_event(type_="Card", detail="Red Card"),
    ]))
    events = await adapter.get_events(999, home_team_id=33)
    assert events is not None and len(events) == 2
    assert events[0].event_type == "RCRD"
    assert events[1].event_type == "RCRD"


@pytest.mark.asyncio
async def test_normalize_af_subst_and_var_and_cgol():
    adapter = APIFootballEventsAdapter(_FakeAPIClient([
        _af_event(type_="subst", detail=""),
        _af_event(type_="Var", detail="Penalty awarded"),
        _af_event(type_="Var", detail="Goal cancelled"),
        _af_event(type_="Goal", detail="Cancelled Goal"),
    ]))
    events = await adapter.get_events(999, home_team_id=33)
    types = [e.event_type for e in events]
    assert types == ["SUBS", "VAR", "CGOL", "CGOL"]


@pytest.mark.asyncio
async def test_event_minute_adds_extra_time():
    """time.elapsed + time.extra (acréscimos) somam."""
    adapter = APIFootballEventsAdapter(_FakeAPIClient([
        _af_event(minute=45, extra=3),
    ]))
    events = await adapter.get_events(999, home_team_id=33)
    assert events is not None and events[0].event_minute == 48


@pytest.mark.asyncio
async def test_unmapped_type_logs_warning_and_uses_fallback(caplog):
    """Type+detail desconhecido → fallback type.upper() + WARNING log."""
    with caplog.at_level(logging.WARNING, logger="cpes.providers.apifootball.events"):
        canonical = _map_af_to_canonical("NewAFType", "NewDetail", fixture_id=42)
    assert canonical == "NEWAFTYPE"
    assert any(
        "events_adapter.af.unmapped_type" in r.message for r in caplog.records
    )


@pytest.mark.asyncio
async def test_side_unresolved_when_no_home_team_id():
    """Sem home_team_id, side fica None (graceful)."""
    adapter = APIFootballEventsAdapter(_FakeAPIClient([_af_event(team_id=33)]))
    events = await adapter.get_events(999)  # sem home_team_id
    assert events is not None and len(events) == 1
    assert events[0].team_side is None


@pytest.mark.asyncio
async def test_get_events_returns_none_on_client_error():
    adapter = APIFootballEventsAdapter(_FakeAPIClient(raises=True))
    events = await adapter.get_events(999, home_team_id=33)
    assert events is None
