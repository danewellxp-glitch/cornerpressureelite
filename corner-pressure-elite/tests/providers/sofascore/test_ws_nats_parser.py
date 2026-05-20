"""Tests do parser NATS do SofaScoreLiveFeed (Sprint N)."""
from __future__ import annotations

from data.providers.sofascore.ws_client import LiveDelta, parse_nats


def test_parse_single_msg():
    payload = '{"homeScore.current":2,"id":15832136}'
    buf = f"MSG sport.football 1 {len(payload)}\r\n{payload}\r\n"
    events, rest, ping = parse_nats(buf)
    assert rest == ""
    assert ping is False
    assert len(events) == 1
    d = events[0]
    assert isinstance(d, LiveDelta)
    assert d.subject == "sport.football"
    assert d.sofa_event_id == 15832136
    assert d.fields["homeScore.current"] == 2
    assert d.has_score_change is True


def test_parse_multiple_msgs_in_one_buffer():
    payload1 = '{"id":1,"homeScore.current":1}'
    payload2 = '{"id":2,"status.type":"finished","statusDescription":"FT"}'
    buf = (
        f"MSG sport.football 1 {len(payload1)}\r\n{payload1}\r\n"
        f"MSG sport.football 1 {len(payload2)}\r\n{payload2}\r\n"
    )
    events, rest, _ = parse_nats(buf)
    assert rest == ""
    assert [e.sofa_event_id for e in events] == [1, 2]
    assert events[1].is_finished is True


def test_parse_partial_frame_preserves_remainder():
    payload = '{"id":7,"cardsCode":"00"}'
    full = f"MSG event.7 2 {len(payload)}\r\n{payload}\r\n"
    # corta no meio do payload
    cut = len(full) - 6
    events, rest, _ = parse_nats(full[:cut])
    assert events == []           # frame incompleto -> nada emitido
    assert rest == full[:cut]     # buffer preservado
    # completa: junta o resto e re-parseia
    events2, rest2, _ = parse_nats(rest + full[cut:])
    assert rest2 == ""
    assert len(events2) == 1
    assert events2[0].has_card_change is True


def test_server_ping_flag():
    events, rest, ping = parse_nats("PING\r\n")
    assert ping is True
    assert events == []
    assert rest == ""


def test_info_and_pong_ignored():
    buf = 'INFO {"server_id":"x"}\r\nPONG\r\n'
    events, rest, ping = parse_nats(buf)
    assert events == []
    assert ping is False
    assert rest == ""


def test_invalid_json_payload_skipped():
    payload = "NOTJSON"
    buf = f"MSG sport.football 1 {len(payload)}\r\n{payload}\r\n"
    events, rest, _ = parse_nats(buf)
    assert events == []
    assert rest == ""


def test_finished_helper_false_for_score_only():
    payload = '{"homeScore.current":3,"id":99}'
    buf = f"MSG sport.football 1 {len(payload)}\r\n{payload}\r\n"
    events, _, _ = parse_nats(buf)
    assert events[0].is_finished is False
    assert events[0].has_card_change is False
