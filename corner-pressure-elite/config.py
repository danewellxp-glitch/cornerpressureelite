import os
from dotenv import load_dotenv

load_dotenv()

# --- API-Football ---
API_FOOTBALL_KEY = os.getenv("API_FOOTBALL_KEY", "")
API_FOOTBALL_BASE_URL = "https://v3.football.api-sports.io"
API_DAILY_LIMIT = int(os.getenv("API_DAILY_LIMIT", "100"))

# --- Polling ---
POLLING_INTERVAL = 60  # segundos entre ciclos
STATUS_CHECK_INTERVAL = 300  # verificar status da API a cada 5 min

# --- Janela de Monitoramento ---
MINUTO_INICIO = 50
MINUTO_FIM = 90
# Janela: 50-90 min (analise durante todo o tempo regulamentar)
JANELA_ANTECIPADA_INICIO = 50

# --- Filtros Estruturais ---
MAX_DIFERENCA_GOLS = 2
MIN_ESCANTEIOS_TOTAL = 5
MIN_ESCANTEIOS_5MIN = 1
MIN_ESCANTEIOS_JOGO_MORNO = 7  # 0x0 apos min 60

# --- Pressure Score ---
MIN_SCORE_NORMAL = 8
MIN_SCORE_PREMIUM = 9

# --- Edge ---
MIN_EDGE_NORMAL = 1.3
MIN_EDGE_PREMIUM = 2.0

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
    {"id": 39, "nome": "Premier League", "pais": "England", "media_esperada": 10.8},
    {"id": 78, "nome": "Bundesliga", "pais": "Germany", "media_esperada": 11.2},
    {"id": 71, "nome": "Brasileirão A", "pais": "Brazil", "media_esperada": 9.8},
    {"id": 72, "nome": "Brasileirão B", "pais": "Brazil", "media_esperada": 9.5},
    {"id": 624, "nome": "Carioca A", "pais": "Brazil", "media_esperada": 9.5},
    {"id": 128, "nome": "Liga Profesional Argentina", "pais": "Argentina", "media_esperada": 10.2},
    {"id": 265, "nome": "Primera División Chile", "pais": "Chile", "media_esperada": 10.0},
]

LIGA_IDS = [liga["id"] for liga in LIGAS_MONITORADAS]

# --- WAHA (WhatsApp HTTP API) ---
WAHA_URL = os.getenv("WAHA_URL", "http://localhost:3000")
WAHA_SESSION_NAME = os.getenv("WAHA_SESSION_NAME", "cpes-alerts")
WAHA_API_KEY = os.getenv("WAHA_API_KEY", "")
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
