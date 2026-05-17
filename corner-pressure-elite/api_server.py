"""
CPES API - Backend FastAPI para dashboard web.
Expõe dados do sistema: stats, sinais, logs, status.

Uso: uvicorn api_server:app --host 0.0.0.0 --port 8000
"""

import os
import sys
import logging
import json
import asyncio
import aiohttp

sys.path.insert(0, os.path.dirname(__file__))

from fastapi import FastAPI, HTTPException, Request, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer
from sse_starlette.sse import EventSourceResponse
from pydantic import BaseModel, EmailStr
from typing import List, Optional
from datetime import datetime, timedelta
from jose import JWTError, jwt
# from passlib.context import CryptContext

from data.models import User, Subscription, UserStrategyPreference
from notifier.asaas_client import AsaasClient

from config import (
    API_DAILY_LIMIT,
    LIGAS_MONITORADAS,
    MINUTO_INICIO,
    MINUTO_FIM,
    POLLING_INTERVAL,
    WAHA_URL,
    WAHA_SESSION_NAME,
    WAHA_API_KEY,
    WHATSAPP_ADMIN,
    WHATSAPP_UPDATES,
    MIN_SCORE_NORMAL,
    MIN_SCORE_PREMIUM,
    MIN_EDGE_NORMAL,
    MIN_EDGE_NORMAL,
    MIN_EDGE_PREMIUM,
    JWT_SECRET,
    JWT_ALGORITHM,
    ACCESS_TOKEN_EXPIRE_MINUTES,
    WHATSAPP_GROUP_ID,
    WHATSAPP_GROUP_CARTOES,
    APP_URL,
)
from services.email_worker import (
    publish_event,
    process_events,
    EVENT_USER_REGISTERED,
    EVENT_PAYMENT_CONFIRMED,
    EVENT_SUBSCRIPTION_CANCELLED,
    EVENT_SUBSCRIPTION_RENEWED,
    EVENT_CHECKOUT_ABANDONED,
)
from data_reader import (
    get_db_stats,
    get_recent_signals,
    parse_log_for_status,
    read_last_lines,
    get_log_file,
    get_live_state,
    get_upcoming_games,
    get_audit_state,
    get_signals_history,
)
from storage.database import Database
from notifier.whatsapp_client import WhatsAppClient, WAHAConfig
from notifier.waha_manager import send_whatsapp_message, get_waha_last_health, check_waha_health
from notifier.message_formatter import MessageFormatter
from api.public import router as public_router

logger = logging.getLogger("CPES.API")

app = FastAPI(title="CPES API", description="API para dashboard Corner Pressure Elite")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:3001",
        "http://127.0.0.1:3001",
        "https://iqpressure.online",
        "https://www.iqpressure.online",
        "https://membros.iqpressure.online",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(public_router)


# ============= Background task: recovery de checkout abandonado =============

_RECOVERY_INTERVAL_S = 1800  # 30 min
_RECOVERY_MIN_AGE_HOURS = 1


async def _checkout_recovery_loop():
    """Loop infinito: a cada 30min, busca subs pending > 1h e envia recovery email.

    Idempotente via users.recovery_email_sent_at (1 envio por user).
    Re-checa sub.status imediatamente antes de enviar pra evitar enviar pra quem pagou
    entre o filtro e o publish.
    """
    # Aguarda 60s no boot pra não bater no DB durante a inicialização do pool
    await asyncio.sleep(60)
    while True:
        try:
            db = Database()
            asaas = AsaasClient()
            candidates = await db.list_abandoned_checkouts(min_age_hours=_RECOVERY_MIN_AGE_HOURS)
            if candidates:
                logger.info(f"[RECOVERY] {len(candidates)} checkout(s) abandonado(s) detectado(s)")
            for c in candidates:
                # Re-check do status (alguém pode ter pago entre o query e o envio)
                sub = await db.get_subscription_by_user_id(c["user_id"])
                if not sub or sub.status != "pending":
                    continue
                # Regenera invoiceUrl
                invoice_url = await asaas.get_subscription_invoice_url(c["asaas_id"])
                if not invoice_url:
                    logger.warning(
                        f"[RECOVERY] Sem invoice_url para sub {c['asaas_id']} (user {c['user_id']}) — pulando"
                    )
                    continue
                publish_event(EVENT_CHECKOUT_ABANDONED, {
                    "user_id": c["user_id"],
                    "email": c["email"],
                    "full_name": c["full_name"],
                    "plan": c["plan"],
                    "invoice_url": invoice_url,
                })
                # Marca antes do envio efetivo (e-mail é async via worker) pra evitar
                # corrida com a próxima iteração se o worker demorar
                await db.mark_recovery_sent(c["user_id"])
                logger.info(
                    f"[RECOVERY] Recovery email enfileirado para user {c['user_id']} ({c['email']})"
                )
        except Exception as e:
            logger.error(f"[RECOVERY] Erro no loop: {e}", exc_info=True)
        await asyncio.sleep(_RECOVERY_INTERVAL_S)


# ============= Inicialização - Registrar Webhooks =============

@app.on_event("startup")
async def register_webhooks_on_startup():
    """Registra webhooks em WAHA Plus durante a inicialização."""
    if not WAHA_API_KEY:
        logger.warning("WAHA_API_KEY não configurado, pulando registro de webhooks")
        return
    
    max_retries = 30
    retry_delay = 2
    
    logger.info(f"[WEBHOOK] Registrando webhook em sessão '{WAHA_SESSION_NAME}'...")
    
    # Initialize DB
    db = Database()
    await db.init()

    # Start email worker background task
    asyncio.create_task(process_events())
    logger.info("[STARTUP] Email worker iniciado.")

    # Start checkout recovery loop (envia recovery email 1h após sub pending)
    asyncio.create_task(_checkout_recovery_loop())
    logger.info("[STARTUP] Checkout recovery loop iniciado.")

    # Aguardar WAHA ficar disponível
    for attempt in range(1, max_retries + 1):
        try:
            async with aiohttp.ClientSession() as session:
                headers = {"X-Api-Key": WAHA_API_KEY}
                async with session.get(
                    f"{WAHA_URL}/api/sessions",
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=5)
                ) as response:
                    if response.status == 200:
                        logger.info(f"[WEBHOOK] ✓ WAHA disponível após {attempt * retry_delay}s")
                        break
        except Exception as e:
            if attempt == max_retries:
                logger.error(f"[WEBHOOK] ✗ WAHA não respondeu após {max_retries * retry_delay}s: {e}")
                return
            logger.debug(f"[WEBHOOK] Tentativa {attempt}/{max_retries}. Aguardando {retry_delay}s...")
            await asyncio.sleep(retry_delay)
    
    # Registrar webhook
    try:
        async with aiohttp.ClientSession() as session:
            webhook_url = "http://cpes-api:8000/api/webhook/whatsapp"
            headers = {
                "X-Api-Key": WAHA_API_KEY,
                "Content-Type": "application/json"
            }
            payload = {
                "config": {
                    "webhooks": [
                        {
                            "url": webhook_url,
                            "events": ["message"]
                        }
                    ]
                }
            }
            
            async with session.put(
                f"{WAHA_URL}/api/sessions/{WAHA_SESSION_NAME}",
                headers=headers,
                json=payload,
                timeout=aiohttp.ClientTimeout(total=10)
            ) as response:
                result = await response.json()
                
                if response.status == 200 and "webhooks" in result.get("config", {}):
                    logger.info(f"[WEBHOOK] ✓ Webhook registrado com sucesso em {webhook_url}")
                else:
                    logger.warning(f"[WEBHOOK] Resposta inesperada: {response.status} - {result}")
                    
    except Exception as e:
        logger.error(f"[WEBHOOK] ✗ Erro ao registrar webhook: {e}")


# ============= Modelos Pydantic =============
class LigasConfig(BaseModel):
    liga_ids: List[int]


# Modelo Pydantic para POST /api/config/thresholds
class ThresholdsConfig(BaseModel):
    min_score_normal: float = None
    min_score_premium: float = None
    min_edge_normal: float = None
    min_edge_premium: float = None

    class Config:
        extra = "allow"  # Permite fields extras


class DevModeConfig(BaseModel):
    enabled: Optional[bool] = None
    max_games: Optional[int] = None
    polling_interval: Optional[int] = None
    status_check_interval: Optional[int] = None
    api_daily_limit: Optional[int] = None
    normal_polling_interval: Optional[int] = None
    normal_status_check_interval: Optional[int] = None
    normal_api_daily_limit: Optional[int] = None


# --- Auth Models ---
class UserCreate(BaseModel):
    email: EmailStr
    password: str
    full_name: str
    whatsapp: str
    cpf: Optional[str] = None  # CPF obrigatório para checkout Asaas

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class Token(BaseModel):
    access_token: str
    token_type: str
    user: dict

class CheckoutRequest(BaseModel):
    plan: str  # 'pro' or 'max'
    upgrade_from: Optional[str] = None  # 'pro' quando fazendo upgrade de Pro→Max

class VerifyEmailRequest(BaseModel):
    email: EmailStr
    code: str  # 6-digit code

class ResendVerificationRequest(BaseModel):
    email: EmailStr


VALID_STRATEGY_TIERS = ["conservative", "moderate", "aggressive", "brute"]


class StrategyPreferenceUpdate(BaseModel):
    corners_strategy: Optional[str] = None
    cards_strategy: Optional[str] = None


class StrategyPreferenceResponse(BaseModel):
    corners_strategy: str
    cards_strategy: str
    updated_at: Optional[str] = None


class SignalAnnotation(BaseModel):
    signal_id: int
    tipo_sinal: str
    pressure_score: int
    edge: float
    matches_user_strategy: bool
    matched_tiers: List[str]

# --- Auth Utils ---
# from passlib.context import CryptContext (Removed)
import bcrypt

# pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto") (Removed)
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/auth/login")

def verify_password(plain_password, hashed_password):
    # Ensure bytes for bcrypt
    if isinstance(plain_password, str):
        plain_password = plain_password.encode('utf-8')
    if isinstance(hashed_password, str):
        hashed_password = hashed_password.encode('utf-8')
    return bcrypt.checkpw(plain_password, hashed_password)

def get_password_hash(password):
    if isinstance(password, str):
        password = password.encode('utf-8')
    return bcrypt.hashpw(password, bcrypt.gensalt()).decode('utf-8')

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, JWT_SECRET, algorithm=JWT_ALGORITHM)
    return encoded_jwt

async def get_current_user(token: str = Depends(oauth2_scheme)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    
    db = Database()
    user = await db.get_user_by_email(email)
    if user is None:
        raise credentials_exception
    return user

async def get_current_active_user(current_user: User = Depends(get_current_user)):
    # Aqui poderia checar se o user está ativo/banido
    return current_user


async def require_admin(current_user: User = Depends(get_current_active_user)) -> User:
    """Dependency: bloqueia 403 se o user nao for admin."""
    if (current_user.role or "user") != "admin":
        raise HTTPException(status_code=403, detail="Admin role required")
    return current_user


async def require_max_plan(
    current_user: User = Depends(get_current_active_user),
) -> User:
    """Dependency: libera só pra users com plano Max ativo (ou admin)."""
    if (current_user.role or "user") == "admin":
        return current_user
    db = Database()
    sub = await db.get_subscription_by_user_id(current_user.id)
    if not sub or sub.status != "active":
        raise HTTPException(status_code=403, detail="Assinatura ativa necessária.")
    if sub.plan != "max":
        raise HTTPException(
            status_code=403,
            detail="Robô Auto-Aposta disponível apenas no plano Max.",
        )
    if sub.expires_at:
        exp = sub.expires_at
        if isinstance(exp, str):
            try:
                exp = datetime.fromisoformat(exp)
            except ValueError:
                exp = None
        if exp and exp < datetime.now():
            raise HTTPException(status_code=403, detail="Assinatura expirada.")
    return current_user


async def require_paid_subscription(
    current_user: User = Depends(get_current_active_user),
) -> User:
    """Dependency: libera só para usuários com assinatura ativa (ou admin)."""
    if (current_user.role or "user") == "admin":
        return current_user
    db = Database()
    sub = await db.get_subscription_by_user_id(current_user.id)
    if not sub or sub.status != "active":
        raise HTTPException(status_code=402, detail="Assinatura inativa")
    if sub.expires_at:
        exp = sub.expires_at
        if isinstance(exp, str):
            try:
                exp = datetime.fromisoformat(exp)
            except ValueError:
                exp = None
        if exp and exp < datetime.now():
            raise HTTPException(status_code=402, detail="Assinatura expirada")
    return current_user



@app.get("/")
def root():
    return {"service": "CPES API", "docs": "/docs"}


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.get("/api/whatsapp/health")
async def whatsapp_health(_: User = Depends(require_admin)):
    """Healthcheck da sessão WAHA com último status conhecido."""
    last = get_waha_last_health()
    if last:
        return last
    return {"status": "UNKNOWN", "healthy": False, "action_taken": "never_checked", "details": {}}


@app.post("/api/whatsapp/health/check")
async def whatsapp_health_check(_: User = Depends(require_admin)):
    """Força um healthcheck WAHA imediato com tentativa de recuperação."""
    result = await check_waha_health()
    return result


@app.get("/api/stats")
async def api_stats(type: Optional[str] = None, _: User = Depends(require_paid_subscription)):
    """Estatísticas de performance (1D, 7D, 30D, total)."""
    return await get_db_stats(tipo_analise=type)


@app.get("/api/signals/list")
async def api_signals_list(
    result: str = "all",
    limit: int = 100,
    _: User = Depends(require_paid_subscription),
):
    """Lista sinais filtrados por resultado: 'all' | 'GREEN' | 'RED' | 'PENDENTE'.

    Usado pelo drawer dos KPI cards do dashboard.
    """
    if result not in ("all", "GREEN", "RED", "PENDENTE"):
        raise HTTPException(400, "result deve ser one of all|GREEN|RED|PENDENTE")
    if limit < 1 or limit > 500:
        raise HTTPException(400, "limit 1..500")

    db = Database()
    await db.connect()
    async with db.pool.acquire() as conn:
        if result == "PENDENTE":
            where = "resultado IS NULL"
        elif result == "all":
            where = "TRUE"
        else:
            where = "resultado = $1"

        sql = f"""
            SELECT id, timestamp, liga_nome, jogo_descricao, tipo_sinal,
                   pressure_score, projecao, edge, linha, odd,
                   resultado, escanteios_final, tipo_analise, matching_tiers,
                   minuto, placar, roi
            FROM sinais
            WHERE {where} AND reavaliacao = FALSE
            ORDER BY timestamp DESC
            LIMIT ${'1' if result == 'all' or result == 'PENDENTE' else '2'}
        """
        params = []
        if result not in ("all", "PENDENTE"):
            params.append(result)
        params.append(limit)
        rows = await conn.fetch(sql, *params)

    return [
        {
            "id": r["id"],
            "timestamp": r["timestamp"].isoformat() if r["timestamp"] else None,
            "liga_nome": r["liga_nome"],
            "jogo_descricao": r["jogo_descricao"],
            "tipo_sinal": r["tipo_sinal"],
            "pressure_score": r["pressure_score"],
            "projecao": float(r["projecao"]) if r["projecao"] is not None else None,
            "edge": float(r["edge"]) if r["edge"] is not None else None,
            "linha": float(r["linha"]) if r["linha"] is not None else None,
            "odd": float(r["odd"]) if r["odd"] is not None else None,
            "resultado": r["resultado"] or "PENDENTE",
            "escanteios_final": r["escanteios_final"],
            "tipo_analise": r["tipo_analise"] or "ESCANTEIOS",
            "matching_tiers": list(r["matching_tiers"] or []),
            "minuto": r["minuto"],
            "placar": r["placar"],
            "roi": float(r["roi"]) if r["roi"] is not None else None,
        }
        for r in rows
    ]


@app.get("/api/signals/recent")
async def api_signals_recent(
    limit: int = 5,
    type: Optional[str] = None,
    _: User = Depends(require_paid_subscription),
):
    """Últimos sinais emitidos."""
    rows = await get_recent_signals(limit=limit, tipo_analise=type)
    return [
        {
            "timestamp": r["timestamp"].isoformat() if hasattr(r.get("timestamp"), "isoformat") else r.get("timestamp"),
            "jogo_descricao": r.get("jogo_descricao"),
            "tipo_sinal": r.get("tipo_sinal"),
            "pressure_score": r.get("pressure_score"),
            "projecao": float(r["projecao"]) if r.get("projecao") is not None else None,
            "edge": float(r["edge"]) if r.get("edge") is not None else None,
            "linha": float(r["linha"]) if r.get("linha") is not None else None,
            "odd": float(r["odd"]) if r.get("odd") is not None else None,
            "resultado": r.get("resultado") or "PENDENTE",
            "escanteios_final": r.get("escanteios_final"),
            "tipo_analise": r.get("tipo_analise") or "ESCANTEIOS",
        }
        for r in rows
    ]


@app.get("/api/status")
def api_status(_: User = Depends(require_paid_subscription)):
    """Status do sistema extraído do log (ciclo, jogos ao vivo, API usage)."""
    log_file = get_log_file()
    log_lines = read_last_lines(log_file, 50)
    status = parse_log_for_status(log_lines)
    return {
        **status,
        "minuto_inicio": MINUTO_INICIO,
        "minuto_fim": MINUTO_FIM,
        "polling_interval": POLLING_INTERVAL,
    }


@app.get("/api/logs")
def api_logs(lines: int = 50, _: User = Depends(require_admin)):
    """Últimas linhas do log."""
    log_file = get_log_file()
    log_lines = read_last_lines(log_file, lines)
    # Remove ANSI/encoding issues - retorna texto limpo
    return {"lines": [line.rstrip() for line in log_lines]}


@app.get("/api/polling-stats")
async def api_polling_stats(_: User = Depends(require_paid_subscription)):
    """Estatísticas do polling (motor de economia)."""
    live = await get_live_state()
    stats = live.get("polling_stats", {})
    return {
        "intervalos": {
            "primeiro_tempo_0_30": "5 min (0-30)",
            "pre_janela_31_50": "3 min (31-50)",
            "pre_janela_early_7esc": "1 min (31-50 com 7+ esc) - EARLY TRIGGER",
            "janela_analise": "30 seg (50-90) - JANELA",
            "reta_final": "30 seg (90+ acréscimos) - FASE CRITICA",
        },
        "jogos_monitorados": stats.get("jogos_monitorados", 0),
        "jogos_analisando": stats.get("jogos_analisando", 0),
        "economia_pct": stats.get("economia_pct", 0),
        "destaque": "0-30: 5m | 31-50: 3m (ou 1m se 7+ esc) | 50-90: 30s | 90+: 30s",
    }


@app.get("/api/live-games")
async def api_live_games(_: User = Depends(require_paid_subscription)):
    """Estado das filas de monitoramento."""
    return await get_live_state()


@app.get("/api/upcoming-games")
async def api_upcoming_games(_: User = Depends(require_paid_subscription)):
    """Agenda de jogos."""
    return await get_upcoming_games()

def api_config():
    """Configuração do sistema (ligas, janela)."""
    return {
        "ligas": LIGAS_MONITORADAS,
        "minuto_inicio": MINUTO_INICIO,
        "minuto_fim": MINUTO_FIM,
        "api_daily_limit": API_DAILY_LIMIT,
        "polling_interval": POLLING_INTERVAL,
    }


@app.get("/api/config/leagues")
async def api_get_ligas(_: User = Depends(require_paid_subscription)):
    """Retorna lista de liga_ids ativas."""
    db = Database()
    ligas_ativas = await db.get_ligas_ativas()
    
    # Mapeia IDs a nomes
    liga_map = {liga["id"]: liga["nome"] for liga in LIGAS_MONITORADAS}
    
    return {
        "ativas": ligas_ativas,
        "todas": LIGAS_MONITORADAS,
        "nomes": {liga_id: liga_map.get(liga_id, "Unknown") for liga_id in ligas_ativas}
    }


@app.post("/api/config/leagues")
async def api_set_ligas(config: LigasConfig, _: User = Depends(require_admin)):
    """Atualiza quais ligas devem ser monitoradas."""
    # Valida se os IDs são válidos
    liga_ids_validos = {liga["id"] for liga in LIGAS_MONITORADAS}
    for liga_id in config.liga_ids:
        if liga_id not in liga_ids_validos:
            raise HTTPException(
                status_code=400,
                detail=f"Liga ID {liga_id} not found"
            )
    
    db = Database()
    await db.set_ligas_ativas(config.liga_ids)
    
    return {
        "status": "updated",
        "ligas_ativas": config.liga_ids,
        "total": len(config.liga_ids)
    }


@app.get("/api/config/thresholds")
async def api_get_thresholds(_: User = Depends(require_paid_subscription)):
    """Retorna thresholds atuais."""
    db = Database()
    thresholds = await db.get_thresholds()
    
    return {
        "thresholds": thresholds,
    }


@app.post("/api/config/thresholds")
async def api_set_thresholds(config: ThresholdsConfig, _: User = Depends(require_admin)):
    """Atualiza valores de thresholds (pressure_score e edge)."""
    db = Database()

    # Converter para dict, ignorando None values
    updates = {}
    for key, value in config.dict().items():
        if value is not None:
            updates[key] = value

    if not updates:
        raise HTTPException(
            status_code=400,
            detail="No threshold values provided"
        )

    await db.set_thresholds(updates)

    return {
        "status": "updated",
        "atualizados": updates
    }


@app.get("/api/config/dev-mode")
async def api_get_dev_mode(_: User = Depends(require_admin)):
    """Retorna config de DEV TEST MODE (somente admin)."""
    db = Database()
    config = await db.get_state("dev_mode_config")
    if config is None:
        await db.init_dev_mode_config()
        config = await db.get_state("dev_mode_config")
    return {"config": config or {}}


@app.post("/api/config/dev-mode")
async def api_set_dev_mode(
    payload: DevModeConfig,
    _: User = Depends(require_admin),
):
    """Atualiza config de DEV TEST MODE (somente admin).

    Aplica em runtime: o robo le essa config no inicio de cada ciclo.
    """
    db = Database()
    current = await db.get_state("dev_mode_config")
    if current is None:
        await db.init_dev_mode_config()
        current = await db.get_state("dev_mode_config") or {}

    updates = {k: v for k, v in payload.dict().items() if v is not None}

    # Validacoes basicas de range
    if "max_games" in updates and not (1 <= updates["max_games"] <= 20):
        raise HTTPException(400, "max_games deve estar entre 1 e 20")
    if "polling_interval" in updates and not (60 <= updates["polling_interval"] <= 3600):
        raise HTTPException(400, "polling_interval deve estar entre 60s e 3600s")
    if "status_check_interval" in updates and not (60 <= updates["status_check_interval"] <= 86400):
        raise HTTPException(400, "status_check_interval deve estar entre 60s e 86400s")
    if "api_daily_limit" in updates and not (10 <= updates["api_daily_limit"] <= 100000):
        raise HTTPException(400, "api_daily_limit deve estar entre 10 e 100000")

    current.update(updates)
    await db.upsert_state("dev_mode_config", current)
    return {"status": "updated", "config": current}


@app.post("/api/dev/asaas/approve/{payment_id}")
async def api_dev_asaas_approve(
    payment_id: str,
    _: User = Depends(require_admin),
):
    """Aprova manualmente uma cobranca Asaas em AWAITING_RISK_ANALYSIS.

    Util no sandbox para nao precisar abrir o painel a cada compra de teste.
    """
    asaas = AsaasClient()
    ok = await asaas.approve_by_risk_analysis(payment_id)
    if not ok:
        raise HTTPException(status_code=502, detail="Asaas nao aprovou a cobranca")
    return {"status": "approved", "payment_id": payment_id}


@app.get("/api/audit")
async def api_audit(_: User = Depends(require_paid_subscription)):
    """Dados de auditoria: funil de decisao, filtros, jogos detalhados, historico."""
    audit = await get_audit_state()
    history = await get_signals_history(days=7)
    stats_hoje = await get_db_stats()

    return {
        "atualizado": audit.get("atualizado"),
        "ciclo": audit.get("ciclo", 0),
        "funil": audit.get("funil", {}),
        "filtros_breakdown": audit.get("filtros_breakdown", {}),
        "jogos": audit.get("jogos", []),
        "taxas": audit.get("taxas", {}),
        "sinais_hoje": stats_hoje,
        "historico_7d": history,
        "config": {
            "min_score_normal": MIN_SCORE_NORMAL,
            "min_score_premium": MIN_SCORE_PREMIUM,
            "min_edge_normal": MIN_EDGE_NORMAL,
            "min_edge_premium": MIN_EDGE_PREMIUM,
        },
    }


async def _build_dashboard_payload() -> dict:
    """Helper interno: monta o payload do dashboard. Usado pela rota e pelo SSE."""
    stats = await get_db_stats()
    recent = await get_recent_signals(10)
    log_file = get_log_file()
    log_lines = read_last_lines(log_file, 30)
    status = parse_log_for_status(log_lines)

    signals = [
        {
            "timestamp": r["timestamp"].isoformat() if hasattr(r.get("timestamp"), "isoformat") else r.get("timestamp"),
            "jogo_descricao": r.get("jogo_descricao"),
            "tipo_sinal": r.get("tipo_sinal"),
            "pressure_score": r.get("pressure_score"),
            "projecao": float(r["projecao"]) if r.get("projecao") is not None else None,
            "edge": float(r["edge"]) if r.get("edge") is not None else None,
            "linha": float(r["linha"]) if r.get("linha") is not None else None,
            "odd": float(r["odd"]) if r.get("odd") is not None else None,
            "resultado": r.get("resultado") or "PENDENTE",
            "escanteios_final": r.get("escanteios_final"),
            "tipo_analise": r.get("tipo_analise") or "ESCANTEIOS",
        }
        for r in recent
    ]

    live_state = await get_live_state()

    return {
        "stats": stats,
        "status": {**status, "minuto_inicio": MINUTO_INICIO, "minuto_fim": MINUTO_FIM},
        "signals": signals,
        "logs": [line.rstrip() for line in log_lines[-15:]],
        "ligas": LIGAS_MONITORADAS,
        "live_games": live_state,
    }


@app.get("/api/dashboard")
async def api_dashboard(_: User = Depends(require_paid_subscription)):
    """Todos os dados para o dashboard em uma única chamada."""
    return await _build_dashboard_payload()


async def _authenticate_sse(request: Request, token: Optional[str]) -> User:
    """Auth para SSE: aceita token via query (?token=) OU header Authorization.
    EventSource não envia header — query é o padrão. JWT já expira, mitigando
    o risco de vazamento via logs/history.
    """
    raw = token
    if not raw:
        auth_header = request.headers.get("Authorization", "")
        if auth_header.lower().startswith("bearer "):
            raw = auth_header[7:].strip()
    if not raw:
        raise HTTPException(status_code=401, detail="Token ausente")
    try:
        payload = jwt.decode(raw, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        email = payload.get("sub")
        if not email:
            raise HTTPException(status_code=401, detail="Token inválido")
    except JWTError:
        raise HTTPException(status_code=401, detail="Token inválido")
    db = Database()
    user = await db.get_user_by_email(email)
    if not user:
        raise HTTPException(status_code=401, detail="Usuário não encontrado")
    # mesma checagem do require_paid_subscription
    if (user.role or "user") != "admin":
        sub = await db.get_subscription_by_user_id(user.id)
        if not sub or sub.status != "active":
            raise HTTPException(status_code=402, detail="Assinatura inativa")
    return user


@app.get("/api/stream/dashboard")
async def stream_dashboard(request: Request, token: Optional[str] = None):
    """SSE endpoint. Auth via ?token= (EventSource) ou Authorization header."""
    await _authenticate_sse(request, token)

    async def event_generator():
        # Envia estado inicial imediatamente
        ultimo_estado = await _build_dashboard_payload()
        yield {
            "event": "message",
            "data": json.dumps(ultimo_estado)
        }

        while True:
            # Se o cliente desconectou, paramos
            if await request.is_disconnected():
                break

            estado_atual = await _build_dashboard_payload()
            
            # Envia se algo mudou (na prática seria melhor checar hash ou updated_at, 
            # mas simplificamos por envio caso a estrutura mude)
            if estado_atual != ultimo_estado:
                ultimo_estado = estado_atual
                yield {
                    "event": "message",
                    "data": json.dumps(ultimo_estado)
                }
            
            await asyncio.sleep(2)  # Verifica mudanças a cada 2 segundos

    return EventSourceResponse(event_generator())


# ============= Auth Endpoints =============

@app.post("/api/auth/register")
async def register(user: UserCreate):
    db = Database()

    # Verificar se email ja existe
    existing = await db.get_user_by_email(user.email)
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")

    # Validar que o número está no WhatsApp (fail-open se WAHA offline)
    waha_config = WAHAConfig(
        base_url=WAHA_URL, session_name=WAHA_SESSION_NAME, api_key=WAHA_API_KEY,
    )
    async with WhatsAppClient(waha_config) as wa:
        exists = await wa.check_number_exists(user.whatsapp)
    if not exists:
        raise HTTPException(
            status_code=400,
            detail="Número não está no WhatsApp. Confira o DDD e tente novamente.",
        )

    hashed_password = get_password_hash(user.password)

    new_user = User(
        email=user.email,
        password_hash=hashed_password,
        full_name=user.full_name,
        whatsapp=user.whatsapp,
        cpf=user.cpf or "",
        is_verified=False,
    )

    user_id = await db.create_user(new_user)
    if not user_id:
        raise HTTPException(status_code=500, detail="Could not create user")

    # Publicar evento — worker envia email com código de verificação (não bloqueia o request)
    publish_event(EVENT_USER_REGISTERED, {
        "user_id": user_id,
        "email": user.email,
        "full_name": user.full_name,
    })

    return {
        "message": "Conta criada! Verifique seu email para ativar a conta.",
        "email": user.email,
        "requires_verification": True,
    }


@app.post("/api/auth/verify-email")
async def verify_email(body: VerifyEmailRequest):
    """Valida código de 6 dígitos enviado por email."""
    db = Database()
    ok, message = await db.verify_email_code(body.email, body.code)

    if not ok:
        raise HTTPException(status_code=400, detail=message)

    # Email verificado — emitir token JWT
    user = await db.get_user_by_email(body.email)
    access_token = create_access_token(
        data={"sub": body.email},
        expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
    )
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": {
            "email": user.email,
            "full_name": user.full_name,
            "whatsapp": user.whatsapp,
            "role": user.role,
        },
    }


@app.post("/api/auth/resend-verification")
async def resend_verification(body: ResendVerificationRequest):
    """Reenvia código de verificação (rate limit: 1 por 60s via expires_at)."""
    from datetime import datetime, timedelta
    db = Database()
    user = await db.get_user_by_email(body.email)

    if not user:
        # Não revelar se email existe ou não (segurança)
        return {"message": "Se o email estiver cadastrado, um novo código será enviado."}

    if user.is_verified:
        return {"message": "Email já verificado."}

    # Rate limit: mínimo 60s entre reenvios (código expira em 15min)
    # → bloquear se ainda restam mais de (15 - 1) = 14 min de validade
    RESEND_COOLDOWN_S = 60
    if user.verification_expires_at:
        try:
            exp = user.verification_expires_at
            if isinstance(exp, str):
                exp = datetime.fromisoformat(exp)
            unlock_at = exp - timedelta(minutes=15) + timedelta(seconds=RESEND_COOLDOWN_S)
            remaining = int((unlock_at - datetime.now()).total_seconds())
            if remaining > 0:
                raise HTTPException(
                    status_code=429,
                    detail=f"Aguarde {remaining}s antes de pedir novo código.",
                )
        except HTTPException:
            raise
        except Exception:
            pass

    publish_event(EVENT_USER_REGISTERED, {
        "user_id": user.id,
        "email": user.email,
        "full_name": user.full_name,
    })
    return {"message": "Se o email estiver cadastrado, um novo código será enviado."}

@app.post("/api/auth/login", response_model=Token)
async def login(user_in: UserLogin):
    db = Database()
    user = await db.get_user_by_email(user_in.email)
    if not user or not verify_password(user_in.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Bloquear login até verificação de email
    if not user.is_verified:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Email não verificado. Verifique sua caixa de entrada.",
        )

    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.email}, expires_delta=access_token_expires
    )

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": {
            "email": user.email,
            "full_name": user.full_name,
            "whatsapp": user.whatsapp,
            "role": user.role
        }
    }

@app.get("/api/users/me")
async def read_users_me(current_user: User = Depends(get_current_active_user)):
    db = Database()
    sub = await db.get_subscription_by_user_id(current_user.id)
    
    return {
        "user": {
            "id": current_user.id,
            "email": current_user.email,
            "full_name": current_user.full_name,
            "whatsapp": current_user.whatsapp,
            "role": current_user.role
        },
        "subscription": {
            "valid": sub.status == "active" if sub else False,
            "plan": sub.plan if sub else "free",
            "status": sub.status if sub else "none",
            "starts_at": sub.starts_at if sub else None,
            "expires_at": sub.expires_at if sub else None
        } if sub else None
    }


# ============= User Strategy Preference Endpoints =============

@app.get("/api/user/strategy-preference", response_model=StrategyPreferenceResponse)
async def get_strategy_preference(current_user: User = Depends(get_current_active_user)):
    """Returns current strategy preferences for the authenticated user."""
    db = Database()
    prefs = await db.get_user_strategies(current_user.id)
    updated_at = await db.get_user_strategy_preference_updated_at(current_user.id)

    return StrategyPreferenceResponse(
        corners_strategy=prefs["corners"],
        cards_strategy=prefs["cards"],
        updated_at=updated_at.isoformat() if updated_at else None,
    )


@app.put("/api/user/strategy-preference", response_model=StrategyPreferenceResponse)
async def update_strategy_preference(
    body: StrategyPreferenceUpdate,
    current_user: User = Depends(require_paid_subscription)
):
    """Updates strategy preferences for the authenticated user."""
    db = Database()
    existing = await db.get_user_strategies(current_user.id)

    corners = body.corners_strategy or existing["corners"]
    cards = body.cards_strategy or existing["cards"]

    if corners not in VALID_STRATEGY_TIERS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid corners_strategy: {corners}. Must be one of {VALID_STRATEGY_TIERS}"
        )
    if cards not in VALID_STRATEGY_TIERS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid cards_strategy: {cards}. Must be one of {VALID_STRATEGY_TIERS}"
        )

    await db.set_user_strategy(current_user.id, "corners", corners)
    cards_pref = await db.set_user_strategy(current_user.id, "cards", cards)

    return StrategyPreferenceResponse(
        corners_strategy=corners,
        cards_strategy=cards,
        updated_at=cards_pref.updated_at.isoformat() if cards_pref.updated_at else None,
    )


# ============= Notification Settings =============

class NotificationSettings(BaseModel):
    paused_until: Optional[datetime] = None


@app.get("/api/user/notifications", response_model=NotificationSettings)
async def get_notification_settings(current_user: User = Depends(get_current_active_user)):
    db = Database()
    paused_until = await db.get_notifications_paused_until(current_user.id)
    return NotificationSettings(paused_until=paused_until)


@app.patch("/api/user/notifications", response_model=NotificationSettings)
async def set_notification_settings(
    body: NotificationSettings,
    current_user: User = Depends(get_current_active_user),
):
    db = Database()
    # paused_until=None reativa imediato
    await db.set_notifications_paused_until(current_user.id, body.paused_until)
    paused = await db.get_notifications_paused_until(current_user.id)
    return NotificationSettings(paused_until=paused)


# ============= Robô Auto-Aposta =============

VALID_BET_HOUSES = ("betano", "bet365", "kto")
VALID_BOT_MARKETS = ("corners", "cards")


class BotConfigPatch(BaseModel):
    enabled: Optional[bool] = None
    bet_house: Optional[str] = None
    banca_inicial_cents: Optional[int] = None
    max_loss_per_day_cents: Optional[int] = None
    max_bets_per_day: Optional[int] = None
    unit_pct: Optional[float] = None
    allowed_leagues: Optional[List[int]] = None
    allowed_markets: Optional[List[str]] = None
    kill_switch: Optional[bool] = None


class BotConfigResponse(BaseModel):
    enabled: bool
    mode: str
    bet_house: Optional[str]
    banca_inicial_cents: int
    banca_atual_cents: int
    max_loss_per_day_cents: int
    max_bets_per_day: int
    unit_pct: float
    allowed_leagues: List[int]
    allowed_markets: List[str]
    kill_switch: bool
    real_mode_unlocked: bool
    accepted_tos_at: Optional[datetime]


class BotCredentialUpsert(BaseModel):
    bet_house: str
    username: str
    password: str


class BotCredentialItem(BaseModel):
    bet_house: str
    status: str
    last_validated_at: Optional[datetime]


class BotGlobalKill(BaseModel):
    enabled: bool


def _bot_config_response(cfg: dict) -> BotConfigResponse:
    return BotConfigResponse(
        enabled=cfg.get("enabled", False),
        mode=cfg.get("mode", "paper"),
        bet_house=cfg.get("bet_house"),
        banca_inicial_cents=cfg.get("banca_inicial_cents", 0),
        banca_atual_cents=cfg.get("banca_atual_cents", 0),
        max_loss_per_day_cents=cfg.get("max_loss_per_day_cents", 0),
        max_bets_per_day=cfg.get("max_bets_per_day", 0),
        unit_pct=cfg.get("unit_pct", 0.01),
        allowed_leagues=list(cfg.get("allowed_leagues") or []),
        allowed_markets=list(cfg.get("allowed_markets") or []),
        kill_switch=cfg.get("kill_switch", False),
        real_mode_unlocked=cfg.get("real_mode_unlocked", False),
        accepted_tos_at=cfg.get("accepted_tos_at"),
    )


@app.get("/api/bot/config", response_model=BotConfigResponse)
async def get_bot_config(current_user: User = Depends(require_max_plan)):
    db = Database()
    cfg = await db.get_bot_config(current_user.id) or {}
    return _bot_config_response(cfg)


@app.patch("/api/bot/config", response_model=BotConfigResponse)
async def patch_bot_config(
    body: BotConfigPatch,
    current_user: User = Depends(require_max_plan),
):
    db = Database()
    cfg = await db.get_bot_config(current_user.id) or {}

    fields = body.dict(exclude_none=True)

    # Validações de negócio
    if "bet_house" in fields and fields["bet_house"] not in VALID_BET_HOUSES:
        raise HTTPException(400, f"bet_house deve ser um de {VALID_BET_HOUSES}")
    if "allowed_markets" in fields:
        for m in fields["allowed_markets"]:
            if m not in VALID_BOT_MARKETS:
                raise HTTPException(400, f"market inválido: {m}")
    if "unit_pct" in fields and not (0.001 <= fields["unit_pct"] <= 0.05):
        raise HTTPException(400, "unit_pct deve estar entre 0.001 (0.1%) e 0.05 (5%)")
    if "banca_inicial_cents" in fields and fields["banca_inicial_cents"] < 5000:
        raise HTTPException(400, "banca_inicial mínima: R$ 50,00 (5000 cents)")
    if fields.get("enabled") is True:
        # Exige ToS aceito e bet_house configurada
        if not cfg.get("accepted_tos_at"):
            raise HTTPException(412, "Aceite os termos de uso antes de ativar o robô.")
        bet_house = fields.get("bet_house") or cfg.get("bet_house")
        if not bet_house:
            raise HTTPException(400, "Configure a casa de aposta antes de ativar.")
        banca = fields.get("banca_inicial_cents") or cfg.get("banca_inicial_cents", 0)
        if banca < 5000:
            raise HTTPException(400, "Configure a banca antes de ativar (mínimo R$ 50).")

    # Se banca_inicial mudou e banca_atual nunca foi setada → sincroniza
    if "banca_inicial_cents" in fields and not cfg.get("banca_atual_cents"):
        fields["banca_atual_cents"] = fields["banca_inicial_cents"]

    await db.upsert_bot_config(current_user.id, fields)
    new_cfg = await db.get_bot_config(current_user.id) or {}
    return _bot_config_response(new_cfg)


@app.post("/api/bot/tos/accept", response_model=BotConfigResponse)
async def accept_bot_tos(current_user: User = Depends(require_max_plan)):
    db = Database()
    await db.upsert_bot_config(current_user.id, {"accepted_tos_at": datetime.now()})
    cfg = await db.get_bot_config(current_user.id) or {}
    return _bot_config_response(cfg)


@app.get("/api/bot/credentials", response_model=List[BotCredentialItem])
async def list_bot_credentials(current_user: User = Depends(require_max_plan)):
    db = Database()
    rows = await db.list_user_credentials(current_user.id)
    return [
        BotCredentialItem(
            bet_house=r["bet_house"],
            status=r["status"],
            last_validated_at=r.get("last_validated_at"),
        )
        for r in rows
    ]


@app.post("/api/bot/credentials")
async def upsert_bot_credential(
    body: BotCredentialUpsert,
    current_user: User = Depends(require_max_plan),
):
    if body.bet_house not in VALID_BET_HOUSES:
        raise HTTPException(400, f"bet_house inválida: {body.bet_house}")
    if len(body.username) < 3 or len(body.password) < 4:
        raise HTTPException(400, "Username/senha muito curtos.")

    try:
        from services.crypto import get_cipher, CredentialCipherError
        cipher = get_cipher()
        u_blob = cipher.encrypt(body.username)
        p_blob = cipher.encrypt(body.password)
    except CredentialCipherError as e:
        logger.error(f"[bot/credentials] crypto error: {e}")
        raise HTTPException(503, "Serviço de credenciais indisponível.")

    if u_blob.nonce != p_blob.nonce:
        # Usar nonces diferentes nas duas cifras mas só persistir um?
        # Solução: persistir o nonce do username; password usa um nonce derivado
        # implicitamente. Decisão simples: usar mesmo cipher pra cada um,
        # cada blob carrega seu nonce -- mas o schema só tem 1 nonce.
        # → trocar pra cifrar joined "username\npassword" em um blob só.
        pass

    # Reabordando: cifrar joined string num único blob com 1 nonce
    combined = f"{body.username}\n{body.password}"
    blob = cipher.encrypt(combined)
    # Reusa username_ct = blob full, password_ct = b'' como sentinel
    # Mas isso bagunça o schema. Vou cifrar separadamente com nonces independentes
    # e persistir os dois nonces concatenados em `nonce` (12 + 12 = 24 bytes).
    nonce_combined = u_blob.nonce + p_blob.nonce
    db = Database()
    await db.upsert_credential(
        current_user.id, body.bet_house,
        u_blob.ciphertext, p_blob.ciphertext, nonce_combined,
    )
    return {"status": "ok", "bet_house": body.bet_house}


@app.delete("/api/bot/credentials/{bet_house}")
async def delete_bot_credential(
    bet_house: str,
    current_user: User = Depends(require_max_plan),
):
    if bet_house not in VALID_BET_HOUSES:
        raise HTTPException(400, "bet_house inválida.")
    db = Database()
    ok = await db.delete_credential(current_user.id, bet_house)
    return {"status": "deleted" if ok else "not_found"}


@app.post("/api/admin/bot-kill")
async def set_bot_global_kill(
    body: BotGlobalKill,
    _: User = Depends(require_admin),
):
    db = Database()
    await db.set_bot_global_kill(body.enabled)
    return {"enabled": body.enabled}


@app.get("/api/admin/bot-kill")
async def get_bot_global_kill(_: User = Depends(require_admin)):
    db = Database()
    enabled = await db.get_bot_global_kill()
    return {"enabled": enabled}


@app.get("/api/bot/bets")
async def list_bot_bets(
    status: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
    current_user: User = Depends(require_max_plan),
):
    """Lista paginada de bets do user. Filtro opcional por status."""
    if page < 1 or page_size < 1 or page_size > 100:
        raise HTTPException(400, "page>=1, page_size 1..100")
    db = Database()
    await db.connect()
    offset = (page - 1) * page_size
    async with db.pool.acquire() as conn:
        params = [current_user.id]
        clauses = ["b.user_id = $1"]
        if status:
            params.append(status)
            clauses.append(f"b.status = ${len(params)}")
        where = " AND ".join(clauses)
        total = await conn.fetchval(
            f"SELECT COUNT(*) FROM bets b WHERE {where}", *params
        )
        params_with_paging = params + [page_size, offset]
        rows = await conn.fetch(
            f"""
            SELECT b.id, b.signal_id, b.market, b.bet_house, b.mode,
                   b.stake_cents, b.odd, b.linha, b.selecao, b.status,
                   b.payout_cents, b.placed_at, b.settled_at,
                   s.jogo_descricao, s.liga_nome
            FROM bets b
            LEFT JOIN sinais s ON s.id = b.signal_id
            WHERE {where}
            ORDER BY b.placed_at DESC
            LIMIT ${len(params)+1} OFFSET ${len(params)+2}
            """,
            *params_with_paging,
        )
    items = []
    for r in rows:
        items.append({
            "id": r["id"],
            "signal_id": r["signal_id"],
            "market": r["market"],
            "bet_house": r["bet_house"],
            "mode": r["mode"],
            "stake_cents": r["stake_cents"],
            "odd": float(r["odd"]),
            "linha": float(r["linha"]),
            "selecao": r["selecao"],
            "status": r["status"],
            "payout_cents": r["payout_cents"],
            "placed_at": r["placed_at"].isoformat() if r["placed_at"] else None,
            "settled_at": r["settled_at"].isoformat() if r["settled_at"] else None,
            "jogo_descricao": r["jogo_descricao"],
            "liga_nome": r["liga_nome"],
        })
    return {"total": total, "page": page, "page_size": page_size, "items": items}


@app.get("/api/bot/pnl")
async def get_bot_pnl(
    days: int = 30,
    current_user: User = Depends(require_max_plan),
):
    """Agregado de P&L do user: hoje, semana, total + série diária pra gráfico."""
    if days < 1 or days > 365:
        raise HTTPException(400, "days entre 1 e 365")
    db = Database()
    await db.connect()
    async with db.pool.acquire() as conn:
        # cards de período (resolvidas apenas)
        async def agg(start_clause: str) -> dict:
            r = await conn.fetchrow(
                f"""
                SELECT COUNT(*) AS n,
                       COUNT(*) FILTER (WHERE status='won') AS wins,
                       COUNT(*) FILTER (WHERE status='lost') AS losses,
                       COALESCE(SUM(stake_cents),0) AS stake,
                       COALESCE(SUM(payout_cents),0) AS payout
                FROM bets
                WHERE user_id=$1
                  AND status IN ('won','lost','cashed_out')
                  AND settled_at IS NOT NULL
                  AND {start_clause}
                """,
                current_user.id,
            )
            stake = int(r["stake"]) or 0
            payout = int(r["payout"]) or 0
            return {
                "n": int(r["n"]),
                "wins": int(r["wins"]),
                "losses": int(r["losses"]),
                "stake_cents": stake,
                "payout_cents": payout,
                "delta_cents": payout - stake,
                "roi_pct": (((payout - stake) / stake) * 100) if stake > 0 else 0.0,
            }

        today = await agg("settled_at::date = CURRENT_DATE")
        week = await agg("settled_at >= CURRENT_DATE - INTERVAL '7 days'")
        total = await agg(f"settled_at >= CURRENT_DATE - INTERVAL '{days} days'")

        # série diária
        series_rows = await conn.fetch(
            """
            SELECT settled_at::date AS d,
                   COALESCE(SUM(payout_cents - stake_cents), 0) AS delta
            FROM bets
            WHERE user_id=$1
              AND status IN ('won','lost','cashed_out')
              AND settled_at IS NOT NULL
              AND settled_at >= CURRENT_DATE - ($2::int * INTERVAL '1 day')
            GROUP BY d ORDER BY d ASC
            """,
            current_user.id, days,
        )
        series = [{"date": r["d"].isoformat(), "delta_cents": int(r["delta"])} for r in series_rows]

        # apostas open atuais
        open_count = await conn.fetchval(
            "SELECT COUNT(*) FROM bets WHERE user_id=$1 AND status='open'",
            current_user.id,
        )

    return {
        "days": days,
        "today": today,
        "week": week,
        "total": total,
        "series": series,
        "open_count": int(open_count or 0),
    }


@app.get("/api/bot/open-bets")
async def list_open_bets(current_user: User = Depends(require_max_plan)):
    """Apostas abertas com dados do sinal pra exibir live."""
    db = Database()
    await db.connect()
    async with db.pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT b.id, b.signal_id, b.market, b.mode, b.stake_cents,
                   b.odd, b.linha, b.selecao, b.placed_at,
                   s.jogo_descricao, s.liga_nome, s.minuto, s.placar
            FROM bets b
            LEFT JOIN sinais s ON s.id = b.signal_id
            WHERE b.user_id = $1 AND b.status = 'open'
            ORDER BY b.placed_at DESC
            """,
            current_user.id,
        )
    return [
        {
            "id": r["id"],
            "signal_id": r["signal_id"],
            "market": r["market"],
            "mode": r["mode"],
            "stake_cents": r["stake_cents"],
            "odd": float(r["odd"]),
            "linha": float(r["linha"]),
            "selecao": r["selecao"],
            "placed_at": r["placed_at"].isoformat() if r["placed_at"] else None,
            "jogo_descricao": r["jogo_descricao"],
            "liga_nome": r["liga_nome"],
            "minuto": r["minuto"],
            "placar": r["placar"],
        }
        for r in rows
    ]


# ============= Strategy Performance =============

# Cache em memória: { market: (timestamp, payload) }
_strat_perf_cache: dict = {}
_STRAT_PERF_TTL_S = 15 * 60  # 15min


@app.get("/api/stats/strategy-performance")
async def strategy_performance(
    market: str = "corners",
    days: int = 30,
    _: User = Depends(require_paid_subscription),
):
    """Hit rate + ROI por tier (conservative/moderate/aggressive/brute) no mercado.

    Cacheado 15min em memória. Query expensiva (UNNEST + GROUP BY); 1 vez a cada
    15min é o suficiente.
    """
    import time
    if market not in ("corners", "cards"):
        raise HTTPException(status_code=400, detail="market must be 'corners' or 'cards'")

    cache_key = f"{market}:{days}"
    now = time.time()
    cached = _strat_perf_cache.get(cache_key)
    if cached and (now - cached[0]) < _STRAT_PERF_TTL_S:
        return cached[1]

    db = Database()
    perf = await db.get_strategy_performance(market, days=days)
    payload = {
        "market": market,
        "days": days,
        "tiers": perf,  # { tier: {...} }
        "cached_at": int(now),
    }
    _strat_perf_cache[cache_key] = (now, payload)
    return payload


# ============= Subscription Endpoints =============

@app.post("/api/subscriptions/checkout")
async def create_checkout(
    request: CheckoutRequest,
    current_user: User = Depends(get_current_active_user),
):
    """Cria checkout no Asaas e retorna URL. Idempotente:
    - sub active → 409 (já é assinante)
    - sub pending com asaas_id real → reusa invoiceUrl existente
    - caso contrário → cria nova subscription
    """
    if request.plan == "pro":
        value = 39.90
        desc = "PressureIQ - Plano Pro (Mensal)"
    elif request.plan == "max":
        value = 89.90
        desc = "PressureIQ - Plano Max (Mensal)"
    else:
        raise HTTPException(status_code=400, detail="Invalid plan")

    db = Database()
    asaas = AsaasClient()
    success_url = f"{APP_URL.rstrip('/')}/checkout/success"

    existing = await db.get_subscription_by_user_id(current_user.id)
    if existing and existing.status == "active":
        is_upgrade = (
            request.upgrade_from == "pro"
            and existing.plan == "pro"
            and request.plan == "max"
        )
        if not is_upgrade:
            raise HTTPException(status_code=409, detail="Você já tem uma assinatura ativa.")
        # cancela a Pro no Asaas antes de criar Max (evita 2 cobranças paralelas)
        if existing.asaas_id and not existing.asaas_id.startswith("pending_"):
            cancelled = await asaas.cancel_subscription(existing.asaas_id)
            if not cancelled:
                logger.warning(
                    f"[UPGRADE] Falha ao cancelar Pro {existing.asaas_id} no Asaas — prosseguindo"
                )
        logger.info(f"[UPGRADE] User {current_user.id} fazendo Pro→Max")

    # Reuso de pending: só faz sentido se o plano for o mesmo e tivermos o asaas_id real
    if (
        existing
        and existing.status == "pending"
        and existing.plan == request.plan
        and existing.asaas_id
        and not existing.asaas_id.startswith("pending_")
    ):
        reused = await asaas.get_subscription_invoice_url(existing.asaas_id, success_url=success_url)
        if reused:
            logger.info(f"[CHECKOUT] Reusando subscription pending {existing.asaas_id} para user {current_user.id}")
            return {"checkoutUrl": reused}

    # Se havia pending de plano diferente OU asaas_id inválido, tenta cancelar a antiga no Asaas
    if (
        existing
        and existing.status == "pending"
        and existing.asaas_id
        and not existing.asaas_id.startswith("pending_")
    ):
        await asaas.cancel_subscription(existing.asaas_id)

    customer_id = await asaas.create_customer(
        name=current_user.full_name,
        email=current_user.email,
        phone=current_user.whatsapp,
        cpf=current_user.cpf,
        external_id=str(current_user.id),
    )
    if not customer_id:
        raise HTTPException(status_code=500, detail="Failed to create customer on Asaas")

    external_ref = f"cmp-{current_user.id}-{request.plan}-{int(datetime.now().timestamp())}"
    sub_id, redirect_url = await asaas.create_subscription(
        customer_id=customer_id,
        value=value,
        description=desc,
        external_ref=external_ref,
        billing_type="UNDEFINED",
        success_url=success_url,
    )
    if not redirect_url or not sub_id:
        raise HTTPException(status_code=500, detail="Failed to create checkout URL")

    await db.upsert_subscription(Subscription(
        user_id=current_user.id,
        plan=request.plan,
        asaas_id=sub_id,
        status="pending",
    ))

    return {"checkoutUrl": redirect_url}



@app.post("/api/webhook/asaas")
async def webhook_asaas(request: Request):
    """Recebe webhooks do Asaas. Valida o header asaas-access-token."""
    import secrets as _secrets
    from config import ASAAS_WEBHOOK_TOKEN

    if not ASAAS_WEBHOOK_TOKEN:
        logger.error("[WEBHOOK ASAAS] ASAAS_WEBHOOK_TOKEN nao configurado — rejeitando")
        raise HTTPException(status_code=503, detail="Webhook nao configurado")

    received = request.headers.get("asaas-access-token", "")
    if not _secrets.compare_digest(received, ASAAS_WEBHOOK_TOKEN):
        logger.warning(f"[WEBHOOK ASAAS] Token invalido recebido de {request.client.host if request.client else '?'}")
        raise HTTPException(status_code=401, detail="Invalid webhook token")

    try:
        data = await request.json()
    except Exception:
        return {"status": "ignored"}

    event = data.get("event") or ""
    # PAYMENT_* events trazem payload em data["payment"]
    # SUBSCRIPTION_* events trazem payload em data["subscription"]
    payment = data.get("payment") or {}
    subscription = data.get("subscription") or {}
    payload_obj = payment if payment else subscription
    external_ref = (
        payment.get("externalReference")
        or subscription.get("externalReference")
    )

    logger.info(f"[WEBHOOK ASAAS] Event: {event} | Ref: {external_ref}")

    # Precisamos do user_id que está no externalReference (fmt: cmp-{user_id}-{plan}-{ts})
    if not external_ref or not external_ref.startswith("cmp-"):
        return {"status": "ignored", "reason": "invalid reference"}

    parts = external_ref.split("-")
    if len(parts) < 3:
        return {"status": "ignored"}

    user_id = int(parts[1])
    plan_name = parts[2]

    db = Database()

    # Dedup: Asaas envia CONFIRMED e RECEIVED em sequência para o mesmo payment.
    # Agrupamos por "grupo de evento" (confirmed/refunded/overdue/canceled)
    # para processar apenas a primeira ocorrência de cada grupo por payment.
    _GROUPS = {
        "PAYMENT_CONFIRMED": "confirmed",
        "PAYMENT_RECEIVED": "confirmed",
        "PAYMENT_REFUNDED": "refunded",
        "PAYMENT_REFUND_IN_PROGRESS": "refunded",
        "PAYMENT_OVERDUE": "overdue",
        "SUBSCRIPTION_DELETED": "canceled",
        "SUBSCRIPTION_CANCELED": "canceled",
    }
    group = _GROUPS.get(event)
    payment_id = payment.get("id") or subscription.get("id")
    if group and payment_id:
        is_new = await db.mark_payment_processed(payment_id, group)
        if not is_new:
            logger.info(f"[WEBHOOK ASAAS] Ignorando duplicado: {event} payment={payment_id} (grupo {group} já processado)")
            return {"status": "ignored", "reason": "duplicate"}

    # Sandbox: aprova automaticamente cobrancas seguras pelo antifraude.
    # Em producao (api.asaas.com) este branch nao dispara — o fluxo normal de
    # risk analysis manual prevalece. Asaas reemite PAYMENT_CONFIRMED apos approve.
    if event == "PAYMENT_AWAITING_RISK_ANALYSIS":
        from config import ASAAS_API_URL
        is_sandbox = "sandbox" in ASAAS_API_URL.lower()
        if is_sandbox and payment_id:
            ok = await AsaasClient().approve_by_risk_analysis(payment_id)
            logger.info(f"[WEBHOOK ASAAS] Auto-approve sandbox payment={payment_id} ok={ok}")
            return {"status": "auto-approved" if ok else "auto-approve-failed", "payment_id": payment_id}
        return {"status": "ignored", "reason": "awaiting risk analysis (prod mode)"}

    if event in ["PAYMENT_CONFIRMED", "PAYMENT_RECEIVED"]:
        # Renovação = já existia uma assinatura active deste user
        prev_sub = await db.get_subscription_by_user_id(user_id)
        is_renewal = bool(prev_sub and prev_sub.status == "active")

        # Ativar/renovar (30 dias a partir de agora)
        starts = datetime.now()
        expires = starts + timedelta(days=30)

        sub = Subscription(
            user_id=user_id,
            plan=plan_name,
            asaas_id=payment.get("subscription", payment.get("id")), # Se for assinatura ou cobrança unica
            status="active",
            starts_at=starts,
            expires_at=expires,
            next_due_date=expires
        )
        await db.upsert_subscription(sub)
        logger.info(f"[WEBHOOK ASAAS] {'Renovação' if is_renewal else 'Ativação'} para User {user_id} (plano {plan_name})")

        # Publicar evento — renovação ou primeiro pagamento
        user = await db.get_user_by_id(user_id)
        if user:
            value_str = f"{value:.2f}".replace(".", ",") if (value := payment.get("value")) else "--"
            if is_renewal:
                publish_event(EVENT_SUBSCRIPTION_RENEWED, {
                    "user_id": user_id,
                    "email": user.email,
                    "full_name": user.full_name,
                    "plan": plan_name,
                    "next_due_date": expires.strftime("%d/%m/%Y"),
                })
            else:
                publish_event(EVENT_PAYMENT_CONFIRMED, {
                    "user_id": user_id,
                    "email": user.email,
                    "full_name": user.full_name,
                    "plan": plan_name,
                    "value": value_str,
                    "next_due_date": expires.strftime("%d/%m/%Y"),
                })

        # Adicionar ao grupo WhatsApp
        try:
            if not user:
                user = await db.get_user_by_id(user_id)
            if user and user.whatsapp:
                waha_config = WAHAConfig(
                    base_url=WAHA_URL,
                    session_name=WAHA_SESSION_NAME,
                    api_key=WAHA_API_KEY
                )
                async with WhatsAppClient(waha_config) as client:
                    participant_id = WhatsAppClient.format_chat_id(user.whatsapp)
                    
                    # Grupo Escanteios (Todos)
                    if WHATSAPP_GROUP_ID:
                        await client.add_participant(WHATSAPP_GROUP_ID, participant_id)
                        logger.info(f"[WEBHOOK] User {user_id} adicionado ao grupo Escanteios")
                        
                    # Grupo Cartões (Apenas Max ou se configurado para tal)
                    if WHATSAPP_GROUP_CARTOES and plan_name == "max":
                        await client.add_participant(WHATSAPP_GROUP_CARTOES, participant_id)
                        logger.info(f"[WEBHOOK] User {user_id} adicionado ao grupo Cartões")
                        
                    # Enviar boas vindas
                    welcome_msg = f"Bem-vindo ao PressureIQ! Seu plano {plan_name.upper()} está ativo."
                    await client.send_text(participant_id, welcome_msg)
        except Exception as e:
            logger.error(f"[WEBHOOK] Erro ao adicionar user {user_id} ao grupo: {e}")
        
    elif event in ["PAYMENT_OVERDUE", "SUBSCRIPTION_DELETED", "SUBSCRIPTION_CANCELED",
                    "PAYMENT_REFUNDED", "PAYMENT_REFUND_IN_PROGRESS"]:
        # Cancelar/Bloquear/Estornar (SUBSCRIPTION_CANCELED mantido por compat — Asaas v3 emite SUBSCRIPTION_DELETED)
        current_sub = await db.get_subscription_by_user_id(user_id)
        if current_sub:
            if event == "PAYMENT_OVERDUE":
                current_sub.status = "overdue"
            elif event in ("PAYMENT_REFUNDED", "PAYMENT_REFUND_IN_PROGRESS"):
                current_sub.status = "refunded"
            else:
                current_sub.status = "canceled"
            await db.upsert_subscription(current_sub)
            logger.info(f"[WEBHOOK ASAAS] Assinatura {event} para User {user_id}")

            # Publicar evento de cancelamento (overdue também — user deve saber)
            user = await db.get_user_by_id(user_id)
            if user:
                access_until = current_sub.expires_at
                if hasattr(access_until, "strftime"):
                    access_until = access_until.strftime("%d/%m/%Y")
                publish_event(EVENT_SUBSCRIPTION_CANCELLED, {
                    "user_id": user_id,
                    "email": user.email,
                    "full_name": user.full_name,
                    "access_until": access_until or "",
                    "app_url": APP_URL,
                })

    return {"status": "ok"}


# --- WhatsApp Admin Commands (WAHA Webhook) ---

# Numeros autorizados para comandos
_authorized_senders = set()
print(f"[INIT] WHATSAPP_ADMIN={WHATSAPP_ADMIN}, WHATSAPP_UPDATES={WHATSAPP_UPDATES}")
if WHATSAPP_ADMIN:
    admin_id = WhatsAppClient.format_chat_id(WHATSAPP_ADMIN)
    _authorized_senders.add(admin_id)
    print(f"[INIT] ✓ Admin autorizado: {WHATSAPP_ADMIN} → {admin_id}")
    logger.info(f"✓ Admin autorizado: {WHATSAPP_ADMIN} → {admin_id}")
else:
    print("[INIT] ⚠️  WHATSAPP_ADMIN não configurado!")
    logger.warning("⚠️  WHATSAPP_ADMIN não configurado!")

if WHATSAPP_UPDATES:
    updates_id = WhatsAppClient.format_chat_id(WHATSAPP_UPDATES)
    _authorized_senders.add(updates_id)
    print(f"[INIT] ✓ Updates autorizado: {WHATSAPP_UPDATES} → {updates_id}")
    logger.info(f"✓ Updates autorizado: {WHATSAPP_UPDATES} → {updates_id}")
else:
    print("[INIT] ℹ️  WHATSAPP_UPDATES não configurado")
    logger.info("ℹ️  WHATSAPP_UPDATES não configurado")

print(f"[INIT] Senders autorizados: {_authorized_senders}")
logger.info(f"Senders autorizados: {_authorized_senders}")
_formatter = MessageFormatter()

# Comandos aceitos (sem /)
_COMMAND_MAP = {
    "status": "status",
    "saude": "status",
    "jogos": "jogos",
    "agenda": "jogos",
    "games": "jogos",
    "stats": "stats",
    "resultado": "stats",
    "roi": "stats",
    "help": "help",
    "ajuda": "help",
    "?": "help",
}

# Tier name mapping: Portuguese -> English
_STRATEGY_TIER_MAP = {
    "conservador": "conservative",
    "moderado": "moderate",
    "agressivo": "aggressive",
    "bruto": "brute",
    "conservative": "conservative",
    "moderate": "moderate",
    "aggressive": "aggressive",
    "brute": "brute",
}

# Market name mapping: Portuguese -> English
_MARKET_MAP = {
    "escanteios": "corners",
    "corners": "corners",
    "corner": "corners",
    "cartoes": "cards",
    "cards": "cards",
    "cartão": "cards",
    "cartao": "cards",
}


@app.post("/api/webhook/whatsapp")
async def webhook_whatsapp(request: Request):
    """Recebe mensagens do WAHA e responde a comandos admin."""
    try:
        body = await request.json()
    except Exception as e:
        logger.error(f"[WEBHOOK] JSON parse error: {e}")
        return {"status": "ignored", "reason": "invalid json"}

    event = body.get("event", "")
    if event != "message":
        logger.debug(f"[WEBHOOK] Ignorado event type: {event}")
        return {"status": "ignored", "reason": f"event={event}"}

    payload = body.get("payload", {})
    sender = payload.get("from", "")
    message_body = (payload.get("body") or "").strip()

    # Ignorar mensagens enviadas pelo próprio bot (evita loops)
    from_me = payload.get("fromMe", False)
    if from_me:
        logger.debug(f"[WEBHOOK] Ignorando mensagem fromMe (bot's own message)")
        return {"status": "ignored", "reason": "fromMe"}

    logger.info(f"[WEBHOOK] Recebido: from={sender}, body='{message_body[:50]}', fromMe={from_me}")

    # Handle /strategy command for ANY user (before auth check)
    cmd_raw = message_body.lstrip("/").lower().strip()
    if cmd_raw.startswith("strategy") or cmd_raw.startswith("estrategia"):
        return await _handle_strategy_command(sender, message_body)

    # Verificar se e de um remetente autorizado (admin ou updates)
    if not _authorized_senders:
        logger.warning(f"[WEBHOOK] _authorized_senders vazio! WHATSAPP_ADMIN={WHATSAPP_ADMIN}")
        return {"status": "ignored", "reason": "no authorized senders"}

    if sender not in _authorized_senders:
        logger.debug(f"[WEBHOOK] Sender {sender} não autorizado. Autorizados: {_authorized_senders}")
        return {"status": "ignored", "reason": "not authorized"}

    logger.info(f"[WEBHOOK] ✓ Sender autorizado: {sender}")

    # Parsear comando (remove / do inicio, lowercase)
    cmd_raw = message_body.lstrip("/").lower().strip()
    command = _COMMAND_MAP.get(cmd_raw)

    if not command:
        logger.info(f"[WEBHOOK] Comando desconhecido: '{cmd_raw}' (msg: '{message_body[:50]}')")
        return {"status": "ignored", "reason": "unknown command"}

    logger.info(f"[WEBHOOK] Processando: '{cmd_raw}' → {command}")

    # Gerar resposta
    response_text = await _handle_admin_command(command)
    logger.info(f"[WEBHOOK] Resposta gerada (len={len(response_text)})")

    # Enviar resposta via WAHA Manager com retry
    max_retries = 2
    last_error = None
    for attempt in range(1, max_retries + 1):
        try:
            logger.info(f"[WEBHOOK] Enviando para {sender} (tentativa {attempt}/{max_retries})...")
            result = await send_whatsapp_message(sender, response_text)
            logger.info(f"[WEBHOOK] ✓ Resposta enviada com sucesso | WAHA response: {str(result)[:100]}")
            return {"status": "ok", "command": command, "message_sent": True}
        except Exception as e:
            last_error = str(e)[:200]
            logger.error(f"[WEBHOOK] ✗ Tentativa {attempt} falhou: {last_error}")
            if attempt < max_retries:
                await asyncio.sleep(1)  # Breve pausa antes de retry

    logger.error(f"[WEBHOOK] ✗ FALHA TOTAL após {max_retries} tentativas: {last_error}")
    return {"status": "error", "command": command, "message_error": last_error}


async def _handle_admin_command(command: str) -> str:
    """Processa comando admin e retorna texto de resposta."""
    if command == "status":
        log_file = get_log_file()
        log_lines = read_last_lines(log_file, 50)
        status = parse_log_for_status(log_lines)
        status["online"] = True
        return _formatter.format_health_response(status)

    elif command == "jogos":
        upcoming = await get_upcoming_games()
        games = upcoming.get("proximos", [])
        return _formatter.format_upcoming_response(games)

    elif command == "stats":
        stats = await get_db_stats()
        return _formatter.format_stats_response(stats)

    elif command == "help":
        return _formatter.format_help_response()

    return "Comando nao reconhecido. Envie /help para ver os comandos."


async def _handle_strategy_command(sender: str, message_body: str) -> dict:
    """Processa /strategy command para qualquer usuario alterar sua estrategia.

    Formato: /strategy <tier> [market]
    Ex: /strategy conservador
        /strategy agressivo escanteios
        /strategy moderado cartoes
    """
    parts = message_body.lstrip("/").lower().strip().split()

    if len(parts) < 2:
        response = (
            "*Comando: /strategy*\n"
            "\n"
            "Altere sua estrategia de recebimento de sinais.\n"
            "\n"
            "*Formato:* /strategy <nivel> [mercado]\n"
            "\n"
            "*Niveis:*\n"
            "• conservador — poucos sinais, alta confianca\n"
            "• moderado — equilibrio (padrao)\n"
            "• agressivo — mais sinais, risco moderado\n"
            "• bruto — maxima cobertura\n"
            "\n"
            "*Mercados (opcional):*\n"
            "• escanteios (padrao)\n"
            "• cartoes\n"
            "\n"
            "*Exemplos:*\n"
            "/strategy conservador\n"
            "/strategy agressivo escanteios\n"
            "/strategy moderado cartoes"
        )
        try:
            await send_whatsapp_message(sender, response)
        except Exception as e:
            logger.error(f"[STRATEGY] Erro ao enviar resposta: {e}")
        return {"status": "ok", "command": "strategy", "message_sent": True}

    tier_raw = parts[1]
    market_raw = parts[2] if len(parts) > 2 else "escanteios"

    tier = _STRATEGY_TIER_MAP.get(tier_raw)
    if not tier:
        response = (
            f"Nivel '{tier_raw}' nao reconhecido.\n"
            f"Use: conservador, moderado, agressivo ou bruto.\n"
            f"Ex: /strategy conservador"
        )
        try:
            await send_whatsapp_message(sender, response)
        except Exception as e:
            logger.error(f"[STRATEGY] Erro ao enviar resposta: {e}")
        return {"status": "error", "reason": "invalid_tier"}

    market = _MARKET_MAP.get(market_raw)
    if not market:
        response = (
            f"Mercado '{market_raw}' nao reconhecido.\n"
            f"Use: escanteios ou cartoes.\n"
            f"Ex: /strategy conservador escanteios"
        )
        try:
            await send_whatsapp_message(sender, response)
        except Exception as e:
            logger.error(f"[STRATEGY] Erro ao enviar resposta: {e}")
        return {"status": "error", "reason": "invalid_market"}

    # Look up user by WhatsApp number
    db = Database()
    await db.connect()
    user = await db.get_user_by_whatsapp(sender.replace("@c.us", "").replace("@g.us", ""))
    if not user:
        response = (
            "Usuario nao encontrado.\n"
            "Facca cadastro em {app_url} para usar este comando.".format(app_url=APP_URL or "PressureIQ")
        )
        try:
            await send_whatsapp_message(sender, response)
        except Exception as e:
            logger.error(f"[STRATEGY] Erro ao enviar resposta: {e}")
        return {"status": "error", "reason": "user_not_found"}

    # Update strategy preference
    await db.set_user_strategy(user.id, market, tier)

    market_label = "Escanteios" if market == "corners" else "Cartoes"
    response = (
        f"Estrategia atualizada!\n"
        f"\n"
        f"*Mercado:* {market_label}\n"
        f"*Nivel:* {tier.title()}\n"
        f"\n"
        f"Voce agora recebera sinais de {market_label.lower()} "
        f"com nivel {tier_raw}."
    )
    try:
        await send_whatsapp_message(sender, response)
    except Exception as e:
        logger.error(f"[STRATEGY] Erro ao enviar confirmacao: {e}")
        return {"status": "error", "reason": "send_failed"}

    logger.info(f"[STRATEGY] User {user.id} ({user.full_name}) -> {market}={tier}")
    return {"status": "ok", "command": "strategy", "user_id": user.id, "tier": tier, "market": market}


# ============= Banca per-user (Sprint M) =============

from data.repositories.banca import BancaRepo  # noqa: E402


async def _get_banca_repo() -> BancaRepo:
    db = Database()
    await db.connect()
    return BancaRepo(db.pool)


@app.get("/api/banca")
async def api_banca_summary(current_user: User = Depends(require_paid_subscription)):
    """Estado atual da banca + stats. configured=false se nunca setup."""
    repo = await _get_banca_repo()
    summary = await repo.get_summary(current_user.id)
    if not summary:
        return {
            "configured": False,
            "banca_inicial_cents": 0,
            "banca_atual_cents": 0,
        }
    return summary


@app.get("/api/banca/series")
async def api_banca_series(
    days: int = 30,
    current_user: User = Depends(require_paid_subscription),
):
    days = max(1, min(days, 365))
    repo = await _get_banca_repo()
    return {"days": days, "series": await repo.series(current_user.id, days=days)}


@app.get("/api/banca/movements")
async def api_banca_movements(
    tipo: Optional[str] = None,
    page: int = 1,
    page_size: int = 100,
    current_user: User = Depends(require_paid_subscription),
):
    page = max(1, page)
    page_size = max(1, min(page_size, 500))
    repo = await _get_banca_repo()
    return await repo.list_movements(current_user.id, tipo=tipo, page=page, page_size=page_size)


@app.post("/api/banca/setup")
async def api_banca_setup(
    body: dict,
    current_user: User = Depends(require_paid_subscription),
):
    initial = int(body.get("initial_cents", 0))
    if initial <= 0:
        raise HTTPException(400, "initial_cents > 0 obrigatorio")
    repo = await _get_banca_repo()
    return await repo.setup(
        current_user.id,
        initial_cents=initial,
        unit_pct=body.get("unit_pct"),
        max_loss_per_day_cents=body.get("max_loss_per_day_cents"),
        max_bets_per_day=body.get("max_bets_per_day"),
    )


@app.post("/api/banca/movements")
async def api_banca_add_movement(
    body: dict,
    current_user: User = Depends(require_paid_subscription),
):
    tipo = body.get("tipo")
    valor = body.get("valor_cents")
    if tipo not in {"deposit", "withdraw", "correction"}:
        raise HTTPException(400, "tipo deve ser deposit|withdraw|correction")
    if not isinstance(valor, int) or valor == 0:
        raise HTTPException(400, "valor_cents int != 0 obrigatorio")
    repo = await _get_banca_repo()
    try:
        return await repo.add_movement(
            current_user.id,
            tipo=tipo,
            valor_cents=valor,
            descricao=body.get("descricao"),
            motivo=body.get("motivo"),
        )
    except LookupError:
        raise HTTPException(409, "banca nao configurada — chame POST /banca/setup primeiro")
    except ValueError as e:
        raise HTTPException(400, str(e))


@app.post("/api/banca/reset")
async def api_banca_reset(
    body: Optional[dict] = None,
    current_user: User = Depends(require_paid_subscription),
):
    motivo = (body or {}).get("motivo")
    repo = await _get_banca_repo()
    try:
        return await repo.reset(current_user.id, motivo=motivo)
    except LookupError:
        raise HTTPException(409, "banca nao configurada")


@app.delete("/api/banca")
async def api_banca_delete(current_user: User = Depends(require_paid_subscription)):
    """Wipe completo: deleta banca + movements. Volta a estado 'nao configurada'.

    Diferente do reset que so zera saldo. Usar quando user quer
    recomecar do zero (re-setup com valor diferente, por exemplo).
    """
    repo = await _get_banca_repo()
    deleted = await repo.delete(current_user.id)
    return {"deleted": deleted, "configured": False}


# ============= User signal decisions (Sprint M) =============

from data.repositories.user_signal_decisions import UserSignalDecisionsRepo  # noqa: E402


async def _get_decisions_repo() -> UserSignalDecisionsRepo:
    db = Database()
    await db.connect()
    return UserSignalDecisionsRepo(db.pool)


@app.post("/api/signals/{signal_id}/decision")
async def api_signal_decide(
    signal_id: int,
    body: dict,
    current_user: User = Depends(require_paid_subscription),
):
    """Marca decisao do user sobre um sinal: entered (com odd+valor) ou skipped."""
    decision = body.get("decision")
    if decision not in {"entered", "skipped"}:
        raise HTTPException(400, "decision deve ser 'entered' ou 'skipped'")
    repo = await _get_decisions_repo()
    try:
        result = await repo.decide(
            current_user.id,
            signal_id,
            decision=decision,
            odd_entrada=body.get("odd_entrada"),
            valor_apostado_cents=body.get("valor_apostado_cents"),
        )
    except ValueError as e:
        raise HTTPException(400, str(e))

    # Se entered, gera movimento de stake na banca (debita pra "reservar").
    # Movement bet_loss negativo de stake; se resultado vier GREEN depois,
    # geramos bet_win positivo com payout. Garantia atomica fica no settle().
    if decision == "entered":
        try:
            banca_repo = await _get_banca_repo()
            await banca_repo.add_movement(
                current_user.id,
                tipo="bet_loss",   # debita stake (otimista; settle compensa em GREEN)
                valor_cents=-(body.get("valor_apostado_cents") or 0),
                bet_id=result["id"],
                descricao=f"Stake signal #{signal_id}",
                motivo="entered",
            )
        except (LookupError, ValueError) as e:
            # Banca nao configurada ou saldo insuficiente — decision continua
            # registrada mas avisa. UI deve mostrar warning.
            log = logging.getLogger("cpes.api.decision")
            log.warning(f"user {current_user.id} entered signal {signal_id} but banca move falhou: {e}")
    return result


@app.get("/api/users/me/stats")
async def api_user_stats(current_user: User = Depends(require_paid_subscription)):
    """Stats user-scoped (winrate/ROI/etc) — vem de user_signal_decisions."""
    repo = await _get_decisions_repo()
    return await repo.compute_user_stats(current_user.id)


@app.get("/api/users/me/signals")
async def api_user_signals(
    limit: int = 100,
    current_user: User = Depends(require_paid_subscription),
):
    """Sinais recentes JOIN com decision do user (cria 'pending' se faltar)."""
    repo = await _get_decisions_repo()
    return await repo.list_signals_with_decision(current_user.id, limit=limit)
