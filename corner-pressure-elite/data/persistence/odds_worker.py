"""Worker que persiste `odds_history`."""
from __future__ import annotations

import logging
from typing import Optional

from data.repositories.odds_history import OddsHistoryEntry, OddsHistoryRepo

from ._base import _BaseBatchWorker

log = logging.getLogger("cpes.persistence.odds")


class OddsPersistenceWorker(_BaseBatchWorker[OddsHistoryEntry]):
    """Persiste odds capturadas pelo CompositeOddsProvider."""

    def __init__(
        self,
        repo: OddsHistoryRepo,
        *,
        queue_size: int = 10000,
        batch_size: int = 10,
        batch_timeout_s: float = 5.0,
    ):
        super().__init__(
            name="odds_worker",
            queue_size=queue_size,
            batch_size=batch_size,
            batch_timeout_s=batch_timeout_s,
        )
        self._repo = repo

    async def flush(self, batch: list[OddsHistoryEntry]) -> None:
        await self._repo.bulk_insert(batch)

    # ---- helper consumido pelo CompositeOddsProvider via duck typing ----

    def enqueue_from_dispatch(
        self,
        *,
        fixture,
        market_kind: str,
        primary,
        all_results: list,
        pressure_score: Optional[float] = None,
        tension_score: Optional[float] = None,
        provider_pressure: Optional[float] = None,
    ) -> None:
        entry = OddsHistoryEntry(
            fixture_id=fixture.fixture_id,
            source=primary.source,
            market_kind=market_kind,
            market_code=primary.market_code or None,
            linha=float(primary.linha),
            odd_over=float(primary.odd_over),
            odd_under=float(primary.odd_under),
            minute=None,
            score_home=fixture.score_home,
            score_away=fixture.score_away,
            pressure_score=pressure_score,
            tension_score=tension_score,
            provider_pressure=provider_pressure,
            raw={
                "providers": [
                    {
                        "name": name,
                        "linha": r.linha if r else None,
                        "odd_over": r.odd_over if r else None,
                        "odd_under": r.odd_under if r else None,
                    }
                    for name, r in all_results
                ],
            },
        )
        self.enqueue(entry)
