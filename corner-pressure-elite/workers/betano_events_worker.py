"""BetanoEventsWorker — captura eventos via bridge Betano (Fase F).

Worker stateless por fixture — orquestrador chama `capture(fixture)` quando
quer persistir eventos do snapshot atual. Padrão idêntico ao
`BetanoStatsWorker` (Fase E.1).

**Escopo "dataset puro"** (PASSO 0 confirmou zero consumidores externos
de eventos): events_history popula em paralelo ao pipeline live, sem
afetar decision_engine. Alimenta Quant H1-H4 com timeline real
(GOAL/YELL/CRNR/etc + minuto exato).

Dedup garantido pelo `EventsHistoryRepo.upsert_batch` (ON CONFLICT DO
NOTHING via UNIQUE constraint do schema 0006).
"""
from __future__ import annotations

import logging
from typing import Any, Optional, Protocol

from data.events_provider import CanonicalEvent
from data.repositories.af_sofa_map import AfSofaFixtureMapRepo
from data.repositories.events_history import EventsHistoryRepo

log = logging.getLogger("cpes.workers.betano_events")


class _EventsSource(Protocol):
    """Subset do EventsProvider Protocol que o worker usa.

    Aceita `BridgeEventsAdapter` direto OU `CompositeEventsProvider`
    (cascata Betano→AF).
    """

    async def get_events(
        self,
        fixture_id: int,
        *,
        betano_event_id: Optional[int] = None,
        home_team_id: Optional[int] = None,
    ) -> Optional[list[CanonicalEvent]]: ...


class BetanoEventsWorker:
    def __init__(
        self,
        provider: _EventsSource,
        repo: EventsHistoryRepo,
        af_sofa_map: Optional[AfSofaFixtureMapRepo] = None,
    ):
        self._provider = provider
        self._repo = repo
        self._af_sofa_map = af_sofa_map

    async def capture(
        self,
        fixture_id: int,
        *,
        betano_event_id: Optional[int] = None,
        home_team_id: Optional[int] = None,
    ) -> tuple[int, int]:
        """Roda 1 ciclo de captura+persistência. Retorna `(inserted, skipped)`.

        - Provider devolve `None` → `(0, 0)` (erro/sem mapping). Log warning.
        - Provider devolve `[]` → `(0, 0)`. Log debug — events composite já
          loga INFO "empty" pra primary, evita ruído duplicado.
        - Provider devolve lista → `repo.upsert_batch` faz dedup natural via
          UNIQUE constraint. Retorna `(novos_inseridos, duplicates_pulados)`.

        Caller (PARTE F wiring main.py) decide quando chamar — não há loop
        interno. Padrão idêntico ao `BetanoStatsWorker.poll`.
        """
        events = await self._provider.get_events(
            fixture_id,
            betano_event_id=betano_event_id,
            home_team_id=home_team_id,
        )
        if events is None:
            log.warning(
                "betano_events_worker.miss fixture=%d — provider devolveu None",
                fixture_id,
            )
            return 0, 0
        if not events:
            log.debug(
                "betano_events_worker.empty fixture=%d", fixture_id,
            )
            return 0, 0

        try:
            # Fase H A1.3 + fix: sofa_event_id pode vir nativo do provider
            # (SofaScore resolve em runtime e populates entity.sofa_event_id)
            # OU via mapping table af_sofa_fixture_map (bridge/AF que so
            # conhecem fixture_id). Provider native tem prioridade.
            sofa_event_id: Optional[int] = events[0].sofa_event_id if events else None
            if self._af_sofa_map is not None:
                if sofa_event_id is None:
                    try:
                        sofa_event_id = await self._af_sofa_map.get_sofa_id(fixture_id)
                    except Exception as e:
                        log.debug("betano_events_worker.af_sofa_lookup_error fixture=%d err=%s",
                                  fixture_id, e)
                else:
                    # Opportunistic upsert: 1 hit SofaScore beneficia N
                    # capturas futuras de bridge/AF do mesmo fixture.
                    try:
                        await self._af_sofa_map.upsert(
                            fixture_id, sofa_event_id, mapped_via="provider_native",
                        )
                    except Exception as e:
                        log.debug("betano_events_worker.opportunistic_upsert_failed fixture=%d err=%s",
                                  fixture_id, e)
                inserted, skipped = await self._repo.upsert_batch(events, sofa_event_id=sofa_event_id)
            else:
                inserted, skipped = await self._repo.upsert_batch(events)
        except Exception as e:
            log.warning(
                "betano_events_worker.persist_error fixture=%d events=%d err=%s",
                fixture_id, len(events), e,
            )
            return 0, len(events)

        source = events[0].source if events else "?"
        log.info(
            "betano_events_worker.captured fixture=%d source=%s "
            "inserted=%d skipped_dup=%d total=%d",
            fixture_id, source, inserted, skipped, len(events),
        )
        return inserted, skipped
