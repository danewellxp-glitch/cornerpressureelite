"""Fase H A1.2 — Backfill sofa_event_id em tabelas historicas.

Estrategia:
1. Coleta fixture_ids distintos com sofa_event_id IS NULL (UNION 5 tabelas).
2. Pra cada fixture, extrai metadata (home, away, kickoff_date) via:
   a. betano_fixture_map (preferido — confidence 1.00 da D.2 PARTE A)
   b. sinais (fallback — jogo_descricao + timestamp.date como kickoff)
3. Busca SofaScore /scheduled-events/{date} (cache por dia pra economizar reqs).
4. Fuzzy match (home, away) + tie-breaker temporal ±60min.
5. Persiste em af_sofa_fixture_map + UPDATE em 6 tabelas.
6. Reporta cobertura final por tabela.

PRESERVA orfaos (decisao Daniel ajuste 2): fixtures sem match ficam
sofa_event_id=NULL. Historico read-only continua acessivel.

Idempotente: re-run pula fixtures ja em af_sofa_fixture_map.

ABORT THRESHOLD (ajuste 3): se cobertura events_history <60%, scripts sai
com exit code 2 (sinaliza pra Daniel reconsiderar OPCAO B).

Run:
    docker exec -e PYTHONPATH=/app -w /app cpes-main \\
        python scripts/backfill_sofa_event_id.py
"""
from __future__ import annotations

import asyncio
import logging
import os
import sys
from datetime import date as date_cls, datetime, timezone
from typing import Optional

import asyncpg
from rapidfuzz import fuzz

# Permite rodar standalone (sem PYTHONPATH=/app o asyncpg ainda funciona).
sys.path.insert(0, "/app")

from data.providers.sofascore.client import SofaScoreClient  # noqa: E402

log = logging.getLogger("backfill")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(name)-15s | %(levelname)-8s | %(message)s",
)

_FUZZ_THRESHOLD = 85
_KICKOFF_WINDOW_MIN = 60   # mais frouxo que event_resolver (resolver é 30min p/ live)
_BATCH_SIZE = 100
_INTER_FIXTURE_SLEEP = 0.3
_TABLES_WITH_FIXTURE_ID = (
    "odds_history",
    "stats_history",
    "events_history",
    "lineups_history",
    "blocked_signals",
)


async def _connect_pool() -> asyncpg.Pool:
    dsn = os.getenv("DATABASE_URL") or os.getenv("POSTGRES_DSN")
    if not dsn:
        # Defaults same as storage/database.py
        host = os.getenv("POSTGRES_HOST", "postgres")
        port = os.getenv("POSTGRES_PORT", "5432")
        db = os.getenv("POSTGRES_DB", "cpes")
        user = os.getenv("POSTGRES_USER", "cpes_user")
        pwd = os.getenv("POSTGRES_PASSWORD", "cpes_password_2026")
        dsn = f"postgresql://{user}:{pwd}@{host}:{port}/{db}"
    log.info("connecting to db: %s", dsn.replace(pwd if 'pwd' in locals() else '***', '***'))
    return await asyncpg.create_pool(dsn, min_size=1, max_size=4)


async def collect_fixtures_to_resolve(pool: asyncpg.Pool) -> list[int]:
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT fixture_id FROM (
                SELECT fixture_id FROM odds_history WHERE sofa_event_id IS NULL
                UNION SELECT fixture_id FROM stats_history WHERE sofa_event_id IS NULL
                UNION SELECT fixture_id FROM events_history WHERE sofa_event_id IS NULL
                UNION SELECT fixture_id FROM lineups_history WHERE sofa_event_id IS NULL
                UNION SELECT fixture_id FROM blocked_signals WHERE sofa_event_id IS NULL
                UNION SELECT jogo_id AS fixture_id FROM sinais WHERE sofa_event_id IS NULL
            ) AS uniq
            WHERE fixture_id NOT IN (SELECT fixture_id FROM af_sofa_fixture_map)
            ORDER BY fixture_id DESC
            """
        )
    return [int(r["fixture_id"]) for r in rows]


async def fetch_metadata(pool: asyncpg.Pool, fixture_id: int) -> Optional[dict]:
    """Tenta extrair (home, away, kickoff_date) pra fixture_id.

    Prefere betano_fixture_map (cobertura ~67%, kickoff_utc certo).
    Fallback: sinais (jogo_descricao + timestamp).
    Retorna None se nenhum tiver.
    """
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT home_team, away_team, kickoff_utc
            FROM betano_fixture_map WHERE fixture_id = $1
            """,
            fixture_id,
        )
    if row and row["home_team"] and row["away_team"]:
        kickoff = row["kickoff_utc"]
        return {
            "home": row["home_team"],
            "away": row["away_team"],
            "kickoff": kickoff,
            "date_str": kickoff.date().isoformat() if kickoff else None,
            "source": "betano_fixture_map",
        }
    # Fallback: sinais
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT jogo_descricao, timestamp
            FROM sinais
            WHERE jogo_id = $1
            ORDER BY id ASC
            LIMIT 1
            """,
            fixture_id,
        )
    if not row or not row["jogo_descricao"] or " vs " not in row["jogo_descricao"]:
        return None
    parts = row["jogo_descricao"].split(" vs ", 1)
    if len(parts) != 2:
        return None
    ts = row["timestamp"]
    # `timestamp` em sinais é WHEN signal emitted (minuto 50+), kickoff foi ~50-90min antes.
    # Pra scheduled-events, basta date — toleramos diferença pq janela é por dia.
    return {
        "home": parts[0].strip(),
        "away": parts[1].strip(),
        "kickoff": ts.replace(tzinfo=timezone.utc) if ts and ts.tzinfo is None else ts,
        "date_str": ts.date().isoformat() if ts else None,
        "source": "sinais",
    }


def fuzzy_match(
    events: list[dict],
    home: str,
    away: str,
    kickoff: Optional[datetime],
) -> Optional[int]:
    candidates: list[tuple[float, int]] = []
    for ev in events:
        if not isinstance(ev, dict):
            continue
        ev_id = ev.get("id")
        if not isinstance(ev_id, int):
            continue
        ht = (ev.get("homeTeam") or {})
        at = (ev.get("awayTeam") or {})
        ev_home = ht.get("name") if isinstance(ht, dict) else None
        ev_away = at.get("name") if isinstance(at, dict) else None
        if not ev_home or not ev_away:
            continue
        score = (fuzz.ratio(home, ev_home) + fuzz.ratio(away, ev_away)) / 2

        # Tie-breaker temporal opcional
        if kickoff is not None:
            ts = ev.get("startTimestamp")
            if isinstance(ts, int):
                sofa_kickoff = datetime.fromtimestamp(ts, tz=timezone.utc)
                k = kickoff.astimezone(timezone.utc) if kickoff.tzinfo else kickoff.replace(tzinfo=timezone.utc)
                if abs((sofa_kickoff - k).total_seconds() / 60) > _KICKOFF_WINDOW_MIN:
                    continue

        if score >= _FUZZ_THRESHOLD:
            candidates.append((score, ev_id))

    if not candidates:
        return None
    candidates.sort(key=lambda x: -x[0])
    return candidates[0][1]


async def persist_mapping_and_update(
    pool: asyncpg.Pool,
    fixture_id: int,
    sofa_id: int,
    mapped_via: str,
) -> None:
    async with pool.acquire() as conn, conn.transaction():
        await conn.execute(
            """
            INSERT INTO af_sofa_fixture_map (fixture_id, sofa_event_id, confidence, mapped_via)
            VALUES ($1, $2, 1.0, $3)
            ON CONFLICT (fixture_id) DO UPDATE SET
                sofa_event_id = EXCLUDED.sofa_event_id,
                mapped_via = EXCLUDED.mapped_via,
                last_validated_at = NOW()
            """,
            fixture_id, sofa_id, mapped_via,
        )
        # Update 5 tabelas com fixture_id + sinais (jogo_id)
        for table in _TABLES_WITH_FIXTURE_ID:
            await conn.execute(
                f"UPDATE {table} SET sofa_event_id = $2 WHERE fixture_id = $1 AND sofa_event_id IS NULL",
                fixture_id, sofa_id,
            )
        await conn.execute(
            "UPDATE sinais SET sofa_event_id = $2 WHERE jogo_id = $1 AND sofa_event_id IS NULL",
            fixture_id, sofa_id,
        )


async def report_coverage(pool: asyncpg.Pool) -> dict:
    queries = {
        "odds_history": "SELECT COUNT(*) AS total, COUNT(sofa_event_id) AS resolved FROM odds_history",
        "stats_history": "SELECT COUNT(*), COUNT(sofa_event_id) FROM stats_history",
        "events_history": "SELECT COUNT(*), COUNT(sofa_event_id) FROM events_history",
        "lineups_history": "SELECT COUNT(*), COUNT(sofa_event_id) FROM lineups_history",
        "blocked_signals": "SELECT COUNT(*), COUNT(sofa_event_id) FROM blocked_signals",
        "sinais": "SELECT COUNT(*), COUNT(sofa_event_id) FROM sinais",
    }
    out = {}
    async with pool.acquire() as conn:
        for table, q in queries.items():
            row = await conn.fetchrow(q)
            total = int(row[0] if isinstance(row[0], int) else row["count"])
            resolved = int(row[1] if isinstance(row[1], int) else 0)
            pct = (resolved / total * 100) if total > 0 else 100.0
            out[table] = {"total": total, "resolved": resolved, "pct": round(pct, 1)}
    return out


async def main():
    pool = await _connect_pool()
    fixtures = await collect_fixtures_to_resolve(pool)
    log.info("fixtures pra resolver: %d", len(fixtures))
    if not fixtures:
        log.info("nada pra fazer.")
        await pool.close()
        return

    sofa = SofaScoreClient()
    await sofa.start()

    # Cache de scheduled-events por dia (evita refetch quando varios fixtures
    # caem no mesmo dia)
    schedule_cache: dict[str, Optional[list[dict]]] = {}

    resolved = 0
    no_metadata = 0
    no_match = 0
    by_via: dict[str, int] = {}

    try:
        for i, fixture_id in enumerate(fixtures, 1):
            meta = await fetch_metadata(pool, fixture_id)
            if not meta or not meta.get("date_str"):
                no_metadata += 1
                log.debug("[NO_META] fixture=%d (sem betano_map nem sinais usaveis)", fixture_id)
                continue

            date_str = meta["date_str"]
            if date_str not in schedule_cache:
                log.info("[SCHEDULE] fetching %s ...", date_str)
                schedule_cache[date_str] = await sofa.get_scheduled_events(date_str)
                await asyncio.sleep(0.5)  # gentle rate limit
            events = schedule_cache[date_str] or []
            if not events:
                log.debug("[NO_SCHEDULE] fixture=%d date=%s (sofa retornou vazio)", fixture_id, date_str)
                no_match += 1
                continue

            sofa_id = fuzzy_match(events, meta["home"], meta["away"], meta.get("kickoff"))
            if sofa_id is None:
                no_match += 1
                log.debug("[NO_MATCH] fixture=%d home=%r away=%r (em %d events)",
                          fixture_id, meta["home"], meta["away"], len(events))
                continue

            mapped_via = f"backfill_via_{meta['source']}"
            await persist_mapping_and_update(pool, fixture_id, sofa_id, mapped_via)
            resolved += 1
            by_via[mapped_via] = by_via.get(mapped_via, 0) + 1

            if i % 10 == 0:
                log.info("[PROGRESS] %d/%d processados (resolved=%d)", i, len(fixtures), resolved)

            await asyncio.sleep(_INTER_FIXTURE_SLEEP)
    finally:
        await sofa.close()

    log.info("=" * 60)
    log.info("RESUMO BACKFILL")
    log.info("=" * 60)
    log.info("total fixtures processados: %d", len(fixtures))
    log.info("  resolvidos:               %d", resolved)
    log.info("  sem metadata:             %d", no_metadata)
    log.info("  sem match no SofaScore:   %d", no_match)
    for via, n in by_via.items():
        log.info("  via %s: %d", via, n)
    log.info("")
    log.info("COBERTURA por tabela (apos backfill):")
    coverage = await report_coverage(pool)
    for table, stats in coverage.items():
        log.info("  %-18s %5d/%5d (%5.1f%%)", table, stats["resolved"], stats["total"], stats["pct"])

    await pool.close()

    # AJUSTE 3: abort se events_history (maior) <60%
    events_pct = coverage["events_history"]["pct"]
    if events_pct < 60.0:
        log.warning("ABORT THRESHOLD: events_history cobertura %.1f%% < 60%%", events_pct)
        log.warning("Reportar pra Daniel — considerar OPCAO B")
        sys.exit(2)


if __name__ == "__main__":
    asyncio.run(main())
