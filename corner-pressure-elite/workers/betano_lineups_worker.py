"""BetanoLineupsWorker — captura lineups via bridge Betano (Fase G.1).

Worker stateless por fixture. Diferente do `BetanoEventsWorker` (chama
todo poll), lineups são ESTÁVEIS pós-confirmação: capturamos UMA VEZ no
primeiro tick com `minute < LINEUPS_MAX_MINUTE` e desistimos do fixture
no cache (re-fetch zero pelo resto do jogo).

**Escopo "dataset puro"** (G.0 confirmou CASO α puro, mesmo endpoint da
E.1 — zero nova request HTTP): lineups_history popula em paralelo, sem
afetar decision_engine. Alimenta Quant H2-H4 (formation, qualidade XI
titular, profundidade bench).

Cache duplo:
- In-memory (`_captured`): short-circuit dentro do processo.
- `repo.exists_for_fixture`: short-circuit entre restarts (DB é fonte
  de verdade de longo prazo).

UNIQUE constraint `(fixture, source, team_side)` é a última linha de
defesa contra race (worker chamado 2× antes do cache popular).
"""
from __future__ import annotations

import logging
from typing import Optional, Protocol

from data.lineups_provider import CanonicalLineup
from data.repositories.lineups_history import LineupsHistoryRepo

log = logging.getLogger("cpes.workers.betano_lineups")


class _LineupsSource(Protocol):
    """Subset do LineupsProvider Protocol que o worker usa.

    Aceita `BridgeLineupsAdapter` direto OU `CompositeLineupsProvider`
    (cascata Betano→AF).
    """

    async def get_lineups(
        self,
        fixture_id: int,
        *,
        betano_event_id: Optional[int] = None,
        home_team_id: Optional[int] = None,
    ) -> Optional[list[CanonicalLineup]]: ...


class BetanoLineupsWorker:
    def __init__(
        self,
        provider: _LineupsSource,
        repo: LineupsHistoryRepo,
        max_minute: int = 5,
    ):
        self._provider = provider
        self._repo = repo
        self._max_minute = max_minute
        # Cache in-memory: fixtures já capturados nesta execução.
        # Reset em restart (repo.exists_for_fixture cobre o gap).
        self._captured: set[int] = set()

    async def capture_if_needed(
        self,
        fixture_id: int,
        *,
        minute: Optional[int] = None,
        betano_event_id: Optional[int] = None,
        home_team_id: Optional[int] = None,
    ) -> tuple[int, int]:
        """Captura lineups se ainda não persistiu pro fixture.

        Returns `(inserted, skipped_dup)`. `(0, 0)` quando short-circuit
        (já capturado / minute fora da janela / provider falhou).

        Ordem de checks (cheap → caro):
        1. Cache in-memory.
        2. `minute > max_minute` (lineup costuma ser publicada nos primeiros
           minutos; tarde demais = perda de tempo + risco da Betano já não
           expor mais o roster do snapshot inicial).
        3. `repo.exists_for_fixture` (DB lookup).
        4. Provider fetch + persist.
        """
        if fixture_id in self._captured:
            return 0, 0

        if minute is not None and minute > self._max_minute:
            log.debug(
                "betano_lineups_worker.skip_late fixture=%d minute=%d max=%d",
                fixture_id, minute, self._max_minute,
            )
            # NÃO marca cache: se minute vier com spike transiente (bug de
            # parsing, race no recálculo), próximo poll com valor correto
            # ainda tem chance de capturar. Custo: repo.exists_for_fixture
            # extra por poll desses fixtures (1 query barata).
            return 0, 0

        try:
            already = await self._repo.exists_for_fixture(fixture_id)
        except Exception as e:
            log.warning(
                "betano_lineups_worker.exists_check_error fixture=%d err=%s",
                fixture_id, e,
            )
            already = False
        if already:
            self._captured.add(fixture_id)
            return 0, 0

        lineups = await self._provider.get_lineups(
            fixture_id,
            betano_event_id=betano_event_id,
            home_team_id=home_team_id,
        )
        if lineups is None:
            log.warning(
                "betano_lineups_worker.miss fixture=%d — provider devolveu None",
                fixture_id,
            )
            return 0, 0
        if not lineups:
            log.debug(
                "betano_lineups_worker.empty fixture=%d", fixture_id,
            )
            return 0, 0

        try:
            inserted, skipped = await self._repo.upsert_batch(lineups)
        except Exception as e:
            log.warning(
                "betano_lineups_worker.persist_error fixture=%d sides=%d err=%s",
                fixture_id, len(lineups), e,
            )
            return 0, len(lineups)

        if inserted > 0:
            # Só marca cache quando persistiu — se todos foram skip_dup,
            # repo.exists_for_fixture vai short-circuit no próximo poll.
            self._captured.add(fixture_id)

        source = lineups[0].source if lineups else "?"
        log.info(
            "betano_lineups_worker.captured fixture=%d source=%s "
            "inserted=%d skipped_dup=%d total=%d",
            fixture_id, source, inserted, skipped, len(lineups),
        )
        return inserted, skipped

    def forget_fixture(self, fixture_id: int) -> None:
        """Esquece o fixture (jogo terminou). Próxima captura re-checa repo."""
        self._captured.discard(fixture_id)
