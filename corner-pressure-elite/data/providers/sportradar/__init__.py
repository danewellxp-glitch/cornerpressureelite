"""Provider Sportradar (stats ao vivo via CDN gismo).

Documentos de referência:
- docs/sprints/2026-05-12-betano-discovery-master.md (master)
- docs/sprints/2026-05-12-betano-fase-A-sportradar-provider.md (harness)
"""
from .adapter import to_jogo_ao_vivo_fields
from .client import SportradarClient
from .schemas import (
    CoverageFlags,
    MatchDetailsExtended,
    MatchInfo,
    MatchSituation,
    MatchTimelineDelta,
    SeasonMeta,
    TeamSeasonStats,
    TimelineEvent,
)
from .session import SportradarSession

__all__ = [
    "CoverageFlags",
    "MatchDetailsExtended",
    "MatchInfo",
    "MatchSituation",
    "MatchTimelineDelta",
    "SeasonMeta",
    "SportradarClient",
    "SportradarSession",
    "TeamSeasonStats",
    "TimelineEvent",
    "to_jogo_ao_vivo_fields",
]
