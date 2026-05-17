"""CachedBetanoOddsProvider — wrapper Betano-only com fallback pra cache stale.

Fase K — P4-B (2026-05-17). Substitui o `CompositeOddsProvider([bridge, af])`
do path runtime de odds. Decisão D4 aprovada: ZERO AF em odds. Sistema fica
silente em outage extremo (cache expirado + bridge down) — melhor silêncio
que sinal errado.

Fluxo:

    1. tenta BetanoBridgeOddsAdapter.get_<market>(...)
       - sucesso → cacheia + retorna (is_stale=False, age=0)
       - None/erro → vai pra (2)
    2. consulta OddsCache pra (fixture, market)
       - fresh (idade ≤ TTL) → retorna com is_stale=False, age=N
       - stale (TTL < idade ≤ 2×TTL) → retorna com is_stale=True (caller bloqueia emit)
       - expirado/ausente → retorna None (sinal bloqueado por ausência)

Implementa o `OddsProvider` Protocol (signature back-compat com adapter atual).
"""
from __future__ import annotations

import logging
from dataclasses import replace
from typing import Optional

from data.odds_provider import CanonicalFixture, CanonicalOverUnder
from data.providers.betano_bridge.odds_cache import OddsCache

log = logging.getLogger("cpes.providers.betano_bridge.cached")


class CachedBetanoOddsProvider:
    """Wrap BetanoBridgeOddsAdapter + OddsCache, sem AF."""

    name = "betano_bridge_cached"

    def __init__(self, adapter, cache: OddsCache):
        self._adapter = adapter
        self._cache = cache

    async def get_corners(
        self,
        fixture: CanonicalFixture,
        current_score: int,
        line: Optional[float] = None,
        *,
        minute: Optional[int] = None,
        pressure_score: Optional[float] = None,
        tension_score: Optional[float] = None,
        persist_telemetry: bool = False,
    ) -> Optional[CanonicalOverUnder]:
        return await self._fetch(
            "corners", fixture, current_score, line,
            minute=minute, pressure_score=pressure_score,
            tension_score=tension_score, persist_telemetry=persist_telemetry,
        )

    async def get_cards(
        self,
        fixture: CanonicalFixture,
        current_score: int,
        line: Optional[float] = None,
        *,
        minute: Optional[int] = None,
        pressure_score: Optional[float] = None,
        tension_score: Optional[float] = None,
        persist_telemetry: bool = False,
    ) -> Optional[CanonicalOverUnder]:
        return await self._fetch(
            "cards", fixture, current_score, line,
            minute=minute, pressure_score=pressure_score,
            tension_score=tension_score, persist_telemetry=persist_telemetry,
        )

    async def healthcheck(self) -> bool:
        return await self._adapter.healthcheck()

    async def _fetch(
        self,
        market_kind: str,
        fixture: CanonicalFixture,
        current_score: int,
        line: Optional[float],
        **ctx,
    ) -> Optional[CanonicalOverUnder]:
        method_name = f"get_{market_kind}"
        # 1. Tenta bridge fresh
        result = None
        try:
            result = await getattr(self._adapter, method_name)(
                fixture, current_score, line, **ctx
            )
        except Exception as e:
            log.warning(
                "cached.bridge_error fixture=%d market=%s err=%s",
                fixture.fixture_id, market_kind, e,
            )

        if result is not None:
            # cacheia (cache substitui entry anterior)
            self._cache.put(fixture.fixture_id, market_kind, result)
            return result

        # 2. bridge falhou — consulta cache
        cached = self._cache.get(fixture.fixture_id, market_kind)
        if cached is None:
            log.error(
                "cached.outage fixture=%d market=%s — bridge falhou + cache vazio/expirado, sinal bloqueado",
                fixture.fixture_id, market_kind,
            )
            return None

        payload = cached.payload
        if not isinstance(payload, CanonicalOverUnder):
            log.warning(
                "cached.unexpected_payload fixture=%d market=%s type=%s — descartando",
                fixture.fixture_id, market_kind, type(payload).__name__,
            )
            return None

        age = cached.age_seconds()
        is_stale = cached.is_stale()
        source = "betano_cache_stale" if is_stale else "betano_cache"
        if is_stale:
            log.warning(
                "cached.serving_stale fixture=%d market=%s age=%ds",
                fixture.fixture_id, market_kind, age,
            )
        # Retorna copy do CanonicalOverUnder com source/stale/age atualizados.
        return replace(payload, source=source, is_stale=is_stale, age_seconds=age)
