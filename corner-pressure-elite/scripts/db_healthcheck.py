"""Healthcheck das 3 tabelas Fase D + indicadores de actividade dos workers.

Uso (dentro do container cpes-api):
    docker exec -it cpes-api python scripts/db_healthcheck.py
"""
from __future__ import annotations

import asyncio
import logging
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import asyncpg  # noqa: E402

from config import DATABASE_URL  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("CPES.db_healthcheck")

TABLES = [
    ("betano_fixture_map", "resolved_at"),
    ("odds_history", "captured_at"),
    ("incidents_history", "captured_at"),
]


async def main() -> int:
    url = DATABASE_URL.replace("postgres://", "postgresql://", 1)
    try:
        pool = await asyncpg.create_pool(url, min_size=1, max_size=2)
    except Exception as e:
        log.error("Não consegui conectar: %s", e)
        return 2
    try:
        async with pool.acquire() as conn:
            for tbl, ts_col in TABLES:
                exists = await conn.fetchval(
                    "SELECT to_regclass($1) IS NOT NULL", f"public.{tbl}"
                )
                if not exists:
                    print(f"[FAIL] {tbl}: tabela não existe")
                    continue
                row = await conn.fetchrow(f"SELECT COUNT(*) AS n FROM {tbl}")
                n = int(row["n"])
                row = await conn.fetchrow(
                    f"SELECT MAX({ts_col}) AS last FROM {tbl}"
                )
                last = row["last"]
                print(f"[OK]   {tbl}: {n} linhas, último {ts_col}={last}")
    finally:
        await pool.close()
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
