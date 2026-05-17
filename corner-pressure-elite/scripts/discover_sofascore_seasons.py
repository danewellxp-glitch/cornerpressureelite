"""Descobre season_id atual de cada liga em SOFASCORE_LEAGUE_MAP.

Roda 1x por temporada (ou quando suspeitar de mudança). Saída é uma
tabela imprimível pra atualizar `data/providers/sofascore/league_map.py`
manualmente — não escreve no arquivo (evita pisar em comentários).

Uso:
    docker compose run --rm main python scripts/discover_sofascore_seasons.py
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

# Permite rodar de /app no container (PYTHONPATH=. equivalente)
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from data.providers.sofascore.client import SofaScoreClient  # noqa: E402
from data.providers.sofascore.league_map import SOFASCORE_LEAGUE_MAP  # noqa: E402


async def main() -> None:
    async with SofaScoreClient() as client:
        print(
            f"{'liga':<35} | {'af_id':>5} | {'tid':>5} | "
            f"{'season atual':>14} | descrição"
        )
        print("-" * 95)
        for af_id, info in SOFASCORE_LEAGUE_MAP.items():
            tid = info["unique_tournament_id"]
            data = await client.get(f"/unique-tournament/{tid}/seasons")
            seasons = (data or {}).get("seasons") or []
            if not seasons:
                print(
                    f"{info['name']:<35} | {af_id:>5} | {tid:>5} | "
                    f"{'(sem seasons)':>14} | —"
                )
                continue
            current = seasons[0]
            cur_id = current.get("id")
            cur_name = current.get("name") or "?"
            hardcoded = info.get("season_id_current")
            tag = ""
            if hardcoded is None:
                tag = " ← FALTA NO MAP"
            elif hardcoded != cur_id:
                tag = f" ← DIVERGE (map={hardcoded})"
            print(
                f"{info['name']:<35} | {af_id:>5} | {tid:>5} | "
                f"{cur_id:>14} | {cur_name}{tag}"
            )


if __name__ == "__main__":
    asyncio.run(main())
