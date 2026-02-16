"""
Backtest Reporter — Gera relatorios markdown dos resultados.
"""

import os
import logging
from datetime import datetime
from typing import List, Dict
from collections import defaultdict

from backtest.simulator import BacktestRun

logger = logging.getLogger("CPES.Backtest.Reporter")


def generate_report(run: BacktestRun, title: str = "Backtest CPES") -> str:
    """Gera relatorio markdown de um run de backtest."""
    lines = []
    now = datetime.now().strftime("%Y-%m-%d %H:%M")

    lines.append(f"# {title}")
    lines.append(f"\n> Gerado em: {now}")
    lines.append("")

    # --- Parametros ---
    lines.append("## Parametros")
    lines.append("")
    lines.append("| Parametro | Valor |")
    lines.append("|-----------|-------|")
    for k, v in run.params.items():
        lines.append(f"| {k} | {v} |")
    lines.append("")

    # --- Resumo Geral ---
    lines.append("## Resumo Geral")
    lines.append("")
    lines.append(f"- **Total de jogos analisados:** {len(run.results)}")
    lines.append(f"- **Sinais emitidos:** {run.total_sinais} ({run.premiums} PREMIUM, {run.normais} NORMAL)")
    lines.append(f"- **Com resultado:** {len(run.sinais_com_resultado)}")
    lines.append(f"- **Greens:** {run.greens}")
    lines.append(f"- **Reds:** {run.reds}")
    lines.append(f"- **Winrate:** {run.winrate}%")
    lines.append(f"- **ROI Total:** {run.roi_total:+.2f}u")
    lines.append(f"- **Drawdown Maximo:** {run.drawdown_maximo:.2f}u")
    lines.append("")

    # --- Por Liga ---
    sinais_por_liga = defaultdict(list)
    for r in run.sinais_com_resultado:
        sinais_por_liga[r.liga_nome].append(r)

    if sinais_por_liga:
        lines.append("## Performance por Liga")
        lines.append("")
        lines.append("| Liga | Sinais | Greens | Reds | Winrate | ROI |")
        lines.append("|------|--------|--------|------|---------|-----|")

        for liga, sinais in sorted(sinais_por_liga.items(), key=lambda x: -sum(s.roi or 0 for s in x[1])):
            g = len([s for s in sinais if s.resultado == "GREEN"])
            r = len([s for s in sinais if s.resultado == "RED"])
            total = g + r
            wr = round(g / total * 100, 1) if total > 0 else 0
            roi = sum(s.roi or 0 for s in sinais)
            lines.append(f"| {liga} | {total} | {g} | {r} | {wr}% | {roi:+.2f}u |")
        lines.append("")

    # --- Detalhes dos Sinais ---
    if run.sinais_com_resultado:
        lines.append("## Detalhes dos Sinais")
        lines.append("")
        lines.append("| Jogo | Min | Tipo | Score | Edge | Linha | Odd | Corners | Resultado | ROI |")
        lines.append("|------|-----|------|-------|------|-------|-----|---------|-----------|-----|")

        for r in sorted(run.sinais_com_resultado, key=lambda x: x.fixture_id):
            emoji = "+" if r.resultado == "GREEN" else "-"
            lines.append(
                f"| {r.jogo_desc} | {r.minuto} | {r.sinal_tipo} | {r.score} | "
                f"{r.edge:.1f} | {r.linha:.1f} | {r.odd:.2f}x | "
                f"{r.corners_final} | {r.resultado} | {emoji}{abs(r.roi or 0):.2f}u |"
            )
        lines.append("")

    return "\n".join(lines)


def generate_optimization_report(runs: List[BacktestRun]) -> str:
    """Gera relatorio comparativo de multiplos runs (grid search)."""
    lines = []
    now = datetime.now().strftime("%Y-%m-%d %H:%M")

    lines.append("# Otimizacao de Parametros — CPES Backtest")
    lines.append(f"\n> Gerado em: {now}")
    lines.append(f"\n> Total de combinacoes testadas: {len(runs)}")
    lines.append("")

    # Top 10 melhores configs
    lines.append("## Top 10 Melhores Configuracoes (por ROI)")
    lines.append("")
    lines.append("| # | Min Score | Min Edge | Min Score P | Min Edge P | Sinais | Winrate | ROI | Drawdown |")
    lines.append("|---|-----------|----------|-------------|------------|--------|---------|-----|----------|")

    for i, run in enumerate(runs[:10], 1):
        p = run.params
        lines.append(
            f"| {i} | {p.get('min_score_normal', '-')} | "
            f"{p.get('min_edge_normal', '-')} | "
            f"{p.get('min_score_premium', '-')} | "
            f"{p.get('min_edge_premium', '-')} | "
            f"{run.total_sinais} | {run.winrate}% | "
            f"{run.roi_total:+.2f}u | {run.drawdown_maximo:.2f}u |"
        )
    lines.append("")

    # Piores 5 configs
    if len(runs) > 10:
        lines.append("## 5 Piores Configuracoes")
        lines.append("")
        lines.append("| # | Min Score | Min Edge | Sinais | Winrate | ROI |")
        lines.append("|---|-----------|----------|--------|---------|-----|")

        for i, run in enumerate(runs[-5:], 1):
            p = run.params
            lines.append(
                f"| {i} | {p.get('min_score_normal', '-')} | "
                f"{p.get('min_edge_normal', '-')} | "
                f"{run.total_sinais} | {run.winrate}% | {run.roi_total:+.2f}u |"
            )
        lines.append("")

    # Analise
    if runs and runs[0].total_sinais > 0:
        best = runs[0]
        lines.append("## Recomendacao")
        lines.append("")
        lines.append(f"Melhor configuracao encontrada:")
        lines.append(f"- `min_score_normal = {best.params.get('min_score_normal')}`")
        lines.append(f"- `min_edge_normal = {best.params.get('min_edge_normal')}`")
        lines.append(f"- `min_score_premium = {best.params.get('min_score_premium')}`")
        lines.append(f"- `min_edge_premium = {best.params.get('min_edge_premium')}`")
        lines.append(f"- ROI: **{best.roi_total:+.2f}u** | Winrate: **{best.winrate}%** | Sinais: {best.total_sinais}")
        lines.append("")

    return "\n".join(lines)


def save_report(content: str, filename: str, docs_dir: str = None) -> str:
    """Salva relatorio em docs/analises/."""
    if docs_dir is None:
        # Subir ate a raiz do projeto
        base = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        docs_dir = os.path.join(base, "docs", "analises")

    os.makedirs(docs_dir, exist_ok=True)
    filepath = os.path.join(docs_dir, filename)

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)

    logger.info(f"Relatorio salvo em: {filepath}")
    return filepath
