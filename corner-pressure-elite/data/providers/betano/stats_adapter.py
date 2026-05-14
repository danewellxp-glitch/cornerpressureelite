"""Adapter `StatsProvider` para a stack Betano (StatsStream Opta-backed).

Consolida `get_stats_detailed` + `get_momentum` em `CanonicalStats`. Score e
minuto saem de `get_info_aggregated` (1 chamada extra) — alternativa cara, mas
a stats_detailed por si só não carrega o clock.
"""
from __future__ import annotations

import logging
from typing import Optional

from data.odds_provider import CanonicalFixture
from data.stats_provider import CanonicalStats

from .catalog import BetanoCatalog
from .session import BetanoSession
from .statsstream import BetanoStatsStream

log = logging.getLogger("cpes.providers.betano.stats")


class BetanoStatsProvider:
    name = "betano"

    def __init__(
        self,
        session: BetanoSession,
        stream: BetanoStatsStream,
        catalog: BetanoCatalog,
        fixture_repo=None,
    ):
        self._session = session
        self._stream = stream
        self._catalog = catalog
        self._fixture_repo = fixture_repo
        self._event_id_cache: dict[int, int] = {}

    async def get_stats(self, fixture: CanonicalFixture) -> Optional[CanonicalStats]:
        event_id = await self._resolve_event_id(fixture)
        if not event_id:
            return None
        detailed = await self._stream.get_stats_detailed(event_id)
        if not detailed:
            return None
        momentum = await self._stream.get_momentum(event_id)
        latest_pressure: Optional[float] = None
        if momentum and momentum.points:
            latest_pressure = float(momentum.points[-1].pressure)

        # Stats Opta não vêm com clock. Tenta `info/aggregated` somente como
        # fallback; em produção orquestrador pode preencher.
        minute = 0
        score_home = fixture.score_home
        score_away = fixture.score_away
        try:
            info = await self._stream.get_info_aggregated(event_id)
            if info:
                # current_period é 1=1T, 2=2T, ...; minuto exato fica para o
                # caller. Aqui só fica explícito que é live.
                if info.started:
                    minute = max(minute, 1)
        except Exception:
            pass

        h_total = detailed.home.total
        a_total = detailed.away.total
        return CanonicalStats(
            fixture_id=fixture.fixture_id,
            source=self.name,
            minute=minute,
            score_home=int(h_total.goals or score_home),
            score_away=int(a_total.goals or score_away),
            corners_home=int(h_total.corners),
            corners_away=int(a_total.corners),
            yellow_cards_home=int(h_total.yellow_cards),
            yellow_cards_away=int(a_total.yellow_cards),
            red_cards_home=int(h_total.red_cards),
            red_cards_away=int(a_total.red_cards),
            shots_on_target_home=int(h_total.shots_on_target),
            shots_on_target_away=int(a_total.shots_on_target),
            dangerous_attacks_home=int(h_total.dangerous_attacks),
            dangerous_attacks_away=int(a_total.dangerous_attacks),
            possession_home=int(h_total.possession),
            possession_away=int(a_total.possession),
            x_goals_home=float(h_total.x_goals_live),
            x_goals_away=float(a_total.x_goals_live),
            provider_pressure=latest_pressure,
            raw={"event_id": event_id},
        )

    async def healthcheck(self) -> bool:
        try:
            return await self._stream.healthcheck()
        except Exception as e:
            log.warning("betano.stats.healthcheck.error err=%s", e)
            return False

    async def _resolve_event_id(self, fixture: CanonicalFixture) -> Optional[int]:
        cached = self._event_id_cache.get(fixture.fixture_id)
        if cached:
            return cached
        if self._fixture_repo is not None:
            try:
                ev = await self._fixture_repo.get_betano_event_id(fixture.fixture_id)
            except Exception:
                ev = None
            if ev:
                self._event_id_cache[fixture.fixture_id] = ev
                return ev
        try:
            ev = await self._catalog.find_event_by_fixture(
                fixture_id=fixture.fixture_id,
                team_home=fixture.home_team,
                team_away=fixture.away_team,
                kickoff_at=fixture.starts_at_utc,
                league_id_hint=fixture.league_id,
            )
        except Exception:
            return None
        if ev:
            self._event_id_cache[fixture.fixture_id] = ev
        return ev
