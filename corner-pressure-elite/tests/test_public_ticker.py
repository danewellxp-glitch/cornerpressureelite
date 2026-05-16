"""Testes do endpoint público /api/v1/public/ticker e /api/v1/public/health."""
from __future__ import annotations

import json
from datetime import datetime
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.testclient import TestClient

import api.public as public_mod
from api.public import router as public_router


def _build_test_app() -> FastAPI:
    """Mini app que monta apenas o router público + CORS.

    Evita importar `api_server.app` porque ele depende de módulos WIP
    (notifier.asaas_client) que ainda não foram commitados.
    O CORS replica o de produção pra que o teste cubra os headers reais.
    """
    test_app = FastAPI()
    test_app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:3000",
            "https://iqpressure.online",
            "https://www.iqpressure.online",
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    test_app.include_router(public_router)
    return test_app


app = _build_test_app()


class _FakeConn:
    """Conn fake: serve filas de rows na ordem em que `fetch` é chamado."""

    def __init__(self):
        self.rows_queue: list[list[dict]] = []
        self.queries: list[tuple[str, tuple]] = []

    async def fetch(self, sql: str, *args) -> list[dict]:
        self.queries.append((sql, args))
        if self.rows_queue:
            return self.rows_queue.pop(0)
        return []


class _FakePool:
    def __init__(self, conn: _FakeConn):
        self._conn = conn

    def acquire(self):
        conn = self._conn

        class _Ctx:
            async def __aenter__(self):
                return conn

            async def __aexit__(self, exc_type, exc, tb):
                return False

        return _Ctx()

    async def close(self):
        return None


@pytest.fixture(autouse=True)
def _reset_public_state():
    public_mod._cache.clear()
    public_mod._request_log.clear()
    yield
    public_mod._cache.clear()
    public_mod._request_log.clear()


@pytest.fixture
def fake_db(monkeypatch):
    """Substitui o pool asyncpg por um fake (sem rede)."""
    from storage.database import Database

    conn = _FakeConn()
    pool = _FakePool(conn)

    async def _fake_connect(self):
        Database._shared_pool = pool

    monkeypatch.setattr(Database, "connect", _fake_connect)
    Database._shared_pool = pool
    yield conn
    Database._shared_pool = None


@pytest.fixture
def live_state(monkeypatch, tmp_path):
    """Permite escrever um live_state.json temp para cada teste."""
    state_file = tmp_path / "live_state.json"
    monkeypatch.setattr(public_mod, "_LIVE_STATE_PATH", state_file)

    def _write(state: dict[str, Any]) -> None:
        state_file.write_text(json.dumps(state), encoding="utf-8")

    return _write


@pytest.fixture
def client():
    return TestClient(app)


def _empty_state() -> dict[str, Any]:
    return {"pre_janela": [], "na_janela": [], "pos_janela": [], "ids_observados": []}


def test_health_endpoint(client):
    r = client.get("/api/v1/public/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert "version" in body
    assert isinstance(body["uptime_seconds"], int)
    assert body["uptime_seconds"] >= 0


def test_ticker_returns_live_games_when_active(client, fake_db, live_state):
    live_state(
        {
            "atualizado": "2026-05-16T20:00:00",
            "ciclo": 1,
            "pre_janela": [],
            "na_janela": [
                {
                    "id": 999,
                    "home": "Manchester City",
                    "away": "Arsenal",
                    "liga": "Premier League",
                    "minuto": 67,
                    "placar": "1-1",
                    "fase": "na_janela",
                }
            ],
            "pos_janela": [],
            "ids_observados": [],
        }
    )
    # fetch sequence: pressure_scores (fixture_id=999) → recent_signals
    fake_db.rows_queue = [
        [{"jogo_id": 999, "tipo_analise": "ESCANTEIOS", "pressure_score": 8}],
        [],  # no signals
    ]
    r = client.get("/api/v1/public/ticker")
    assert r.status_code == 200
    body = r.json()
    assert len(body["live"]) == 1
    g = body["live"][0]
    assert g["match"] == "Manchester City × Arsenal"
    assert g["league"] == "Premier League"
    assert g["minute"] == 67
    assert g["score"] == "1-1"
    assert g["pressure_score"] == 8
    assert g["tension_score"] is None
    assert body["recent_signals"] == []


def test_ticker_returns_recent_signals_with_15min_delay(client, fake_db, live_state):
    live_state(_empty_state())
    old_ts = datetime(2026, 5, 16, 20, 0, 0)  # naive — endpoint marca como UTC
    fake_db.rows_queue = [
        [  # _fetch_recent_signals (no live games, so pressure_scores skipped)
            {
                "timestamp": old_ts,
                "liga_nome": "La Liga",
                "jogo_descricao": "Real Madrid × Barcelona",
                "tipo_analise": "CARTOES",
                "linha": 4.5,
                "odd": 1.88,
                "resultado": None,
            }
        ]
    ]
    r = client.get("/api/v1/public/ticker")
    assert r.status_code == 200
    body = r.json()
    sigs = body["recent_signals"]
    assert len(sigs) == 1
    s = sigs[0]
    assert s["match"] == "Real Madrid × Barcelona"
    assert s["league"] == "La Liga"
    assert s["market"] == "Mais 4.5 cartões amarelos"
    assert s["odd"] == 1.88
    assert s["result"] is None
    assert s["delta_pct"] is None
    assert s["emitted_at"].startswith("2026-05-16T20:00:00")


def test_ticker_never_returns_signals_under_15min(client, fake_db, live_state):
    """Garante que a query SQL aplica o filtro NOW() - 15min (não passa via Python)."""
    live_state(_empty_state())
    r = client.get("/api/v1/public/ticker")
    assert r.status_code == 200
    # Filtra para queries de sinais (não a de pressure_scores)
    signal_queries = [
        sql for sql, _ in fake_db.queries if "FROM sinais" in sql and "INTERVAL" in sql
    ]
    assert len(signal_queries) == 1, "ticker deve emitir exatamente uma query de sinais"
    sql = signal_queries[0]
    assert "INTERVAL '15 minutes'" in sql
    assert "timestamp < NOW()" in sql


def test_ticker_respects_limit_parameter(client, fake_db, live_state):
    live_state(
        {
            "pre_janela": [],
            "na_janela": [
                {"id": i, "home": f"H{i}", "away": f"A{i}", "liga": "L",
                 "minuto": i + 50, "placar": "0-0"}
                for i in range(10)
            ],
            "pos_janela": [],
            "ids_observados": [],
        }
    )
    fake_db.rows_queue = [[], []]  # pressure_scores empty, signals empty
    r = client.get("/api/v1/public/ticker?limit=3")
    assert r.status_code == 200
    body = r.json()
    assert len(body["live"]) == 3
    # Ordenação por minuto DESC: 59, 58, 57
    assert [g["minute"] for g in body["live"]] == [59, 58, 57]


def test_ticker_rejects_invalid_limit(client):
    assert client.get("/api/v1/public/ticker?limit=21").status_code == 422
    assert client.get("/api/v1/public/ticker?limit=0").status_code == 422


def test_ticker_cache_hit_under_60s(client, fake_db, live_state):
    live_state(_empty_state())
    r1 = client.get("/api/v1/public/ticker")
    assert r1.status_code == 200
    assert r1.headers.get("x-cache") == "MISS"
    r2 = client.get("/api/v1/public/ticker")
    assert r2.status_code == 200
    assert r2.headers.get("x-cache") == "HIT"
    assert r1.json() == r2.json()
    # DB foi chamado apenas no MISS (1 vez — apenas signals, sem live games)
    signal_queries = [q for q, _ in fake_db.queries if "FROM sinais" in q]
    assert len(signal_queries) == 1


def test_ticker_rate_limit_429_after_60_requests(client, fake_db, live_state):
    live_state(_empty_state())
    for i in range(public_mod.RATE_LIMIT_MAX):
        r = client.get("/api/v1/public/ticker")
        assert r.status_code == 200, f"request #{i} should pass"
        assert r.headers.get("x-ratelimit-limit") == str(public_mod.RATE_LIMIT_MAX)

    blocked = client.get("/api/v1/public/ticker")
    assert blocked.status_code == 429
    assert blocked.headers.get("retry-after") is not None
    assert blocked.headers.get("x-ratelimit-remaining") == "0"


def test_cors_headers_present(client, fake_db, live_state):
    live_state(_empty_state())
    r = client.get(
        "/api/v1/public/ticker",
        headers={"Origin": "https://iqpressure.online"},
    )
    assert r.status_code == 200
    assert r.headers.get("access-control-allow-origin") == "https://iqpressure.online"
