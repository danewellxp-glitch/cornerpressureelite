"""Abstração canônica de provider de lineups + Composite (Fase G.1).

Espelha `events_provider.py` (Fase F) e `stats_provider.py` (Fase E.1).
`CanonicalLineup` traz lineup de UM lado do fixture (home OU away). Worker
chama `get_lineups(fixture)` e recebe lista de 2 itens (home + away) quando
disponível.

# Política de fonte (CASO α puro — G.0 confirmou)

- **bridge_betano** (primary) — extrai `event.roster` do payload
  `/event/<id>/state` que `BridgeStatsAdapter` (E.1) já busca a cada poll.
  ZERO nova request HTTP.
- **apifootball** (fallback) — `GET /fixtures/lineups` da AF, normaliza
  formation + startXI + substitutes + coach.

# Gap Betano: coach (técnico)

`BETANO_GAPS_LINEUPS` documenta o gap. `coach_name` fica `None` quando
provider é `bridge_betano`. Quando Composite cai pra AF, `coach_name` é
preenchido. Workers/consumers downstream tratam `None` graciosamente.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Optional, Protocol, runtime_checkable

log = logging.getLogger("cpes.providers.lineups")


# Campos que Betano NÃO cobre (ver doc G.0 betano-lineups-api.md §2).
# Documentação explícita pro Composite + downstream saberem o que esperar.
BETANO_GAPS_LINEUPS: frozenset[str] = frozenset({
    "coach_name",
})


@dataclass(frozen=True)
class PlayerEntry:
    """Player individual numa lineup."""

    name: str                                      # sempre presente
    player_id: Optional[int] = None                # None pra unknownPlayers Betano (UUID local)
    position: Optional[str] = None                 # 'GK' | 'DF' | 'MF' | 'FW' | outro
    position_display: Optional[str] = None         # localizado (pt-BR no Betano)
    shirt_number: Optional[int] = None
    is_substitute: bool = False


@dataclass(frozen=True)
class CanonicalLineup:
    """Lineup canônica de UM lado (home OU away) de UM fixture."""

    fixture_id: int
    source: str                                    # 'bridge_betano' | 'apifootball'
    team_side: str                                 # 'home' | 'away'
    formation: Optional[str] = None                # "4-3-3", "5-4-1", etc — None se cobertura zero
    coach_name: Optional[str] = None               # gap Betano (sempre None pra bridge)
    starting_eleven: list[PlayerEntry] = field(default_factory=list)
    substitutes: list[PlayerEntry] = field(default_factory=list)
    tactical_grid: Optional[list[list[int]]] = None  # Betano lineup[][] (player_ids por linha)
    version: Optional[int] = None
    raw: dict = field(default_factory=dict)

    @property
    def has_starting_eleven(self) -> bool:
        """True se starting_eleven tem >=1 player. Usado pelo Composite pra
        decidir fallback (Betano cobertura zero → AF assume)."""
        return len(self.starting_eleven) > 0


@runtime_checkable
class LineupsProvider(Protocol):
    name: str

    async def get_lineups(
        self,
        fixture_id: int,
        *,
        betano_event_id: Optional[int] = None,
    ) -> Optional[list[CanonicalLineup]]:
        """Retorna lineups do fixture.

        Args:
            fixture_id: ID canônico (API-Football).
            betano_event_id: Hint pra bridge — evita lookup no `fixture_repo`.

        Retorno:
        - `list[CanonicalLineup]` com 2 itens (home + away) quando provider OK.
          Pode ter `formation=None` + `starting_eleven=[]` se cobertura zero
          (caller decide se vale persistir snapshot vazio ou fallback).
        - `list[CanonicalLineup]` com 1 item se provider só conseguiu 1 lado.
        - `None` quando provider falhou (erro de rede, sem mapping, etc).
        """
        ...

    async def healthcheck(self) -> bool: ...


class CompositeLineupsProvider:
    """Cascata: primary → fallback se primary devolve None OU se primary
    devolve lineups sem `starting_eleven` (cobertura zero da liga no Betano).

    Diferente do `CompositeEventsProvider`: lá `[]` = sucesso. Aqui lineups
    sem starting_eleven = cobertura zero, cai pra fallback. Coach faltando
    NÃO aciona fallback (gap conhecido).
    """

    name = "composite_lineups"

    def __init__(self, providers: list[LineupsProvider]):
        if not providers:
            raise ValueError("CompositeLineupsProvider precisa de >=1 provider")
        self._providers = list(providers)

    async def get_lineups(
        self,
        fixture_id: int,
        *,
        betano_event_id: Optional[int] = None,
    ) -> Optional[list[CanonicalLineup]]:
        for p in self._providers:
            try:
                lineups = await p.get_lineups(
                    fixture_id, betano_event_id=betano_event_id,
                )
            except Exception as e:
                log.warning(
                    "composite_lineups.%s.error fixture=%d err=%s",
                    p.name, fixture_id, e,
                )
                continue
            if lineups is None:
                continue
            # Cobertura zero detectada? (nenhum lado tem starting_eleven)
            has_any_starting = any(ln.has_starting_eleven for ln in lineups)
            if not has_any_starting:
                log.info(
                    "composite_lineups.zero_coverage source=%s fixture=%d — falling back",
                    p.name, fixture_id,
                )
                continue
            log.debug(
                "composite_lineups.hit provider=%s fixture=%d sides=%d",
                p.name, fixture_id, len(lineups),
            )
            return lineups
        return None

    async def healthcheck(self) -> bool:
        for p in self._providers:
            try:
                if await p.healthcheck():
                    return True
            except Exception:
                log.exception("composite_lineups.healthcheck.error name=%s", p.name)
        return False
