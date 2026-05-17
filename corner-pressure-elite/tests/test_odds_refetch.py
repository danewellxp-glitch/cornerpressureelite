"""Tests do refetch just-before-send (Fase K, 2026-05-17)."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

import pytest

from data.odds_provider import CanonicalFixture, CanonicalOverUnder
from engine.odds_refetch import refetch_validate_corners, refetch_validate_cards


@dataclass
class _FakeJogo:
    linha_atual: float = 9.5
    odd_atual: float = 1.42
    linha_cartoes: float = 3.5
    odd_cartoes: float = 1.70


def _fixture(fid: int = 100) -> CanonicalFixture:
    return CanonicalFixture(
        fixture_id=fid, home_team="A", away_team="B",
        league_id=140, starts_at_utc=datetime.now(timezone.utc),
    )


def _odds(linha: float = 9.5, odd_over: float = 1.42, is_stale: bool = False, age: int = 0):
    return CanonicalOverUnder(
        source="betano_bridge", market_kind="corners", market_code="CNOU",
        linha=linha, odd_over=odd_over, odd_under=2.0,
        is_stale=is_stale, age_seconds=age,
    )


class _FakeComposite:
    def __init__(self, fresh_corners=None, fresh_cards=None, raises: Optional[Exception] = None):
        self._corners = fresh_corners
        self._cards = fresh_cards
        self._raises = raises

    async def get_corners(self, fixture, current_score, line=None):
        if self._raises:
            raise self._raises
        return self._corners

    async def get_cards(self, fixture, current_score, line=None):
        if self._raises:
            raise self._raises
        return self._cards


@pytest.mark.asyncio
async def test_corners_emit_ok_when_odds_unchanged():
    c = _FakeComposite(fresh_corners=_odds(9.5, 1.42))
    j = _FakeJogo()
    ok = await refetch_validate_corners(c, _fixture(), 0, j)
    assert ok is True
    assert j.odd_atual == 1.42  # mantém


@pytest.mark.asyncio
async def test_corners_emit_ok_with_minor_drift_updates_odd():
    """Drift 7% (dentro de 15%) — emit + atualiza odd com valor fresh."""
    c = _FakeComposite(fresh_corners=_odds(9.5, 1.52))  # +7%
    j = _FakeJogo(odd_atual=1.42)
    ok = await refetch_validate_corners(c, _fixture(), 0, j)
    assert ok is True
    assert j.odd_atual == 1.52  # atualizado pra fresh


@pytest.mark.asyncio
async def test_corners_blocked_when_odd_drifted_too_much():
    """Drift 18% (>15%) — abort."""
    c = _FakeComposite(fresh_corners=_odds(9.5, 1.68))  # +18%
    j = _FakeJogo(odd_atual=1.42)
    ok = await refetch_validate_corners(c, _fixture(), 0, j)
    assert ok is False
    assert j.odd_atual == 1.42  # NÃO atualizou (abortou)


@pytest.mark.asyncio
async def test_corners_blocked_when_line_changed():
    """Linha 9.5 → 10.5 — mercado fechou, abort."""
    c = _FakeComposite(fresh_corners=_odds(10.5, 1.42))
    j = _FakeJogo(linha_atual=9.5)
    ok = await refetch_validate_corners(c, _fixture(), 0, j)
    assert ok is False


@pytest.mark.asyncio
async def test_corners_blocked_when_refetch_returns_none():
    c = _FakeComposite(fresh_corners=None)
    j = _FakeJogo()
    ok = await refetch_validate_corners(c, _fixture(), 0, j)
    assert ok is False


@pytest.mark.asyncio
async def test_corners_blocked_when_refetch_stale():
    c = _FakeComposite(fresh_corners=_odds(9.5, 1.42, is_stale=True, age=35))
    j = _FakeJogo()
    ok = await refetch_validate_corners(c, _fixture(), 0, j)
    assert ok is False


@pytest.mark.asyncio
async def test_corners_blocked_when_composite_raises():
    c = _FakeComposite(raises=RuntimeError("bridge fail"))
    j = _FakeJogo()
    ok = await refetch_validate_corners(c, _fixture(), 0, j)
    assert ok is False


@pytest.mark.asyncio
async def test_corners_emit_ok_when_orig_odd_zero():
    """Sinal com odd=0 (degradado) — refetch fornece valor."""
    c = _FakeComposite(fresh_corners=_odds(9.5, 1.42))
    j = _FakeJogo(odd_atual=0.0)
    ok = await refetch_validate_corners(c, _fixture(), 0, j)
    assert ok is True
    assert j.odd_atual == 1.42  # populado


@pytest.mark.asyncio
async def test_cards_path_independent():
    """Refetch cards usa get_cards, atualiza odd_cartoes."""
    fresh = CanonicalOverUnder(
        source="betano_bridge", market_kind="cards", market_code="TCOU",
        linha=3.5, odd_over=1.75, odd_under=2.0,
    )
    c = _FakeComposite(fresh_cards=fresh)
    j = _FakeJogo(linha_cartoes=3.5, odd_cartoes=1.70)
    ok = await refetch_validate_cards(c, _fixture(), 0, j)
    assert ok is True
    assert j.odd_cartoes == 1.75  # atualizado


@pytest.mark.asyncio
async def test_custom_max_drift_pct():
    """Tolerância configurável: drift 18% passa se max=0.20."""
    c = _FakeComposite(fresh_corners=_odds(9.5, 1.68))  # +18%
    j = _FakeJogo(odd_atual=1.42)
    ok = await refetch_validate_corners(c, _fixture(), 0, j, max_drift_pct=0.20)
    assert ok is True
    assert j.odd_atual == 1.68
