# 2026-05-13 — Fase D: Persistência Histórica completa

> Continuação da Fase D (migrations já aplicadas em
> `docs/changelog/2026-05-13-fase-d-migrations.md`): repositories, workers,
> hooks, healthcheck e queries SQL.
>
> **Harness:** `docs/sprints/2026-05-12-betano-fase-D-persistencia-historica.md`.

## O que foi feito

### Módulos novos

```
corner-pressure-elite/
├── data/
│   ├── repositories/
│   │   ├── __init__.py
│   │   ├── fixture_map.py          # FixtureMapRepo.upsert / get_betano_event_id
│   │   ├── odds_history.py         # OddsHistoryRepo.bulk_insert + Entry
│   │   └── incidents_history.py    # IncidentsHistoryRepo + Entry + event_uid()
│   └── persistence/
│       ├── __init__.py
│       ├── _base.py                # _BaseBatchWorker (queue + batch + flush)
│       ├── odds_worker.py          # OddsPersistenceWorker + enqueue_from_dispatch
│       ├── incidents_worker.py     # IncidentsPersistenceWorker + make_ws_callback
│       └── cleanup_worker.py       # CleanupWorker diário (TTL configurável)
└── scripts/
    ├── db_healthcheck.py
    └── sql/queries/
        ├── drift_summary_last_24h.sql
        ├── pressao_pre_incidente.sql
        └── fixtures_resolvidos_por_dia.sql
```

### Wiring

- **`CompositeOddsProvider`** (Fase C) já aceita `persistence_worker` no
  construtor. Quando recebe um `OddsPersistenceWorker`, chama
  `worker.enqueue_from_dispatch(...)` após cada dispatch, sem bloquear.
- **`BetanoOddsProvider._resolve_event_id`** (Fase C) consulta
  `FixtureMapRepo.get_betano_event_id` antes do fuzzy match; em hit do
  catalog, faz upsert via repo. Catalog também recebe `prime_fixture_map`
  para sincronizar.
- **`IncidentsPersistenceWorker.make_ws_callback`** retorna uma callback
  pronta para o `BetanoWSClient.subscribe_match(event_id, on_event=...)`. O
  caller injeta `fixture_id_for(opta_match_id) -> int | None`.
- **`CleanupWorker`** roda 1×/dia (configurável). TTL: odds_history 90d,
  incidents_history 180d. Pode rodar avulso via `await worker.run_once()`.

### Testes (Fase D)

- `tests/test_persistence_workers.py` — **11 unit tests**:
  - `OddsPersistenceWorker`: drain, queue cheia (descarte), continua após
    erro de flush, `enqueue_from_dispatch` serializa CanonicalOverUnder.
  - `event_uid`: determinístico, difere por segundos, None ≡ "".
  - `IncidentsPersistenceWorker`: drain, callback WS gera entry com
    `event_uid` correto e flags propagadas.
  - `CleanupWorker._parse_delete_status`: extrai `n` de "DELETE n".
- `tests/test_repositories.py` — **5 unit tests** com `_FakePool`:
  - `FixtureMapRepo.upsert` emite `ON CONFLICT (fixture_id) DO UPDATE`.
  - `FixtureMapRepo.get_betano_event_id` retorna int ou None.
  - `OddsHistoryRepo.bulk_insert` emite N rows com 14 colunas.
  - Empty insert é noop.
  - `IncidentsHistoryRepo.bulk_insert` inclui
    `ON CONFLICT (opta_match_id, event_uid) DO NOTHING`.

Total Fase D: **16 unit tests verdes** (incluindo os de migration / healthcheck
helpers).

## Decisões e ajustes vs spec

1. **Worker base genérico** (`_BaseBatchWorker`): odds/incidents/cleanup
   compartilham o mesmo padrão (queue → batch → flush → log). Reduz
   duplicação e centraliza políticas de drain/stop.

2. **`enqueue_from_dispatch` é método do worker**, não do composite. Mantém
   o Composite agnóstico de schemas de DB; basta o worker quack-implementar
   o método.

3. **`event_uid` é função pura** em `repositories/incidents_history.py`
   (não no schema do `MatchEvent`) — mais simples de testar e mantém
   determinismo independente do payload bruto.

4. **`CleanupWorker.run_once()`** exposto separadamente: permite invocar via
   admin endpoint ou cron externo se preferir.

5. **`scripts/sql/queries/`** prontas mas não wired em endpoint: cabe a
   sprints futuras decidir se viram /api/admin/drift-summary, dashboard, ou
   só ficam para debug ad-hoc.

## Verificação

```bash
cd corner-pressure-elite
python3 -m pytest tests/test_persistence_workers.py tests/test_repositories.py -v
# 16 passed

# Quando container estiver up e migrations aplicadas:
docker exec -it cpes-api python scripts/db_healthcheck.py
```

## Acceptance — §8 do harness

- [x] 3 migrations aplicadas (anterior changelog)
- [x] 3 repositories implementados com upsert/bulk_insert
- [x] 3 workers async funcionais (odds, incidents, cleanup)
- [x] Hook no `CompositeOddsProvider` enfileira após cada call
- [x] Hook no callback do `BetanoWSClient.subscribe_match` enfileira incidents
- [x] `BetanoCatalog.find_event_by_fixture` usa cache → DB → fuzzy match
      (via `_resolve_event_id` no `BetanoOddsProvider` + `prime_fixture_map`)
- [x] `event_uid` determinístico e único
- [x] Healthcheck `db_healthcheck.py` lista as 3 tabelas
- [x] 3 queries SQL prontas em `scripts/sql/queries/`
- [x] Workers param graciosamente em shutdown (drain do remanescente)
- [ ] Documentação `sistema-completo.md` §21 — alvo ainda não existe
- [x] Testes unit (16+ Fase D, 72 totais do pivot)

## Não feito (próximos passos)

- **Wiring no startup do orquestrador**: ainda não há um único ponto onde
  o `main.py` / `api_server.py` instancia o pool, os repos e os workers e
  passa para o `build_providers(...)`. Sprint dedicada quando
  `USE_NEW_PROVIDERS` for ligado.
- **Integração com Postgres real** dos testes: os repos usam `_FakePool` —
  uma sessão de teste com container `cpes-postgres` (ou `testcontainers`)
  validaria SQL real. Deixar para sprint de hardening.
- **Particionamento por mês** de `odds_history` se volume crescer >10M
  linhas (out-of-scope §12 do harness).

## Referências

- Harness: `docs/sprints/2026-05-12-betano-fase-D-persistencia-historica.md`
- Migrations: `docs/changelog/2026-05-13-fase-d-migrations.md`
- Fase C (Composite providers): `docs/changelog/2026-05-13-fase-c-pipeline-refactor.md`
