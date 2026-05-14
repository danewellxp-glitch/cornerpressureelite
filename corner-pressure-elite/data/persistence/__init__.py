"""Workers async para persistência granular (Fase D).

- `OddsPersistenceWorker` — consome `OddsHistoryEntry` da fila e batcha inserts.
- `IncidentsPersistenceWorker` — idem para `IncidentHistoryEntry`.
- `CleanupWorker` — diário, aplica TTL.

Todos são isolados do caminho crítico via `asyncio.Queue` — descarte com log
em queue cheia, evita back-pressure no orquestrador.
"""
from .cleanup_worker import CleanupWorker
from .incidents_worker import IncidentsPersistenceWorker
from .odds_worker import OddsPersistenceWorker

__all__ = [
    "CleanupWorker",
    "IncidentsPersistenceWorker",
    "OddsPersistenceWorker",
]
