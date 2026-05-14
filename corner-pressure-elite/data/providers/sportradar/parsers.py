"""Parsers puros JSON → schemas tipados.

⚠️ STATUS: best-effort sem `.mitm` golden. Os paths abaixo seguem o
schema documentado no master §3.4/§3.5 e padrões gismo conhecidos
(`_doc=event`, `doc[0].data.match`, etc), mas a estrutura exata só será
confirmada quando o spike trouxer o flow real. Cada parser com path
duvidoso está marcado `# TODO[spike]:` para revisão.

Princípios (harness Fase A §4.6):
- Funções puras, sem efeito colateral
- Campos opcionais ausentes viram `None`, não exception
- Apenas campo obrigatório ausente (ex. `match.id`) levanta
  `SportradarParseError`
"""
import logging
from typing import Any, Optional

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

log = logging.getLogger("cpes.sportradar.parser")


class SportradarParseError(ValueError):
    """Path obrigatório ausente no payload — schema gismo divergiu."""


def _safe_get(d: Any, *keys: Any, default: Any = None) -> Any:
    """Navega em dict/list aninhado; retorna `default` se qualquer chave
    faltar ou tipo divergir.

    Aceita `int` como chave para indexação de listas (ex. `doc[0]`).
    """
    cur = d
    for k in keys:
        if isinstance(k, int):
            if not isinstance(cur, list) or k >= len(cur) or k < -len(cur):
                return default
            cur = cur[k]
        else:
            if not isinstance(cur, dict) or k not in cur:
                return default
            cur = cur[k]
        if cur is None:
            return default
    return cur


def _as_int(v: Any) -> Optional[int]:
    if v is None:
        return None
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


def _as_float(v: Any) -> Optional[float]:
    if v is None:
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


# ---------------------------------------------------------------------------
# match_info
# ---------------------------------------------------------------------------

def parse_match_info(raw: dict) -> MatchInfo:
    # TODO[spike]: confirmar se gismo retorna sempre wrappado em
    # `doc[0].data.match` ou se algumas versões retornam `data.match`
    # direto. O path abaixo segue padrão observado em master §3.4.
    m = _safe_get(raw, "doc", 0, "data", "match", default={}) or _safe_get(
        raw, "data", "match", default={}
    )
    if not m or "_id" not in m:
        raise SportradarParseError(
            "match_info sem doc[0].data.match._id — schema divergiu"
        )

    return MatchInfo(
        match_id=str(m["_id"]),
        sport_id=_as_int(_safe_get(m, "_sid", default=1)) or 1,
        league_id=_as_int(_safe_get(m, "tournament", "_id")),
        season_id=_as_int(_safe_get(m, "season", "_id")),
        home_team_name=_safe_get(
            m, "teams", "home", "name", default="?"
        ),
        home_team_id=_as_int(_safe_get(m, "teams", "home", "_id")),
        away_team_name=_safe_get(
            m, "teams", "away", "name", default="?"
        ),
        away_team_id=_as_int(_safe_get(m, "teams", "away", "_id")),
        # TODO[spike]: status pode vir como `status.name`, `status.code`,
        # ou `matchstatus`. Cobrir os 3 candidatos.
        status=str(
            _safe_get(m, "status", "name", default=None)
            or _safe_get(m, "status", default="unknown")
        ),
        minute=_as_int(_safe_get(m, "matchstatus", "minute")),
        score_home=_as_int(_safe_get(m, "result", "home")),
        score_away=_as_int(_safe_get(m, "result", "away")),
        coverage=CoverageFlags(
            cornerson=bool(
                _safe_get(m, "coverage", "cornerson", default=False)
            ),
            cardson=bool(
                _safe_get(m, "coverage", "cardson", default=False)
            ),
            lineups=bool(
                _safe_get(m, "coverage", "lineups", default=False)
            ),
            bookings=bool(
                _safe_get(m, "coverage", "bookings", default=False)
            ),
            extended=bool(
                _safe_get(m, "coverage", "extended", default=False)
            ),
        ),
    )


# ---------------------------------------------------------------------------
# match_timeline / match_timelinedelta
# ---------------------------------------------------------------------------

def _parse_event(ev: dict) -> TimelineEvent:
    return TimelineEvent(
        event_id=str(ev.get("_id", "")),
        type=str(ev.get("_doctype", "")),
        type_id=(
            str(ev["_typeid"]) if ev.get("_typeid") is not None else None
        ),
        minute=_as_int(ev.get("time")) or 0,
        seconds=_as_int(ev.get("seconds")) or 0,
        team=ev.get("team"),
        player_name=_safe_get(ev, "player", "name"),
        x=_as_int(ev.get("X")),
        y=_as_int(ev.get("Y")),
        name=ev.get("name"),
        raw=ev,
    )


def parse_timeline_full(raw: dict) -> list[TimelineEvent]:
    events_raw = (
        _safe_get(raw, "doc", 0, "data", "events", default=[])
        or _safe_get(raw, "data", "events", default=[])
        or []
    )
    return [_parse_event(ev) for ev in events_raw if isinstance(ev, dict)]


def parse_timeline_delta(
    raw: dict, since_uts: int = 0
) -> MatchTimelineDelta:
    """Retorna apenas eventos com `seconds > since_uts`.

    `since_uts=0` retorna timeline completa. Filtragem client-side porque
    o gismo (até confirmação no spike) não expõe cursor server-side.
    """
    match_id = str(
        _safe_get(raw, "doc", 0, "data", "match", "_id", default="")
        or _safe_get(raw, "data", "match", "_id", default="")
    )
    events_raw = (
        _safe_get(raw, "doc", 0, "data", "events", default=[])
        or _safe_get(raw, "data", "events", default=[])
        or []
    )
    events: list[TimelineEvent] = []
    last_seconds = since_uts
    for ev in events_raw:
        if not isinstance(ev, dict):
            continue
        seconds = _as_int(ev.get("seconds")) or 0
        if seconds <= since_uts:
            continue
        events.append(_parse_event(ev))
        if seconds > last_seconds:
            last_seconds = seconds
    return MatchTimelineDelta(
        match_id=match_id,
        events=events,
        last_seconds=last_seconds,
    )


# ---------------------------------------------------------------------------
# stats_match_situation
# ---------------------------------------------------------------------------

def parse_match_situation(raw: dict) -> MatchSituation:
    # TODO[spike]: confirmar paths exatos. Master §3.4 lista o endpoint
    # como "Posse, ataque, X/Y da bola" mas não documenta a estrutura
    # interna. Os campos abaixo seguem convenção gismo observada em
    # outros sports.
    d = (
        _safe_get(raw, "doc", 0, "data", default={})
        or _safe_get(raw, "data", default={})
        or {}
    )
    match_id = str(_safe_get(d, "match", "_id", default=""))
    sit = _safe_get(d, "situation", default={}) or {}

    return MatchSituation(
        match_id=match_id,
        possession_home_pct=_as_float(
            _safe_get(sit, "possession", "home")
        ),
        possession_away_pct=_as_float(
            _safe_get(sit, "possession", "away")
        ),
        attack_home_pct=_as_float(_safe_get(sit, "attack", "home")),
        attack_away_pct=_as_float(_safe_get(sit, "attack", "away")),
        dangerous_attack_home_pct=_as_float(
            _safe_get(sit, "dangerousattack", "home")
        ),
        dangerous_attack_away_pct=_as_float(
            _safe_get(sit, "dangerousattack", "away")
        ),
        ball_x=_as_int(_safe_get(sit, "ball", "X")),
        ball_y=_as_int(_safe_get(sit, "ball", "Y")),
        minute=_as_int(_safe_get(sit, "time")),
    )


# ---------------------------------------------------------------------------
# match_detailsextended
# ---------------------------------------------------------------------------

def parse_details_extended(raw: dict) -> MatchDetailsExtended:
    # TODO[spike]: este é o endpoint mais valioso (substitui várias
    # chamadas API-Football). Master §3.4 diz "Match + lineup + injuries
    # + cornerson". Estrutura provável: `doc[0].data.match` + chaves
    # agregadas como `corners`, `cards`, `shots`.
    d = (
        _safe_get(raw, "doc", 0, "data", default={})
        or _safe_get(raw, "data", default={})
        or {}
    )
    match = _safe_get(d, "match", default={}) or {}
    stats = _safe_get(d, "statistics", default={}) or {}

    corners = _safe_get(stats, "corners", default={}) or {}
    cards = _safe_get(stats, "cards", default={}) or {}
    shots = _safe_get(stats, "shots", default={}) or {}

    return MatchDetailsExtended(
        match_id=str(_safe_get(match, "_id", default="")),
        minute=_as_int(_safe_get(match, "matchstatus", "minute")) or 0,
        score_home=_as_int(_safe_get(match, "result", "home")) or 0,
        score_away=_as_int(_safe_get(match, "result", "away")) or 0,
        corners_home=_as_int(_safe_get(corners, "home")) or 0,
        corners_away=_as_int(_safe_get(corners, "away")) or 0,
        yellowcards_home=_as_int(_safe_get(cards, "yellow", "home")) or 0,
        yellowcards_away=_as_int(_safe_get(cards, "yellow", "away")) or 0,
        redcards_home=_as_int(_safe_get(cards, "red", "home")) or 0,
        redcards_away=_as_int(_safe_get(cards, "red", "away")) or 0,
        shots_on_target_home=_as_int(
            _safe_get(shots, "ontarget", "home")
        ) or 0,
        shots_on_target_away=_as_int(
            _safe_get(shots, "ontarget", "away")
        ) or 0,
        shots_total_home=_as_int(_safe_get(shots, "total", "home")) or 0,
        shots_total_away=_as_int(_safe_get(shots, "total", "away")) or 0,
        raw=raw,
    )


# ---------------------------------------------------------------------------
# stats_season_meta
# ---------------------------------------------------------------------------

def parse_season_meta(raw: dict) -> SeasonMeta:
    # TODO[spike]: estrutura exata a confirmar.
    d = (
        _safe_get(raw, "doc", 0, "data", "season", default={})
        or _safe_get(raw, "data", "season", default={})
        or {}
    )
    if not d:
        raise SportradarParseError("season_meta sem data.season")
    return SeasonMeta(
        season_id=_as_int(d.get("_id")) or 0,
        name=str(d.get("name", "")),
        league_id=_as_int(_safe_get(d, "tournament", "_id")) or 0,
        year=_as_int(d.get("year")) or 0,
    )


# ---------------------------------------------------------------------------
# stats_season_uniqueteamstats
# ---------------------------------------------------------------------------

def parse_team_season_stats(raw: dict) -> list[TeamSeasonStats]:
    # TODO[spike]: estrutura exata a confirmar. Provavelmente
    # `data.teams` é lista de times com `statistics` agregadas.
    teams = (
        _safe_get(raw, "doc", 0, "data", "teams", default=[])
        or _safe_get(raw, "data", "teams", default=[])
        or []
    )
    result: list[TeamSeasonStats] = []
    for t in teams:
        if not isinstance(t, dict):
            continue
        s = _safe_get(t, "statistics", default={}) or {}
        result.append(TeamSeasonStats(
            team_id=_as_int(t.get("_id")) or 0,
            team_name=str(t.get("name", "")),
            matches_played=_as_int(s.get("matches_played")) or 0,
            avg_corners_for=_as_float(s.get("avg_corners_for")) or 0.0,
            avg_corners_against=_as_float(
                s.get("avg_corners_against")
            ) or 0.0,
            avg_yellowcards=_as_float(s.get("avg_yellowcards")) or 0.0,
        ))
    return result
