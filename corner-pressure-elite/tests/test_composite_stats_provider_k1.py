"""CompositeStatsProvider K.1 — fallback intermediário + enrichment (B.7)."""
from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
from typing import Optional

import pytest

from data.odds_provider import CanonicalFixture
from data.stats_provider import (
    BETANO_GAPS_STATS,
    CanonicalStats,
    CompositeStatsProvider,
    _is_betano_gap_field,
    _merge_enrichment,
)


class _FakeProvider:
    def __init__(self, name="x", stats=None, raises=False):
        self.name = name
        self._stats = stats
        self._raises = raises
        self.calls = 0

    async def get_stats(self, fixture):
        self.calls += 1
        if self._raises:
            raise RuntimeError("boom")
        return self._stats

    async def healthcheck(self): return True


def _fix() -> CanonicalFixture:
    return CanonicalFixture(
        fixture_id=42, home_team="A", away_team="B", league_id=325,
        starts_at_utc=datetime.now(timezone.utc),
        score_home=1, score_away=0,
    )


def _stats(source="bridge_betano", **kw) -> CanonicalStats:
    base = dict(
        fixture_id=42, source=source, minute=70,
        score_home=1, score_away=0,
        corners_home=8, corners_away=4,
        yellow_cards_home=2, yellow_cards_away=1,
        red_cards_home=0, red_cards_away=0,
        shots_on_target_home=0, shots_on_target_away=0,  # gap Betano
        dangerous_attacks_home=33, dangerous_attacks_away=10,
        possession_home=58, possession_away=42,
        x_goals_home=1.2, x_goals_away=0.4,
    )
    base.update(kw)
    return CanonicalStats(**base)


def test_betano_gap_field_shots_on_target():
    """shots_on_target==0 + source=bridge_betano → gap detectado."""
    assert _is_betano_gap_field("shots_on_target_home", _stats()) is True
    s2 = _stats(source="apifootball")
    assert _is_betano_gap_field("shots_on_target_home", s2) is False
    s3 = _stats(shots_on_target_home=5)
    assert _is_betano_gap_field("shots_on_target_home", s3) is False


def test_betano_gap_field_optional_via_is_none():
    """Demais campos: gap se is None."""
    assert _is_betano_gap_field("big_chances_home", _stats()) is True
    s2 = _stats(big_chances_home=3)
    assert _is_betano_gap_field("big_chances_home", s2) is False


def test_merge_enrichment_fills_gaps():
    primary = _stats(source="bridge_betano")  # shots_on_target=0 gap
    enricher = _stats(
        source="sofascore",
        shots_on_target_home=5, shots_on_target_away=3,
        big_chances_home=2, big_chances_away=1,
    )
    merged = _merge_enrichment(primary, enricher, "sofascore")
    assert merged.shots_on_target_home == 5
    assert merged.shots_on_target_away == 3
    assert merged.big_chances_home == 2
    assert merged.enriched_by == ["sofascore"]


def test_merge_enrichment_does_not_overwrite_non_gap():
    primary = _stats(source="bridge_betano", shots_on_target_home=7)
    enricher = _stats(source="sofascore", shots_on_target_home=99)
    merged = _merge_enrichment(primary, enricher, "sofascore")
    assert merged.shots_on_target_home == 7  # primary preservado


def test_merge_enrichment_no_change_returns_same_object():
    primary = _stats(source="bridge_betano", shots_on_target_home=7,
                     shots_on_target_away=4,
                     big_chances_home=3, big_chances_away=1,
                     big_chances_missed_home=0, big_chances_missed_away=0,
                     shots_off_target_home=2, shots_off_target_away=1,
                     blocked_shots_home=1, blocked_shots_away=0,
                     stats_1h={}, stats_2h={})
    # primary sem gap → enricher ignorado, retorna mesma instância
    enricher = _stats(source="sofascore", shots_on_target_home=99)
    merged = _merge_enrichment(primary, enricher, "sofascore")
    assert merged is primary


@pytest.mark.asyncio
async def test_k1_cascade_primary_success_with_enrichment():
    primary = _FakeProvider("primary", stats=_stats(source="bridge_betano"))
    enricher = _FakeProvider("sofascore", stats=_stats(
        source="sofascore", shots_on_target_home=4, big_chances_home=2
    ))
    final = _FakeProvider("af", stats=None)
    comp = CompositeStatsProvider(
        primary=primary, fallback_intermediate=enricher, fallback_final=final,
    )
    out = await comp.get_stats(_fix())
    assert out is not None
    assert out.source == "bridge_betano"
    assert out.shots_on_target_home == 4  # enriched
    assert out.enriched_by == ["sofascore"]
    assert primary.calls == 1
    assert enricher.calls == 1
    assert final.calls == 0


@pytest.mark.asyncio
async def test_k1_cascade_primary_fail_uses_intermediate():
    primary = _FakeProvider("primary", stats=None)
    enricher = _FakeProvider("sofascore", stats=_stats(source="sofascore"))
    final = _FakeProvider("af", stats=None)
    comp = CompositeStatsProvider(
        primary=primary, fallback_intermediate=enricher, fallback_final=final,
    )
    out = await comp.get_stats(_fix())
    assert out is not None and out.source == "sofascore"
    assert enricher.calls == 1
    assert final.calls == 0


@pytest.mark.asyncio
async def test_k1_cascade_falls_to_final_when_both_above_fail():
    primary = _FakeProvider("primary", stats=None)
    enricher = _FakeProvider("sofascore", stats=None)
    final = _FakeProvider("af", stats=_stats(source="apifootball"))
    comp = CompositeStatsProvider(
        primary=primary, fallback_intermediate=enricher, fallback_final=final,
    )
    out = await comp.get_stats(_fix())
    assert out is not None and out.source == "apifootball"
    assert final.calls == 1


@pytest.mark.asyncio
async def test_k1_enrichment_disabled_skips_intermediate_when_primary_ok():
    primary = _FakeProvider("primary", stats=_stats(source="bridge_betano"))
    enricher = _FakeProvider("sofascore", stats=_stats(source="sofascore"))
    comp = CompositeStatsProvider(
        primary=primary, fallback_intermediate=enricher,
        enable_enrichment=False,
    )
    out = await comp.get_stats(_fix())
    assert out is not None and out.source == "bridge_betano"
    assert enricher.calls == 0  # enrichment off → não bate sofa


@pytest.mark.asyncio
async def test_k1_enrichment_failure_returns_primary_pure():
    primary = _FakeProvider("primary", stats=_stats(source="bridge_betano"))
    enricher = _FakeProvider("sofascore", raises=True)
    comp = CompositeStatsProvider(
        primary=primary, fallback_intermediate=enricher,
    )
    out = await comp.get_stats(_fix())
    assert out is not None and out.source == "bridge_betano"
    assert out.enriched_by is None  # sem enrichment


@pytest.mark.asyncio
async def test_legacy_cascade_still_works():
    """CompositeStatsProvider(providers=[...]) modo antigo cascata pura."""
    primary = _FakeProvider("primary", stats=None)
    secondary = _FakeProvider("secondary", stats=_stats(source="apifootball"))
    comp = CompositeStatsProvider(providers=[primary, secondary])
    out = await comp.get_stats(_fix())
    assert out is not None and out.source == "apifootball"
