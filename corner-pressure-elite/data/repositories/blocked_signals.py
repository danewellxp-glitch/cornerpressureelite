"""Repository de blocked_signals (Fase K — P5, 2026-05-17).

Persiste sinais que o refetch just-before-send abortou. Permite análise:
- Quantos sinais bloqueados por dia?
- Qual razão mais comum (refetch_none, odd_drift, line_changed, etc.)?
- Estimativa esperada: 5-15% dos sinais (final de jogo + odds voando).
"""
from __future__ import annotations

import json
import logging
from typing import Optional

log = logging.getLogger("cpes.repo.blocked_signals")


class BlockedSignalsRepo:
    def __init__(self, pool):
        self._pool = pool

    async def insert(
        self,
        *,
        fixture_id: int,
        market_kind: str,
        linha: Optional[float],
        reason: str,
        orig_odd: Optional[float],
        fresh_odd: Optional[float],
        drift_pct: Optional[float],
        metadata: Optional[dict] = None,
    ) -> None:
        async with self._pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO blocked_signals
                  (fixture_id, market_kind, linha, reason,
                   orig_odd, fresh_odd, drift_pct, metadata)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8::jsonb)
                """,
                fixture_id, market_kind, linha, reason,
                orig_odd, fresh_odd, drift_pct,
                json.dumps(metadata or {}, ensure_ascii=False),
            )
