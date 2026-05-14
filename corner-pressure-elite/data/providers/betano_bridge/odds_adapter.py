"""Adapter `OddsProvider` para o bridge Betano local.

Resolve `betano_event_id` por:
1. Cache local em memória.
2. `fixture_repo.get_betano_event_id(fixture_id)` (Fase D).
Sem `fixture_repo` configurado e sem cache → devolve `None` e o
`CompositeOddsProvider` cai pro próximo provider (APIFootball).

Modos de operação (Fase 2a):
- `line=None`  → consome o catálogo completo via `/markets` e escolhe a
  linha central pela política `_pick_central_line` (faixa de odds
  preferida + degradação pra mais próxima do centro).
- `line=X`     → consulta exatamente a linha X via `/quote` (Fase 3).

Convenções:
- Captura toda exceção do client no boundary e devolve `None`
  (segue padrão de `APIFootballOddsProvider`).
"""
from __future__ import annotations

import asyncio
import logging
import time
from typing import Optional

from data.odds_provider import CanonicalFixture, CanonicalOverUnder
from data.providers.betano_bridge.client import BetanoBridgeClient
from data.providers.betano_bridge.exceptions import (
    BridgeMarketNotFound,
    BridgeTimeout,
    BridgeUnavailable,
)

log = logging.getLogger("cpes.providers.betano_bridge.odds")


class BetanoBridgeOddsAdapter:
    """Implementa `OddsProvider` consumindo o bridge HTTP local."""

    name = "betano_bridge"

    def __init__(
        self,
        client: BetanoBridgeClient,
        fixture_repo=None,
        min_score: int = 0,
        odd_min: float = 1.50,
        odd_max: float = 1.70,
    ):
        self._client = client
        self._fixture_repo = fixture_repo
        self._min_score = int(min_score)
        self._odd_min = float(odd_min)
        self._odd_max = float(odd_max)
        self._event_id_cache: dict[int, str] = {}

    async def get_corners(
        self, fixture: CanonicalFixture, current_score: int,
        line: Optional[float] = None,
    ) -> Optional[CanonicalOverUnder]:
        return await self._get_market(fixture, current_score, line, "corners_over_under", "corners")

    async def get_cards(
        self, fixture: CanonicalFixture, current_score: int,
        line: Optional[float] = None,
    ) -> Optional[CanonicalOverUnder]:
        return await self._get_market(fixture, current_score, line, "cards_over_under", "cards")

    async def healthcheck(self) -> bool:
        try:
            data = await self._client.health()
        except Exception as e:  # fronteira: HTTP
            log.warning("betano_bridge.healthcheck.error err=%s", e)
            return False
        return bool(data.get("chrome_connected"))

    # ---- política de seleção de linha ----

    def _pick_central_line(self, lines: list) -> tuple[Optional[dict], bool]:
        """Escolhe a linha central pela faixa de odds preferida.

        Retorna `(linha_escolhida_ou_None, in_preferred_range)`:
        - há linha com `over_price` em [odd_min, odd_max] → a mais próxima
          do centro da faixa, `in_preferred_range=True`.
        - nenhuma na faixa → a mais próxima do centro mesmo fora,
          `in_preferred_range=False` (degradado — melhor que cair pro AF).
        - lista vazia → `(None, False)`.
        """
        if not lines:
            return None, False

        center = (self._odd_min + self._odd_max) / 2
        in_range = [
            l for l in lines
            if self._odd_min <= l["over_price"] <= self._odd_max
        ]
        if in_range:
            chosen = min(in_range, key=lambda l: abs(l["over_price"] - center))
            return chosen, True

        chosen = min(lines, key=lambda l: abs(l["over_price"] - center))
        return chosen, False

    # ---- helpers ----

    async def _get_market(
        self,
        fixture: CanonicalFixture,
        current_score: int,
        line: Optional[float],
        bridge_market: str,
        market_kind: str,
    ) -> Optional[CanonicalOverUnder]:
        if current_score < self._min_score:
            return None
        if line is not None and line <= 0:
            log.debug(
                "betano_bridge.invalid_line fixture=%d market=%s line=%s",
                fixture.fixture_id, market_kind, line,
            )
            return None

        event_id = await self._resolve_event_id(fixture)
        if not event_id:
            log.debug(
                "betano_bridge.no_event_id fixture=%d market=%s",
                fixture.fixture_id, market_kind,
            )
            return None

        if line is None:
            return await self._from_catalog(event_id, bridge_market, market_kind)
        return await self._from_quote(event_id, line, bridge_market, market_kind)

    async def _from_quote(
        self, event_id: str, line: float, bridge_market: str, market_kind: str
    ) -> Optional[CanonicalOverUnder]:
        """Caminho line=X (Fase 3): consulta over+under da linha específica."""
        t0 = time.perf_counter()
        try:
            over, under = await asyncio.gather(
                self._client.quote(event_id, bridge_market, line, side="over"),
                self._client.quote(event_id, bridge_market, line, side="under"),
            )
        except BridgeMarketNotFound as e:
            log.debug(
                "betano_bridge.market_not_found event_id=%s market=%s line=%s err=%s",
                event_id, market_kind, line, e,
            )
            return None
        except BridgeTimeout as e:
            log.warning(
                "betano_bridge.timeout event_id=%s market=%s err=%s",
                event_id, market_kind, e,
            )
            return None
        except BridgeUnavailable as e:
            log.warning(
                "betano_bridge.unavailable event_id=%s market=%s err=%s",
                event_id, market_kind, e,
            )
            return None
        except Exception as e:  # fronteira: erro inesperado do client
            log.exception(
                "betano_bridge.unexpected event_id=%s market=%s err=%s",
                event_id, market_kind, e,
            )
            return None

        elapsed = round(time.perf_counter() - t0, 2)
        log.info(
            "betano_bridge.ok event_id=%s market=%s line=%s over=%s under=%s elapsed=%ss",
            event_id, market_kind, line, over.get("odd"), under.get("odd"), elapsed,
        )

        try:
            odd_over = float(over["odd"])
            odd_under = float(under["odd"])
            line_found = float(over.get("line_found") or line)
        except (KeyError, TypeError, ValueError):
            log.warning(
                "betano_bridge.parse_error event_id=%s market=%s",
                event_id, market_kind,
            )
            return None

        if odd_over <= 0 or odd_under <= 0 or line_found <= 0:
            return None

        return CanonicalOverUnder(
            source=self.name,
            market_kind=market_kind,
            market_code="",
            linha=line_found,
            odd_over=odd_over,
            odd_under=odd_under,
        )

    async def _from_catalog(
        self, event_id: str, bridge_market: str, market_kind: str
    ) -> Optional[CanonicalOverUnder]:
        """Caminho line=None: consome /markets e escolhe linha central."""
        t0 = time.perf_counter()
        try:
            catalog = await self._client.markets(event_id, bridge_market)
        except BridgeMarketNotFound as e:
            log.debug(
                "betano_bridge.catalog_empty event_id=%s market=%s err=%s",
                event_id, market_kind, e,
            )
            return None
        except BridgeTimeout as e:
            log.warning(
                "betano_bridge.timeout event_id=%s market=%s err=%s",
                event_id, market_kind, e,
            )
            return None
        except BridgeUnavailable as e:
            log.warning(
                "betano_bridge.unavailable event_id=%s market=%s err=%s",
                event_id, market_kind, e,
            )
            return None
        except Exception as e:  # fronteira: erro inesperado do client
            log.exception(
                "betano_bridge.unexpected event_id=%s market=%s err=%s",
                event_id, market_kind, e,
            )
            return None

        elapsed = round(time.perf_counter() - t0, 2)
        lines = catalog.get("lines") or []
        chosen, in_range = self._pick_central_line(lines)
        if chosen is None:
            log.debug(
                "betano_bridge.catalog_no_lines event_id=%s market=%s",
                event_id, market_kind,
            )
            return None

        if in_range:
            log.info(
                "betano_bridge.line_selected event_id=%s market=%s chosen_line=%s "
                "chosen_odd=%s in_preferred_range=true elapsed=%ss",
                event_id, market_kind, chosen["line"], chosen["over_price"], elapsed,
            )
        else:
            log.warning(
                "betano_bridge.line_degraded event_id=%s market=%s chosen_line=%s "
                "chosen_odd=%s available_lines=%s preferred_range=[%s,%s] elapsed=%ss",
                event_id, market_kind, chosen["line"], chosen["over_price"],
                [l["line"] for l in lines], self._odd_min, self._odd_max, elapsed,
            )

        try:
            odd_over = float(chosen["over_price"])
            odd_under = float(chosen["under_price"])
            linha = float(chosen["line"])
        except (KeyError, TypeError, ValueError):
            log.warning(
                "betano_bridge.parse_error event_id=%s market=%s",
                event_id, market_kind,
            )
            return None

        if odd_over <= 0 or odd_under <= 0 or linha <= 0:
            return None

        return CanonicalOverUnder(
            source=self.name,
            market_kind=market_kind,
            market_code="",
            linha=linha,
            odd_over=odd_over,
            odd_under=odd_under,
        )

    async def _resolve_event_id(self, fixture: CanonicalFixture) -> Optional[str]:
        cached = self._event_id_cache.get(fixture.fixture_id)
        if cached:
            return cached

        if self._fixture_repo is None:
            return None

        try:
            ev = await self._fixture_repo.get_betano_event_id(fixture.fixture_id)
        except Exception as e:  # fronteira: DB
            log.warning(
                "betano_bridge.fixture_repo.error fixture=%d err=%s",
                fixture.fixture_id, e,
            )
            return None

        if not ev:
            return None

        ev_str = str(ev)
        self._event_id_cache[fixture.fixture_id] = ev_str
        return ev_str
