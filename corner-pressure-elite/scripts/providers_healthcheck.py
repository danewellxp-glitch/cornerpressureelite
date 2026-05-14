"""Healthcheck consolidado dos providers ativos (Fase C).

Reflete a configuração atual de `USE_NEW_PROVIDERS`/`DRIFT_CHECK_PROVIDERS`.
Sai com código 0 se ambos (odds + stats) respondem; 1 caso contrário.

Uso (dentro do container cpes-api):
    docker exec -it cpes-api python scripts/providers_healthcheck.py
"""
from __future__ import annotations

import asyncio
import logging
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import config as settings  # noqa: E402

from data.api_client import APIFootballClient  # noqa: E402
from data.providers.factory import build_providers  # noqa: E402
from utils.rate_limiter import RateLimiter  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("CPES.providers_healthcheck")


async def main() -> int:
    rl = RateLimiter(
        max_per_minute=getattr(settings, "API_RATE_LIMIT_MINUTE", 450),
        max_per_day=getattr(settings, "API_DAILY_LIMIT", 7500),
    )
    api_client = APIFootballClient(getattr(settings, "API_FOOTBALL_KEY", ""), rl)
    try:
        odds, stats, shutdown = await build_providers(settings, api_client)
        try:
            odds_ok = await odds.healthcheck()
            stats_ok = await stats.healthcheck()
            print(f"USE_NEW_PROVIDERS={settings.USE_NEW_PROVIDERS}")
            print(f"DRIFT_CHECK_PROVIDERS={settings.DRIFT_CHECK_PROVIDERS}")
            print(f"odds  composite: {'OK' if odds_ok  else 'FAIL'}")
            print(f"stats composite: {'OK' if stats_ok else 'FAIL'}")
            return 0 if (odds_ok and stats_ok) else 1
        finally:
            await shutdown()
    finally:
        await api_client.close()


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
