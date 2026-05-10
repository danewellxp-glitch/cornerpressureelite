"""Strategy tier definitions for corners and cards signals.

Each tier defines the minimum score and edge thresholds required to emit
a signal. Lower tiers produce more signals with higher risk; higher tiers
produce fewer signals with higher confidence.

Tiers (low → high risk):
  CONSERVATIVE  — Fewest signals, highest confidence
  MODERATE      — Balanced (current default behavior)
  AGGRESSIVE    — More signals, moderate risk
  BRUTE         — Maximum signal coverage, lowest threshold
"""

from dataclasses import dataclass
from typing import Literal, Dict, Optional

StrategyTier = Literal["conservative", "moderate", "aggressive", "brute"]


@dataclass(frozen=True)
class CornerStrategy:
    """Thresholds for corner (escanteios) signals."""
    min_score: int
    min_edge: float
    premium_score: int
    premium_edge: float
    min_escanteios_total: int
    min_escanteios_5min: int
    early_window_escanteios: int
    max_linha_asianica: float
    label: str


@dataclass(frozen=True)
class CardStrategy:
    """Thresholds for card (cartões) signals."""
    min_score: int
    min_edge: float
    premium_score: int
    premium_edge: float
    min_cartoes_total: int
    min_cartoes_5min: int
    early_window_cartoes: int
    label: str


# ============================================================
# CORNER STRATEGIES
# ============================================================

CORNER_STRATEGIES: Dict[StrategyTier, CornerStrategy] = {
    "conservative": CornerStrategy(
        min_score=8,
        min_edge=1.5,
        premium_score=10,
        premium_edge=2.0,
        min_escanteios_total=5,
        min_escanteios_5min=1,
        early_window_escanteios=9,
        max_linha_asianica=11.5,
        label="Conservador",
    ),
    "moderate": CornerStrategy(
        min_score=6,
        min_edge=1.2,
        premium_score=8,
        premium_edge=1.5,
        min_escanteios_total=3,
        min_escanteios_5min=1,
        early_window_escanteios=7,
        max_linha_asianica=12.5,
        label="Moderado",
    ),
    "aggressive": CornerStrategy(
        min_score=5,
        min_edge=0.8,
        premium_score=7,
        premium_edge=1.0,
        min_escanteios_total=3,
        min_escanteios_5min=1,
        early_window_escanteios=6,
        max_linha_asianica=13.5,
        label="Agressivo",
    ),
    "brute": CornerStrategy(
        min_score=4,
        min_edge=0.5,
        premium_score=6,
        premium_edge=0.8,
        min_escanteios_total=2,
        min_escanteios_5min=0,
        early_window_escanteios=5,
        max_linha_asianica=14.5,
        label="Bruto",
    ),
}

# ============================================================
# CARD STRATEGIES
# ============================================================

CARD_STRATEGIES: Dict[StrategyTier, CardStrategy] = {
    "conservative": CardStrategy(
        min_score=7,
        min_edge=1.2,
        premium_score=9,
        premium_edge=1.8,
        min_cartoes_total=3,
        min_cartoes_5min=1,
        early_window_cartoes=5,
        label="Conservador",
    ),
    "moderate": CardStrategy(
        min_score=5,
        min_edge=0.5,
        premium_score=8,
        premium_edge=1.2,
        min_cartoes_total=1,
        min_cartoes_5min=1,
        early_window_cartoes=4,
        label="Moderado",
    ),
    "aggressive": CardStrategy(
        min_score=4,
        min_edge=0.3,
        premium_score=6,
        premium_edge=0.7,
        min_cartoes_total=1,
        min_cartoes_5min=0,
        early_window_cartoes=3,
        label="Agressivo",
    ),
    "brute": CardStrategy(
        min_score=3,
        min_edge=0.0,
        premium_score=5,
        premium_edge=0.5,
        min_cartoes_total=1,
        min_cartoes_5min=0,
        early_window_cartoes=2,
        label="Bruto",
    ),
}

# ============================================================
# DEFAULT
# ============================================================

DEFAULT_CORNER_STRATEGY: StrategyTier = "moderate"
DEFAULT_CARD_STRATEGY: StrategyTier = "moderate"


def get_corner_strategy(tier: Optional[StrategyTier] = None) -> CornerStrategy:
    """Return the CornerStrategy for the given tier, or the default."""
    if tier is None:
        tier = DEFAULT_CORNER_STRATEGY
    return CORNER_STRATEGIES[tier]


def get_card_strategy(tier: Optional[StrategyTier] = None) -> CardStrategy:
    """Return the CardStrategy for the given tier, or the default."""
    if tier is None:
        tier = DEFAULT_CARD_STRATEGY
    return CARD_STRATEGIES[tier]


ALL_TIERS: list[StrategyTier] = ["conservative", "moderate", "aggressive", "brute"]


def compute_matching_tiers(
    score: int,
    edge: float,
    strategies: dict,
) -> list[StrategyTier]:
    """Return tiers whose min_score/min_edge thresholds the signal satisfies.

    Tiers are returned from highest (conservative) to lowest (brute) that match.
    """
    matched: list[StrategyTier] = []
    for tier in ALL_TIERS:
        strat = strategies[tier]
        if score >= strat.min_score and edge >= strat.min_edge:
            matched.append(tier)
    return matched
