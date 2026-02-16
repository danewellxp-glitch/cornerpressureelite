"""Testes do modulo de backtest (Sprint 3)."""

import sys
import os
import asyncio
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from backtest.simulator import (
    snapshot_to_jogo,
    simulate_snapshot,
    BacktestRun,
    BacktestResult,
    run_backtest,
)
from backtest.reporter import generate_report, generate_optimization_report
from engine.decision_engine import DecisionEngine
from storage.database import Database


def _snapshot_base(**kwargs) -> dict:
    """Cria snapshot de teste com defaults razoaveis."""
    defaults = dict(
        id=1,
        timestamp="2026-02-15T15:00:00",
        fixture_id=12345,
        liga_id=39,
        liga_nome="Premier League",
        time_casa="Arsenal",
        time_fora="Chelsea",
        minuto=63,
        placar_casa=1,
        placar_fora=1,
        escanteios_total=9,
        escanteios_casa=5,
        escanteios_fora=4,
        escanteios_ultimos_10min=3,
        escanteios_ultimos_5min=1,
        ataques_perigosos=8,
        posse_dominante=62.0,
        finalizacoes=4,
        media_historica=10.8,
        linha_atual=9.5,
        odd_atual=1.85,
        corners_final=12,
        resultado_final="GREEN",
    )
    defaults.update(kwargs)
    return defaults


# --- snapshot_to_jogo ---

def test_snapshot_to_jogo_campos_basicos():
    """Converte snapshot em JogoAoVivo com campos corretos."""
    snap = _snapshot_base()
    jogo = snapshot_to_jogo(snap)

    assert jogo.id == 12345
    assert jogo.liga_id == 39
    assert jogo.liga_nome == "Premier League"
    assert jogo.time_casa == "Arsenal"
    assert jogo.time_fora == "Chelsea"
    assert jogo.minuto == 63
    assert jogo.placar_casa == 1
    assert jogo.placar_fora == 1
    assert jogo.escanteios_total == 9
    assert jogo.escanteios_casa == 5
    assert jogo.escanteios_fora == 4
    assert jogo.linha_atual == 9.5
    assert jogo.odd_atual == 1.85


def test_snapshot_to_jogo_stats():
    """Converte campos de stats corretamente."""
    snap = _snapshot_base()
    jogo = snapshot_to_jogo(snap)

    assert jogo.escanteios_ultimos_10min == 3
    assert jogo.escanteios_ultimos_5min == 1
    assert jogo.ataques_perigosos_ultimos_10min == 8
    assert jogo.posse_ultimos_10min == 62.0
    assert jogo.finalizacoes_recentes == 4
    assert jogo.media_historica_combinada == 10.8


def test_snapshot_to_jogo_defaults():
    """Snapshot com campos faltando usa defaults."""
    snap = {"fixture_id": 999}
    jogo = snapshot_to_jogo(snap)

    assert jogo.id == 999
    assert jogo.minuto == 0
    assert jogo.escanteios_total == 0
    assert jogo.linha_atual == 0.0


# --- simulate_snapshot ---

def test_simulate_snapshot_com_sinal():
    """Snapshot com boas stats deve gerar sinal."""
    snap = _snapshot_base(
        escanteios_ultimos_10min=3,
        escanteios_ultimos_5min=1,
        ataques_perigosos=8,
        posse_dominante=62.0,
        finalizacoes=4,
        linha_atual=9.5,
        odd_atual=1.85,
        corners_final=12,
    )
    engine = DecisionEngine()
    result = simulate_snapshot(engine, snap)

    assert result.fixture_id == 12345
    assert result.sinal_tipo is not None  # deve gerar sinal
    assert result.resultado == "GREEN"  # 12 > 9.5
    assert result.roi is not None
    assert result.roi > 0  # GREEN com odd 1.85 = +0.85


def test_simulate_snapshot_sem_sinal():
    """Snapshot com stats ruins nao deve gerar sinal."""
    snap = _snapshot_base(
        minuto=30,  # fora da janela
        escanteios_total=2,  # poucos
        escanteios_ultimos_10min=0,
        escanteios_ultimos_5min=0,
        ataques_perigosos=1,
        posse_dominante=50.0,
        finalizacoes=0,
    )
    engine = DecisionEngine()
    result = simulate_snapshot(engine, snap)

    assert result.sinal_tipo is None
    assert result.resultado is None
    assert result.roi is None


def test_simulate_snapshot_red():
    """Snapshot que gera sinal mas corners finais < linha = RED."""
    snap = _snapshot_base(
        corners_final=8,  # abaixo da linha 9.5
    )
    engine = DecisionEngine()
    result = simulate_snapshot(engine, snap)

    if result.sinal_tipo is not None:
        assert result.resultado == "RED"
        assert result.roi == -1.0


def test_simulate_snapshot_sem_resultado():
    """Snapshot sem corners_final = resultado None."""
    snap = _snapshot_base(corners_final=None, resultado_final=None)
    engine = DecisionEngine()
    result = simulate_snapshot(engine, snap)

    # Pode ou nao gerar sinal, mas resultado deve ser None
    if result.sinal_tipo is not None:
        assert result.resultado is None
        assert result.roi is None


# --- BacktestRun ---

def test_backtest_run_metricas():
    """Calcula metricas corretamente."""
    run = BacktestRun(params={"min_score_normal": 6})
    run.results = [
        BacktestResult(1, "A vs B", "PL", 60, "NORMAL", 7, 12.0, 1.5, 9.5, 1.85, 12, "GREEN", 0.85),
        BacktestResult(2, "C vs D", "PL", 65, "PREMIUM", 9, 13.0, 2.0, 10.5, 2.00, 9, "RED", -1.0),
        BacktestResult(3, "E vs F", "PL", 55, "NORMAL", 6, 11.5, 1.0, 9.5, 1.90, 11, "GREEN", 0.90),
        BacktestResult(4, "G vs H", "BL", 70, None, 0, 0.0, 0.0, 0.0, 0.0, 8, None, None),  # sem sinal
    ]

    assert run.total_sinais == 3
    assert run.greens == 2
    assert run.reds == 1
    assert run.winrate == 66.7
    assert abs(run.roi_total - 0.75) < 0.01  # 0.85 + (-1.0) + 0.90
    assert run.premiums == 1
    assert run.normais == 2


def test_backtest_run_vazio():
    """Run sem resultados retorna zeros."""
    run = BacktestRun(params={})
    assert run.total_sinais == 0
    assert run.greens == 0
    assert run.winrate == 0.0
    assert run.roi_total == 0.0
    assert run.drawdown_maximo == 0.0


def test_backtest_run_drawdown():
    """Calcula drawdown maximo corretamente."""
    run = BacktestRun(params={})
    run.results = [
        BacktestResult(1, "", "", 0, "NORMAL", 0, 0, 0, 0, 1.85, 0, "GREEN", 0.85),
        BacktestResult(2, "", "", 0, "NORMAL", 0, 0, 0, 0, 1.90, 0, "RED", -1.0),
        BacktestResult(3, "", "", 0, "NORMAL", 0, 0, 0, 0, 2.00, 0, "RED", -1.0),
        BacktestResult(4, "", "", 0, "NORMAL", 0, 0, 0, 0, 1.80, 0, "GREEN", 0.80),
    ]
    # Acumulado: 0.85, -0.15, -1.15, -0.35
    # Pico: 0.85
    # Drawdown max: 0.85 - (-1.15) = 2.0
    assert run.drawdown_maximo == 2.0


# --- Reporter ---

def test_generate_report_markdown():
    """Gera relatorio markdown valido."""
    run = BacktestRun(params={"min_score_normal": 6, "min_edge_normal": 0.8})
    run.results = [
        BacktestResult(1, "A vs B", "PL", 60, "NORMAL", 7, 12.0, 1.5, 9.5, 1.85, 12, "GREEN", 0.85),
        BacktestResult(2, "C vs D", "PL", 65, "PREMIUM", 9, 13.0, 2.0, 10.5, 2.00, 9, "RED", -1.0),
    ]

    report = generate_report(run)

    assert "# Backtest CPES" in report
    assert "Winrate" in report
    assert "ROI Total" in report
    assert "A vs B" in report
    assert "GREEN" in report
    assert "RED" in report


def test_generate_optimization_report():
    """Gera relatorio de otimizacao."""
    runs = [
        BacktestRun(params={"min_score_normal": 5, "min_edge_normal": 0.5}),
        BacktestRun(params={"min_score_normal": 6, "min_edge_normal": 0.8}),
    ]
    runs[0].results = [
        BacktestResult(1, "A vs B", "PL", 60, "NORMAL", 6, 12.0, 1.5, 9.5, 1.85, 12, "GREEN", 0.85),
    ]

    report = generate_optimization_report(runs)

    assert "Otimizacao" in report
    assert "Top 10" in report


# --- Database integration (async) ---

def test_salvar_e_buscar_snapshots():
    """Testa salvar snapshot e buscar do banco."""
    async def _test():
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name

        try:
            from data.models import JogoAoVivo

            db = Database(db_path=db_path)
            await db.init()

            jogo = JogoAoVivo(
                id=999, liga_id=39, liga_nome="Premier League",
                time_casa="TeamA", time_fora="TeamB",
                placar_casa=1, placar_fora=0,
                minuto=60, escanteios_total=8,
                escanteios_casa=5, escanteios_fora=3,
                linha_atual=9.5, odd_atual=1.90,
            )

            await db.salvar_snapshot(jogo)
            snapshots = await db.get_snapshots()
            assert len(snapshots) == 1
            assert snapshots[0]["fixture_id"] == 999
            assert snapshots[0]["escanteios_total"] == 8

            # Atualizar resultado
            await db.atualizar_snapshot_resultado(999, 11)
            snapshots = await db.get_snapshots(apenas_com_resultado=True)
            assert len(snapshots) == 1
            assert snapshots[0]["corners_final"] == 11
            assert snapshots[0]["resultado_final"] == "GREEN"

            # Stats
            stats = await db.get_snapshot_stats()
            assert stats["total_snapshots"] == 1
            assert stats["com_resultado"] == 1
            assert stats["jogos_unicos"] == 1
        finally:
            os.unlink(db_path)

    asyncio.run(_test())


def test_backtest_completo_com_banco():
    """Testa fluxo completo: salvar snapshots -> rodar backtest."""
    async def _test():
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name

        try:
            from data.models import JogoAoVivo

            db = Database(db_path=db_path)
            await db.init()

            # Salvar 3 jogos com diferentes resultados
            jogos = [
                JogoAoVivo(
                    id=1, liga_id=39, liga_nome="Premier League",
                    time_casa="Arsenal", time_fora="Chelsea",
                    placar_casa=1, placar_fora=1, minuto=63,
                    escanteios_total=9, escanteios_casa=5, escanteios_fora=4,
                    escanteios_ultimos_10min=3, escanteios_ultimos_5min=1,
                    ataques_perigosos_ultimos_10min=8,
                    posse_ultimos_10min=62.0, finalizacoes_recentes=4,
                    media_historica_combinada=10.8,
                    linha_atual=9.5, odd_atual=1.85,
                ),
                JogoAoVivo(
                    id=2, liga_id=78, liga_nome="Bundesliga",
                    time_casa="Bayern", time_fora="Dortmund",
                    placar_casa=2, placar_fora=1, minuto=65,
                    escanteios_total=10, escanteios_casa=6, escanteios_fora=4,
                    escanteios_ultimos_10min=2, escanteios_ultimos_5min=1,
                    ataques_perigosos_ultimos_10min=6,
                    posse_ultimos_10min=58.0, finalizacoes_recentes=3,
                    media_historica_combinada=11.2,
                    linha_atual=10.5, odd_atual=1.95,
                ),
                JogoAoVivo(
                    id=3, liga_id=39, liga_nome="Premier League",
                    time_casa="Liverpool", time_fora="Man City",
                    placar_casa=0, placar_fora=0, minuto=55,
                    escanteios_total=4, escanteios_casa=2, escanteios_fora=2,
                    escanteios_ultimos_10min=0, escanteios_ultimos_5min=0,
                    ataques_perigosos_ultimos_10min=2,
                    posse_ultimos_10min=50.0, finalizacoes_recentes=1,
                    media_historica_combinada=10.8,
                    linha_atual=9.5, odd_atual=1.80,
                ),
            ]

            for jogo in jogos:
                await db.salvar_snapshot(jogo)

            # Atualizar resultados
            await db.atualizar_snapshot_resultado(1, 12)  # GREEN (12 > 9.5)
            await db.atualizar_snapshot_resultado(2, 9)   # RED (9 < 10.5)
            await db.atualizar_snapshot_resultado(3, 7)   # RED (7 < 9.5)

            # Rodar backtest
            run = await run_backtest(db_path=db_path)

            assert len(run.results) > 0
            # Verificar que ROI e calculado
            for r in run.sinais_com_resultado:
                assert r.resultado in ("GREEN", "RED")
                assert r.roi is not None
        finally:
            os.unlink(db_path)

    asyncio.run(_test())


if __name__ == "__main__":
    test_snapshot_to_jogo_campos_basicos()
    test_snapshot_to_jogo_stats()
    test_snapshot_to_jogo_defaults()
    test_simulate_snapshot_com_sinal()
    test_simulate_snapshot_sem_sinal()
    test_simulate_snapshot_red()
    test_simulate_snapshot_sem_resultado()
    test_backtest_run_metricas()
    test_backtest_run_vazio()
    test_backtest_run_drawdown()
    test_generate_report_markdown()
    test_generate_optimization_report()
    test_salvar_e_buscar_snapshots()
    test_backtest_completo_com_banco()
    print("Todos os testes de backtest passaram!")
