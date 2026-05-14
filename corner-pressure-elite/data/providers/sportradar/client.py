"""Cliente HTTP para a CDN gismo da Sportradar.

Headers e fingerprint: master §3.6 e §13.4 + harness Fase A §4.7, §5.3.

- `curl_cffi.requests.AsyncSession` com `impersonate="chrome131"` para
  passar JA3 de Chrome real (a CDN aceita anônimo, mas detecta Python puro).
- Headers `Origin` e `Referer` apontando para `https://www.betano.bet.br`
  (validação `act=origincheck` no token).
- Retry 3x com backoff exponencial + jitter; em 401 força refresh do token
  e tenta 1x; em 403/451 retorna `None` (caller cai para fallback);
  em 200 com JSON inválido retorna `None`.
"""
import asyncio
import logging
import random
import time
from typing import Optional

from curl_cffi.requests import AsyncSession

from . import parsers
from .schemas import (
    MatchDetailsExtended,
    MatchInfo,
    MatchSituation,
    MatchTimelineDelta,
    SeasonMeta,
    TeamSeasonStats,
)
from .session import SportradarSession

log = logging.getLogger("cpes.sportradar.client")

BASE = "https://widgets.fn.sportradar.com/betano/pt/Etc:UTC/gismo"

HEADERS = {
    "Accept": "*/*",
    "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
    "Origin": "https://www.betano.bet.br",
    "Referer": "https://www.betano.bet.br/",
    "User-Agent": (
        "Mozilla/5.0 (iPhone; CPU iPhone OS 18_5 like Mac OS X) "
        "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.5 "
        "Mobile/15E148 Safari/604.1"
    ),
    "Sec-Fetch-Site": "cross-site",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Dest": "empty",
}

# matchId estável usado pelo healthcheck — jogo encerrado, payload imutável.
# Origem: master §4 (Internacional×Athletic-MG, eventId 84591315).
HEALTHCHECK_MATCH_ID = "70401284"

MAX_ATTEMPTS = 3


class SportradarClient:
    """Wrappers tipados para os 10 endpoints gismo principais."""

    def __init__(
        self,
        session: SportradarSession,
        proxy: Optional[str] = None,
        timeout: float = 15.0,
    ):
        self._sr_session = session
        self._http = AsyncSession(
            impersonate="chrome131",
            proxies=(
                {"http": proxy, "https": proxy} if proxy else None
            ),
            timeout=timeout,
        )

    async def close(self) -> None:
        await self._http.close()

    async def __aenter__(self) -> "SportradarClient":
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        await self.close()

    async def _get(self, endpoint: str, id_: str) -> Optional[dict]:
        """GET genérico com retry, refresh em 401, fallback em 403/451.

        Retorna dict do JSON em 200; `None` em qualquer outro caminho que
        o caller deve tratar como "sem dado". Try/except aqui é fronteira
        (HTTP externa) — autorizado pelo CLAUDE.md §7.
        """
        url = f"{BASE}/{endpoint}/{id_}"
        for attempt in range(MAX_ATTEMPTS):
            token = await self._sr_session.get_or_refresh()
            full_url = f"{url}?{token}"
            t0 = time.monotonic()
            try:
                r = await self._http.get(full_url, headers=HEADERS)
            except Exception as e:
                dur_ms = (time.monotonic() - t0) * 1000
                log.warning(
                    "sportradar.get.network_error endpoint=%s id=%s "
                    "attempt=%d dur_ms=%.0f err=%s",
                    endpoint, id_, attempt, dur_ms, e,
                )
                await asyncio.sleep((2 ** attempt) + random.random())
                continue

            dur_ms = (time.monotonic() - t0) * 1000
            log.info(
                "sportradar.get endpoint=%s id=%s status=%d "
                "dur_ms=%.0f attempt=%d ttl_s=%d",
                endpoint, id_, r.status_code, dur_ms, attempt,
                self._sr_session.ttl_remaining(),
            )

            if r.status_code == 200:
                try:
                    return r.json()
                except Exception as e:
                    log.warning(
                        "sportradar.get.json_decode endpoint=%s err=%s",
                        endpoint, e,
                    )
                    return None

            if r.status_code == 401 and attempt == 0:
                # Token expirou no servidor antes do exp local.
                # Força refresh e tenta de novo.
                log.warning(
                    "sportradar.get.401 endpoint=%s — forcing token refresh",
                    endpoint,
                )
                self._sr_session._exp = 0  # noqa: SLF001
                continue

            if r.status_code in (403, 451):
                log.warning(
                    "sportradar.get.blocked endpoint=%s status=%d",
                    endpoint, r.status_code,
                )
                return None

            # 5xx ou outros → backoff
            await asyncio.sleep((2 ** attempt) + random.random())

        log.warning(
            "sportradar.get.exhausted endpoint=%s id=%s attempts=%d",
            endpoint, id_, MAX_ATTEMPTS,
        )
        return None

    async def match_info(self, match_id: str) -> Optional[MatchInfo]:
        raw = await self._get("match_info", str(match_id))
        return parsers.parse_match_info(raw) if raw else None

    async def match_details_extended(
        self, match_id: str
    ) -> Optional[MatchDetailsExtended]:
        raw = await self._get("match_detailsextended", str(match_id))
        return parsers.parse_details_extended(raw) if raw else None

    async def match_timeline(self, match_id: str) -> Optional[list]:
        raw = await self._get("match_timeline", str(match_id))
        return parsers.parse_timeline_full(raw) if raw else None

    async def get_timeline_delta(
        self, match_id: str, since_uts: int = 0
    ) -> Optional[MatchTimelineDelta]:
        """`match_timelinedelta` (heartbeat).

        O gismo, na captura do master §3.4, não expôs query param de cursor
        — retorna timeline inteira e o caller filtra por `since_uts`.
        O spike confirma se há query param oficial; até lá, filtragem
        client-side.
        """
        raw = await self._get("match_timelinedelta", str(match_id))
        return (
            parsers.parse_timeline_delta(raw, since_uts) if raw else None
        )

    async def stats_match_situation(
        self, match_id: str
    ) -> Optional[MatchSituation]:
        raw = await self._get("stats_match_situation", str(match_id))
        return parsers.parse_match_situation(raw) if raw else None

    async def stats_match_form(self, match_id: str) -> Optional[dict]:
        # Schema concreto a definir após captura — parser passa o raw.
        raw = await self._get("stats_match_form", str(match_id))
        return raw

    async def stats_season_meta(
        self, season_id: str
    ) -> Optional[SeasonMeta]:
        raw = await self._get("stats_season_meta", str(season_id))
        return parsers.parse_season_meta(raw) if raw else None

    async def stats_season_uniqueteamstats(
        self, season_id: str
    ) -> Optional[list[TeamSeasonStats]]:
        raw = await self._get(
            "stats_season_uniqueteamstats", str(season_id)
        )
        return parsers.parse_team_season_stats(raw) if raw else None

    async def stats_season_tables(self, season_id: str) -> Optional[dict]:
        raw = await self._get("stats_season_tables", str(season_id))
        return raw

    async def stats_cup_brackets(self, match_id: str) -> Optional[dict]:
        # path especial: "gm-{matchId}" (master §3.4)
        raw = await self._get("stats_cup_brackets", f"gm-{match_id}")
        return raw

    async def healthcheck(self) -> bool:
        """Chama `match_info` para um match estável conhecido."""
        return await self.match_info(HEALTHCHECK_MATCH_ID) is not None
