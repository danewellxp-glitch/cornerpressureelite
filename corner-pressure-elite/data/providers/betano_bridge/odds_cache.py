"""Cache local de odds Betano com TTL adaptativo por mercado (P4-B, 2026-05-17).

Substitui o fallback AF na pipeline de odds: quando bridge falha, retornamos
cache se ainda fresh, ou cache marcado como stale se expirado (TTL excedido
mas dentro de 2× TTL).

Cache stale é entregue ao caller (CompositeOddsProvider), gravado em
`odds_history` com `is_stale=true`, MAS bloqueado no momento de emit do sinal
(decision_engine não envia WhatsApp com odds stale).

Decisão D1: TTL por mercado, calibrado pra estabilidade (cards/corners variam
mais devagar que match_winner ao vivo).
"""
from __future__ import annotations

import time
from collections import defaultdict
from dataclasses import dataclass
from typing import Optional


# TTL adaptativo (segundos) — decisão D1 aprovada 2026-05-17.
# Após TTL: cache vira "stale" (entrega mas marca).
# Após 2× TTL: cache "expira" (remove + retorna None).
TTL_BY_MARKET: dict[str, int] = {
    "corners": 30,
    "cards": 30,
    "goals": 20,
    "over_under_goals": 20,
    "both_teams_score": 20,
    "match_winner": 15,
    "half_time": 15,
}
TTL_DEFAULT = 20


def ttl_for(market_kind: str) -> int:
    return TTL_BY_MARKET.get(market_kind, TTL_DEFAULT)


@dataclass
class CachedOdds:
    fixture_id: int
    market_kind: str
    payload: object  # CanonicalOverUnder ou dict — opaque pra cache
    captured_at: float

    def age_seconds(self) -> int:
        return int(time.time() - self.captured_at)

    def is_stale(self) -> bool:
        return self.age_seconds() > ttl_for(self.market_kind)

    def is_expired(self) -> bool:
        return self.age_seconds() > (ttl_for(self.market_kind) * 2)


class OddsCache:
    """In-memory cache de odds por (fixture_id, market_kind).

    Single-threaded — ok pra workers async no mesmo process. Cleanup periódico
    via `cleanup(max_age_seconds)` deve rodar fora (asyncio.create_task).
    """

    def __init__(self):
        self._cache: dict[int, dict[str, CachedOdds]] = defaultdict(dict)

    def put(self, fixture_id: int, market_kind: str, payload) -> None:
        self._cache[fixture_id][market_kind] = CachedOdds(
            fixture_id=fixture_id,
            market_kind=market_kind,
            payload=payload,
            captured_at=time.time(),
        )

    def get(self, fixture_id: int, market_kind: str) -> Optional[CachedOdds]:
        entry = self._cache.get(fixture_id, {}).get(market_kind)
        if entry is None:
            return None
        if entry.is_expired():
            # Auto-evict expired
            del self._cache[fixture_id][market_kind]
            if not self._cache[fixture_id]:
                del self._cache[fixture_id]
            return None
        return entry

    def cleanup(self, max_age_seconds: int = 600) -> int:
        """Remove entries com idade > max_age_seconds. Retorna count removido."""
        now = time.time()
        removed = 0
        for fixture_id in list(self._cache.keys()):
            for market in list(self._cache[fixture_id].keys()):
                if (now - self._cache[fixture_id][market].captured_at) > max_age_seconds:
                    del self._cache[fixture_id][market]
                    removed += 1
            if not self._cache[fixture_id]:
                del self._cache[fixture_id]
        return removed

    def stats(self) -> dict:
        total = sum(len(m) for m in self._cache.values())
        stale = sum(
            1 for f in self._cache.values() for e in f.values() if e.is_stale()
        )
        return {
            "fixtures": len(self._cache),
            "total": total,
            "fresh": total - stale,
            "stale": stale,
        }
