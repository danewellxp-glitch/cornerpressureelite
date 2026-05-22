"""Tests da comparação de cobertura discovery SofaScore vs AF (A2 shadow)."""
from __future__ import annotations

from data.providers.sofascore.discovery import (
    CoverageReport,
    SofaFixture,
    compare_coverage,
)


def _sofa(eid: int, lid: int, home: str, away: str) -> SofaFixture:
    return SofaFixture(
        sofa_event_id=eid,
        af_league_id=lid,
        home_team=home,
        away_team=away,
        kickoff_utc=None,
        status_type="notstarted",
    )


def test_exact_match_full_coverage():
    af = [(39, "Arsenal", "Chelsea"), (39, "Liverpool", "Everton")]
    sofa = [_sofa(1, 39, "Arsenal", "Chelsea"), _sofa(2, 39, "Liverpool", "Everton")]
    r = compare_coverage(af, sofa)
    assert isinstance(r, CoverageReport)
    assert r.matched == 2
    assert r.af_only == []
    assert r.sofa_only == []
    assert r.af_match_pct == 100.0


def test_fuzzy_match_minor_name_diff():
    # "Real Madrid" vs "Real Madrid CF" ~ 88 (>= 85).
    af = [(140, "Real Madrid", "Barcelona")]
    sofa = [_sofa(10, 140, "Real Madrid CF", "Barcelona")]
    r = compare_coverage(af, sofa)
    assert r.matched == 1
    assert r.af_only == []


def test_af_only_when_sofa_missing_fixture():
    af = [(39, "Arsenal", "Chelsea"), (39, "Brentford", "Fulham")]
    sofa = [_sofa(1, 39, "Arsenal", "Chelsea")]
    r = compare_coverage(af, sofa)
    assert r.matched == 1
    assert r.af_only == [(39, "Brentford", "Fulham")]
    assert r.sofa_only == []


def test_sofa_only_when_af_missing_fixture():
    af = [(39, "Arsenal", "Chelsea")]
    sofa = [_sofa(1, 39, "Arsenal", "Chelsea"), _sofa(2, 39, "Brentford", "Fulham")]
    r = compare_coverage(af, sofa)
    assert r.matched == 1
    assert r.af_only == []
    assert [sf.sofa_event_id for sf in r.sofa_only] == [2]


def test_no_cross_league_match():
    # Mesmos nomes, ligas diferentes -> NÃO casa (mata FP cross-competição).
    af = [(39, "Racing", "Boca")]
    sofa = [_sofa(1, 128, "Racing", "Boca")]
    r = compare_coverage(af, sofa)
    assert r.matched == 0
    assert r.af_only == [(39, "Racing", "Boca")]
    assert [sf.sofa_event_id for sf in r.sofa_only] == [1]


def test_one_sofa_consumed_only_once():
    # Dois AF iguais, um Sofa -> só um casa; o outro vira af_only.
    af = [(39, "Arsenal", "Chelsea"), (39, "Arsenal", "Chelsea")]
    sofa = [_sofa(1, 39, "Arsenal", "Chelsea")]
    r = compare_coverage(af, sofa)
    assert r.matched == 1
    assert r.af_only == [(39, "Arsenal", "Chelsea")]
    assert r.sofa_only == []


def test_empty_af_all_sofa_only():
    sofa = [_sofa(1, 39, "Arsenal", "Chelsea")]
    r = compare_coverage([], sofa)
    assert r.af_total == 0
    assert r.matched == 0
    assert r.af_match_pct == 0.0
    assert [sf.sofa_event_id for sf in r.sofa_only] == [1]


def test_below_threshold_does_not_match():
    af = [(39, "Arsenal", "Chelsea")]
    sofa = [_sofa(1, 39, "Tottenham Hotspur", "Newcastle United")]
    r = compare_coverage(af, sofa)
    assert r.matched == 0
    assert r.af_only == [(39, "Arsenal", "Chelsea")]
