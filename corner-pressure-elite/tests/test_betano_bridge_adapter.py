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
    def __init__(self, responses=None, raises=None, catalog=None, catalog_raises=None):
        self._responses = responses or {}
        self._raises = raises
        self._catalog = catalog  # lista de dicts pra markets()
        self._catalog_raises = catalog_raises
        self.calls = []
        self.markets_calls = []

    async def quote(self, event_id, market, line, side="over"):
        self.calls.append({"event_id": event_id, "market": market, "line": line, "side": side})
        if self._raises is not None:
            raise self._raises
        key = (market, side)
        if key not in self._responses:
            raise BridgeMarketNotFound(f"no fake for {key}")
        return self._responses[key]

    async def markets(self, event_id, market):
        self.markets_calls.append({"event_id": event_id, "market": market})
        if self._catalog_raises is not None:
            raise self._catalog_raises
        lines = self._catalog if self._catalog is not None else []
        return {
            "found": True,
            "event_id": event_id,
            "market": market,
            "lines_count": len(lines),
            "lines": lines,
        }

    async def health(self):
        if isinstance(self._raises, BridgeUnavailable):
            raise self._raises
        return {"status": "ok", "chrome_connected": True, "pages_open": 1, "uptime_seconds": 10}

    async def close(self):
        pass


def _line(line: float, over: float, under: float) -> dict:
    return {
        "line": line,
        "over_price": over,
        "under_price": under,
        "selection_over_label": f"Mais de {line}",
        "selection_under_label": f"Menos de {line}",
    }


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

    res = await adapter.get_corners(_fixture(), current_score=0, line=9.5)

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
    # Fase 3: line passada pela engine vai literal pro client
    assert all(c["line"] == 9.5 for c in client.calls)


@pytest.mark.asyncio
async def test_quote_ok_returns_snapshot_cards():
    client = _FakeClient(responses={
        ("cards_over_under", "over"): _ok_payload("over", line=3.5, market="cards_over_under"),
        ("cards_over_under", "under"): _ok_payload("under", line=3.5, market="cards_over_under"),
    })
    adapter = BetanoBridgeOddsAdapter(
        client=client, fixture_repo=_FakeRepo({100: "84592546"})
    )

    res = await adapter.get_cards(_fixture(), current_score=0, line=3.5)

    assert res is not None
    assert res.source == "betano_bridge"
    assert res.market_kind == "cards"
    assert res.linha == 3.5
    assert res.odd_over == 1.85
    assert all(c["line"] == 3.5 for c in client.calls)


@pytest.mark.asyncio
async def test_quote_404_returns_none():
    """Bridge 404 (mercado/linha inexistente) → adapter devolve None pra cascade."""
    client = _FakeClient(raises=BridgeMarketNotFound("no market"))
    adapter = BetanoBridgeOddsAdapter(
        client=client, fixture_repo=_FakeRepo({100: "84592546"})
    )
    assert await adapter.get_corners(_fixture(), current_score=0, line=9.5) is None


@pytest.mark.asyncio
async def test_quote_timeout_returns_none():
    """Cliente real esgotando retries em timeout."""
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("simulated", request=request)

    real_client = _client_with_transport(handler)
    adapter = BetanoBridgeOddsAdapter(
        client=real_client, fixture_repo=_FakeRepo({100: "84592546"})
    )

    res = await adapter.get_corners(_fixture(), current_score=0, line=9.5)
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

    res = await adapter.get_corners(_fixture(), current_score=0, line=9.5)
    assert res is None
    await real_client.close()


@pytest.mark.asyncio
async def test_fixture_without_betano_event_id_returns_none_no_http():
    """Sem mapeamento → adapter não chama HTTP."""
    client = _FakeClient()  # sem responses, qualquer call falharia
    adapter = BetanoBridgeOddsAdapter(
        client=client, fixture_repo=_FakeRepo({})  # vazio
    )

    res = await adapter.get_corners(_fixture(), current_score=0, line=9.5)
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

        async def get_corners(self, fixture, current_score, line):
            return CanonicalOverUnder(
                source="apifootball", market_kind="corners", market_code="",
                linha=10.5, odd_over=1.92, odd_under=1.88,
            )

        async def get_cards(self, fixture, current_score, line):
            return None

        async def healthcheck(self):
            return True

    af = _StubAF()
    composite = CompositeOddsProvider([bridge, af])

    res = await composite.get_corners(_fixture(), current_score=0, line=9.5)
    assert res is not None
    assert res.source == "apifootball"
    assert res.linha == 10.5


# ─── Testes novos da Fase 3: line negociável ───────────────────────


@pytest.mark.asyncio
async def test_bridge_get_corners_uses_provided_line():
    """Engine passa line=5.5 (Liga MX) — bridge recebe exatamente 5.5, não 9.5."""
    client = _FakeClient(responses={
        ("corners_over_under", "over"): _ok_payload("over", line=5.5),
        ("corners_over_under", "under"): _ok_payload("under", line=5.5),
    })
    adapter = BetanoBridgeOddsAdapter(
        client=client, fixture_repo=_FakeRepo({100: "84592546"})
    )

    res = await adapter.get_corners(_fixture(), current_score=0, line=5.5)

    assert res is not None
    assert res.linha == 5.5
    assert all(c["line"] == 5.5 for c in client.calls)
    # Garante que NÃO usou 9.5 hardcoded
    assert not any(c["line"] == 9.5 for c in client.calls)


@pytest.mark.asyncio
async def test_bridge_get_corners_line_unavailable_returns_none():
    """Engine pede line=99.5 (inexistente) → bridge 404 → adapter retorna None."""
    client = _FakeClient(raises=BridgeMarketNotFound("line=99.5 not offered"))
    adapter = BetanoBridgeOddsAdapter(
        client=client, fixture_repo=_FakeRepo({100: "84592546"})
    )

    res = await adapter.get_corners(_fixture(), current_score=0, line=99.5)
    assert res is None


# ─── Testes novos da Fase 2a: line=None consome catálogo /markets ───


@pytest.mark.asyncio
async def test_get_corners_with_line_none_calls_markets_not_quote():
    """line=None → adapter chama client.markets(), nunca client.quote()."""
    client = _FakeClient(catalog=[_line(9.5, 1.60, 2.30)])
    adapter = BetanoBridgeOddsAdapter(
        client=client, fixture_repo=_FakeRepo({100: "84592546"})
    )

    res = await adapter.get_corners(_fixture(), current_score=0)  # line omitido (None)

    assert res is not None
    assert len(client.markets_calls) == 1
    assert client.markets_calls[0]["market"] == "corners_over_under"
    assert client.calls == []  # quote NUNCA chamado


@pytest.mark.asyncio
async def test_get_corners_with_line_none_picks_central_when_in_range():
    """Catálogo com over 1.20/1.60/1.85/2.50 → escolhe 1.60 (centro da faixa 1.50-1.70)."""
    client = _FakeClient(catalog=[
        _line(12.5, 1.20, 4.50),
        _line(9.5, 1.60, 2.30),
        _line(8.5, 1.85, 1.95),
        _line(6.5, 2.50, 1.50),
    ])
    adapter = BetanoBridgeOddsAdapter(
        client=client, fixture_repo=_FakeRepo({100: "84592546"})
    )

    res = await adapter.get_corners(_fixture(), current_score=0)

    assert res is not None
    assert res.source == "betano_bridge"
    assert res.linha == 9.5
    assert res.odd_over == 1.60
    assert res.odd_under == 2.30


@pytest.mark.asyncio
async def test_get_corners_with_line_none_picks_closest_to_center_in_range():
    """Catálogo com over 1.51/1.59/1.68 (todas na faixa) → escolhe 1.59 (mais perto de 1.60)."""
    client = _FakeClient(catalog=[
        _line(10.5, 1.51, 2.40),
        _line(9.5, 1.59, 2.25),
        _line(8.5, 1.68, 2.10),
    ])
    adapter = BetanoBridgeOddsAdapter(
        client=client, fixture_repo=_FakeRepo({100: "84592546"})
    )

    res = await adapter.get_corners(_fixture(), current_score=0)

    assert res is not None
    assert res.odd_over == 1.59
    assert res.linha == 9.5


@pytest.mark.asyncio
async def test_get_corners_with_line_none_picks_closest_when_no_odd_in_range():
    """Catálogo sem nenhuma odd na faixa 1.50-1.70 → degrada pra mais perto do centro.

    over 1.20/1.30/1.85/2.50; distâncias de 1.60: 0.40/0.30/0.25/0.90 → escolhe 1.85.
    """
    client = _FakeClient(catalog=[
        _line(14.5, 1.20, 4.50),
        _line(12.5, 1.30, 3.50),
        _line(8.5, 1.85, 1.95),
        _line(6.5, 2.50, 1.50),
    ])
    adapter = BetanoBridgeOddsAdapter(
        client=client, fixture_repo=_FakeRepo({100: "84592546"})
    )

    res = await adapter.get_corners(_fixture(), current_score=0)

    assert res is not None
    assert res.odd_over == 1.85  # degradado: mais próximo de 1.60 fora da faixa
    assert res.linha == 8.5


@pytest.mark.asyncio
async def test_get_corners_with_line_none_returns_none_when_catalog_empty():
    """Catálogo vazio → adapter retorna None (Composite cai pro fallback)."""
    client = _FakeClient(catalog=[])
    adapter = BetanoBridgeOddsAdapter(
        client=client, fixture_repo=_FakeRepo({100: "84592546"})
    )

    res = await adapter.get_corners(_fixture(), current_score=0)
    assert res is None


@pytest.mark.asyncio
async def test_get_corners_with_specific_line_uses_quote_not_markets():
    """line=X (float) → preserva comportamento Fase 3: chama quote, nunca markets."""
    client = _FakeClient(responses={
        ("corners_over_under", "over"): _ok_payload("over", line=5.5),
        ("corners_over_under", "under"): _ok_payload("under", line=5.5),
    })
    adapter = BetanoBridgeOddsAdapter(
        client=client, fixture_repo=_FakeRepo({100: "84592546"})
    )

    res = await adapter.get_corners(_fixture(), current_score=0, line=5.5)

    assert res is not None
    assert res.linha == 5.5
    assert len(client.calls) == 2  # quote: over + under
    assert client.markets_calls == []  # markets NUNCA chamado


@pytest.mark.asyncio
async def test_pick_central_line_empty_returns_none():
    """_pick_central_line com lista vazia → (None, False)."""
    adapter = BetanoBridgeOddsAdapter(client=_FakeClient())
    chosen, in_range = adapter._pick_central_line([])
    assert chosen is None
    assert in_range is False
