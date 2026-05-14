"""Adapters da API-Football para as interfaces canônicas Composite.

NÃO modifica `data/api_client.py` (legado intocado para permitir rollback).
"""
from .odds_adapter import APIFootballOddsProvider
from .stats_adapter import APIFootballStatsProvider

__all__ = ["APIFootballOddsProvider", "APIFootballStatsProvider"]
