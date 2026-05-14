"""Testes unit do `SportradarSession`.

Não dependem de fixtures reais nem de token válido — só da lógica de
parsing de exp, detecção de expiração e serialização do refresh via lock.
Harness Fase A §8.1.
"""
import asyncio
import time
from typing import Awaitable, Callable

import pytest

from data.providers.sportradar import SportradarSession
from data.providers.sportradar.session import TOKEN_REFRESH_MARGIN_S


def _token(exp_in: int) -> str:
    """Constrói um token sintético com exp=<now + exp_in>."""
    return f"T=exp={int(time.time()) + exp_in}~acl=/*~data=xxx~hmac=yyy"


def test_session_parses_exp_correctly():
    sess = SportradarSession()
    sess.set_token(_token(7200))
    assert 7100 < sess.ttl_remaining() <= 7200


def test_session_set_token_invalid_raises():
    sess = SportradarSession()
    with pytest.raises(ValueError):
        sess.set_token("nao-eh-token-valido")


def test_session_is_expired_uses_margin():
    sess = SportradarSession()
    # Token com TTL menor que a margem → tratado como expirado
    sess.set_token(_token(TOKEN_REFRESH_MARGIN_S - 10))
    assert sess.is_expired() is True

    # Token com TTL muito maior que a margem → não expirado
    sess.set_token(_token(TOKEN_REFRESH_MARGIN_S + 600))
    assert sess.is_expired() is False


def test_session_expired_when_no_token():
    sess = SportradarSession()
    assert sess.is_expired() is True


@pytest.mark.asyncio
async def test_session_get_or_refresh_returns_existing_token():
    sess = SportradarSession()
    sess.set_token(_token(7200))
    out = await sess.get_or_refresh()
    assert out == sess.token


@pytest.mark.asyncio
async def test_session_get_or_refresh_calls_refresher_when_expired():
    calls = 0

    async def refresher() -> str:
        nonlocal calls
        calls += 1
        return _token(7200)

    sess = SportradarSession(token_refresher=refresher)
    out = await sess.get_or_refresh()
    assert calls == 1
    assert out is not None
    assert "T=exp=" in out


@pytest.mark.asyncio
async def test_session_refresh_calls_refresher_once_under_contention():
    """20 corotinas pedindo refresh simultâneo → refresher chamado 1x.

    Garante que o lock async serializa e que após o primeiro adquirir,
    os outros re-checam expiração e usam o token já refrescado.
    """
    calls = 0

    async def slow_refresher() -> str:
        nonlocal calls
        calls += 1
        # Garante que outras corotinas tenham tempo de bater no lock
        await asyncio.sleep(0.05)
        return _token(7200)

    sess = SportradarSession(token_refresher=slow_refresher)
    tokens = await asyncio.gather(*[
        sess.get_or_refresh() for _ in range(20)
    ])
    assert calls == 1
    assert all(t == tokens[0] for t in tokens)


@pytest.mark.asyncio
async def test_session_refresh_raises_without_refresher_when_expired():
    sess = SportradarSession()
    with pytest.raises(RuntimeError, match="token_refresher"):
        await sess.get_or_refresh()


@pytest.mark.asyncio
async def test_session_refresh_after_token_aged_out():
    """Cenário real: token válido inicialmente, depois expira, refresher
    é chamado e o novo token vale."""
    calls = 0

    async def refresher() -> str:
        nonlocal calls
        calls += 1
        return _token(7200)

    sess = SportradarSession(token_refresher=refresher)
    sess.set_token(_token(TOKEN_REFRESH_MARGIN_S - 10))  # já dentro da margem

    out = await sess.get_or_refresh()
    assert calls == 1
    # Token foi substituído por um fresco
    assert not sess.is_expired()
    assert out == sess.token
