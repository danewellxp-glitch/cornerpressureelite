"""Schemas tipados (frozen dataclasses) para os endpoints gismo da Sportradar.

Fonte: docs/sprints/2026-05-12-betano-discovery-master.md §3.4 e §3.5.
Endpoints cobertos: ver harness §6 (Fase A).
"""
from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class CoverageFlags:
    """Flags de cobertura por categoria (`match_info.data.match.coverage`).

    Gate crítico (harness §4.5): se `cornerson=False` ou `cardson=False`,
    o caller (Fase C) deve cair para fallback API-Football.
    """
    cornerson: bool = False
    cardson: bool = False
    lineups: bool = False
    bookings: bool = False
    extended: bool = False


@dataclass(frozen=True)
class TimelineEvent:
    """Evento individual da timeline (`match_timeline` / `match_timelinedelta`).

    Schema do gismo (master §3.5): cada item tem `_doc=event`, `_doctype` com
    o tipo (corner, yellowcard, goal, throwin, substitution, matchsituation),
    `X/Y` 0-100 no campo, `seconds` (ts absoluto do jogo), `time` (minuto).
    """
    event_id: str
    type: str
    type_id: Optional[str]
    minute: int
    seconds: int
    team: Optional[str]
    player_name: Optional[str]
    x: Optional[int]
    y: Optional[int]
    name: Optional[str]
    raw: dict


@dataclass(frozen=True)
class MatchInfo:
    """Metadata estática do jogo (`match_info`)."""
    match_id: str
    sport_id: int
    league_id: Optional[int]
    season_id: Optional[int]
    home_team_name: str
    home_team_id: Optional[int]
    away_team_name: str
    away_team_id: Optional[int]
    status: str
    minute: Optional[int]
    score_home: Optional[int]
    score_away: Optional[int]
    coverage: CoverageFlags


@dataclass(frozen=True)
class MatchSituation:
    """Posse/ataque/posição da bola (`stats_match_situation`)."""
    match_id: str
    possession_home_pct: Optional[float]
    possession_away_pct: Optional[float]
    attack_home_pct: Optional[float]
    attack_away_pct: Optional[float]
    dangerous_attack_home_pct: Optional[float]
    dangerous_attack_away_pct: Optional[float]
    ball_x: Optional[int]
    ball_y: Optional[int]
    minute: Optional[int]


@dataclass(frozen=True)
class MatchTimelineDelta:
    """Resposta de `match_timelinedelta`.

    `last_seconds` é o maior `seconds` da lista — caller passa de volta como
    `since_uts` na próxima chamada (filtragem client-side; o gismo não tem
    cursor server-side observado na captura — confirmar no spike).
    """
    match_id: str
    events: list
    last_seconds: int


@dataclass(frozen=True)
class MatchDetailsExtended:
    """Stats agregadas do jogo (`match_detailsextended`).

    Substitui múltiplas chamadas API-Football (`get_statistics` +
    `get_events`).
    """
    match_id: str
    minute: int
    score_home: int
    score_away: int
    corners_home: int
    corners_away: int
    yellowcards_home: int
    yellowcards_away: int
    redcards_home: int
    redcards_away: int
    shots_on_target_home: int
    shots_on_target_away: int
    shots_total_home: int
    shots_total_away: int
    raw: dict


@dataclass(frozen=True)
class SeasonMeta:
    """Metadata da temporada (`stats_season_meta`)."""
    season_id: int
    name: str
    league_id: int
    year: int


@dataclass(frozen=True)
class TeamSeasonStats:
    """Stats agregadas de um time na temporada
    (`stats_season_uniqueteamstats`).

    Substitui chamadas `/teams/statistics` da API-Football.
    """
    team_id: int
    team_name: str
    matches_played: int
    avg_corners_for: float
    avg_corners_against: float
    avg_yellowcards: float
