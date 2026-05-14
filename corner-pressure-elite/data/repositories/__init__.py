"""Repositories da Fase D: persistência granular Betano + AF.

Tabelas em `migrations/000{1,2,3}_*.sql`, já aplicadas. Os repositories são
thin wrappers sobre o pool `asyncpg` compartilhado em `storage.database`.
"""
from .fixture_map import FixtureMapRepo
from .incidents_history import (
    IncidentHistoryEntry,
    IncidentsHistoryRepo,
    event_uid,
)
from .odds_history import OddsHistoryEntry, OddsHistoryRepo

__all__ = [
    "FixtureMapRepo",
    "IncidentHistoryEntry",
    "IncidentsHistoryRepo",
    "OddsHistoryEntry",
    "OddsHistoryRepo",
    "event_uid",
]
