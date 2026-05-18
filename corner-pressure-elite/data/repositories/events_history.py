"""Repository de `events_history` — eventos granulares por fixture (Fase F).

Persiste `CanonicalEvent` vindos de `BetanoEventsWorker` (capturado via
bridge Betano `event.incidents[]` ou AF fallback).

Dedup via UNIQUE constraint `(fixture_id, source, event_type, event_minute,
team_side, player_name)`. Mesmo evento em polls subsequentes vira no-op
(INSERT … ON CONFLICT DO NOTHING).
"""
from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING, Optional

log = logging.getLogger("cpes.repo.events_history")

if TYPE_CHECKING:
    from data.events_provider import CanonicalEvent


class EventsHistoryRepo:
    def __init__(self, pool):
        self._pool = pool

    async def upsert_event(
        self,
        event: "CanonicalEvent",
        sofa_event_id: Optional[int] = None,
    ) -> bool:
        """INSERT idempotente (dedup UNIQUE). Returns True se inseriu, False se duplicate.

        sofa_event_id (Fase H A1.3): dual-write. None = unresolved.
        """
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO events_history
                  (fixture_id, source, event_type, event_minute, event_second,
                   team_side, player_name, props, raw, sofa_event_id)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8::jsonb, $9::jsonb, $10)
                ON CONFLICT (fixture_id, source, event_type, event_minute, team_side, player_name)
                  DO NOTHING
                RETURNING id
                """,
                event.fixture_id, event.source, event.event_type,
                event.event_minute, event.event_second,
                event.team_side, event.player_name,
                json.dumps(event.props or {}, ensure_ascii=False),
                json.dumps(event.raw or {}, ensure_ascii=False),
                sofa_event_id,
            )
        return row is not None

    async def upsert_batch(
        self,
        events: list["CanonicalEvent"],
        sofa_event_id: Optional[int] = None,
    ) -> tuple[int, int]:
        """Bulk upsert. Returns (inserted, skipped_duplicates).

        Usa executemany pra eficiência (1 round-trip por batch). RETURNING id
        funciona com ON CONFLICT DO NOTHING — None nos pulos. Mas executemany
        não devolve rows facilmente; fazemos um loop com fetchrow pra contar
        com precisão.

        sofa_event_id (Fase H A1.3): mesmo valor aplicado a todos os eventos
        do batch (todos pertencem ao mesmo fixture). COALESCE preserva valor
        existente em duplicates pra nao sobrescrever com NULL.
        """
        if not events:
            return 0, 0
        inserted = 0
        async with self._pool.acquire() as conn:
            async with conn.transaction():
                for e in events:
                    row = await conn.fetchrow(
                        """
                        INSERT INTO events_history
                          (fixture_id, source, event_type, event_minute, event_second,
                           team_side, player_name, props, raw, sofa_event_id)
                        VALUES ($1, $2, $3, $4, $5, $6, $7, $8::jsonb, $9::jsonb, $10)
                        ON CONFLICT (fixture_id, source, event_type, event_minute, team_side, player_name)
                          DO NOTHING
                        RETURNING id
                        """,
                        e.fixture_id, e.source, e.event_type,
                        e.event_minute, e.event_second,
                        e.team_side, e.player_name,
                        json.dumps(e.props or {}, ensure_ascii=False),
                        json.dumps(e.raw or {}, ensure_ascii=False),
                        sofa_event_id,
                    )
                    if row is not None:
                        inserted += 1
        return inserted, len(events) - inserted

    async def get_recent_by_fixture(
        self, fixture_id: int, limit: int = 50
    ) -> list[dict]:
        """Eventos do fixture ordenados por event_minute ASC (cronológico)."""
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT id, fixture_id, source, event_type, event_minute,
                       event_second, team_side, player_name, props, raw,
                       captured_at
                  FROM events_history
                 WHERE fixture_id = $1
                 ORDER BY event_minute ASC, event_second ASC NULLS FIRST, id ASC
                 LIMIT $2
                """,
                fixture_id, limit,
            )
        return [dict(r) for r in rows]

    async def get_by_type_in_window(
        self, fixture_id: int, event_type: str, since_minute: int
    ) -> list[dict]:
        """Eventos de 1 tipo dentro de [since_minute, ∞), ordenado por minute ASC."""
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT id, fixture_id, source, event_type, event_minute,
                       event_second, team_side, player_name, props, raw,
                       captured_at
                  FROM events_history
                 WHERE fixture_id = $1
                   AND event_type = $2
                   AND event_minute >= $3
                 ORDER BY event_minute ASC, event_second ASC NULLS FIRST, id ASC
                """,
                fixture_id, event_type, since_minute,
            )
        return [dict(r) for r in rows]
