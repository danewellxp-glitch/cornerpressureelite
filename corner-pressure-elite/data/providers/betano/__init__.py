"""Provider único Betano (REST + WS) — pós-spike 2026-05-12.

Fase A: `BetanoStatsStream` + schemas Opta.
Fase B: `BetanoMarkets`, `BetanoCatalog`, `BetanoWSClient`, warmup Playwright.
"""
from .catalog import BetanoCatalog
from .markets import BetanoMarkets
from .schemas import (
    BetanoIncident,
    BetanoLiveData,
    BetanoLiveEvent,
    BetanoMarket,
    BetanoOverUnder,
    BetanoParticipant,
    BetanoSelection,
    BetanoStatsPlayerMapping,
    DetailedStats,
    EventSnapshot,
    H2H,
    H2HMatch,
    H2HSummary,
    LineupPlayer,
    Lineups,
    MatchConfig,
    MatchEvent,
    MatchInfo,
    Momentum,
    MomentumPoint,
    PlayerStats,
    TeamLineup,
    TeamStats,
    TeamStatsPerHalf,
)
from .session import (
    BetanoBlockedError,
    BetanoParseError,
    BetanoSession,
)
from .statsstream import BetanoStatsStream
from .wsclient import BetanoWSClient

__all__ = [
    "BetanoBlockedError",
    "BetanoCatalog",
    "BetanoIncident",
    "BetanoLiveData",
    "BetanoLiveEvent",
    "BetanoMarket",
    "BetanoMarkets",
    "BetanoOverUnder",
    "BetanoParseError",
    "BetanoParticipant",
    "BetanoSelection",
    "BetanoSession",
    "BetanoStatsPlayerMapping",
    "BetanoStatsStream",
    "BetanoWSClient",
    "DetailedStats",
    "EventSnapshot",
    "H2H",
    "H2HMatch",
    "H2HSummary",
    "LineupPlayer",
    "Lineups",
    "MatchConfig",
    "MatchEvent",
    "MatchInfo",
    "Momentum",
    "MomentumPoint",
    "PlayerStats",
    "TeamLineup",
    "TeamStats",
    "TeamStatsPerHalf",
]
