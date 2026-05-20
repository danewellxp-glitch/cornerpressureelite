"""Fase H A1.3 — Repositorio do mapping af_sofa_fixture_map.

Source-of-truth: tabela af_sofa_fixture_map (PK fixture_id, NOT NULL sofa_event_id).
Cache in-process LRU pra evitar query em cada gravacao.

Uso tipico nos workers:

    sofa_id = await af_sofa_repo.get_sofa_id(fixture_id)
    if sofa_id is None and live_resolver:
        sofa_id = await live_resolver.resolve(canonical_fixture)
        if sofa_id is not None:
            await af_sofa_repo.upsert(fixture_id, sofa_id, mapped_via="realtime_live")
    # passar `sofa_id` (pode ser None) pra repo.insert(...) — dual-write
"""
from __future__ import annotations

import logging
from collections import OrderedDict
from typing import Optional

log = logging.getLogger("cpes.repo.af_sofa_map")

_CACHE_MAX = 2048


class AfSofaFixtureMapRepo:
    def __init__(self, pool):
        self._pool = pool
        self._cache: OrderedDict[int, Optional[int]] = OrderedDict()

    async def get_sofa_id(self, fixture_id: int) -> Optional[int]:
        """Lookup sofa_event_id pra fixture_id. Cache LRU 2048. Pode retornar None."""
        if fixture_id in self._cache:
            self._cache.move_to_end(fixture_id)
            return self._cache[fixture_id]
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT sofa_event_id FROM af_sofa_fixture_map WHERE fixture_id = $1",
                fixture_id,
            )
        sofa_id = int(row["sofa_event_id"]) if row else None
        self._cache[fixture_id] = sofa_id
        if len(self._cache) > _CACHE_MAX:
            self._cache.popitem(last=False)
        return sofa_id

    async def get_or_resolve(
        self,
        fixture_id: int,
        *,
        resolver=None,
        mapped_via: str = "realtime_live",
    ) -> Optional[int]:
        """Lookup no banco; se NULL, cai pro resolver live e persiste o mapping.

        É o passo descrito no docstring do módulo que faltava nos workers bridge
        (Fase H A1.3 fix): sem o fallback, fixtures que só passam pelo
        bridge_betano nunca entram no af_sofa_fixture_map e ficam com
        sofa_event_id NULL pra sempre (chicken-and-egg).
        """
        sofa_id = await self.get_sofa_id(fixture_id)
        if sofa_id is not None or resolver is None:
            return sofa_id
        try:
            sofa_id = await resolver.resolve_by_fixture_id(fixture_id)
        except Exception as e:
            log.debug("af_sofa_map.resolve_error fixture=%d err=%s", fixture_id, e)
            return None
        if sofa_id is not None:
            await self.upsert(fixture_id, sofa_id, mapped_via=mapped_via)
        return sofa_id

    async def upsert(
        self,
        fixture_id: int,
        sofa_event_id: int,
        *,
        confidence: float = 1.0,
        mapped_via: str = "realtime_live",
    ) -> None:
        async with self._pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO af_sofa_fixture_map
                  (fixture_id, sofa_event_id, confidence, mapped_via)
                VALUES ($1, $2, $3, $4)
                ON CONFLICT (fixture_id) DO UPDATE SET
                  sofa_event_id = EXCLUDED.sofa_event_id,
                  confidence = EXCLUDED.confidence,
                  mapped_via = EXCLUDED.mapped_via,
                  last_validated_at = NOW()
                """,
                fixture_id, sofa_event_id, confidence, mapped_via,
            )
        # update cache
        self._cache[fixture_id] = sofa_event_id
        self._cache.move_to_end(fixture_id)

    def invalidate(self, fixture_id: int) -> None:
        self._cache.pop(fixture_id, None)
