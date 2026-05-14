"""Integração viva contra a Betano — depende de cookies congelados.

Skip automático se `config/betano_cookies.json` não existir. Útil quando
quisermos validar que cookies / fingerprint ainda funcionam.
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest

COOKIES_PATH = Path("config/betano_cookies.json")

pytestmark = pytest.mark.skipif(
    not COOKIES_PATH.exists(),
    reason="config/betano_cookies.json não encontrado — testes de integração pulados",
)

KNOWN_EVENT = int(os.environ.get("BETANO_TEST_EVENT", "84586925"))


@pytest.mark.asyncio
async def test_get_config_real_call():
    from data.providers.betano import BetanoSession, BetanoStatsStream

    session = BetanoSession.from_file(COOKIES_PATH)
    client = BetanoStatsStream(session)
    try:
        cfg = await client.get_config(KNOWN_EVENT)
        assert cfg is not None
        assert cfg.provider_type in ("Opta", "Sportradar", "?")
    finally:
        await session.close()


@pytest.mark.asyncio
async def test_get_stats_detailed_real_call():
    from data.providers.betano import BetanoSession, BetanoStatsStream

    session = BetanoSession.from_file(COOKIES_PATH)
    client = BetanoStatsStream(session)
    try:
        det = await client.get_stats_detailed(KNOWN_EVENT)
        # evento finalizado pode retornar None — só tipa se vier
        if det is not None:
            assert det.home.total.corners >= 0
            assert det.away.total.corners >= 0
    finally:
        await session.close()


@pytest.mark.asyncio
async def test_healthcheck_returns_bool():
    from data.providers.betano import BetanoSession, BetanoStatsStream

    session = BetanoSession.from_file(COOKIES_PATH)
    client = BetanoStatsStream(session)
    try:
        ok = await client.healthcheck(KNOWN_EVENT)
        assert isinstance(ok, bool)
    finally:
        await session.close()
