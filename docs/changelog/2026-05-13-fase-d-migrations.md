# 2026-05-13 — Fase D: migrations de persistência Betano aplicadas

> Implementa o primeiro passo da cronologia do pivot Betano
> (`docs/sprints/README.md` §"Cronologia de execução sugerida" item 1):
> aplicar as migrations da Fase D primeiro, independente das fases A/B/C.

## O que foi feito

1. Criados 3 arquivos SQL idempotentes em
   `corner-pressure-elite/migrations/` conforme §5.1-5.3 de
   `docs/sprints/2026-05-12-betano-fase-D-persistencia-historica.md`:
   - `0001_betano_fixture_map.sql` — mapping `fixture_id` (API-Football) ↔
     `event_id` (Betano) + `sr_match_id` / `opta_match_id` / metadados.
   - `0002_odds_history.sql` — histórico granular de odds capturadas (Betano +
     API-Football) com `pressure_score` / `tension_score` / `provider_pressure`.
   - `0003_incidents_history.sql` — eventos Opta granulares (X/Y, attack flags)
     com `UNIQUE (opta_match_id, event_uid)` para dedupe.
2. Adicionado loader idempotente `Database._apply_sql_migrations` em
   `corner-pressure-elite/storage/database.py:269-285` que lê
   `migrations/*.sql` em ordem lexicográfica ao final de `init()`. Garante que
   próximos startups aplicam migrations novas sem rebuild.
3. Script standalone `corner-pressure-elite/scripts/run_migrations.py` para
   aplicação ad-hoc fora do ciclo de startup.
4. Migrations aplicadas em produção via
   `docker exec -i cpes-postgres psql -U cpes_user -d cpes < <arquivo>`.
   Re-rodadas em seguida — somente `NOTICE … skipping`, idempotência verde.

## Verificação

```bash
docker exec -i cpes-postgres psql -U cpes_user -d cpes -c "\\d betano_fixture_map"
docker exec -i cpes-postgres psql -U cpes_user -d cpes -c "\\d odds_history"
docker exec -i cpes-postgres psql -U cpes_user -d cpes -c "\\d incidents_history"
```

Todas as 3 tabelas existem com colunas, índices e constraints conforme spec.

## Não feito (próximos passos)

- Repositories (`data/repositories/{fixture_map,odds_history,incidents_history}.py`)
- Workers async (`OddsPersistenceWorker`, `IncidentsPersistenceWorker`, `CleanupWorker`)
- Hooks no `CompositeOddsProvider` e callback do `BetanoWSClient`
- Wiring no orchestrator startup
- Healthcheck `scripts/db_healthcheck.py`
- Queries SQL em `scripts/sql/queries/`

Esses passos dependem das Fases A/B/C estarem implementadas (providers Betano e
Composite ainda não existem). Voltar à Fase D após concluir A → B → C.

## Referências

- Harness: `docs/sprints/2026-05-12-betano-fase-D-persistencia-historica.md`
- Master: `docs/sprints/2026-05-12-betano-discovery-master.md`
- README do pacote: `docs/sprints/README.md`
