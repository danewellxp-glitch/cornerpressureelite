"""Smoke test fim-a-fim do provider Sportradar.

Uso:
    python scripts/sportradar_smoke.py --match-id 70401284 \\
        --token "T=exp=...~hmac=..."

    SPORTRADAR_TOKEN="T=exp=..." python scripts/sportradar_smoke.py \\
        --match-id 70401284

    python scripts/sportradar_smoke.py --match-id 70401284 \\
        --proxy http://user:pass@ip:port

Harness Fase A §5.6.
"""
import argparse
import asyncio
import logging
import os
import sys
from pathlib import Path

# Permite rodar `python scripts/sportradar_smoke.py ...` da raiz do projeto.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from data.providers.sportradar import SportradarClient, SportradarSession  # noqa: E402


def setup_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)-7s %(name)s %(message)s",
        datefmt="%H:%M:%S",
    )


async def main() -> int:
    ap = argparse.ArgumentParser(
        description="Smoke test do provider Sportradar"
    )
    ap.add_argument("--match-id", required=True, help="matchId Sportradar")
    ap.add_argument(
        "--token",
        help="Token completo (T=exp=...~hmac=...). Fallback: env "
             "SPORTRADAR_TOKEN",
    )
    ap.add_argument("--proxy", help="http://user:pass@ip:port (opcional)")
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args()

    setup_logging(args.verbose)

    token = args.token or os.environ.get("SPORTRADAR_TOKEN")
    if not token:
        print(
            "ERRO: forneça --token ou exporte SPORTRADAR_TOKEN com o "
            "token completo (T=exp=...~hmac=...)",
            file=sys.stderr,
        )
        return 2

    session = SportradarSession()
    session.set_token(token)

    async with SportradarClient(session, proxy=args.proxy) as client:
        match_id = args.match_id

        info = await client.match_info(match_id)
        print("\n=== match_info ===")
        if info:
            print(
                f"  {info.home_team_name} {info.score_home or '?'} x "
                f"{info.score_away or '?'} {info.away_team_name}"
            )
            print(f"  status={info.status} minute={info.minute}")
            print(
                f"  coverage: cornerson={info.coverage.cornerson} "
                f"cardson={info.coverage.cardson} "
                f"lineups={info.coverage.lineups}"
            )
        else:
            print("  (sem resposta — token expirado ou matchId inválido)")
            return 1

        sit = await client.stats_match_situation(match_id)
        print("\n=== situation ===")
        if sit:
            print(
                f"  possession: {sit.possession_home_pct}% vs "
                f"{sit.possession_away_pct}%"
            )
            print(
                f"  attack:     {sit.attack_home_pct}% vs "
                f"{sit.attack_away_pct}%"
            )
            print(
                f"  dangerous:  {sit.dangerous_attack_home_pct}% vs "
                f"{sit.dangerous_attack_away_pct}%"
            )
        else:
            print("  (sem dados)")

        delta = await client.get_timeline_delta(match_id)
        print("\n=== timeline_delta ===")
        if delta:
            print(
                f"  {len(delta.events)} eventos, "
                f"last_seconds={delta.last_seconds}"
            )
            for e in delta.events[-5:]:
                print(
                    f"  [{e.minute:3d}'] {e.type:18s} "
                    f"{(e.team or '?'):5s} {(e.player_name or '?')}"
                )
        else:
            print("  (sem dados)")

        ext = await client.match_details_extended(match_id)
        print("\n=== details_extended ===")
        if ext:
            print(f"  minute: {ext.minute}")
            print(
                f"  escanteios: {ext.corners_home} x {ext.corners_away}"
            )
            print(
                f"  cartões amarelos: {ext.yellowcards_home} x "
                f"{ext.yellowcards_away}"
            )
            print(
                f"  cartões vermelhos: {ext.redcards_home} x "
                f"{ext.redcards_away}"
            )
            print(
                f"  shots on target: {ext.shots_on_target_home} x "
                f"{ext.shots_on_target_away}"
            )
        else:
            print("  (sem dados)")

    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
