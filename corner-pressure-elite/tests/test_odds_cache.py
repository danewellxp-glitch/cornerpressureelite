"""Unit tests do OddsCache (Fase K — P4-B, 2026-05-17)."""
from __future__ import annotations

import time

from data.providers.betano_bridge.odds_cache import (
    OddsCache,
    ttl_for,
    TTL_BY_MARKET,
    TTL_DEFAULT,
)


def test_ttl_corners_30s():
    assert ttl_for("corners") == 30


def test_ttl_cards_30s():
    assert ttl_for("cards") == 30


def test_ttl_match_winner_15s():
    assert ttl_for("match_winner") == 15


def test_ttl_default_unknown_market():
    assert ttl_for("unknown_market") == TTL_DEFAULT


def test_put_then_get_returns_fresh():
    cache = OddsCache()
    cache.put(100, "corners", {"odd": 1.80})
    entry = cache.get(100, "corners")
    assert entry is not None
    assert entry.payload == {"odd": 1.80}
    assert not entry.is_stale()
    assert not entry.is_expired()
    assert entry.age_seconds() < 2


def test_get_returns_none_when_absent():
    cache = OddsCache()
    assert cache.get(999, "corners") is None


def test_get_after_ttl_returns_stale(monkeypatch):
    cache = OddsCache()
    cache.put(100, "corners", {"odd": 1.80})
    # Avança "now" pra +35s (TTL=30s, < 2× TTL=60s)
    real_time = time.time
    monkeypatch.setattr(time, "time", lambda: real_time() + 35)
    entry = cache.get(100, "corners")
    assert entry is not None
    assert entry.is_stale()
    assert not entry.is_expired()


def test_get_after_2x_ttl_returns_none_and_evicts(monkeypatch):
    cache = OddsCache()
    cache.put(100, "corners", {"odd": 1.80})
    # Avança pra +70s (> 2× TTL=60s)
    real_time = time.time
    monkeypatch.setattr(time, "time", lambda: real_time() + 70)
    assert cache.get(100, "corners") is None
    # Cache deve ter sido limpo (fixture removido se vazio)
    assert cache.stats()["total"] == 0


def test_cleanup_removes_old_entries(monkeypatch):
    cache = OddsCache()
    cache.put(100, "corners", {"odd": 1.80})
    cache.put(101, "cards", {"odd": 1.50})
    # Não mexe enquanto frescos
    assert cache.cleanup(max_age_seconds=600) == 0
    # Avança 700s
    real_time = time.time
    monkeypatch.setattr(time, "time", lambda: real_time() + 700)
    removed = cache.cleanup(max_age_seconds=600)
    assert removed == 2
    assert cache.stats()["total"] == 0


def test_stats_returns_fresh_stale_breakdown(monkeypatch):
    cache = OddsCache()
    cache.put(100, "corners", {"odd": 1.80})
    cache.put(101, "cards", {"odd": 1.50})
    # Avança 35s — corners + cards ficam stale (TTL=30s)
    real_time = time.time
    monkeypatch.setattr(time, "time", lambda: real_time() + 35)
    s = cache.stats()
    assert s == {"fixtures": 2, "total": 2, "fresh": 0, "stale": 2}


def test_put_overwrites_existing_entry():
    cache = OddsCache()
    cache.put(100, "corners", {"odd": 1.80})
    cache.put(100, "corners", {"odd": 1.95})
    assert cache.get(100, "corners").payload == {"odd": 1.95}
