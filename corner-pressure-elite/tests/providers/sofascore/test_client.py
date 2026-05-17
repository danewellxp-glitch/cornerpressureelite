"""Testes do SofaScoreClient (Fase K.1 PARTE A).

5 testes: 1 unitário puro, 1 context manager, 2 smoke real (rede), 1 rate limit.
Smoke real podem ser pulados em CI sem rede via `pytest -k "not real"`.
"""
from __future__ import annotations

import time

import pytest

from data.providers.sofascore.client import (
    SofaScoreBlockedError,
    SofaScoreClient,
    SofaScoreClientError,
)


@pytest.mark.asyncio
async def test_client_instantiation():
    client = SofaScoreClient()
    assert client._impersonate == "chrome120"
    assert client._rate_limit == 10
    assert client._session is None
    assert client._base_url == "https://api.sofascore.com/api/v1"


@pytest.mark.asyncio
async def test_client_context_manager():
    async with SofaScoreClient() as client:
        assert client._session is not None
    # Após exit, sessão encerrada.
    assert client._session is None


@pytest.mark.asyncio
async def test_health_real():
    """Smoke real contra SofaScore."""
    async with SofaScoreClient() as client:
        healthy = await client.health()
        assert healthy is True


@pytest.mark.asyncio
async def test_get_live_events_real():
    """Smoke real: lista de jogos live (pode ser vazio fora de horários de pico)."""
    async with SofaScoreClient() as client:
        events = await client.get_live_events()
        assert events is not None, "API devolveu None — possível 403/bloqueio"
        assert isinstance(events, list)
        # Não asserta len>0 — pode não ter jogo live no momento.


@pytest.mark.asyncio
async def test_rate_limit_throttles():
    """Token bucket: 4 chamadas a 2 req/s ⇒ >= ~1.5s."""
    client = SofaScoreClient(rate_limit_per_sec=2)
    await client.start()
    try:
        start = time.monotonic()
        for _ in range(4):
            await client._acquire_token()
        elapsed = time.monotonic() - start
        # 4 tokens a 2/s: 2 primeiros free (bucket cheio), 3º e 4º
        # esperam 0.5s cada. Total >= 1.0s (com folga pra jitter).
        assert elapsed >= 1.0, f"Esperado >=1s, foi {elapsed:.2f}s"
    finally:
        await client.close()
