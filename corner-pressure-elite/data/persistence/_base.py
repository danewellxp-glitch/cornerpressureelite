"""Base genérica para os workers de persistência."""
from __future__ import annotations

import asyncio
import logging
from typing import Generic, Optional, TypeVar

log = logging.getLogger("cpes.persistence.worker")

T = TypeVar("T")


class _BaseBatchWorker(Generic[T]):
    """Lê itens de `asyncio.Queue`, batcha e chama `flush(batch)`.

    - `queue_size` cap evita OOM em alta carga.
    - `batch_size` itens ou `batch_timeout_s` segundos disparam um flush.
    - Erros do flush são logados; itens do batch são perdidos. Trade-off
      consciente: pipeline crítico fica protegido.
    """

    def __init__(
        self,
        *,
        name: str,
        queue_size: int = 10000,
        batch_size: int = 10,
        batch_timeout_s: float = 5.0,
    ) -> None:
        self._name = name
        self._q: asyncio.Queue[T] = asyncio.Queue(maxsize=queue_size)
        self._batch_size = batch_size
        self._batch_timeout = batch_timeout_s
        self._stop = asyncio.Event()
        self._task: Optional[asyncio.Task] = None

    @property
    def queue_size(self) -> int:
        return self._q.qsize()

    def enqueue(self, entry: T) -> None:
        try:
            self._q.put_nowait(entry)
        except asyncio.QueueFull:
            log.warning("%s.queue_full — descarte (size=%d)", self._name, self._q.qsize())

    async def start(self) -> None:
        if self._task and not self._task.done():
            return
        self._stop.clear()
        self._task = asyncio.create_task(self._run(), name=self._name)
        log.info("%s.started", self._name)

    async def stop(self) -> None:
        self._stop.set()
        if self._task:
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        log.info("%s.stopped", self._name)

    async def _run(self) -> None:
        while not self._stop.is_set():
            batch = await self._collect_batch()
            if not batch:
                continue
            try:
                await self.flush(batch)
                log.debug("%s.flushed n=%d", self._name, len(batch))
            except Exception:
                log.exception("%s.flush_error n=%d", self._name, len(batch))
        # drain restante ao parar
        remaining: list[T] = []
        while not self._q.empty():
            try:
                remaining.append(self._q.get_nowait())
            except asyncio.QueueEmpty:
                break
        if remaining:
            try:
                await self.flush(remaining)
                log.info("%s.drained n=%d", self._name, len(remaining))
            except Exception:
                log.exception("%s.drain_error n=%d", self._name, len(remaining))

    async def _collect_batch(self) -> list[T]:
        batch: list[T] = []
        try:
            first = await asyncio.wait_for(self._q.get(), timeout=self._batch_timeout)
            batch.append(first)
        except asyncio.TimeoutError:
            return batch
        while len(batch) < self._batch_size:
            try:
                batch.append(self._q.get_nowait())
            except asyncio.QueueEmpty:
                break
        return batch

    async def flush(self, batch: list[T]) -> None:
        raise NotImplementedError
