"""Abstração canônica de provider de stats + Composite com cascata.

Espelha `odds_provider.py`. `CanonicalStats` traz o subset que o orquestrador
precisa: placar, escanteios, cartões, shots, posse, xG e (Fase B+)
`provider_pressure` vindo do momentum da Opta.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field, replace
from typing import Optional, Protocol, runtime_checkable

from .odds_provider import CanonicalFixture

log = logging.getLogger("cpes.providers.stats")


# Campos que Betano NÃO cobre via `event.roster` / `event.statistics` (gaps
# conhecidos da fonte). Composite usa pra enriquecer com SofaScore quando
# Betano primary é o sucesso. `shots_on_target_home/away` está aqui mesmo
# sendo `int` (não Optional) — detecção via heurística especial em
# `_is_betano_gap_field` porque Betano preenche 0 (não None) nessas keys.
BETANO_GAPS_STATS: frozenset[str] = frozenset({
    "shots_on_target_home",
    "shots_on_target_away",
    "shots_off_target_home",
    "shots_off_target_away",
    "blocked_shots_home",
    "blocked_shots_away",
    "big_chances_home",
    "big_chances_away",
    "big_chances_missed_home",
    "big_chances_missed_away",
    "stats_1h",
    "stats_2h",
})


@dataclass(frozen=True)
class CanonicalStats:
    """Snapshot canônico de stats de 1 fixture, agregado por StatsProvider.

    **Campos GARANTIDOS** (todo provider sempre preenche; nunca None):
        fixture_id, source, minute, score_home/away, corners_home/away,
        yellow_cards_home/away, red_cards_home/away, shots_on_target_home/away,
        dangerous_attacks_home/away, possession_home/away, x_goals_home/away.

        Quando a fonte não cobre uma métrica, o adapter preenche `0`/`0.0`
        (conforme `score_engine` e `cards_score_engine` já lidam com zero).

    **Campos OPCIONAIS** (None quando o provider/fase não preenche):
        - `provider_pressure`: Opta momentum (Fase A — só StatsStream Opta).
        - `version`: versão do snapshot Betano (`BridgeStatsAdapter` Fase E.1).
          AF e Fase A deixam None.
        - `second_since_start`: clock granular em segundos (Betano `/latest`).
          AF expõe só minuto → deixa None.
        - `corners_last_5min`/`_10min`, `yellow_last_5min`/`_10min`:
          janelas calculadas **a posteriori** por `StatsWindowCalculator`
          (PARTE E') a partir do histórico em `stats_history`. Snapshot recém-saído
          do adapter sempre vem com essas 4 keys = None — checar via
          `has_window_stats` antes de assumir presença.

    Downstream que precisa dos campos opcionais deve fazer `if x is None`
    checagem explícita ou usar a property `has_window_stats`.
    """

    fixture_id: int
    source: str                 # "betano" | "apifootball" | "bridge_betano"
    minute: int
    score_home: int
    score_away: int
    corners_home: int
    corners_away: int
    yellow_cards_home: int
    yellow_cards_away: int
    red_cards_home: int
    red_cards_away: int
    shots_on_target_home: int
    shots_on_target_away: int
    dangerous_attacks_home: int
    dangerous_attacks_away: int
    possession_home: int
    possession_away: int
    x_goals_home: float
    x_goals_away: float
    provider_pressure: Optional[float] = None  # Opta momentum (Fase A)
    raw: dict = field(default_factory=dict)
    # ----- Campos Fase E.1 — opcionais -----
    version: Optional[int] = None
    second_since_start: Optional[int] = None
    corners_last_5min: Optional[int] = None
    corners_last_10min: Optional[int] = None
    yellow_last_5min: Optional[int] = None
    yellow_last_10min: Optional[int] = None
    captured_at_ts: Optional[float] = None
    """Unix timestamp (segundos) do snapshot. Bridge devolve em
    `payload.captured_at`; AF/Fase A deixam None. Usado pelo orquestrador
    pra recalcular minuto quando snapshot vem cached (`is_cached=True`)."""
    # ----- Campos K.1 PARTE B — enrichment SofaScore -----
    # Default None = não preenchido por este provider. Composite enrichment
    # detecta `is None` (ou val==0 quando shots_on_target via _is_betano_gap)
    # e completa via SofaScore quando Betano primary deixou gap.
    shots_off_target_home: Optional[int] = None
    shots_off_target_away: Optional[int] = None
    blocked_shots_home: Optional[int] = None
    blocked_shots_away: Optional[int] = None
    big_chances_home: Optional[int] = None
    big_chances_away: Optional[int] = None
    big_chances_missed_home: Optional[int] = None
    big_chances_missed_away: Optional[int] = None
    stats_1h: Optional[dict] = None
    stats_2h: Optional[dict] = None
    enriched_by: Optional[list[str]] = None
    """Lista de providers que enriqueceram o snapshot (ordem cronológica
    do enrichment). None = sem enrichment. Ex: ['sofascore']."""
    sofa_event_id: Optional[int] = None
    """H A1.3 fix: SofaScore conhece nativamente (resolve em runtime). Bridge/AF
    deixam None — worker faz fallback via af_sofa_fixture_map."""
    is_cached: bool = False
    """True quando snapshot vem do cache interno do adapter (304 Not Modified).

    Implicações pra orquestrador (PARTE F'):
    - `minute` pode estar congelado (no momento do último 200) — recalcular via
      `minute_atual = cached.minute + int((now - cached.captured_at_ts) / 60)`
    - `StatsWindowCalculator.add_snapshot` NÃO deve ser chamado de novo (evita
      duplicata no histórico de janelas)
    - `stats_history` pode persistir com flag `source_freshness='cached'` pra
      auditoria (vs `'fresh'` quando is_cached=False)
    - Log diferenciado: `stats fixture=X cached_age=Ns` vs `stats fresh`

    Convenção:
    - Adapter retorna `is_cached=True` quando 304 com cache HIT
    - Adapter retorna `is_cached=False` em todos outros caminhos (200 fresh,
      304 com cache MISS + re-fetch que veio 200, etc)
    """

    @property
    def has_window_stats(self) -> bool:
        """True se as 4 janelas (corners/yellow × 5/10min) estão preenchidas."""
        return (
            self.corners_last_5min is not None
            and self.corners_last_10min is not None
            and self.yellow_last_5min is not None
            and self.yellow_last_10min is not None
        )


@runtime_checkable
class StatsProvider(Protocol):
    name: str

    async def get_stats(self, fixture: CanonicalFixture) -> Optional[CanonicalStats]: ...

    async def healthcheck(self) -> bool: ...


def _is_betano_gap_field(
    field_name: str, primary: CanonicalStats
) -> bool:
    """Detecta se `field_name` está vazio no `primary` (gap Betano).

    Regra:
    - `shots_on_target_*`: int garantido. Considerado gap quando ==0 E source
      é 'bridge_betano' (Betano não cobre essa métrica, sempre devolve 0).
    - Demais campos em BETANO_GAPS_STATS: Optional[*]. Gap quando `is None`.
    """
    if field_name in ("shots_on_target_home", "shots_on_target_away"):
        return (
            primary.source == "bridge_betano"
            and getattr(primary, field_name, 0) == 0
        )
    return getattr(primary, field_name, None) is None


def _merge_enrichment(
    primary: CanonicalStats,
    enricher: CanonicalStats,
    enricher_source: str,
) -> CanonicalStats:
    """Preenche em `primary` os campos `BETANO_GAPS_STATS` ainda vazios,
    usando valores do `enricher`. NUNCA sobrescreve valores não-gap.
    Marca `enriched_by` com o nome do source.
    """
    merge: dict = {}
    for f in BETANO_GAPS_STATS:
        if not _is_betano_gap_field(f, primary):
            continue
        sofa_val = getattr(enricher, f, None)
        if sofa_val is None or sofa_val == 0:
            continue
        merge[f] = sofa_val

    if not merge:
        return primary

    enriched_by = list(primary.enriched_by or []) + [enricher_source]
    merge["enriched_by"] = enriched_by
    return replace(primary, **merge)


class CompositeStatsProvider:
    """Composite com cascata sequencial + enrichment opcional do primary.

    Política K.1:
    - **primary**: tenta primeiro (Betano via bridge).
    - Se primary OK: tenta enriquecer com `fallback_intermediate` (SofaScore)
      em paralelo — falha de enrichment NÃO derruba primary.
    - Se primary falha: cai pra `fallback_intermediate`; se falha, cai pra
      `fallback_final` (AF super-residual).

    Compat: construtor antigo `CompositeStatsProvider(providers, drift_check)`
    continua funcionando (cascata pura sem enrichment).
    """

    name = "composite"

    def __init__(
        self,
        providers: Optional[list[StatsProvider]] = None,
        drift_check: bool = False,
        *,
        primary: Optional[StatsProvider] = None,
        fallback_intermediate: Optional[StatsProvider] = None,
        fallback_final: Optional[StatsProvider] = None,
        enable_enrichment: bool = True,
    ):
        if providers is not None:
            # Modo legado (E.1, F, G): lista de providers cascade pura.
            self._providers = list(providers)
            self._primary = providers[0] if providers else None
            self._fallback_int = None
            self._fallback_final = None
        else:
            # Modo K.1: primary + intermediário + final.
            if primary is None:
                raise ValueError(
                    "CompositeStatsProvider precisa de `providers` OU `primary`"
                )
            self._primary = primary
            self._fallback_int = fallback_intermediate
            self._fallback_final = fallback_final
            self._providers = [
                p
                for p in (primary, fallback_intermediate, fallback_final)
                if p is not None
            ]
        self._drift_check = drift_check
        self._enable_enrichment = enable_enrichment

    async def get_stats(self, fixture: CanonicalFixture) -> Optional[CanonicalStats]:
        # Caminho legado (lista de providers, sem fallback_int/final separados):
        # cascata pura sem enrichment.
        if self._fallback_int is None and self._fallback_final is None:
            return await self._cascade_legacy(fixture)

        # Caminho K.1: primary com enrichment + 2 níveis de fallback.
        return await self._cascade_k1(fixture)

    async def _cascade_legacy(
        self, fixture: CanonicalFixture
    ) -> Optional[CanonicalStats]:
        results: list[tuple[str, Optional[CanonicalStats]]] = []
        for p in self._providers:
            try:
                r = await p.get_stats(fixture)
            except Exception as e:
                log.warning(
                    "composite.stats.%s.error fixture=%d err=%s",
                    p.name, fixture.fixture_id, e,
                )
                r = None
            results.append((p.name, r))
            if r is not None and not self._drift_check:
                break

        primary = next((r for _, r in results if r is not None), None)
        if self._drift_check and sum(1 for _, r in results if r is not None) >= 2:
            _log_stats_drift(fixture.fixture_id, results)
        return primary

    async def _cascade_k1(
        self, fixture: CanonicalFixture
    ) -> Optional[CanonicalStats]:
        # 1. Primary
        try:
            primary_stats = await self._primary.get_stats(fixture)
        except Exception as e:
            log.warning(
                "composite.stats.primary.error fixture=%d err=%s",
                fixture.fixture_id, e,
            )
            primary_stats = None

        if primary_stats is not None:
            if self._enable_enrichment and self._fallback_int is not None:
                enriched = await self._try_enrich(primary_stats, fixture)
                if enriched is not None:
                    return enriched
            return primary_stats

        # 2. Fallback intermediário
        if self._fallback_int is not None:
            try:
                int_stats = await self._fallback_int.get_stats(fixture)
            except Exception as e:
                log.warning(
                    "composite.stats.fallback_int.error fixture=%d err=%s",
                    fixture.fixture_id, e,
                )
                int_stats = None
            if int_stats is not None:
                return int_stats

        # 3. Fallback final (AF super-residual)
        if self._fallback_final is not None:
            try:
                final_stats = await self._fallback_final.get_stats(fixture)
            except Exception as e:
                log.warning(
                    "composite.stats.fallback_final.error fixture=%d err=%s",
                    fixture.fixture_id, e,
                )
                final_stats = None
            if final_stats is not None:
                log.warning(
                    "composite.stats.using_super_residual fixture=%d",
                    fixture.fixture_id,
                )
                return final_stats

        return None

    async def _try_enrich(
        self,
        primary_stats: CanonicalStats,
        fixture: CanonicalFixture,
    ) -> Optional[CanonicalStats]:
        # Curto-circuito: nenhum gap → pula chamada SofaScore.
        has_gap = any(_is_betano_gap_field(f, primary_stats) for f in BETANO_GAPS_STATS)
        if not has_gap:
            return primary_stats

        try:
            enricher_stats = await self._fallback_int.get_stats(fixture)
        except Exception as e:
            log.debug(
                "composite.stats.enrichment.failed fixture=%d err=%s",
                fixture.fixture_id, e,
            )
            return primary_stats  # silencioso: primary vence
        if enricher_stats is None:
            return primary_stats

        try:
            merged = _merge_enrichment(
                primary_stats, enricher_stats, self._fallback_int.name
            )
        except Exception as e:
            log.warning(
                "composite.stats.enrichment.merge_error fixture=%d err=%s",
                fixture.fixture_id, e,
            )
            return primary_stats

        if merged is not primary_stats:
            log.debug(
                "composite.stats.enriched fixture=%d source=%s by=%s",
                fixture.fixture_id, primary_stats.source,
                merged.enriched_by,
            )
        return merged

    async def healthcheck(self) -> bool:
        for p in self._providers:
            try:
                if await p.healthcheck():
                    return True
            except Exception:
                log.exception("composite.stats.healthcheck.error name=%s", p.name)
        return False


def _log_stats_drift(
    fixture_id: int, results: list[tuple[str, Optional[CanonicalStats]]]
) -> None:
    pairs = [(name, r) for name, r in results if r is not None]
    if len(pairs) < 2:
        return
    a_name, a = pairs[0]
    b_name, b = pairs[1]
    log.info(
        "stats.drift fixture=%d %s corners=%d-%d  %s corners=%d-%d  "
        "yellows=%d-%d / %d-%d",
        fixture_id,
        a_name, a.corners_home, a.corners_away,
        b_name, b.corners_home, b.corners_away,
        a.yellow_cards_home, a.yellow_cards_away,
        b.yellow_cards_home, b.yellow_cards_away,
    )
