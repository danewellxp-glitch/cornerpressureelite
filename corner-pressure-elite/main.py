"""
Corner Pressure Elite System (CPES)
Motor de analise estatistica para escanteios ao vivo.
Alertas via WhatsApp (WAHA API).

Uso: python main.py
"""

import asyncio
import json
import sys
import os
import time
import logging
from typing import Dict, List, Any
from datetime import datetime

# Adicionar diretorio raiz ao path
sys.path.insert(0, os.path.dirname(__file__))

from config import (
    API_FOOTBALL_KEY,
    API_DAILY_LIMIT,
    LIGA_IDS,
    POLLING_INTERVAL,
    STATUS_CHECK_INTERVAL,
    MINUTO_INICIO,
    MINUTO_FIM,
    JANELA_ANTECIPADA_INICIO,
    WAHA_URL,
    WAHA_SESSION_NAME,
    WAHA_API_KEY,
    WHATSAPP_GROUP_ID,
    WHATSAPP_ADMIN,
    WHATSAPP_UPDATES,
    DAILY_SUMMARY_TIME,
)
from data.api_client import APIFootballClient
from engine.decision_engine import DecisionEngine
from engine.state_manager import StateManager
from notifier.whatsapp_client import WAHAConfig
from notifier.notification_manager import NotificationManager
from storage.database import Database
from storage.logger import setup_logging
from utils.rate_limiter import RateLimiter
from utils.adaptive_polling import AdaptivePolling
from utils.helpers import parse_fixture_to_jogo
from data_reader import LIVE_STATE_PATH

logger = logging.getLogger("CPES.Main")


def _serialize_fixture(
    fixture: Dict, fase: str, escanteios: int | None = None
) -> Dict[str, Any]:
    """Extrai dados minimos para exibicao no dashboard."""
    fixture_info = fixture.get("fixture", {})
    teams = fixture.get("teams", {})
    goals = fixture.get("goals", {}) or {}
    league = fixture.get("league", {})
    status = fixture_info.get("status", {}) or {}
    elapsed = status.get("elapsed", 0) or 0
    return {
        "id": fixture_info.get("id", 0),
        "home": teams.get("home", {}).get("name", "?"),
        "away": teams.get("away", {}).get("name", "?"),
        "liga": league.get("name", "?"),
        "minuto": elapsed,
        "placar": f"{goals.get('home', 0) or 0}-{goals.get('away', 0) or 0}",
        "fase": fase,
        "escanteios": escanteios,
    }


class CornerPressureElite:
    """Sistema principal do CPES."""

    def __init__(self):
        self.rate_limiter = RateLimiter(
            max_requests_per_day=API_DAILY_LIMIT,
            max_requests_per_minute=10,
        )
        self.api_client = APIFootballClient(API_FOOTBALL_KEY, self.rate_limiter)
        self.decision_engine = DecisionEngine()
        self.state_manager = StateManager()
        self.database = Database()
        self._running = False
        self._cycles = 0
        self._last_summary_date = None

        # WAHA NotificationManager
        waha_config = WAHAConfig(
            base_url=WAHA_URL,
            session_name=WAHA_SESSION_NAME,
            api_key=WAHA_API_KEY or None,
        )
        self.notifier = NotificationManager(
            waha_config,
            group_id=WHATSAPP_GROUP_ID,
            admin_number=WHATSAPP_ADMIN,
            updates_number=WHATSAPP_UPDATES,
        )
        self.adaptive_polling = AdaptivePolling()
        self._escanteios_cache: Dict[int, int] = {}

    async def iniciar(self):
        """Inicializa o sistema e comeca o loop principal."""
        logger.info("=" * 60)
        logger.info("  CORNER PRESSURE ELITE SYSTEM v2.0.0")
        logger.info("  Motor de Analise de Escanteios + WhatsApp (WAHA)")
        logger.info("=" * 60)

        # Verificar API key
        if not API_FOOTBALL_KEY:
            logger.error("API_FOOTBALL_KEY nao configurada no .env!")
            return

        # Inicializar banco de dados
        await self.database.init()

        # Inicializar notificador WhatsApp
        await self.notifier.start()

        # Verificar conexao WhatsApp (WAHA)
        if WHATSAPP_GROUP_ID:
            try:
                waha_status = await self.notifier.client.check_status()
                session_status = waha_status.get("status", "UNKNOWN")
                if session_status == "WORKING":
                    logger.info("WhatsApp conectado via WAHA")
                else:
                    logger.warning(
                        f"WhatsApp status: {session_status} - "
                        "Verifique o WAHA e escaneie o QR code"
                    )
            except Exception as e:
                logger.warning(
                    f"WAHA nao disponivel: {e} - "
                    "Alertas serao impressos apenas no console"
                )
        else:
            logger.info("Sem grupo WhatsApp configurado - alertas apenas no console")

        # Verificar status da API Football
        try:
            status = await self.api_client.check_status()
            plan = status.get("subscription", {}).get("plan", "?")
            current = status.get("requests", {}).get("current", 0)
            limit = status.get("requests", {}).get("limit_day", 0)
            logger.info(f"API Football - Plano: {plan} | Usado: {current}/{limit}")
        except Exception as e:
            logger.error(f"Erro ao conectar com API Football: {e}")

        # Info
        logger.info(f"Ligas monitoradas: {LIGA_IDS}")
        logger.info(f"Janela: min {MINUTO_INICIO}-{MINUTO_FIM}")
        logger.info(f"Limite diario: {API_DAILY_LIMIT} requisicoes")
        logger.info(f"Intervalo de polling: {POLLING_INTERVAL}s")
        logger.info(f"Grupo WhatsApp: {WHATSAPP_GROUP_ID[:25]}...")
        logger.info("")

        # Enviar status inicial via WhatsApp
        await self._send_startup_status()

        # Loop principal
        self._running = True
        try:
            await self._main_loop()
        except KeyboardInterrupt:
            logger.info("Sistema interrompido pelo usuario")
        finally:
            await self._shutdown()

    async def _main_loop(self):
        """Loop principal de monitoramento."""
        last_status_check = 0

        while self._running:
            try:
                self._cycles += 1
                logger.info(f"--- Ciclo #{self._cycles} ---")

                # Verificar status periodicamente
                now = time.time()
                if now - last_status_check > STATUS_CHECK_INTERVAL:
                    try:
                        await self.api_client.check_status()
                        last_status_check = now
                    except Exception:
                        pass

                # Verificar se tem requisicoes disponiveis
                remaining = self.rate_limiter.remaining_daily()
                if remaining < 5:
                    logger.warning(
                        f"Poucas requisicoes restantes ({remaining}). "
                        "Pausando monitoramento por 10 minutos."
                    )
                    await asyncio.sleep(600)
                    continue

                # 1. Buscar jogos ao vivo
                logger.info("Buscando jogos ao vivo...")
                fixtures = await self.api_client.get_live_fixtures(LIGA_IDS)

                if not fixtures:
                    logger.info("Nenhum jogo ao vivo nas ligas monitoradas")
                    try:
                        with open(LIVE_STATE_PATH, "w", encoding="utf-8") as f:
                            json.dump({
                                "atualizado": datetime.now().isoformat(),
                                "ciclo": self._cycles,
                                "pre_janela": [], "na_janela": [], "pos_janela": [],
                                "ids_observados": [],
                            }, f, ensure_ascii=False)
                    except Exception:
                        pass
                    await self._check_daily_summary()
                    await asyncio.sleep(POLLING_INTERVAL)
                    continue

                logger.info(f"Encontrados {len(fixtures)} jogos ao vivo")

                # 2. Filtrar jogos por fase (janela antecipada 50-78 + reta final 78+)
                jogos_para_analisar: List[Dict] = []
                jogos_ativos_ids = set()
                jogos_por_fase: Dict[str, List[Dict]] = {
                    "pre_janela": [],
                    "na_janela": [],
                    "pos_janela": [],
                }
                jogos_por_fase_detalhada = {
                    "primeiro_tempo_0_30": 0,
                    "pre_janela_31_50": 0,
                    "na_janela": 0,
                    "reta_final": 0,
                }
                ids_na_janela = set()
                ids_observados = set(self.state_manager._alertas.keys())

                for fixture in fixtures:
                    fixture_info = fixture.get("fixture", {})
                    fixture_id = fixture_info.get("id", 0)
                    jogos_ativos_ids.add(fixture_id)
                    esc = self._escanteios_cache.get(fixture_id)

                    status = fixture_info.get("status", {}) or {}
                    elapsed = status.get("elapsed", 0) or 0

                    # Early trigger: 7+ escanteios antes do min 50 -> na_janela (sendo analisados)
                    early_trigger = esc is not None and esc >= 7
                    na_janela_ou_early = elapsed >= JANELA_ANTECIPADA_INICIO or early_trigger

                    # Classificar por fase (para live_state e polling)
                    if elapsed > MINUTO_FIM:
                        fase = "pos_janela"
                        jogos_por_fase_detalhada["reta_final"] += 1
                        ids_na_janela.add(fixture_id)
                        if self.adaptive_polling.should_poll(fixture_id, elapsed, esc):
                            jogos_para_analisar.append(fixture)
                            teams = fixture.get("teams", {})
                            desc = f"{teams.get('home', {}).get('name', '?')} vs {teams.get('away', {}).get('name', '?')}"
                            logger.debug(f"Polling RETAFINAL: {desc} - Min {elapsed}")
                    elif na_janela_ou_early:
                        fase = "na_janela"
                        jogos_por_fase_detalhada["na_janela"] += 1
                        ids_na_janela.add(fixture_id)
                        if self.adaptive_polling.should_poll(fixture_id, elapsed, esc):
                            jogos_para_analisar.append(fixture)
                            teams = fixture.get("teams", {})
                            desc = f"{teams.get('home', {}).get('name', '?')} vs {teams.get('away', {}).get('name', '?')}"
                            tag = "(Early 7esc)" if early_trigger else "(Janela)"
                            logger.debug(f"Polling: {desc} - Min {elapsed} {tag}")
                        else:
                            next_p = self.adaptive_polling.get_next_poll_time(
                                fixture_id, elapsed, esc
                            )
                            teams = fixture.get("teams", {})
                            desc = f"{teams.get('home', {}).get('name', '?')} vs {teams.get('away', {}).get('name', '?')}"
                            logger.debug(f"Skip: {desc} - Min {elapsed} (Prox: {next_p})")
                    else:
                        # Pre-janela: 0-50 min, sem 7 esc (ou sem cache ainda)
                        fase = "pre_janela"
                        if elapsed <= 30:
                            jogos_por_fase_detalhada["primeiro_tempo_0_30"] += 1
                        else:
                            jogos_por_fase_detalhada["pre_janela_31_50"] += 1
                        # Analisa para obter/cachear escanteios e detectar early trigger
                        if self.adaptive_polling.should_poll(fixture_id, elapsed, esc):
                            jogos_para_analisar.append(fixture)
                            teams = fixture.get("teams", {})
                            desc = f"{teams.get('home', {}).get('name', '?')} vs {teams.get('away', {}).get('name', '?')}"
                            logger.debug(f"Polling PreJanela: {desc} - Min {elapsed} (5m/3m)")
                        else:
                            next_p = self.adaptive_polling.get_next_poll_time(
                                fixture_id, elapsed, esc
                            )
                            teams = fixture.get("teams", {})
                            desc = f"{teams.get('home', {}).get('name', '?')} vs {teams.get('away', {}).get('name', '?')}"
                            logger.debug(f"Skip PreJanela: {desc} - Min {elapsed} (Prox: {next_p})")

                    jogos_por_fase[fase].append(_serialize_fixture(fixture, fase, esc))

                # Limpar jogos encerrados
                self.state_manager.limpar_jogos_encerrados(jogos_ativos_ids)
                self.adaptive_polling.clear_finished_games(list(jogos_ativos_ids))
                for gid in list(self._escanteios_cache.keys()):
                    if gid not in jogos_ativos_ids:
                        del self._escanteios_cache[gid]

                # Economia
                total = len(fixtures)
                analisando = len(jogos_para_analisar)
                economia_pct = ((total - analisando) / total * 100) if total > 0 else 0

                if total > 0:
                    logger.info(
                        f"Economia: {analisando}/{total} jogos processados ({economia_pct:.0f}% economizado)"
                    )
                logger.info(
                    f"Fases: 0-30={jogos_por_fase_detalhada['primeiro_tempo_0_30']} | "
                    f"31-50={jogos_por_fase_detalhada['pre_janela_31_50']} | "
                    f"Janela={jogos_por_fase_detalhada['na_janela']} | "
                    f"RetaFinal={jogos_por_fase_detalhada['reta_final']}"
                )

                # Salvar estado para dashboard
                try:
                    live_state = {
                        "atualizado": datetime.now().isoformat(),
                        "ciclo": self._cycles,
                        "pre_janela": jogos_por_fase["pre_janela"],
                        "na_janela": jogos_por_fase["na_janela"],
                        "pos_janela": jogos_por_fase["pos_janela"],
                        "ids_observados": list(ids_observados & ids_na_janela),
                        "polling_stats": {
                            "jogos_monitorados": total,
                            "jogos_analisando": analisando,
                            "economia_pct": round(economia_pct, 1),
                        },
                    }
                    os.makedirs(os.path.dirname(LIVE_STATE_PATH), exist_ok=True)
                    with open(LIVE_STATE_PATH, "w", encoding="utf-8") as f:
                        json.dump(live_state, f, ensure_ascii=False, indent=2)
                except Exception as e:
                    logger.debug(f"Nao foi possivel salvar live_state: {e}")

                # 3. Analisar apenas jogos que devem ser atualizados (should_poll)
                for fixture in jogos_para_analisar:
                    if not self.rate_limiter.can_request():
                        logger.warning("Sem requisicoes - parando analise dos jogos")
                        break

                    jogo = await self._analisar_jogo(fixture)
                    if jogo:
                        fid = fixture.get("fixture", {}).get("id", 0)
                        self._escanteios_cache[fid] = jogo.escanteios_total
                        # Atualizar escanteios no jogos_por_fase para salvar no live_state
                        for lista in jogos_por_fase.values():
                            for item in lista:
                                if item.get("id") == fid:
                                    item["escanteios"] = jogo.escanteios_total
                                    break

                # Re-salvar live_state com escanteios atualizados
                try:
                    live_state = {
                        "atualizado": datetime.now().isoformat(),
                        "ciclo": self._cycles,
                        "pre_janela": jogos_por_fase["pre_janela"],
                        "na_janela": jogos_por_fase["na_janela"],
                        "pos_janela": jogos_por_fase["pos_janela"],
                        "ids_observados": list(ids_observados & ids_na_janela),
                        "polling_stats": {
                            "jogos_monitorados": total,
                            "jogos_analisando": analisando,
                            "economia_pct": round(economia_pct, 1),
                        },
                    }
                    with open(LIVE_STATE_PATH, "w", encoding="utf-8") as f:
                        json.dump(live_state, f, ensure_ascii=False, indent=2)
                except Exception as e:
                    logger.debug(f"Nao foi possivel re-salvar live_state: {e}")

                # 4. Verificar resumo diario
                await self._check_daily_summary()

                # 5. Aguardar proximo ciclo
                logger.info(
                    f"Restantes: {self.rate_limiter.remaining_daily()} req | "
                    f"Proximo ciclo em {POLLING_INTERVAL}s"
                )
                await asyncio.sleep(POLLING_INTERVAL)

            except Exception as e:
                logger.error(f"Erro no loop principal: {e}", exc_info=True)
                try:
                    await self.notifier.send_error_alert(str(e))
                except Exception:
                    pass
                await asyncio.sleep(POLLING_INTERVAL)

    async def _analisar_jogo(self, fixture: Dict):
        """Analisa um jogo individual. Retorna jogo se sucesso, None senao."""
        fixture_info = fixture.get("fixture", {})
        fixture_id = fixture_info.get("id", 0)
        league = fixture.get("league", {})
        liga_id = league.get("id", 0)
        teams = fixture.get("teams", {})
        desc = (
            f"{teams.get('home', {}).get('name', '?')} vs "
            f"{teams.get('away', {}).get('name', '?')}"
        )

        try:
            # Buscar estatisticas
            stats = await self.api_client.get_statistics(fixture_id)

            # Converter para JogoAoVivo
            jogo = parse_fixture_to_jogo(fixture, stats, liga_id)

            logger.info(
                f"Analisando: {desc} | Min {jogo.minuto} | "
                f"Escanteios: {jogo.escanteios_total} | "
                f"Placar: {jogo.placar}"
            )

            # Avaliar entrada
            sinal = self.decision_engine.avaliar(jogo)

            if sinal:
                if not self.state_manager.ja_alertou(fixture_id):
                    # Primeiro alerta -> WhatsApp
                    await self.notifier.send_signal(sinal)
                    await self.database.registrar_sinal(sinal)
                    self.state_manager.registrar_alerta(sinal)

                elif self.state_manager.deve_reavaliar(fixture_id, sinal):
                    # Re-avaliacao -> WhatsApp
                    self.state_manager.atualizar_reavaliacao(sinal)
                    await self.notifier.send_reevaluation(sinal)
                    await self.database.registrar_sinal(sinal)

            return jogo
        except Exception as e:
            logger.error(f"Erro ao analisar jogo {desc} ({fixture_id}): {e}")
            return None

    async def _check_daily_summary(self):
        """Verifica se deve enviar resumo diario via WhatsApp."""
        now = datetime.now()

        try:
            summary_time = datetime.strptime(DAILY_SUMMARY_TIME, "%H:%M").time()
        except ValueError:
            return

        if now.time() >= summary_time and self._last_summary_date != now.date():
            stats = await self.database.get_estatisticas()
            await self.notifier.send_daily_summary(stats)
            self._last_summary_date = now.date()
            logger.info("Resumo diario enviado")

    async def _send_startup_status(self):
        """Envia status ao iniciar sistema via WhatsApp."""
        status = {
            "online": True,
            "api_requests": self.rate_limiter.requests_today,
            "api_limit": API_DAILY_LIMIT,
            "jogos_ativos": 0,
            "sinais_hoje": 0,
            "ultima_atualizacao": datetime.now().strftime("%H:%M:%S"),
        }
        try:
            await self.notifier.send_status(status)
        except Exception as e:
            logger.debug(f"Nao foi possivel enviar status inicial: {e}")

    async def _shutdown(self):
        """Encerra o sistema graciosamente."""
        logger.info("Encerrando CPES...")

        await self.notifier.close()
        await self.api_client.close()

        stats = await self.database.get_estatisticas()
        logger.info(
            f"Resumo da sessao: "
            f"{stats['total']} sinais | "
            f"{stats['greens']}G/{stats['reds']}R | "
            f"Winrate: {stats['winrate']}%"
        )
        logger.info("CPES encerrado com sucesso")


async def main():
    setup_logging()
    sistema = CornerPressureElite()
    await sistema.iniciar()


if __name__ == "__main__":
    asyncio.run(main())
