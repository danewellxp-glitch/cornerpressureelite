"""Pytest config global para o projeto."""
import asyncio
import pytest_asyncio

from storage.database import Database


@pytest_asyncio.fixture(autouse=True)
async def _reset_db_pool():
    """Antes de cada teste async: garante pool fresco no loop atual.

    O `Database._shared_pool` é singleton de classe; ao trocar de event loop
    entre testes, o pool antigo fica preso ao loop anterior (fechado).
    Reset = força o `connect()` a recriar no loop ativo.
    """
    # Fecha pool antigo se existir
    if Database._shared_pool is not None:
        try:
            await Database._shared_pool.close()
        except Exception:
            pass
        Database._shared_pool = None
    Database._pool_lock = None
    yield
    if Database._shared_pool is not None:
        try:
            await Database._shared_pool.close()
        except Exception:
            pass
        Database._shared_pool = None
    Database._pool_lock = None
