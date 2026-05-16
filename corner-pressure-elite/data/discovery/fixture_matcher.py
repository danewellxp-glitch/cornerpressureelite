"""Resolve evento Betano → fixture API-Football.

Estratégia em 2 camadas:
1. Lookup determinístico via `betano_team_map.api_football_team_id`
   (somente se ambos times do match já foram mapeados antes).
2. Fallback fuzzy: rapidfuzz.fuzz.ratio sobre nomes normalizados, com
   validação de kickoff (±N minutos). Se match >= threshold, UPSERT
   teams no map pra acelerar próximas resoluções.

O matcher é stateless de IO de fixtures — o caller (worker) injeta o
pool de candidate_fixtures (geralmente o get_today_schedule cacheado
do api_client). Mantém o matcher fácil de testar e desacoplado.
"""
from __future__ import annotations

import logging
import re
import unicodedata
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional, Sequence

from rapidfuzz import fuzz

from data.repositories.betano_team_map import BetanoTeamEntry, BetanoTeamMapRepo

log = logging.getLogger("cpes.discovery.fixture_matcher")


@dataclass(frozen=True)
class MatchResult:
    fixture_id: int
    betano_event_id: int
    confidence: float
    method: str  # 'team_id_lookup' | 'fuzzy'
    home_team: Optional[str] = None
    away_team: Optional[str] = None
    league_id: Optional[int] = None
    kickoff_utc: Optional[datetime] = None


class FixtureMatcher:
    def __init__(
        self,
        team_repo: BetanoTeamMapRepo,
        confidence_threshold: float = 0.85,
    ):
        self._team_repo = team_repo
        self._threshold = float(confidence_threshold)

    async def match_event(
        self,
        betano_event: dict,
        candidate_fixtures: Sequence[dict],
        tolerance_minutes: int = 30,
    ) -> Optional[MatchResult]:
        """Tenta achar fixture API-Football compatível com o evento Betano.

        Args:
            betano_event: dict do bridge /events/live (com participants[],
                start_time_ms, event_id, etc).
            candidate_fixtures: fixtures API-Football no formato bruto
                (com `fixture.id`, `fixture.date`, `teams.home/away.{id,name}`,
                `league.id`). Caller injeta — tipicamente get_today_schedule.
            tolerance_minutes: janela de match de kickoff.

        Returns:
            MatchResult se confidence >= threshold; None caso contrário.
            Quando match é via fuzzy, os teams envolvidos são UPSERTed em
            betano_team_map pra próximos lookups serem determinísticos.
        """
        participants = betano_event.get("participants") or []
        home_p = _pick_home(participants)
        away_p = _pick_away(participants, home_p)
        if not (home_p and away_p):
            log.debug(
                "match_event sem 2 participants identificáveis event_id=%s",
                betano_event.get("event_id"),
            )
            return None

        # 1. Lookup determinístico
        home_entry = await self._team_repo.get_by_betano_id(int(home_p["team_id"]))
        away_entry = await self._team_repo.get_by_betano_id(int(away_p["team_id"]))
        if (home_entry and home_entry.api_football_team_id
                and away_entry and away_entry.api_football_team_id):
            fixture = _find_fixture_by_teams_and_kickoff(
                candidate_fixtures,
                home_af_id=home_entry.api_football_team_id,
                away_af_id=away_entry.api_football_team_id,
                kickoff_ms=betano_event.get("start_time_ms"),
                tolerance_minutes=tolerance_minutes,
            )
            if fixture:
                return _build_result(
                    fixture=fixture,
                    betano_event_id=int(betano_event["event_id"]),
                    confidence=1.0,
                    method="team_id_lookup",
                )

        # 2. Fallback fuzzy
        return await self._fuzzy_match(
            betano_event=betano_event,
            candidate_fixtures=candidate_fixtures,
            home_p=home_p,
            away_p=away_p,
            tolerance_minutes=tolerance_minutes,
        )

    async def _fuzzy_match(
        self,
        betano_event: dict,
        candidate_fixtures: Sequence[dict],
        home_p: dict,
        away_p: dict,
        tolerance_minutes: int,
    ) -> Optional[MatchResult]:
        home_name = home_p.get("name") or ""
        away_name = away_p.get("name") or ""
        kickoff_ms = betano_event.get("start_time_ms")
        betano_dt = _ms_to_datetime(kickoff_ms)
        tol = timedelta(minutes=tolerance_minutes)

        norm_betano_home = _normalize_team_name(home_name)
        norm_betano_away = _normalize_team_name(away_name)

        best: Optional[dict] = None
        best_score = 0.0
        for f in candidate_fixtures:
            af_home = (f.get("teams", {}).get("home", {}) or {}).get("name", "")
            af_away = (f.get("teams", {}).get("away", {}) or {}).get("name", "")
            af_dt = _parse_iso((f.get("fixture", {}) or {}).get("date", ""))

            if betano_dt and af_dt and abs(af_dt - betano_dt) > tol:
                continue

            score_home = fuzz.ratio(norm_betano_home, _normalize_team_name(af_home)) / 100.0
            score_away = fuzz.ratio(norm_betano_away, _normalize_team_name(af_away)) / 100.0
            score = (score_home + score_away) / 2.0

            if score > best_score:
                best_score = score
                best = f

        if not (best and best_score >= self._threshold):
            return None

        # UPSERT teams resolvidos pra próximos lookups serem determinísticos
        await self._team_repo.bulk_upsert(
            [
                BetanoTeamEntry(
                    betano_team_id=int(home_p["team_id"]),
                    betano_team_name=home_name,
                    api_football_team_id=int(best["teams"]["home"]["id"]),
                    api_football_team_name=best["teams"]["home"]["name"],
                    match_method="fuzzy",
                    match_confidence=round(best_score, 2),
                ),
                BetanoTeamEntry(
                    betano_team_id=int(away_p["team_id"]),
                    betano_team_name=away_name,
                    api_football_team_id=int(best["teams"]["away"]["id"]),
                    api_football_team_name=best["teams"]["away"]["name"],
                    match_method="fuzzy",
                    match_confidence=round(best_score, 2),
                ),
            ]
        )

        return _build_result(
            fixture=best,
            betano_event_id=int(betano_event["event_id"]),
            confidence=round(best_score, 2),
            method="fuzzy",
        )


# ============================================================
# Helpers (puros — testáveis isoladamente)
# ============================================================

# Sufixos/prefixos comuns em nomes de clube — ruído pra comparação.
# Dois patterns: tokens-com-paren (sem boundary, porque "(" é non-word)
# e tokens-palavra (com boundary).
_TEAM_NOISE_PAREN = re.compile(
    r"\((f|m|esports?|jr|junior|sub-?\d+|u\d+|reservas?|b)\)",
    flags=re.IGNORECASE,
)
_TEAM_NOISE_WORDS = re.compile(
    r"\b(fc|sc|cf|cd|ac|aj|fk|sk|club|de futbol|de futebol|esports?|"
    r"jr|junior|sub-?\d+|u\d+|reservas?)\b",
    flags=re.IGNORECASE,
)


def _normalize_team_name(name: str) -> str:
    """lowercase + sem acentos + remove ruído + collapsa espaços."""
    if not name:
        return ""
    s = name.lower().strip()
    # Remove acentos
    s = "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c))
    s = _TEAM_NOISE_PAREN.sub("", s)
    s = _TEAM_NOISE_WORDS.sub("", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def _pick_home(participants: Sequence[dict]) -> Optional[dict]:
    """Escolhe o home: prefere is_home=True; cai pro primeiro da lista (Betano usa is_home=null no away)."""
    for p in participants:
        if p.get("is_home") is True:
            return p
    return participants[0] if participants else None


def _pick_away(participants: Sequence[dict], home: Optional[dict]) -> Optional[dict]:
    if not participants or not home:
        return None
    for p in participants:
        if p is home:
            continue
        return p
    return None


def _ms_to_datetime(ms: Optional[int]) -> Optional[datetime]:
    if not ms:
        return None
    try:
        return datetime.fromtimestamp(int(ms) / 1000, tz=timezone.utc)
    except (ValueError, OSError):
        return None


def _parse_iso(date_str: str) -> Optional[datetime]:
    if not date_str:
        return None
    try:
        return datetime.fromisoformat(date_str.replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None


def _find_fixture_by_teams_and_kickoff(
    fixtures: Sequence[dict],
    home_af_id: int,
    away_af_id: int,
    kickoff_ms: Optional[int],
    tolerance_minutes: int,
) -> Optional[dict]:
    betano_dt = _ms_to_datetime(kickoff_ms)
    tol = timedelta(minutes=tolerance_minutes)
    for f in fixtures:
        t = f.get("teams", {}) or {}
        if (t.get("home", {}) or {}).get("id") != home_af_id:
            continue
        if (t.get("away", {}) or {}).get("id") != away_af_id:
            continue
        if betano_dt:
            af_dt = _parse_iso((f.get("fixture", {}) or {}).get("date", ""))
            if af_dt and abs(af_dt - betano_dt) > tol:
                continue
        return f
    return None


def _build_result(
    fixture: dict,
    betano_event_id: int,
    confidence: float,
    method: str,
) -> MatchResult:
    f_meta = fixture.get("fixture", {}) or {}
    teams = fixture.get("teams", {}) or {}
    league = fixture.get("league", {}) or {}
    return MatchResult(
        fixture_id=int(f_meta.get("id")),
        betano_event_id=betano_event_id,
        confidence=confidence,
        method=method,
        home_team=(teams.get("home", {}) or {}).get("name"),
        away_team=(teams.get("away", {}) or {}).get("name"),
        league_id=league.get("id"),
        kickoff_utc=_parse_iso(f_meta.get("date", "")),
    )
