"""BetanoStatsWorker — orquestra captura + enriquecimento + persistência
de stats por fixture, via bridge Betano (CASO α / Fase E.1).

**Responsabilidade única**: `poll(fixture)` é uma rodada atômica:
    1. Chama `BridgeStatsAdapter.get_stats(fixture)`
    2. Se OK: hidrata janelas via `StatsWindowCalculator.compute_windows`
    3. Persiste em `stats_history` via `StatsHistoryRepo.insert`
    4. Retorna o `CanonicalStats` enriquecido (pronto pra pipeline downstream)

Quem decide _quais_ fixtures monitorar e _quando_ chamar `poll` é PARTE F'
(main.py wire). Worker em si não tem loop interno — fica stateless across
fixtures, deixando o orquestrador no controle do adaptive polling.

`bootstrap_fixture(fixture)`: chamado quando o worker vê um fixture pela
1ª vez (ou restart do processo). Hidrata o calculator a partir do
`stats_history` pra que as janelas 5/10min já saiam preenchidas no 1º
poll bem-sucedido — sem isso elas ficariam None até acumular ~10min.
"""
from __future__ import annotations

import logging
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from typing import Any, Optional, Protocol

from data.odds_provider import CanonicalFixture
from data.repositories.af_sofa_map import AfSofaFixtureMapRepo
from data.repositories.stats_history import StatsHistoryEntry, StatsHistoryRepo
from data.services.stats_window_calculator import StatsWindowCalculator
from data.stats_provider import CanonicalStats

log = logging.getLogger("cpes.workers.betano_stats")


class _StatsSource(Protocol):
    """Subset do StatsProvider Protocol que o worker usa. Aceita
    BridgeStatsAdapter direto OU CompositeStatsProvider (cascata + AF fallback)."""

    async def get_stats(self, fixture: CanonicalFixture) -> Optional[CanonicalStats]: ...


class BetanoStatsWorker:
    def __init__(
        self,
        adapter: _StatsSource,
        repo: StatsHistoryRepo,
        calculator: StatsWindowCalculator,
        bootstrap_lookback_min: int = 20,
        af_sofa_map: Optional[AfSofaFixtureMapRepo] = None,
        event_resolver=None,
    ):
        self._adapter = adapter
        self._repo = repo
        self._calculator = calculator
        self._bootstrap_lookback_min = bootstrap_lookback_min
        self._bootstrapped: set[int] = set()
        self._af_sofa_map = af_sofa_map
        # SofaScoreEventResolver — fallback live quando af_sofa_map não tem o
        # fixture (essencial pra dual-write nos snapshots bridge_betano).
        self._event_resolver = event_resolver

    async def poll(self, fixture: CanonicalFixture) -> Optional[CanonicalStats]:
        """Roda 1 ciclo de captura+enrichment+persistência. Retorna `CanonicalStats`
        com janelas preenchidas, ou `None` se nada novo (404/erro/sem mapping).

        **Tratamento de `is_cached=True`** (snapshot vindo do cache interno do
        adapter, 304 HIT do bridge):
        - NÃO chama `add_snapshot` no calculator (evita duplicata no deque).
        - Computa janelas com o deque atual (mesmo valor do poll anterior fresh).
        - Persiste com `raw.freshness='cached'` pra auditoria. INSERT é
          idempotente via `ON CONFLICT (fixture, source, version) DO NOTHING`,
          então duplicate é no-op no DB de qualquer jeito.

        Bootstrap implícito: 1ª vez vendo `fixture`, hidrata calculator antes.
        """
        if fixture.fixture_id not in self._bootstrapped:
            await self.bootstrap_fixture(fixture.fixture_id)

        snapshot = await self._adapter.get_stats(fixture)
        if snapshot is None:
            return None

        captured_at = self._captured_at_from_snapshot(snapshot)

        if not snapshot.is_cached:
            # Snapshot fresco — atualiza deque do calculator.
            self._calculator.add_snapshot(
                fixture_id=snapshot.fixture_id,
                captured_at=captured_at,
                corners_total=snapshot.corners_home + snapshot.corners_away,
                yellow_total=snapshot.yellow_cards_home + snapshot.yellow_cards_away,
            )
            freshness = "fresh"
        else:
            # Snapshot cached — NÃO duplica no deque. Janelas serão calculadas
            # com o deque atual (estado do último fresh).
            freshness = "cached"
            log.debug(
                "betano_stats_worker.cached fixture=%d version=%s — skipping deque add",
                snapshot.fixture_id, snapshot.version,
            )

        windows = self._calculator.compute_windows(snapshot.fixture_id, now=captured_at)

        enriched = replace(
            snapshot,
            corners_last_5min=windows["corners_last_5min"],
            corners_last_10min=windows["corners_last_10min"],
            yellow_last_5min=windows["yellow_last_5min"],
            yellow_last_10min=windows["yellow_last_10min"],
        )

        # Fase H A1.3 + fix: provider native (SofaScore) tem prioridade sobre
        # af_sofa_map lookup. Quando snapshot vem com sofa_event_id, faz upsert
        # opportunistico pra beneficiar futuras capturas bridge/AF do fixture.
        sofa_event_id: Optional[int] = enriched.sofa_event_id
        if self._af_sofa_map is not None:
            if sofa_event_id is None:
                try:
                    sofa_event_id = await self._af_sofa_map.get_or_resolve(
                        snapshot.fixture_id, resolver=self._event_resolver,
                    )
                except Exception as e:
                    log.debug("betano_stats_worker.af_sofa_lookup_error fixture=%d err=%s",
                              snapshot.fixture_id, e)
            else:
                try:
                    await self._af_sofa_map.upsert(
                        snapshot.fixture_id, sofa_event_id, mapped_via="provider_native",
                    )
                except Exception as e:
                    log.debug("betano_stats_worker.opportunistic_upsert_failed fixture=%d err=%s",
                              snapshot.fixture_id, e)

        try:
            entry = _to_entry(enriched, captured_at, freshness)
            entry = replace(entry, sofa_event_id=sofa_event_id)
            await self._repo.insert(entry)
        except Exception as e:
            log.warning(
                "betano_stats_worker.persist_error fixture=%d version=%s freshness=%s err=%s",
                snapshot.fixture_id, snapshot.version, freshness, e,
            )

        return enriched

    async def bootstrap_fixture(self, fixture_id: int) -> None:
        """Hidrata o StatsWindowCalculator a partir do stats_history."""
        since = datetime.now(timezone.utc) - timedelta(
            minutes=self._bootstrap_lookback_min
        )
        try:
            rows = await self._repo.list_recent_for_fixture(
                fixture_id, since=since, limit=200,
            )
        except Exception as e:
            log.warning(
                "betano_stats_worker.bootstrap_error fixture=%d err=%s",
                fixture_id, e,
            )
            rows = []
        self._calculator.bootstrap_from_history(fixture_id, rows)
        self._bootstrapped.add(fixture_id)
        log.debug(
            "betano_stats_worker.bootstrapped fixture=%d snapshots=%d lookback=%dmin",
            fixture_id, len(rows), self._bootstrap_lookback_min,
        )

    def forget_fixture(self, fixture_id: int) -> None:
        """Esquece o fixture (jogo terminou). Próximo poll re-bootstrapa."""
        self._calculator.reset_fixture(fixture_id)
        self._bootstrapped.discard(fixture_id)

    @staticmethod
    def _captured_at_from_snapshot(snap: CanonicalStats) -> datetime:
        raw_ts = snap.raw.get("captured_at") if isinstance(snap.raw, dict) else None
        if isinstance(raw_ts, (int, float)):
            return datetime.fromtimestamp(raw_ts, tz=timezone.utc)
        return datetime.now(timezone.utc)


def _to_entry(
    snap: CanonicalStats, captured_at: datetime, freshness: str = "fresh"
) -> StatsHistoryEntry:
    raw_with_freshness = dict(snap.raw) if isinstance(snap.raw, dict) else {}
    raw_with_freshness["freshness"] = freshness
    return StatsHistoryEntry(
        fixture_id=snap.fixture_id,
        source=snap.source,
        minute=snap.minute,
        second_since_start=snap.second_since_start,
        score_home=snap.score_home,
        score_away=snap.score_away,
        corners_home=snap.corners_home,
        corners_away=snap.corners_away,
        yellow_cards_home=snap.yellow_cards_home,
        yellow_cards_away=snap.yellow_cards_away,
        red_cards_home=snap.red_cards_home,
        red_cards_away=snap.red_cards_away,
        shots_on_target_home=snap.shots_on_target_home,
        shots_on_target_away=snap.shots_on_target_away,
        dangerous_attacks_home=snap.dangerous_attacks_home,
        dangerous_attacks_away=snap.dangerous_attacks_away,
        possession_home=snap.possession_home,
        possession_away=snap.possession_away,
        x_goals_home=snap.x_goals_home,
        x_goals_away=snap.x_goals_away,
        version=snap.version,
        provider_pressure=snap.provider_pressure,
        corners_last_5min=snap.corners_last_5min,
        corners_last_10min=snap.corners_last_10min,
        yellow_last_5min=snap.yellow_last_5min,
        yellow_last_10min=snap.yellow_last_10min,
        captured_at=captured_at,
        raw=raw_with_freshness,
        enriched_by=snap.enriched_by,
    )
