"""Popula betano_team_map cruzando AF /teams + fuzzy match contra betano_team_name.

Estratégia (PRIORIDADE 2, sessão 2026-05-17):

Pra cada liga AF alvo:
1. GET /teams?league=X&season=Y → ~20 times AF oficiais
2. Pra cada time AF, fuzzy match contra TODOS times Betano sem `api_football_team_id`
   (excluindo Esports/virtuais)
3. Resolver conflitos: se 2 AF apontam pro mesmo Betano, mantém maior confidence
4. Output:
   - /tmp/team_map_proposed.json — pra review
   - /tmp/team_map_updates.sql — pra apply (UPDATE ON CONFLICT)
5. Apply manual: `psql ... < /tmp/team_map_updates.sql` (após review)

Schema real (betano_team_map):
    betano_team_id (PK) | betano_team_name | api_football_team_id (nullable)
    | api_football_team_name | match_method | match_confidence | resolved_at | updated_at

Esse script só faz UPDATE de rows existentes (não INSERT) — popular os 423 sem AF
que vieram via `match_method='static_catalog'` do Danae.

Run dentro do container: `docker exec cpes-main python data/scripts/populate_team_map.py`
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import unicodedata
from dataclasses import dataclass, asdict
from typing import Optional

from rapidfuzz import fuzz

from data.api_client import APIFootballClient
from utils.rate_limiter import RateLimiter
from storage.database import Database

log = logging.getLogger("populate_team_map")
logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")

# Ligas alvo: (af_league_id, season_year, name_pt)
TARGET_LEAGUES: list[tuple[int, int, str]] = [
    (39,  2025, "Premier League"),
    (140, 2025, "La Liga"),
    (135, 2025, "Serie A Italia"),
    (78,  2025, "Bundesliga"),
    (61,  2025, "Ligue 1"),
    (88,  2025, "Eredivisie"),
    (94,  2025, "Liga Portugal"),
    (2,   2025, "Champions League"),
    (3,   2025, "Europa League"),
    (253, 2025, "MLS"),
    (128, 2026, "Liga Argentina"),
    (72,  2026, "Brasileirão B"),
    (13,  2026, "Copa Libertadores"),
    (11,  2026, "Copa Sul-Americana"),
]

CONFIDENCE_AUTO = 0.90  # ≥ vira approved automaticamente
CONFIDENCE_REVIEW = 0.75  # entre 0.75 e 0.90 → review manual; < 0.75 descarta


def _norm(name: str) -> str:
    """Lowercase + sem acentos + sem sufixos comuns (FC, SC, CF, AC, ...)."""
    s = unicodedata.normalize("NFKD", name).encode("ASCII", "ignore").decode().lower()
    for suffix in (" fc", " sc", " cf", " ac", " ec", " af", " ud", " cd", " ca"):
        if s.endswith(suffix):
            s = s[: -len(suffix)]
    return s.strip()


def fuzzy_score(a: str, b: str) -> float:
    """Combinação rapidfuzz: ratio + token_sort + partial → max."""
    na, nb = _norm(a), _norm(b)
    return max(
        fuzz.ratio(na, nb),
        fuzz.token_sort_ratio(na, nb),
        fuzz.partial_ratio(na, nb),
    ) / 100.0


@dataclass
class Proposal:
    betano_team_id: int
    betano_team_name: str
    af_team_id: int
    af_team_name: str
    af_league_id: int
    af_league_name: str
    confidence: float
    needs_review: bool


async def fetch_betano_unmapped(db: Database) -> list[tuple[int, str]]:
    """Retorna times Betano sem AF (excluindo Esports/Snow/Dexter)."""
    query = """
        SELECT betano_team_id, betano_team_name
        FROM betano_team_map
        WHERE api_football_team_id IS NULL
          AND betano_team_name NOT LIKE '%Esports%'
          AND betano_team_name NOT LIKE '%(Snow)%'
          AND betano_team_name NOT LIKE '%(Dexter)%'
          AND betano_team_name NOT LIKE '%Sub-%'
    """
    async with db.pool.acquire() as conn:
        rows = await conn.fetch(query)
    return [(r["betano_team_id"], r["betano_team_name"]) for r in rows]


async def fetch_af_teams(
    client: APIFootballClient, league_id: int, season: int
) -> list[tuple[int, str]]:
    """Retorna lista (af_team_id, af_team_name) pra uma liga/season."""
    r = await client._request("teams", params={"league": league_id, "season": season})
    return [(t["team"]["id"], t["team"]["name"]) for t in r.get("response", [])]


async def main():
    db = Database()
    await db.connect()
    rl = RateLimiter(max_requests_per_day=7500, max_requests_per_minute=30)
    client = APIFootballClient(os.getenv("API_FOOTBALL_KEY"), rl)

    betano_unmapped = await fetch_betano_unmapped(db)
    log.info("betano_unmapped: %d times sem AF", len(betano_unmapped))

    # best_for_betano: betano_team_id → Proposal (mantém maior confidence)
    best_for_betano: dict[int, Proposal] = {}

    for af_league_id, season, league_name in TARGET_LEAGUES:
        log.info("--- Liga %s (af_id=%d season=%d) ---", league_name, af_league_id, season)
        try:
            af_teams = await fetch_af_teams(client, af_league_id, season)
        except Exception as e:
            log.warning("Liga %d falhou: %s", af_league_id, e)
            continue
        log.info("  %d times AF", len(af_teams))

        league_matches = 0
        for af_id, af_name in af_teams:
            best_score = 0.0
            best_betano = None
            for bt_id, bt_name in betano_unmapped:
                s = fuzzy_score(af_name, bt_name)
                if s > best_score:
                    best_score = s
                    best_betano = (bt_id, bt_name)

            if best_betano is None or best_score < CONFIDENCE_REVIEW:
                continue
            bt_id, bt_name = best_betano

            existing = best_for_betano.get(bt_id)
            if existing and existing.confidence >= best_score:
                continue  # já tem match melhor

            best_for_betano[bt_id] = Proposal(
                betano_team_id=bt_id,
                betano_team_name=bt_name,
                af_team_id=af_id,
                af_team_name=af_name,
                af_league_id=af_league_id,
                af_league_name=league_name,
                confidence=round(best_score, 3),
                needs_review=best_score < CONFIDENCE_AUTO,
            )
            league_matches += 1
            status = "✓" if best_score >= CONFIDENCE_AUTO else "⚠"
            log.info("  %s %-30s → %-30s (%.2f)", status, af_name[:30], bt_name[:30], best_score)
        log.info("  → %d matches nesta liga", league_matches)

    proposals = list(best_for_betano.values())
    auto_ok = [p for p in proposals if not p.needs_review]
    review = [p for p in proposals if p.needs_review]

    out_json = "/tmp/team_map_proposed.json"
    with open(out_json, "w") as f:
        json.dump([asdict(p) for p in proposals], f, indent=2, ensure_ascii=False)

    # SQL só pros auto-OK (≥0.90)
    out_sql = "/tmp/team_map_updates.sql"
    with open(out_sql, "w") as f:
        f.write("-- UPDATE betano_team_map: auto-aprovados ≥0.90 confidence\n")
        f.write(f"-- Gerado: {len(auto_ok)} updates\n\n")
        for p in auto_ok:
            af_name_esc = p.af_team_name.replace("'", "''")
            f.write(
                f"UPDATE betano_team_map SET "
                f"api_football_team_id = {p.af_team_id}, "
                f"api_football_team_name = '{af_name_esc}', "
                f"match_method = 'af_league_fuzzy', "
                f"match_confidence = {p.confidence}, "
                f"updated_at = NOW() "
                f"WHERE betano_team_id = {p.betano_team_id} AND api_football_team_id IS NULL;\n"
            )

    print(f"\n=== RESUMO ===")
    print(f"Total proposals: {len(proposals)}")
    print(f"  Auto-OK (≥{CONFIDENCE_AUTO}):    {len(auto_ok)}")
    print(f"  Review needed [{CONFIDENCE_REVIEW},{CONFIDENCE_AUTO}): {len(review)}")
    print(f"\nFiles:")
    print(f"  {out_json}  — todos proposals (revisar)")
    print(f"  {out_sql}   — UPDATEs prontos pra apply")

    await client.close()
    await db.close()


if __name__ == "__main__":
    asyncio.run(main())
