"""Repository de `stats_history` — snapshots granulares de stats por fixture.

Usado por:
- `workers.betano_stats_worker.BetanoStatsWorker` — `insert` a cada poll OK.
- `data.services.stats_window_calculator.StatsWindowCalculator` —
  `list_recent_for_fixture(since=...)` pra reconstruir janelas corners/yellow.

Persistência é idempotente em relação à `version` do bridge (UNIQUE index
parcial em `(fixture_id, source, version) WHERE version IS NOT NULL`). Race
de duplicar mesma version vira `UniqueViolationError` — caller trata como
no-op.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

log = logging.getLogger("cpes.repo.stats_history")


@dataclass(frozen=True)
class StatsHistoryEntry:
    fixture_id: int
    source: str                  # 'bridge_betano' | 'apifootball'
    minute: Optional[int] = None
    second_since_start: Optional[int] = None
    score_home: Optional[int] = None
    score_away: Optional[int] = None
    corners_home: Optional[int] = None
    corners_away: Optional[int] = None
    yellow_cards_home: Optional[int] = None
    yellow_cards_away: Optional[int] = None
    red_cards_home: int = 0
    red_cards_away: int = 0
    shots_on_target_home: int = 0
    shots_on_target_away: int = 0
    dangerous_attacks_home: int = 0
    dangerous_attacks_away: int = 0
    possession_home: int = 0
    possession_away: int = 0
    x_goals_home: float = 0.0
    x_goals_away: float = 0.0
    version: Optional[int] = None
    provider_pressure: Optional[float] = None
    corners_last_5min: Optional[int] = None
    corners_last_10min: Optional[int] = None
    yellow_last_5min: Optional[int] = None
    yellow_last_10min: Optional[int] = None
    captured_at: Optional[datetime] = None
    raw: Optional[dict] = None
    # K.1 PARTE B.7: lista de providers que enriqueceram o snapshot.
    enriched_by: Optional[list[str]] = None
    # Fase H A1.3: dual-write sofa_event_id (None = unresolved)
    sofa_event_id: Optional[int] = None


class StatsHistoryRepo:
    def __init__(self, pool):
        self._pool = pool

    async def insert(self, entry: StatsHistoryEntry) -> Optional[int]:
        """INSERT idempotente (em version) — retorna `id` ou `None` se duplicate."""
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO stats_history
                  (fixture_id, source,
                   minute, second_since_start,
                   score_home, score_away,
                   corners_home, corners_away,
                   yellow_cards_home, yellow_cards_away,
                   red_cards_home, red_cards_away,
                   shots_on_target_home, shots_on_target_away,
                   dangerous_attacks_home, dangerous_attacks_away,
                   possession_home, possession_away,
                   x_goals_home, x_goals_away,
                   version, provider_pressure,
                   corners_last_5min, corners_last_10min,
                   yellow_last_5min, yellow_last_10min,
                   captured_at, raw, enriched_by, sofa_event_id)
                VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,
                        $13,$14,$15,$16,$17,$18,$19,$20,$21,$22,
                        $23,$24,$25,$26,
                        COALESCE($27, NOW()), $28::jsonb, $29::jsonb, $30)
                ON CONFLICT (fixture_id, source, version)
                  WHERE version IS NOT NULL
                  DO NOTHING
                RETURNING id
                """,
                entry.fixture_id, entry.source,
                entry.minute, entry.second_since_start,
                entry.score_home, entry.score_away,
                entry.corners_home, entry.corners_away,
                entry.yellow_cards_home, entry.yellow_cards_away,
                entry.red_cards_home, entry.red_cards_away,
                entry.shots_on_target_home, entry.shots_on_target_away,
                entry.dangerous_attacks_home, entry.dangerous_attacks_away,
                entry.possession_home, entry.possession_away,
                entry.x_goals_home, entry.x_goals_away,
                entry.version, entry.provider_pressure,
                entry.corners_last_5min, entry.corners_last_10min,
                entry.yellow_last_5min, entry.yellow_last_10min,
                entry.captured_at,
                json.dumps(entry.raw or {}, ensure_ascii=False),
                json.dumps(entry.enriched_by) if entry.enriched_by else None,
                entry.sofa_event_id,
            )
        return int(row["id"]) if row else None

    async def list_recent_for_fixture(
        self,
        fixture_id: int,
        since: Optional[datetime] = None,
        limit: int = 200,
    ) -> list[dict]:
        """Snapshots recentes de 1 fixture, ordem cronológica DESC.

        `since` filtra captured_at >= since. Default sem filtro (últimos `limit`).
        Usado pelo StatsWindowCalculator pra reconstruir janelas 5/10min.
        """
        async with self._pool.acquire() as conn:
            if since is None:
                rows = await conn.fetch(
                    """
                    SELECT * FROM stats_history
                     WHERE fixture_id = $1
                     ORDER BY captured_at DESC
                     LIMIT $2
                    """,
                    fixture_id, limit,
                )
            else:
                rows = await conn.fetch(
                    """
                    SELECT * FROM stats_history
                     WHERE fixture_id = $1 AND captured_at >= $2
                     ORDER BY captured_at DESC
                     LIMIT $3
                    """,
                    fixture_id, since, limit,
                )
        return [dict(r) for r in rows]

    async def latest_version_for_fixture(
        self, fixture_id: int, source: str
    ) -> Optional[int]:
        """Max version persistida pra (fixture, source). Útil pra restart do worker."""
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT MAX(version) AS v FROM stats_history
                 WHERE fixture_id = $1 AND source = $2
                """,
                fixture_id, source,
            )
        return int(row["v"]) if row and row["v"] is not None else None
