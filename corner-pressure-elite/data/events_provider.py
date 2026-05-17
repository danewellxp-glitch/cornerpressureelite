"""Abstração canônica de provider de eventos + Composite com cascata (Fase F).

Espelha `stats_provider.py` (Fase E.1). `CanonicalEvent` traz o subset mínimo
de um incidente individual (tipo, minuto, lado, player) + raw preservado.

Política de fonte:
- **bridge_betano** (primary) — extrai `event.incidents[]` do
  `/danae-webapi/api/live/events/<id>/latest` via bridge.
- **apifootball** (fallback) — `GET /fixtures/events` da AF, normaliza
  type+detail pra type canônico.

Tipos canônicos (do doc E.0 `betano-stats-api.md §1.4`):

| Type | Significado |
|---|---|
| GOAL | Gol |
| YELL | Cartão amarelo |
| RCRD | Cartão vermelho |
| CRNR | Escanteio |
| OFFS | Impedimento |
| SUBS | Substituição |
| PENL | Pênalti marcado (não-gol) |
| PBEG | Início de tempo |
| PEND | Fim de tempo |
| EBEG | Início de partida |
| StoppageTime | Acréscimos |
| Aggregated | Janela agregada (10min) |
| VAR | Var (não visto Betano, mas AF traz) |
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Optional, Protocol, runtime_checkable

log = logging.getLogger("cpes.providers.events")


@dataclass(frozen=True)
class CanonicalEvent:
    """Evento individual normalizado de qualquer provider."""

    fixture_id: int
    source: str                  # 'bridge_betano' | 'apifootball'
    event_type: str              # 'GOAL' | 'YELL' | 'CRNR' | ...
    event_minute: int            # minuto do incidente (0..120+)
    event_second: Optional[int] = None       # opcional (Betano clock granular)
    team_side: Optional[str] = None          # 'home' | 'away' | None
    player_name: Optional[str] = None        # opcional
    props: dict = field(default_factory=dict)   # campos específicos do provider
    raw: dict = field(default_factory=dict)     # incident original preservado


@runtime_checkable
class EventsProvider(Protocol):
    name: str

    async def get_events(
        self,
        fixture_id: int,
        *,
        betano_event_id: Optional[int] = None,
        home_team_id: Optional[int] = None,
    ) -> Optional[list[CanonicalEvent]]:
        """Retorna lista de eventos do fixture.

        Args:
            fixture_id: ID canônico do fixture (API-Football).
            betano_event_id: Hint pré-resolvido pra bridge Betano evitar
                lookup no `fixture_repo`. AF ignora.
            home_team_id: Hint pra adapters AF resolverem `team_side` via
                `team.id`. Bridge Betano ignora — `teamSide` já vem 0/1.

        Retorno:
        - `list[CanonicalEvent]` (possivelmente vazia) quando provider OK.
        - `None` quando provider falhou (erro de rede, sem mapping, etc) —
          caller decide se faz fallback.
        """
        ...

    async def healthcheck(self) -> bool: ...


class CompositeEventsProvider:
    """Cascata sequencial: tenta cada provider em ordem, retorna o 1º não-None.

    Mesma semântica do `CompositeStatsProvider` (Fase E.1). Erros e None
    em providers anteriores acionam fallback transparente. Quando todos
    falham → retorna None.
    """

    name = "composite_events"

    def __init__(self, providers: list[EventsProvider]):
        if not providers:
            raise ValueError("CompositeEventsProvider precisa de >=1 provider")
        self._providers = list(providers)

    async def get_events(
        self,
        fixture_id: int,
        *,
        betano_event_id: Optional[int] = None,
        home_team_id: Optional[int] = None,
    ) -> Optional[list[CanonicalEvent]]:
        for p in self._providers:
            try:
                events = await p.get_events(
                    fixture_id,
                    betano_event_id=betano_event_id,
                    home_team_id=home_team_id,
                )
            except Exception as e:
                log.warning(
                    "composite_events.%s.error fixture=%d err=%s",
                    p.name, fixture_id, e,
                )
                continue
            if events is None:
                continue
            # [] = sucesso (provider respondeu, sem eventos novos). Não cai
            # pra fallback. Log INFO ajuda analytics futuro detectar pattern
            # (ex: Betano persistentemente vazio quando devia ter eventos).
            if not events:
                log.info(
                    "composite_events.empty source=%s fixture=%d",
                    p.name, fixture_id,
                )
            else:
                log.debug(
                    "composite_events.hit provider=%s fixture=%d count=%d",
                    p.name, fixture_id, len(events),
                )
            return events
        return None

    async def healthcheck(self) -> bool:
        for p in self._providers:
            try:
                if await p.healthcheck():
                    return True
            except Exception:
                log.exception("composite_events.healthcheck.error name=%s", p.name)
        return False
