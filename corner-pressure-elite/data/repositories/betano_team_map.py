"""Repository de `betano_team_map` — mapping team_id Betano ↔ API-Football.

Populado pelo BetanoFixtureDiscovery worker (Fase D.2):
- catálogo estático (todos os teams da Betano, on-demand, api_football_team_id pode ser NULL)
- matches resolvidos (fuzzy ou manual) com api_football_team_id preenchido + match_confidence
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional, Sequence

log = logging.getLogger("cpes.repo.betano_team_map")


@dataclass(frozen=True)
class BetanoTeamEntry:
    betano_team_id: int
    betano_team_name: str
    api_football_team_id: Optional[int] = None
    api_football_team_name: Optional[str] = None
    match_method: Optional[str] = None        # 'static_catalog' | 'fuzzy' | 'manual'
    match_confidence: Optional[float] = None  # 0.00 a 1.00


class BetanoTeamMapRepo:
    def __init__(self, pool):
        self._pool = pool

    async def get_by_betano_id(self, betano_team_id: int) -> Optional[BetanoTeamEntry]:
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT betano_team_id, betano_team_name,
                       api_football_team_id, api_football_team_name,
                       match_method, match_confidence
                FROM betano_team_map
                WHERE betano_team_id = $1
                """,
                int(betano_team_id),
            )
        if not row:
            return None
        return BetanoTeamEntry(
            betano_team_id=int(row["betano_team_id"]),
            betano_team_name=row["betano_team_name"],
            api_football_team_id=row["api_football_team_id"],
            api_football_team_name=row["api_football_team_name"],
            match_method=row["match_method"],
            match_confidence=float(row["match_confidence"]) if row["match_confidence"] is not None else None,
        )

    async def get_by_api_football_id(self, api_football_team_id: int) -> Optional[BetanoTeamEntry]:
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT betano_team_id, betano_team_name,
                       api_football_team_id, api_football_team_name,
                       match_method, match_confidence
                FROM betano_team_map
                WHERE api_football_team_id = $1
                """,
                int(api_football_team_id),
            )
        if not row:
            return None
        return BetanoTeamEntry(
            betano_team_id=int(row["betano_team_id"]),
            betano_team_name=row["betano_team_name"],
            api_football_team_id=row["api_football_team_id"],
            api_football_team_name=row["api_football_team_name"],
            match_method=row["match_method"],
            match_confidence=float(row["match_confidence"]) if row["match_confidence"] is not None else None,
        )

    async def bulk_upsert(self, entries: Sequence[BetanoTeamEntry]) -> int:
        """UPSERT em batch. Retorna número de linhas processadas.

        Conflito por betano_team_id; preenche api_football_* só se não-NULL
        no input (não sobrescreve match resolvido com NULL do catálogo).
        """
        if not entries:
            return 0
        rows = [
            (
                e.betano_team_id,
                e.betano_team_name,
                e.api_football_team_id,
                e.api_football_team_name,
                e.match_method,
                e.match_confidence,
            )
            for e in entries
        ]
        async with self._pool.acquire() as conn:
            await conn.executemany(
                """
                INSERT INTO betano_team_map
                  (betano_team_id, betano_team_name,
                   api_football_team_id, api_football_team_name,
                   match_method, match_confidence)
                VALUES ($1,$2,$3,$4,$5,$6)
                ON CONFLICT (betano_team_id) DO UPDATE
                  SET betano_team_name       = EXCLUDED.betano_team_name,
                      api_football_team_id   = COALESCE(EXCLUDED.api_football_team_id,
                                                        betano_team_map.api_football_team_id),
                      api_football_team_name = COALESCE(EXCLUDED.api_football_team_name,
                                                        betano_team_map.api_football_team_name),
                      match_method           = COALESCE(EXCLUDED.match_method,
                                                        betano_team_map.match_method),
                      match_confidence       = COALESCE(EXCLUDED.match_confidence,
                                                        betano_team_map.match_confidence),
                      updated_at             = NOW();
                """,
                rows,
            )
        return len(rows)

    async def find_by_fuzzy_name(
        self,
        name: str,
        threshold: float = 0.85,
        limit: int = 3,
    ) -> list[tuple[BetanoTeamEntry, float]]:
        """Busca top N teams Betano cujo nome é similar a `name` (pg_trgm).

        Usado pra detecção de duplicatas / lookup reverso (Betano → Betano).
        O matching cross-source (Betano ↔ API-Football) acontece em
        FixtureMatcher usando rapidfuzz (carregando dataset menor em memória).
        """
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT betano_team_id, betano_team_name,
                       api_football_team_id, api_football_team_name,
                       match_method, match_confidence,
                       similarity(betano_team_name, $1) AS sim
                FROM betano_team_map
                WHERE similarity(betano_team_name, $1) >= $2
                ORDER BY sim DESC
                LIMIT $3
                """,
                name, float(threshold), int(limit),
            )
        return [
            (
                BetanoTeamEntry(
                    betano_team_id=int(r["betano_team_id"]),
                    betano_team_name=r["betano_team_name"],
                    api_football_team_id=r["api_football_team_id"],
                    api_football_team_name=r["api_football_team_name"],
                    match_method=r["match_method"],
                    match_confidence=float(r["match_confidence"]) if r["match_confidence"] is not None else None,
                ),
                float(r["sim"]),
            )
            for r in rows
        ]
