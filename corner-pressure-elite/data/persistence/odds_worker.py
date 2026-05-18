"""Worker que persiste `odds_history`."""
from __future__ import annotations

import logging
from dataclasses import replace
from datetime import datetime, timezone
from typing import Optional

from data.repositories.af_sofa_map import AfSofaFixtureMapRepo
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
        af_sofa_map: Optional[AfSofaFixtureMapRepo] = None,
    ):
        super().__init__(
            name="odds_worker",
            queue_size=queue_size,
            batch_size=batch_size,
            batch_timeout_s=batch_timeout_s,
        )
        self._repo = repo
        self._af_sofa_map = af_sofa_map

    async def flush(self, batch: list[OddsHistoryEntry]) -> None:
        # Fase H A1.3: enriquece batch com sofa_event_id via cache LRU.
        # Lookup eh O(1) cached + barato. Misses ficam com None (orfao).
        if self._af_sofa_map is not None:
            enriched: list[OddsHistoryEntry] = []
            for e in batch:
                if e.sofa_event_id is not None:
                    enriched.append(e)
                    continue
                try:
                    sofa_id = await self._af_sofa_map.get_sofa_id(e.fixture_id)
                except Exception:
                    sofa_id = None
                enriched.append(replace(e, sofa_event_id=sofa_id))
            batch = enriched
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

    # ---- catálogo completo (Fase D.0 — full coverage) ----

    def enqueue_catalog(
        self,
        *,
        fixture_id: int,
        source: str,
        market_kind: str,
        catalog_lines: list[dict],
        minute: Optional[int] = None,
        score_home: Optional[int] = None,
        score_away: Optional[int] = None,
        pressure_score: Optional[float] = None,
        tension_score: Optional[float] = None,
    ) -> None:
        """Enfileira N entries (uma por linha do catálogo) com contexto rico.

        `catalog_lines`: lista vinda do bridge no formato
          [{"line": 5.5, "over_price": 1.19, "under_price": 4.15, ...}, ...]

        Todas as N linhas compartilham o mesmo `captured_at` — capturadas no
        mesmo instante, viabiliza `GROUP BY captured_at` como "uma captura".
        """
        captured_at = datetime.now(timezone.utc)
        for position, line_data in enumerate(catalog_lines):
            entry = OddsHistoryEntry(
                fixture_id=fixture_id,
                source=source,
                market_kind=market_kind,
                market_code="",
                linha=float(line_data["line"]),
                odd_over=float(line_data["over_price"]),
                odd_under=float(line_data["under_price"]),
                minute=minute,
                score_home=score_home,
                score_away=score_away,
                pressure_score=pressure_score,
                tension_score=tension_score,
                captured_at=captured_at,
                raw={"catalog_position": position},
            )
            self.enqueue(entry)
