"""
CPES API - Backend FastAPI para dashboard web.
Expõe dados do sistema: stats, sinais, logs, status.

Uso: uvicorn api_server:app --host 0.0.0.0 --port 8000
"""

import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import (
    API_DAILY_LIMIT,
    LIGAS_MONITORADAS,
    MINUTO_INICIO,
    MINUTO_FIM,
    POLLING_INTERVAL,
)
from data_reader import (
    get_db_stats,
    get_recent_signals,
    parse_log_for_status,
    read_last_lines,
    get_log_file,
    get_live_state,
)

app = FastAPI(title="CPES API", description="API para dashboard Corner Pressure Elite")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000", "http://localhost:3001", "http://127.0.0.1:3001"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


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
            "janela_analise": "1 min (50-90) - JANELA",
            "reta_final": "30 seg (90+ acréscimos) - FASE CRITICA",
        },
        "jogos_monitorados": stats.get("jogos_monitorados", 0),
        "jogos_analisando": stats.get("jogos_analisando", 0),
        "economia_pct": stats.get("economia_pct", 0),
        "destaque": "0-30: 5m | 31-50: 3m (ou 1m se 7+ esc) | 50-90: 1m | 90+: 30s",
    }


@app.get("/api/live-games")
def api_live_games():
    """Jogos ao vivo por fase: pre_janela, na_janela (analisados), pos_janela; ids_observados."""
    return get_live_state()


@app.get("/api/config")
def api_config():
    """Configuração do sistema (ligas, janela)."""
    return {
        "ligas": LIGAS_MONITORADAS,
        "minuto_inicio": MINUTO_INICIO,
        "minuto_fim": MINUTO_FIM,
        "api_daily_limit": API_DAILY_LIMIT,
        "polling_interval": POLLING_INTERVAL,
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
            "resultado": r[7] or "-",
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
