"""Endpoints públicos para landing page (sem autenticação).

Princípios:
- Sinais com delay >=15min (proteção contra scraping de sinais frescos).
- Estado de jogos ao vivo é público (placar/minuto já visíveis na Betano).
- Cache 60s + rate limit 60req/min por IP.
"""
from __future__ import annotations

import json
import logging
import os
import time
from collections import defaultdict, deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, Request, Response

from storage.database import Database

logger = logging.getLogger("CPES.API.Public")

router = APIRouter(prefix="/api/v1/public", tags=["public"])

CACHE_TTL_S = 60
RATE_LIMIT_WINDOW_S = 60
RATE_LIMIT_MAX = 60
SIGNAL_DELAY_MINUTES = 15

_cache: dict[str, tuple[float, dict]] = {}
_request_log: dict[str, deque[float]] = defaultdict(deque)
_app_start_ts = time.time()

_VERSION = os.getenv("CPES_VERSION", "0.1.0")
_LIVE_STATE_PATH = Path(__file__).resolve().parent.parent / "data" / "live_state.json"


def _client_ip(request: Request) -> str:
    xff = request.headers.get("x-forwarded-for")
    if xff:
        return xff.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _enforce_rate_limit(request: Request, response: Response) -> None:
    ip = _client_ip(request)
    now = time.time()
    window_start = now - RATE_LIMIT_WINDOW_S
    log = _request_log[ip]
    while log and log[0] < window_start:
        log.popleft()

    if len(log) >= RATE_LIMIT_MAX:
        retry_after = max(1, int(log[0] + RATE_LIMIT_WINDOW_S - now))
        raise HTTPException(
            status_code=429,
            detail={"error": "rate_limit_exceeded", "retry_after_seconds": retry_after},
            headers={
                "X-RateLimit-Limit": str(RATE_LIMIT_MAX),
                "X-RateLimit-Remaining": "0",
                "Retry-After": str(retry_after),
            },
        )

    log.append(now)
    response.headers["X-RateLimit-Limit"] = str(RATE_LIMIT_MAX)
    response.headers["X-RateLimit-Remaining"] = str(RATE_LIMIT_MAX - len(log))


def _cache_get(key: str) -> Optional[dict]:
    entry = _cache.get(key)
    if not entry:
        return None
    ts, value = entry
    if time.time() - ts > CACHE_TTL_S:
        _cache.pop(key, None)
        return None
    return value


def _cache_set(key: str, value: dict) -> None:
    _cache[key] = (time.time(), value)


def _format_market(tipo_analise: str, linha: float) -> str:
    if (tipo_analise or "").upper() == "CARTOES":
        return f"Mais {linha} cartões amarelos"
    return f"Mais {linha} escanteios"


def _load_live_games(limit: int) -> list[dict]:
    """Lê live_state.json e formata jogos ao vivo (sem delay; estado público)."""
    try:
        with _LIVE_STATE_PATH.open("r", encoding="utf-8") as f:
            state = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return []

    games: list[dict] = []
    for bucket in ("na_janela", "pre_janela", "pos_janela"):
        for g in state.get(bucket, []) or []:
            games.append(g)

    games.sort(key=lambda g: g.get("minuto") or 0, reverse=True)
    return games[:limit]


async def _fetch_pressure_scores(fixture_ids: list[int]) -> dict[int, dict[str, int]]:
    """Para cada fixture, retorna scores do sinal mais recente por tipo_analise.

    Returns: {fixture_id: {"pressure_score": int|None, "tension_score": int|None}}
    `pressure_score` vem do último sinal ESCANTEIOS, `tension_score` do último CARTOES.
    """
    if not fixture_ids:
        return {}

    db = Database()
    await db.connect()
    pool = db.pool
    if pool is None:
        return {}

    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT DISTINCT ON (jogo_id, tipo_analise)
                   jogo_id, tipo_analise, pressure_score
              FROM sinais
             WHERE jogo_id = ANY($1::int[])
             ORDER BY jogo_id, tipo_analise, timestamp DESC
            """,
            fixture_ids,
        )

    out: dict[int, dict[str, Optional[int]]] = {fid: {"pressure_score": None, "tension_score": None} for fid in fixture_ids}
    for r in rows:
        tipo = (r["tipo_analise"] or "ESCANTEIOS").upper()
        key = "tension_score" if tipo == "CARTOES" else "pressure_score"
        out[r["jogo_id"]][key] = r["pressure_score"]
    return out


async def _fetch_recent_signals(limit: int) -> list[dict]:
    """Sinais persistidos, sempre com delay >=15min (privacidade)."""
    db = Database()
    await db.connect()
    pool = db.pool
    if pool is None:
        return []

    async with pool.acquire() as conn:
        rows = await conn.fetch(
            f"""
            SELECT timestamp, liga_nome, jogo_descricao,
                   tipo_analise, linha, odd, resultado
              FROM sinais
             WHERE reavaliacao = FALSE
               AND timestamp < NOW() - INTERVAL '{SIGNAL_DELAY_MINUTES} minutes'
             ORDER BY timestamp DESC
             LIMIT $1
            """,
            limit,
        )

    out = []
    for r in rows:
        ts = r["timestamp"]
        if ts is not None and ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        out.append(
            {
                "emitted_at": ts.isoformat() if ts else None,
                "match": r["jogo_descricao"] or "",
                "league": r["liga_nome"] or "",
                "market": _format_market(r["tipo_analise"] or "ESCANTEIOS", float(r["linha"])),
                "odd": float(r["odd"]) if r["odd"] is not None else None,
                "delta_pct": None,  # reservado: movimento de odd requer join com odds_history
                "result": r["resultado"],
            }
        )
    return out


@router.get("/ticker")
async def public_ticker(
    request: Request,
    response: Response,
    limit: int = Query(10, ge=1, le=20),
) -> dict:
    """Ticker para landing page.

    `limit` aplica a cada lista (live e recent_signals).
    Sinais sempre com delay >=15min via SQL.
    Cache 60s. Rate limit 60req/min/IP.
    """
    _enforce_rate_limit(request, response)

    cache_key = f"ticker:{limit}"
    cached = _cache_get(cache_key)
    if cached is not None:
        response.headers["X-Cache"] = "HIT"
        return cached

    live_games = _load_live_games(limit)
    fixture_ids = [g["id"] for g in live_games if isinstance(g.get("id"), int)]
    scores_by_fixture = await _fetch_pressure_scores(fixture_ids)
    signals = await _fetch_recent_signals(limit)

    live_payload = []
    for g in live_games:
        fid = g.get("id")
        scores = scores_by_fixture.get(fid, {}) if isinstance(fid, int) else {}
        home = (g.get("home") or "").strip()
        away = (g.get("away") or "").strip()
        live_payload.append(
            {
                "match": f"{home} × {away}".strip(" ×"),
                "league": g.get("liga") or "",
                "minute": int(g.get("minuto") or 0),
                "score": g.get("placar") or "",
                "pressure_score": scores.get("pressure_score"),
                "tension_score": scores.get("tension_score"),
            }
        )

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "live": live_payload,
        "recent_signals": signals,
    }

    _cache_set(cache_key, payload)
    response.headers["X-Cache"] = "MISS"
    return payload


@router.get("/health")
def public_health() -> dict:
    """Health probe público (sem rate limit, sem cache)."""
    return {
        "status": "ok",
        "version": _VERSION,
        "uptime_seconds": int(time.time() - _app_start_ts),
    }
