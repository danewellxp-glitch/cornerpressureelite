"""Smoke fim-a-fim do BetanoStatsStream.

Uso (a partir de corner-pressure-elite/):
    python scripts/betano_statsstream_smoke.py --event-id 84586925 \\
        --cookies config/betano_cookies.json

Cookies devem vir de uma sessão real (ver `docs/sprints/2026-05-12-betano-spike-mitmproxy.md`)
ou serem extraídos do navegador. Esperados em JSON com chave `cookies`.
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from pathlib import Path

# permite rodar de qualquer cwd dentro do projeto
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from data.providers.betano import BetanoSession, BetanoStatsStream  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")


async def run(event_id: int, cookies_path: str) -> int:
    session = BetanoSession.from_file(cookies_path)
    client = BetanoStatsStream(session)
    try:
        info = await client.get_info_aggregated(event_id)
        print(f"\n=== info ===")
        if info:
            print(f"  {info.home_team} ({info.home_team_code}) "
                  f"x {info.away_team} ({info.away_team_code})")
            print(f"  Liga: {info.league_name}")
            print(f"  Opta match_id: {info.opta_match_id}")
            print(f"  Período: {info.current_period}  Started: {info.started}")
        else:
            print("  (nenhuma resposta)")

        cfg = await client.get_config(event_id)
        print(f"\n=== config ===")
        if cfg:
            print(f"  Provider: {cfg.provider_type}")
            print(f"  Momentum enabled: {cfg.momentum_enabled}")
            print(f"  Disabled tabs: {cfg.disabled_tabs}")

        det = await client.get_stats_detailed(event_id)
        print(f"\n=== stats detailed (total) ===")
        if det:
            h, a = det.home.total, det.away.total
            print(f"  Corners:   {h.corners} x {a.corners}")
            print(f"  Yellow:    {h.yellow_cards} x {a.yellow_cards}")
            print(f"  Red:       {h.red_cards} x {a.red_cards}")
            print(f"  Shots OnT: {h.shots_on_target} x {a.shots_on_target}")
            print(f"  Dang.Att:  {h.dangerous_attacks} x {a.dangerous_attacks}")
            print(f"  Posse:     {h.possession}% x {a.possession}%")
            print(f"  xG live:   {h.x_goals_live:.2f} x {a.x_goals_live:.2f}")

        mom = await client.get_momentum(event_id)
        print(f"\n=== momentum ===")
        if mom:
            print(f"  Pontos: {len(mom.points)}")
            for p in mom.points[-5:]:
                print(f"  [{p.minute:3d}'] {p.period:18s} pressure={p.pressure:+4d}")

        lin = await client.get_lineups(event_id)
        print(f"\n=== lineups ===")
        if lin:
            print(f"  {lin.home.name}: formação {lin.home.formation or '?'}, "
                  f"{sum(len(r) for r in lin.home.on_pitch)} jogadores em campo")
            print(f"  {lin.away.name}: formação {lin.away.formation or '?'}, "
                  f"{sum(len(r) for r in lin.away.on_pitch)} jogadores em campo")

        h2h = await client.get_h2h(event_id)
        print(f"\n=== h2h ===")
        if h2h:
            s = h2h.summary
            print(f"  V {s.home_wins} | E {s.draws} | D {s.away_wins} "
                  f"({len(h2h.previous_meetings)} jogos)")

        print()
        return 0
    finally:
        await session.close()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--event-id", type=int, required=True)
    ap.add_argument("--cookies", default="config/betano_cookies.json")
    args = ap.parse_args()
    return asyncio.run(run(args.event_id, args.cookies))


if __name__ == "__main__":
    sys.exit(main())
