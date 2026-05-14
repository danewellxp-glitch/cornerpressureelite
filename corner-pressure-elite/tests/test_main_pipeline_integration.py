"""Testes de integração do pipeline de odds em `main._analisar_jogo`.

Cobrem o roteamento USE_BETANO_BRIDGE on/off:
- flag off  -> api_client.get_live_odds_multi_bookmaker (multi-bookmaker legado)
- flag on   -> composite_odds.get_corners/get_cards (fonte única)

Estratégia: instancia `CornerPressureElite` via `object.__new__` (pula o
`__init__` pesado) e injeta colaboradores mockados. `parse_fixture_to_jogo`
e `enrich_jogo_with_cards` são monkeypatchados pra isolar o roteamento.
"""
from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

import main
from data.models import JogoAoVivo, Sinal
from data.odds_provider import CanonicalFixture, CanonicalOverUnder
from notifier.message_formatter import MessageFormatter


# ─── Helpers ────────────────────────────────────────────────────────

_FIXTURE = {
    "fixture": {"id": 12345},
    "league": {"id": 71},
    "teams": {"home": {"name": "A"}, "away": {"name": "B"}},
}


def _jogo(**over) -> JogoAoVivo:
    base = dict(
        id=12345, liga_id=71, liga_nome="Brasileirão",
        time_casa="Flamengo", time_fora="Palmeiras",
        placar_casa=1, placar_fora=0, minuto=60,
        escanteios_total=7, escanteios_casa=4, escanteios_fora=3,
    )
    base.update(over)
    return JogoAoVivo(**base)


def _make_sistema(monkeypatch, *, flag_on: bool, jogo: JogoAoVivo,
                  cards_active: bool = False) -> "main.CornerPressureElite":
    sistema = object.__new__(main.CornerPressureElite)

    sistema.api_client = MagicMock()
    sistema.api_client.get_statistics = AsyncMock(return_value=[])
    sistema.api_client.get_live_odds_multi_bookmaker = AsyncMock(return_value={})
    sistema.api_client.get_live_odds = AsyncMock(return_value={})
    sistema.api_client.get_live_odds_cards = AsyncMock(return_value={})

    sistema.composite_odds = MagicMock()
    sistema.composite_odds.get_corners = AsyncMock(return_value=None)
    sistema.composite_odds.get_cards = AsyncMock(return_value=None)

    sistema.decision_engine = MagicMock()
    sistema.decision_engine.pre_avaliar.return_value = 5
    sistema.decision_engine.avaliar.return_value = None

    sistema.cards_decision_engine = MagicMock()
    sistema.cards_decision_engine.avaliar.return_value = None

    sistema.database = MagicMock()
    sistema.database.salvar_snapshot = AsyncMock()
    sistema.database.list_users_for_broadcast = AsyncMock(return_value=[])

    sistema.state_manager = MagicMock()
    sistema.cards_state_manager = MagicMock()
    sistema.cards_state_manager.ja_alertou.return_value = True
    sistema.cards_state_manager.deve_reavaliar.return_value = False
    sistema.notifier = MagicMock()

    monkeypatch.setattr(main, "USE_BETANO_BRIDGE", flag_on)
    monkeypatch.setattr(main, "ANALISE_CARTOES_ATIVA", cards_active)
    monkeypatch.setattr(main, "parse_fixture_to_jogo", lambda *a, **k: jogo)
    monkeypatch.setattr(main, "enrich_jogo_with_cards", lambda *a, **k: None)
    return sistema


def _canonical(source: str, market_kind: str = "corners", **over) -> CanonicalOverUnder:
    base = dict(
        source=source, market_kind=market_kind, market_code="",
        linha=9.5, odd_over=1.85, odd_under=1.95,
    )
    base.update(over)
    return CanonicalOverUnder(**base)


# ─── Roteamento de odds (corners) ───────────────────────────────────

@pytest.mark.asyncio
async def test_pipeline_uses_api_client_when_flag_off(monkeypatch):
    jogo = _jogo()
    sistema = _make_sistema(monkeypatch, flag_on=False, jogo=jogo)
    sistema.api_client.get_live_odds_multi_bookmaker = AsyncMock(return_value={
        "linha": 9.5, "betano": 1.85, "bet365": 1.90,
        "bookmaker_usado": "betano", "linha_betano": 9.5, "linha_bet365": 9.5,
    })

    await sistema._analisar_jogo(_FIXTURE)

    sistema.api_client.get_live_odds_multi_bookmaker.assert_awaited_once()
    sistema.composite_odds.get_corners.assert_not_awaited()
    assert jogo.odd_betano == 1.85
    assert jogo.odd_bet365 == 1.90
    assert jogo.linha_atual == 9.5
    assert jogo.odds_source is None


@pytest.mark.asyncio
async def test_pipeline_uses_composite_when_flag_on(monkeypatch):
    jogo = _jogo()
    sistema = _make_sistema(monkeypatch, flag_on=True, jogo=jogo)
    sistema.composite_odds.get_corners = AsyncMock(
        return_value=_canonical("betano_bridge", linha=9.5, odd_over=1.85)
    )

    await sistema._analisar_jogo(_FIXTURE)

    sistema.composite_odds.get_corners.assert_awaited_once()
    sistema.api_client.get_live_odds_multi_bookmaker.assert_not_awaited()
    assert jogo.linha_atual == 9.5
    assert jogo.odd_atual == 1.85
    assert jogo.odds_source == "betano_bridge"
    assert jogo.bookmaker_usado == "betano_bridge"
    # Campos legados ficam no default 0.0 (não setados como None).
    assert jogo.odd_betano == 0.0
    assert jogo.odd_bet365 == 0.0


@pytest.mark.asyncio
async def test_pipeline_falls_back_to_apifootball_via_composite(monkeypatch):
    jogo = _jogo()
    sistema = _make_sistema(monkeypatch, flag_on=True, jogo=jogo)
    # Composite faz a cascata internamente: bridge falhou, AF respondeu.
    sistema.composite_odds.get_corners = AsyncMock(
        return_value=_canonical("apifootball", linha=10.5, odd_over=1.72)
    )

    await sistema._analisar_jogo(_FIXTURE)

    assert jogo.odds_source == "apifootball"
    assert jogo.linha_atual == 10.5
    assert jogo.odd_atual == 1.72


@pytest.mark.asyncio
async def test_pipeline_handles_composite_none_gracefully(monkeypatch):
    jogo = _jogo()
    sistema = _make_sistema(monkeypatch, flag_on=True, jogo=jogo)
    sistema.composite_odds.get_corners = AsyncMock(return_value=None)

    resultado = await sistema._analisar_jogo(_FIXTURE)

    # Não crasha; jogo segue sem odds; engine não emite sinal.
    assert resultado is jogo
    assert jogo.odds_source is None
    assert jogo.odd_atual == 0.0
    assert jogo.linha_atual == 0.0


@pytest.mark.asyncio
async def test_cards_uses_composite_when_flag_on(monkeypatch):
    jogo = _jogo(linha_cartoes=0.0, odd_cartoes=0.0)
    sistema = _make_sistema(monkeypatch, flag_on=True, jogo=jogo, cards_active=True)
    sistema.cards_decision_engine.avaliar.return_value = MagicMock()  # sinal truthy
    sistema.composite_odds.get_cards = AsyncMock(
        return_value=_canonical("betano_bridge", market_kind="cards",
                                linha=4.5, odd_over=1.60, odd_under=2.30)
    )

    await sistema._analisar_jogo(_FIXTURE)

    sistema.composite_odds.get_cards.assert_awaited_once()
    sistema.api_client.get_live_odds_cards.assert_not_awaited()
    assert jogo.linha_cartoes == 4.5
    assert jogo.odd_cartoes == 1.60
    assert jogo.odds_source_cartoes == "betano_bridge"


# ─── Formatters ─────────────────────────────────────────────────────

def test_message_formatter_single_source_when_bridge():
    jogo = _jogo(linha_atual=9.5, odd_atual=1.85, odds_source="betano_bridge",
                 bookmaker_usado="betano_bridge")
    sinal = Sinal(tipo="NORMAL", jogo=jogo, pressure_score=7,
                  projecao=11.2, edge=1.7)

    msg = MessageFormatter.format_signal(sinal)

    assert "Betano: 1.85x" in msg
    assert "Bet365" not in msg
    assert "(Betano)" in msg


def test_message_formatter_multi_bookmaker_when_legacy():
    jogo = _jogo(linha_atual=9.5, odd_atual=1.90, odd_betano=1.85,
                 odd_bet365=1.90, bookmaker_usado="betano", odds_source=None)
    sinal = Sinal(tipo="PREMIUM", jogo=jogo, pressure_score=9,
                  projecao=12.0, edge=2.1)

    msg = MessageFormatter.format_signal(sinal)

    assert "Betano: 1.85x" in msg
    assert "Bet365: 1.90x" in msg


# ─── _build_canonical_fixture ───────────────────────────────────────

def test_canonical_fixture_built_from_jogo():
    kickoff = datetime(2026, 5, 14, 21, 0, tzinfo=timezone.utc)
    jogo = _jogo(kickoff_at=kickoff, placar_casa=2, placar_fora=1)
    sistema = object.__new__(main.CornerPressureElite)

    cf = sistema._build_canonical_fixture(jogo)

    assert isinstance(cf, CanonicalFixture)
    assert cf.fixture_id == 12345
    assert cf.home_team == "Flamengo"
    assert cf.away_team == "Palmeiras"
    assert cf.league_id == 71
    assert cf.starts_at_utc == kickoff
    assert cf.score_home == 2
    assert cf.score_away == 1

    # kickoff_at=None -> fallback datetime (não crasha, campo não é consumido).
    jogo_sem_kickoff = _jogo(kickoff_at=None)
    cf2 = sistema._build_canonical_fixture(jogo_sem_kickoff)
    assert isinstance(cf2.starts_at_utc, datetime)
