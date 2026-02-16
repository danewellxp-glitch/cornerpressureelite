import os
from dotenv import load_dotenv

load_dotenv()

# --- API-Football ---
API_FOOTBALL_KEY = os.getenv("API_FOOTBALL_KEY", "")
API_FOOTBALL_BASE_URL = "https://v3.football.api-sports.io"
API_DAILY_LIMIT = int(os.getenv("API_DAILY_LIMIT", "7500"))

# --- Polling ---
POLLING_INTERVAL = 60  # segundos entre ciclos
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

# --- Pressure Score ---
MIN_SCORE_NORMAL = 5   # Cenario B: reduzido de 6 para capturar mais sinais
MIN_SCORE_PREMIUM = 8

# --- Edge ---
MIN_EDGE_NORMAL = 0.7  # Cenario B: reduzido de 0.8 para volume sustentavel
MIN_EDGE_PREMIUM = 1.5

# --- Projecao ---
PROJECAO_MINUTO_TOTAL = 95
AJUSTE_PRESSAO_FATOR = 0.25
AJUSTE_HISTORICO_THRESHOLD = 10.5
AJUSTE_HISTORICO_VALOR = 0.5

# --- Re-avaliacao ---
REAVALIACAO_MIN_INTERVALO = 3  # minutos
REAVALIACAO_EDGE_DELTA = 0.7
REAVALIACAO_SCORE_DELTA = 1

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

    # América do Sul (Season 2026 - calendário hemisfério sul)
    {"id": 128, "nome": "Liga Profesional Argentina", "pais": "Argentina", "media_esperada": 10.2, "season": 2026},
]

LIGA_IDS = [liga["id"] for liga in LIGAS_MONITORADAS]

# --- WAHA (WhatsApp HTTP API) ---
# NOTA: Migrado para WAHA PLUS (webhooks push + segurança)
# Documentação: https://waha.devlike.pro/
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

# --- Database ---
DB_PATH = os.getenv("DB_PATH", "data/cpes.db")

# --- Logging ---
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

# --- Resumo Diario ---
DAILY_SUMMARY_TIME = os.getenv("DAILY_SUMMARY_TIME", "23:00")

# --- Notificacoes de Agenda ---
UPCOMING_NOTIFICATION_TIME = os.getenv("UPCOMING_NOTIFICATION_TIME", "08:00")
PRE_GAME_ALERT_MINUTES = int(os.getenv("PRE_GAME_ALERT_MINUTES", "30"))
