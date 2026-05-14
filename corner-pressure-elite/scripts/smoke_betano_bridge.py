"""Smoke manual end-to-end do bridge Betano.

Bate contra o bridge HTTP real em :8080. Dois modos:

  catalog  (default) — chama client.markets(), mostra o catálogo completo
            de linhas e simula a política _pick_central_line do adapter
            (qual linha o adapter escolheria + se está in_preferred_range).
  quote    — chama client.quote() com --line e --side específicos
            (caminho Fase 3, política não dispara).

Uso:
  python3 scripts/smoke_betano_bridge.py --event-id 85687755
  python3 scripts/smoke_betano_bridge.py --event-id 85687755 --market goals_over_under
  python3 scripts/smoke_betano_bridge.py --event-id 85687755 --mode quote --line 4.5 --side over

Requer PYTHONPATH=. (rodar da raiz do projeto corner-pressure-elite).
"""
import argparse
import asyncio
import logging
import os
import sys

# Configurar env vars ANTES de importar config
os.environ.setdefault("USE_BETANO_BRIDGE", "true")
os.environ.setdefault("BETANO_BRIDGE_URL", "http://localhost:8080")

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logging.getLogger("httpx").setLevel(logging.INFO)

import config  # noqa: E402
from data.providers.betano_bridge.client import BetanoBridgeClient  # noqa: E402
from data.providers.betano_bridge.exceptions import BridgeError  # noqa: E402
from data.providers.betano_bridge.odds_adapter import BetanoBridgeOddsAdapter  # noqa: E402


def _parse_args():
    p = argparse.ArgumentParser(description="Smoke do bridge Betano")
    p.add_argument("--event-id", required=True, help="event_id de jogo ao vivo na Betano")
    p.add_argument(
        "--market", default="corners_over_under",
        choices=["corners_over_under", "cards_over_under", "goals_over_under"],
    )
    p.add_argument("--mode", default="catalog", choices=["catalog", "quote"])
    p.add_argument("--line", type=float, default=None, help="só usado em --mode quote")
    p.add_argument("--side", default="over", choices=["over", "under"], help="só em --mode quote")
    return p.parse_args()


async def _run_catalog(client: BetanoBridgeClient, args):
    print(f"--- mode=catalog market={args.market} event_id={args.event_id} ---")
    try:
        catalog = await client.markets(args.event_id, args.market)
    except BridgeError as e:
        print(f"  FALHOU: {type(e).__name__}: {e}")
        return

    lines = catalog.get("lines") or []
    print(f"  lines_count: {catalog.get('lines_count')}")
    for l in lines:
        print(f"    line={l['line']:6}  over={l['over_price']:6}  under={l['under_price']:6}")

    # Simula a política do adapter sem precisar de fixture_repo
    adapter = BetanoBridgeOddsAdapter(
        client=client,
        odd_min=config.BETANO_BRIDGE_PREFERRED_ODD_MIN,
        odd_max=config.BETANO_BRIDGE_PREFERRED_ODD_MAX,
    )
    chosen, in_range = adapter._pick_central_line(lines)
    print(f"\n  política _pick_central_line "
          f"(faixa [{config.BETANO_BRIDGE_PREFERRED_ODD_MIN}, "
          f"{config.BETANO_BRIDGE_PREFERRED_ODD_MAX}]):")
    if chosen is None:
        print("    catálogo vazio → adapter retornaria None")
    else:
        tag = "line_selected (INFO)" if in_range else "line_degraded (WARNING)"
        print(f"    escolhida: line={chosen['line']} over={chosen['over_price']} "
              f"under={chosen['under_price']}")
        print(f"    in_preferred_range={in_range} → log {tag}")


async def _run_quote(client: BetanoBridgeClient, args):
    if args.line is None:
        print("ERRO: --mode quote exige --line", file=sys.stderr)
        sys.exit(1)
    print(f"--- mode=quote market={args.market} line={args.line} side={args.side} "
          f"event_id={args.event_id} ---")
    try:
        data = await client.quote(args.event_id, args.market, args.line, side=args.side)
    except BridgeError as e:
        print(f"  FALHOU: {type(e).__name__}: {e}")
        return
    print(f"  found: {data.get('found')}")
    print(f"  odd: {data.get('odd')}")
    print(f"  line_found: {data.get('line_found')}")
    print(f"  selection_label: {data.get('selection_label')}")
    print(f"  page_url: {data.get('page_url')}")


async def main():
    args = _parse_args()
    print(f"=== Smoke bridge Betano — event_id={args.event_id} ===\n")

    client = BetanoBridgeClient(
        base_url=config.BETANO_BRIDGE_URL,
        timeout_sec=config.BETANO_BRIDGE_TIMEOUT_SEC,
        capture_sec=config.BETANO_BRIDGE_CAPTURE_SEC,
        retries=config.BETANO_BRIDGE_RETRIES,
    )

    print("--- Health check ---")
    try:
        health = await client.health()
        print(f"  ok: {health}\n")
    except BridgeError as e:
        print(f"  FALHOU: {e}")
        await client.close()
        return

    if args.mode == "catalog":
        await _run_catalog(client, args)
    else:
        await _run_quote(client, args)

    await client.close()
    print("\n=== Smoke concluído ===")


asyncio.run(main())
