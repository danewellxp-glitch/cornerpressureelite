"""Testes de **lógica** dos parsers — independem de schema gismo real.

Validam o comportamento de filtragem, navegação defensiva e tipagem.
Os testes de **paths** (estrutura real do JSON gismo) ficam em
`test_parsers_schema.py`, pendentes de fixtures extraídas do `.mitm` golden.

Harness Fase A §8.1.
"""
import pytest

from data.providers.sportradar.parsers import (
    SportradarParseError,
    _safe_get,
    parse_match_info,
    parse_timeline_delta,
    parse_timeline_full,
)


# ---------------------------------------------------------------------------
# _safe_get — navegação defensiva
# ---------------------------------------------------------------------------

def test_safe_get_navigates_nested_dict():
    assert _safe_get({"a": {"b": {"c": 1}}}, "a", "b", "c") == 1


def test_safe_get_returns_default_for_missing_key():
    assert _safe_get({"a": {}}, "a", "b", default="x") == "x"


def test_safe_get_returns_default_for_wrong_type():
    assert _safe_get({"a": "string"}, "a", "b", default=None) is None


def test_safe_get_handles_list_index():
    assert _safe_get({"a": [{"b": 1}, {"b": 2}]}, "a", 0, "b") == 1
    assert _safe_get({"a": [{"b": 1}, {"b": 2}]}, "a", 1, "b") == 2


def test_safe_get_returns_default_for_out_of_range_index():
    assert _safe_get({"a": [{"b": 1}]}, "a", 5, "b", default="x") == "x"


def test_safe_get_returns_default_for_none_value():
    assert _safe_get({"a": None}, "a", "b", default="x") == "x"


# ---------------------------------------------------------------------------
# parse_match_info — erro em campo obrigatório ausente
# ---------------------------------------------------------------------------

def test_parse_match_info_raises_without_match_id():
    with pytest.raises(SportradarParseError):
        parse_match_info({"doc": [{"data": {"match": {}}}]})


def test_parse_match_info_raises_on_empty_response():
    with pytest.raises(SportradarParseError):
        parse_match_info({})


def test_parse_match_info_minimal_payload_succeeds():
    """Apenas `_id` é obrigatório — resto cai em defaults."""
    info = parse_match_info({
        "doc": [{"data": {"match": {"_id": 12345}}}]
    })
    assert info.match_id == "12345"
    assert info.home_team_name == "?"
    assert info.coverage.cornerson is False
    assert info.coverage.cardson is False


def test_parse_match_info_coverage_flags_parsed():
    info = parse_match_info({
        "doc": [{"data": {"match": {
            "_id": "1",
            "coverage": {
                "cornerson": True,
                "cardson": False,
                "lineups": True,
                "bookings": False,
                "extended": True,
            },
        }}}]
    })
    assert info.coverage.cornerson is True
    assert info.coverage.cardson is False
    assert info.coverage.lineups is True
    assert info.coverage.bookings is False
    assert info.coverage.extended is True


def test_parse_match_info_accepts_alternate_wrapper():
    """Tolera variação `data.match` em vez de `doc[0].data.match`."""
    info = parse_match_info({"data": {"match": {"_id": 42}}})
    assert info.match_id == "42"


# ---------------------------------------------------------------------------
# parse_timeline_delta — filtragem por since_uts
# ---------------------------------------------------------------------------

def _make_timeline(events: list) -> dict:
    return {"doc": [{"data": {"match": {"_id": "M1"}, "events": events}}]}


def test_parse_timeline_delta_filters_events_before_since():
    raw = _make_timeline([
        {"_id": "e1", "_doctype": "corner", "seconds": 100, "time": 5},
        {"_id": "e2", "_doctype": "yellowcard", "seconds": 500, "time": 25},
        {"_id": "e3", "_doctype": "corner", "seconds": 1000, "time": 50},
    ])
    td = parse_timeline_delta(raw, since_uts=200)
    assert [e.event_id for e in td.events] == ["e2", "e3"]


def test_parse_timeline_delta_last_seconds_tracks_max():
    raw = _make_timeline([
        {"_id": "e1", "_doctype": "corner", "seconds": 1000},
        {"_id": "e2", "_doctype": "corner", "seconds": 800},
        {"_id": "e3", "_doctype": "corner", "seconds": 1200},
    ])
    td = parse_timeline_delta(raw, since_uts=0)
    assert td.last_seconds == 1200


def test_parse_timeline_delta_no_new_events_keeps_since():
    raw = _make_timeline([
        {"_id": "e1", "_doctype": "corner", "seconds": 100},
    ])
    td = parse_timeline_delta(raw, since_uts=500)
    assert td.events == []
    assert td.last_seconds == 500


def test_parse_timeline_delta_returns_match_id():
    raw = _make_timeline([
        {"_id": "e1", "_doctype": "corner", "seconds": 100},
    ])
    td = parse_timeline_delta(raw, since_uts=0)
    assert td.match_id == "M1"


def test_parse_timeline_delta_skips_non_dict_events():
    raw = _make_timeline([
        {"_id": "e1", "_doctype": "corner", "seconds": 100},
        "garbage-string",
        None,
        {"_id": "e2", "_doctype": "corner", "seconds": 200},
    ])
    td = parse_timeline_delta(raw, since_uts=0)
    assert len(td.events) == 2


def test_parse_timeline_delta_event_fields_extracted():
    raw = _make_timeline([
        {
            "_id": "ev123",
            "_doctype": "yellowcard",
            "_typeid": "37",
            "seconds": 500,
            "time": 25,
            "team": "home",
            "player": {"name": "João da Silva"},
            "X": 75,
            "Y": 50,
            "name": "Cartão amarelo",
        },
    ])
    td = parse_timeline_delta(raw, since_uts=0)
    e = td.events[0]
    assert e.event_id == "ev123"
    assert e.type == "yellowcard"
    assert e.type_id == "37"
    assert e.minute == 25
    assert e.seconds == 500
    assert e.team == "home"
    assert e.player_name == "João da Silva"
    assert e.x == 75
    assert e.y == 50
    assert e.name == "Cartão amarelo"


def test_parse_timeline_delta_event_optional_fields_become_none():
    raw = _make_timeline([
        {"_id": "ev1", "_doctype": "corner", "seconds": 100, "time": 5},
    ])
    td = parse_timeline_delta(raw, since_uts=0)
    e = td.events[0]
    assert e.team is None
    assert e.player_name is None
    assert e.x is None
    assert e.y is None
    assert e.type_id is None


# ---------------------------------------------------------------------------
# parse_timeline_full — sem filtragem
# ---------------------------------------------------------------------------

def test_parse_timeline_full_returns_all_events():
    raw = _make_timeline([
        {"_id": "e1", "_doctype": "corner", "seconds": 100},
        {"_id": "e2", "_doctype": "yellowcard", "seconds": 500},
        {"_id": "e3", "_doctype": "corner", "seconds": 1000},
    ])
    events = parse_timeline_full(raw)
    assert len(events) == 3
    assert [e.event_id for e in events] == ["e1", "e2", "e3"]


def test_parse_timeline_full_empty_returns_empty():
    assert parse_timeline_full({}) == []
    assert parse_timeline_full({"doc": [{"data": {}}]}) == []
