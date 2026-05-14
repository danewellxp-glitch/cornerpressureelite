"""Repository de `incidents_history` — eventos Opta granulares (X/Y, flags).

`event_uid` é um sha1 dos campos discriminantes, garantindo dedupe quando o
WS reconecta e re-envia os mesmos eventos. UNIQUE em DB previne duplicação.
"""
from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass
from typing import Optional

log = logging.getLogger("cpes.repo.incidents")


@dataclass(frozen=True)
class IncidentHistoryEntry:
    fixture_id: Optional[int]
    opta_match_id: str
    event_uid: str
    event_type: int
    period_id: Optional[int]
    minute: Optional[int]
    seconds: Optional[int]
    team_id: Optional[str]
    player_id: Optional[str]
    x: Optional[float]
    y: Optional[float]
    x_end: Optional[float]
    y_end: Optional[float]
    is_attack: Optional[bool]
    is_dangerous_attack: Optional[bool]
    is_possession: Optional[bool]
    is_dangerous: Optional[bool]
    raw: Optional[dict] = None


def event_uid(
    opta_match_id: str,
    team_id: Optional[str],
    player_id: Optional[str],
    minute: int,
    seconds: int,
    event_type: int,
    x: Optional[float],
    y: Optional[float],
) -> str:
    """Hash determinístico (sha1, 24 chars) dos campos discriminantes."""
    parts = (
        f"{opta_match_id}|{team_id or ''}|{player_id or ''}|"
        f"{minute}|{seconds}|{event_type}|{(x or 0):.1f}|{(y or 0):.1f}"
    )
    return hashlib.sha1(parts.encode("utf-8")).hexdigest()[:24]


class IncidentsHistoryRepo:
    def __init__(self, pool):
        self._pool = pool

    async def bulk_insert(self, entries: list[IncidentHistoryEntry]) -> int:
        if not entries:
            return 0
        rows = [
            (
                e.fixture_id, e.opta_match_id, e.event_uid, e.event_type,
                e.period_id, e.minute, e.seconds,
                e.team_id, e.player_id,
                e.x, e.y, e.x_end, e.y_end,
                e.is_attack, e.is_dangerous_attack,
                e.is_possession, e.is_dangerous,
                json.dumps(e.raw or {}, ensure_ascii=False),
            )
            for e in entries
        ]
        async with self._pool.acquire() as conn:
            await conn.executemany(
                """
                INSERT INTO incidents_history
                  (fixture_id, opta_match_id, event_uid, event_type,
                   period_id, minute, seconds,
                   team_id, player_id,
                   x, y, x_end, y_end,
                   is_attack, is_dangerous_attack, is_possession, is_dangerous,
                   raw)
                VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16,$17,$18::jsonb)
                ON CONFLICT (opta_match_id, event_uid) DO NOTHING
                """,
                rows,
            )
        return len(rows)

    async def count_recent_dangerous_for_team(
        self, opta_match_id: str, team_id: str, minute: int, window_minutes: int = 10
    ) -> int:
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT COUNT(*) AS n FROM incidents_history
                 WHERE opta_match_id=$1
                   AND team_id=$2
                   AND is_dangerous_attack=TRUE
                   AND minute BETWEEN $3 AND $4
                """,
                opta_match_id, team_id, max(0, minute - window_minutes), minute,
            )
        return int(row["n"]) if row else 0
