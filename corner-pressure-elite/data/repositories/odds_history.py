"""Repository de `odds_history` — granularidade total das odds capturadas."""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

log = logging.getLogger("cpes.repo.odds_history")


@dataclass(frozen=True)
class OddsHistoryEntry:
    fixture_id: int
    source: str
    market_kind: str
    market_code: Optional[str]
    linha: Optional[float]
    odd_over: Optional[float]
    odd_under: Optional[float]
    minute: Optional[int] = None
    score_home: Optional[int] = None
    score_away: Optional[int] = None
    pressure_score: Optional[float] = None
    tension_score: Optional[float] = None
    provider_pressure: Optional[float] = None
    # None -> banco usa DEFAULT NOW(). enqueue_catalog seta um valor único
    # pras N linhas de uma captura compartilharem timestamp idêntico.
    captured_at: Optional[datetime] = None
    raw: Optional[dict] = None


class OddsHistoryRepo:
    def __init__(self, pool):
        self._pool = pool

    async def bulk_insert(self, entries: list[OddsHistoryEntry]) -> int:
        if not entries:
            return 0
        rows = [
            (
                e.fixture_id, e.source, e.market_kind, e.market_code,
                e.linha, e.odd_over, e.odd_under,
                e.minute, e.score_home, e.score_away,
                e.pressure_score, e.tension_score, e.provider_pressure,
                e.captured_at,
                json.dumps(e.raw or {}, ensure_ascii=False),
            )
            for e in entries
        ]
        async with self._pool.acquire() as conn:
            await conn.executemany(
                """
                INSERT INTO odds_history
                  (fixture_id, source, market_kind, market_code,
                   linha, odd_over, odd_under,
                   minute, score_home, score_away,
                   pressure_score, tension_score, provider_pressure,
                   captured_at, raw)
                VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,
                        COALESCE($14, NOW()), $15::jsonb)
                """,
                rows,
            )
        return len(rows)

    async def list_recent_for_fixture(
        self, fixture_id: int, market_kind: str, limit: int = 50
    ) -> list[dict]:
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT * FROM odds_history
                 WHERE fixture_id=$1 AND market_kind=$2
                 ORDER BY captured_at DESC
                 LIMIT $3
                """,
                fixture_id, market_kind, limit,
            )
        return [dict(r) for r in rows]
