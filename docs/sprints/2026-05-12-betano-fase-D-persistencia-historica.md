# Fase D — Persistência Histórica (odds + incidents)

> **Mestre:** [`2026-05-12-betano-discovery-master.md`](2026-05-12-betano-discovery-master.md)
>
> **Pré-requisitos:** [Fase A](2026-05-12-betano-fase-A-statsstream-provider.md), [B](2026-05-12-betano-fase-B-markets-ws-provider.md) e [C](2026-05-12-betano-fase-C-pipeline-refactor.md) concluídas.
>
> **Duração estimada:** ~10h

---

## 1. Objetivo

Persistir histórico de **fixture map**, **odds capturadas** e **incidents
granulares** (eventos Opta com X/Y) em Postgres. Hooks plugados no fluxo dos
Composite providers; sem bloquear o caminho crítico do orquestrador.

Dados servem para:
- Recalibração de `quality_model.py` e thresholds (Fase 4 do robô auto)
- Debug de drift histórico de odds
- Backtests com dados reais
- Análise de pressão pré-incidente (X/Y dos ataques que precederam um escanteio)

---

## 2. Pré-requisitos

- [x] Postgres operacional (já existe no projeto)
- [x] `data/db.py` ou equivalente com pool async (asyncpg ou SQLAlchemy)
- [x] Fase A/B/C concluídas

---

## 3. Capabilities entregues

1. **3 migrations idempotentes** (`betano_fixture_map`, `odds_history`,
   `incidents_history`) em `migrations/` numeradas.
2. **Repositories** (`data/repositories/fixture_map.py`,
   `odds_history.py`, `incidents_history.py`) com métodos
   `upsert`, `get`, `list_recent`.
3. **Hook no `CompositeOddsProvider`** — após cada chamada bem sucedida, enfileira
   write em `asyncio.Queue` para worker dedicado.
4. **Hook no `BetanoWSClient.subscribe_match` callback** — cada `MatchEvent`
   recebido vai pra fila de incidents.
5. **Workers async** — `odds_persistence_worker.py` e
   `incidents_persistence_worker.py` rodam paralelos ao orquestrador,
   consomem da fila, batcham inserts (10 por batch), commitam.
6. **Cache do `fixture_map`** dentro do `BetanoCatalog` — primeira resolução
   persiste, próximas lêem do cache local.
7. **Cleanup worker** — diariamente apaga `odds_history` > 90 dias e
   `incidents_history` > 180 dias (configurável).
8. **Queries úteis prontas** — `scripts/sql/queries/` com snippets para
   recall de drift, distribuição de pressure pre-incidente, etc.
9. **Healthcheck** — `scripts/db_healthcheck.py` testa as 3 tabelas e
   verifica que workers estão escrevendo.

---

## 4. Decisões críticas

### 4.1 Schema de `betano_fixture_map` — chave primária = fixture_id

```sql
CREATE TABLE IF NOT EXISTS betano_fixture_map (
  fixture_id        INT PRIMARY KEY,
  betano_event_id   BIGINT UNIQUE NOT NULL,
  sr_match_id       TEXT,
  opta_match_id     TEXT,
  home_team         TEXT,
  away_team         TEXT,
  league_id         INT,
  kickoff_utc       TIMESTAMPTZ,
  resolved_at       TIMESTAMPTZ DEFAULT NOW(),
  resolved_via      TEXT          -- 'fuzzy_match' | 'manual' | 'statsplayer'
);

CREATE INDEX IF NOT EXISTS ix_fxm_betano_event
  ON betano_fixture_map(betano_event_id);
```

### 4.2 Schema de `odds_history` — particionado por mês opcional

```sql
CREATE TABLE IF NOT EXISTS odds_history (
  id            BIGSERIAL PRIMARY KEY,
  fixture_id    INT NOT NULL,
  source        TEXT NOT NULL,         -- 'betano' | 'apifootball'
  market_kind   TEXT NOT NULL,         -- 'corners' | 'cards'
  market_code   TEXT,                  -- 'CNOU', 'TCOU', ''
  linha         NUMERIC(5,2),
  odd_over      NUMERIC(6,2),
  odd_under     NUMERIC(6,2),
  minute        INT,
  score_home    INT,
  score_away    INT,
  pressure_score    NUMERIC(5,2),      -- CPES próprio (do main.py)
  tension_score     NUMERIC(5,2),
  provider_pressure NUMERIC(5,2),      -- de Opta/Betano momentum
  captured_at   TIMESTAMPTZ DEFAULT NOW(),
  raw           JSONB
);

CREATE INDEX IF NOT EXISTS ix_oh_fixture_market_time
  ON odds_history(fixture_id, market_kind, captured_at DESC);
CREATE INDEX IF NOT EXISTS ix_oh_captured_at ON odds_history(captured_at);
```

**Particionamento por mês** opcional via `CREATE TABLE ... PARTITION BY RANGE`
se volume ficar pesado (>10M linhas).

### 4.3 Schema de `incidents_history` — UNIQUE em event_uid

```sql
CREATE TABLE IF NOT EXISTS incidents_history (
  id              BIGSERIAL PRIMARY KEY,
  fixture_id      INT,
  opta_match_id   TEXT NOT NULL,
  event_uid       TEXT NOT NULL,             -- hash determinístico
  event_type      INT NOT NULL,
  period_id       INT,
  minute          INT,
  seconds         INT,
  team_id         TEXT,
  player_id       TEXT,
  x               REAL,
  y               REAL,
  x_end           REAL,
  y_end           REAL,
  is_attack       BOOLEAN,
  is_dangerous_attack BOOLEAN,
  is_possession   BOOLEAN,
  is_dangerous    BOOLEAN,
  captured_at     TIMESTAMPTZ DEFAULT NOW(),
  raw             JSONB,
  UNIQUE (opta_match_id, event_uid)
);

CREATE INDEX IF NOT EXISTS ix_ih_fixture_minute
  ON incidents_history(fixture_id, minute);
CREATE INDEX IF NOT EXISTS ix_ih_opta_match
  ON incidents_history(opta_match_id);
```

**`event_uid`** = sha1 dos campos discriminantes:
```python
def event_uid(opta_match_id, team_id, player_id, minute, seconds, event_type, x, y):
    parts = f"{opta_match_id}|{team_id or ''}|{player_id or ''}|" \
            f"{minute}|{seconds}|{event_type}|{x or 0:.1f}|{y or 0:.1f}"
    return hashlib.sha1(parts.encode()).hexdigest()[:24]
```

Garante idempotência: WS re-conectado e re-enviando mesmos eventos não duplica.

### 4.4 Workers desacoplados via asyncio.Queue

```python
class OddsPersistenceWorker:
    def __init__(self, repo, queue_size=10000, batch_size=10,
                 batch_timeout_s=5):
        self._repo = repo
        self._q: asyncio.Queue = asyncio.Queue(maxsize=queue_size)
        self._batch_size = batch_size
        self._batch_timeout = batch_timeout_s
        self._stop = asyncio.Event()
        self._task: asyncio.Task | None = None

    def enqueue(self, entry: OddsHistoryEntry) -> None:
        try:
            self._q.put_nowait(entry)
        except asyncio.QueueFull:
            log.warning("odds_worker.queue_full — descarte (size=%d)",
                        self._q.qsize())

    async def start(self):
        self._task = asyncio.create_task(self._run())

    async def stop(self):
        self._stop.set()
        if self._task:
            await self._task

    async def _run(self):
        while not self._stop.is_set():
            batch = await self._collect_batch()
            if not batch:
                continue
            try:
                await self._repo.bulk_insert(batch)
                log.debug("odds_worker.flushed n=%d", len(batch))
            except Exception:
                log.exception("odds_worker.flush_error n=%d", len(batch))

    async def _collect_batch(self):
        batch = []
        try:
            first = await asyncio.wait_for(self._q.get(),
                                            timeout=self._batch_timeout)
            batch.append(first)
        except asyncio.TimeoutError:
            return batch
        while len(batch) < self._batch_size:
            try:
                batch.append(self._q.get_nowait())
            except asyncio.QueueEmpty:
                break
        return batch
```

Caller (Composite) chama `worker.enqueue(...)` — não bloqueia. Se a fila
estiver cheia, descarta com log de aviso (proteção contra back-pressure).

### 4.5 Hook no Composite — não bloqueia o caller

```python
class CompositeOddsProvider:
    def __init__(self, providers, drift_check=False,
                 persistence_worker=None):
        # ...
        self._persistence = persistence_worker

    async def _dispatch(self, method, fixture, score, market):
        # ... mesma lógica do Fase C ...

        if primary and self._persistence:
            entry = OddsHistoryEntry(
                fixture_id=fixture.fixture_id,
                source=primary.source,
                market_kind=market,
                market_code=primary.market_code,
                linha=primary.linha,
                odd_over=primary.odd_over,
                odd_under=primary.odd_under,
                minute=getattr(fixture, "minute", None),
                score_home=fixture.score_home,
                score_away=fixture.score_away,
                pressure_score=None,    # caller injeta após orchestrator calcular
                tension_score=None,
                provider_pressure=None,
                raw={"providers_results": [
                    {"name": n, "result": r.__dict__ if r else None}
                    for n, r in results
                ]},
            )
            self._persistence.enqueue(entry)

        return primary
```

### 4.6 Hook no WS callback — incidents

```python
async def on_match_event(me: MatchEvent):
    # ... uso normal pelo orchestrator (pressure_score etc) ...

    if incidents_worker:
        entry = IncidentHistoryEntry(
            fixture_id=resolve_fixture_id(me.sportsbook_match_id),
            opta_match_id=me.opta_match_id,
            event_uid=compute_event_uid(me),
            event_type=me.event_type,
            period_id=me.period_id,
            minute=me.minute,
            seconds=me.seconds,
            team_id=me.team_id,
            player_id=me.player_id,
            x=me.x, y=me.y, x_end=me.x_end, y_end=me.y_end,
            is_attack=me.is_attack,
            is_dangerous_attack=me.is_dangerous_attack,
            is_possession=me.is_possession,
            is_dangerous=me.is_dangerous,
            raw=me.raw,
        )
        incidents_worker.enqueue(entry)
```

### 4.7 Repositórios — bulk insert com ON CONFLICT DO NOTHING

```python
class IncidentsHistoryRepo:
    def __init__(self, pool):
        self._pool = pool

    async def bulk_insert(self, entries: list[IncidentHistoryEntry]):
        if not entries:
            return
        # SQL com VALUES múltiplos + ON CONFLICT
        sql = """
        INSERT INTO incidents_history (
            fixture_id, opta_match_id, event_uid, event_type, period_id,
            minute, seconds, team_id, player_id,
            x, y, x_end, y_end,
            is_attack, is_dangerous_attack, is_possession, is_dangerous,
            raw
        ) VALUES %s
        ON CONFLICT (opta_match_id, event_uid) DO NOTHING;
        """
        rows = [(
            e.fixture_id, e.opta_match_id, e.event_uid, e.event_type, e.period_id,
            e.minute, e.seconds, e.team_id, e.player_id,
            e.x, e.y, e.x_end, e.y_end,
            e.is_attack, e.is_dangerous_attack, e.is_possession, e.is_dangerous,
            json.dumps(e.raw),
        ) for e in entries]

        async with self._pool.acquire() as conn:
            # asyncpg: copy_records_to_table é mais rápido, mas perde ON CONFLICT
            # usamos executemany via execute_values equivalente
            await conn.executemany("""
                INSERT INTO incidents_history (...)
                VALUES ($1, $2, ..., $18)
                ON CONFLICT (opta_match_id, event_uid) DO NOTHING
            """, rows)
```

### 4.8 Cleanup worker — TTL configurável

```python
class CleanupWorker:
    """Roda 1x/dia. Apaga odds_history > 90d e incidents_history > 180d."""

    def __init__(self, pool, odds_ttl_days=90, incidents_ttl_days=180):
        self._pool = pool
        self._odds_ttl = odds_ttl_days
        self._incidents_ttl = incidents_ttl_days
        self._task: asyncio.Task | None = None

    async def start(self):
        self._task = asyncio.create_task(self._run())

    async def _run(self):
        while True:
            try:
                async with self._pool.acquire() as conn:
                    n_odds = await conn.execute(
                        f"DELETE FROM odds_history "
                        f"WHERE captured_at < NOW() - INTERVAL '{self._odds_ttl} days'"
                    )
                    n_inc = await conn.execute(
                        f"DELETE FROM incidents_history "
                        f"WHERE captured_at < NOW() - INTERVAL '{self._incidents_ttl} days'"
                    )
                    log.info("cleanup.done odds=%s incidents=%s", n_odds, n_inc)
            except Exception:
                log.exception("cleanup.error")
            await asyncio.sleep(86400)  # 24h
```

---

## 5. Componentes novos

### 5.1 `migrations/0001_betano_fixture_map.sql`

```sql
BEGIN;
CREATE TABLE IF NOT EXISTS betano_fixture_map (
  fixture_id        INT PRIMARY KEY,
  betano_event_id   BIGINT UNIQUE NOT NULL,
  sr_match_id       TEXT,
  opta_match_id     TEXT,
  home_team         TEXT,
  away_team         TEXT,
  league_id         INT,
  kickoff_utc       TIMESTAMPTZ,
  resolved_at       TIMESTAMPTZ DEFAULT NOW(),
  resolved_via      TEXT
);
CREATE INDEX IF NOT EXISTS ix_fxm_betano_event
  ON betano_fixture_map(betano_event_id);
COMMIT;
```

### 5.2 `migrations/0002_odds_history.sql`

```sql
BEGIN;
CREATE TABLE IF NOT EXISTS odds_history (
  id            BIGSERIAL PRIMARY KEY,
  fixture_id    INT NOT NULL,
  source        TEXT NOT NULL,
  market_kind   TEXT NOT NULL,
  market_code   TEXT,
  linha         NUMERIC(5,2),
  odd_over      NUMERIC(6,2),
  odd_under     NUMERIC(6,2),
  minute        INT,
  score_home    INT,
  score_away    INT,
  pressure_score    NUMERIC(5,2),
  tension_score     NUMERIC(5,2),
  provider_pressure NUMERIC(5,2),
  captured_at   TIMESTAMPTZ DEFAULT NOW(),
  raw           JSONB
);
CREATE INDEX IF NOT EXISTS ix_oh_fixture_market_time
  ON odds_history(fixture_id, market_kind, captured_at DESC);
CREATE INDEX IF NOT EXISTS ix_oh_captured_at
  ON odds_history(captured_at);
COMMIT;
```

### 5.3 `migrations/0003_incidents_history.sql`

```sql
BEGIN;
CREATE TABLE IF NOT EXISTS incidents_history (
  id              BIGSERIAL PRIMARY KEY,
  fixture_id      INT,
  opta_match_id   TEXT NOT NULL,
  event_uid       TEXT NOT NULL,
  event_type      INT NOT NULL,
  period_id       INT,
  minute          INT,
  seconds         INT,
  team_id         TEXT,
  player_id       TEXT,
  x               REAL, y REAL, x_end REAL, y_end REAL,
  is_attack       BOOLEAN,
  is_dangerous_attack BOOLEAN,
  is_possession   BOOLEAN,
  is_dangerous    BOOLEAN,
  captured_at     TIMESTAMPTZ DEFAULT NOW(),
  raw             JSONB,
  UNIQUE (opta_match_id, event_uid)
);
CREATE INDEX IF NOT EXISTS ix_ih_fixture_minute
  ON incidents_history(fixture_id, minute);
CREATE INDEX IF NOT EXISTS ix_ih_opta_match
  ON incidents_history(opta_match_id);
COMMIT;
```

### 5.4 `data/repositories/fixture_map.py`

```python
class FixtureMapRepo:
    def __init__(self, pool):
        self._pool = pool

    async def get_betano_event_id(self, fixture_id: int) -> int | None:
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT betano_event_id FROM betano_fixture_map WHERE fixture_id=$1",
                fixture_id,
            )
        return row["betano_event_id"] if row else None

    async def upsert(
        self, fixture_id: int, betano_event_id: int,
        sr_match_id: str | None = None,
        opta_match_id: str | None = None,
        home_team: str | None = None,
        away_team: str | None = None,
        league_id: int | None = None,
        kickoff_utc=None,
        resolved_via: str = "fuzzy_match",
    ):
        async with self._pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO betano_fixture_map
                  (fixture_id, betano_event_id, sr_match_id, opta_match_id,
                   home_team, away_team, league_id, kickoff_utc, resolved_via)
                VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9)
                ON CONFLICT (fixture_id) DO UPDATE
                  SET betano_event_id=EXCLUDED.betano_event_id,
                      sr_match_id=COALESCE(EXCLUDED.sr_match_id,
                                            betano_fixture_map.sr_match_id),
                      opta_match_id=COALESCE(EXCLUDED.opta_match_id,
                                              betano_fixture_map.opta_match_id);
            """, fixture_id, betano_event_id, sr_match_id, opta_match_id,
                home_team, away_team, league_id, kickoff_utc, resolved_via)
```

### 5.5 `data/repositories/odds_history.py`

```python
@dataclass(frozen=True)
class OddsHistoryEntry:
    fixture_id: int
    source: str
    market_kind: str
    market_code: str
    linha: float
    odd_over: float
    odd_under: float
    minute: int | None
    score_home: int | None
    score_away: int | None
    pressure_score: float | None
    tension_score: float | None
    provider_pressure: float | None
    raw: dict


class OddsHistoryRepo:
    def __init__(self, pool):
        self._pool = pool

    async def bulk_insert(self, entries: list[OddsHistoryEntry]):
        if not entries:
            return
        rows = [(
            e.fixture_id, e.source, e.market_kind, e.market_code,
            e.linha, e.odd_over, e.odd_under,
            e.minute, e.score_home, e.score_away,
            e.pressure_score, e.tension_score, e.provider_pressure,
            json.dumps(e.raw),
        ) for e in entries]
        async with self._pool.acquire() as conn:
            await conn.executemany("""
                INSERT INTO odds_history
                  (fixture_id, source, market_kind, market_code,
                   linha, odd_over, odd_under,
                   minute, score_home, score_away,
                   pressure_score, tension_score, provider_pressure, raw)
                VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14::jsonb)
            """, rows)

    async def list_recent_for_fixture(
        self, fixture_id: int, market_kind: str, limit: int = 50
    ) -> list[dict]:
        async with self._pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT * FROM odds_history
                WHERE fixture_id=$1 AND market_kind=$2
                ORDER BY captured_at DESC LIMIT $3
            """, fixture_id, market_kind, limit)
        return [dict(r) for r in rows]
```

### 5.6 `data/repositories/incidents_history.py`

Análogo, com `event_uid`. Inclui método `count_recent_dangerous_for_team`
útil para sanidade da pressão CPES vs incidents reais.

### 5.7 Workers

`data/persistence/odds_worker.py` + `incidents_worker.py` + `cleanup_worker.py`
seguem o template da decisão §4.4.

### 5.8 Wiring no orchestrator startup

```python
async def startup():
    pool = await asyncpg.create_pool(...)

    fixture_repo = FixtureMapRepo(pool)
    odds_repo = OddsHistoryRepo(pool)
    incidents_repo = IncidentsHistoryRepo(pool)

    odds_worker = OddsPersistenceWorker(odds_repo)
    incidents_worker = IncidentsPersistenceWorker(incidents_repo)
    cleanup = CleanupWorker(pool)

    await odds_worker.start()
    await incidents_worker.start()
    await cleanup.start()

    odds_provider, stats_provider, shutdown_providers = await build_providers(settings)
    # Composite agora recebe o worker como parâmetro
    odds_provider._persistence = odds_worker

    # ... resto do startup ...
```

### 5.9 `scripts/db_healthcheck.py`

```python
"""Healthcheck do DB e workers de persistência."""
async def main():
    pool = await asyncpg.create_pool(settings.DATABASE_URL)
    try:
        async with pool.acquire() as conn:
            for tbl in ["betano_fixture_map", "odds_history", "incidents_history"]:
                row = await conn.fetchrow(f"SELECT COUNT(*) AS n FROM {tbl}")
                print(f"{tbl}: {row['n']} rows")
                row = await conn.fetchrow(
                    f"SELECT MAX(COALESCE(captured_at, resolved_at)) AS last FROM {tbl}"
                )
                print(f"  last row: {row['last']}")
    finally:
        await pool.close()
```

### 5.10 Cache do `fixture_map` no `BetanoCatalog`

```python
class BetanoCatalog:
    # ... métodos da Fase B ...

    async def find_event_by_fixture(self, fixture_id, ..., fixture_repo=None):
        # 1. cache em memória
        if fixture_id in self._fixture_map:
            return self._fixture_map[fixture_id]
        # 2. DB (Fase D)
        if fixture_repo:
            ev = await fixture_repo.get_betano_event_id(fixture_id)
            if ev:
                self._fixture_map[fixture_id] = ev
                return ev
        # 3. fuzzy match
        # ... lógica da Fase B ...
        # ao final, se encontrou:
        if ev and fixture_repo:
            try:
                await fixture_repo.upsert(fixture_id, ev,
                                          home_team=team_home, away_team=team_away,
                                          league_id=league_id_hint,
                                          kickoff_utc=kickoff_at,
                                          resolved_via="fuzzy_match")
            except Exception:
                log.warning("fixture_repo.upsert.fail fixture=%d", fixture_id)
        return ev
```

### 5.11 Queries SQL prontas — `scripts/sql/queries/`

```sql
-- drift_summary_last_24h.sql
SELECT
  market_kind,
  COUNT(*) FILTER (WHERE source = 'betano') AS n_betano,
  COUNT(*) FILTER (WHERE source = 'apifootball') AS n_af,
  AVG(linha) FILTER (WHERE source = 'betano') AS avg_linha_betano,
  AVG(linha) FILTER (WHERE source = 'apifootball') AS avg_linha_af,
  AVG(odd_over) FILTER (WHERE source = 'betano') AS avg_over_betano,
  AVG(odd_over) FILTER (WHERE source = 'apifootball') AS avg_over_af
FROM odds_history
WHERE captured_at >= NOW() - INTERVAL '24 hours'
GROUP BY market_kind;

-- pressao_pre_escanteio.sql
-- Soma de incidents "dangerous_attack" nos 60s antes de cada escanteio gerado
WITH corners AS (
  SELECT opta_match_id, team_id, minute, seconds,
         (minute * 60 + seconds) AS t
  FROM incidents_history
  WHERE event_type = X /* descobrir event_type de corner com inspeção real */
)
SELECT c.opta_match_id, c.team_id, c.minute,
  (SELECT COUNT(*) FROM incidents_history i
   WHERE i.opta_match_id = c.opta_match_id
     AND i.team_id = c.team_id
     AND i.is_dangerous_attack
     AND (i.minute * 60 + i.seconds) BETWEEN c.t - 60 AND c.t) AS dang_atk_60s_before
FROM corners c;

-- bocais_resolvidos_por_dia.sql
SELECT DATE(resolved_at), COUNT(*),
       AVG(EXTRACT(EPOCH FROM (resolved_at - kickoff_utc)) / 60) AS avg_resolve_minutes
FROM betano_fixture_map
WHERE kickoff_utc IS NOT NULL
GROUP BY 1 ORDER BY 1 DESC;
```

---

## 6. Edge cases

| Caso | Comportamento |
|---|---|
| Queue cheia (descarte de odds entry) | Log warning; entrada perdida; pipeline segue |
| Worker crash | Task cancelada; reinicia no próximo startup; nada perdido em DB |
| DB indisponível | Worker tenta inserir, falha com log; entries acumulam até OOM em alta carga |
| Mesmo `event_uid` duas vezes (WS re-conectou) | ON CONFLICT DO NOTHING; sem duplicação |
| Composite chama Betano e AF; persiste apenas o primary | Decisão correta para evitar duplicação |
| `pressure_score` ainda não calculado quando persistimos | Salva `NULL`; backfill via script possível |
| Migration aplicada duas vezes | IF NOT EXISTS protege; CREATE INDEX idem |
| Cleanup deletando linhas que vão ser usadas no minuto seguinte | TTL é dias; impacto zero |
| Schema evoluiu (campo novo na Opta) | `raw JSONB` preserva tudo; migration adiciona coluna sem perda |

---

## 7. Testes

### 7.1 Unit (mocks de pool)

- [ ] `test_fixture_map_upsert_then_get`
- [ ] `test_fixture_map_upsert_preserves_existing_fields`
- [ ] `test_odds_history_bulk_insert_inserts_all`
- [ ] `test_incidents_history_bulk_insert_dedupes_by_event_uid`
- [ ] `test_event_uid_is_deterministic`
- [ ] `test_event_uid_differs_when_seconds_differ`

### 7.2 Worker

- [ ] `test_odds_worker_drains_queue_in_batches`
- [ ] `test_odds_worker_drops_when_full`
- [ ] `test_incidents_worker_handles_db_error_gracefully`
- [ ] `test_cleanup_worker_runs_within_24h`

### 7.3 Integração (Postgres real)

- [ ] `test_full_persistence_loop_with_real_pg`
- [ ] `test_idempotent_migrations_apply_twice`

---

## 8. Acceptance

- [ ] 3 migrations aplicadas (`betano_fixture_map`, `odds_history`,
      `incidents_history`)
- [ ] 3 repositories implementados com upsert/bulk_insert
- [ ] 3 workers async funcionais (odds, incidents, cleanup)
- [ ] Hook no `CompositeOddsProvider` enfileira após cada call
- [ ] Hook no callback do `BetanoWSClient.subscribe_match` enfileira incidents
- [ ] `BetanoCatalog.find_event_by_fixture` usa cache → DB → fuzzy match
- [ ] `event_uid` determinístico e único
- [ ] Healthcheck `db_healthcheck.py` mostra rows recentes
- [ ] 3 queries SQL prontas em `scripts/sql/queries/`
- [ ] Workers param graciosamente em shutdown (sem perda de batch parcial)
- [ ] Documentação `sistema-completo.md` §21 atualizada
- [ ] Testes unit + integração verdes (12+ testes)

---

## 9. Pilares cobertos

| Pilar | Contribuição |
|---|---|
| **Observabilidade** | Histórico completo de odds + incidents |
| **Determinismo** | Migrations idempotentes; event_uid hash |
| **Resiliência** | Queue isola pipeline crítico; ON CONFLICT dedup |
| **Custo** | Cleanup TTL evita crescimento ilimitado |
| **Suporte a evolução** | `raw JSONB` preserva campos não modelados |

---

## 10. Esforço estimado

| Sub-task | Horas |
|---|---|
| Migrations (3 arquivos) | 0.5 |
| Repositories (3 classes) | 2.0 |
| Workers (3 classes) | 1.5 |
| Hooks no Composite + WS | 1.0 |
| Cache fixture_map | 0.5 |
| Wiring startup | 0.5 |
| Healthcheck + queries SQL | 1.0 |
| Testes (12+) | 2.0 |
| Buffer | 1.0 |
| **Total** | **10h** |

---

## 11. Bloqueios potenciais

| Bloqueio | Resolução |
|---|---|
| `event_type` de Opta não documentado (qual é "corner"?) | Inspecionar incidents na fase pós-deploy; mapeamento em arquivo `data/static/opta_event_types.json` |
| Pool de DB saturado em alta carga | Aumentar `max_size` no pool; batchear mais agressivo (`batch_size=50`) |
| Volume de incidents enorme (centenas/min por jogo) | Sample (1 em cada 3); ou armazenar só `is_dangerous_attack=true` |
| Postgres rejeita NUMERIC com precisão errada | Schema com tolerância (5,2 e 6,2 já cobrem); validar no parser |

---

## 12. Out of scope

- ❌ Particionamento automático (manual, se necessário, mais tarde)
- ❌ Replicação read-replica
- ❌ Backups separados (uso da infra geral do projeto)
- ❌ Dashboards (Fase futura — usar Metabase/Grafana sobre as 3 tabelas)
- ❌ Migração de odds históricas antigas da API-Football
- ❌ Backfill de `pressure_score` em odds antigas (script opcional posterior)
