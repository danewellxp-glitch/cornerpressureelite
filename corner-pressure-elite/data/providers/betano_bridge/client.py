"""Cliente HTTPX async para o bridge FastAPI local em :8080.

O bridge:
- `GET /quote?event_id=X&market=Y&line=Z&side=over|under&capture_seconds=N`
  → 200 `{found: true, odd, line_found, selection_label, ...}` ou
    404 `{found: false, ...}`
- `GET /markets?event_id=X&market=Y&capture_seconds=N`
  → 200 `{found: true, lines_count, lines: [{line, over_price, under_price, ...}]}`
    ou 404 `{found: false, reason}`
- `GET /health` → `{status, chrome_connected, pages_open, uptime_seconds}`
"""
from __future__ import annotations

import logging
from typing import Optional

import httpx

from data.providers.betano_bridge.exceptions import (
    BridgeMarketNotFound,
    BridgeTimeout,
    BridgeUnavailable,
)

log = logging.getLogger("cpes.providers.betano_bridge.client")


class BetanoBridgeClient:
    """Cliente HTTP async para o bridge FastAPI local.

    Mantém um `httpx.AsyncClient` reaproveitado (keep-alive). Chamar
    `close()` no shutdown do orquestrador.
    """

    def __init__(
        self,
        base_url: str,
        timeout_sec: float,
        capture_sec: float,
        retries: int = 1,
    ):
        self._base_url = base_url.rstrip("/")
        self._timeout_sec = float(timeout_sec)
        self._capture_sec = float(capture_sec)
        self._retries = int(retries)
        self._client: Optional[httpx.AsyncClient] = None

    async def _ensure_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self._base_url,
                timeout=httpx.Timeout(self._timeout_sec),
            )
        return self._client

    async def quote(
        self,
        event_id: str,
        market: str,
        line: float,
        side: str = "over",
    ) -> dict:
        """Pede odd ao bridge. Retorna o JSON em caso de sucesso.

        Levanta:
          - `BridgeUnavailable` se rede falha ou HTTP >= 500
          - `BridgeTimeout` se o tempo total excede `timeout_sec`
          - `BridgeMarketNotFound` se HTTP 404 ou `found:false`
        """
        client = await self._ensure_client()
        params = {
            "event_id": event_id,
            "market": market,
            "line": line,
            "side": side,
            "capture_seconds": self._capture_sec,
        }

        attempts = self._retries + 1
        last_timeout: Optional[Exception] = None
        last_unavailable: Optional[Exception] = None

        for attempt in range(1, attempts + 1):
            try:
                response = await client.get("/quote", params=params)
            except httpx.TimeoutException as e:
                last_timeout = e
                log.warning(
                    "bridge.quote.timeout attempt=%d/%d event_id=%s market=%s",
                    attempt, attempts, event_id, market,
                )
                continue
            except httpx.RequestError as e:
                last_unavailable = e
                log.warning(
                    "bridge.quote.unreachable attempt=%d/%d event_id=%s err=%s",
                    attempt, attempts, event_id, e,
                )
                continue

            if response.status_code == 404:
                # Fluxo legítimo: bridge respondeu mas mercado/linha não existe.
                raise BridgeMarketNotFound(
                    f"market={market} line={line} side={side} event_id={event_id}"
                )

            if response.status_code >= 500:
                last_unavailable = BridgeUnavailable(
                    f"HTTP {response.status_code}"
                )
                log.warning(
                    "bridge.quote.server_error attempt=%d/%d status=%d",
                    attempt, attempts, response.status_code,
                )
                continue

            response.raise_for_status()
            data = response.json()

            if not data.get("found"):
                raise BridgeMarketNotFound(
                    f"found=false market={market} line={line} side={side} event_id={event_id}"
                )

            return data

        if last_timeout is not None:
            raise BridgeTimeout(
                f"bridge timeout após {attempts} tentativas event_id={event_id}"
            ) from last_timeout
        raise BridgeUnavailable(
            f"bridge unreachable após {attempts} tentativas event_id={event_id}"
        ) from last_unavailable

    async def markets(self, event_id: str, market: str) -> dict:
        """Pede o catálogo completo de linhas ao bridge.

        Retorna o JSON `{found, event_id, market, lines_count, lines: [...]}`.

        Levanta:
          - `BridgeUnavailable` se rede falha ou HTTP >= 500
          - `BridgeTimeout` se o tempo total excede `timeout_sec`
          - `BridgeMarketNotFound` se HTTP 404 ou `found:false`
        """
        client = await self._ensure_client()
        params = {
            "event_id": event_id,
            "market": market,
            "capture_seconds": self._capture_sec,
        }

        attempts = self._retries + 1
        last_timeout: Optional[Exception] = None
        last_unavailable: Optional[Exception] = None

        for attempt in range(1, attempts + 1):
            try:
                response = await client.get("/markets", params=params)
            except httpx.TimeoutException as e:
                last_timeout = e
                log.warning(
                    "bridge.markets.timeout attempt=%d/%d event_id=%s market=%s",
                    attempt, attempts, event_id, market,
                )
                continue
            except httpx.RequestError as e:
                last_unavailable = e
                log.warning(
                    "bridge.markets.unreachable attempt=%d/%d event_id=%s err=%s",
                    attempt, attempts, event_id, e,
                )
                continue

            if response.status_code == 404:
                raise BridgeMarketNotFound(
                    f"catálogo vazio market={market} event_id={event_id}"
                )

            if response.status_code >= 500:
                last_unavailable = BridgeUnavailable(f"HTTP {response.status_code}")
                log.warning(
                    "bridge.markets.server_error attempt=%d/%d status=%d",
                    attempt, attempts, response.status_code,
                )
                continue

            response.raise_for_status()
            data = response.json()

            if not data.get("found"):
                raise BridgeMarketNotFound(
                    f"found=false market={market} event_id={event_id}"
                )

            return data

        if last_timeout is not None:
            raise BridgeTimeout(
                f"bridge timeout após {attempts} tentativas event_id={event_id}"
            ) from last_timeout
        raise BridgeUnavailable(
            f"bridge unreachable após {attempts} tentativas event_id={event_id}"
        ) from last_unavailable

    async def event_state(self, event_id: str) -> dict:
        """Pede o payload /event/<id>/state do bridge (E.1 PARTE B).

        Retorna o JSON `{captured_at, event_id, version, from_cache, data: {...}}`.

        Levanta:
          - `BridgeUnavailable` se rede falha ou HTTP >= 500
          - `BridgeTimeout` se o tempo total excede `timeout_sec`
          - `BridgeMarketNotFound` se HTTP 404 (event não existe)
        """
        client = await self._ensure_client()

        attempts = self._retries + 1
        last_timeout: Optional[Exception] = None
        last_unavailable: Optional[Exception] = None

        for attempt in range(1, attempts + 1):
            try:
                response = await client.get(f"/event/{event_id}/state")
            except httpx.TimeoutException as e:
                last_timeout = e
                log.warning(
                    "bridge.event_state.timeout attempt=%d/%d event_id=%s",
                    attempt, attempts, event_id,
                )
                continue
            except httpx.RequestError as e:
                last_unavailable = e
                log.warning(
                    "bridge.event_state.unreachable attempt=%d/%d event_id=%s err=%s",
                    attempt, attempts, event_id, e,
                )
                continue

            if response.status_code == 404:
                raise BridgeMarketNotFound(f"event_state not_found event_id={event_id}")

            if response.status_code >= 500:
                last_unavailable = BridgeUnavailable(f"HTTP {response.status_code}")
                log.warning(
                    "bridge.event_state.server_error attempt=%d/%d status=%d",
                    attempt, attempts, response.status_code,
                )
                continue

            response.raise_for_status()
            return response.json()

        if last_timeout is not None:
            raise BridgeTimeout(
                f"bridge timeout após {attempts} tentativas event_id={event_id}"
            ) from last_timeout
        raise BridgeUnavailable(
            f"bridge unreachable após {attempts} tentativas event_id={event_id}"
        ) from last_unavailable

    async def health(self) -> dict:
        """Retorna `{status, chrome_connected, pages_open, uptime_seconds}`."""
        client = await self._ensure_client()
        try:
            r = await client.get("/health", timeout=httpx.Timeout(5.0))
            r.raise_for_status()
            return r.json()
        except (httpx.TimeoutException, httpx.RequestError) as e:
            raise BridgeUnavailable(f"health falhou: {e}") from e

    async def close(self) -> None:
        if self._client is not None and not self._client.is_closed:
            await self._client.aclose()
        self._client = None
