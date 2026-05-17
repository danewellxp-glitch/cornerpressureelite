"""CompositeLineupsProvider K.1 B.7 — enrichment coach + missing_players."""
from __future__ import annotations

from datetime import date
from typing import Optional

import pytest

from data.lineups_provider import (
    CanonicalLineup,
    CompositeLineupsProvider,
    MissingPlayer,
    PlayerEntry,
)


class _FakeProvider:
    def __init__(self, name="x", lineups=None, raises=False):
        self.name = name
        self._lineups = lineups
        self._raises = raises
        self.calls = 0

    async def get_lineups(self, fixture_id, *, betano_event_id=None, home_team_id=None):
        self.calls += 1
        if self._raises:
            raise RuntimeError("boom")
        return self._lineups

    async def healthcheck(self): return True


def _ln(
    *, source="bridge_betano", side="home", has_starters=True,
    coach=None, missing=None,
) -> CanonicalLineup:
    return CanonicalLineup(
        fixture_id=42, source=source, team_side=side,
        formation="4-3-3" if has_starters else None,
        coach_name=coach,
        starting_eleven=[PlayerEntry(name="A", player_id=1)] if has_starters else [],
        substitutes=[],
        missing_players=list(missing or []),
    )


def _mp(name="X", reason="injury") -> MissingPlayer:
    return MissingPlayer(
        player_id=1, name=name, reason=reason,
        reason_code=1, expected_return=date(2026, 12, 1),
        source="sofascore",
    )


@pytest.mark.asyncio
async def test_enrichment_fills_coach_when_betano_none():
    primary = _FakeProvider("bridge_betano", lineups=[
        _ln(side="home", coach=None),
        _ln(side="away", coach=None),
    ])
    enricher = _FakeProvider("sofascore", lineups=[
        _ln(source="sofascore", side="home", coach="Coach H"),
        _ln(source="sofascore", side="away", coach="Coach A"),
    ])
    comp = CompositeLineupsProvider([primary], enricher=enricher)
    out = await comp.get_lineups(42)
    assert out is not None and len(out) == 2
    assert out[0].coach_name == "Coach H"
    assert out[1].coach_name == "Coach A"
    # Source da lineup base permanece Betano (apenas campos foram enriquecidos)
    assert out[0].source == "bridge_betano"


@pytest.mark.asyncio
async def test_enrichment_fills_missing_players_when_betano_empty():
    primary = _FakeProvider("bridge_betano", lineups=[
        _ln(side="home", coach="Coach H", missing=[]),
        _ln(side="away", coach="Coach A", missing=[]),
    ])
    enricher = _FakeProvider("sofascore", lineups=[
        _ln(source="sofascore", side="home", coach="X", missing=[_mp("Hurt", "injury")]),
        _ln(source="sofascore", side="away", coach="Y", missing=[_mp("Susp", "suspension")]),
    ])
    comp = CompositeLineupsProvider([primary], enricher=enricher)
    out = await comp.get_lineups(42)
    assert out is not None
    assert len(out[0].missing_players) == 1
    assert out[0].missing_players[0].name == "Hurt"
    assert len(out[1].missing_players) == 1


@pytest.mark.asyncio
async def test_enrichment_does_not_overwrite_existing_coach():
    primary = _FakeProvider("bridge_betano", lineups=[
        _ln(side="home", coach="Real Coach"),
        _ln(side="away", coach=None),
    ])
    enricher = _FakeProvider("sofascore", lineups=[
        _ln(source="sofascore", side="home", coach="Wrong Coach"),
        _ln(source="sofascore", side="away", coach="Coach A"),
    ])
    comp = CompositeLineupsProvider([primary], enricher=enricher)
    out = await comp.get_lineups(42)
    assert out[0].coach_name == "Real Coach"  # NÃO sobrescreve
    assert out[1].coach_name == "Coach A"     # preenche o que faltava


@pytest.mark.asyncio
async def test_enrichment_skipped_when_no_gap():
    """Primary já tem coach + missing → não chama enricher."""
    primary = _FakeProvider("bridge_betano", lineups=[
        _ln(side="home", coach="H", missing=[_mp("X")]),
        _ln(side="away", coach="A", missing=[_mp("Y")]),
    ])
    enricher = _FakeProvider("sofascore", lineups=[])
    comp = CompositeLineupsProvider([primary], enricher=enricher)
    await comp.get_lineups(42)
    assert enricher.calls == 0


@pytest.mark.asyncio
async def test_enrichment_failure_silent_returns_primary():
    primary = _FakeProvider("bridge_betano", lineups=[
        _ln(side="home", coach=None),
        _ln(side="away", coach=None),
    ])
    enricher = _FakeProvider("sofascore", raises=True)
    comp = CompositeLineupsProvider([primary], enricher=enricher)
    out = await comp.get_lineups(42)
    assert out is not None
    assert all(ln.coach_name is None for ln in out)


@pytest.mark.asyncio
async def test_enrichment_disabled_skips_enricher():
    primary = _FakeProvider("bridge_betano", lineups=[
        _ln(side="home", coach=None),
        _ln(side="away", coach=None),
    ])
    enricher = _FakeProvider("sofascore", lineups=[
        _ln(source="sofascore", side="home", coach="X"),
    ])
    comp = CompositeLineupsProvider([primary], enricher=enricher, enable_enrichment=False)
    await comp.get_lineups(42)
    assert enricher.calls == 0


@pytest.mark.asyncio
async def test_enricher_not_called_when_enricher_is_primary():
    """Edge: enricher.name == primary.name → não chamar duplicado."""
    same = _FakeProvider("bridge_betano", lineups=[
        _ln(side="home", coach=None),
        _ln(side="away", coach=None),
    ])
    comp = CompositeLineupsProvider([same], enricher=same)
    await comp.get_lineups(42)
    assert same.calls == 1  # só uma chamada (não enricher round)
