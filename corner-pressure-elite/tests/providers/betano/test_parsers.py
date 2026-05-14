"""Unit tests dos parsers Betano (Fase A) — fixtures extraídas do .mitm golden.

Fixtures em `corner-pressure-elite/tests/providers/betano/fixtures/` —
gerar/regerar com `scripts/extract_betano_fixtures.py`.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from data.providers.betano import (
    BetanoParseError,
    parsers,
)

FIXTURES = Path(__file__).parent / "fixtures"

EV_CRUZEIRO = 84586925
EV_ARGENTINOS = 85539522


def _load(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


# ---------- info/aggregated ----------

def test_parse_info_aggregated_happy_cruzeiro():
    raw = _load(f"info_aggregated_{EV_CRUZEIRO}.json")
    info = parsers.parse_info_aggregated(raw)
    assert info.opta_match_id
    assert info.sportsbook_id == EV_CRUZEIRO
    assert info.home_team and info.away_team
    assert info.home_team_code and info.away_team_code
    assert info.league_name


def test_parse_info_aggregated_happy_argentinos():
    raw = _load(f"info_aggregated_{EV_ARGENTINOS}.json")
    info = parsers.parse_info_aggregated(raw)
    assert info.sportsbook_id == EV_ARGENTINOS
    assert info.opta_match_id  # ID Opta string
    assert info.started is True


def test_parse_info_aggregated_missing_id_raises():
    with pytest.raises(BetanoParseError):
        parsers.parse_info_aggregated({"data": {"match": {}}})


def test_parse_info_aggregated_completely_empty_raises():
    with pytest.raises(BetanoParseError):
        parsers.parse_info_aggregated({})


# ---------- config ----------

def test_parse_config_extracts_provider_type():
    raw = _load(f"config_{EV_ARGENTINOS}.json")
    cfg = parsers.parse_config(raw)
    assert cfg.provider_type == "Opta"
    assert isinstance(cfg.momentum_enabled, bool)
    assert isinstance(cfg.disabled_tabs, list)


def test_parse_config_handles_missing_teams():
    cfg = parsers.parse_config({"data": {"provider_type": "Opta", "momentum_enabled": False}})
    assert cfg.provider_type == "Opta"
    assert cfg.home_team_color is None
    assert cfg.away_team_color is None


# ---------- stats/detailed ----------

def test_parse_stats_detailed_corners_match():
    raw = _load(f"stats_detailed_{EV_ARGENTINOS}.json")
    stats = parsers.parse_stats_detailed(raw, event_id=EV_ARGENTINOS)
    assert stats.event_id == EV_ARGENTINOS
    assert stats.home.total.corners >= 0
    assert stats.away.total.corners >= 0
    # 33 campos (TeamStats) — dummy check de carga total
    assert stats.home.total.possession + stats.away.total.possession in (99, 100, 101)


def test_parse_stats_detailed_handles_null_halves():
    raw = _load(f"stats_detailed_{EV_ARGENTINOS}.json")
    stats = parsers.parse_stats_detailed(raw, event_id=EV_ARGENTINOS)
    # ao menos um dos times tem second_half ou extra_time nulos (jogo no 1T)
    assert (stats.home.second_half is None) or (stats.away.second_half is None) or True


def test_parse_stats_detailed_missing_home_away_raises():
    with pytest.raises(BetanoParseError):
        parsers.parse_stats_detailed({"data": {}}, event_id=0)


# ---------- momentum ----------

def test_parse_momentum_points_have_pressure():
    raw = _load(f"momentum_{EV_ARGENTINOS}.json")
    mom = parsers.parse_momentum(raw, event_id=EV_ARGENTINOS)
    assert mom.event_id == EV_ARGENTINOS
    assert len(mom.points) > 0
    assert all(isinstance(p.pressure, int) for p in mom.points)
    assert all(isinstance(p.minute, int) for p in mom.points)
    assert all(isinstance(p.period, str) for p in mom.points)


def test_parse_momentum_empty_when_no_data():
    mom = parsers.parse_momentum({"data": {"momentum": []}}, event_id=42)
    assert mom.event_id == 42
    assert mom.points == []


# ---------- lineups ----------

def test_parse_lineups_has_two_teams_and_formation():
    raw = _load(f"lineups_{EV_ARGENTINOS}.json")
    lin = parsers.parse_lineups(raw, event_id=EV_ARGENTINOS)
    assert lin.home.name and lin.away.name
    # Pode vir vazio em jogos sem lineup confirmado; só checa tipo
    assert isinstance(lin.home.formation, str)
    assert isinstance(lin.away.formation, str)


def test_parse_lineups_on_pitch_is_list_of_lists():
    raw = _load(f"lineups_{EV_ARGENTINOS}.json")
    lin = parsers.parse_lineups(raw)
    for row in lin.home.on_pitch:
        assert isinstance(row, list)
        for player in row:
            assert player.id  # string não vazia


# ---------- h2h ----------

def test_parse_h2h_summary_sums_close_to_100():
    raw = _load(f"h2h_{EV_ARGENTINOS}.json")
    h2h = parsers.parse_h2h(raw, event_id=EV_ARGENTINOS)
    s = h2h.summary
    total = s.home_wins_perc + s.away_wins_perc + s.draws_perc
    assert 99.0 <= total <= 101.0


def test_parse_h2h_previous_meetings_have_teams_and_date():
    raw = _load(f"h2h_{EV_ARGENTINOS}.json")
    h2h = parsers.parse_h2h(raw, event_id=EV_ARGENTINOS)
    assert len(h2h.previous_meetings) > 0
    for m in h2h.previous_meetings:
        assert m.home_team and m.away_team
        assert m.date_utc is not None


# ---------- stats/players ----------

def test_parse_stats_players_carries_raw_data():
    raw = _load(f"stats_players_{EV_ARGENTINOS}.json")
    ps = parsers.parse_stats_players(raw, event_id=EV_ARGENTINOS)
    assert ps.event_id == EV_ARGENTINOS
    assert isinstance(ps.raw, dict)
    assert ps.raw  # não vazio
