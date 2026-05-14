"""Schemas tipados (dataclasses frozen) para respostas da Betano StatsStream.

Fase A — provider único Betano (Opta-backed). Schemas seguem §5.4 do harness.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass(frozen=True)
class TeamStats:
    goals: int
    total_shots: int
    shots_on_target: int
    shots_off_target: int
    shots_blocked: int
    shots_inside_box: int
    shots_outside_box: int
    throw_ins: int
    corners: int
    offsides: int
    big_chances: int
    big_chances_missed: int
    woodwork: int
    x_goals_live: float
    attacks: int
    dangerous_attacks: int
    fouls: int
    yellow_cards: int
    red_cards: int
    goalkeeper_saves: int
    tackles: int
    interceptions: int
    clearances: int
    aerials_won: int
    duels_won: int
    possession_lost: int
    dribbles: int
    possession: int
    passing_accuracy: int
    passes_attempted: int
    passes_completed: int
    acc_long_balls: int
    acc_crosses: int


@dataclass(frozen=True)
class TeamStatsPerHalf:
    first_half: Optional[TeamStats]
    second_half: Optional[TeamStats]
    extra_time: Optional[TeamStats]
    total: TeamStats


@dataclass(frozen=True)
class DetailedStats:
    event_id: int
    home: TeamStatsPerHalf
    away: TeamStatsPerHalf


@dataclass(frozen=True)
class MatchInfo:
    opta_match_id: str
    sportsbook_id: int
    home_team: str
    home_team_id: str
    home_team_code: str
    home_team_color: Optional[str]
    away_team: str
    away_team_id: str
    away_team_code: str
    away_team_color: Optional[str]
    coverage_level: str
    date_utc: datetime
    current_period: int
    league_name: str
    kaizen_match_name: str
    started: bool
    supports_pass_coordinates: bool


@dataclass(frozen=True)
class MatchConfig:
    provider_type: str
    momentum_enabled: bool
    disabled_tabs: list[int]
    home_team_color: Optional[str]
    away_team_color: Optional[str]


@dataclass(frozen=True)
class MomentumPoint:
    minute: int
    period: str
    pressure: int
    home_incidents: list[dict] = field(default_factory=list)
    away_incidents: list[dict] = field(default_factory=list)


@dataclass(frozen=True)
class Momentum:
    event_id: int
    points: list[MomentumPoint]


@dataclass(frozen=True)
class LineupPlayer:
    id: str
    name: str
    number: int
    has_yellow_card: bool
    has_second_yellow_card: bool
    has_red_card: bool
    goals: int
    own_goals: int
    is_substituted: bool
    position: Optional[str] = None


@dataclass(frozen=True)
class TeamLineup:
    id: str
    name: str
    formation: str
    captain_id: str
    coach_name: Optional[str]
    on_pitch: list[list[LineupPlayer]]
    substitutes: list[LineupPlayer]


@dataclass(frozen=True)
class Lineups:
    event_id: int
    home: TeamLineup
    away: TeamLineup


@dataclass(frozen=True)
class H2HMatch:
    league_id: int
    league_name: str
    date_utc: datetime
    home_team: str
    away_team: str
    home_score: int
    away_score: int


@dataclass(frozen=True)
class H2HSummary:
    home_wins: int
    home_wins_perc: float
    away_wins: int
    away_wins_perc: float
    draws: int
    draws_perc: float


@dataclass(frozen=True)
class H2H:
    event_id: int
    summary: H2HSummary
    previous_meetings: list[H2HMatch]


@dataclass(frozen=True)
class PlayerStats:
    event_id: int
    raw: dict


# ============================================================
# Fase B — Markets / Catalog / WebSocket schemas
# ============================================================


@dataclass(frozen=True)
class BetanoLiveData:
    score_home: int
    score_away: int
    clock_seconds: int


@dataclass(frozen=True)
class BetanoParticipant:
    name: str
    is_home: bool
    team_id: int
    color: Optional[str] = None


@dataclass(frozen=True)
class BetanoIncident:
    type: str
    description: str
    props: dict


@dataclass(frozen=True)
class BetanoMarket:
    id: int
    type_code: str
    type_id: int
    name: str
    handicap: Optional[float]
    selection_ids: list[int]
    display_order: int
    rendering_layout: int
    market_close_time_millis: int


@dataclass(frozen=True)
class BetanoSelection:
    id: int
    name: str
    full_name: str
    price: float
    type_id: int
    column_index: int
    display_order: int


@dataclass(frozen=True)
class BetanoOverUnder:
    event_id: int
    market_code: str
    handicap: float
    odd_over: float
    odd_under: float


@dataclass(frozen=True)
class EventSnapshot:
    event_id: int
    sport_id: str
    league_id: int
    zone_id: int
    is_live: bool
    start_time: datetime
    participants: list[BetanoParticipant]
    live_data: BetanoLiveData
    total_markets_available: int
    betradar_match_id: Optional[int]
    incidents: list[BetanoIncident]
    url: str
    markets: dict[int, BetanoMarket]
    selections: dict[int, BetanoSelection]


@dataclass(frozen=True)
class BetanoLiveEvent:
    event_id: int
    sport_id: str
    league_id: int
    zone_id: int
    participants: list[BetanoParticipant]
    start_time: datetime
    is_live: bool
    will_go_live: bool
    total_markets_available: int
    betradar_match_id: Optional[int]
    url: str


@dataclass(frozen=True)
class BetanoStatsPlayerMapping:
    event_id: int
    sr_match_id: Optional[str]
    opta_match_id: Optional[str]
    available_stat_types: list[int]


@dataclass(frozen=True)
class MatchEvent:
    opta_match_id: str
    sportsbook_match_id: int
    event_type: int
    period_id: int
    minute: int
    seconds: int
    team_id: Optional[str]
    player_id: Optional[str]
    x: Optional[float]
    y: Optional[float]
    x_end: Optional[float]
    y_end: Optional[float]
    is_attack: bool
    is_dangerous_attack: bool
    is_possession: bool
    is_dangerous: bool
    provider_type: str
    raw: dict
