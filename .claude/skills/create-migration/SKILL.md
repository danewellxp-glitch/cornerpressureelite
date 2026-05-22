---
name: create-migration
description: Cria uma nova migration SQL do CPES (numerada, idempotente) e mostra como aplicar. Use quando precisar adicionar/alterar tabelas, colunas, indices ou constraints no Postgres do CPES.
disable-model-invocation: true
---

# Criar migration CPES

Migrations vivem em `corner-pressure-elite/migrations/NNNN_slug.sql` e rodam **idempotentes no boot** (`storage/database.py::_apply_sql_migrations`). Uma migration que falha ao re-rodar quebra o startup.

## Passos

1. **Descobrir o próximo número:**
   ```bash
   ls corner-pressure-elite/migrations/ | sort | tail -3
   ```
   Use o próximo número livre, 4 dígitos (`0018`, `0019`, ...).

2. **Criar o arquivo** `corner-pressure-elite/migrations/NNNN_slug.sql` com este esqueleto:
   ```sql
   -- NNNN (YYYY-MM-DD) — <titulo curto>
   --
   -- <o que faz + por que, 2-3 linhas>
   -- Idempotente. Sem DROP de dados de producao.

   BEGIN;

   -- exemplos (sempre IF NOT EXISTS / DROP IF EXISTS antes de ADD):
   -- ALTER TABLE <t> ADD COLUMN IF NOT EXISTS <col> <tipo> DEFAULT <safe>;
   -- CREATE TABLE IF NOT EXISTS <t> ( ... );
   -- CREATE INDEX IF NOT EXISTS idx_<...> ON <t>(<col>) WHERE <cond>;
   -- ALTER TABLE <t> DROP CONSTRAINT IF EXISTS <c>;
   -- ALTER TABLE <t> ADD CONSTRAINT <c> CHECK (...);

   COMMIT;
   ```

3. **Regras obrigatórias:**
   - Tudo idempotente: `IF NOT EXISTS` em create/add; `DROP CONSTRAINT IF EXISTS` antes de `ADD CONSTRAINT`.
   - Sem DROP destrutivo de coluna/tabela com dados (pergunte ao usuário — CLAUDE.md §11).
   - FK de `banca_movements.bet_id` → `user_signal_decisions(id)` (nunca `bets` legado).
   - Default seguro em coluna nova (não-null sem default quebra linhas existentes).

4. **Validar** com o subagent `migration-reviewer` (recomendado) antes de aplicar.

5. **Aplicar** (idempotente — pode rodar agora além do boot automático):
   ```bash
   docker exec -i cpes-postgres psql -U cpes_user -d cpes < corner-pressure-elite/migrations/NNNN_slug.sql
   ```

6. **Refletir no código:** se mudou modelo (`data/models.py`) ou repos, atualize-os. Mudança de schema → atualizar o repo correspondente em `data/repositories/`.

7. **Doc:** registrar em `docs/CHANGELOG.md` (e `docs/DECISIONS.md` se for decisão de design), conforme CLAUDE.md §12.
