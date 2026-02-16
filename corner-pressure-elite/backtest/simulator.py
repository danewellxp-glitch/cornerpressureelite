"""
Backtest Simulator — Replay do decision engine sobre snapshots reais.

Carrega snapshots coletados durante analise ao vivo e roda o decision engine
com parametros customizaveis para avaliar performance de diferentes configs.
"""

import sys
import os
import asyncio
import logging
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple
from itertools import product

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from data.models import JogoAoVivo
import engine.decision_engine as de_module
from engine.decision_engine import DecisionEngine
from storage.database import Database

logger = logging.getLogger("CPES.Backtest")


@dataclass
class BacktestResult:
    """Resultado de um backtest para um snapshot."""
    fixture_id: int
    jogo_desc: str
    liga_nome: str
    minuto: int
    sinal_tipo: Optional[str]  # NORMAL, PREMIUM, ou None (sem sinal)
    score: int
    projecao: float
    edge: float
    linha: float
    odd: float
    corners_final: Optional[int]
    resultado: Optional[str]  # GREEN, RED, ou None (sem resultado)
    roi: Optional[float]


@dataclass
class BacktestRun:
    """Resultado agregado de um run de backtest."""
    params: Dict
    results: List[BacktestResult] = field(default_factory=list)

    @property
    def sinais(self) -> List[BacktestResult]:
        return [r for r in self.results if r.sinal_tipo is not None]

    @property
    def sinais_com_resultado(self) -> List[BacktestResult]:
        return [r for r in self.sinais if r.resultado is not None]

    @property
    def greens(self) -> int:
        return len([r for r in self.sinais_com_resultado if r.resultado == "GREEN"])

    @property
    def reds(self) -> int:
        return len([r for r in self.sinais_com_resultado if r.resultado == "RED"])

    @property
    def winrate(self) -> float:
        total = self.greens + self.reds
        return round(self.greens / total * 100, 1) if total > 0 else 0.0

    @property
    def roi_total(self) -> float:
        return round(sum(r.roi for r in self.sinais_com_resultado if r.roi is not None), 2)

    @property
    def total_sinais(self) -> int:
        return len(self.sinais)

    @property
    def premiums(self) -> int:
        return len([r for r in self.sinais if r.sinal_tipo == "PREMIUM"])

    @property
    def normais(self) -> int:
        return len([r for r in self.sinais if r.sinal_tipo == "NORMAL"])

    @property
    def drawdown_maximo(self) -> float:
        """Calcula drawdown maximo (maior sequencia de perdas)."""
        roi_acumulado = 0.0
        pico = 0.0
        max_dd = 0.0
        for r in self.sinais_com_resultado:
            if r.roi is not None:
                roi_acumulado += r.roi
                pico = max(pico, roi_acumulado)
                dd = pico - roi_acumulado
                max_dd = max(max_dd, dd)
        return round(max_dd, 2)


def snapshot_to_jogo(snap: Dict) -> JogoAoVivo:
    """Converte um snapshot do banco em JogoAoVivo."""
    return JogoAoVivo(
        id=snap["fixture_id"],
        liga_id=snap.get("liga_id", 0),
        liga_nome=snap.get("liga_nome", ""),
        time_casa=snap.get("time_casa", "?"),
        time_fora=snap.get("time_fora", "?"),
        placar_casa=snap.get("placar_casa", 0),
        placar_fora=snap.get("placar_fora", 0),
        minuto=snap.get("minuto", 0),
        escanteios_total=snap.get("escanteios_total", 0),
        escanteios_casa=snap.get("escanteios_casa", 0),
        escanteios_fora=snap.get("escanteios_fora", 0),
        escanteios_ultimos_10min=snap.get("escanteios_ultimos_10min", 0),
        escanteios_ultimos_5min=snap.get("escanteios_ultimos_5min", 0),
        ataques_perigosos_ultimos_10min=snap.get("ataques_perigosos", 0),
        posse_ultimos_10min=snap.get("posse_dominante", 0.0),
        finalizacoes_recentes=snap.get("finalizacoes", 0),
        media_historica_combinada=snap.get("media_historica", 0.0),
        linha_atual=snap.get("linha_atual", 0.0),
        odd_atual=snap.get("odd_atual", 0.0),
    )


def _apply_params(params: Dict):
    """Aplica parametros customizados no modulo do decision engine."""
    mapping = {
        "min_score_normal": "MIN_SCORE_NORMAL",
        "min_score_premium": "MIN_SCORE_PREMIUM",
        "min_edge_normal": "MIN_EDGE_NORMAL",
        "min_edge_premium": "MIN_EDGE_PREMIUM",
    }
    for key, attr in mapping.items():
        if key in params:
            setattr(de_module, attr, params[key])


def _save_original_params() -> Dict:
    """Salva parametros originais do decision engine."""
    return {
        "MIN_SCORE_NORMAL": de_module.MIN_SCORE_NORMAL,
        "MIN_SCORE_PREMIUM": de_module.MIN_SCORE_PREMIUM,
        "MIN_EDGE_NORMAL": de_module.MIN_EDGE_NORMAL,
        "MIN_EDGE_PREMIUM": de_module.MIN_EDGE_PREMIUM,
    }


def _restore_params(original: Dict):
    """Restaura parametros originais."""
    for attr, val in original.items():
        setattr(de_module, attr, val)


def simulate_snapshot(engine: DecisionEngine, snap: Dict) -> BacktestResult:
    """Simula o decision engine sobre um snapshot."""
    jogo = snapshot_to_jogo(snap)
    sinal = engine.avaliar(jogo)

    corners_final = snap.get("corners_final")
    resultado = None
    roi = None

    if sinal and corners_final is not None:
        linha = jogo.linha_atual
        resultado = "GREEN" if corners_final > linha else "RED"
        odd = jogo.odd_atual or 1.0
        roi = (odd - 1.0) if resultado == "GREEN" else -1.0

    return BacktestResult(
        fixture_id=snap["fixture_id"],
        jogo_desc=f"{snap.get('time_casa', '?')} vs {snap.get('time_fora', '?')}",
        liga_nome=snap.get("liga_nome", ""),
        minuto=snap.get("minuto", 0),
        sinal_tipo=sinal.tipo if sinal else None,
        score=sinal.pressure_score if sinal else 0,
        projecao=sinal.projecao if sinal else 0.0,
        edge=sinal.edge if sinal else 0.0,
        linha=jogo.linha_atual,
        odd=jogo.odd_atual,
        corners_final=corners_final,
        resultado=resultado,
        roi=roi,
    )


async def run_backtest(
    db_path: Optional[str] = None,
    params: Optional[Dict] = None,
    liga_id: Optional[int] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
) -> BacktestRun:
    """Roda backtest sobre snapshots com parametros customizados."""
    db = Database(db_path=db_path)
    snapshots = await db.get_snapshots(
        liga_id=liga_id,
        date_from=date_from,
        date_to=date_to,
        apenas_com_resultado=True,
    )

    if not snapshots:
        logger.warning("Nenhum snapshot com resultado encontrado para backtest")
        return BacktestRun(params=params or {})

    original_params = _save_original_params()

    try:
        if params:
            _apply_params(params)

        engine = DecisionEngine()
        run = BacktestRun(params=params or {
            "min_score_normal": de_module.MIN_SCORE_NORMAL,
            "min_score_premium": de_module.MIN_SCORE_PREMIUM,
            "min_edge_normal": de_module.MIN_EDGE_NORMAL,
            "min_edge_premium": de_module.MIN_EDGE_PREMIUM,
        })

        # Deduplica: pegar apenas 1 snapshot por fixture (o do minuto mais alto)
        latest_by_fixture = {}
        for snap in snapshots:
            fid = snap["fixture_id"]
            if fid not in latest_by_fixture or snap["minuto"] > latest_by_fixture[fid]["minuto"]:
                latest_by_fixture[fid] = snap

        for snap in latest_by_fixture.values():
            result = simulate_snapshot(engine, snap)
            run.results.append(result)

        logger.info(
            f"Backtest concluido: {run.total_sinais} sinais de {len(latest_by_fixture)} jogos | "
            f"Winrate: {run.winrate}% | ROI: {run.roi_total:+.2f}u"
        )
        return run
    finally:
        _restore_params(original_params)


async def run_optimization(
    db_path: Optional[str] = None,
    liga_id: Optional[int] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
) -> List[BacktestRun]:
    """Roda grid search de parametros para encontrar melhor configuracao."""
    param_grid = {
        "min_score_normal": [5, 6, 7],
        "min_edge_normal": [0.5, 0.8, 1.0, 1.2],
        "min_score_premium": [7, 8, 9],
        "min_edge_premium": [1.0, 1.5, 2.0],
    }

    # Gerar todas as combinacoes
    keys = list(param_grid.keys())
    values = list(param_grid.values())
    combos = list(product(*values))

    logger.info(f"Otimizacao: testando {len(combos)} combinacoes de parametros...")

    runs = []
    for combo in combos:
        params = dict(zip(keys, combo))
        run = await run_backtest(
            db_path=db_path,
            params=params,
            liga_id=liga_id,
            date_from=date_from,
            date_to=date_to,
        )
        runs.append(run)

    # Ordenar por ROI (melhor primeiro)
    runs.sort(key=lambda r: r.roi_total, reverse=True)

    if runs:
        best = runs[0]
        logger.info(
            f"Melhor config: {best.params} | "
            f"Sinais: {best.total_sinais} | Winrate: {best.winrate}% | ROI: {best.roi_total:+.2f}u"
        )

    return runs
