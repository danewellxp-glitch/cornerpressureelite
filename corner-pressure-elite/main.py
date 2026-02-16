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
from datetime import datetime, timedelta, timezone

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
    UPCOMING_NOTIFICATION_TIME,
    PRE_GAME_ALERT_MINUTES,
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
from data_reader import LIVE_STATE_PATH, UPCOMING_GAMES_PATH, AUDIT_STATE_PATH

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
            max_requests_per_minute=450,  # API-Football Pro permite 450/min
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
        self._today_schedule: List[Dict] = []
        self._schedule_date: str = ""
        self._last_schedule_fetch: float = 0  # timestamp da ultima busca de agenda
        self._last_morning_msg_date = None  # date do ultimo resumo matinal
        self._pre_game_alerted: set = set()  # timestamps de jogos ja alertados

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
        
        # Inicializar config de ligas
        from config import LIGAS_MONITORADAS
        all_liga_ids = [liga["id"] for liga in LIGAS_MONITORADAS]
        await self.database.init_ligas_config(all_liga_ids)
        
        # Inicializar config de thresholds
        await self.database.init_thresholds_config()

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

    async def _fetch_today_schedule(self, force: bool = False):
        """Busca agenda do dia. Pode ser forcada para refresh periodico."""
        today = datetime.now().strftime("%Y-%m-%d")

        # Pular se ja buscou recentemente (a nao ser que force=True ou mudou o dia)
        if not force and self._schedule_date == today and self._today_schedule:
            return

        try:
            # Carregar ligas ativas da database
            ligas_ativas = await self.database.get_ligas_ativas()
            
            self._today_schedule = await self.api_client.get_today_schedule(
                ligas_ativas, today
            )
            self._schedule_date = today

            if self._today_schedule:
                horarios = []
                for f in self._today_schedule:
                    ts = f.get("fixture", {}).get("timestamp", 0)
                    if ts:
                        horarios.append(datetime.fromtimestamp(ts, tz=timezone.utc))
                horarios.sort()

                nomes = []
                for f in self._today_schedule:
                    teams = f.get("teams", {})
                    h = teams.get("home", {}).get("name", "?")
                    a = teams.get("away", {}).get("name", "?")
                    ts = f.get("fixture", {}).get("timestamp", 0)
                    hora = datetime.fromtimestamp(ts, tz=timezone.utc).astimezone().strftime("%H:%M") if ts else "?"
                    nomes.append(f"  {hora} - {h} vs {a}")

                logger.info(
                    f"Agenda do dia: {len(self._today_schedule)} jogos\n"
                    + "\n".join(nomes)
                )
                
                # Salvar próximos jogos formatados para dashboard
                self._save_upcoming_games()
            else:
                logger.info("Nenhum jogo programado para hoje nas ligas monitoradas")
                self._save_upcoming_games([])
        except Exception as e:
            logger.error(f"Erro ao buscar agenda: {e}")
    
    def _save_upcoming_games(self, games: List[Dict] = None):
        """Salva próximos jogos em arquivo JSON para dashboard."""
        if games is None:
            games = self._today_schedule or []
        
        now = datetime.now(timezone.utc)
        upcoming = []
        
        for f in games:
            ts = f.get("fixture", {}).get("timestamp", 0)
            if not ts:
                continue
            
            # Pula jogos finalizados
            fixture_status = f.get("fixture", {}).get("status", {})
            status_short = fixture_status.get("short", "NS")
            if status_short in ["FT", "AET", "PEN"]:
                continue
            
            game_start = datetime.fromtimestamp(ts, tz=timezone.utc)
            game_end_estimate = game_start + timedelta(minutes=105)
            if now > game_end_estimate:
                continue
            
            # Calcula minutos até início
            minutes_until = max(0, int((game_start - now).total_seconds() / 60))
            
            # Status do jogo
            fixture_info = f.get("fixture", {})
            status = fixture_info.get("status", {})
            status_short = status.get("short", "NS")  # NS = Not Started
            
            teams = f.get("teams", {})
            goals = f.get("goals", {}) or {}
            league = f.get("league", {})
            
            upcoming.append({
                "id": fixture_info.get("id", 0),
                "timestamp": ts,
                "hora_inicio": game_start.astimezone().strftime("%H:%M"),
                "minutos_ate": minutes_until,
                "home": teams.get("home", {}).get("name", "?"),
                "away": teams.get("away", {}).get("name", "?"),
                "liga": league.get("name", "?"),
                "placar": f"{goals.get('home', 0) or 0}-{goals.get('away', 0) or 0}",
                "status": status_short,
            })
        
        # Ordena por timestamp
        upcoming.sort(key=lambda x: x["timestamp"])
        
        try:
            os.makedirs(os.path.dirname(UPCOMING_GAMES_PATH), exist_ok=True)
            with open(UPCOMING_GAMES_PATH, "w", encoding="utf-8") as f:
                json.dump({
                    "atualizado": datetime.now().isoformat(),
                    "proximos": upcoming,
                }, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Erro ao salvar próximos jogos: {e}")


    def _save_audit_state(self):
        """Salva dados de auditoria do ciclo para dashboard."""
        try:
            audit_data = self.decision_engine.get_audit_data()
            audit_data["atualizado"] = datetime.now().isoformat()
            audit_data["ciclo"] = self._cycles
            os.makedirs(os.path.dirname(AUDIT_STATE_PATH), exist_ok=True)
            with open(AUDIT_STATE_PATH, "w", encoding="utf-8") as f:
                json.dump(audit_data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.debug(f"Erro ao salvar audit_state: {e}")

    def _minutes_until_next_game(self) -> int:
        """Retorna minutos ate o proximo jogo comecar. 0 se ja tem jogo rolando."""
        now = datetime.now(timezone.utc)

        for f in self._today_schedule:
            ts = f.get("fixture", {}).get("timestamp", 0)
            if not ts:
                continue
            game_start = datetime.fromtimestamp(ts, tz=timezone.utc)
            # Jogo dura ~105 min, se comecou ha menos de 105 min ainda esta rolando
            game_end_estimate = game_start + timedelta(minutes=105)
            if now < game_end_estimate:
                diff = (game_start - now).total_seconds() / 60
                return max(0, int(diff))

        return -1  # nenhum jogo restante hoje

    def _idle_interval(self, mins_until: int) -> tuple:
        """Retorna (segundos_sleep, descricao, deve_atualizar_agenda).
        Escala progressiva: longe = 2h, perto = mais frequente.
        """
        if mins_until < 0:
            # Sem jogos hoje: atualiza a cada 2h
            return 7200, "2h (sem jogos hoje)", True
        elif mins_until > 120:
            # Jogo em 2h+: atualiza a cada 2h
            return 7200, "2h", True
        elif mins_until > 60:
            # Jogo em 1-2h: atualiza a cada 1h
            return 3600, "1h", True
        elif mins_until > 30:
            # Jogo em 30-60 min: atualiza a cada 15 min
            return 900, "15min", True
        elif mins_until > 15:
            # Jogo em 15-30 min: atualiza a cada 5 min
            return 300, "5min", False
        else:
            # Jogo em < 15 min: polling normal
            return POLLING_INTERVAL, f"{POLLING_INTERVAL}s", False

    async def _main_loop(self):
        """Loop principal de monitoramento."""
        last_status_check = 0

        while self._running:
            try:
                # Buscar agenda do dia (1 req, 1x por dia)
                await self._fetch_today_schedule()

                # Verificar se tem jogo proximo
                mins_until = self._minutes_until_next_game()

                if mins_until < 0 or mins_until > 15:
                    # Sem jogos ou proximo jogo longe -> polling progressivo
                    sleep_secs, desc, refresh_schedule = self._idle_interval(mins_until)

                    if mins_until < 0:
                        status_msg = "Sem jogos restantes"
                        # Reset schedule para nova data (apos meia-noite)
                        if datetime.now().hour == 0:
                            self._schedule_date = ""
                    else:
                        status_msg = f"Proximo jogo em {mins_until} min"

                    logger.info(f"{status_msg}. Proximo check em {desc}")

                    try:
                        with open(LIVE_STATE_PATH, "w", encoding="utf-8") as fp:
                            json.dump({
                                "atualizado": datetime.now().isoformat(),
                                "ciclo": self._cycles,
                                "status": "aguardando",
                                "proximo_jogo_min": mins_until if mins_until >= 0 else None,
                                "proximo_check": desc,
                                "pre_janela": [], "na_janela": [], "pos_janela": [],
                                "ids_observados": [],
                            }, fp, ensure_ascii=False)
                    except Exception:
                        pass

                    await self._check_daily_summary()
                    await self._check_upcoming_notifications()
                    await self._verificar_resultados()
                    await asyncio.sleep(sleep_secs)

                    # Refresh agenda se necessario (busca novos jogos)
                    if refresh_schedule:
                        await self._fetch_today_schedule(force=True)
                        self._save_upcoming_games()

                    continue

                # Tem jogo rolando ou proximo -> polling ativo
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

                # 1. Buscar jogos ao vivo (1 requisicao para todas as ligas)
                logger.info("Buscando jogos ao vivo...")
                ligas_ativas = await self.database.get_ligas_ativas()
                fixtures = await self.api_client.get_live_fixtures(ligas_ativas)

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
                    await self._check_upcoming_notifications()
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
                self.decision_engine.reset_ciclo_stats()
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

                # Log relatório de auditoria do ciclo
                audit_report = self.decision_engine.get_ciclo_report()
                if audit_report:
                    logger.info(audit_report)

                # Salvar dados de auditoria para dashboard
                self._save_audit_state()

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

                # 4. Verificar resultados de jogos finalizados (Sprint 2)
                await self._verificar_resultados()

                # 5. Verificar resumo diario e notificacoes de agenda
                await self._check_daily_summary()
                await self._check_upcoming_notifications()

                # 6. Aguardar proximo ciclo
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

            # Pre-avaliacao: filtros + score SEM buscar odds (economia de 1-2 reqs)
            pre_score = self.decision_engine.pre_avaliar(jogo)
            if pre_score is not None:
                # Jogo passou filtros+score -> buscar odds (vale a pena)
                odds_data = await self.api_client.get_live_odds(fixture_id)
                if odds_data:
                    jogo.linha_atual = odds_data.get("linha", jogo.linha_atual)
                    jogo.odd_atual = odds_data.get("odd_over", 1.0)
                    logger.debug(
                        f"Odds obtidas para {desc}: Linha {jogo.linha_atual} "
                        f"@ {odds_data.get('odd_over', '?')} ({odds_data.get('bookmaker', '?')})"
                    )

            # Salvar snapshot para backtest (com odds se disponivel)
            try:
                await self.database.salvar_snapshot(jogo)
            except Exception as snap_err:
                logger.debug(f"Erro ao salvar snapshot: {snap_err}")

            # Avaliacao completa com auditoria
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

    async def _verificar_resultados(self):
        """Verifica resultados de jogos finalizados e atualiza sinais pendentes (Sprint 2)."""
        try:
            # Expirar sinais com mais de 24h sem resultado
            await self.database.expirar_sinais_antigos()

            # Buscar sinais pendentes (ultimas 24h, sem resultado)
            sinais_pendentes = await self.database.get_sinais_pendentes()

            if not sinais_pendentes:
                logger.debug("Nenhum sinal pendente para verificação")
                return

            # Filtrar: so verificar sinais de jogos com mais de 2h (provavelmente finalizados)
            from datetime import datetime as dt
            agora = dt.now()
            sinais_para_verificar = []
            for s in sinais_pendentes:
                try:
                    ts = dt.fromisoformat(s.timestamp) if isinstance(s.timestamp, str) else s.timestamp
                    if (agora - ts).total_seconds() >= 7200:  # 2 horas
                        sinais_para_verificar.append(s)
                except (ValueError, TypeError):
                    sinais_para_verificar.append(s)  # na duvida, verifica

            if not sinais_para_verificar:
                logger.debug("Sinais pendentes ainda recentes (<2h), aguardando...")
                return

            logger.info(f"Verificando resultados de {len(sinais_para_verificar)} sinais pendentes...")

            resultados_obtidos = []

            for sinal in sinais_para_verificar:
                if not self.rate_limiter.can_request():
                    logger.warning("Sem requisições disponíveis para verificar resultados")
                    break

                jogo_id = sinal.jogo_id
                resultado_final = await self.api_client.get_fixture_result(jogo_id)
                
                if resultado_final:
                    escanteios_final = resultado_final.get("escanteios_totais", 0)
                    linha = sinal.linha
                    
                    # Determinar se foi GREEN ou RED
                    resultado = "GREEN" if escanteios_final > linha else "RED"
                    
                    # Calcular ROI: se GREEN, ganho = od - 1; se RED, perda = -1
                    # Nota: odd foi salvo no banco desde Sprint 1
                    odd = sinal.odd or 1.0
                    roi = (odd - 1.0) if resultado == "GREEN" else -1.0
                    
                    # Atualizar banco de sinais
                    await self.database.atualizar_resultado(
                        jogo_id=jogo_id,
                        resultado=resultado,
                        escanteios_final=escanteios_final,
                        roi=roi
                    )

                    # Atualizar snapshots com resultado (Sprint 3)
                    try:
                        await self.database.atualizar_snapshot_resultado(jogo_id, escanteios_final)
                    except Exception as snap_err:
                        logger.debug(f"Erro ao atualizar snapshot resultado: {snap_err}")
                    
                    resultados_obtidos.append({
                        "jogo_id": jogo_id,
                        "jogo_desc": sinal.jogo_descricao,
                        "resultado": resultado,
                        "escanteios_final": escanteios_final,
                        "linha": linha,
                        "roi": roi,
                        "odd": odd,
                    })
                    
                    logger.info(
                        f"Resultado atualizado: {sinal.jogo_descricao} | "
                        f"{escanteios_final} escs (linha {linha}) | {resultado} {roi:+.2f}u"
                    )
            
            # Enviar notificação com resultados (Sprint 2.4)
            if resultados_obtidos:
                await self._enviar_resultados_whatsapp(resultados_obtidos)
        
        except Exception as e:
            logger.error(f"Erro ao verificar resultados: {e}", exc_info=True)

    async def _enviar_resultados_whatsapp(self, resultados: list):
        """Envia resumo de resultados via WhatsApp (Sprint 2.4)."""
        try:
            greens = len([r for r in resultados if r["resultado"] == "GREEN"])
            reds = len([r for r in resultados if r["resultado"] == "RED"])
            roi_total = sum(r["roi"] for r in resultados)
            
            msg = f"\U0001f4ca *RESULTADOS FINAIS*\n\n"
            
            for r in resultados:
                emoji = "\u2705" if r["resultado"] == "GREEN" else "\u274c"
                logo = " GANHO" if r["resultado"] == "GREEN" else " PERDA"
                msg += (
                    f"{emoji} {r['jogo_desc']}\n"
                    f"   {r['escanteios_final']} escanteios vs linha {r['linha']}\n"
                    f"   Odd {r['odd']:.2f}x → {r['roi']:+.2f}u\n\n"
                )
            
            msg += (
                f"\U0001f4c8 *RESUMO:*\n"
                f"\u2705 Greens: {greens}\n"
                f"\u274c Reds: {reds}\n"
                f"\U0001f4b0 ROI: {roi_total:+.2f}u\n"
            )
            
            await self.notifier.send_message(msg)
            logger.info(f"Resumo de resultados enviado: {greens}G/{reds}R {roi_total:+.2f}u")
        
        except Exception as e:
            logger.error(f"Erro ao enviar resultados via WhatsApp: {e}")

    async def _check_daily_summary(self):
        """Verifica se deve enviar resumo diario via WhatsApp."""
        now = datetime.now(timezone.utc)

        try:
            summary_time = datetime.strptime(DAILY_SUMMARY_TIME, "%H:%M").time()
        except ValueError:
            return

        if now.time() >= summary_time and self._last_summary_date != now.date():
            stats = await self.database.get_estatisticas()
            await self.notifier.send_daily_summary(stats)
            self._last_summary_date = now.date()
            logger.info("Resumo diario enviado")

    async def _check_upcoming_notifications(self):
        """Envia notificacoes de agenda: resumo matinal e alertas pre-jogo."""
        now = datetime.now(timezone.utc)

        # Reset alertas a meia-noite
        if now.hour == 0 and now.minute < 5:
            self._pre_game_alerted.clear()

        # 1. Resumo matinal
        try:
            notif_time = datetime.strptime(UPCOMING_NOTIFICATION_TIME, "%H:%M").time()
        except ValueError:
            notif_time = datetime.strptime("08:00", "%H:%M").time()

        if (
            now.time() >= notif_time
            and self._last_morning_msg_date != now.date()
            and self._today_schedule
        ):
            # Formatar jogos para a notificacao
            games = self._get_upcoming_games_list()
            if games:
                await self.notifier.send_upcoming_games(games)
                logger.info(f"Agenda matinal enviada: {len(games)} jogos")
            self._last_morning_msg_date = now.date()

        # 2. Alerta pre-jogo (jogos comecando em <= PRE_GAME_ALERT_MINUTES)
        games_soon = []
        for f in self._today_schedule:
            ts = f.get("fixture", {}).get("timestamp", 0)
            if not ts or ts in self._pre_game_alerted:
                continue
            game_start = datetime.fromtimestamp(ts, tz=timezone.utc)
            mins_until = (game_start - now).total_seconds() / 60
            if 0 < mins_until <= PRE_GAME_ALERT_MINUTES:
                teams = f.get("teams", {})
                league = f.get("league", {})
                games_soon.append({
                    "hora_inicio": game_start.astimezone().strftime("%H:%M"),
                    "home": teams.get("home", {}).get("name", "?"),
                    "away": teams.get("away", {}).get("name", "?"),
                    "liga": league.get("name", "?"),
                    "minutos_ate": int(mins_until),
                    "timestamp": ts,
                })
                self._pre_game_alerted.add(ts)

        if games_soon:
            await self.notifier.send_pre_game_alert(games_soon)
            logger.info(f"Alerta pre-jogo enviado: {len(games_soon)} jogos")

    def _get_upcoming_games_list(self) -> list:
        """Converte _today_schedule para lista formatada de jogos."""
        now = datetime.now(timezone.utc)
        games = []
        for f in self._today_schedule:
            ts = f.get("fixture", {}).get("timestamp", 0)
            if not ts:
                continue
            game_start = datetime.fromtimestamp(ts, tz=timezone.utc)
            teams = f.get("teams", {})
            league = f.get("league", {})
            
            # Pula jogos + 105 min (finalizados)
            if now > game_start + timedelta(minutes=105):
                continue
            
            # Pula jogos no passado (erro de timezone/API)
            if (game_start - now).total_seconds() / 60 < -60:
                continue
            
            mins_until = max(0, int((game_start - now).total_seconds() / 60))
            status_short = f.get("fixture", {}).get("status", {}).get("short", "NS")
            games.append({
                "hora_inicio": game_start.astimezone().strftime("%H:%M"),
                "home": teams.get("home", {}).get("name", "?"),
                "away": teams.get("away", {}).get("name", "?"),
                "liga": league.get("name", "?"),
                "minutos_ate": mins_until,
                "timestamp": ts,
                "status": status_short,
            })
        games.sort(key=lambda x: x["timestamp"])
        return games

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
