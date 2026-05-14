"""Aplica migrations/*.sql em ordem lexicográfica via asyncpg.

Uso (dentro do container cpes-api ou com DATABASE_URL no ambiente):
    docker exec -it cpes-api python scripts/run_migrations.py
Ou no host com DATABASE_URL exportada apontando para o Postgres exposto.

Arquivos devem ser idempotentes (IF NOT EXISTS / ON CONFLICT). Sem tabela de
controle por enquanto — basta re-rodar caso queira garantir o estado.
"""
import asyncio
import logging
import sys
from pathlib import Path

# permite rodar de qualquer cwd dentro do projeto
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import asyncpg

from config import DATABASE_URL

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("CPES.run_migrations")


async def main() -> int:
    migrations_dir = ROOT / "migrations"
    if not migrations_dir.is_dir():
        log.error("Diretório não existe: %s", migrations_dir)
        return 2

    files = sorted(migrations_dir.glob("*.sql"))
    if not files:
        log.warning("Nenhum arquivo .sql encontrado em %s", migrations_dir)
        return 0

    url = DATABASE_URL.replace("postgres://", "postgresql://", 1)
    conn = await asyncpg.connect(url)
    try:
        for path in files:
            sql = path.read_text(encoding="utf-8")
            if not sql.strip():
                continue
            log.info("Aplicando %s ...", path.name)
            await conn.execute(sql)
            log.info("OK %s", path.name)
    finally:
        await conn.close()

    log.info("Concluído: %d arquivo(s) aplicado(s).", len(files))
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
