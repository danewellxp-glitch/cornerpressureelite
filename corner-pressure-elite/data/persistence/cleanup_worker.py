"""Worker diário de cleanup com TTL configurável.

Padrão:
- odds_history > 90 dias
- incidents_history > 180 dias

Mantido como classe (não cron externo) para subir/descer junto com o
orquestrador. Idempotente: se a fila estiver vazia, DELETE só passa por
linhas que já estão fora do TTL.
"""
from __future__ import annotations

import asyncio
import logging

log = logging.getLogger("cpes.persistence.cleanup")

_INTERVAL_DAILY_SECONDS = 86400


class CleanupWorker:
    def __init__(
        self,
        pool,
        *,
        odds_ttl_days: int = 90,
        incidents_ttl_days: int = 180,
        interval_seconds: int = _INTERVAL_DAILY_SECONDS,
    ):
        self._pool = pool
        self._odds_ttl = odds_ttl_days
        self._incidents_ttl = incidents_ttl_days
        self._interval = interval_seconds
        self._stop = asyncio.Event()
        self._task: asyncio.Task | None = None

    async def start(self) -> None:
        if self._task and not self._task.done():
            return
        self._stop.clear()
        self._task = asyncio.create_task(self._run(), name="cleanup_worker")
        log.info("cleanup.started odds_ttl=%d incidents_ttl=%d",
                 self._odds_ttl, self._incidents_ttl)

    async def stop(self) -> None:
        self._stop.set()
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    async def run_once(self) -> tuple[int, int]:
        async with self._pool.acquire() as conn:
            n_odds = await conn.execute(
                "DELETE FROM odds_history "
                f"WHERE captured_at < NOW() - INTERVAL '{int(self._odds_ttl)} days'"
            )
            n_inc = await conn.execute(
                "DELETE FROM incidents_history "
                f"WHERE captured_at < NOW() - INTERVAL '{int(self._incidents_ttl)} days'"
            )
        deleted_odds = _parse_delete_status(n_odds)
        deleted_inc = _parse_delete_status(n_inc)
        log.info("cleanup.done odds=%d incidents=%d", deleted_odds, deleted_inc)
        return deleted_odds, deleted_inc

    async def _run(self) -> None:
        while not self._stop.is_set():
            try:
                await self.run_once()
            except Exception:
                log.exception("cleanup.error")
            try:
                await asyncio.wait_for(self._stop.wait(), timeout=self._interval)
            except asyncio.TimeoutError:
                continue


def _parse_delete_status(status: str) -> int:
    """asyncpg.execute() retorna 'DELETE <n>'. Extrai o n."""
    try:
        parts = status.split()
        return int(parts[-1]) if parts else 0
    except (ValueError, AttributeError):
        return 0
