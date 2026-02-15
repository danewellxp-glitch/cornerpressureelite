import json
import aiohttp
import logging
from typing import List, Dict, Optional

from config import API_FOOTBALL_BASE_URL
from utils.rate_limiter import RateLimiter

logger = logging.getLogger("CPES.APIClient")


class APIFootballClient:
    """Cliente async para API-Football v3."""

    def __init__(self, api_key: str, rate_limiter: RateLimiter):
        self.api_key = api_key
        self.rate_limiter = rate_limiter
        self._session: Optional[aiohttp.ClientSession] = None

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                headers={"x-apisports-key": self.api_key}
            )
        return self._session

    async def _request(self, endpoint: str, params: Optional[Dict] = None) -> Dict:
        await self.rate_limiter.wait_if_needed()

        session = await self._get_session()
        url = f"{API_FOOTBALL_BASE_URL}/{endpoint}"

        try:
            async with session.get(url, params=params) as response:
                body = await response.text()
                ct = response.headers.get("Content-Type", "")

                # API Football retorna 503 com text/plain em manutencao ou sobrecarga
                if response.status >= 400:
                    logger.error(
                        "API HTTP %s | Content-Type: %s | url: %s | corpo: %s",
                        response.status,
                        ct,
                        response.url,
                        (body[:300] + "...") if len(body) > 300 else body or "(vazio)",
                    )
                    if "application/json" not in ct:
                        raise aiohttp.ClientError(
                            f"API Football indisponivel (HTTP {response.status}). "
                            f"Tente novamente em alguns minutos. "
                            f"Url: {response.url}"
                        )
                    try:
                        data = json.loads(body)
                        if data.get("errors"):
                            logger.error(f"API erro em {endpoint}: {data.get('errors')}")
                    except Exception:
                        pass
                    raise aiohttp.ClientError(
                        f"API Football retornou HTTP {response.status}: {response.reason}"
                    )

                if "application/json" not in ct:
                    logger.error(
                        "API retornou Content-Type inesperado: %s. Corpo: %s",
                        ct,
                        (body[:200] + "...") if len(body) > 200 else body,
                    )
                    raise aiohttp.ClientError(
                        f"API Football retornou resposta invalida (Content-Type: {ct})"
                    )

                data = json.loads(body)
                self.rate_limiter.record_request()

                errors = data.get("errors", {})
                if errors:
                    logger.error(f"API erro em {endpoint}: {errors}")

                remaining = self.rate_limiter.remaining_daily()
                logger.debug(f"API {endpoint} | Restantes: {remaining}")

                return data

        except aiohttp.ClientError:
            raise
        except Exception as e:
            logger.error(f"Erro na requisicao {endpoint}: {e}")
            raise

    async def check_status(self) -> Dict:
        """Verifica status da conta (NAO conta como requisicao)."""
        session = await self._get_session()
        url = f"{API_FOOTBALL_BASE_URL}/status"

        async with session.get(url) as response:
            body = await response.text()
            if response.status >= 400 or "application/json" not in response.headers.get("Content-Type", ""):
                logger.error(
                    "API Status HTTP %s | Content-Type: %s | corpo: %s",
                    response.status,
                    response.headers.get("Content-Type", ""),
                    (body[:200] + "...") if len(body) > 200 else body,
                )
                raise aiohttp.ClientError(
                    f"API Football indisponivel (HTTP {response.status}). Tente novamente em alguns minutos."
                )
            data = json.loads(body)

        account = data.get("response", {})
        current = account.get("requests", {}).get("current", 0)
        self.rate_limiter.sync_from_api(current)

        plan = account.get("subscription", {}).get("plan", "Unknown")
        limit = account.get("requests", {}).get("limit_day", 0)
        logger.info(f"API Status - Plano: {plan} | Usado: {current}/{limit}")

        return account

    async def get_live_fixtures(self, league_ids: List[int]) -> List[Dict]:
        """Busca jogos ao vivo de ligas especificas."""
        all_fixtures = []

        for league_id in league_ids:
            if not self.rate_limiter.can_request():
                logger.warning("Sem requisicoes disponiveis, pulando liga %d", league_id)
                break

            data = await self._request(
                "fixtures", params={"live": "all", "league": league_id}
            )
            fixtures = data.get("response", [])
            all_fixtures.extend(fixtures)
            logger.info(f"Liga {league_id}: {len(fixtures)} jogos ao vivo")

        return all_fixtures

    async def get_statistics(self, fixture_id: int) -> List[Dict]:
        """Busca estatisticas detalhadas de um jogo."""
        data = await self._request(
            "fixtures/statistics", params={"fixture": fixture_id}
        )
        return data.get("response", [])

    async def get_events(self, fixture_id: int) -> List[Dict]:
        """Busca eventos (gols, cartoes, escanteios) de um jogo."""
        data = await self._request(
            "fixtures/events", params={"fixture": fixture_id}
        )
        return data.get("response", [])

    async def get_fixture_by_id(self, fixture_id: int) -> Optional[Dict]:
        """Busca dados de um jogo especifico."""
        data = await self._request("fixtures", params={"id": fixture_id})
        response = data.get("response", [])
        return response[0] if response else None

    async def close(self):
        if self._session and not self._session.closed:
            await self._session.close()
            logger.info("Sessao API encerrada")
