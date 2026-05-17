"""Unit tests do state_markets_parser (Fase E.1 PRIORIDADE 1).

Cobre extract_lines() pra corners + cards a partir do payload Danae
(/danae-webapi/api/live/events/<id>/latest, proxied via /event/<id>/state
do bridge).
"""
from __future__ import annotations

from data.providers.betano_bridge.state_markets_parser import (
    extract_lines,
    has_coverage,
)


def _wrap_bridge(payload: dict) -> dict:
    """Simula o wrapper {data: payload} do endpoint /event/<id>/state."""
    return {"event_id": 123, "version": 1, "from_cache": False, "data": payload}


def _market(market_id: int, type_code: str, name: str, handicap: float, sel_ids: list[int]) -> dict:
    return {
        "id": market_id,
        "type": type_code,
        "name": name,
        "handicap": handicap,
        "selectionIdList": sel_ids,
        "displayOrder": 100,
    }


def _selection(sel_id: int, price: float, name: str) -> dict:
    return {"id": sel_id, "price": price, "name": name, "fullName": name}


def test_extract_corners_cnou_returns_lines_sorted():
    payload = {
        "markets": {
            "1": _market(1, "CNOU", "Escanteios Mais/Menos", 7.5, [10, 11]),
            "2": _market(2, "CNOU", "Escanteios Mais/Menos", 5.5, [20, 21]),
            "3": _market(3, "CNOU", "Escanteios Mais/Menos", 6.5, [30, 31]),
        },
        "selections": {
            "10": _selection(10, 2.37, "Mais de 7.5"),
            "11": _selection(11, 1.56, "Menos de 7.5"),
            "20": _selection(20, 1.40, "Mais de 5.5"),
            "21": _selection(21, 2.85, "Menos de 5.5"),
            "30": _selection(30, 1.78, "Mais de 6.5"),
            "31": _selection(31, 1.93, "Menos de 6.5"),
        },
    }
    lines = extract_lines(payload, "corners")
    assert [l["line"] for l in lines] == [5.5, 6.5, 7.5]
    assert lines[1] == {"line": 6.5, "over_price": 1.78, "under_price": 1.93}


def test_extract_cards_tcou():
    payload = {
        "markets": {
            "1": _market(1, "TCOU", "Total de Cartões Mais/Menos", 4.5, [10, 11]),
            "2": _market(2, "TCOU", "Total de Cartões Mais/Menos", 3.5, [20, 21]),
        },
        "selections": {
            "10": _selection(10, 1.87, "Mais de 4.5"),
            "11": _selection(11, 1.87, "Menos de 4.5"),
            "20": _selection(20, 1.40, "Mais de 3.5"),
            "21": _selection(21, 2.82, "Menos de 3.5"),
        },
    }
    lines = extract_lines(payload, "cards")
    assert len(lines) == 2
    assert lines[0]["line"] == 3.5
    assert lines[0]["over_price"] == 1.40


def test_handles_swapped_selection_order():
    """Danae não garante ordem — se sel[0] é Menos, sel[1] é Mais."""
    payload = {
        "markets": {"1": _market(1, "CNOU", "Esc.", 6.5, [10, 11])},
        "selections": {
            "10": _selection(10, 1.93, "Menos de 6.5"),  # under primeiro
            "11": _selection(11, 1.78, "Mais de 6.5"),
        },
    }
    [line] = extract_lines(payload, "corners")
    assert line == {"line": 6.5, "over_price": 1.78, "under_price": 1.93}


def test_ignores_other_market_types():
    """Markets de gols (MROU, etc.) não devem aparecer em corners."""
    payload = {
        "markets": {
            "1": _market(1, "MROU", "Total Gols", 2.5, [10, 11]),
            "2": _market(2, "CNOU", "Escanteios", 6.5, [20, 21]),
        },
        "selections": {
            "10": _selection(10, 1.8, "Mais de 2.5"),
            "11": _selection(11, 2.0, "Menos de 2.5"),
            "20": _selection(20, 1.78, "Mais de 6.5"),
            "21": _selection(21, 1.93, "Menos de 6.5"),
        },
    }
    [line] = extract_lines(payload, "corners")
    assert line["line"] == 6.5


def test_handles_missing_markets_section():
    """Payload vazio ou sem markets → []."""
    assert extract_lines({}, "corners") == []
    assert extract_lines({"markets": {}}, "corners") == []
    assert extract_lines({"markets": None}, "corners") == []


def test_accepts_bridge_wrapper_and_raw_payload():
    """Aceita {data: {...}} (wrapper bridge) e {...} (Danae cru)."""
    inner = {
        "markets": {"1": _market(1, "CNOU", "Esc.", 6.5, [10, 11])},
        "selections": {
            "10": _selection(10, 1.78, "Mais de 6.5"),
            "11": _selection(11, 1.93, "Menos de 6.5"),
        },
    }
    assert extract_lines(inner, "corners") == extract_lines(_wrap_bridge(inner), "corners")


def test_dedup_by_handicap():
    """Mesma linha (handicap=6.5) com types diferentes (CNOU+COU1) — keep first."""
    payload = {
        "markets": {
            "1": _market(1, "CNOU", "Escanteios", 6.5, [10, 11]),
            "2": _market(2, "COU1", "Escanteios 1°T", 6.5, [20, 21]),
        },
        "selections": {
            "10": _selection(10, 1.78, "Mais de 6.5"),
            "11": _selection(11, 1.93, "Menos de 6.5"),
            "20": _selection(20, 1.50, "Mais de 6.5"),
            "21": _selection(21, 2.40, "Menos de 6.5"),
        },
    }
    lines = extract_lines(payload, "corners")
    assert len(lines) == 1


def test_skips_malformed_markets():
    """Markets com handicap None, selections ausentes, price inválido — silenciosamente pulados."""
    payload = {
        "markets": {
            "1": _market(1, "CNOU", "Esc.", None, [10, 11]),  # handicap None
            "2": _market(2, "CNOU", "Esc.", 6.5, [99, 100]),  # selections ausentes
            "3": _market(3, "CNOU", "Esc.", 7.5, [30, 31]),  # válido
            "4": _market(4, "CNOU", "Esc.", 8.5, [40]),       # só 1 selection
            "5": "not a dict",                                 # garbage
        },
        "selections": {
            "10": _selection(10, 1.78, "Mais"),
            "11": _selection(11, 1.93, "Menos"),
            "30": _selection(30, 2.37, "Mais de 7.5"),
            "31": _selection(31, 1.56, "Menos de 7.5"),
            "40": _selection(40, 1.0, "Mais"),
        },
    }
    lines = extract_lines(payload, "corners")
    assert len(lines) == 1
    assert lines[0]["line"] == 7.5


def test_has_coverage_helper():
    assert not has_coverage({}, "corners")
    payload_with = {
        "markets": {"1": _market(1, "CNOU", "Esc.", 6.5, [10, 11])},
        "selections": {
            "10": _selection(10, 1.78, "Mais de 6.5"),
            "11": _selection(11, 1.93, "Menos de 6.5"),
        },
    }
    assert has_coverage(payload_with, "corners")
    assert not has_coverage(payload_with, "cards")


def test_unknown_market_kind_returns_empty():
    payload = {
        "markets": {"1": _market(1, "CNOU", "Esc.", 6.5, [10, 11])},
        "selections": {
            "10": _selection(10, 1.78, "Mais de 6.5"),
            "11": _selection(11, 1.93, "Menos de 6.5"),
        },
    }
    assert extract_lines(payload, "goals") == []
    assert extract_lines(payload, "") == []
