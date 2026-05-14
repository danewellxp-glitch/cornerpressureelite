"""Smoke fim-a-fim de markets + catalog.

Uso (a partir de corner-pressure-elite/):
    python scripts/betano_markets_smoke.py --event-id 84586925 \\
        --cookies config/betano_cookies.json

Não toca em WebSocket aqui — para WS use `betano_ws_smoke.py` (futuro).
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from data.providers.betano import (  # noqa: E402
    BetanoCatalog,
    BetanoMarkets,
    BetanoSession,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")


async def run(event_id: int, cookies_path: str) -> int:
    session = BetanoSession.from_file(cookies_path)
    markets = BetanoMarkets(session)
    catalog = BetanoCatalog(session)
    try:
        snap = await markets.get_event_latest(event_id)
        print(f"\n=== event {event_id} ===")
        if snap:
            home = snap.participants[0].name if snap.participants else "?"
            away = snap.participants[1].name if len(snap.participants) > 1 else "?"
            print(f"  {home} {snap.live_data.score_home} x {snap.live_data.score_away} {away}")
            print(f"  Markets disponíveis: {snap.total_markets_available}")
            print(f"  betradarMatchId: {snap.betradar_match_id}")
            print(f"  Liga: {snap.league_id}  Zone: {snap.zone_id}")
            print(f"  Live: {snap.is_live}  Clock(s): {snap.live_data.clock_seconds}")
        else:
            print("  (nenhuma resposta)")

        cnou = await markets.fetch_corners(event_id)
        print(f"\n=== CNOU (principal) ===")
        if cnou:
            print(f"  Linha {cnou.handicap}: Over {cnou.odd_over} | Under {cnou.odd_under}")

        tcou = await markets.fetch_cards(event_id)
        print(f"\n=== TCOU (principal) ===")
        if tcou:
            print(f"  Linha {tcou.handicap}: Over {tcou.odd_over} | Under {tcou.odd_under}")

        mapping = await catalog.resolve_event_full(event_id)
        print(f"\n=== statsplayer mapping ===")
        if mapping:
            print(f"  Sportradar matchId: {mapping.sr_match_id}")
            print(f"  Opta match_id: {mapping.opta_match_id}")
            print(f"  statTypes disponíveis: {mapping.available_stat_types}")
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
