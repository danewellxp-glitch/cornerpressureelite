"""Unit tests do `BetanoBridgeOddsAdapter` + `BetanoBridgeClient`.

Mockam HTTP via `httpx.MockTransport` (builtin) — sem dependências extras.
Mockam o client via classe fake quando o foco é a lógica do adapter.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

import httpx
import pytest

from data.odds_provider import (
    CanonicalFixture,
    CanonicalOverUnder,
    CompositeOddsProvider,
)
from data.providers.betano_bridge.client import BetanoBridgeClient
from data.providers.betano_bridge.exceptions import (
    BridgeMarketNotFound,
    BridgeTimeout,
    BridgeUnavailable,
)
from data.providers.betano_bridge.odds_adapter import BetanoBridgeOddsAdapter


# ─── Helpers ────────────────────────────────────────────────────────


def _fixture(fixture_id: int = 100) -> CanonicalFixture:
    return CanonicalFixture(
        fixture_id=fixture_id,
        home_team="Mirassol",
        away_team="Bragantino",
        league_id=73,
        starts_at_utc=datetime(2026, 5, 13, 22, 30, tzinfo=timezone.utc),
    )


class _FakeRepo:
    """fixture_repo que mapeia fixture_id → betano_event_id em memória."""

    def __init__(self, mapping: Optional[dict] = None, raises: bool = False):
        self._mapping = mapping or {}
        self._raises = raises

    async def get_betano_event_id(self, fixture_id: int):
        if self._raises:
            raise RuntimeError("db boom")
        return self._mapping.get(fixture_id)


def _client_with_transport(handler) -> BetanoBridgeClient:
    """Constrói client com MockTransport injetado (substitui o AsyncClient interno)."""
    client = BetanoBridgeClient(
        base_url="http://bridge.test",
        timeout_sec=2.0,
        capture_sec=5.0,
        retries=1,
    )
    client._client = httpx.AsyncClient(
        base_url="http://bridge.test",
        transport=httpx.MockTransport(handler),
        timeout=httpx.Timeout(2.0),
    )
    return client


def _ok_payload(side: str, line: float = 9.5, market: str = "corners_over_under") -> dict:
    odd = 1.85 if side == "over" else 2.07
    return {
        "found": True,
        "event_id": "84592546",
        "market": market,
        "line": line,
        "side": side,
        "elapsed_seconds": 14.32,
        "page_url": "https://www.betano.bet.br/live/m/84592546/",
        "odd": odd,
        "line_found": line,
        "selection_label": "Mais de" if side == "over" else "Menos de",
        "title_pos": 1234,
    }


# ─── Fake client (pra testar lógica do adapter sem HTTP) ────────────


class _FakeClient:
    def __init__(self, responses=None, raises=None):
        self._responses = responses or {}
        self._raises = raises
        self.calls = []

    async def quote(self, event_id, market, line, side="over"):
        self.calls.append({"event_id": event_id, "market": market, "line": line, "side": side})
        if self._raises is not None:
            raise self._raises
        key = (market, side)
        if key not in self._responses:
            raise BridgeMarketNotFound(f"no fake for {key}")
        return self._responses[key]

    async def health(self):
        if isinstance(self._raises, BridgeUnavailable):
            raise self._raises
        return {"status": "ok", "chrome_connected": True, "pages_open": 1, "uptime_seconds": 10}

    async def close(self):
        pass


# ─── Casos ──────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_quote_ok_returns_snapshot_corners():
    client = _FakeClient(responses={
        ("corners_over_under", "over"): _ok_payload("over", line=9.5),
        ("corners_over_under", "under"): _ok_payload("under", line=9.5),
    })
    adapter = BetanoBridgeOddsAdapter(
        client=client, fixture_repo=_FakeRepo({100: "84592546"})
    )

    res = await adapter.get_corners(_fixture(), current_score=0)

    assert res is not None
    assert isinstance(res, CanonicalOverUnder)
    assert res.source == "betano_bridge"
    assert res.market_kind == "corners"
    assert res.linha == 9.5
    assert res.odd_over == 1.85
    assert res.odd_under == 2.07
    # Fez 2 chamadas, uma por side
    assert len(client.calls) == 2
    assert {c["side"] for c in client.calls} == {"over", "under"}


@pytest.mark.asyncio
async def test_quote_ok_returns_snapshot_cards():
    client = _FakeClient(responses={
        ("cards_over_under", "over"): _ok_payload("over", line=3.5, market="cards_over_under"),
        ("cards_over_under", "under"): _ok_payload("under", line=3.5, market="cards_over_under"),
    })
    adapter = BetanoBridgeOddsAdapter(
        client=client, fixture_repo=_FakeRepo({100: "84592546"})
    )

    res = await adapter.get_cards(_fixture(), current_score=0)

    assert res is not None
    assert res.source == "betano_bridge"
    assert res.market_kind == "cards"
    assert res.linha == 3.5
    assert res.odd_over == 1.85
    # Default line de cards é 3.5
    assert all(c["line"] == 3.5 for c in client.calls)


@pytest.mark.asyncio
async def test_quote_404_returns_none():
    """Bridge 404 (mercado/linha inexistente) → adapter devolve None pra cascade."""
    client = _FakeClient(raises=BridgeMarketNotFound("no market"))
    adapter = BetanoBridgeOddsAdapter(
        client=client, fixture_repo=_FakeRepo({100: "84592546"})
    )
    assert await adapter.get_corners(_fixture(), current_score=0) is None


@pytest.mark.asyncio
async def test_quote_timeout_returns_none():
    """Cliente real esgotando retries em timeout."""
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("simulated", request=request)

    real_client = _client_with_transport(handler)
    adapter = BetanoBridgeOddsAdapter(
        client=real_client, fixture_repo=_FakeRepo({100: "84592546"})
    )

    res = await adapter.get_corners(_fixture(), current_score=0)
    assert res is None
    await real_client.close()


@pytest.mark.asyncio
async def test_quote_connection_error_returns_none():
    """Bridge offline (rede falha) → BridgeUnavailable interna → None."""
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused", request=request)

    real_client = _client_with_transport(handler)
    adapter = BetanoBridgeOddsAdapter(
        client=real_client, fixture_repo=_FakeRepo({100: "84592546"})
    )

    res = await adapter.get_corners(_fixture(), current_score=0)
    assert res is None
    await real_client.close()


@pytest.mark.asyncio
async def test_fixture_without_betano_event_id_returns_none_no_http():
    """Sem mapeamento → adapter não chama HTTP."""
    client = _FakeClient()  # sem responses, qualquer call falharia
    adapter = BetanoBridgeOddsAdapter(
        client=client, fixture_repo=_FakeRepo({})  # vazio
    )

    res = await adapter.get_corners(_fixture(), current_score=0)
    assert res is None
    assert client.calls == []


@pytest.mark.asyncio
async def test_composite_falls_back_to_apifootball_on_bridge_error():
    """Bridge falha → CompositeOddsProvider chama AF e retorna AF result."""
    bridge = BetanoBridgeOddsAdapter(
        client=_FakeClient(raises=BridgeUnavailable("offline")),
        fixture_repo=_FakeRepo({100: "84592546"}),
    )

    class _StubAF:
        name = "apifootball"

        async def get_corners(self, fixture, current_score):
            return CanonicalOverUnder(
                source="apifootball", market_kind="corners", market_code="",
                linha=10.5, odd_over=1.92, odd_under=1.88,
            )

        async def get_cards(self, fixture, current_score):
            return None

        async def healthcheck(self):
            return True

    af = _StubAF()
    composite = CompositeOddsProvider([bridge, af])

    res = await composite.get_corners(_fixture(), current_score=0)
    assert res is not None
    assert res.source == "apifootball"
    assert res.linha == 10.5
