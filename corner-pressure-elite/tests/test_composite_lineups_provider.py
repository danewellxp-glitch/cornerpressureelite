"""Unit tests do CompositeLineupsProvider (Fase G.1 PARTE D)."""
from __future__ import annotations

import logging
from typing import Optional

import pytest

from data.lineups_provider import (
    BETANO_GAPS_LINEUPS,
    CanonicalLineup,
    CompositeLineupsProvider,
    PlayerEntry,
)


class _FakeProvider:
    def __init__(
        self,
        name: str,
        result: Optional[list[CanonicalLineup]] = None,
        raises: bool = False,
    ):
        self.name = name
        self._result = result
        self._raises = raises
        self.calls: list[tuple] = []

    async def get_lineups(
        self,
        fixture_id: int,
        *,
        betano_event_id=None,
        home_team_id=None,
    ):
        self.calls.append((fixture_id, betano_event_id, home_team_id))
        if self._raises:
            raise RuntimeError(f"{self.name} simulated")
        return self._result

    async def healthcheck(self) -> bool:
        return not self._raises


def _lineup(
    *, source: str, team_side: str, has_starters: bool = True,
    coach_name: Optional[str] = None,
) -> CanonicalLineup:
    return CanonicalLineup(
        fixture_id=999,
        source=source,
        team_side=team_side,
        formation="4-3-3" if has_starters else None,
        coach_name=coach_name,
        starting_eleven=(
            [PlayerEntry(name="X", player_id=1)] if has_starters else []
        ),
    )


@pytest.mark.asyncio
async def test_prefers_betano_when_starting_eleven_present():
    """Betano com starting_eleven em ambos lados → usa Betano, ignora AF."""
    betano = _FakeProvider("bridge_betano", result=[
        _lineup(source="bridge_betano", team_side="home"),
        _lineup(source="bridge_betano", team_side="away"),
    ])
    af = _FakeProvider("apifootball", result=[
        _lineup(source="apifootball", team_side="home", coach_name="X"),
        _lineup(source="apifootball", team_side="away", coach_name="Y"),
    ])
    composite = CompositeLineupsProvider([betano, af])

    out = await composite.get_lineups(999)
    assert out is not None and len(out) == 2
    assert all(ln.source == "bridge_betano" for ln in out)
    assert af.calls == []


@pytest.mark.asyncio
async def test_falls_back_to_af_when_zero_coverage(caplog):
    """Betano sem starting_eleven em nenhum lado (cobertura zero) → cai pra AF.
    Log INFO `composite_lineups.zero_coverage`."""
    betano = _FakeProvider("bridge_betano", result=[
        _lineup(source="bridge_betano", team_side="home", has_starters=False),
        _lineup(source="bridge_betano", team_side="away", has_starters=False),
    ])
    af = _FakeProvider("apifootball", result=[
        _lineup(source="apifootball", team_side="home", coach_name="A"),
        _lineup(source="apifootball", team_side="away", coach_name="B"),
    ])
    composite = CompositeLineupsProvider([betano, af])

    with caplog.at_level(logging.INFO, logger="cpes.providers.lineups"):
        out = await composite.get_lineups(999)
    assert out is not None
    assert all(ln.source == "apifootball" for ln in out)
    assert any("zero_coverage" in r.message for r in caplog.records)


@pytest.mark.asyncio
async def test_accepts_partial_coverage_warns(caplog):
    """AJUSTE 4b: Betano com home_ok mas away vazio → aceita resultado (não cai
    pra fallback) MAS loga WARNING `lineups.partial_coverage`."""
    betano = _FakeProvider("bridge_betano", result=[
        _lineup(source="bridge_betano", team_side="home", has_starters=True),
        _lineup(source="bridge_betano", team_side="away", has_starters=False),
    ])
    af = _FakeProvider("apifootball", result=[])
    composite = CompositeLineupsProvider([betano, af])

    with caplog.at_level(logging.WARNING, logger="cpes.providers.lineups"):
        out = await composite.get_lineups(999)
    assert out is not None and len(out) == 2
    assert all(ln.source == "bridge_betano" for ln in out)
    assert af.calls == []  # parcial OK, NÃO fallback
    assert any("partial_coverage" in r.message
               and "home_ok=True" in r.message
               and "away_ok=False" in r.message
               for r in caplog.records)


@pytest.mark.asyncio
async def test_accepts_betano_parcial_with_missing_coach():
    """AJUSTE 4c: Betano com starting_eleven mas coach_name=None (gap) → ACEITA.
    Coach é gap conhecido (BETANO_GAPS_LINEUPS), não aciona fallback."""
    assert "coach_name" in BETANO_GAPS_LINEUPS
    betano = _FakeProvider("bridge_betano", result=[
        _lineup(source="bridge_betano", team_side="home", coach_name=None),
        _lineup(source="bridge_betano", team_side="away", coach_name=None),
    ])
    af = _FakeProvider("apifootball", result=[])
    composite = CompositeLineupsProvider([betano, af])

    out = await composite.get_lineups(999)
    assert out is not None
    assert all(ln.coach_name is None for ln in out)
    assert af.calls == []  # coach gap NÃO aciona fallback


@pytest.mark.asyncio
async def test_provider_none_triggers_fallback():
    """Primary devolve None → fallback chamado."""
    betano = _FakeProvider("bridge_betano", result=None)
    af = _FakeProvider("apifootball", result=[
        _lineup(source="apifootball", team_side="home"),
        _lineup(source="apifootball", team_side="away"),
    ])
    composite = CompositeLineupsProvider([betano, af])

    out = await composite.get_lineups(999)
    assert out is not None and out[0].source == "apifootball"


@pytest.mark.asyncio
async def test_provider_raises_triggers_fallback(caplog):
    """Exceção em primary → log warning + fallback chamado."""
    betano = _FakeProvider("bridge_betano", raises=True)
    af = _FakeProvider("apifootball", result=[
        _lineup(source="apifootball", team_side="home"),
        _lineup(source="apifootball", team_side="away"),
    ])
    composite = CompositeLineupsProvider([betano, af])

    with caplog.at_level(logging.WARNING, logger="cpes.providers.lineups"):
        out = await composite.get_lineups(999)
    assert out is not None and out[0].source == "apifootball"
    assert any("bridge_betano.error" in r.message for r in caplog.records)


@pytest.mark.asyncio
async def test_returns_none_when_all_fail():
    betano = _FakeProvider("bridge_betano", result=None)
    af = _FakeProvider("apifootball", result=None)
    composite = CompositeLineupsProvider([betano, af])
    out = await composite.get_lineups(999)
    assert out is None


@pytest.mark.asyncio
async def test_passes_hints_to_providers():
    """Composite repassa betano_event_id + home_team_id pros providers."""
    betano = _FakeProvider("bridge_betano", result=[
        _lineup(source="bridge_betano", team_side="home"),
        _lineup(source="bridge_betano", team_side="away"),
    ])
    composite = CompositeLineupsProvider([betano])
    await composite.get_lineups(999, betano_event_id=12345, home_team_id=33)
    assert betano.calls == [(999, 12345, 33)]


def test_init_requires_at_least_one_provider():
    with pytest.raises(ValueError):
        CompositeLineupsProvider([])
