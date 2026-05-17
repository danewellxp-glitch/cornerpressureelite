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
from dataclasses import dataclass, field, replace
from datetime import date
from typing import Optional, Protocol, runtime_checkable

log = logging.getLogger("cpes.providers.lineups")


# Campos que Betano NÃO cobre.
# - coach_name: gap original G.0 (técnico não vem em event.roster).
# - missing_players: gap novo K.0 (lesões/suspensões não vêm em event.roster
#   nem em qualquer payload Betano testado).
# Composite usa pra enriquecer via SofaScore quando disponível (K.1+).
BETANO_GAPS_LINEUPS: frozenset[str] = frozenset({
    "coach_name",
    "missing_players",
})


@dataclass(frozen=True)
class MissingPlayer:
    """Jogador ausente do jogo (lesão / suspensão / dúvida).

    Origem: SofaScore `lineups.{side}.missingPlayers[]` (K.0) — Betano não
    cobre. AF cobre parcialmente via `/injuries`.
    """

    player_id: Optional[int]
    name: str
    # categoria humana: 'injury' | 'suspension' | 'doubtful' | 'unknown'
    reason: Optional[str] = None
    # código numérico da fonte (auditoria — SofaScore: int 1..N).
    reason_code: Optional[int] = None
    expected_return: Optional[date] = None
    # 'sofascore' | 'apifootball' (de onde veio o registro).
    source: str = ""


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
    # Lesões / suspensões / dúvidas (K.0: gap Betano, preenchido por SofaScore).
    # Sempre `[]` quando `source='bridge_betano'`.
    missing_players: list[MissingPlayer] = field(default_factory=list)
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
        home_team_id: Optional[int] = None,
    ) -> Optional[list[CanonicalLineup]]:
        """Retorna lineups do fixture.

        Args:
            fixture_id: ID canônico (API-Football).
            betano_event_id: Hint pra bridge — evita lookup no `fixture_repo`.
            home_team_id: Hint pra AF resolver `team_side` via `team.id`
                (AF response não vem ordenado de forma confiável). Bridge
                Betano ignora — `teamSide` já vem do payload.

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

    K.1 PARTE B.7: quando `enricher` injetado, lineups do primary com
    `coach_name=None` e/ou `missing_players=[]` (BETANO_GAPS_LINEUPS) são
    enriquecidos via chamada paralela ao enricher (SofaScore). Falha do
    enrichment NÃO derruba primary.
    """

    name = "composite_lineups"

    def __init__(
        self,
        providers: list[LineupsProvider],
        *,
        enricher: Optional[LineupsProvider] = None,
        enable_enrichment: bool = True,
    ):
        if not providers:
            raise ValueError("CompositeLineupsProvider precisa de >=1 provider")
        self._providers = list(providers)
        self._enricher = enricher
        self._enable_enrichment = enable_enrichment

    async def get_lineups(
        self,
        fixture_id: int,
        *,
        betano_event_id: Optional[int] = None,
        home_team_id: Optional[int] = None,
    ) -> Optional[list[CanonicalLineup]]:
        for p in self._providers:
            try:
                lineups = await p.get_lineups(
                    fixture_id,
                    betano_event_id=betano_event_id,
                    home_team_id=home_team_id,
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
            # AJUSTE 4b — log WARNING quando cobertura PARCIAL (1 lado OK, outro vazio).
            has_home = (
                len(lineups) > 0
                and lineups[0].team_side == "home"
                and lineups[0].has_starting_eleven
            )
            has_away = (
                len(lineups) > 1
                and lineups[1].team_side == "away"
                and lineups[1].has_starting_eleven
            )
            if has_home != has_away:
                log.warning(
                    "lineups.partial_coverage source=%s fixture=%d home_ok=%s away_ok=%s",
                    p.name, fixture_id, has_home, has_away,
                )
            log.debug(
                "composite_lineups.hit provider=%s fixture=%d sides=%d",
                p.name, fixture_id, len(lineups),
            )
            # Enrichment opcional: coach + missing_players (BETANO_GAPS_LINEUPS).
            if (
                self._enable_enrichment
                and self._enricher is not None
                and p.name != self._enricher.name
            ):
                lineups = await self._try_enrich(
                    lineups, fixture_id,
                    betano_event_id=betano_event_id,
                    home_team_id=home_team_id,
                )
            return lineups
        return None

    async def _try_enrich(
        self,
        primary_lineups: list[CanonicalLineup],
        fixture_id: int,
        *,
        betano_event_id: Optional[int] = None,
        home_team_id: Optional[int] = None,
    ) -> list[CanonicalLineup]:
        """Enriquece coach_name + missing_players via enricher se primary tem gaps."""
        needs_coach = any(ln.coach_name is None for ln in primary_lineups)
        needs_missing = any(not ln.missing_players for ln in primary_lineups)
        if not (needs_coach or needs_missing):
            return primary_lineups

        try:
            enricher_lineups = await self._enricher.get_lineups(
                fixture_id,
                betano_event_id=betano_event_id,
                home_team_id=home_team_id,
            )
        except Exception as e:
            log.debug(
                "composite_lineups.enrichment.failed fixture=%d err=%s",
                fixture_id, e,
            )
            return primary_lineups
        if not enricher_lineups:
            return primary_lineups

        by_side = {ln.team_side: ln for ln in enricher_lineups}
        merged: list[CanonicalLineup] = []
        any_change = False
        for ln in primary_lineups:
            side_match = by_side.get(ln.team_side)
            if side_match is None:
                merged.append(ln)
                continue
            kwargs: dict = {}
            if ln.coach_name is None and side_match.coach_name:
                kwargs["coach_name"] = side_match.coach_name
            if not ln.missing_players and side_match.missing_players:
                kwargs["missing_players"] = list(side_match.missing_players)
            if kwargs:
                any_change = True
                merged.append(replace(ln, **kwargs))
            else:
                merged.append(ln)

        if any_change:
            log.debug(
                "composite_lineups.enriched fixture=%d enricher=%s sides=%d",
                fixture_id, self._enricher.name, len(merged),
            )
        return merged

    async def healthcheck(self) -> bool:
        for p in self._providers:
            try:
                if await p.healthcheck():
                    return True
            except Exception:
                log.exception("composite_lineups.healthcheck.error name=%s", p.name)
        return False
