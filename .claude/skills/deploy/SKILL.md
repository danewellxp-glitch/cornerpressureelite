---
name: deploy
description: Runbook de deploy do CPES (Docker Compose 5 serviços). Diz QUAL serviço rebuildar/reiniciar para cada tipo de mudança, com o cuidado da árvore suja e os passos de verificação. Use ao fazer deploy de qualquer mudança.
disable-model-invocation: true
---

# Deploy CPES

Topologia: `cpes-api` (FastAPI :8000), `cpes-main` (robô, sem porta), `cpes-dashboard` (Next :3001), `cpes-postgres`, `waha`. Build context do api/main/dashboard via `docker-compose.yml`.

## Regra-chave: o que precisa de rebuild vs restart

| Mudou | Ação |
|---|---|
| Arquivo em `corner-pressure-elite/data/**` ou `logs/**` | **bind-mounted** → vale no próximo boot do processo. `docker compose restart main api` (ou rebuild, tanto faz) |
| `corner-pressure-elite/main.py`, `config.py`, `api_server.py`, `engine/**`, `workers/**`, `notifier/**` | NÃO são bind-mount → **rebuild**: `docker compose up -d --build main` (e/ou `api`) |
| Frontend (`dashboard/**`) | source compilado na imagem → **rebuild**: `docker compose up -d --build dashboard` |
| Migration SQL | aplicar (`docker exec -i cpes-postgres psql ... < migration`) — roda idempotente no boot tb |
| `.env` | `docker compose up -d` (recria com novo env) |

## ⚠️ Cuidado crítico: árvore suja no rebuild do dashboard
`docker compose up --build dashboard` empacota a **árvore inteira atual**, não só o que você mudou. Em 2026-05-20 isso deployou WIP não-commitada de terceiros e regrediu o layout (ver `docs/BUGS.md`).
**Antes de rebuildar o dashboard:** `git status dashboard/` e confirme que TODA a WIP deve ir pra imagem. (O hook `guard-build.sh` bloqueia esse caso — é proposital.)

## Passos de deploy
1. **Decida o(s) serviço(s)** pela tabela acima.
2. Se for dashboard com árvore suja → checar `git status dashboard/` primeiro.
3. Rebuild/restart:
   ```bash
   docker compose up -d --build <servico>     # rebuild
   # ou
   docker compose restart <servico>           # so restart (mudancas em data/)
   ```
4. **Verificar boot** (esperar ~15s):
   ```bash
   docker ps --format '{{.Names}} | {{.Status}}'
   docker logs --since 30s cpes-main 2>&1 | grep -iE "Ligas monitoradas|ativo|error|traceback"
   docker exec cpes-dashboard sh -c "wget -qO- --server-response http://localhost:3001/login 2>&1 | head -1"  # 200/307 = ok
   ```
5. Erros conhecidos a IGNORAR no log: `bridge /events/live 503` (bridge Betano externo), `get_fixture_result_cards` (bug pré-existente de cartões), WAHA `getChat`/422 transiente no boot.
6. **Rollback rápido** (se um rebuild quebrou): a imagem anterior fica dangling — `docker images -a`, `docker tag <id_anterior> cornerpressureelite-<svc>:latest`, `docker compose up -d --no-build --force-recreate <svc>`.
7. **Doc:** registrar em `docs/CHANGELOG.md` (CLAUDE.md §12).

## Notas
- `docker compose up --build dashboard` pode **recriar o cpes-api junto** (dependência do compose) — é efeito colateral conhecido, o api volta.
- Restart do `cpes-main` interrompe o monitoramento ~1min (recupera sozinho).
