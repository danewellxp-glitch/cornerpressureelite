"""Discovery nativo SofaScore (Sprint N — base do A2).

Em vez de descobrir a agenda via API-Football (`get_today_schedule`), busca os
jogos do dia direto no SofaScore, **por torneio** (um request por liga monitorada
que tenha mapeamento em SOFASCORE_LEAGUE_MAP). Resultado é keyed por
`sofa_event_id` — a chave que o A2 vai promover a primária.

NÃO substitui o AF ainda (flag SOFASCORE_DISCOVERY_ENABLED default OFF). Por ora
serve pra: (a) comparar cobertura vs AF, (b) ser o source-of-truth do discovery
quando o A2 virar a chave.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

from rapidfuzz import fuzz

from .league_map import get_sofascore_ids

log = logging.getLogger("cpes.providers.sofascore.discovery")

# Mesmo threshold do SofaScoreEventResolver (fuzzy ratio médio home+away).
_MATCH_THRESHOLD = 85.0

# status.type do SofaScore que contam como "monitorável" (futuro/ao vivo).
_OPEN_STATUS = {"notstarted", "inprogress"}


@dataclass(frozen=True)
class SofaFixture:
    sofa_event_id: int
    af_league_id: int
    home_team: str
    away_team: str
    kickoff_utc: Optional[datetime]
    status_type: str          # notstarted | inprogress | finished | ...

    @property
    def is_open(self) -> bool:
        return self.status_type in _OPEN_STATUS


def _normalize(ev: dict, af_league_id: int) -> Optional[SofaFixture]:
    eid = ev.get("id")
    if not isinstance(eid, int):
        return None
    home = (ev.get("homeTeam") or {}).get("name")
    away = (ev.get("awayTeam") or {}).get("name")
    if not home or not away:
        return None
    ts = ev.get("startTimestamp")
    kickoff = (
        datetime.fromtimestamp(ts, tz=timezone.utc) if isinstance(ts, int) else None
    )
    status_type = (ev.get("status") or {}).get("type") or "unknown"
    return SofaFixture(
        sofa_event_id=eid,
        af_league_id=af_league_id,
        home_team=home,
        away_team=away,
        kickoff_utc=kickoff,
        status_type=status_type,
    )


async def discover_scheduled(
    client,
    af_league_ids: list[int],
    date: str,
    *,
    only_open: bool = False,
) -> list[SofaFixture]:
    """Agenda do dia via SofaScore, por torneio. `date` = YYYY-MM-DD.

    `only_open=True` filtra pra notstarted/inprogress (descarta finished).
    Ligas sem mapeamento em SOFASCORE_LEAGUE_MAP são puladas (logadas).
    """
    out: list[SofaFixture] = []
    for af_lid in af_league_ids:
        ids = get_sofascore_ids(af_lid)
        if ids is None:
            log.debug("discovery.skip_unmapped af_league=%d", af_lid)
            continue
        tid = ids[0]
        try:
            events = await client.get_tournament_scheduled_events(tid, date)
        except Exception as e:
            log.warning("discovery.tournament_error af_league=%d tid=%d err=%s",
                        af_lid, tid, e)
            continue
        for ev in events or []:
            fx = _normalize(ev, af_lid)
            if fx is None:
                continue
            if only_open and not fx.is_open:
                continue
            out.append(fx)
    log.info("discovery.scheduled date=%s ligas=%d fixtures=%d (only_open=%s)",
             date, len(af_league_ids), len(out), only_open)
    return out


@dataclass(frozen=True)
class CoverageReport:
    """Comparação shadow entre a agenda AF (atual) e a agenda SofaScore (futura).

    Mede o que o cutover A2 ganharia/perderia se trocasse a fonte do discovery:
      - `af_only`: jogos que o AF vê e o SofaScore NÃO → o cutover PERDERIA.
      - `sofa_only`: jogos que só o SofaScore vê → o cutover GANHARIA (ou ruído).
    """
    af_total: int
    sofa_total: int
    matched: int
    af_only: list[tuple[int, str, str]]   # (af_league_id, home, away) sem par Sofa
    sofa_only: list[SofaFixture]          # Sofa sem par AF

    @property
    def af_match_pct(self) -> float:
        return 100.0 * self.matched / self.af_total if self.af_total else 0.0


def compare_coverage(
    af_fixtures: list[tuple[int, str, str]],
    sofa_fixtures: list[SofaFixture],
    *,
    threshold: float = _MATCH_THRESHOLD,
) -> CoverageReport:
    """Casa a agenda AF com a agenda SofaScore (puro in-memory, zero I/O).

    `af_fixtures`: tuplas `(af_league_id, home_team, away_team)`.
    Match = fuzzy ratio médio (home+away) ≥ `threshold`, restrito à MESMA liga
    (mesma regra do `SofaScoreEventResolver`). Cada Sofa fixture casa com no
    máximo um AF (consumido), pra `sofa_only` ficar exato.
    """
    by_league: dict[int, list[SofaFixture]] = {}
    for sf in sofa_fixtures:
        by_league.setdefault(sf.af_league_id, []).append(sf)

    consumed: set[int] = set()
    matched = 0
    af_only: list[tuple[int, str, str]] = []

    for (lid, home, away) in af_fixtures:
        best_score = -1.0
        best_sf: Optional[SofaFixture] = None
        for sf in by_league.get(lid, []):
            if sf.sofa_event_id in consumed:
                continue
            score = (fuzz.ratio(home, sf.home_team)
                     + fuzz.ratio(away, sf.away_team)) / 2
            if score > best_score:
                best_score = score
                best_sf = sf
        if best_sf is not None and best_score >= threshold:
            consumed.add(best_sf.sofa_event_id)
            matched += 1
        else:
            af_only.append((lid, home, away))

    sofa_only = [sf for sf in sofa_fixtures if sf.sofa_event_id not in consumed]
    return CoverageReport(
        af_total=len(af_fixtures),
        sofa_total=len(sofa_fixtures),
        matched=matched,
        af_only=af_only,
        sofa_only=sofa_only,
    )
