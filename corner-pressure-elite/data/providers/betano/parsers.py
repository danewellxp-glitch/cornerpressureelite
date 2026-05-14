"""Parsers puros JSON → schemas tipados.

Defensivos: campos opcionais ausentes viram `None`/default. Campos obrigatórios
ausentes levantam `BetanoParseError`. Mantidos sem efeitos colaterais para
serem trivialmente testáveis com fixtures golden.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any, Optional

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
from .session import BetanoParseError

log = logging.getLogger("cpes.betano.parser")


def _safe(d: Any, *keys, default=None):
    cur = d
    for k in keys:
        if not isinstance(cur, dict) or k not in cur:
            return default
        cur = cur[k]
    return cur if cur is not None else default


def _parse_iso_or_epoch(value: Any) -> datetime:
    """Aceita ISO ('...Z' ou com offset) ou epoch ms/s. Fallback: now()."""
    if value is None:
        return datetime.now(timezone.utc)
    if isinstance(value, (int, float)):
        # heurística: > 10**12 → ms; senão segundos
        ts = value / 1000 if value > 10**12 else value
        return datetime.fromtimestamp(ts, tz=timezone.utc)
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            pass
    return datetime.now(timezone.utc)


def parse_info_aggregated(raw: dict) -> MatchInfo:
    m = _safe(raw, "data", "match", default={})
    if not m or "id" not in m:
        raise BetanoParseError("info/aggregated sem data.match.id")
    return MatchInfo(
        opta_match_id=str(m["id"]),
        sportsbook_id=int(m["sportsbook_id"]),
        home_team=m.get("home_team", "?"),
        home_team_id=str(m.get("home_team_id", "")),
        home_team_code=m.get("home_team_code", ""),
        home_team_color=m.get("home_team_color"),
        away_team=m.get("away_team", "?"),
        away_team_id=str(m.get("away_team_id", "")),
        away_team_code=m.get("away_team_code", ""),
        away_team_color=m.get("away_team_color"),
        coverage_level=str(m.get("coverage_level", "")),
        date_utc=_parse_iso_or_epoch(m.get("date")),
        current_period=int(m.get("current_period", 0) or 0),
        league_name=m.get("league_name", ""),
        kaizen_match_name=m.get("kaizen_match_name", ""),
        started=bool(m.get("started", False)),
        supports_pass_coordinates=bool(m.get("supports_pass_coordinates", False)),
    )


def _parse_team_stats(d: dict) -> TeamStats:
    def _i(key: str, default: int = 0) -> int:
        v = d.get(key, default)
        try:
            return int(v) if v is not None else default
        except (TypeError, ValueError):
            return default

    def _f(key: str, default: float = 0.0) -> float:
        v = d.get(key, default)
        try:
            return float(v) if v is not None else default
        except (TypeError, ValueError):
            return default

    return TeamStats(
        goals=_i("goals"),
        total_shots=_i("total_shots"),
        shots_on_target=_i("shots_on_target"),
        shots_off_target=_i("shots_off_target"),
        shots_blocked=_i("shots_blocked"),
        shots_inside_box=_i("shots_inside_box"),
        shots_outside_box=_i("shots_outside_box"),
        throw_ins=_i("throw_ins"),
        corners=_i("corners"),
        offsides=_i("offsides"),
        big_chances=_i("big_chances"),
        big_chances_missed=_i("big_chances_missed"),
        woodwork=_i("woodwork"),
        x_goals_live=_f("x_goals_live"),
        attacks=_i("attacks"),
        dangerous_attacks=_i("dangerous_attacks"),
        fouls=_i("fouls"),
        yellow_cards=_i("yellow_cards"),
        red_cards=_i("red_cards"),
        goalkeeper_saves=_i("goalkeeper_saves"),
        tackles=_i("tackles"),
        interceptions=_i("interceptions"),
        clearances=_i("clearances"),
        aerials_won=_i("aerials_won"),
        duels_won=_i("duels_won"),
        possession_lost=_i("possession_lost"),
        dribbles=_i("dribbles"),
        possession=_i("possession"),
        passing_accuracy=_i("passing_accuracy"),
        passes_attempted=_i("passes_attempted"),
        passes_completed=_i("passes_completed"),
        acc_long_balls=_i("acc_long_balls"),
        acc_crosses=_i("acc_crosses"),
    )


def _parse_per_half(d: dict) -> TeamStatsPerHalf:
    if "total" not in d or not isinstance(d.get("total"), dict):
        raise BetanoParseError("stats/detailed: falta `total` no time")
    return TeamStatsPerHalf(
        first_half=_parse_team_stats(d["first_half"]) if isinstance(d.get("first_half"), dict) else None,
        second_half=_parse_team_stats(d["second_half"]) if isinstance(d.get("second_half"), dict) else None,
        extra_time=_parse_team_stats(d["extra_time"]) if isinstance(d.get("extra_time"), dict) else None,
        total=_parse_team_stats(d["total"]),
    )


def parse_stats_detailed(raw: dict, event_id: int = 0) -> DetailedStats:
    data = raw.get("data") or {}
    if "home" not in data or "away" not in data:
        raise BetanoParseError("stats/detailed sem data.home/away")
    return DetailedStats(
        event_id=event_id,
        home=_parse_per_half(data["home"]),
        away=_parse_per_half(data["away"]),
    )


def parse_momentum(raw: dict, event_id: int = 0) -> Momentum:
    points_raw = _safe(raw, "data", "momentum", default=[]) or []
    points: list[MomentumPoint] = []
    for p in points_raw:
        if not isinstance(p, dict):
            continue
        points.append(
            MomentumPoint(
                minute=int(p.get("minute", 0) or 0),
                period=p.get("period", ""),
                pressure=int(p.get("pressure", 0) or 0),
                home_incidents=p.get("homeIncidents", []) or [],
                away_incidents=p.get("awayIncidents", []) or [],
            )
        )
    return Momentum(event_id=event_id, points=points)


def parse_config(raw: dict) -> MatchConfig:
    data = raw.get("data") or {}
    return MatchConfig(
        provider_type=data.get("provider_type", "?"),
        momentum_enabled=bool(data.get("momentum_enabled", False)),
        disabled_tabs=[
            t.get("id")
            for t in (data.get("disabled_tabs") or [])
            if isinstance(t, dict) and "id" in t
        ],
        home_team_color=_safe(data, "teams", "home_team", "color"),
        away_team_color=_safe(data, "teams", "away_team", "color"),
    )


def _parse_lineup_player(d: dict) -> LineupPlayer:
    return LineupPlayer(
        id=str(d.get("id", "")),
        name=d.get("name", "?"),
        number=int(d.get("number", 0) or 0),
        has_yellow_card=bool(d.get("has_yellow_card", False)),
        has_second_yellow_card=bool(d.get("has_second_yellow_card", False)),
        has_red_card=bool(d.get("has_red_card", False)),
        goals=int(d.get("goals", 0) or 0),
        own_goals=int(d.get("own_goals", 0) or 0),
        is_substituted=bool(d.get("is_substituted", False)),
        position=d.get("position"),
    )


def _parse_team_lineup(d: dict) -> TeamLineup:
    on_pitch_raw = d.get("on_pitch", [])
    on_pitch: list[list[LineupPlayer]] = []
    if isinstance(on_pitch_raw, list):
        for row in on_pitch_raw:
            if isinstance(row, list):
                on_pitch.append([_parse_lineup_player(p) for p in row if isinstance(p, dict)])
            elif isinstance(row, dict):
                on_pitch.append([_parse_lineup_player(row)])
    subs = [
        _parse_lineup_player(p)
        for p in (d.get("substitutes") or [])
        if isinstance(p, dict)
    ]
    return TeamLineup(
        id=str(d.get("id", "")),
        name=d.get("name", "?"),
        formation=d.get("formation", "") or "",
        captain_id=str(d.get("captain_id", "") or ""),
        coach_name=d.get("coach_name"),
        on_pitch=on_pitch,
        substitutes=subs,
    )


def parse_lineups(raw: dict, event_id: int = 0) -> Lineups:
    data = raw.get("data") or {}
    return Lineups(
        event_id=event_id,
        home=_parse_team_lineup(data.get("home") or {}),
        away=_parse_team_lineup(data.get("away") or {}),
    )


def parse_h2h(raw: dict, event_id: int = 0) -> H2H:
    data = raw.get("data") or {}
    s = data.get("previous_meetings_summary") or {}
    matches: list[H2HMatch] = []
    for m in data.get("previous_meetings") or []:
        if not isinstance(m, dict):
            continue
        try:
            matches.append(
                H2HMatch(
                    league_id=int(m.get("league_id", 0) or 0),
                    league_name=m.get("league_name", "") or "",
                    date_utc=_parse_iso_or_epoch(m.get("start_time") or m.get("date")),
                    home_team=m.get("home_team_name") or m.get("home_team", "") or "",
                    away_team=m.get("away_team_name") or m.get("away_team", "") or "",
                    home_score=int(m.get("home_score", 0) or 0),
                    away_score=int(m.get("away_score", 0) or 0),
                )
            )
        except (TypeError, ValueError):
            continue
    return H2H(
        event_id=event_id,
        summary=H2HSummary(
            home_wins=int(s.get("home_wins", 0) or 0),
            home_wins_perc=float(s.get("home_wins_perc", 0) or 0),
            away_wins=int(s.get("away_wins", 0) or 0),
            away_wins_perc=float(s.get("away_wins_perc", 0) or 0),
            draws=int(s.get("draws", 0) or 0),
            draws_perc=float(s.get("draws_perc", 0) or 0),
        ),
        previous_meetings=matches,
    )


def parse_stats_players(raw: dict, event_id: int = 0) -> PlayerStats:
    return PlayerStats(event_id=event_id, raw=raw.get("data") or {})


# ============================================================
# Fase B — markets / catalog / matchhub parsers
# ============================================================


def _parse_market(m: dict) -> BetanoMarket:
    handicap_raw = m.get("handicap")
    return BetanoMarket(
        id=int(m.get("id", 0) or 0),
        type_code=m.get("type", "") or "",
        type_id=int(m.get("typeId", 0) or 0),
        name=m.get("name", "") or "",
        handicap=float(handicap_raw) if handicap_raw is not None else None,
        selection_ids=[int(s) for s in (m.get("selectionIdList") or []) if s is not None],
        display_order=int(m.get("displayOrder", 0) or 0),
        rendering_layout=int(m.get("renderingLayout", 0) or 0),
        market_close_time_millis=int(m.get("marketCloseTimeMillis", 0) or 0),
    )


def _parse_selection(s: dict) -> BetanoSelection:
    return BetanoSelection(
        id=int(s.get("id", 0) or 0),
        name=s.get("name", "") or "",
        full_name=s.get("fullName", "") or "",
        price=float(s.get("price", 0) or 0),
        type_id=int(s.get("typeId", 0) or 0),
        column_index=int(s.get("columnIndex", 0) or 0),
        display_order=int(s.get("displayOrder", 0) or 0),
    )


def _parse_participants(raw: list) -> list[BetanoParticipant]:
    out: list[BetanoParticipant] = []
    for p in raw or []:
        if not isinstance(p, dict):
            continue
        out.append(
            BetanoParticipant(
                name=p.get("name", "") or "",
                is_home=bool(p.get("isHome", False)),
                team_id=int(p.get("teamId", 0) or 0),
                color=p.get("color"),
            )
        )
    return out


def _parse_live_data(ev: dict) -> BetanoLiveData:
    return BetanoLiveData(
        score_home=int(_safe(ev, "liveData", "score", "home", default=0) or 0),
        score_away=int(_safe(ev, "liveData", "score", "away", default=0) or 0),
        clock_seconds=int(_safe(ev, "liveData", "clock", "secondsSinceStart", default=0) or 0),
    )


def _parse_incidents(raw: list) -> list[BetanoIncident]:
    out: list[BetanoIncident] = []
    for i in raw or []:
        if not isinstance(i, dict):
            continue
        out.append(
            BetanoIncident(
                type=i.get("type", "") or "",
                description=i.get("description", "") or "",
                props=i.get("props") or {},
            )
        )
    return out


def parse_event_snapshot(raw: dict) -> EventSnapshot:
    """Parse de `/danae-webapi/api/live/events/{id}/latest`."""
    ev = raw.get("event") or {}
    if not ev or "id" not in ev:
        raise BetanoParseError("event_latest sem event.id")
    markets_raw = raw.get("markets") or {}
    selections_raw = raw.get("selections") or {}

    bm_id = ev.get("betradarMatchId")
    return EventSnapshot(
        event_id=int(ev["id"]),
        sport_id=ev.get("sportId", "") or "",
        league_id=int(ev.get("leagueId", 0) or 0),
        zone_id=int(ev.get("zoneId", 0) or 0),
        is_live=bool(ev.get("isLive", False)),
        start_time=_parse_iso_or_epoch(ev.get("startTime")),
        participants=_parse_participants(ev.get("participants") or []),
        live_data=_parse_live_data(ev),
        total_markets_available=int(ev.get("totalMarketsAvailable", 0) or 0),
        betradar_match_id=int(bm_id) if bm_id is not None else None,
        incidents=_parse_incidents(ev.get("incidents") or []),
        url=ev.get("url", "") or "",
        markets={int(mid): _parse_market(m) for mid, m in markets_raw.items() if isinstance(m, dict)},
        selections={int(sid): _parse_selection(s) for sid, s in selections_raw.items() if isinstance(s, dict)},
    )


# --- Over/Under extraction ---

_OVER_PREFIXES = ("mais", "over", "+")
_UNDER_PREFIXES = ("menos", "under", "-")


def _is_over(name: str) -> bool:
    n = (name or "").strip().lower()
    return any(n.startswith(p) for p in _OVER_PREFIXES)


def _is_under(name: str) -> bool:
    n = (name or "").strip().lower()
    return any(n.startswith(p) for p in _UNDER_PREFIXES)


def _split_over_under(
    market: BetanoMarket, selections: dict[int, BetanoSelection]
) -> tuple[Optional[BetanoSelection], Optional[BetanoSelection]]:
    over = under = None
    for sid in market.selection_ids:
        sel = selections.get(sid)
        if not sel:
            continue
        if _is_over(sel.name):
            over = sel
        elif _is_under(sel.name):
            under = sel
    # Fallback: se nomes não casaram mas há exatamente 2 selections, assume [over, under].
    if (over is None or under is None) and len(market.selection_ids) == 2:
        s0 = selections.get(market.selection_ids[0])
        s1 = selections.get(market.selection_ids[1])
        if s0 and s1 and over is None and under is None:
            over, under = s0, s1
    return over, under


def _pick_main_line(
    matching: list[BetanoMarket], selections: dict[int, BetanoSelection]
) -> Optional[BetanoMarket]:
    """Linha cuja odd do Over está mais próxima de 1.95 (= equilibrada)."""
    best: Optional[BetanoMarket] = None
    best_dist = float("inf")
    for m in matching:
        if not m.selection_ids:
            continue
        over, _ = _split_over_under(m, selections)
        if not over:
            continue
        dist = abs(over.price - 1.95)
        if dist < best_dist:
            best_dist = dist
            best = m
    return best


def extract_over_under(
    snap: EventSnapshot, type_code: str, linha: Optional[float] = None
) -> Optional[BetanoOverUnder]:
    matching = [m for m in snap.markets.values() if m.type_code == type_code]
    if linha is not None:
        matching = [m for m in matching if m.handicap == linha]
    if not matching:
        return None
    market = matching[0] if linha is not None else _pick_main_line(matching, snap.selections)
    if not market:
        return None
    over, under = _split_over_under(market, snap.selections)
    if not over or not under:
        return None
    return BetanoOverUnder(
        event_id=snap.event_id,
        market_code=type_code,
        handicap=float(market.handicap or 0),
        odd_over=over.price,
        odd_under=under.price,
    )


# --- Live overview catalog ---


def parse_live_overview_events(raw: dict) -> list[BetanoLiveEvent]:
    """Parse de `/danae-webapi/api/live/overview/latest`."""
    events_raw = raw.get("events") or {}
    out: list[BetanoLiveEvent] = []
    for eid, ev in events_raw.items():
        if not isinstance(ev, dict):
            continue
        try:
            bm_id = ev.get("betradarMatchId")
            out.append(
                BetanoLiveEvent(
                    event_id=int(ev.get("id", eid) or 0),
                    sport_id=ev.get("sportId", "") or "",
                    league_id=int(ev.get("leagueId", 0) or 0),
                    zone_id=int(ev.get("zoneId", 0) or 0),
                    participants=_parse_participants(ev.get("participants") or []),
                    start_time=_parse_iso_or_epoch(ev.get("startTime")),
                    is_live=bool(ev.get("isLive", False)),
                    will_go_live=bool(ev.get("willGoLive", False)),
                    total_markets_available=int(ev.get("totalMarketsAvailable", 0) or 0),
                    betradar_match_id=int(bm_id) if bm_id is not None else None,
                    url=ev.get("url", "") or "",
                )
            )
        except (TypeError, ValueError):
            continue
    return out


# --- statsplayer mapping ---


def parse_statsplayer(raw: dict, event_id: int) -> BetanoStatsPlayerMapping:
    """Extrai matchIds Sportradar (statType=4) e Opta (statType=6)."""
    models = _safe(raw, "data", "statPlayerModels", default=[]) or []
    sr_id: Optional[str] = None
    opta_id: Optional[str] = None
    types: list[int] = []
    for m in models:
        if not isinstance(m, dict):
            continue
        t = m.get("statType")
        if t is None:
            continue
        try:
            types.append(int(t))
        except (TypeError, ValueError):
            continue
        mid = str(m.get("matchId") or "")
        if not mid:
            continue
        if int(t) == 4 and mid.isdigit():
            sr_id = mid
        elif int(t) == 6:
            opta_id = mid
    return BetanoStatsPlayerMapping(
        event_id=event_id,
        sr_match_id=sr_id,
        opta_match_id=opta_id,
        available_stat_types=types,
    )


# --- matchhub MatchEvent ---


def _build_match_event(data: dict) -> MatchEvent:
    ed = data.get("event_data") or {}
    bp = ed.get("ball_position") or {}
    bpe = ed.get("ball_position_end") or {}
    return MatchEvent(
        opta_match_id=str(data.get("event_match_id") or ""),
        sportsbook_match_id=int(data.get("sportsbook_match_id", 0) or 0),
        event_type=int(data.get("event_type", -1) if data.get("event_type") is not None else -1),
        period_id=int(data.get("event_period_id", 0) or 0),
        minute=int(data.get("event_match_minute", 0) or 0),
        seconds=int(data.get("event_match_second", 0) or 0),
        team_id=ed.get("team_id"),
        player_id=ed.get("player_id"),
        x=bp.get("x") if isinstance(bp.get("x"), (int, float)) else None,
        y=bp.get("y") if isinstance(bp.get("y"), (int, float)) else None,
        x_end=bpe.get("x") if isinstance(bpe.get("x"), (int, float)) else None,
        y_end=bpe.get("y") if isinstance(bpe.get("y"), (int, float)) else None,
        is_attack=bool(ed.get("is_attack", False)),
        is_dangerous_attack=bool(ed.get("is_dangerous_attack", False)),
        is_possession=bool(ed.get("is_possession", False)),
        is_dangerous=bool(ed.get("is_dangerous", False)),
        provider_type=str(data.get("event_provider_type") or "?"),
        raw=data,
    )


def parse_match_event(arg_str: str) -> MatchEvent:
    """Parse de uma string JSON do WS `matchhub` (target=MatchEvent)."""
    data = json.loads(arg_str) if isinstance(arg_str, str) else arg_str
    if not isinstance(data, dict):
        raise BetanoParseError("matchhub MatchEvent não é dict")
    return _build_match_event(data)


def parse_match_event_initial(data: dict) -> Optional[MatchEvent]:
    """Parse da primeira resposta do `Subscribe` (type=3 completion)."""
    if not isinstance(data, dict) or "event_data" not in data:
        return None
    return _build_match_event(data)
