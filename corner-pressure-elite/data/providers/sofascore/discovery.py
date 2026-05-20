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

from .league_map import get_sofascore_ids

log = logging.getLogger("cpes.providers.sofascore.discovery")

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
