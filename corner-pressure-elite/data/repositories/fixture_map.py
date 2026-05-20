"""Repository de `betano_fixture_map` — mapping fixture_id ↔ event_id."""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional

log = logging.getLogger("cpes.repo.fixture_map")


class FixtureMapRepo:
    def __init__(self, pool):
        self._pool = pool

    async def get_betano_event_id(self, fixture_id: int) -> Optional[int]:
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT betano_event_id FROM betano_fixture_map WHERE fixture_id=$1",
                fixture_id,
            )
        return int(row["betano_event_id"]) if row else None

    async def get_by_fixture_id(self, fixture_id: int) -> Optional[dict]:
        """Linha completa do mapping (names canônicos Betano + kickoff + liga).

        Usado pelo SofaScoreEventResolver pra resolver `sofa_event_id` a partir
        só de `fixture_id` (workers bridge/AF que não têm CanonicalFixture). Sem
        este método o resolver caía no `except` e perdia os names canônicos.
        """
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT fixture_id, betano_event_id, home_team, away_team, "
                "league_id, kickoff_utc FROM betano_fixture_map WHERE fixture_id=$1",
                fixture_id,
            )
        return dict(row) if row else None

    async def upsert(
        self,
        fixture_id: int,
        betano_event_id: int,
        sr_match_id: Optional[str] = None,
        opta_match_id: Optional[str] = None,
        home_team: Optional[str] = None,
        away_team: Optional[str] = None,
        league_id: Optional[int] = None,
        kickoff_utc: Optional[datetime] = None,
        resolved_via: str = "fuzzy_match",
    ) -> None:
        async with self._pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO betano_fixture_map
                  (fixture_id, betano_event_id, sr_match_id, opta_match_id,
                   home_team, away_team, league_id, kickoff_utc, resolved_via)
                VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9)
                ON CONFLICT (fixture_id) DO UPDATE
                  SET betano_event_id = EXCLUDED.betano_event_id,
                      sr_match_id     = COALESCE(EXCLUDED.sr_match_id,
                                                  betano_fixture_map.sr_match_id),
                      opta_match_id   = COALESCE(EXCLUDED.opta_match_id,
                                                  betano_fixture_map.opta_match_id),
                      home_team       = COALESCE(EXCLUDED.home_team,
                                                  betano_fixture_map.home_team),
                      away_team       = COALESCE(EXCLUDED.away_team,
                                                  betano_fixture_map.away_team),
                      league_id       = COALESCE(EXCLUDED.league_id,
                                                  betano_fixture_map.league_id),
                      kickoff_utc     = COALESCE(EXCLUDED.kickoff_utc,
                                                  betano_fixture_map.kickoff_utc),
                      resolved_via    = EXCLUDED.resolved_via,
                      resolved_at     = NOW();
                """,
                fixture_id, betano_event_id, sr_match_id, opta_match_id,
                home_team, away_team, league_id, kickoff_utc, resolved_via,
            )

    async def list_recent(self, limit: int = 100) -> list[dict]:
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT * FROM betano_fixture_map ORDER BY resolved_at DESC LIMIT $1",
                limit,
            )
        return [dict(r) for r in rows]
