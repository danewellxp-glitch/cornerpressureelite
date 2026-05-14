"""Unit tests Fase B — markets / catalog / WS parsers + fuzzy match.

Fixtures golden em `tests/providers/betano/fixtures/` (extraídas do `.mitm`).
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from data.providers.betano import (
    BetanoCatalog,
    BetanoParseError,
    BetanoWSClient,
    parsers,
)
from data.providers.betano.codes import (
    MARKET_CODES_CARDS_MAIN,
    MARKET_CODES_CORNERS_MAIN,
)
from data.providers.betano.session import BetanoSession

FIXTURES = Path(__file__).parent / "fixtures"
EV_CRUZEIRO = 84586925
EV_ARGENTINOS = 85539522


def _load(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


# ============================================================
# parse_event_snapshot
# ============================================================

def test_parse_event_snapshot_extracts_betradar_match_id():
    snap = parsers.parse_event_snapshot(_load(f"live_event_latest_{EV_CRUZEIRO}.json"))
    assert snap.event_id == EV_CRUZEIRO
    assert snap.betradar_match_id == 70401308
    assert snap.sport_id == "FOOT"
    assert snap.is_live is True
    assert len(snap.participants) == 2
    assert snap.participants[0].is_home is True


def test_parse_event_snapshot_parses_markets_and_selections_dicts():
    snap = parsers.parse_event_snapshot(_load(f"live_event_latest_{EV_CRUZEIRO}.json"))
    assert len(snap.markets) > 0
    assert len(snap.selections) > 0
    # CNOU deve aparecer (escanteios)
    cnou = [m for m in snap.markets.values() if m.type_code == MARKET_CODES_CORNERS_MAIN]
    assert len(cnou) >= 1
    # TCOU deve aparecer (cartões)
    tcou = [m for m in snap.markets.values() if m.type_code == MARKET_CODES_CARDS_MAIN]
    assert len(tcou) >= 1


def test_parse_event_snapshot_missing_event_id_raises():
    with pytest.raises(BetanoParseError):
        parsers.parse_event_snapshot({"event": {}})


# ============================================================
# extract_over_under
# ============================================================

def test_extract_over_under_picks_requested_handicap():
    snap = parsers.parse_event_snapshot(_load(f"live_event_latest_{EV_CRUZEIRO}.json"))
    ou = parsers.extract_over_under(snap, MARKET_CODES_CORNERS_MAIN, linha=9.5)
    assert ou is not None
    assert ou.handicap == 9.5
    assert ou.odd_over > 0 and ou.odd_under > 0
    assert ou.market_code == MARKET_CODES_CORNERS_MAIN


def test_extract_over_under_picks_main_when_no_handicap():
    snap = parsers.parse_event_snapshot(_load(f"live_event_latest_{EV_CRUZEIRO}.json"))
    ou = parsers.extract_over_under(snap, MARKET_CODES_CORNERS_MAIN)
    assert ou is not None
    # principal: a com odd_over mais próxima de 1.95
    assert abs(ou.odd_over - 1.95) <= 0.5


def test_extract_over_under_returns_none_for_unknown_linha():
    snap = parsers.parse_event_snapshot(_load(f"live_event_latest_{EV_CRUZEIRO}.json"))
    assert parsers.extract_over_under(snap, MARKET_CODES_CORNERS_MAIN, linha=99.5) is None


def test_extract_over_under_cards_tcou():
    snap = parsers.parse_event_snapshot(_load(f"live_event_latest_{EV_CRUZEIRO}.json"))
    ou = parsers.extract_over_under(snap, MARKET_CODES_CARDS_MAIN)
    assert ou is not None
    assert ou.market_code == MARKET_CODES_CARDS_MAIN
    assert ou.handicap > 0


def test_extract_over_under_handles_missing_selection_gracefully():
    # remove uma selection a propósito
    raw = _load(f"live_event_latest_{EV_CRUZEIRO}.json")
    # Pega uma CNOU e dropa sua primeira selection (over)
    for mid, m in raw["markets"].items():
        if m.get("type") == "CNOU":
            target_sel = str(m["selectionIdList"][0])
            raw["selections"].pop(target_sel, None)
            break
    snap = parsers.parse_event_snapshot(raw)
    # extract com linha específica que perdeu o over → não deve crashear; vira None
    # ou cai pra outra linha (depende do main). Aceita ambos.
    ou = parsers.extract_over_under(snap, MARKET_CODES_CORNERS_MAIN)
    assert ou is None or (ou.odd_over > 0 and ou.odd_under > 0)


# ============================================================
# parse_live_overview_events
# ============================================================

def test_parse_live_overview_returns_many_events():
    raw = _load("live_overview_latest_unknown.json")
    events = parsers.parse_live_overview_events(raw)
    assert len(events) > 50  # captura tinha 96
    # ao menos 1 FOOT live
    foot_live = [e for e in events if e.sport_id == "FOOT" and e.is_live]
    assert len(foot_live) >= 1


def test_parse_live_overview_event_has_participants_and_start_time():
    raw = _load("live_overview_latest_unknown.json")
    events = parsers.parse_live_overview_events(raw)
    foot = [e for e in events if e.sport_id == "FOOT"]
    assert foot, "esperava ao menos 1 FOOT event"
    e = foot[0]
    assert len(e.participants) >= 2
    assert e.start_time.tzinfo is not None  # tz-aware


# ============================================================
# parse_statsplayer
# ============================================================

def test_parse_statsplayer_picks_numeric_sr_and_opta_ids():
    fake = {
        "data": {
            "statPlayerModels": [
                {"statType": 7},
                {"matchId": "70401308", "stageId": "70401308", "statType": 4},
                {"matchId": "55n9jqpc9lsi0nxt4zpw29ez8", "statType": 6},
            ]
        }
    }
    mapping = parsers.parse_statsplayer(fake, event_id=84586925)
    assert mapping.event_id == 84586925
    assert mapping.sr_match_id == "70401308"
    assert mapping.opta_match_id == "55n9jqpc9lsi0nxt4zpw29ez8"
    assert 4 in mapping.available_stat_types
    assert 6 in mapping.available_stat_types
    assert 7 in mapping.available_stat_types


def test_parse_statsplayer_empty_models_returns_none_ids():
    mapping = parsers.parse_statsplayer({"data": {"statPlayerModels": []}}, event_id=42)
    assert mapping.sr_match_id is None
    assert mapping.opta_match_id is None
    assert mapping.available_stat_types == []


# ============================================================
# parse_match_event
# ============================================================

def test_parse_match_event_extracts_xy_and_flags():
    payload = json.dumps({
        "event_data": {
            "ball_position": {"x": 67.2, "y": 12.4},
            "ball_position_end": {"x": 65.7, "y": 39.1},
            "team_id": "bd6vujl7jfv4wtc8gvo1o1t5y",
            "player_id": "19154029",
            "is_possession": False,
            "is_attack": True,
            "is_dangerous_attack": False,
        },
        "event_match_id": "55n9jqpc9lsi0nxt4zpw29ez8",
        "sportsbook_match_id": "84586925",
        "event_type": 0,
        "event_period_id": 2,
        "event_match_minute": 24,
        "event_match_second": 29,
        "event_provider_type": "Opta",
    })
    me = parsers.parse_match_event(payload)
    assert me.opta_match_id == "55n9jqpc9lsi0nxt4zpw29ez8"
    assert me.sportsbook_match_id == 84586925
    assert me.x == 67.2 and me.y == 12.4
    assert me.x_end == 65.7 and me.y_end == 39.1
    assert me.is_attack is True
    assert me.is_dangerous_attack is False
    assert me.minute == 24 and me.seconds == 29


def test_parse_match_event_handles_no_ball_position_end():
    payload = json.dumps({
        "event_data": {
            "ball_position": {"x": 50.0, "y": 50.0},
            "team_id": "t",
            "is_attack": False,
        },
        "event_match_id": "opta1",
        "sportsbook_match_id": 1,
        "event_type": 3,
        "event_period_id": 1,
        "event_match_minute": 5,
        "event_match_second": 0,
        "event_provider_type": "Opta",
    })
    me = parsers.parse_match_event(payload)
    assert me.x_end is None and me.y_end is None
    assert me.is_attack is False


def test_parse_match_event_initial_returns_none_without_event_data():
    assert parsers.parse_match_event_initial({"foo": "bar"}) is None


# ============================================================
# BetanoCatalog fuzzy match
# ============================================================

def _kickoff(epoch_ms: int) -> datetime:
    return datetime.fromtimestamp(epoch_ms / 1000, tz=timezone.utc)


def _make_catalog_with_cache(raw_overview_path: str = "live_overview_latest_unknown.json") -> BetanoCatalog:
    sess = BetanoSession(cookies={}, kbversion="3.41.0")
    cat = BetanoCatalog(sess)
    raw = _load(raw_overview_path)
    cat._events_cache = parsers.parse_live_overview_events(raw)
    return cat


@pytest.mark.asyncio
async def test_catalog_find_by_fixture_normalizes_team_names():
    """Match com nome acentuado deve achar evento na captura."""
    cat = _make_catalog_with_cache()
    # encontra um FOOT event na cache para usar como verdade
    foot = [e for e in cat._events_cache if e.sport_id == "FOOT" and len(e.participants) >= 2]
    assert foot, "esperava FOOT events na captura"
    ev = foot[0]
    home = ev.participants[0].name
    away = ev.participants[1].name
    # adultera com acento/caixa
    home_query = home.upper()
    away_query = away.upper()
    res = await cat.find_event_by_fixture(
        fixture_id=12345,
        team_home=home_query,
        team_away=away_query,
        kickoff_at=ev.start_time,
    )
    assert res == ev.event_id


@pytest.mark.asyncio
async def test_catalog_find_by_fixture_respects_kickoff_window():
    cat = _make_catalog_with_cache()
    foot = [e for e in cat._events_cache if e.sport_id == "FOOT" and len(e.participants) >= 2]
    ev = foot[0]
    # kickoff +20min fora da janela de 15
    kickoff_off = datetime.fromtimestamp(
        ev.start_time.timestamp() + 20 * 60, tz=timezone.utc
    )
    res = await cat.find_event_by_fixture(
        fixture_id=12346,
        team_home=ev.participants[0].name,
        team_away=ev.participants[1].name,
        kickoff_at=kickoff_off,
    )
    assert res is None


@pytest.mark.asyncio
async def test_catalog_find_by_fixture_returns_none_for_unknown_teams():
    cat = _make_catalog_with_cache()
    foot = [e for e in cat._events_cache if e.sport_id == "FOOT" and len(e.participants) >= 2]
    ev = foot[0]
    res = await cat.find_event_by_fixture(
        fixture_id=99999,
        team_home="Time Inexistente FC",
        team_away="Outro Inexistente AC",
        kickoff_at=ev.start_time,
    )
    assert res is None


@pytest.mark.asyncio
async def test_catalog_fixture_map_caches_result():
    cat = _make_catalog_with_cache()
    foot = [e for e in cat._events_cache if e.sport_id == "FOOT" and len(e.participants) >= 2]
    ev = foot[0]
    cat.prime_fixture_map(fixture_id=777, event_id=ev.event_id)
    res = await cat.find_event_by_fixture(
        fixture_id=777,
        team_home="qualquer",
        team_away="coisa",
        kickoff_at=ev.start_time,
    )
    assert res == ev.event_id
    assert cat.fixture_map_snapshot()[777] == ev.event_id


# ============================================================
# BetanoWSClient — extração de eventId do diff
# ============================================================

def test_ws_extract_event_id_from_diff_finds_id():
    import base64
    payload = base64.b64encode(b'whatever..."eventId":12345678,...').decode()
    eid = BetanoWSClient._extract_event_id_from_diff(payload)
    assert eid == 12345678


def test_ws_extract_event_id_from_diff_returns_none_on_garbage():
    assert BetanoWSClient._extract_event_id_from_diff("não-é-base64-real$$$") is None
