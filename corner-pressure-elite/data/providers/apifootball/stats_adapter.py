"""Adapter `StatsProvider` para `data.api_client.APIFootballClient`.

Consolida `get_fixture_by_id` (minuto, placar) + `get_statistics` (corners,
yellow, etc) em `CanonicalStats`.
"""
from __future__ import annotations

import logging
from typing import Optional

from data.odds_provider import CanonicalFixture
from data.stats_provider import CanonicalStats
from utils.helpers import extrair_estatistica

log = logging.getLogger("cpes.providers.apifootball.stats")


def _i(value, default: int = 0) -> int:
    if value is None:
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        # API às vezes manda string com sufixo, ex. "65%"
        try:
            return int(str(value).rstrip("%"))
        except (TypeError, ValueError):
            return default


class APIFootballStatsProvider:
    name = "apifootball"

    def __init__(self, api_client):
        self._c = api_client

    async def get_stats(self, fixture: CanonicalFixture) -> Optional[CanonicalStats]:
        try:
            raw_fixture = await self._c.get_fixture_by_id(fixture.fixture_id)
            stats_list = await self._c.get_statistics(fixture.fixture_id)
        except Exception as e:
            log.warning("apifootball.stats.fetch_error fixture=%d err=%s", fixture.fixture_id, e)
            return None
        if not stats_list:
            return None

        minute = 0
        score_home = fixture.score_home
        score_away = fixture.score_away
        if raw_fixture:
            status = (raw_fixture.get("fixture") or {}).get("status") or {}
            minute = _i(status.get("elapsed"))
            goals = raw_fixture.get("goals") or {}
            score_home = _i(goals.get("home"), default=score_home)
            score_away = _i(goals.get("away"), default=score_away)

        ch = _i(extrair_estatistica(stats_list, 0, "Corner Kicks"))
        ca = _i(extrair_estatistica(stats_list, 1, "Corner Kicks"))
        yh = _i(extrair_estatistica(stats_list, 0, "Yellow Cards"))
        ya = _i(extrair_estatistica(stats_list, 1, "Yellow Cards"))
        rh = _i(extrair_estatistica(stats_list, 0, "Red Cards"))
        ra = _i(extrair_estatistica(stats_list, 1, "Red Cards"))
        sh = _i(extrair_estatistica(stats_list, 0, "Shots on Goal"))
        sa = _i(extrair_estatistica(stats_list, 1, "Shots on Goal"))
        dh = _i(extrair_estatistica(stats_list, 0, "Dangerous Attacks"))
        da = _i(extrair_estatistica(stats_list, 1, "Dangerous Attacks"))
        ph = _i(extrair_estatistica(stats_list, 0, "Ball Possession"))
        pa = _i(extrair_estatistica(stats_list, 1, "Ball Possession"))
        # A API-Football não tem xG no live; ficam 0.0
        return CanonicalStats(
            fixture_id=fixture.fixture_id,
            source=self.name,
            minute=minute,
            score_home=score_home,
            score_away=score_away,
            corners_home=ch,
            corners_away=ca,
            yellow_cards_home=yh,
            yellow_cards_away=ya,
            red_cards_home=rh,
            red_cards_away=ra,
            shots_on_target_home=sh,
            shots_on_target_away=sa,
            dangerous_attacks_home=dh,
            dangerous_attacks_away=da,
            possession_home=ph,
            possession_away=pa,
            x_goals_home=0.0,
            x_goals_away=0.0,
            provider_pressure=None,
            raw={"stats": stats_list, "fixture": raw_fixture},
        )

    async def healthcheck(self) -> bool:
        try:
            status = await self._c.check_status()
        except Exception as e:
            log.warning("apifootball.stats.healthcheck.error err=%s", e)
            return False
        return bool(status)
