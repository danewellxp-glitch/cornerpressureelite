"""Abstração canônica de provider de stats + Composite com cascata.

Espelha `odds_provider.py`. `CanonicalStats` traz o subset que o orquestrador
precisa: placar, escanteios, cartões, shots, posse, xG e (Fase B+)
`provider_pressure` vindo do momentum da Opta.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Optional, Protocol, runtime_checkable

from .odds_provider import CanonicalFixture

log = logging.getLogger("cpes.providers.stats")


@dataclass(frozen=True)
class CanonicalStats:
    fixture_id: int
    source: str                 # "betano" | "apifootball"
    minute: int
    score_home: int
    score_away: int
    corners_home: int
    corners_away: int
    yellow_cards_home: int
    yellow_cards_away: int
    red_cards_home: int
    red_cards_away: int
    shots_on_target_home: int
    shots_on_target_away: int
    dangerous_attacks_home: int
    dangerous_attacks_away: int
    possession_home: int
    possession_away: int
    x_goals_home: float
    x_goals_away: float
    provider_pressure: Optional[float] = None  # Opta momentum
    raw: dict = field(default_factory=dict)


@runtime_checkable
class StatsProvider(Protocol):
    name: str

    async def get_stats(self, fixture: CanonicalFixture) -> Optional[CanonicalStats]: ...

    async def healthcheck(self) -> bool: ...


class CompositeStatsProvider:
    name = "composite"

    def __init__(self, providers: list[StatsProvider], drift_check: bool = False):
        self._providers = list(providers)
        self._drift_check = drift_check

    async def get_stats(self, fixture: CanonicalFixture) -> Optional[CanonicalStats]:
        results: list[tuple[str, Optional[CanonicalStats]]] = []
        for p in self._providers:
            try:
                r = await p.get_stats(fixture)
            except Exception as e:
                log.warning(
                    "composite.stats.%s.error fixture=%d err=%s",
                    p.name, fixture.fixture_id, e,
                )
                r = None
            results.append((p.name, r))
            if r is not None and not self._drift_check:
                break

        primary = next((r for _, r in results if r is not None), None)

        if self._drift_check and sum(1 for _, r in results if r is not None) >= 2:
            _log_stats_drift(fixture.fixture_id, results)

        return primary

    async def healthcheck(self) -> bool:
        for p in self._providers:
            try:
                if await p.healthcheck():
                    return True
            except Exception:
                log.exception("composite.stats.healthcheck.error name=%s", p.name)
        return False


def _log_stats_drift(
    fixture_id: int, results: list[tuple[str, Optional[CanonicalStats]]]
) -> None:
    pairs = [(name, r) for name, r in results if r is not None]
    if len(pairs) < 2:
        return
    a_name, a = pairs[0]
    b_name, b = pairs[1]
    log.info(
        "stats.drift fixture=%d %s corners=%d-%d  %s corners=%d-%d  "
        "yellows=%d-%d / %d-%d",
        fixture_id,
        a_name, a.corners_home, a.corners_away,
        b_name, b.corners_home, b.corners_away,
        a.yellow_cards_home, a.yellow_cards_away,
        b.yellow_cards_home, b.yellow_cards_away,
    )
