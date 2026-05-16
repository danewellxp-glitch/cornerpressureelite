"""Unit tests do StatsWindowCalculator (Fase E.1 PARTE E')."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from data.services.stats_window_calculator import StatsWindowCalculator


def _t(minutes: float) -> datetime:
    """Helper: timestamp UTC com offset em minutos a partir de uma base fixa."""
    base = datetime(2026, 5, 16, 20, 0, 0, tzinfo=timezone.utc)
    return base + timedelta(minutes=minutes)


def test_window_empty_history_returns_all_none():
    calc = StatsWindowCalculator(history_size=10)
    out = calc.compute_windows(fixture_id=999)
    assert out == {
        "corners_last_5min": None,
        "corners_last_10min": None,
        "yellow_last_5min": None,
        "yellow_last_10min": None,
    }


def test_window_only_one_snapshot_returns_all_none():
    """Com 1 snapshot só, sem base de comparação → None."""
    calc = StatsWindowCalculator(history_size=10)
    calc.add_snapshot(1, _t(0), corners_total=3, yellow_total=1)
    out = calc.compute_windows(fixture_id=1, now=_t(0))
    assert all(v is None for v in out.values())


def test_window_corners_decreased_returns_zero_not_negative():
    """Defesa contra reset/bug: delta negativo vira 0, nunca exposed."""
    calc = StatsWindowCalculator(history_size=10)
    calc.add_snapshot(1, _t(0), corners_total=5, yellow_total=2)
    calc.add_snapshot(1, _t(3), corners_total=3, yellow_total=1)  # decresceu
    out = calc.compute_windows(fixture_id=1, now=_t(3))
    assert out["corners_last_5min"] == 0
    assert out["yellow_last_5min"] == 0


def test_window_fixture_first_seen_mid_match_returns_none():
    """Fixture aparece pela 1ª vez já com valor alto → não há base 'antes' → None."""
    calc = StatsWindowCalculator(history_size=10)
    # Único snapshot tem corners=8, yellow=3 (jogo já vai pelo min 60+).
    calc.add_snapshot(1, _t(0), corners_total=8, yellow_total=3)
    out = calc.compute_windows(fixture_id=1, now=_t(0))
    assert out == {
        "corners_last_5min": None,
        "corners_last_10min": None,
        "yellow_last_5min": None,
        "yellow_last_10min": None,
    }


def test_window_explicit_reset_clears_state():
    calc = StatsWindowCalculator(history_size=10)
    calc.add_snapshot(1, _t(0), corners_total=3, yellow_total=1)
    calc.add_snapshot(1, _t(2), corners_total=5, yellow_total=2)
    out = calc.compute_windows(fixture_id=1, now=_t(2))
    assert out["corners_last_5min"] == 2  # delta válido
    calc.reset_fixture(1)
    out2 = calc.compute_windows(fixture_id=1, now=_t(3))
    assert all(v is None for v in out2.values())


def test_window_maxlen_eviction_affects_long_windows():
    """history_size=3 + 4 snapshots: o oldest evita → janela 10min usa só o que sobrou."""
    calc = StatsWindowCalculator(history_size=3)
    calc.add_snapshot(1, _t(0), corners_total=0, yellow_total=0)
    calc.add_snapshot(1, _t(2), corners_total=1, yellow_total=0)
    calc.add_snapshot(1, _t(7), corners_total=4, yellow_total=2)
    # Esse push evita o snapshot _t(0).
    calc.add_snapshot(1, _t(9), corners_total=6, yellow_total=3)

    out = calc.compute_windows(fixture_id=1, now=_t(9))
    # Janela 5min: base é o snapshot dentro da janela (_t(7) com corners=4),
    # delta = 6 - 4 = 2.
    assert out["corners_last_5min"] == 2
    # Janela 10min: base seria _t(0) com corners=0 (delta=6) mas foi evictada.
    # Snapshot fora da janela = nenhum (o oldest do deque é _t(2) e está dentro
    # de 10min de _t(9)). Logo usamos _t(2) como base inside_window. Delta=6-1=5.
    assert out["corners_last_10min"] == 5


def test_window_concurrent_fixtures_isolated():
    calc = StatsWindowCalculator(history_size=10)
    calc.add_snapshot(1, _t(0), corners_total=0, yellow_total=0)
    calc.add_snapshot(1, _t(3), corners_total=2, yellow_total=1)
    calc.add_snapshot(2, _t(0), corners_total=10, yellow_total=4)
    calc.add_snapshot(2, _t(4), corners_total=15, yellow_total=5)

    out1 = calc.compute_windows(fixture_id=1, now=_t(3))
    out2 = calc.compute_windows(fixture_id=2, now=_t(4))

    assert out1["corners_last_5min"] == 2  # 2-0
    assert out2["corners_last_5min"] == 5  # 15-10
    assert out1["yellow_last_5min"] == 1
    assert out2["yellow_last_5min"] == 1


def test_window_idempotent_same_captured_at_is_noop():
    """Push duplicado com mesmo captured_at = no-op."""
    calc = StatsWindowCalculator(history_size=10)
    calc.add_snapshot(1, _t(0), corners_total=0, yellow_total=0)
    calc.add_snapshot(1, _t(3), corners_total=2, yellow_total=1)
    calc.add_snapshot(1, _t(3), corners_total=99, yellow_total=99)  # dup ignorado
    out = calc.compute_windows(fixture_id=1, now=_t(3))
    assert out["corners_last_5min"] == 2  # usa o 1º _t(3), não o dup


def test_window_history_size_validation():
    with pytest.raises(ValueError):
        StatsWindowCalculator(history_size=1)


def test_window_naive_datetime_treated_as_utc():
    """Datetime naive → assumido UTC, sem TypeError."""
    calc = StatsWindowCalculator(history_size=10)
    naive = datetime(2026, 5, 16, 20, 0, 0)
    calc.add_snapshot(1, naive, corners_total=0, yellow_total=0)
    naive2 = datetime(2026, 5, 16, 20, 3, 0)
    calc.add_snapshot(1, naive2, corners_total=2, yellow_total=1)
    out = calc.compute_windows(fixture_id=1)
    assert out["corners_last_5min"] == 2


def test_window_bootstrap_from_history_populates_deque():
    """bootstrap_from_history hidrata deque pré-existente do stats_history."""
    calc = StatsWindowCalculator(history_size=10)
    # Mock rows como vêm do StatsHistoryRepo (DESC).
    rows = [
        {
            "captured_at": _t(5),
            "corners_home": 3, "corners_away": 1,
            "yellow_cards_home": 1, "yellow_cards_away": 1,
        },
        {
            "captured_at": _t(2),
            "corners_home": 1, "corners_away": 0,
            "yellow_cards_home": 0, "yellow_cards_away": 0,
        },
        {
            "captured_at": _t(0),
            "corners_home": 0, "corners_away": 0,
            "yellow_cards_home": 0, "yellow_cards_away": 0,
        },
    ]
    calc.bootstrap_from_history(fixture_id=1, rows=rows)
    out = calc.compute_windows(fixture_id=1, now=_t(5))
    # Snapshot mais recente: corners_total=4, yellow_total=2.
    # Janela 5min começa em _t(0). Snapshot _t(0) está dentro → delta=4-0=4.
    assert out["corners_last_5min"] == 4
    assert out["yellow_last_5min"] == 2
