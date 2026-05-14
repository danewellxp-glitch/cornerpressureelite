"""Testes do rate_limiter com chave expirada e fallback gracioso."""

import sys
import os
import asyncio
import logging
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from unittest.mock import AsyncMock, MagicMock, patch
from aiohttp import ClientError

from utils.rate_limiter import RateLimiter


# ------------------------------------------------------------------
# RateLimiter — expired-key state
# ------------------------------------------------------------------

class TestRateLimiterExpiredKey:
    """Valida comportamento do rate_limiter quando a chave expira."""

    def test_key_expired_flag_defaults_false(self):
        limiter = RateLimiter(max_requests_per_day=7500)
        assert limiter.key_expired is False

    def test_mark_key_expired_sets_flag(self):
        limiter = RateLimiter(max_requests_per_day=7500)
        limiter.mark_key_expired("HTTP 401")
        assert limiter.key_expired is True

    def test_reset_key_expired_clears_flag(self):
        limiter = RateLimiter(max_requests_per_day=7500)
        limiter.mark_key_expired()
        limiter.reset_key_expired()
        assert limiter.key_expired is False

    def test_can_request_returns_false_when_key_expired(self):
        limiter = RateLimiter(max_requests_per_day=7500)
        limiter.mark_key_expired()
        assert limiter.can_request() is False

    def test_can_request_returns_true_when_key_valid(self):
        limiter = RateLimiter(max_requests_per_day=7500)
        assert limiter.can_request() is True

    def test_can_request_returns_false_at_daily_limit(self):
        limiter = RateLimiter(max_requests_per_day=2, max_requests_per_minute=10)
        limiter.record_request()
        limiter.record_request()
        assert limiter.can_request() is False

    @pytest.mark.asyncio
    async def test_wait_if_needed_returns_immediately_when_key_expired(self):
        """wait_if_needed NAO deve levantar excecao quando chave expirada."""
        limiter = RateLimiter(max_requests_per_day=7500)
        limiter.mark_key_expired()
        # Deve retornar sem levantar excecao
        await limiter.wait_if_needed()

    @pytest.mark.asyncio
    async def test_wait_if_needed_raises_at_daily_limit(self):
        """wait_if_needed ainda deve levantar excecao no limite diario."""
        limiter = RateLimiter(max_requests_per_day=2, max_requests_per_minute=10)
        limiter.record_request()
        limiter.record_request()
        with pytest.raises(RuntimeError, match="Limite diario"):
            await limiter.wait_if_needed()

    def test_record_request_does_nothing_special_when_expired(self):
        """record_request funciona mesmo com chave expirada (idempotente)."""
        limiter = RateLimiter(max_requests_per_day=7500)
        limiter.mark_key_expired()
        # Nao deve crashar
        limiter.record_request()
        assert limiter.requests_today == 1

    def test_sync_from_api_does_not_clear_expired_flag(self):
        """sync_from_api NAO deve limpar o flag de expirada automaticamente."""
        limiter = RateLimiter(max_requests_per_day=7500)
        limiter.mark_key_expired()
        limiter.sync_from_api(100, 7500)
        assert limiter.key_expired is True

    def test_remaining_daily_returns_value_when_expired(self):
        limiter = RateLimiter(max_requests_per_day=7500)
        limiter.mark_key_expired()
        # Deve retornar o valor normal, nao crashar
        assert limiter.remaining_daily() == 7500


# ------------------------------------------------------------------
# APIFootballClient — 401/403 detection
# ------------------------------------------------------------------

class TestAPIClientExpiredKey:
    """Valida que o API client detecta chave expirada via HTTP 401/403."""

    def _make_client(self, limiter: RateLimiter):
        """Cria um APIFootballClient mockado com o rate_limiter fornecido."""
        from data.api_client import APIFootballClient
        return APIFootballClient(api_key="test-key", rate_limiter=limiter)

    @pytest.mark.asyncio
    async def test_request_marks_key_expired_on_401(self):
        """HTTP 401 deve marcar a chave como expirada."""
        limiter = RateLimiter(max_requests_per_day=7500)
        client = self._make_client(limiter)

        mock_response = AsyncMock()
        mock_response.status = 401
        mock_response.headers = {"Content-Type": "application/json"}
        mock_response.text = AsyncMock(return_value='{"message": "Unauthorized"}')
        mock_response.url = "http://test.url"

        mock_session = AsyncMock()
        mock_session.get = MagicMock(return_value=AsyncMock(
            __aenter__=AsyncMock(return_value=mock_response),
            __aexit__=AsyncMock(return_value=None),
        ))

        with patch.object(client, '_get_session', return_value=mock_session):
            with pytest.raises(ClientError, match="expirada"):
                await client._request("fixtures")

        assert limiter.key_expired is True

    @pytest.mark.asyncio
    async def test_request_marks_key_expired_on_403(self):
        """HTTP 403 deve marcar a chave como expirada."""
        limiter = RateLimiter(max_requests_per_day=7500)
        client = self._make_client(limiter)

        mock_response = AsyncMock()
        mock_response.status = 403
        mock_response.headers = {"Content-Type": "application/json"}
        mock_response.text = AsyncMock(return_value='{"message": "Forbidden"}')
        mock_response.url = "http://test.url"

        mock_session = AsyncMock()
        mock_session.get = MagicMock(return_value=AsyncMock(
            __aenter__=AsyncMock(return_value=mock_response),
            __aexit__=AsyncMock(return_value=None),
        ))

        with patch.object(client, '_get_session', return_value=mock_session):
            with pytest.raises(ClientError, match="expirada"):
                await client._request("fixtures")

        assert limiter.key_expired is True

    @pytest.mark.asyncio
    async def test_check_status_marks_key_expired_on_401(self):
        """check_status com HTTP 401 deve marcar chave como expirada."""
        limiter = RateLimiter(max_requests_per_day=7500)
        client = self._make_client(limiter)

        mock_response = AsyncMock()
        mock_response.status = 401
        mock_response.headers = {"Content-Type": "application/json"}
        mock_response.text = AsyncMock(return_value='{"message": "Unauthorized"}')

        mock_session = AsyncMock()
        mock_session.get = MagicMock(return_value=AsyncMock(
            __aenter__=AsyncMock(return_value=mock_response),
            __aexit__=AsyncMock(return_value=None),
        ))

        with patch.object(client, '_get_session', return_value=mock_session):
            with pytest.raises(ClientError, match="expirada"):
                await client.check_status()

        assert limiter.key_expired is True

    @pytest.mark.asyncio
    async def test_no_api_calls_after_key_expired(self):
        """Depois de marcar key_expired, can_request retorna False e
        wait_if_needed retorna imediatamente sem crashar."""
        limiter = RateLimiter(max_requests_per_day=7500)
        limiter.mark_key_expired("HTTP 401")

        # can_request deve bloquear
        assert limiter.can_request() is False

        # wait_if_needed deve retornar sem excecao
        await limiter.wait_if_needed()

        # O sistema pode continuar operando sem crashar
        assert limiter.key_expired is True


# ------------------------------------------------------------------
# Integration: full pipeline simulation with expired key
# ------------------------------------------------------------------

class TestExpiredKeyIntegration:
    """Simula o ciclo completo do pipeline com chave expirada."""

    @pytest.mark.asyncio
    async def test_pipeline_graceful_degradation_on_expired_key(self):
        """O pipeline deve degradar graciosamente sem crashar quando
        a chave expira durante operacao."""
        limiter = RateLimiter(max_requests_per_day=7500)

        # Simula operacao normal
        assert limiter.can_request() is True
        limiter.record_request()

        # Simula deteccao de chave expirada (como faria o api_client)
        limiter.mark_key_expired("HTTP 401 em /fixtures")

        # Pipeline tenta continuar — deve degradar graciosamente
        assert limiter.can_request() is False
        await limiter.wait_if_needed()  # Nao deve crashar
        assert limiter.remaining_daily() >= 0

    @pytest.mark.asyncio
    async def test_key_renewal_resumes_operations(self):
        """Apos renovacao da chave, o pipeline deve voltar a operar."""
        limiter = RateLimiter(max_requests_per_day=7500)
        limiter.mark_key_expired()
        limiter.record_request()  # conta mesmo com key expirada

        # Renovacao
        limiter.reset_key_expired()
        limiter.requests_today = 0  # reset contagem

        assert limiter.key_expired is False
        assert limiter.can_request() is True
        await limiter.wait_if_needed()  # Nao deve crashar
