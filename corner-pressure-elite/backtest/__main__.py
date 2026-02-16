"""
CLI do Backtest CPES.

Uso:
    python -m backtest simulate                           # Simular com parametros atuais
    python -m backtest simulate --min-score 5 --min-edge 0.5  # Parametros custom
    python -m backtest optimize                           # Grid search de parametros
    python -m backtest report                             # Gerar relatorio do ultimo backtest
    python -m backtest status                             # Status dos dados coletados
"""

import sys
import os
import asyncio
import argparse

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from datetime import datetime


def main():
    parser = argparse.ArgumentParser(description="CPES Backtest Engine")
    subparsers = parser.add_subparsers(dest="command", help="Comando")

    # simulate
    sim = subparsers.add_parser("simulate", help="Simular com parametros")
    sim.add_argument("--min-score", type=int, help="Min pressure score (NORMAL)")
    sim.add_argument("--min-edge", type=float, help="Min edge (NORMAL)")
    sim.add_argument("--min-score-premium", type=int, help="Min pressure score (PREMIUM)")
    sim.add_argument("--min-edge-premium", type=float, help="Min edge (PREMIUM)")
    sim.add_argument("--liga", type=int, help="Filtrar por liga ID")
    sim.add_argument("--from", dest="date_from", help="Data inicio (YYYY-MM-DD)")
    sim.add_argument("--to", dest="date_to", help="Data fim (YYYY-MM-DD)")
    sim.add_argument("--db", help="Caminho do banco de dados")

    # optimize
    opt = subparsers.add_parser("optimize", help="Grid search de parametros")
    opt.add_argument("--liga", type=int, help="Filtrar por liga ID")
    opt.add_argument("--from", dest="date_from", help="Data inicio")
    opt.add_argument("--to", dest="date_to", help="Data fim")
    opt.add_argument("--db", help="Caminho do banco de dados")
    opt.add_argument("--save", action="store_true", help="Salvar relatorio em docs/")

    # report
    rep = subparsers.add_parser("report", help="Gerar relatorio")
    rep.add_argument("--db", help="Caminho do banco de dados")
    rep.add_argument("--liga", type=int, help="Filtrar por liga ID")

    # status
    st = subparsers.add_parser("status", help="Status dos dados coletados")
    st.add_argument("--db", help="Caminho do banco de dados")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    asyncio.run(_run(args))


async def _run(args):
    if args.command == "status":
        await _cmd_status(args)
    elif args.command == "simulate":
        await _cmd_simulate(args)
    elif args.command == "optimize":
        await _cmd_optimize(args)
    elif args.command == "report":
        await _cmd_report(args)


async def _cmd_status(args):
    from storage.database import Database

    db = Database(db_path=args.db)
    await db.init()  # garante que tabelas existem
    stats = await db.get_snapshot_stats()

    print("\n=== CPES Backtest — Status dos Dados ===\n")
    print(f"  Total de snapshots:   {stats['total_snapshots']}")
    print(f"  Com resultado:        {stats['com_resultado']}")
    print(f"  Sem resultado:        {stats['sem_resultado']}")
    print(f"  Jogos unicos:         {stats['jogos_unicos']}")
    print()

    if stats["por_liga"]:
        print("  Por liga:")
        for liga, cnt in stats["por_liga"]:
            print(f"    {liga or 'Desconhecida':30s} {cnt} snapshots")

    if stats["total_snapshots"] == 0:
        print("\n  Nenhum dado coletado ainda.")
        print("  Execute o sistema principal (python main.py) para coletar snapshots.")
    elif stats["com_resultado"] == 0:
        print("\n  Nenhum snapshot com resultado final.")
        print("  Aguarde os jogos terminarem para verificacao automatica dos resultados.")
    else:
        print(f"\n  Pronto para backtest com {stats['com_resultado']} snapshots.")
    print()


async def _cmd_simulate(args):
    from backtest.simulator import run_backtest
    from backtest.reporter import generate_report

    params = {}
    if args.min_score is not None:
        params["min_score_normal"] = args.min_score
    if args.min_edge is not None:
        params["min_edge_normal"] = args.min_edge
    if args.min_score_premium is not None:
        params["min_score_premium"] = args.min_score_premium
    if args.min_edge_premium is not None:
        params["min_edge_premium"] = args.min_edge_premium

    run = await run_backtest(
        db_path=args.db,
        params=params if params else None,
        liga_id=args.liga,
        date_from=args.date_from,
        date_to=args.date_to,
    )

    if not run.results:
        print("\nNenhum snapshot encontrado. Execute 'python -m backtest status' para verificar.")
        return

    print(f"\n=== CPES Backtest — Simulacao ===\n")
    print(f"  Jogos analisados:  {len(run.results)}")
    print(f"  Sinais emitidos:   {run.total_sinais} ({run.premiums}P + {run.normais}N)")
    print(f"  Com resultado:     {len(run.sinais_com_resultado)}")
    print(f"  Greens:            {run.greens}")
    print(f"  Reds:              {run.reds}")
    print(f"  Winrate:           {run.winrate}%")
    print(f"  ROI Total:         {run.roi_total:+.2f}u")
    print(f"  Drawdown Max:      {run.drawdown_maximo:.2f}u")
    print()

    # Mostrar detalhes dos sinais
    for r in run.sinais_com_resultado:
        emoji = "GREEN" if r.resultado == "GREEN" else " RED "
        print(
            f"  [{emoji}] {r.jogo_desc:40s} min {r.minuto:2d} | "
            f"Score {r.score} Edge {r.edge:+.1f} | "
            f"Linha {r.linha:.1f} Odd {r.odd:.2f}x | "
            f"Corners {r.corners_final} | ROI {r.roi:+.2f}u"
        )
    print()


async def _cmd_optimize(args):
    from backtest.simulator import run_optimization
    from backtest.reporter import generate_optimization_report, save_report

    runs = await run_optimization(
        db_path=args.db,
        liga_id=args.liga,
        date_from=args.date_from,
        date_to=args.date_to,
    )

    if not runs:
        print("\nNenhum dado para otimizacao.")
        return

    print(f"\n=== CPES Backtest — Otimizacao ({len(runs)} combinacoes) ===\n")
    print("  Top 5 configuracoes:\n")
    print(f"  {'#':>3s}  {'Score':>5s}  {'Edge':>5s}  {'ScoreP':>6s}  {'EdgeP':>5s}  {'Sinais':>6s}  {'WR':>6s}  {'ROI':>8s}")
    print(f"  {'---':>3s}  {'-----':>5s}  {'-----':>5s}  {'------':>6s}  {'-----':>5s}  {'------':>6s}  {'------':>6s}  {'--------':>8s}")

    for i, run in enumerate(runs[:5], 1):
        p = run.params
        print(
            f"  {i:3d}  {p.get('min_score_normal', '-'):>5}  "
            f"{p.get('min_edge_normal', '-'):>5}  "
            f"{p.get('min_score_premium', '-'):>6}  "
            f"{p.get('min_edge_premium', '-'):>5}  "
            f"{run.total_sinais:>6}  {run.winrate:>5.1f}%  "
            f"{run.roi_total:>+7.2f}u"
        )
    print()

    if args.save:
        report = generate_optimization_report(runs)
        date_str = datetime.now().strftime("%Y-%m-%d")
        filepath = save_report(report, f"backtest-optimization-{date_str}.md")
        print(f"  Relatorio salvo: {filepath}")
        print()


async def _cmd_report(args):
    from backtest.simulator import run_backtest
    from backtest.reporter import generate_report, save_report

    run = await run_backtest(db_path=args.db, liga_id=args.liga)

    if not run.results:
        print("\nNenhum dado para relatorio.")
        return

    report = generate_report(run)
    date_str = datetime.now().strftime("%Y-%m-%d")
    filepath = save_report(report, f"backtest-results-{date_str}.md")
    print(f"\nRelatorio gerado: {filepath}")


if __name__ == "__main__":
    main()
