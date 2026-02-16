import json
import aiohttp
import logging
from typing import List, Dict, Optional
from datetime import datetime

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
        limit = account.get("requests", {}).get("limit_day", 0)
        self.rate_limiter.sync_from_api(current, limit)

        plan = account.get("subscription", {}).get("plan", "Unknown")
        logger.info(f"API Status - Plano: {plan} | Usado: {current}/{limit}")

        return account

    async def get_live_fixtures(self, league_ids: List[int]) -> List[Dict]:
        """Busca jogos ao vivo de todas as ligas em UMA requisicao.
        
        🔧 FIX: API Football não retorna fixtures quando se passa live=all + múltiplas ligas.
        Solução: Buscar global com live=all, depois filtrar por liga_id localmente.
        """
        if not self.rate_limiter.can_request():
            logger.warning("Sem requisicoes disponiveis para buscar jogos ao vivo")
            return []

        league_ids_set = set(league_ids)
        logger.info(f"[DEBUG LIVE] Buscando jogos ao vivo globalmente (depois filtra {len(league_ids)} ligas)")
        
        # Buscar SEM filtro de liga (live=all globalmente)
        data = await self._request("fixtures", params={"live": "all"})
        all_fixtures = data.get("response", [])
        logger.info(f"[DEBUG LIVE] API globalmente retornou {len(all_fixtures)} fixtures")
        
        # Filtrar localmente para apenas as ligas que queremos
        filtered_fixtures = [
            f for f in all_fixtures 
            if f.get("league", {}).get("id") in league_ids_set
        ]
        logger.info(f"[DEBUG LIVE] ✓ Após filtro local: {len(filtered_fixtures)} fixtures em {len(league_ids)} ligas")
        
        if filtered_fixtures:
            amostra = [f"{f.get('teams', {}).get('home', {}).get('name', '?')} vs {f.get('teams', {}).get('away', {}).get('name', '?')}" for f in filtered_fixtures[:2]]
            logger.info(f"[DEBUG LIVE] Amostra: {amostra}")
        
        logger.info(f"Jogos ao vivo: {len(filtered_fixtures)} em {len(league_ids)} ligas (1 req)")
        return filtered_fixtures

    async def _debug_validate_seasons(self, league_id: int, date: str) -> Dict:
        """DEBUG FASE 3: Testa a mesma requisição com seasons diferentes.
        Valida qual season retorna mais resultados.
        """
        logger.info("=" * 80)
        logger.info("[DEBUG FASE 3] VALIDANDO SEASONS")
        logger.info("=" * 80)
        
        date_year = int(date[:4])
        logger.info(f"[DEBUG] Data solicitada: {date}")
        logger.info(f"[DEBUG] Year da data: {date_year}")
        logger.info(f"[DEBUG] Liga testada: {league_id}")
        
        results = {}
        
        # Testar seasons 2025 e 2026
        for season in [2025, 2026]:
            if not self.rate_limiter.can_request():
                logger.warning(f"[DEBUG] ⚠ Rate limiter bloqueou teste season {season}")
                continue
            
            logger.info(f"[DEBUG] Testando season {season}...")
            try:
                data = await self._request(
                    "fixtures",
                    params={"date": date, "league": league_id, "season": season}
                )
                fixtures = data.get("response", [])
                results[season] = len(fixtures)
                logger.info(f"[DEBUG]   Season {season}: {len(fixtures)} jogos")
            except Exception as e:
                logger.warning(f"[DEBUG] Erro ao testar season {season}: {e}")
                results[season] = 0
        
        logger.info("[DEBUG] Comparação de seasons:")
        logger.info(f"[DEBUG]   2025: {results.get(2025, 0)} jogos")
        logger.info(f"[DEBUG]   2026: {results.get(2026, 0)} jogos")
        
        season_recomendada = max(results, key=results.get) if results else date_year
        logger.info(f"[DEBUG] ⚠ Recomendação: Season {season_recomendada} retorna mais resultados")
        logger.info("=" * 80)
        
        return results

    async def get_today_schedule(self, league_ids: List[int], date: str) -> List[Dict]:
        """Busca agenda do dia para todas as ligas.
        date: formato YYYY-MM-DD
        Retorna lista de fixtures com horarios de inicio.
        
        🔧 FIX CRÍTICO: Usa seasons corretos por liga (2025 para Europa, 2026 para hemisfério sul).
        Isso resolve o bug onde 0 jogos eram retornados porque o código usava season=2026
        para TODAS as ligas, quando as europeias têm dados em season=2025.
        """
        all_fixtures = []

        # Usar seasons corretas por liga (2025 Europa, 2026 hemisfério sul)
        # Criar map de liga_id → season
        from config import LIGAS_MONITORADAS
        season_map = {liga["id"]: liga.get("season", 2025) for liga in LIGAS_MONITORADAS}
        
        logger.info(f"[DEBUG] Ligas a filtrar: {league_ids} (total: {len(league_ids)})")
        logger.info(f"[DEBUG] Rate limiter status: {self.rate_limiter.remaining_daily()} reqs restantes")
        
        for league_id in league_ids:
            if not self.rate_limiter.can_request():
                logger.warning(f"[DEBUG] ⚠ Sem requisicoes disponiveis para agenda, pulando liga {league_id}")
                break

            # Usar season correto para cada liga (BUG FIX!)
            season = season_map.get(league_id, 2025)  # Default 2025 se não encontrar
            
            logger.info(f"[DEBUG] Requisitando liga {league_id} com season {season}")
            data = await self._request(
                "fixtures", params={"date": date, "league": league_id, "season": season}
            )
            fixtures = data.get("response", [])
            logger.info(f"[DEBUG] Liga {league_id}: {len(fixtures)} jogos retornados (season {season})")
            
            if fixtures:
                for i, f in enumerate(fixtures[:2]):  # Log dos 2 primeiros
                    teams = f.get("teams", {})
                    h = teams.get("home", {}).get("name", "?")
                    a = teams.get("away", {}).get("name", "?")
                    logger.debug(f"[DEBUG]   Jogo {i+1}: {h} vs {a}")
            
            all_fixtures.extend(fixtures)
        
        logger.info("=" * 80)
        logger.info(f"[DEBUG] ✓ RESUMO FINAL (FIX APLICADO): {len(all_fixtures)} jogos após filtrar {len(league_ids)} ligas")
        logger.info(f"[DEBUG] Rate limiter final: {self.rate_limiter.remaining_daily()} reqs restantes")
        logger.info("=" * 80)
        
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

    async def get_live_odds(self, fixture_id: int) -> Dict:
        """Busca odds ao vivo para um jogo especifico (escanteios).
        Tenta /odds/live primeiro (odds in-play), fallback para /odds (pre-match).
        Retorna dicionario com: linha, odd_over, odd_under, bookmaker, timestamp.
        """
        # Tentar odds ao vivo (in-play)
        result = await self._fetch_live_odds(fixture_id)
        if result:
            return result

        # Fallback: odds pre-match
        result = await self._fetch_prematch_odds(fixture_id)
        if result:
            return result

        logger.debug(f"Nenhuma odd encontrada para fixture {fixture_id}")
        return {}

    async def _fetch_live_odds(self, fixture_id: int) -> Dict:
        """Busca odds in-play via /odds/live."""
        try:
            data = await self._request("odds/live", params={"fixture": fixture_id})
            response = data.get("response", [])

            if not response:
                return {}

            # /odds/live: response e lista, cada item tem odds[]
            fixture_data = response[0] if isinstance(response, list) else response
            odds_list = fixture_data.get("odds", [])

            return self._parse_corners_odds(odds_list, "Live")
        except Exception as e:
            logger.debug(f"Odds live nao disponiveis para fixture {fixture_id}: {e}")
            return {}

    async def _fetch_prematch_odds(self, fixture_id: int) -> Dict:
        """Busca odds pre-match via /odds (fallback)."""
        try:
            data = await self._request("odds", params={"fixture": fixture_id, "bookmaker": "1"})
            response = data.get("response", [])

            if not response:
                return {}

            # /odds: response e lista, cada item tem bookmakers[].bets[]
            first = response[0] if isinstance(response, list) else response
            bookmakers = first.get("bookmakers", [])

            if not bookmakers:
                return {}

            bets = bookmakers[0].get("bets", [])
            bookmaker_name = bookmakers[0].get("name", "Pre-match")
            return self._parse_corners_odds(bets, bookmaker_name)
        except Exception as e:
            logger.debug(f"Odds pre-match nao disponiveis para fixture {fixture_id}: {e}")
            return {}

    def _parse_corners_odds(self, odds_list: list, bookmaker: str) -> Dict:
        """Extrai odds de escanteios de uma lista de mercados.
        Funciona para formato live (/odds/live) e pre-match (/odds).
        """
        CORNER_KEYWORDS = ["corner", "escanteio"]

        for market in odds_list:
            name = market.get("name", "").lower()
            if not any(kw in name for kw in CORNER_KEYWORDS):
                continue

            values = market.get("values", [])
            if not values:
                continue

            odd_over = None
            odd_under = None
            linha = None

            for val in values:
                market_value = str(val.get("value", ""))
                odd = val.get("odd", 0.0)

                if "over" in market_value.lower():
                    odd_over = float(odd) if odd else None
                    try:
                        linha = float(market_value.split()[-1])
                    except (ValueError, IndexError):
                        pass
                elif "under" in market_value.lower():
                    odd_under = float(odd) if odd else None

            if odd_over and odd_under and linha:
                result = {
                    "linha": linha,
                    "odd_over": odd_over,
                    "odd_under": odd_under,
                    "bookmaker": bookmaker,
                    "timestamp": datetime.now().isoformat(),
                }
                logger.debug(
                    f"Odds corners: Over {odd_over} / Under {odd_under} "
                    f"@ {linha} ({bookmaker})"
                )
                return result

        return {}

    async def get_fixture_result(self, fixture_id: int) -> Optional[Dict]:
        """Busca resultado final de um jogo (quando ja terminou).
        Usa statistics + events para contagem de escanteios (pega o maior).
        Retorna: escanteios_totais, placar_final, status.
        """
        try:
            fixture = await self.get_fixture_by_id(fixture_id)
            if not fixture:
                logger.debug(f"Fixture {fixture_id} nao encontrada")
                return None

            fixture_info = fixture.get("fixture", {})
            status = fixture_info.get("status", {}) or {}
            status_short = status.get("short", "")

            # Verificar se jogo ja terminou
            if status_short not in ["FT", "AET", "PEN"]:
                logger.debug(f"Fixture {fixture_id} ainda nao terminou (status: {status_short})")
                return None

            # Buscar escanteios finais via statistics (mais confiavel)
            corners_from_stats = 0
            try:
                stats = await self.get_statistics(fixture_id)
                for team_stats in stats:
                    for stat in team_stats.get("statistics", []):
                        if stat.get("type") == "Corner Kicks":
                            val = stat.get("value")
                            if val is not None:
                                corners_from_stats += int(val)
            except Exception:
                pass

            # Buscar escanteios via events (fallback)
            corners_from_events = 0
            try:
                events = await self.get_events(fixture_id)
                corners_from_events = len([e for e in events if e.get("type") == "Corner"])
            except Exception:
                pass

            # Usar o maior valor (mais confiavel)
            corners_total = max(corners_from_stats, corners_from_events)

            goals = fixture.get("goals", {}) or {}
            placar_final = {
                "home": goals.get("home", 0) or 0,
                "away": goals.get("away", 0) or 0,
            }

            teams = fixture.get("teams", {})

            result = {
                "fixture_id": fixture_id,
                "escanteios_totais": corners_total,
                "placar_final": placar_final,
                "status": status_short,
                "timestamp": datetime.now().isoformat(),
            }

            logger.info(
                f"Resultado fixture {fixture_id}: "
                f"{teams.get('home', {}).get('name', '?')} {placar_final['home']}-{placar_final['away']} "
                f"{teams.get('away', {}).get('name', '?')} | {corners_total} escanteios "
                f"(stats={corners_from_stats}, events={corners_from_events})"
            )
            return result

        except Exception as e:
            logger.error(f"Erro ao buscar resultado fixture {fixture_id}: {e}")
            return None

    async def close(self):
        if self._session and not self._session.closed:
            await self._session.close()
            logger.info("Sessao API encerrada")
