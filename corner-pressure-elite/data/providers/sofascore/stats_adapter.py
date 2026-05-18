"""SofaScoreStatsAdapter — stats live via SofaScore (Fase K.1 PARTE B).

Substitui `APIFootballStatsAdapter` no Composite como fallback intermediário
(entre `BridgeStatsAdapter` Betano primary e AF super-residual).

# Schema response SofaScore `/event/{id}/statistics`

```json
{
  "statistics": [
    {"period": "ALL", "groups": [...]},
    {"period": "1ST", "groups": [...]},
    {"period": "2ND", "groups": [...]},
  ]
}
```

Cada `group` tem `groupName` (Match overview, Shots, Attack, Passes, Duels,
Defending, Goalkeeping) e `statisticsItems[]` com `name`, `home`, `away`.

Adapter extrai **só `period: "ALL"`** (agregado total do jogo). Períodos 1H/2H
ficam em `raw` pra Fase futura (decision_engine pode usar pra ajuste de
momentum).

# Mapping SofaScore → CanonicalStats

| CanonicalStats           | SofaScore (period=ALL)               | Status |
|--------------------------|--------------------------------------|--------|
| corners_home/away        | "Corner kicks"                       | ✅ |
| yellow_cards_home/away   | "Yellow cards"                       | ✅ |
| shots_on_target_home/away| "Shots on target"                    | ✅ |
| possession_home/away     | "Ball possession" (string "49%")     | ✅ |
| x_goals_home/away        | "Expected goals" (string "1.38")     | ✅ |
| red_cards_home/away      | (não vem em /statistics)             | GAP (SOFASCORE_GAPS_STATS) |
| dangerous_attacks_*      | (SofaScore não tem direto)           | GAP (SOFASCORE_GAPS_STATS) |
| minute                   | (não vem em /statistics)             | preenchido via param ou fixture.score (0 fallback) |

# Resolução fixture_id → sofa_event_id

K.1 PARTE B.5 implementa `SofaScoreEventResolver`. Pra K.1 PARTE B (este
adapter), recebe `event_id_resolver: Callable[[CanonicalFixture], Awaitable[Optional[int]]]`
injetado. Se resolver=None ou devolve None, adapter retorna None (Composite
cai pra próximo fallback).
"""
from __future__ import annotations

import logging
from typing import Any, Awaitable, Callable, Optional

from data.odds_provider import CanonicalFixture
from data.stats_provider import CanonicalStats

from .client import SofaScoreClient

log = logging.getLogger("cpes.providers.sofascore.stats")


# Campos que SofaScore /statistics NÃO cobre. Composite + downstream sabem
# que esses ficam 0/None — preencher via outra fonte (Betano primary cobre
# tudo; AF super-residual cobre red_cards + dangerous_attacks).
SOFASCORE_GAPS_STATS: frozenset[str] = frozenset({
    "red_cards_home",
    "red_cards_away",
    "dangerous_attacks_home",
    "dangerous_attacks_away",
})


EventIdResolver = Callable[[CanonicalFixture], Awaitable[Optional[int]]]


def _parse_pct(value: Any) -> int:
    """'49%' → 49. None / inválido → 0."""
    if isinstance(value, (int, float)):
        return int(value)
    if isinstance(value, str):
        s = value.strip().rstrip("%")
        try:
            return int(float(s))
        except (TypeError, ValueError):
            return 0
    return 0


def _parse_int(value: Any) -> int:
    """'17' / 17 / None → int (0 fallback)."""
    if isinstance(value, (int, float)):
        return int(value)
    if isinstance(value, str):
        try:
            return int(float(value.strip()))
        except (TypeError, ValueError):
            return 0
    return 0


def _parse_float(value: Any) -> float:
    """'1.38' / 1.38 / None → float (0.0 fallback)."""
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value.strip())
        except (TypeError, ValueError):
            return 0.0
    return 0.0


def _flatten_period(period_block: dict) -> dict[str, dict]:
    """Achata groups → {statisticName: {'home': val, 'away': val}}."""
    flat: dict[str, dict] = {}
    for group in period_block.get("groups", []):
        for item in group.get("statisticsItems", []):
            name = item.get("name")
            if not name:
                continue
            flat[name] = {"home": item.get("home"), "away": item.get("away")}
    return flat


class SofaScoreStatsAdapter:
    """Provider stats via SofaScore. Implementa `StatsProvider` Protocol."""

    name = "sofascore"

    def __init__(
        self,
        client: SofaScoreClient,
        event_id_resolver: Optional[EventIdResolver] = None,
    ):
        self._client = client
        self._resolver = event_id_resolver

    async def get_stats(
        self, fixture: CanonicalFixture
    ) -> Optional[CanonicalStats]:
        if self._resolver is None:
            log.debug("sofascore_stats.no_resolver fixture=%d", fixture.fixture_id)
            return None
        sofa_event_id = await self._resolver(fixture)
        if sofa_event_id is None:
            log.debug(
                "sofascore_stats.no_sofa_event_id fixture=%d",
                fixture.fixture_id,
            )
            return None

        try:
            raw_stats = await self._client.get_statistics(sofa_event_id)
        except Exception as e:
            log.warning(
                "sofascore_stats.client_error fixture=%d sofa=%d err=%s",
                fixture.fixture_id, sofa_event_id, e,
            )
            return None
        if not raw_stats:
            return None

        return self._normalize(fixture, sofa_event_id, raw_stats)

    async def healthcheck(self) -> bool:
        return await self._client.health()

    def _normalize(
        self,
        fixture: CanonicalFixture,
        sofa_event_id: int,
        raw_stats: list[dict],
    ) -> Optional[CanonicalStats]:
        all_period = next(
            (p for p in raw_stats if p.get("period") == "ALL"), None
        )
        if not all_period:
            log.debug(
                "sofascore_stats.no_all_period fixture=%d sofa=%d",
                fixture.fixture_id, sofa_event_id,
            )
            return None

        flat = _flatten_period(all_period)

        def _h(name: str) -> Any:
            return flat.get(name, {}).get("home")

        def _a(name: str) -> Any:
            return flat.get(name, {}).get("away")

        # Extra periods 1H/2H pra stats_1h / stats_2h (gap Betano).
        def _period_summary(period_name: str) -> Optional[dict]:
            block = next(
                (p for p in raw_stats if p.get("period") == period_name), None
            )
            if not block:
                return None
            f = _flatten_period(block)
            return {
                "corners_home": _parse_int(f.get("Corner kicks", {}).get("home")),
                "corners_away": _parse_int(f.get("Corner kicks", {}).get("away")),
                "yellow_cards_home": _parse_int(f.get("Yellow cards", {}).get("home")),
                "yellow_cards_away": _parse_int(f.get("Yellow cards", {}).get("away")),
                "shots_on_target_home": _parse_int(f.get("Shots on target", {}).get("home")),
                "shots_on_target_away": _parse_int(f.get("Shots on target", {}).get("away")),
                "possession_home": _parse_pct(f.get("Ball possession", {}).get("home")),
                "possession_away": _parse_pct(f.get("Ball possession", {}).get("away")),
                "x_goals_home": _parse_float(f.get("Expected goals", {}).get("home")),
                "x_goals_away": _parse_float(f.get("Expected goals", {}).get("away")),
            }

        return CanonicalStats(
            fixture_id=fixture.fixture_id,
            source=self.name,
            minute=0,  # SofaScore /statistics não traz minuto;
                      # caller pode hidratar via outra source (Betano clock).
            score_home=fixture.score_home,
            score_away=fixture.score_away,
            corners_home=_parse_int(_h("Corner kicks")),
            corners_away=_parse_int(_a("Corner kicks")),
            yellow_cards_home=_parse_int(_h("Yellow cards")),
            yellow_cards_away=_parse_int(_a("Yellow cards")),
            red_cards_home=0,                  # GAP SofaScore (vem em /incidents)
            red_cards_away=0,                  # GAP SofaScore (vem em /incidents)
            shots_on_target_home=_parse_int(_h("Shots on target")),
            shots_on_target_away=_parse_int(_a("Shots on target")),
            dangerous_attacks_home=0,          # GAP SofaScore (proxy: Big chances)
            dangerous_attacks_away=0,          # GAP SofaScore (proxy: Big chances)
            possession_home=_parse_pct(_h("Ball possession")),
            possession_away=_parse_pct(_a("Ball possession")),
            x_goals_home=_parse_float(_h("Expected goals")),
            x_goals_away=_parse_float(_a("Expected goals")),
            # ----- enrichment fields (BETANO_GAPS_STATS) -----
            shots_off_target_home=_parse_int(_h("Shots off target")),
            shots_off_target_away=_parse_int(_a("Shots off target")),
            blocked_shots_home=_parse_int(_h("Blocked shots")),
            blocked_shots_away=_parse_int(_a("Blocked shots")),
            big_chances_home=_parse_int(_h("Big chances")),
            big_chances_away=_parse_int(_a("Big chances")),
            big_chances_missed_home=_parse_int(_h("Big chances missed")),
            big_chances_missed_away=_parse_int(_a("Big chances missed")),
            stats_1h=_period_summary("1ST"),
            stats_2h=_period_summary("2ND"),
            raw={"sofa_event_id": sofa_event_id, "statistics": raw_stats},
            sofa_event_id=sofa_event_id,
        )
