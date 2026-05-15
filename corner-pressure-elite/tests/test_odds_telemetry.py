"""Testes da telemetria de odds full coverage (Fase D.0).

Cobrem:
- Janela técnica por mercado (minuto mínimo) em _capturar_odds_para_telemetria.
- Ciclo de captura por mercado (não captura todo ciclo do _main_loop).
- Contexto rico (minuto + scores) repassado ao Composite.
- enqueue_catalog enfileira uma entry por linha do catálogo.
- Falha de telemetria é fire-and-forget — não bloqueia o pipeline de sinal.

Estratégia: igual `test_main_pipeline_integration.py` — instancia
`CornerPressureElite` via `object.__new__` e injeta colaboradores mockados.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

import config
import main
from data.persistence.odds_worker import OddsPersistenceWorker

from .test_main_pipeline_integration import _FIXTURE, _jogo, _make_sistema


# ─── Helpers ────────────────────────────────────────────────────────


def _telemetry_sistema(*, pressure: int = 7, tension: int = 4) -> "main.CornerPressureElite":
    """Sistema mínimo pra exercitar _capturar_odds_para_telemetria isolado."""
    s = object.__new__(main.CornerPressureElite)

    s.composite_odds = MagicMock()
    s.composite_odds.get_corners = AsyncMock(return_value=None)
    s.composite_odds.get_cards = AsyncMock(return_value=None)
    # GOALS dormente: Composite real não expõe get_goals.
    del s.composite_odds.get_goals

    s.decision_engine = MagicMock()
    s.decision_engine.score_engine.calcular.return_value = pressure
    s.cards_decision_engine = MagicMock()
    s.cards_decision_engine.score_engine.calcular.return_value = tension

    s._last_capture_at = {}
    return s


class _Clock:
    """Relógio controlável pra substituir `main.time` nos testes de ciclo."""

    def __init__(self, start: float = 1_000_000.0):
        self.now = start

    def time(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


# ─── Janela técnica por mercado ─────────────────────────────────────


@pytest.mark.asyncio
async def test_telemetria_chama_composite_quando_minuto_acima_janela_corners(monkeypatch):
    monkeypatch.setattr(main, "USE_BETANO_BRIDGE", True)
    jogo = _jogo(minuto=20)
    sistema = _telemetry_sistema()

    await sistema._capturar_odds_para_telemetria(jogo)

    sistema.composite_odds.get_corners.assert_awaited_once()
    _, kwargs = sistema.composite_odds.get_corners.await_args
    assert kwargs["minute"] == 20
    assert kwargs["persist_telemetry"] is True


@pytest.mark.asyncio
async def test_telemetria_skip_quando_minuto_abaixo_janela_corners(monkeypatch):
    monkeypatch.setattr(main, "USE_BETANO_BRIDGE", True)
    # minuto 10 < ODDS_CAPTURE_MIN_MINUTE_CORNERS (15) -> corners não captura.
    jogo = _jogo(minuto=10)
    sistema = _telemetry_sistema()

    await sistema._capturar_odds_para_telemetria(jogo)

    sistema.composite_odds.get_corners.assert_not_awaited()


# ─── Ciclo de captura por mercado ───────────────────────────────────


@pytest.mark.asyncio
async def test_telemetria_respeita_ciclo_de_90s_corners(monkeypatch):
    monkeypatch.setattr(main, "USE_BETANO_BRIDGE", True)
    clock = _Clock()
    monkeypatch.setattr(main, "time", clock)
    sistema = _telemetry_sistema()

    # Captura 1: dispara e marca o timestamp.
    await sistema._capturar_odds_para_telemetria(_jogo(minuto=20))
    assert sistema.composite_odds.get_corners.await_count == 1

    # Captura 2: 30s depois (< 90s do ciclo) -> não dispara de novo.
    clock.advance(30)
    await sistema._capturar_odds_para_telemetria(_jogo(minuto=21))
    assert sistema.composite_odds.get_corners.await_count == 1

    # Captura 3: 120s do início (>= 90s) -> dispara de novo.
    clock.advance(90)
    await sistema._capturar_odds_para_telemetria(_jogo(minuto=22))
    assert sistema.composite_odds.get_corners.await_count == 2


# ─── Contexto rico ──────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_telemetria_envia_contexto_rico(monkeypatch):
    monkeypatch.setattr(main, "USE_BETANO_BRIDGE", True)
    jogo = _jogo(minuto=30)
    sistema = _telemetry_sistema(pressure=7, tension=4)

    await sistema._capturar_odds_para_telemetria(jogo)

    _, kwargs = sistema.composite_odds.get_corners.await_args
    assert kwargs["minute"] == 30
    assert kwargs["pressure_score"] == 7
    assert kwargs["tension_score"] == 4
    assert kwargs["persist_telemetry"] is True


# ─── enqueue_catalog ────────────────────────────────────────────────


def test_enqueue_catalog_insere_n_entries():
    worker = OddsPersistenceWorker(MagicMock())
    catalog_lines = [
        {"line": 5.5, "over_price": 1.19, "under_price": 4.15},
        {"line": 6.5, "over_price": 1.45, "under_price": 2.70},
        {"line": 7.5, "over_price": 1.85, "under_price": 1.95},
        {"line": 8.5, "over_price": 2.50, "under_price": 1.50},
        {"line": 9.5, "over_price": 3.40, "under_price": 1.30},
    ]

    worker.enqueue_catalog(
        fixture_id=999,
        source="betano_bridge",
        market_kind="corners",
        catalog_lines=catalog_lines,
        minute=40,
        score_home=1,
        score_away=0,
        pressure_score=6,
        tension_score=3,
    )

    assert worker.queue_size == 5
    entries = [worker._q.get_nowait() for _ in range(5)]

    # Uma entry por linha, na ordem do catálogo.
    assert [e.linha for e in entries] == [5.5, 6.5, 7.5, 8.5, 9.5]
    assert [e.raw["catalog_position"] for e in entries] == [0, 1, 2, 3, 4]
    # Contexto rico replicado em todas.
    assert all(e.minute == 40 for e in entries)
    assert all(e.pressure_score == 6 for e in entries)
    assert all(e.tension_score == 3 for e in entries)
    # captured_at IDÊNTICO nas N linhas: viabiliza GROUP BY temporal.
    assert len({e.captured_at for e in entries}) == 1
    assert entries[0].captured_at is not None


# ─── Fire-and-forget ────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_telemetria_falha_nao_bloqueia_pipeline(monkeypatch, caplog):
    jogo = _jogo()
    sistema = _make_sistema(monkeypatch, flag_on=True, jogo=jogo)

    async def _fail_only_telemetry(*args, **kwargs):
        # Telemetria passa persist_telemetry=True; emissão não.
        if kwargs.get("persist_telemetry"):
            raise RuntimeError("bridge down")
        return None

    sistema.composite_odds.get_corners = AsyncMock(side_effect=_fail_only_telemetry)

    # Não levanta — a telemetria é fire-and-forget.
    await sistema._analisar_jogo(_FIXTURE)

    # O pipeline de sinal seguiu apesar da falha de telemetria.
    sistema.decision_engine.pre_avaliar.assert_called_once()
    assert "Telemetria de odds falhou" in caplog.text
