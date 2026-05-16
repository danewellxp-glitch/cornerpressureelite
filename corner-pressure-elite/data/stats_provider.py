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
    """Snapshot canônico de stats de 1 fixture, agregado por StatsProvider.

    **Campos GARANTIDOS** (todo provider sempre preenche; nunca None):
        fixture_id, source, minute, score_home/away, corners_home/away,
        yellow_cards_home/away, red_cards_home/away, shots_on_target_home/away,
        dangerous_attacks_home/away, possession_home/away, x_goals_home/away.

        Quando a fonte não cobre uma métrica, o adapter preenche `0`/`0.0`
        (conforme `score_engine` e `cards_score_engine` já lidam com zero).

    **Campos OPCIONAIS** (None quando o provider/fase não preenche):
        - `provider_pressure`: Opta momentum (Fase A — só StatsStream Opta).
        - `version`: versão do snapshot Betano (`BridgeStatsAdapter` Fase E.1).
          AF e Fase A deixam None.
        - `second_since_start`: clock granular em segundos (Betano `/latest`).
          AF expõe só minuto → deixa None.
        - `corners_last_5min`/`_10min`, `yellow_last_5min`/`_10min`:
          janelas calculadas **a posteriori** por `StatsWindowCalculator`
          (PARTE E') a partir do histórico em `stats_history`. Snapshot recém-saído
          do adapter sempre vem com essas 4 keys = None — checar via
          `has_window_stats` antes de assumir presença.

    Downstream que precisa dos campos opcionais deve fazer `if x is None`
    checagem explícita ou usar a property `has_window_stats`.
    """

    fixture_id: int
    source: str                 # "betano" | "apifootball" | "bridge_betano"
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
    provider_pressure: Optional[float] = None  # Opta momentum (Fase A)
    raw: dict = field(default_factory=dict)
    # ----- Campos Fase E.1 — opcionais -----
    version: Optional[int] = None
    second_since_start: Optional[int] = None
    corners_last_5min: Optional[int] = None
    corners_last_10min: Optional[int] = None
    yellow_last_5min: Optional[int] = None
    yellow_last_10min: Optional[int] = None

    @property
    def has_window_stats(self) -> bool:
        """True se as 4 janelas (corners/yellow × 5/10min) estão preenchidas."""
        return (
            self.corners_last_5min is not None
            and self.corners_last_10min is not None
            and self.yellow_last_5min is not None
            and self.yellow_last_10min is not None
        )


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
