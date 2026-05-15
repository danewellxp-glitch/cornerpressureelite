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
from typing import Dict, List, Any, Optional
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
    ANALISE_CARTOES_ATIVA,
    WHATSAPP_GROUP_CARTOES,
    WAHA_HEALTHCHECK_INTERVAL,
    DEV_TEST_MODE,
    DEV_TEST_MAX_GAMES,
    DEV_TEST_LOW_BUDGET_THRESHOLD,
    USE_BETANO_BRIDGE,
    BETANO_EVENT_MAP,
)
import config
from data.api_client import APIFootballClient
from engine.decision_engine import DecisionEngine
from engine.state_manager import StateManager
from engine.cards_decision_engine import CardsDecisionEngine
from engine.cards_state_manager import CardsStateManager
from notifier.whatsapp_client import WAHAConfig
from notifier.notification_manager import NotificationManager
from notifier.waha_manager import WAHASessionManager
from storage.database import Database
from storage.logger import setup_logging
from utils.rate_limiter import RateLimiter
from utils.adaptive_polling import AdaptivePolling
from utils.helpers import parse_fixture_to_jogo, enrich_jogo_with_cards
from data.odds_provider import CanonicalFixture
from data.providers.factory import build_providers
from data.repositories.fixture_map import FixtureMapRepo
from data.repositories.odds_history import OddsHistoryRepo
from data.persistence.odds_worker import OddsPersistenceWorker

logger = logging.getLogger("CPES.Main")


def _serialize_fixture(
    fixture: Dict, fase: str, escanteios: int | None = None,
    cartoes: int | None = None,
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
        "cartoes": cartoes,
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
        self.cards_decision_engine = CardsDecisionEngine()
        self.cards_state_manager = CardsStateManager()
        self.database = Database()
        # CompositeOddsProvider — instanciado em iniciar() (build_providers é
        # async). None enquanto USE_BETANO_BRIDGE=false ou antes do startup.
        self.composite_odds = None
        self._providers_shutdown = None
        # Worker de telemetria de odds (Fase D.0) — instanciado em iniciar()
        # só quando USE_BETANO_BRIDGE=true.
        self.odds_persistence_worker: Optional[OddsPersistenceWorker] = None
        # Última captura de telemetria por (fixture_id, market) -> timestamp ms.
        self._last_capture_at: Dict[tuple, int] = {}
        self._running = False
        self._cycles = 0
        self._pending_signals_remaining = 0
        self._last_summary_date = None
        self._healthcheck_task: Optional[asyncio.Task] = None
        self._waha_manager = WAHASessionManager()

        # Dev-mode runtime config (sincronizado do DB no inicio de cada ciclo)
        self.dev_mode_enabled = bool(DEV_TEST_MODE)
        self.dev_max_games = int(DEV_TEST_MAX_GAMES)
        self.effective_polling_interval = POLLING_INTERVAL
        self.effective_status_check_interval = STATUS_CHECK_INTERVAL

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
            cards_group_id=WHATSAPP_GROUP_CARTOES or None,
            database=self.database,
        )
        self.adaptive_polling = AdaptivePolling()
        self._escanteios_cache: Dict[int, int] = {}
        self._cartoes_cache: Dict[int, int] = {}
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

        # Bridge Betano: seed manual fixture->event_id + Composite provider.
        # USE_BETANO_BRIDGE=false -> composite_odds fica None, pipeline legado.
        if USE_BETANO_BRIDGE:
            seeded = await self.database.seed_betano_fixture_map(BETANO_EVENT_MAP)
            logger.info(
                f"BETANO_EVENT_MAP: {seeded} fixture(s) seedados em betano_fixture_map"
            )
            # Telemetria de odds (Fase D.0): worker batcha inserts em
            # odds_history. Iniciado ANTES de build_providers — o adapter
            # Betano recebe a referência via factory.
            self.odds_persistence_worker = OddsPersistenceWorker(
                OddsHistoryRepo(self.database.pool)
            )
            await self.odds_persistence_worker.start()
            logger.info("OddsPersistenceWorker iniciado — telemetria de odds ATIVA")

            fixture_repo = FixtureMapRepo(self.database.pool)
            self.composite_odds, _composite_stats, self._providers_shutdown = (
                await build_providers(
                    settings=config,
                    api_client=self.api_client,
                    fixture_repo=fixture_repo,
                    odds_persistence_worker=self.odds_persistence_worker,
                )
            )
            logger.info("CompositeOddsProvider ativo (bridge Betano primário)")

        # Restaurar timestamps de jogos ja alertados hoje (sobrevive a restart)
        await self._load_pre_game_alerted()

        # Inicializar config de ligas
        from config import LIGAS_MONITORADAS
        all_liga_ids = [liga["id"] for liga in LIGAS_MONITORADAS]
        await self.database.init_ligas_config(all_liga_ids)

        # Inicializar config de thresholds
        await self.database.init_thresholds_config()

        # Seed dev_mode_config se ainda nao existir (apos isso, DB eh source of truth)
        await self.database.init_dev_mode_config()
        await self._refresh_dev_mode_config(log_change=False)

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
        logger.info(f"Intervalo de polling: {self.effective_polling_interval}s")
        logger.info(f"Grupo WhatsApp: {WHATSAPP_GROUP_ID[:25]}...")
        if self.dev_mode_enabled:
            logger.warning(
                "DEV_TEST_MODE ATIVO: cap %d jogos/ciclo, polling %ds, "
                "status check %ds, budget %d reqs/dia",
                self.dev_max_games,
                self.effective_polling_interval,
                self.effective_status_check_interval,
                self.rate_limiter.max_daily,
            )
        logger.info("")

        # Enviar status inicial via WhatsApp
        await self._send_startup_status()

        # Iniciar healthcheck WAHA em background
        self._healthcheck_task = asyncio.create_task(self._waha_healthcheck_loop())
        logger.info(f"WAHA healthcheck iniciado (intervalo: {WAHA_HEALTHCHECK_INTERVAL}s)")

        # Loop principal
        self._running = True
        try:
            await self._main_loop()
        except KeyboardInterrupt:
            logger.info("Sistema interrompido pelo usuario")
        finally:
            await self._shutdown()

    async def _refresh_dev_mode_config(self, log_change: bool = True):
        """Le dev_mode_config do DB e aplica em runtime (chamado a cada ciclo).

        Quando enabled=true: cap de jogos, polling longo, status check raro, budget reduzido.
        Quando enabled=false: volta aos valores 'normal_*' do config (defaults: 60s/300s/7500).
        """
        try:
            cfg = await self.database.get_state("dev_mode_config")
        except Exception as e:
            logger.debug(f"Falha ao ler dev_mode_config: {e}")
            return

        if not cfg:
            return

        new_enabled = bool(cfg.get("enabled", False))
        was_enabled = self.dev_mode_enabled

        normal_polling = int(cfg.get("normal_polling_interval", 60))
        normal_status = int(cfg.get("normal_status_check_interval", 300))
        normal_daily = int(cfg.get("normal_api_daily_limit", 7500))

        if new_enabled:
            self.dev_max_games = int(cfg.get("max_games", DEV_TEST_MAX_GAMES))
            self.effective_polling_interval = int(cfg.get("polling_interval", 180))
            self.effective_status_check_interval = int(cfg.get("status_check_interval", 1800))
            target_daily = int(cfg.get("api_daily_limit", 1000))
        else:
            self.effective_polling_interval = normal_polling
            self.effective_status_check_interval = normal_status
            target_daily = normal_daily

        self.dev_mode_enabled = new_enabled

        if self.rate_limiter.max_daily != target_daily:
            self.rate_limiter.sync_from_api(
                self.rate_limiter.requests_today, target_daily
            )

        if log_change and was_enabled != new_enabled:
            logger.warning(
                "DEV_TEST_MODE %s | polling=%ss | status_check=%ss | budget=%d/dia | max_games=%d",
                "ATIVADO" if new_enabled else "DESATIVADO (normal)",
                self.effective_polling_interval,
                self.effective_status_check_interval,
                target_daily,
                self.dev_max_games,
            )

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
                await self._save_upcoming_games()
            else:
                logger.info("Nenhum jogo programado para hoje nas ligas monitoradas")
                await self._save_upcoming_games([])
        except Exception as e:
            logger.error(f"Erro ao buscar agenda: {e}")
    
    async def _save_upcoming_games(self, games: List[Dict] = None):
        """Salva próximos jogos no postgres para dashboard."""
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
            await self.database.upsert_state("upcoming_games", {
                "atualizado": datetime.now().isoformat(),
                "proximos": upcoming,
            })
        except Exception as e:
            logger.error(f"Erro ao salvar próximos jogos: {e}")


    async def _save_audit_state(self):
        """Salva dados de auditoria do ciclo para dashboard."""
        try:
            audit_data = self.decision_engine.get_audit_data()
            audit_data["atualizado"] = datetime.now().isoformat()
            audit_data["ciclo"] = self._cycles
            await self.database.upsert_state("audit_state", audit_data)
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
        polling = self.effective_polling_interval
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
            # Jogo em < 15 min: polling normal (ou polling dev se enabled)
            return polling, f"{polling}s", False

    async def _main_loop(self):
        """Loop principal de monitoramento."""
        last_status_check = 0

        while self._running:
            try:
                # Sincronizar config de dev mode (DB eh source of truth)
                await self._refresh_dev_mode_config()

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
                        await self.database.upsert_state("live_state", {
                            "atualizado": datetime.now().isoformat(),
                            "ciclo": self._cycles,
                            "status": "aguardando",
                            "proximo_jogo_min": mins_until if mins_until >= 0 else None,
                            "proximo_check": desc,
                            "pre_janela": [], "na_janela": [], "pos_janela": [],
                            "ids_observados": [],
                        })
                    except Exception:
                        pass

                    await self._check_daily_summary()
                    await self._check_upcoming_notifications()
                    await self._verificar_resultados()

                    # Se ainda ha sinais pendentes (jogos terminados ou prestes a),
                    # reduz o sleep para re-checar rapido em vez de esperar 15min-2h.
                    if self._pending_signals_remaining > 0:
                        sleep_secs = min(sleep_secs, 180)
                        logger.info(
                            f"{self._pending_signals_remaining} sinal(is) pendente(s) "
                            f"-> proximo check em {sleep_secs}s"
                        )

                    await asyncio.sleep(sleep_secs)

                    # Refresh agenda se necessario (busca novos jogos)
                    if refresh_schedule:
                        await self._fetch_today_schedule(force=True)
                        await self._save_upcoming_games()

                    continue

                # Tem jogo rolando ou proximo -> polling ativo
                self._cycles += 1
                logger.info(f"--- Ciclo #{self._cycles} ---")

                # Verificar status periodicamente
                now = time.time()
                if now - last_status_check > self.effective_status_check_interval:
                    try:
                        await self.api_client.check_status()
                        last_status_check = now
                    except Exception:
                        pass

                # Verificar se tem requisicoes disponiveis
                remaining = self.rate_limiter.remaining_daily()
                low_threshold = DEV_TEST_LOW_BUDGET_THRESHOLD if self.dev_mode_enabled else 5
                if remaining < low_threshold:
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
                        await self.database.upsert_state("live_state", {
                            "atualizado": datetime.now().isoformat(),
                            "ciclo": self._cycles,
                            "pre_janela": [], "na_janela": [], "pos_janela": [],
                            "ids_observados": [],
                        })
                    except Exception:
                        pass
                    await self._check_daily_summary()
                    await self._check_upcoming_notifications()
                    await asyncio.sleep(self.effective_polling_interval)
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
                    cart = self._cartoes_cache.get(fixture_id)

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

                    jogos_por_fase[fase].append(_serialize_fixture(fixture, fase, esc, cart))

                # Limpar jogos encerrados
                self.state_manager.limpar_jogos_encerrados(jogos_ativos_ids)
                self.adaptive_polling.clear_finished_games(list(jogos_ativos_ids))
                for gid in list(self._escanteios_cache.keys()):
                    if gid not in jogos_ativos_ids:
                        del self._escanteios_cache[gid]
                for gid in list(self._cartoes_cache.keys()):
                    if gid not in jogos_ativos_ids:
                        del self._cartoes_cache[gid]

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
                    await self.database.upsert_state("live_state", live_state)
                except Exception as e:
                    logger.debug(f"Nao foi possivel salvar live_state: {e}")

                # 3. Analisar apenas jogos que devem ser atualizados (should_poll)
                self.decision_engine.reset_ciclo_stats()
                if ANALISE_CARTOES_ATIVA:
                    self.cards_decision_engine.reset_ciclo_stats()

                if self.dev_mode_enabled and len(jogos_para_analisar) > self.dev_max_games:
                    def _dev_prio(f: Dict) -> tuple:
                        info = f.get("fixture", {}) or {}
                        elapsed = (info.get("status", {}) or {}).get("elapsed", 0) or 0
                        fid = info.get("id", 0)
                        esc = self._escanteios_cache.get(fid, 0) or 0
                        if elapsed > MINUTO_FIM:
                            fase_rank = 1  # pos_janela
                        elif elapsed >= JANELA_ANTECIPADA_INICIO or esc >= 7:
                            fase_rank = 0  # na_janela (prioridade max)
                        else:
                            fase_rank = 2  # pre_janela
                        return (fase_rank, -elapsed, -esc)

                    jogos_para_analisar.sort(key=_dev_prio)
                    descartados = len(jogos_para_analisar) - self.dev_max_games
                    jogos_para_analisar = jogos_para_analisar[:self.dev_max_games]
                    logger.info(
                        f"DEV_TEST_MODE: cap {self.dev_max_games} jogos/ciclo "
                        f"({descartados} jogo(s) descartado(s) por prioridade)"
                    )

                for fixture in jogos_para_analisar:
                    if not self.rate_limiter.can_request():
                        logger.warning("Sem requisicoes - parando analise dos jogos")
                        break

                    jogo = await self._analisar_jogo(fixture)
                    if jogo:
                        fid = fixture.get("fixture", {}).get("id", 0)
                        self._escanteios_cache[fid] = jogo.escanteios_total
                        self._cartoes_cache[fid] = jogo.cartoes_amarelos_total
                        # Atualizar escanteios/cartoes no jogos_por_fase para salvar no live_state
                        for lista in jogos_por_fase.values():
                            for item in lista:
                                if item.get("id") == fid:
                                    item["escanteios"] = jogo.escanteios_total
                                    item["cartoes"] = jogo.cartoes_amarelos_total
                                    break

                # Log relatórios de auditoria do ciclo
                audit_report = self.decision_engine.get_ciclo_report()
                if audit_report:
                    logger.info(audit_report)
                if ANALISE_CARTOES_ATIVA:
                    cards_audit = self.cards_decision_engine.get_ciclo_report()
                    if cards_audit:
                        logger.info(cards_audit)

                # Salvar dados de auditoria para dashboard
                await self._save_audit_state()

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
                    await self.database.upsert_state("live_state", live_state)
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
                    f"Proximo ciclo em {self.effective_polling_interval}s"
                )
                await asyncio.sleep(self.effective_polling_interval)

            except Exception as e:
                logger.error(f"Erro no loop principal: {e}", exc_info=True)
                try:
                    await self.notifier.send_error_alert(str(e))
                except Exception:
                    pass
                await asyncio.sleep(self.effective_polling_interval)

    def _build_canonical_fixture(self, jogo) -> CanonicalFixture:
        """Constrói CanonicalFixture a partir do JogoAoVivo legado.

        Os adapters (bridge e APIFootball) só usam `fixture_id`; `starts_at_utc`
        é obrigatório no dataclass mas não é consumido — usa `kickoff_at` ou
        agora-UTC como fallback inócuo.
        """
        return CanonicalFixture(
            fixture_id=jogo.id,
            home_team=jogo.time_casa,
            away_team=jogo.time_fora,
            league_id=jogo.liga_id,
            starts_at_utc=jogo.kickoff_at or datetime.now(timezone.utc),
            score_home=jogo.placar_casa,
            score_away=jogo.placar_fora,
        )

    def _should_capture(self, fixture_id: int, market: str, interval_sec: int) -> bool:
        """True se já passou `interval_sec` desde a última captura do mercado."""
        last_ms = self._last_capture_at.get((fixture_id, market), 0)
        now_ms = int(time.time() * 1000)
        return (now_ms - last_ms) >= (interval_sec * 1000)

    def _mark_captured(self, fixture_id: int, market: str) -> None:
        self._last_capture_at[(fixture_id, market)] = int(time.time() * 1000)

    async def _capturar_odds_para_telemetria(self, jogo) -> None:
        """Captura odds pra telemetria, desacoplada da emissão de sinal.

        Política (Fase D.0):
          - Só roda com USE_BETANO_BRIDGE (caminho legado não tem telemetria).
          - Janela técnica por mercado (minuto >= X) — antes do kickoff e
            depois do fim do jogo não chega aqui.
          - Ciclo próprio por mercado, independente do ciclo do _main_loop.
          - Persiste catálogo completo + contexto rico via persist_telemetry=True.
        """
        if not USE_BETANO_BRIDGE:
            return
        if jogo.minuto is None or jogo.minuto <= 0:
            return

        canonical_fixture = self._build_canonical_fixture(jogo)
        score = (jogo.placar_casa or 0) + (jogo.placar_fora or 0)
        # Scores calculados sem log — só pra enriquecer a telemetria.
        pressure_score = self.decision_engine.score_engine.calcular(jogo, log=False)
        tension_score = self.cards_decision_engine.score_engine.calcular(jogo, log=False)

        if (
            jogo.minuto >= config.ODDS_CAPTURE_MIN_MINUTE_CORNERS
            and self._should_capture(
                jogo.id, "corners", config.ODDS_CAPTURE_CYCLE_CORNERS_SEC
            )
        ):
            await self.composite_odds.get_corners(
                canonical_fixture, current_score=score, line=None,
                minute=jogo.minuto, pressure_score=pressure_score,
                tension_score=tension_score, persist_telemetry=True,
            )
            self._mark_captured(jogo.id, "corners")

        if (
            jogo.minuto >= config.ODDS_CAPTURE_MIN_MINUTE_CARDS
            and self._should_capture(
                jogo.id, "cards", config.ODDS_CAPTURE_CYCLE_CARDS_SEC
            )
        ):
            await self.composite_odds.get_cards(
                canonical_fixture, current_score=score, line=None,
                minute=jogo.minuto, pressure_score=pressure_score,
                tension_score=tension_score, persist_telemetry=True,
            )
            self._mark_captured(jogo.id, "cards")

        # GOALS dormante: Composite ainda não expõe get_goals (fase futura).
        if (
            jogo.minuto >= config.ODDS_CAPTURE_MIN_MINUTE_GOALS
            and self._should_capture(
                jogo.id, "goals", config.ODDS_CAPTURE_CYCLE_GOALS_SEC
            )
            and hasattr(self.composite_odds, "get_goals")
        ):
            await self.composite_odds.get_goals(
                canonical_fixture, current_score=score, line=None,
                minute=jogo.minuto, pressure_score=pressure_score,
                tension_score=tension_score, persist_telemetry=True,
            )
            self._mark_captured(jogo.id, "goals")

    async def _analisar_jogo(self, fixture: Dict):
        """Analisa um jogo individual (escanteios + cartoes). Retorna jogo se sucesso, None senao."""
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
            # Buscar estatisticas (1 API call — shared by both analyses)
            stats = await self.api_client.get_statistics(fixture_id)

            # Converter para JogoAoVivo
            jogo = parse_fixture_to_jogo(fixture, stats, liga_id)

            # Enriquecer com dados de cartoes (0 API calls, mesmas stats)
            enrich_jogo_with_cards(jogo, stats, liga_id)

            logger.info(
                f"Analisando: {desc} | Min {jogo.minuto} | "
                f"Escanteios: {jogo.escanteios_total} | "
                f"Cartoes: {jogo.cartoes_amarelos_total} | "
                f"Placar: {jogo.placar}"
            )

            # Telemetria full coverage — captura desacoplada de pre_avaliar.
            # Fire-and-forget: falha aqui não bloqueia o pipeline de sinal.
            try:
                await self._capturar_odds_para_telemetria(jogo)
            except Exception as e:
                logger.warning(
                    f"Telemetria de odds falhou para {fixture_id}: {e}"
                )

            # ========== ANALISE ESCANTEIOS ==========
            # Pre-avaliacao: filtros + score SEM buscar odds (economia de 1-2 reqs)
            pre_score = self.decision_engine.pre_avaliar(jogo)
            if pre_score is not None:
                if USE_BETANO_BRIDGE:
                    # Bridge primário: o Composite resolve odds e já cobre o
                    # fallback APIFootball internamente (cascata). A linha vem
                    # do bookmaker (line=None -> política central do adapter).
                    canonical_fixture = self._build_canonical_fixture(jogo)
                    score = (jogo.placar_casa or 0) + (jogo.placar_fora or 0)
                    canonical_corners = await self.composite_odds.get_corners(
                        canonical_fixture, current_score=score, line=None,
                    )
                    if canonical_corners:
                        jogo.linha_atual = canonical_corners.linha
                        jogo.odd_atual = canonical_corners.odd_over
                        jogo.bookmaker_usado = canonical_corners.source
                        jogo.odds_source = canonical_corners.source
                        logger.debug(
                            f"Odds composite para {desc}: "
                            f"linha={canonical_corners.linha} odd={canonical_corners.odd_over} "
                            f"source={canonical_corners.source}"
                        )
                    else:
                        # Bridge + AF ambos falharam: segue sem odds (engine
                        # não emite sinal). Mesma degradação do path legacy.
                        logger.warning(
                            f"composite.get_corners retornou None para {desc} "
                            f"(fixture={fixture_id}) — segue sem odds"
                        )
                else:
                    # PATH LEGACY — multi-bookmaker (Betano + Bet365), intocado.
                    # Jogo passou filtros+score -> buscar odds de Betano e Bet365
                    try:
                        multi_odds = await self.api_client.get_live_odds_multi_bookmaker(fixture_id)
                        if multi_odds:
                            linha = multi_odds.get("linha", 0.0)
                            betano = multi_odds.get("betano", 0.0)
                            bet365 = multi_odds.get("bet365", 0.0)
                            bm_usado = multi_odds.get("bookmaker_usado") or ""
                            l_betano = multi_odds.get("linha_betano", 0.0)
                            l_bet365 = multi_odds.get("linha_bet365", 0.0)
                            if linha:
                                jogo.linha_atual = linha
                            if betano:
                                jogo.odd_betano = betano
                            if bet365:
                                jogo.odd_bet365 = bet365
                            jogo.bookmaker_usado = bm_usado
                            jogo.linha_betano = l_betano
                            jogo.linha_bet365 = l_bet365
                            # odd_atual = melhor odd disponivel (para compatibilidade)
                            melhor = max(betano, bet365)
                            if melhor:
                                jogo.odd_atual = melhor
                            logger.debug(
                                f"Odds multi-bookmaker para {desc}: "
                                f"Betano(odd={betano} linha={l_betano}) Bet365(odd={bet365} linha={l_bet365}) "
                                f"-> usado={bm_usado} linha_final={linha}"
                            )
                    except Exception as odds_err:
                        logger.debug(f"Erro ao buscar odds multi-bookmaker para {desc}: {odds_err}")
                        # Fallback: odds genericas
                        try:
                            odds_data = await self.api_client.get_live_odds(fixture_id)
                            if odds_data:
                                jogo.linha_atual = odds_data.get("linha", jogo.linha_atual)
                                jogo.odd_atual = odds_data.get("odd_over", 1.0)
                        except Exception:
                            pass

            # Salvar snapshot para backtest (com escanteios + cartoes)
            try:
                await self.database.salvar_snapshot(jogo)
            except Exception as snap_err:
                logger.debug(f"Erro ao salvar snapshot: {snap_err}")

            # Avaliacao completa de escanteios com auditoria
            sinal = self.decision_engine.avaliar(jogo)

            if sinal:
                if not self.state_manager.ja_alertou(fixture_id):
                    # 1) Broadcast pro grupo (mensagem genérica)
                    await self.notifier.send_signal(sinal)
                    # 2) DM per-user filtrado por tier + plano (com prefixo da estratégia)
                    users = await self.database.list_users_for_broadcast()
                    sent_count = 0
                    for u in users:
                        ok = await self.notifier.send_signal_to_user(
                            sinal, u["id"], u["whatsapp"], market="corners",
                        )
                        if ok:
                            sent_count += 1
                    logger.info(
                        f"Sinal escanteios entregue a {sent_count}/{len(users)} users elegíveis + grupo: "
                        f"{sinal.jogo.descricao}"
                    )
                    self.notifier.commit_corner_signal(sinal)
                    await self.database.registrar_sinal(sinal)
                    self.state_manager.registrar_alerta(sinal)

                elif self.state_manager.deve_reavaliar(fixture_id, sinal):
                    # Update unificado: re-avaliacao, com tag opcional de entrada
                    # adicional se as condições também baterem. Conta como 1 das
                    # 2 atualizações permitidas (REAVALIACAO_MAX_POR_JOGO).
                    entrada_adicional = self.state_manager.deve_sugerir_entrada_adicional(
                        fixture_id, sinal
                    )
                    self.state_manager.atualizar_reavaliacao(sinal)
                    if entrada_adicional:
                        self.state_manager.registrar_entrada_adicional(fixture_id)

                    await self.notifier.send_reevaluation(
                        sinal, entrada_adicional=entrada_adicional
                    )
                    users = await self.database.list_users_for_broadcast()
                    for u in users:
                        await self.notifier.send_reevaluation_to_user(
                            sinal, u["id"], u["whatsapp"], market="corners",
                            entrada_adicional=entrada_adicional,
                        )
                    self.notifier.commit_corner_signal(sinal)

            # ========== ANALISE CARTOES AMARELOS ==========
            if ANALISE_CARTOES_ATIVA:
                try:
                    # Pre-avaliacao: filtros + tension score SEM buscar odds.
                    # Espelha o path de escanteios — o gate antigo (avaliar)
                    # exigia linha_cartoes > 0, populada SO apos as odds:
                    # deadlock circular que rejeitava 100% dos sinais de cartoes.
                    pre_cards_score = self.cards_decision_engine.pre_avaliar(jogo)
                    if pre_cards_score is not None:
                        if USE_BETANO_BRIDGE:
                            canonical_fixture = self._build_canonical_fixture(jogo)
                            score = (jogo.placar_casa or 0) + (jogo.placar_fora or 0)
                            canonical_cards = await self.composite_odds.get_cards(
                                canonical_fixture, current_score=score, line=None,
                            )
                            if canonical_cards:
                                jogo.linha_cartoes = canonical_cards.linha
                                jogo.odd_cartoes = canonical_cards.odd_over
                                jogo.odds_source_cartoes = canonical_cards.source
                            else:
                                logger.warning(
                                    f"composite.get_cards retornou None para {desc} "
                                    f"(fixture={fixture_id}) — segue sem odds de cartões"
                                )
                        else:
                            # PATH LEGACY — odds de cartões via APIFootball.
                            try:
                                cards_odds = await self.api_client.get_live_odds_cards(fixture_id)
                                if cards_odds:
                                    jogo.linha_cartoes = cards_odds.get("linha", jogo.linha_cartoes)
                                    jogo.odd_cartoes = cards_odds.get("odd_over", jogo.odd_cartoes)
                            except Exception as odds_err:
                                logger.debug(f"Erro ao buscar odds cartoes: {odds_err}")

                        # Avaliacao completa: agora com odds populadas.
                        sinal_cartoes = self.cards_decision_engine.avaliar(jogo)

                        if sinal_cartoes:
                            # Cartões só para plano max (ou admin)
                            cards_users = [
                                u for u in await self.database.list_users_for_broadcast()
                                if u.get("plan") == "max" or u.get("role") == "admin"
                            ]
                            if not self.cards_state_manager.ja_alertou(fixture_id):
                                # 1) Broadcast pro grupo cartões
                                await self.notifier.send_cards_signal(sinal_cartoes)
                                # 2) DM per-user (max ou admin)
                                sent_count = 0
                                for u in cards_users:
                                    ok = await self.notifier.send_cards_signal_to_user(
                                        sinal_cartoes, u["id"], u["whatsapp"], market="cards",
                                    )
                                    if ok:
                                        sent_count += 1
                                logger.info(
                                    f"Sinal cartões entregue a {sent_count}/{len(cards_users)} users max + grupo: "
                                    f"{sinal_cartoes.jogo.descricao}"
                                )
                                self.notifier.commit_cards_signal(sinal_cartoes)
                                await self.database.registrar_sinal_cartoes(sinal_cartoes)
                                self.cards_state_manager.registrar_alerta(sinal_cartoes)

                            elif self.cards_state_manager.deve_reavaliar(fixture_id, sinal_cartoes):
                                self.cards_state_manager.atualizar_reavaliacao(sinal_cartoes)
                                await self.notifier.send_cards_reevaluation(sinal_cartoes)
                                for u in cards_users:
                                    await self.notifier.send_cards_reevaluation_to_user(
                                        sinal_cartoes, u["id"], u["whatsapp"], market="cards",
                                    )
                                self.notifier.commit_cards_signal(sinal_cartoes)
                except Exception as cards_err:
                    logger.error(f"Erro na analise de cartoes para {desc}: {cards_err}")

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

            # Filtrar: só verificar sinais com mais de 30min. get_fixture_result faz
            # short-circuit em 1 req se status != FT/AET/PEN, então polling agressivo
            # antes do jogo terminar custa pouco e fecha a janela PENDENTE rapidamente.
            from datetime import datetime as dt
            agora = dt.now()
            VERIFICACAO_MIN_IDADE_S = 1800  # 30min (era 1h)
            sinais_para_verificar = []
            for s in sinais_pendentes:
                try:
                    ts = dt.fromisoformat(s.timestamp) if isinstance(s.timestamp, str) else s.timestamp
                    if (agora - ts).total_seconds() >= VERIFICACAO_MIN_IDADE_S:
                        sinais_para_verificar.append(s)
                except (ValueError, TypeError):
                    sinais_para_verificar.append(s)  # na duvida, verifica

            if not sinais_para_verificar:
                self._pending_signals_remaining = len(sinais_pendentes)
                logger.debug("Sinais pendentes ainda recentes (<30min), aguardando...")
                return

            logger.info(f"Verificando resultados de {len(sinais_para_verificar)} sinais pendentes...")

            # Separar sinais por tipo de analise
            sinais_escanteios = [s for s in sinais_para_verificar if s.tipo_analise == "ESCANTEIOS"]
            sinais_cartoes = [s for s in sinais_para_verificar if s.tipo_analise == "CARTOES"]

            # DEDUPLICAR: agrupar por jogo_id e tipo_analise
            sinais_esc_por_jogo: dict = {}
            for s in sinais_escanteios:
                if s.jogo_id not in sinais_esc_por_jogo:
                    sinais_esc_por_jogo[s.jogo_id] = s

            sinais_cards_por_jogo: dict = {}
            for s in sinais_cartoes:
                if s.jogo_id not in sinais_cards_por_jogo:
                    sinais_cards_por_jogo[s.jogo_id] = s

            total_jogos = len(sinais_esc_por_jogo) + len(sinais_cards_por_jogo)
            logger.info(
                f"Apos deduplicacao: {total_jogos} jogos unicos "
                f"({len(sinais_esc_por_jogo)} escanteios, {len(sinais_cards_por_jogo)} cartoes)"
            )

            resultados_escanteios = []
            resultados_cartoes = []

            # Verificar resultados de ESCANTEIOS
            for jogo_id, sinal in sinais_esc_por_jogo.items():
                if not self.rate_limiter.can_request():
                    logger.warning("Sem requisicoes disponiveis para verificar resultados")
                    break

                resultado_final = await self.api_client.get_fixture_result(jogo_id)

                if resultado_final:
                    escanteios_final = resultado_final.get("escanteios_totais", 0)
                    linha = sinal.linha
                    
                    resultado = "GREEN" if escanteios_final > linha else "RED"
                    odd = sinal.odd or 1.0
                    roi = (odd - 1.0) if resultado == "GREEN" else -1.0
                    
                    await self.database.atualizar_resultado(
                        jogo_id=jogo_id,
                        resultado=resultado,
                        escanteios_final=escanteios_final,
                        roi=roi,
                        tipo_analise="ESCANTEIOS"
                    )

                    try:
                        await self.database.atualizar_snapshot_resultado(jogo_id, escanteios_final)
                    except Exception as snap_err:
                        logger.debug(f"Erro ao atualizar snapshot resultado: {snap_err}")
                    
                    resultados_escanteios.append({
                        "jogo_id": jogo_id,
                        "jogo_desc": sinal.jogo_descricao,
                        "resultado": resultado,
                        "valor_final": escanteios_final,
                        "linha": linha,
                        "roi": roi,
                        "odd": odd,
                        "tipo": "ESCANTEIOS",
                    })
                    
                    logger.info(
                        f"[ESCANTEIOS] Resultado: {sinal.jogo_descricao} | "
                        f"{escanteios_final} escs (linha {linha}) | {resultado} {roi:+.2f}u"
                    )

            # Verificar resultados de CARTOES
            for jogo_id, sinal in sinais_cards_por_jogo.items():
                if not self.rate_limiter.can_request():
                    logger.warning("Sem requisicoes disponiveis para verificar resultados de cartoes")
                    break

                resultado_final = await self.api_client.get_fixture_result_cards(jogo_id)

                if resultado_final:
                    cartoes_final = resultado_final.get("cartoes_totais", 0)
                    linha = sinal.linha
                    
                    resultado = "GREEN" if cartoes_final > linha else "RED"
                    odd = sinal.odd or 1.0
                    roi = (odd - 1.0) if resultado == "GREEN" else -1.0
                    
                    await self.database.atualizar_resultado(
                        jogo_id=jogo_id,
                        resultado=resultado,
                        escanteios_final=cartoes_final,  # Reutiliza coluna para cartoes
                        roi=roi,
                        tipo_analise="CARTOES"
                    )
                    
                    resultados_cartoes.append({
                        "jogo_id": jogo_id,
                        "jogo_desc": sinal.jogo_descricao,
                        "resultado": resultado,
                        "valor_final": cartoes_final,
                        "linha": linha,
                        "roi": roi,
                        "odd": odd,
                        "tipo": "CARTOES",
                    })
                    
                    logger.info(
                        f"[CARTOES] Resultado: {sinal.jogo_descricao} | "
                        f"{cartoes_final} cartoes (linha {linha}) | {resultado} {roi:+.2f}u"
                    )

            # Enviar notificacoes
            if resultados_escanteios:
                await self._enviar_resultados_whatsapp(resultados_escanteios, tipo="ESCANTEIOS")

            if resultados_cartoes:
                await self._enviar_resultados_whatsapp(resultados_cartoes, tipo="CARTOES")

            # Atualizar contador de pendentes restantes para o loop idle ajustar
            # a cadencia de re-checagem ate todos os sinais serem resolvidos.
            resolvidos = len(resultados_escanteios) + len(resultados_cartoes)
            self._pending_signals_remaining = max(0, len(sinais_pendentes) - resolvidos)

        except Exception as e:
            logger.error(f"Erro ao verificar resultados: {e}", exc_info=True)

    async def _enviar_resultados_whatsapp(self, resultados: list, tipo: str = "ESCANTEIOS"):
        """Envia resumo de resultados via WhatsApp (Sprint 2.4).
        
        Args:
            resultados: Lista de resultados
            tipo: 'ESCANTEIOS' ou 'CARTOES'
        """
        try:
            greens = len([r for r in resultados if r["resultado"] == "GREEN"])
            reds = len([r for r in resultados if r["resultado"] == "RED"])
            roi_total = sum(r["roi"] for r in resultados)
            
            # Emoji e texto baseado no tipo
            if tipo == "CARTOES":
                header_emoji = "\U0001f7e1"  # Yellow circle
                tipo_texto = "CARTÕES"
                unidade = "cartões"
            else:
                header_emoji = "\u26bd"  # Soccer ball
                tipo_texto = "ESCANTEIOS"
                unidade = "escanteios"
            
            msg = f"{header_emoji} *RESULTADOS FINAIS - {tipo_texto}*\n\n"
            
            for r in resultados:
                emoji = "\u2705" if r["resultado"] == "GREEN" else "\u274c"
                valor_final = r.get("valor_final", r.get("escanteios_final", 0))
                msg += (
                    f"{emoji} {r['jogo_desc']}\n"
                    f"   {valor_final} {unidade} vs linha {r['linha']}\n"
                    f"   Odd {r['odd']:.2f}x → {r['roi']:+.2f}u\n\n"
                )
            
            msg += (
                f"\U0001f4c8 *RESUMO:*\n"
                f"\u2705 Greens: {greens}\n"
                f"\u274c Reds: {reds}\n"
                f"\U0001f4b0 ROI: {roi_total:+.2f}u\n"
            )
            
            # Enviar para grupo apropriado
            if tipo == "CARTOES":
                await self.notifier.send_cards_message(msg)
            else:
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
            # Resumo de escanteios (para grupo principal)
            stats_esc = await self.database.get_estatisticas(tipo_analise="ESCANTEIOS")
            await self.notifier.send_daily_summary(stats_esc)
            
            # Resumo de cartões (para grupo de cartões)
            if ANALISE_CARTOES_ATIVA:
                stats_cards = await self.database.get_estatisticas(tipo_analise="CARTOES")
                if stats_cards.get("total", 0) > 0:
                    await self.notifier.send_cards_daily_summary(stats_cards)
            
            self._last_summary_date = now.date()
            logger.info("Resumo diario enviado")

    async def _load_pre_game_alerted(self):
        """Restaura o set de jogos ja alertados hoje (sobrevive restart)."""
        today = datetime.now().strftime("%Y-%m-%d")
        state = await self.database.get_state("pre_game_alerted")
        if state and state.get("date") == today:
            self._pre_game_alerted = set(state.get("timestamps", []))
            logger.info(
                f"Estado pre-game restaurado: {len(self._pre_game_alerted)} jogos ja alertados hoje"
            )
        else:
            self._pre_game_alerted = set()
        self._pre_game_alerted_date = today

    async def _save_pre_game_alerted(self):
        """Persiste o set de jogos alertados em app_state."""
        await self.database.upsert_state("pre_game_alerted", {
            "date": datetime.now().strftime("%Y-%m-%d"),
            "timestamps": list(self._pre_game_alerted),
        })

    async def _check_upcoming_notifications(self):
        """Envia notificacoes de agenda: resumo matinal e alertas pre-jogo."""
        now = datetime.now(timezone.utc)
        today_local = datetime.now().strftime("%Y-%m-%d")

        # Reset quando a data LOCAL muda (não usar UTC: 00h UTC = 21h BRT, zeraria
        # justamente na janela de pre-jogo de partidas das 21:30).
        if today_local != getattr(self, "_pre_game_alerted_date", today_local):
            self._pre_game_alerted.clear()
            self._pre_game_alerted_date = today_local
            await self._save_pre_game_alerted()

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
            await self._save_pre_game_alerted()
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

    async def _waha_healthcheck_loop(self):
        """Loop de healthcheck WAHA — roda em background durante toda a vida do sistema."""
        while self._running:
            try:
                await asyncio.sleep(WAHA_HEALTHCHECK_INTERVAL)
                if not self._running:
                    break

                health = await self._waha_manager.check_session_health()
                status = health.get("status", "UNKNOWN")
                healthy = health.get("healthy", False)
                action = health.get("action_taken", "none")

                if healthy:
                    logger.debug(f"WAHA healthcheck OK: status={status}")
                else:
                    logger.warning(
                        f"WAHA healthcheck ALERTA: status={status}, "
                        f"action={action}, falhas={self._waha_manager._consecutive_failures}"
                    )

                    if self._waha_manager.should_send_alert():
                        alert_msg = (
                            f"\U0001f6a8 *ALERTA WAHA*\n\n"
                            f"Sessão WhatsApp com problema:\n"
                            f"Status: *{status}*\n"
                            f"Ação: {action}\n"
                            f"Falhas consecutivas: {self._waha_manager._consecutive_failures}\n"
                            f"\n"
                            f"Recuperação automática {'funcionou' if healthy else 'FALHOU'}."
                        )
                        try:
                            await self.notifier.send_error_alert(alert_msg)
                            self._waha_manager.mark_alert_sent()
                            logger.info("Alerta WAHA enviado ao admin")
                        except Exception as alert_err:
                            logger.error(f"Falha ao enviar alerta WAHA: {alert_err}")

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Erro no healthcheck WAHA: {e}")

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

        # Parar healthcheck WAHA
        if self._healthcheck_task:
            self._healthcheck_task.cancel()
            try:
                await self._healthcheck_task
            except asyncio.CancelledError:
                pass
            logger.info("WAHA healthcheck encerrado")

        await self.notifier.close()
        await self.api_client.close()
        if self._providers_shutdown is not None:
            await self._providers_shutdown()
        if self.odds_persistence_worker is not None:
            await self.odds_persistence_worker.stop()
            logger.info("OddsPersistenceWorker parado")

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
