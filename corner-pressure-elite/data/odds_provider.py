"""Abstração canônica de provider de odds + Composite com cascata.

Princípios:
- Caller fala apenas com `CompositeOddsProvider`; cascata e drift ficam aqui.
- Adapters concretos (`APIFootballOddsProvider`, `BetanoOddsProvider`)
  implementam o `Protocol` `OddsProvider`.
- Sem exceções no caminho crítico: cada provider trata seus erros e devolve
  `None`; só excepcionalmente o composite captura `Exception` e loga.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional, Protocol, runtime_checkable

log = logging.getLogger("cpes.providers.odds")

DRIFT_LOG_PATH = Path("logs/provider_drift.jsonl")


@dataclass(frozen=True)
class CanonicalFixture:
    """Identificação mínima de uma partida para os providers."""
    fixture_id: int
    home_team: str
    away_team: str
    league_id: int
    starts_at_utc: datetime
    score_home: int = 0
    score_away: int = 0


@dataclass(frozen=True)
class CanonicalOverUnder:
    """Resposta normalizada de qualquer provider para mercados Over/Under."""
    source: str           # "betano" | "apifootball"
    market_kind: str      # "corners" | "cards"
    market_code: str      # "CNOU", "TCOU", "" (vazio para AF)
    linha: float
    odd_over: float
    odd_under: float


@runtime_checkable
class OddsProvider(Protocol):
    name: str

    async def get_corners(
        self, fixture: CanonicalFixture, current_score: int, line: float
    ) -> Optional[CanonicalOverUnder]: ...

    async def get_cards(
        self, fixture: CanonicalFixture, current_score: int, line: float
    ) -> Optional[CanonicalOverUnder]: ...

    async def healthcheck(self) -> bool: ...


class CompositeOddsProvider:
    """Tenta cada provider em ordem; primeiro com resultado vence.

    Se `drift_check=True`, **todos** os providers são chamados em paralelo
    lógico (sequencial mas sem early-return), e divergências de linha/odd são
    logadas em `logs/provider_drift.jsonl`.

    `persistence_worker` (opcional) recebe o resultado primary para gravar em
    `odds_history` — usado na Fase D.
    """
    name = "composite"

    def __init__(
        self,
        providers: list[OddsProvider],
        drift_check: bool = False,
        persistence_worker: Any = None,
    ):
        self._providers = list(providers)
        self._drift_check = drift_check
        self._persistence = persistence_worker

    async def get_corners(
        self, fixture: CanonicalFixture, current_score: int, line: float
    ) -> Optional[CanonicalOverUnder]:
        return await self._dispatch("get_corners", fixture, current_score, line, "corners")

    async def get_cards(
        self, fixture: CanonicalFixture, current_score: int, line: float
    ) -> Optional[CanonicalOverUnder]:
        return await self._dispatch("get_cards", fixture, current_score, line, "cards")

    async def healthcheck(self) -> bool:
        for p in self._providers:
            try:
                if await p.healthcheck():
                    return True
            except Exception:  # fronteira: log e segue para o próximo
                log.exception("composite.healthcheck.provider_error name=%s", p.name)
        return False

    async def _dispatch(
        self, method: str, fixture: CanonicalFixture, score: int, line: float, market_kind: str
    ) -> Optional[CanonicalOverUnder]:
        results: list[tuple[str, Optional[CanonicalOverUnder]]] = []
        for p in self._providers:
            try:
                r = await getattr(p, method)(fixture, score, line)
            except Exception as e:  # fronteira: provider externo
                log.warning(
                    "composite.%s.%s.error fixture=%d line=%s err=%s",
                    p.name, method, fixture.fixture_id, line, e,
                )
                r = None
            results.append((p.name, r))
            if r is not None and not self._drift_check:
                # short-circuit no modo normal
                break

        primary = next((r for _, r in results if r is not None), None)

        if self._drift_check and sum(1 for _, r in results if r is not None) >= 2:
            try:
                _log_drift(market_kind, fixture.fixture_id, results)
            except Exception:
                log.exception("composite.drift_log.error")

        if primary is not None and self._persistence is not None:
            try:
                self._persistence.enqueue_from_dispatch(
                    fixture=fixture,
                    market_kind=market_kind,
                    primary=primary,
                    all_results=results,
                )
            except Exception:
                log.exception("composite.persistence.enqueue_error")

        return primary


def _log_drift(
    market_kind: str,
    fixture_id: int,
    results: list[tuple[str, Optional[CanonicalOverUnder]]],
) -> None:
    entry = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "fixture_id": fixture_id,
        "market_kind": market_kind,
        "providers": [
            {
                "name": name,
                "linha": r.linha if r else None,
                "odd_over": r.odd_over if r else None,
                "odd_under": r.odd_under if r else None,
                "market_code": r.market_code if r else None,
            }
            for name, r in results
        ],
    }
    DRIFT_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with DRIFT_LOG_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
