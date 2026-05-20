import os
from dotenv import load_dotenv

load_dotenv()

# --- API-Football ---
API_FOOTBALL_KEY = os.getenv("API_FOOTBALL_KEY", "")
API_FOOTBALL_BASE_URL = "https://v3.football.api-sports.io"
API_DAILY_LIMIT = int(os.getenv("API_DAILY_LIMIT", "7500"))

# --- Polling ---
POLLING_INTERVAL = 30  # segundos entre ciclos (era 60; reduzido 2026-05-17 — SofaScore primary, AF tem folga)
STATUS_CHECK_INTERVAL = 300  # verificar status da API a cada 5 min

# --- Janela de Monitoramento ---
MINUTO_INICIO = 50
MINUTO_FIM = 90
# Janela: 50-90 min (analise durante todo o tempo regulamentar)
JANELA_ANTECIPADA_INICIO = 50

# --- Filtros Estruturais ---
MAX_DIFERENCA_GOLS = 3  # bloqueia 4x0, 5x1 etc (goleada)
MAX_DIFERENCA_GOLS_1T = 3  # se 3+ gols de diferenca no 1T -> jogo morto
MIN_ESCANTEIOS_TOTAL = 3
MIN_ESCANTEIOS_5MIN = 1
MIN_ESCANTEIOS_JOGO_MORNO = 7  # 0x0 apos min 60
ESCANTEIOS_EARLY_WINDOW = 7  # 7+ escanteios no 1T -> abre janela antecipada
MAX_LINHA_ASIATICA = 12.5  # Bloqueia jogos onde as casas estao cobrando linhas inalcancaveis

# --- Pressure Score ---
MIN_SCORE_NORMAL = 6   # Ajustado para reduzir reds em sinais fracos
MIN_SCORE_PREMIUM = 8

# --- Edge ---
MIN_EDGE_NORMAL = 1.2  # Ajustado para ter mais margem de seguranca
MIN_EDGE_PREMIUM = 1.5

# --- Projecao ---
PROJECAO_MINUTO_TOTAL = 95
AJUSTE_PRESSAO_FATOR = 0.25
AJUSTE_HISTORICO_THRESHOLD = 10.5
AJUSTE_HISTORICO_VALOR = 0.5

# --- Re-avaliacao (escanteios) ---
# Lógica AND/OR (state_manager.deve_reavaliar):
#   delta_min >= REAVALIACAO_MIN_INTERVALO
#   AND (delta_esc >= REAVALIACAO_DELTA_ESCANTEIOS
#        OR delta_edge >= REAVALIACAO_EDGE_DELTA
#        OR delta_score >= REAVALIACAO_SCORE_DELTA
#        OR linha_mudou)
#   AND novo.score >= MIN_SCORE_NORMAL (mantém qualidade)
REAVALIACAO_MIN_INTERVALO = 7  # min entre re-avaliações (era 5)
REAVALIACAO_EDGE_DELTA = 1.5   # recálculo só por matemática realmente significativa
REAVALIACAO_SCORE_DELTA = 2    # 1 ponto é flutuação normal
REAVALIACAO_DELTA_ESCANTEIOS = 3  # pressão real (+3 escanteios desde alerta)
REAVALIACAO_EDGE_REGRESSAO_MAX = 0.3  # se edge regrediu > 0.3, NÃO enviar — não é melhoria
REAVALIACAO_MAX_POR_JOGO = 2  # teto de re-avaliações por jogo (alerta inicial + até 2)

# --- Ligas Monitoradas ---
LIGAS_MONITORADAS = [
    # Big 5 Européias (Season 2025 - calendário europeu)
    {"id": 39, "nome": "Premier League", "pais": "England", "media_esperada": 10.8, "season": 2025},
    {"id": 78, "nome": "Bundesliga", "pais": "Germany", "media_esperada": 11.2, "season": 2025},
    {"id": 135, "nome": "Serie A", "pais": "Italy", "media_esperada": 10.5, "season": 2025},
    {"id": 140, "nome": "La Liga", "pais": "Spain", "media_esperada": 10.3, "season": 2025},

    # Secundárias Européias (Season 2025)
    {"id": 88, "nome": "Eredivisie", "pais": "Netherlands", "media_esperada": 10.6, "season": 2025},
    {"id": 94, "nome": "Liga Portugal", "pais": "Portugal", "media_esperada": 10.0, "season": 2025},
    
    # Brasil (Season 2026 - calendário Brasil começa em 2026)
    {"id": 71, "nome": "Brasileirão A", "pais": "Brazil", "media_esperada": 9.8, "season": 2026},
    {"id": 72, "nome": "Brasileirão B", "pais": "Brazil", "media_esperada": 9.5, "season": 2026},
    {"id": 73, "nome": "Copa do Brasil", "pais": "Brazil", "media_esperada": 9.5, "season": 2026},

    # América do Sul (Season 2026 - calendário hemisfério sul)
    {"id": 128, "nome": "Liga Profesional Argentina", "pais": "Argentina", "media_esperada": 10.2, "season": 2026},

    # América do Norte (Season 2026 - calendário MLS fev→dez)
    {"id": 253, "nome": "MLS", "pais": "USA", "media_esperada": 10.8, "season": 2026},

    # CONMEBOL (Season 2026 - copas continentais sul-americanas, mata-mata fev→nov)
    {"id": 13, "nome": "Copa Libertadores", "pais": "Conmebol", "media_esperada": 10.0, "season": 2026},
    {"id": 11, "nome": "Copa Sul-Americana", "pais": "Conmebol", "media_esperada": 9.8, "season": 2026},
]

LIGA_IDS = [liga["id"] for liga in LIGAS_MONITORADAS]

# --- WAHA (WhatsApp HTTP API) ---
# NOTA: Migrado para WAHA PLUS (webhooks push + seguranca)
# Documentacao: https://waha.devlike.pro/
WAHA_URL = os.getenv("WAHA_URL", "http://localhost:3000")
WAHA_SESSION_NAME = os.getenv("WAHA_SESSION_NAME", "default")
# API Key para WAHA Plus (Bearer token)
WAHA_API_KEY = os.getenv("WAHA_API_KEY", "waha_sk_d3e9f4a1b5c7e2f8a9d1c3e5f7a9b1d3e5f7a9b1")
# Grupo onde sinais sao enviados (formato: ID@g.us)
WHATSAPP_GROUP_ID = os.getenv("WHATSAPP_GROUP_ID", "")
# Numero admin para erros/status (formato: 5541...)
WHATSAPP_ADMIN = os.getenv("WHATSAPP_ADMIN", "")
# Numero adicional para receber updates (formato internacional)
WHATSAPP_UPDATES = os.getenv("WHATSAPP_UPDATES", "")
# Healthcheck WAHA — intervalo em segundos (padrao: 5 min)
WAHA_HEALTHCHECK_INTERVAL = int(os.getenv("WAHA_HEALTHCHECK_INTERVAL", "300"))

# --- Database ---
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://cpes_user:cpes_password@localhost:5432/cpes")

# --- Logging ---
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

# --- Agenda / Fuso ---
# Fuso usado pra montar a AGENDA DO DIA. A API-Football filtra `date` por dia
# UTC quando não recebe `timezone` — isso cortava jogos noturnos sul-americanos
# (Libertadores/Sudamericana 21:30+ BRT viram dia seguinte em UTC). Com este
# timezone, o `date` passa a casar com o dia-calendário local. Ver BUGS.md 2026-05-20.
SCHEDULE_TIMEZONE = os.getenv("SCHEDULE_TIMEZONE", "America/Sao_Paulo")

# --- Resumo Diario ---
DAILY_SUMMARY_TIME = os.getenv("DAILY_SUMMARY_TIME", "23:00")

# --- Notificacoes de Agenda ---
UPCOMING_NOTIFICATION_TIME = os.getenv("UPCOMING_NOTIFICATION_TIME", "08:00")
PRE_GAME_ALERT_MINUTES = int(os.getenv("PRE_GAME_ALERT_MINUTES", "30"))

# ============================================================
# ANALISE DE CARTOES AMARELOS (Over Cards)
# ============================================================
ANALISE_CARTOES_ATIVA = os.getenv("ANALISE_CARTOES_ATIVA", "true").lower() == "true"

# Grupo WhatsApp separado para cartoes
WHATSAPP_GROUP_CARTOES = os.getenv("WHATSAPP_GROUP_CARTOES", "")

# --- Janela de Monitoramento (Cartoes) ---
CARTOES_MINUTO_INICIO = 40  # cartoes comecam mais cedo
CARTOES_MINUTO_FIM = 90
CARTOES_EARLY_WINDOW = 4  # 4+ cartoes antes min 40 -> abre janela

# --- Filtros Estruturais (Cartoes) ---
CARTOES_MAX_DIFERENCA_GOLS = 3
CARTOES_MIN_AMARELOS_TOTAL = 1
CARTOES_MIN_AMARELOS_5MIN = 1
CARTOES_MIN_JOGO_MORNO = 3  # 0x0 apos min 60 com < 3 cartoes -> morno

# --- Tension Score ---
CARTOES_MIN_SCORE_NORMAL = 5
CARTOES_MIN_SCORE_PREMIUM = 8

# --- Edge (Cartoes) ---
CARTOES_MIN_EDGE_NORMAL = 0.5
CARTOES_MIN_EDGE_PREMIUM = 1.2

# --- Projecao (Cartoes) ---
CARTOES_PROJECAO_MINUTO_TOTAL = 95
CARTOES_AJUSTE_TENSAO_FATOR = 0.15
CARTOES_AJUSTE_HISTORICO_THRESHOLD = 4.0
CARTOES_AJUSTE_HISTORICO_VALOR = 0.3

# --- Re-avaliacao (Cartoes) ---
# Mesma lógica AND/OR de escanteios, mas com cartoes em vez de escanteios.
# IMPORTANTE: cards_state_manager.py agora importa essas constantes (antes
# usava as de escanteios silenciosamente — bug corrigido nesta rev).
CARTOES_REAVALIACAO_MIN_INTERVALO = 5  # era 3
CARTOES_REAVALIACAO_EDGE_DELTA = 1.0   # era 0.5 — recálculo significativo
CARTOES_REAVALIACAO_SCORE_DELTA = 2    # era 1
CARTOES_REAVALIACAO_DELTA_CARTOES = 1  # NOVO — exige +1 cartao desde último alerta

# --- Medias historicas de cartoes por liga ---
LIGAS_MEDIA_CARTOES = {
    39: 3.8,   # Premier League
    78: 4.2,   # Bundesliga
    135: 4.8,  # Serie A
    140: 5.0,  # La Liga
    88: 4.0,   # Eredivisie
    94: 4.5,   # Liga Portugal
    71: 4.3,   # Brasileirao A
    72: 4.1,   # Brasileirao B
    73: 4.6,   # Copa do Brasil (eliminatorias = mais tensao)
    128: 4.6,  # Liga Profesional Argentina
    253: 4.0,  # MLS
    13: 5.0,   # Copa Libertadores (mata-mata continental = tensao alta)
    11: 4.8,   # Copa Sul-Americana
}


# --- Asaas API ---
ASAAS_API_URL = os.getenv("ASAAS_API_URL", "https://api.asaas.com/v3")
ASAAS_API_KEY = os.getenv("ASAAS_API_KEY", "")
ASAAS_WEBHOOK_TOKEN = os.getenv("ASAAS_WEBHOOK_TOKEN", "")

# --- Auth ---
JWT_SECRET = os.getenv("JWT_SECRET", "changeme_please_generate_a_secure_random_string")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "43200"))

# --- Email (Resend API) ---
RESEND_API_KEY = os.getenv("RESEND_API_KEY", "")
EMAIL_FROM = os.getenv("EMAIL_FROM", "noreply@pressureiq.com")
APP_URL = os.getenv("APP_URL", "https://pressureiq.com")

# ============================================================
# DEV TEST MODE
# Para testar com key gratuita da API-Football (100 reqs/dia).
# Os valores aqui sao apenas BOOT DEFAULTS — semeados em app_state.dev_mode_config
# na primeira execucao. Em runtime, a fonte de verdade eh a tabela app_state,
# editavel pela dashboard (rota /api/config/dev-mode, admin-only).
# Quando enabled=true, o robo:
#   - Limita o budget diario a `api_daily_limit` (cap em 100)
#   - Sobe polling para `polling_interval` (default 300s)
#   - Sobe status check para `status_check_interval` (default 3600s)
#   - Analisa no maximo `max_games` jogos por ciclo, priorizando janela 50-90.
# ============================================================
DEV_TEST_MODE = os.getenv("DEV_TEST_MODE", "false").lower() == "true"
DEV_TEST_MAX_GAMES = int(os.getenv("DEV_TEST_MAX_GAMES", "5"))
DEV_TEST_POLLING_INTERVAL = int(os.getenv("DEV_TEST_POLLING_INTERVAL", "180"))
DEV_TEST_STATUS_CHECK_INTERVAL = int(os.getenv("DEV_TEST_STATUS_CHECK_INTERVAL", "1800"))
DEV_TEST_API_DAILY_LIMIT = int(os.getenv("DEV_TEST_API_DAILY_LIMIT", "1000"))
DEV_TEST_LOW_BUDGET_THRESHOLD = int(os.getenv("DEV_TEST_LOW_BUDGET_THRESHOLD", "50"))

# ============================================================
# Pivot Betano (Fase C) — Composite providers
# ============================================================
# Default OFF: orquestrador (main.py) segue usando api_client.py direto.
# Quando ON, build_providers() em data.providers.factory monta:
#   CompositeOddsProvider([BetanoOddsProvider, APIFootballOddsProvider])
#   CompositeStatsProvider([BetanoStatsProvider, APIFootballStatsProvider])
# Plano de rollout: ver docs/sprints/README.md "Cronologia de execução".
USE_NEW_PROVIDERS = os.getenv("USE_NEW_PROVIDERS", "false").lower() == "true"
# Quando True, todos providers respondem; divergências logam em logs/provider_drift.jsonl.
DRIFT_CHECK_PROVIDERS = os.getenv("DRIFT_CHECK_PROVIDERS", "false").lower() == "true"
# Gatilho de pré-fetch de odds: se placar < MIN, BetanoOddsProvider devolve None.
MIN_SCORE_TO_FETCH_ODDS = int(os.getenv("MIN_SCORE_TO_FETCH_ODDS", "0"))
# Caminho do JSON com cookies Betano (Fase A/B). Não versionar.
BETANO_COOKIES_PATH = os.getenv("BETANO_COOKIES_PATH", "config/betano_cookies.json")
# Proxies BR opcionais (Webshare) — CSV de URLs http://user:pass@host:port
WEBSHARE_PROXIES = os.getenv("WEBSHARE_PROXIES", "")

# ============================================================
# Betano Bridge (Fase 2 do pivot — substitui acesso direto)
# ============================================================
# Quando ON, build_providers() em data.providers.factory monta:
#   CompositeOddsProvider([BetanoBridgeOddsAdapter, APIFootballOddsProvider])
# Bridge HTTP local (~/cpes-bridge) faz scraping via Chrome+Playwright e
# expõe REST em :8080. Ver docs/sprints/ pra spec completa do bridge.
# Default OFF: comportamento idêntico à USE_NEW_PROVIDERS legacy.
USE_BETANO_BRIDGE = os.getenv("USE_BETANO_BRIDGE", "false").lower() == "true"
# Fase E.1 PRIORIDADE 1 (2026-05-17): quando True, BetanoBridgeOddsAdapter lê
# markets via /event/<id>/state (JSON nativo Danae) em vez de /markets (DOM
# scraping da rota /live/_/<id>/, que foi nuked por anti-bot Cloudflare).
# Default OFF até smoke validar — feature flag de cutover.
USE_NEW_MARKETS_ROUTE = os.getenv("USE_NEW_MARKETS_ROUTE", "false").lower() == "true"
# Fase K — P4-B (2026-05-17): quando True, factory monta CachedBetanoOddsProvider
# em vez de CompositeOddsProvider([bridge, af]). AF removido do path runtime de
# odds — cache stale assume quando bridge falha; cache expirado = sinal bloqueado
# (sistema silente em outage extremo, decisão D4 aprovada). AF continua em uso
# pra discovery + cold checks. Default OFF até smoke validar.
REMOVE_AF_FROM_ODDS_RUNTIME = os.getenv("REMOVE_AF_FROM_ODDS_RUNTIME", "false").lower() == "true"

# Fase K — fidelidade sinal (2026-05-17): antes do envio WhatsApp, refetch
# odds Betano via bridge. Se odd mudou >ODDS_REFETCH_MAX_DRIFT_PCT (15% default)
# OU linha mudou OU adapter retornou stale/None, ABORTA emit (silêncio é melhor
# que sinal errado, mesma filosofia D4). Bridge tem cache 3s, então refetch
# dentro do TTL é instantâneo.
ODDS_REFETCH_BEFORE_EMIT = os.getenv("ODDS_REFETCH_BEFORE_EMIT", "true").lower() == "true"
ODDS_REFETCH_MAX_DRIFT_PCT = float(os.getenv("ODDS_REFETCH_MAX_DRIFT_PCT", "0.15"))
BETANO_BRIDGE_URL = os.getenv("BETANO_BRIDGE_URL", "http://localhost:8080")
# Pós-otimização Fase 2a.1 o bridge faz ~9-12s/consulta; margem pra timeout total.
BETANO_BRIDGE_TIMEOUT_SEC = float(os.getenv("BETANO_BRIDGE_TIMEOUT_SEC", "25.0"))
BETANO_BRIDGE_RETRIES = int(os.getenv("BETANO_BRIDGE_RETRIES", "1"))
# Janela de hidratação Vue passada como query param `capture_seconds`.
BETANO_BRIDGE_CAPTURE_SEC = float(os.getenv("BETANO_BRIDGE_CAPTURE_SEC", "5.0"))
# Política de seleção de linha central quando o adapter consome o catálogo
# (/markets, line=None). Escolhe a linha cujo over_price cai na faixa
# [MIN, MAX]; se nenhuma cai, degrada pra mais próxima do centro da faixa.
BETANO_BRIDGE_PREFERRED_ODD_MIN = float(os.getenv("BETANO_BRIDGE_PREFERRED_ODD_MIN", "1.50"))
BETANO_BRIDGE_PREFERRED_ODD_MAX = float(os.getenv("BETANO_BRIDGE_PREFERRED_ODD_MAX", "1.70"))

# Fase D.2 — descoberta automática de fixtures Betano via bridge /events/live.
# Worker chama bridge periodicamente, casa events com fixtures API-Football,
# UPSERTa em betano_fixture_map. BETANO_EVENT_MAP fica como override manual.
# Só inicia se USE_BETANO_BRIDGE=true (worker depende do bridge).
BETANO_DISCOVERY_ENABLED = os.getenv("BETANO_DISCOVERY_ENABLED", "true").lower() == "true"
BETANO_DISCOVERY_POLL_SEC = int(os.getenv("BETANO_DISCOVERY_POLL_SEC", "150"))
# Threshold de confidence pra fuzzy match Betano ↔ API-Football aceitar.
MATCH_CONFIDENCE_THRESHOLD = float(os.getenv("MATCH_CONFIDENCE_THRESHOLD", "0.85"))


def _parse_betano_event_map(raw: str) -> dict:
    """Parseia "fixture_id1=event_id1,fixture_id2=event_id2" -> {int: str}.

    Seed manual temporário da Fase 2bc: alimenta a tabela betano_fixture_map
    no startup pra o bridge resolver fixture->event_id. A Fase D substitui
    isto por um populador automático (fuzzy match nome+horário).
    """
    mapping: dict = {}
    for par in raw.split(","):
        par = par.strip()
        if not par or "=" not in par:
            continue
        fid, eid = par.split("=", 1)
        fid, eid = fid.strip(), eid.strip()
        if fid.isdigit() and eid:
            mapping[int(fid)] = eid
    return mapping


# Seed manual fixture_id -> betano_event_id. A partir da Fase D.2 isto é
# OVERRIDE OPCIONAL — BetanoFixtureDiscovery descobre fixtures via bridge
# automaticamente. Use BETANO_EVENT_MAP só pra:
#   (a) DEV/debug local (forçar mapping pra teste)
#   (b) overrides manuais quando fuzzy match falha (confidence < threshold)
# UPSERT do seed manual sobrescreve resolved_via como 'manual_seed', então
# inspeção SQL distingue dos resolvidos via discovery.
BETANO_EVENT_MAP = _parse_betano_event_map(os.getenv("BETANO_EVENT_MAP", ""))


# ============================================================
# Telemetria de odds (Fase D.0 — full coverage)
# ============================================================
# Captura desacoplada da emissão de sinal: _capturar_odds_para_telemetria
# em main.py persiste o catálogo completo em odds_history. Só roda com
# USE_BETANO_BRIDGE=true. Ciclos diferenciados por mercado pra caber no
# limite de ~6 req/min de 1 Chrome. GOALS está dormente (sem get_goals
# no Composite ainda) — config existe pra fase futura.
# Ciclos de captura por mercado (segundos entre capturas do mesmo jogo).
ODDS_CAPTURE_CYCLE_CORNERS_SEC = int(os.getenv("ODDS_CAPTURE_CYCLE_CORNERS_SEC", "90"))
ODDS_CAPTURE_CYCLE_CARDS_SEC = int(os.getenv("ODDS_CAPTURE_CYCLE_CARDS_SEC", "240"))
ODDS_CAPTURE_CYCLE_GOALS_SEC = int(os.getenv("ODDS_CAPTURE_CYCLE_GOALS_SEC", "360"))
# Janela técnica mínima por mercado (minuto do jogo). Antes disso não há
# stats live suficientes; após o fim o jogo sai de live e nem entra aqui.
ODDS_CAPTURE_MIN_MINUTE_CORNERS = int(os.getenv("ODDS_CAPTURE_MIN_MINUTE_CORNERS", "15"))
ODDS_CAPTURE_MIN_MINUTE_CARDS = int(os.getenv("ODDS_CAPTURE_MIN_MINUTE_CARDS", "10"))
ODDS_CAPTURE_MIN_MINUTE_GOALS = int(os.getenv("ODDS_CAPTURE_MIN_MINUTE_GOALS", "5"))


# ============================================================
# Stats Betano via bridge (Fase E.1)
# ============================================================
# BridgeStatsAdapter consome `/event/<id>/state` no bridge — reusa pipeline
# D.1 (Brave + danewell renewer + cookie `_cfuvid` aquecido). Stats Betano
# substitui API-Football pra eliminar dependência do crédito AF.
# WIRING: PARTE F' (factory.py) ainda não plugou — flag é a guarda.
USE_BETANO_STATS = os.getenv("USE_BETANO_STATS", "false").lower() == "true"
# Intervalo base entre polls do mesmo fixture (worker pode ser adaptive).
STATS_POLL_INTERVAL_SEC = int(os.getenv("STATS_POLL_INTERVAL_SEC", "15"))
# Maxlen do deque interno do StatsWindowCalculator por fixture. 120 snapshots
# a STATS_POLL_INTERVAL_SEC=15s = 30 min de janela em memória — suficiente
# pras janelas 5/10min com folga.
STATS_WINDOW_HISTORY_SIZE = int(os.getenv("STATS_WINDOW_HISTORY_SIZE", "120"))
# Quanto buscar do stats_history no bootstrap do worker (restart). Default
# 20 min cobre comfortably as janelas de 10min.
STATS_BOOTSTRAP_LOOKBACK_MIN = int(os.getenv("STATS_BOOTSTRAP_LOOKBACK_MIN", "20"))


# ============================================================
# Events Betano via bridge (Fase F — dataset puro)
# ============================================================
# BetanoEventsWorker captura event.incidents[] do mesmo endpoint
# /event/<id>/state já usado pelo BridgeStatsAdapter (Fase E.1).
# Escopo "dataset puro": persiste em events_history, decision_engine NÃO
# consome (PASSO 0 confirmou zero consumidores externos). Alimenta
# Quant H1-H4 (timeline real de eventos).
USE_BETANO_EVENTS = os.getenv("USE_BETANO_EVENTS", "false").lower() == "true"
# Intervalo entre capturas. 30s default — eventos são pontuais (gol, cartão
# etc), polling acima de stats (15s) é desnecessário; dedup do schema absorve
# excesso de qualquer modo.
EVENTS_POLL_INTERVAL_SEC = int(os.getenv("EVENTS_POLL_INTERVAL_SEC", "30"))


# ============================================================
# Lineups Betano via bridge (Fase G.1 — dataset puro)
# ============================================================
# BetanoLineupsWorker captura event.roster (formation + startXI + bench +
# squad) do mesmo endpoint /event/<id>/state da E.1 + F. G.0 confirmou
# CASO α puro (zero nova request HTTP).
# Escopo "dataset puro": persiste em lineups_history, decision_engine
# NÃO consome. Alimenta Quant H2-H4 (formation, qualidade XI, profundidade bench).
USE_BETANO_LINEUPS = os.getenv("USE_BETANO_LINEUPS", "false").lower() == "true"
# Janela máxima (em minutos do jogo) pra tentar capturar lineup. Lineups são
# publicadas pré-jogo / nos primeiros minutos; depois a Betano pode rotacionar
# o snapshot e perder o roster inicial. 5min é colchão seguro.
LINEUPS_MAX_MINUTE = int(os.getenv("LINEUPS_MAX_MINUTE", "5"))


# ============================================================
# SofaScore — fallback dos Composites + dataset extra (Fase K.1)
# ============================================================
# SofaScore via curl_cffi (impersonate Chrome — bypass TLS fingerprint).
# K.0 validou CASO α puro: zero bridge, zero proxy. Investigação completa
# em `docs/architecture/sofascore-api.md`.
#
# Política Composite pós-K.1:
#   Stats/Events: Betano primary → SofaScore fallback → AF super-residual
#   Lineups:      Betano primary; SofaScore enriquece `coach_name` quando
#                 Betano retorna None (chamada paralela barata) +
#                 `missing_players` (lesões/suspensões, novo no schema).
USE_SOFASCORE = os.getenv("USE_SOFASCORE", "false").lower() == "true"
SOFASCORE_RATE_LIMIT_PER_SEC = int(os.getenv("SOFASCORE_RATE_LIMIT_PER_SEC", "10"))
SOFASCORE_TIMEOUT_SEC = float(os.getenv("SOFASCORE_TIMEOUT_SEC", "15"))
SOFASCORE_IMPERSONATE = os.getenv("SOFASCORE_IMPERSONATE", "chrome120")

# AF super-residual (após SofaScore estabilizar — manter 1-2 semanas pra
# regredir rápido se SofaScore degradar). Cascade pós-K.1:
#   Betano → SofaScore → AF (super-residual)
# Setar 0 quando confiança no SofaScore alta. Discovery + cross-check FT
# continuam usando AF independente desta flag (cold path).
AF_SUPER_RESIDUAL_ENABLED = os.getenv("AF_SUPER_RESIDUAL_ENABLED", "true").lower() == "true"

# Enrichment toggle (K.1 B.7): quando Betano primary devolve stats/lineups
# com gaps conhecidos (BETANO_GAPS_STATS / BETANO_GAPS_LINEUPS), Composite
# chama SofaScore em paralelo pra preencher. Falha do enrichment NÃO
# derruba primary. Default ON; setar 'false' pra desligar se causar
# pressão indevida na API SofaScore.
ENABLE_SOFASCORE_ENRICHMENT = os.getenv("ENABLE_SOFASCORE_ENRICHMENT", "true").lower() == "true"
