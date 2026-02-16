"""
CPES API - Backend FastAPI para dashboard web.
Expõe dados do sistema: stats, sinais, logs, status.

Uso: uvicorn api_server:app --host 0.0.0.0 --port 8000
"""

import os
import sys
import logging
import asyncio
import aiohttp

sys.path.insert(0, os.path.dirname(__file__))

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List

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
    MIN_EDGE_PREMIUM,
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
from notifier.waha_manager import send_whatsapp_message
from notifier.message_formatter import MessageFormatter

logger = logging.getLogger("CPES.API")

app = FastAPI(title="CPES API", description="API para dashboard Corner Pressure Elite")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:3001",
        "http://127.0.0.1:3001",
        "https://odontoschultz.online",
        "https://www.odontoschultz.online",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


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


@app.get("/")
def root():
    return {"service": "CPES API", "docs": "/docs"}


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.get("/api/stats")
def api_stats():
    """Estatísticas de performance (greens, reds, winrate, ROI)."""
    return get_db_stats()


@app.get("/api/signals/recent")
def api_recent_signals(limit: int = 10):
    """Sinais mais recentes."""
    rows = get_recent_signals(limit=limit)
    return [
        {
            "timestamp": r[0],
            "jogo_descricao": r[1],
            "tipo_sinal": r[2],
            "pressure_score": r[3],
            "projecao": float(r[4]) if r[4] else None,
            "edge": float(r[5]) if r[5] else None,
            "linha": float(r[6]) if r[6] else None,
            "resultado": r[7] or "-",
        }
        for r in rows
    ]


@app.get("/api/status")
def api_status():
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
def api_logs(lines: int = 50):
    """Últimas linhas do log."""
    log_file = get_log_file()
    log_lines = read_last_lines(log_file, lines)
    # Remove ANSI/encoding issues - retorna texto limpo
    return {"lines": [line.rstrip() for line in log_lines]}


@app.get("/api/polling-stats")
def api_polling_stats():
    """Estatisticas do sistema de polling adaptativo."""
    live = get_live_state()
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
def api_live_games():
    """Jogos ao vivo por fase: pre_janela, na_janela (analisados), pos_janela; ids_observados."""
    return get_live_state()


@app.get("/api/upcoming-games")
def api_upcoming_games():
    """Próximos jogos programados com tempo até início."""
    return get_upcoming_games()

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
async def api_get_ligas():
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
async def api_set_ligas(config: LigasConfig):
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
async def api_get_thresholds():
    """Retorna thresholds atuais."""
    db = Database()
    thresholds = await db.get_thresholds()
    
    return {
        "thresholds": thresholds,
    }


@app.post("/api/config/thresholds")
async def api_set_thresholds(config: ThresholdsConfig):
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


@app.get("/api/audit")
def api_audit():
    """Dados de auditoria: funil de decisao, filtros, jogos detalhados, historico."""
    audit = get_audit_state()
    history = get_signals_history(days=7)
    stats_hoje = get_db_stats()

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


@app.get("/api/dashboard")
def api_dashboard():
    """Todos os dados para o dashboard em uma única chamada."""
    stats = get_db_stats()
    recent = get_recent_signals(10)
    log_file = get_log_file()
    log_lines = read_last_lines(log_file, 30)
    status = parse_log_for_status(log_lines)

    signals = [
        {
            "timestamp": r[0],
            "jogo_descricao": r[1],
            "tipo_sinal": r[2],
            "pressure_score": r[3],
            "projecao": float(r[4]) if r[4] else None,
            "edge": float(r[5]) if r[5] else None,
            "linha": float(r[6]) if r[6] else None,
            "odd": float(r[7]) if r[7] else None,
            "resultado": r[8] or "-",
            "escanteios_final": r[9],
        }
        for r in recent
    ]

    live_state = get_live_state()

    return {
        "stats": stats,
        "status": {**status, "minuto_inicio": MINUTO_INICIO, "minuto_fim": MINUTO_FIM},
        "signals": signals,
        "logs": [line.rstrip() for line in log_lines[-15:]],
        "ligas": LIGAS_MONITORADAS,
        "live_games": live_state,
    }


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
    response_text = _handle_admin_command(command)
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


def _handle_admin_command(command: str) -> str:
    """Processa comando admin e retorna texto de resposta."""
    if command == "status":
        log_file = get_log_file()
        log_lines = read_last_lines(log_file, 50)
        status = parse_log_for_status(log_lines)
        status["online"] = True
        return _formatter.format_health_response(status)

    elif command == "jogos":
        upcoming = get_upcoming_games()
        games = upcoming.get("proximos", [])
        return _formatter.format_upcoming_response(games)

    elif command == "stats":
        stats = get_db_stats()
        return _formatter.format_stats_response(stats)

    elif command == "help":
        return _formatter.format_help_response()

    return "Comando nao reconhecido. Envie /help para ver os comandos."
