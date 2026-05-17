"""Unit tests do APIFootballLineupsAdapter (Fase G.1 PARTE D)."""
from __future__ import annotations

import logging
from typing import Any

import pytest

from data.providers.apifootball.lineups_adapter import (
    APIFootballLineupsAdapter,
    _map_position,
)


class _FakeAPIClient:
    def __init__(self, raw: list[dict] | None = None, raises: bool = False,
                 missing: bool = False):
        self._raw = raw or []
        self._raises = raises
        self._missing = missing

    async def get_lineups(self, fixture_id: int):
        if self._missing:
            raise AttributeError("api_client legacy sem get_lineups")
        if self._raises:
            raise RuntimeError("simulated AF failure")
        return self._raw

    async def check_status(self):
        return {"requests": 1}


def _team_block(*, team_id: int, formation="4-3-3", coach_name="Coach X",
                start: list[dict] | None = None, subs: list[dict] | None = None) -> dict:
    return {
        "team": {"id": team_id, "name": f"Team {team_id}"},
        "formation": formation,
        "coach": {"id": 1, "name": coach_name},
        "startXI": start or [],
        "substitutes": subs or [],
    }


def _player(*, pid=10, name="Player", number=10, pos="M") -> dict:
    return {"player": {"id": pid, "name": name, "number": number, "pos": pos}}


@pytest.mark.asyncio
async def test_normalize_af_lineup_with_coach():
    """AF response 2 entries, com hint home_team_id resolve corretamente."""
    raw = [
        _team_block(team_id=33, formation="4-2-3-1", coach_name="HomeCoach",
                    start=[_player(pid=1, name="GK", number=1, pos="G")]),
        _team_block(team_id=99, formation="5-4-1", coach_name="AwayCoach",
                    start=[_player(pid=2, name="DF", number=4, pos="D")]),
    ]
    adapter = APIFootballLineupsAdapter(_FakeAPIClient(raw))
    out = await adapter.get_lineups(999, home_team_id=33)

    assert out is not None and len(out) == 2
    home, away = out[0], out[1]
    assert home.team_side == "home"
    assert home.formation == "4-2-3-1"
    assert home.coach_name == "HomeCoach"
    assert home.starting_eleven[0].position == "GK"  # G → GK
    assert home.source == "apifootball"
    assert away.team_side == "away"
    assert away.coach_name == "AwayCoach"


@pytest.mark.asyncio
async def test_normalize_af_resolves_home_via_team_id():
    """AJUSTE 2: home_team_id hint deve resolver via team.id, não por ordem.
    Se home_team_id está no segundo entry, deve virar 'home' mesmo assim."""
    raw = [
        _team_block(team_id=99, coach_name="Visitante"),  # ordem trocada
        _team_block(team_id=33, coach_name="Mandante"),
    ]
    adapter = APIFootballLineupsAdapter(_FakeAPIClient(raw))
    out = await adapter.get_lineups(999, home_team_id=33)

    assert out is not None and len(out) == 2
    home = out[0]
    away = out[1]
    assert home.team_side == "home"
    assert home.coach_name == "Mandante"  # team_id=33 = casa, mesmo sendo 2º na ordem
    assert away.team_side == "away"
    assert away.coach_name == "Visitante"


@pytest.mark.asyncio
async def test_normalize_af_fallback_to_order_when_no_hint(caplog):
    """Sem home_team_id → cai na convenção response[0]=home, [1]=away.
    Log DEBUG `lineups_af.using_order_convention` emitido."""
    raw = [
        _team_block(team_id=99, coach_name="First"),
        _team_block(team_id=33, coach_name="Second"),
    ]
    adapter = APIFootballLineupsAdapter(_FakeAPIClient(raw))
    with caplog.at_level(logging.DEBUG,
                        logger="cpes.providers.apifootball.lineups"):
        out = await adapter.get_lineups(999)

    assert out is not None and len(out) == 2
    assert out[0].team_side == "home"
    assert out[0].coach_name == "First"  # ordem convencional
    assert any("using_order_convention" in r.message for r in caplog.records)


def test_map_position_known_letters():
    assert _map_position("G") == "GK"
    assert _map_position("D") == "DF"
    assert _map_position("M") == "MF"
    assert _map_position("F") == "FW"
    assert _map_position("g") == "GK"  # case-insensitive


def test_map_position_none_returns_none():
    assert _map_position(None) is None
    assert _map_position("") is None


def test_unmapped_position_logs_warning(caplog):
    """AJUSTE 3: pos não-mapeada → log WARNING + fallback upper()."""
    with caplog.at_level(logging.WARNING,
                        logger="cpes.providers.apifootball.lineups"):
        result = _map_position("ZZ")
    assert result == "ZZ"
    assert any("unmapped_position" in r.message for r in caplog.records)


@pytest.mark.asyncio
async def test_returns_none_when_client_lacks_method():
    """api_client legado sem get_lineups → None silencioso, sem crash."""
    adapter = APIFootballLineupsAdapter(_FakeAPIClient(missing=True))
    out = await adapter.get_lineups(999, home_team_id=33)
    assert out is None


@pytest.mark.asyncio
async def test_returns_empty_when_no_response():
    """response vazio = []."""
    adapter = APIFootballLineupsAdapter(_FakeAPIClient([]))
    out = await adapter.get_lineups(999, home_team_id=33)
    assert out == []


@pytest.mark.asyncio
async def test_handles_substitutes_with_is_substitute_true():
    raw = [_team_block(
        team_id=33,
        start=[_player(pid=1, name="StartGK", number=1, pos="G")],
        subs=[_player(pid=99, name="BenchGK", number=22, pos="G")],
    )]
    adapter = APIFootballLineupsAdapter(_FakeAPIClient(raw))
    out = await adapter.get_lineups(999, home_team_id=33)
    assert out is not None
    home = out[0]
    assert len(home.starting_eleven) == 1
    assert home.starting_eleven[0].is_substitute is False
    assert len(home.substitutes) == 1
    assert home.substitutes[0].is_substitute is True
    assert home.substitutes[0].shirt_number == 22


@pytest.mark.asyncio
async def test_client_error_returns_none(caplog):
    """Erro genérico no client → log warning + None."""
    adapter = APIFootballLineupsAdapter(_FakeAPIClient(raises=True))
    with caplog.at_level(logging.WARNING,
                        logger="cpes.providers.apifootball.lineups"):
        out = await adapter.get_lineups(999, home_team_id=33)
    assert out is None
    assert any("client_error" in r.message for r in caplog.records)
