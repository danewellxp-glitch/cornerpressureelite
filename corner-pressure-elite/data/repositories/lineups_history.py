"""Repository de `lineups_history` — snapshots de lineups por fixture (Fase G.1).

Persiste `CanonicalLineup` (1 por team_side, ou seja 2 por fixture) vindos
do `BetanoLineupsWorker`. Dedup via UNIQUE `(fixture_id, source, team_side)`
— worker chama 1 vez (early-game) e UNIQUE absorve duplicatas em race.

Cache `exists_for_fixture` ajuda worker pular re-fetch antes de chamar
`upsert_batch` (econômico em CPU/IO).
"""
from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING, Optional

log = logging.getLogger("cpes.repo.lineups_history")

if TYPE_CHECKING:
    from data.lineups_provider import CanonicalLineup


def _serialize_players(players: list) -> str:
    """list[PlayerEntry] → JSONB string."""
    return json.dumps(
        [
            {
                "player_id": p.player_id,
                "name": p.name,
                "position": p.position,
                "position_display": p.position_display,
                "shirt_number": p.shirt_number,
                "is_substitute": p.is_substitute,
            }
            for p in (players or [])
        ],
        ensure_ascii=False,
    )


def _serialize_missing(missing: list) -> str:
    """list[MissingPlayer] → JSONB string. K.1 PARTE B.6."""
    return json.dumps(
        [
            {
                "player_id": m.player_id,
                "name": m.name,
                "reason": m.reason,
                "reason_code": m.reason_code,
                "expected_return": m.expected_return.isoformat() if m.expected_return else None,
                "source": m.source,
            }
            for m in (missing or [])
        ],
        ensure_ascii=False,
    )


class LineupsHistoryRepo:
    def __init__(self, pool):
        self._pool = pool

    async def upsert_lineup(self, lineup: "CanonicalLineup") -> bool:
        """INSERT idempotente. Returns True se inseriu, False se duplicate."""
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO lineups_history
                  (fixture_id, source, team_side, formation, coach_name,
                   starting_eleven, substitutes, tactical_grid,
                   version, raw, missing_players)
                VALUES ($1, $2, $3, $4, $5,
                        $6::jsonb, $7::jsonb, $8::jsonb,
                        $9, $10::jsonb, $11::jsonb)
                ON CONFLICT (fixture_id, source, team_side) DO NOTHING
                RETURNING id
                """,
                lineup.fixture_id,
                lineup.source,
                lineup.team_side,
                lineup.formation,
                lineup.coach_name,
                _serialize_players(lineup.starting_eleven),
                _serialize_players(lineup.substitutes),
                json.dumps(lineup.tactical_grid or [], ensure_ascii=False),
                lineup.version,
                json.dumps(lineup.raw or {}, ensure_ascii=False),
                _serialize_missing(lineup.missing_players),
            )
        return row is not None

    async def upsert_batch(
        self, lineups: list["CanonicalLineup"]
    ) -> tuple[int, int]:
        """Bulk upsert. Returns (inserted, skipped_duplicates)."""
        if not lineups:
            return 0, 0
        inserted = 0
        async with self._pool.acquire() as conn:
            async with conn.transaction():
                for ln in lineups:
                    row = await conn.fetchrow(
                        """
                        INSERT INTO lineups_history
                          (fixture_id, source, team_side, formation, coach_name,
                           starting_eleven, substitutes, tactical_grid,
                           version, raw, missing_players)
                        VALUES ($1, $2, $3, $4, $5,
                                $6::jsonb, $7::jsonb, $8::jsonb,
                                $9, $10::jsonb, $11::jsonb)
                        ON CONFLICT (fixture_id, source, team_side) DO NOTHING
                        RETURNING id
                        """,
                        ln.fixture_id, ln.source, ln.team_side,
                        ln.formation, ln.coach_name,
                        _serialize_players(ln.starting_eleven),
                        _serialize_players(ln.substitutes),
                        json.dumps(ln.tactical_grid or [], ensure_ascii=False),
                        ln.version,
                        json.dumps(ln.raw or {}, ensure_ascii=False),
                        _serialize_missing(ln.missing_players),
                    )
                    if row is not None:
                        inserted += 1
        return inserted, len(lineups) - inserted

    async def get_by_fixture(self, fixture_id: int) -> list[dict]:
        """Lineups do fixture (até 2 por source: home + away)."""
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT id, fixture_id, source, team_side, formation, coach_name,
                       starting_eleven, substitutes, tactical_grid,
                       version, captured_at, raw, missing_players
                  FROM lineups_history
                 WHERE fixture_id = $1
                 ORDER BY source ASC, team_side ASC
                """,
                fixture_id,
            )
        return [dict(r) for r in rows]

    async def exists_for_fixture(self, fixture_id: int) -> bool:
        """True se já existe pelo menos 1 lineup persistida pro fixture.

        Worker usa como short-circuit pra evitar re-fetch entre restarts
        (cache in-memory perde estado, banco persiste).
        """
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT 1 FROM lineups_history WHERE fixture_id = $1 LIMIT 1",
                fixture_id,
            )
        return row is not None
