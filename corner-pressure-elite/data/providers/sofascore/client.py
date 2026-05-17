"""SofaScoreClient — wrapper async sobre curl_cffi.AsyncSession (Fase K.1 PARTE A).

Bypassa o anti-bot TLS fingerprint (JA3) do SofaScore com
`impersonate='chrome120'` (libcurl-impersonate-chrome via curl_cffi).
Detalhes da investigação K.0 em `docs/architecture/sofascore-api.md`.

Rate limit defensivo cliente-side via token bucket. SofaScore empiricamente
aceita ~47 req/s sustentado (K.0 stress test) — default conservador 10 req/s
mantém margem >100× sobre uso CPES (~0.3 req/s).
"""
from __future__ import annotations

import asyncio
import logging
from typing import Optional

from curl_cffi.requests import AsyncSession

logger = logging.getLogger("cpes.providers.sofascore")


class SofaScoreClientError(Exception):
    """Erros do SofaScoreClient."""


class SofaScoreBlockedError(SofaScoreClientError):
    """403/429 do SofaScore — anti-bot ativou ou rate limit excedido."""


class SofaScoreClient:
    """Cliente HTTP pra SofaScore API.

    Uso:
        async with SofaScoreClient() as client:
            events = await client.get_live_events()
    """

    BASE_URL = "https://api.sofascore.com/api/v1"
    DEFAULT_TIMEOUT = 15.0
    DEFAULT_RATE_LIMIT_PER_SEC = 10

    def __init__(
        self,
        base_url: str = BASE_URL,
        timeout: float = DEFAULT_TIMEOUT,
        rate_limit_per_sec: int = DEFAULT_RATE_LIMIT_PER_SEC,
        impersonate: str = "chrome120",
    ):
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout
        self._impersonate = impersonate
        self._session: Optional[AsyncSession] = None

        # Token bucket — refill lazy (1ª chamada de _acquire_token inicializa
        # _last_refill com o tempo real do loop em execução). Evita NoneType
        # em __init__ quando event loop ainda não está rodando (pytest).
        self._rate_limit = float(rate_limit_per_sec)
        self._tokens = float(rate_limit_per_sec)
        self._last_refill: Optional[float] = None
        self._tokens_lock = asyncio.Lock()

    async def __aenter__(self) -> "SofaScoreClient":
        await self.start()
        return self

    async def __aexit__(self, *args) -> None:
        await self.close()

    async def start(self) -> None:
        if self._session is None:
            self._session = AsyncSession(
                impersonate=self._impersonate,
                timeout=self._timeout,
                headers={
                    "Accept": "application/json, text/plain, */*",
                    "Accept-Language": "en-US,en;q=0.9",
                    "Origin": "https://www.sofascore.com",
                    "Referer": "https://www.sofascore.com/",
                },
            )
            logger.info(
                "sofascore.client.started impersonate=%s rate_limit=%s/s",
                self._impersonate, self._rate_limit,
            )

    async def close(self) -> None:
        if self._session is not None:
            await self._session.close()
            self._session = None
            logger.info("sofascore.client.closed")

    async def _acquire_token(self) -> None:
        """Token bucket: aguarda se rate limit excedido."""
        async with self._tokens_lock:
            now = asyncio.get_event_loop().time()
            if self._last_refill is None:
                self._last_refill = now
            elapsed = now - self._last_refill
            self._tokens = min(
                self._rate_limit,
                self._tokens + elapsed * self._rate_limit,
            )
            self._last_refill = now

            if self._tokens < 1:
                # Aguardar até ter token.
                wait_time = (1 - self._tokens) / self._rate_limit
                await asyncio.sleep(wait_time)
                # Refill aplicado durante sleep — recomputa.
                self._last_refill = asyncio.get_event_loop().time()
                self._tokens = 0  # acabou de gastar 1.
            else:
                self._tokens -= 1

    async def get(
        self,
        path: str,
        params: Optional[dict] = None,
    ) -> Optional[dict]:
        """GET path relativo (ex: '/event/123/statistics').

        Returns dict do JSON ou None se 404 / erro de rede.
        Raises SofaScoreBlockedError em 403/429.
        """
        if self._session is None:
            await self.start()

        await self._acquire_token()

        url = f"{self._base_url}{path}"
        start = asyncio.get_event_loop().time()

        try:
            response = await self._session.get(url, params=params)
            elapsed = asyncio.get_event_loop().time() - start

            if response.status_code in (403, 429):
                logger.warning(
                    "sofascore.blocked status=%d path=%s elapsed=%.2fs",
                    response.status_code, path, elapsed,
                )
                raise SofaScoreBlockedError(
                    f"Status {response.status_code} em {path}"
                )

            if response.status_code == 404:
                logger.debug("sofascore.not_found path=%s", path)
                return None

            response.raise_for_status()

            data = response.json()
            logger.debug(
                "sofascore.ok path=%s elapsed=%.2fs size=%dB",
                path, elapsed, len(response.content),
            )
            return data

        except SofaScoreBlockedError:
            raise
        except Exception as e:
            elapsed = asyncio.get_event_loop().time() - start
            logger.warning(
                "sofascore.error path=%s elapsed=%.2fs error=%s: %s",
                path, elapsed, type(e).__name__, e,
            )
            return None

    # ====== Conveniência: 1 método por endpoint ======

    async def get_live_events(self) -> Optional[list[dict]]:
        data = await self.get("/sport/football/events/live")
        return data.get("events", []) if data else None

    async def get_event(self, event_id: int) -> Optional[dict]:
        data = await self.get(f"/event/{event_id}")
        return data.get("event") if data else None

    async def get_statistics(self, event_id: int) -> Optional[list[dict]]:
        data = await self.get(f"/event/{event_id}/statistics")
        return data.get("statistics") if data else None

    async def get_lineups(self, event_id: int) -> Optional[dict]:
        """Retorna {confirmed, home, away, statisticalVersion}."""
        return await self.get(f"/event/{event_id}/lineups")

    async def get_incidents(self, event_id: int) -> Optional[list[dict]]:
        data = await self.get(f"/event/{event_id}/incidents")
        return data.get("incidents") if data else None

    async def get_managers(self, event_id: int) -> Optional[dict]:
        """Retorna {homeManager, awayManager}."""
        return await self.get(f"/event/{event_id}/managers")

    async def get_standings(
        self, unique_tournament_id: int, season_id: int
    ) -> Optional[list[dict]]:
        data = await self.get(
            f"/unique-tournament/{unique_tournament_id}"
            f"/season/{season_id}/standings/total"
        )
        return data.get("standings") if data else None

    async def get_h2h_summary(self, event_id: int) -> Optional[dict]:
        """Sumário H2H: `{teamDuel, managerDuel}` com contagem W/D/L
        agregada (não lista de eventos).

        K.1 PARTE B confirmou: `/h2h/events` NÃO existe (404). Histórico
        de jogos vem via `/team/{id}/events/last/{n}` filtrado pelo time
        adversário (a implementar em B.6 se necessário pra Fase J).
        """
        return await self.get(f"/event/{event_id}/h2h")

    async def get_pregame_form(self, event_id: int) -> Optional[dict]:
        return await self.get(f"/event/{event_id}/pregame-form")

    async def get_team_next_events(
        self, team_id: int, page: int = 0
    ) -> Optional[list[dict]]:
        data = await self.get(f"/team/{team_id}/events/next/{page}")
        return data.get("events") if data else None

    async def get_team_last_events(
        self, team_id: int, page: int = 0
    ) -> Optional[list[dict]]:
        data = await self.get(f"/team/{team_id}/events/last/{page}")
        return data.get("events") if data else None

    async def get_best_players(self, event_id: int) -> Optional[dict]:
        return await self.get(f"/event/{event_id}/best-players/summary")

    async def health(self) -> bool:
        """Health check via /sport/football/events/live."""
        try:
            data = await self.get("/sport/football/events/live")
            return data is not None
        except Exception:
            return False
