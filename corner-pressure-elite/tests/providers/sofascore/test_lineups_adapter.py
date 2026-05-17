"""Unit tests do SofaScoreLineupsAdapter (Fase K.1 PARTE B.4)."""
from __future__ import annotations

import logging
from datetime import date

import pytest

from data.providers.sofascore.lineups_adapter import (
    SofaScoreLineupsAdapter,
    _map_position,
    _missing_reason,
    _parse_expected_end,
)


class _FakeClient:
    def __init__(self, lineups=None, managers=None,
                 lineups_raises=False, managers_raises=False):
        self._lineups = lineups
        self._managers = managers
        self._lineups_raises = lineups_raises
        self._managers_raises = managers_raises

    async def get_lineups(self, event_id):
        if self._lineups_raises:
            raise RuntimeError("lineups boom")
        return self._lineups

    async def get_managers(self, event_id):
        if self._managers_raises:
            raise RuntimeError("managers boom")
        return self._managers

    async def health(self):
        return True


def _sample_team(*, formation="4-3-3", players=None, missing=None):
    return {
        "formation": formation,
        "players": players or [],
        "missingPlayers": missing or [],
    }


def _player(name="X", pid=1, pos="G", shirt=1, substitute=False):
    return {
        "player": {"name": name, "id": pid, "position": pos},
        "shirtNumber": shirt,
        "position": pos,
        "substitute": substitute,
    }


def _missing(name="Y", pid=2, type_="missing", reason=1, end="2026-12-01T00:00:00+00:00"):
    return {
        "player": {"name": name, "id": pid},
        "type": type_,
        "reason": reason,
        "expectedEndDate": end,
    }


def test_map_position_known():
    assert _map_position("G") == "GK"
    assert _map_position("D") == "DF"
    assert _map_position("M") == "MF"
    assert _map_position("F") == "FW"


def test_map_position_unmapped_warns(caplog):
    with caplog.at_level(logging.WARNING, logger="cpes.providers.sofascore.lineups"):
        out = _map_position("XX")
    assert out == "XX"
    assert any("unmapped_position" in r.message for r in caplog.records)


def test_missing_reason_doubtful_preserves_code():
    assert _missing_reason("doubtful", 1) == ("doubtful", 1)
    assert _missing_reason("doubtful", None) == ("doubtful", None)


def test_missing_reason_missing_with_known_code():
    assert _missing_reason("missing", 1) == ("injury", 1)
    assert _missing_reason("missing", 2) == ("suspension", 2)


def test_missing_reason_unknown_code_warns(caplog):
    with caplog.at_level(logging.WARNING, logger="cpes.providers.sofascore.lineups"):
        r, c = _missing_reason("missing", 99)
    assert r == "unknown" and c == 99
    assert any("unmapped_reason_code" in r.message for r in caplog.records)


def test_parse_expected_end_iso():
    assert _parse_expected_end("2026-11-09T00:00:00+00:00") == date(2026, 11, 9)
    assert _parse_expected_end(None) is None
    assert _parse_expected_end("bad") is None


@pytest.mark.asyncio
async def test_no_resolver_returns_none():
    adapter = SofaScoreLineupsAdapter(_FakeClient(), event_id_resolver=None)
    out = await adapter.get_lineups(999)
    assert out is None


@pytest.mark.asyncio
async def test_normalize_lineups_with_coach_and_missing():
    client = _FakeClient(
        lineups={
            "home": _sample_team(
                formation="4-3-3",
                players=[_player("Starter", pos="G"), _player("Bench", pos="F", substitute=True)],
                missing=[_missing("Hurt", type_="missing", reason=1)],
            ),
            "away": _sample_team(
                formation="4-4-2",
                players=[_player("OK", pos="D")],
                missing=[],
            ),
        },
        managers={
            "homeManager": {"name": "Coach Home", "id": 100},
            "awayManager": {"name": "Coach Away", "id": 200},
        },
    )

    async def resolver(_): return 12345

    adapter = SofaScoreLineupsAdapter(client, event_id_resolver=resolver)
    out = await adapter.get_lineups(999)
    assert out is not None and len(out) == 2
    home, away = out
    # Coach (★ resolve gap Betano)
    assert home.coach_name == "Coach Home"
    assert away.coach_name == "Coach Away"
    # Formation
    assert home.formation == "4-3-3"
    # Players starting/sub split
    assert len(home.starting_eleven) == 1
    assert home.starting_eleven[0].position == "GK"
    assert len(home.substitutes) == 1
    # Missing
    assert len(home.missing_players) == 1
    mp = home.missing_players[0]
    assert mp.name == "Hurt"
    assert mp.reason == "injury"
    assert mp.expected_return == date(2026, 12, 1)
    assert mp.source == "sofascore"


@pytest.mark.asyncio
async def test_lineups_client_error_returns_none():
    client = _FakeClient(lineups_raises=True, managers={"homeManager": {"name": "A"}})

    async def resolver(_): return 1

    adapter = SofaScoreLineupsAdapter(client, event_id_resolver=resolver)
    out = await adapter.get_lineups(999)
    assert out is None


@pytest.mark.asyncio
async def test_managers_error_still_returns_lineups_without_coach():
    """Managers exceção: gather retorna Exception → coach_name=None nos 2 lados."""
    client = _FakeClient(
        lineups={"home": _sample_team(players=[_player()]), "away": _sample_team(players=[_player()])},
        managers_raises=True,
    )

    async def resolver(_): return 1

    adapter = SofaScoreLineupsAdapter(client, event_id_resolver=resolver)
    out = await adapter.get_lineups(999)
    assert out is not None and len(out) == 2
    assert all(ln.coach_name is None for ln in out)
