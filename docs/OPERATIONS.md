# RUNBOOK OPERACIONAL

Comandos pra subir, derrubar, validar, fazer recovery. **Quando algo quebra às 3am, segue runbook sem pensar.**

> **Escopo:** quick-reference operacional. Setup detalhado de ambiente vai em `docs/setup/`. Deploy completo vai em `docs/manuals/DEPLOYMENT.md`.

## Stack systemd (uso normal)

3 user units encadeadas via `Requires/After`. `loginctl enable-linger daniel` já habilitado. Sobem no boot automaticamente. Units versionadas em `~/cpes-bridge/systemd/`.

```bash
# Subir tudo (chain Requires sobe xvfb → chrome → bridge)
systemctl --user start cpes-bridge.service

# Status
systemctl --user status xvfb-bridge chrome-bridge cpes-bridge --no-pager

# Restart limpo
systemctl --user restart cpes-bridge.service

# Parar tudo
systemctl --user stop cpes-bridge.service chrome-bridge.service xvfb-bridge.service

# Logs em tempo real
journalctl --user -u cpes-bridge.service -f
tail -f ~/cpes-bridge/bridge.log
tail -f ~/cpes-bridge/chrome-systemd.log
```

`Restart=always` em todas — qualquer crash ou kill externo restarta em ≤15s.

## Subir bridge manualmente (fallback de emergência)

Usar só se systemd estiver indisponível ou pra debug interativo:

```bash
# 1. Xvfb :100
if ! pgrep -u daniel -f "Xvfb.*:100" > /dev/null; then
    nohup Xvfb :100 -screen 0 1920x1080x24 > /tmp/xvfb-100.log 2>&1 &
    disown
    sleep 2
fi

# 2. Chrome local :9223 (limpa lock files antes)
rm -f /home/daniel/chrome-betano-test-profile/Singleton{Lock,Cookie,Socket}
DISPLAY=:100 nohup google-chrome-stable \
    --user-data-dir=/home/daniel/chrome-betano-test-profile \
    --remote-debugging-port=9223 \
    --remote-debugging-address=0.0.0.0 \
    --no-first-run \
    --no-default-browser-check \
    --disable-gpu \
    --disable-dev-shm-usage \
    --lang=pt-BR \
    > /tmp/chrome-local.log 2>&1 &
disown
sleep 5

# 3. Bridge FastAPI
cd ~/cpes-bridge
nohup .venv/bin/python server.py > bridge.log 2>&1 &
disown
sleep 4

# 4. Validar
curl -s http://localhost:8080/pool/status | python3 -m json.tool
```

## Validar saúde do sistema

```bash
# Pool
curl -s http://localhost:8080/pool/status | python3 -m json.tool

# Container CPES
docker ps | grep cpes-main

# DB
docker exec cpes-postgres psql -U cpes_user -d cpes -c \
  "SELECT COUNT(*), MAX(captured_at) FROM odds_history;"
```

## Listar jogos elegíveis pra smoke

```bash
docker exec cpes-main python3 -c "
import os, httpx
from config import LIGAS_MONITORADAS
ids = [l['id'] for l in LIGAS_MONITORADAS]
r = httpx.get('https://v3.football.api-sports.io/fixtures',
    params={'live': 'all'},
    headers={'x-apisports-key': os.getenv('API_FOOTBALL_KEY')}, timeout=15.0)
data = r.json()
for f in data.get('response', []):
    lid = f['league']['id']
    m = f['fixture']['status']['elapsed'] or 0
    if lid in ids and m >= 15:
        print(f\"{f['fixture']['id']} | min {m} | {f['teams']['home']['name']} x {f['teams']['away']['name']} | {f['league']['name']}\")
"
```

## Smoke real Fase D.0

```bash
# Pegar event_id da URL Betano do jogo escolhido
export USE_BETANO_BRIDGE=true
export BETANO_EVENT_MAP="<FIXTURE>=<EVENT>"

docker compose stop main
docker compose up -d --build main
sleep 8

docker logs -f cpes-main 2>&1 | grep -iE "telemetria|composite|enqueue|sinal"
```

## Investigação técnica de scraping (regras)

Antes de qualquer sessão de exploração / scraping novo apontando pra Betano (ou outro alvo Cloudflare), seguir [`architecture/playwright-anti-bot-checklist.md`](architecture/playwright-anti-bot-checklist.md). Em resumo:

- **Mapear endpoint novo / schema desconhecido** → mitmproxy no PC humano, NÃO Playwright
- **Validar URL** → navegador humano, NÃO `goto()` em loop
- **Extrair de URL conhecida** → Playwright via bridge **com throttling ≥30s + jitter**
- **Polling de API descoberta** → `httpx` direto, Chrome só pra renovar cookies
- **Smoke test ad-hoc em produção** → ❌ proibido sem mitmproxy primeiro

Detecção em runtime: se `page.title()` contiver "Splash Screen" ou body mencionar "restricted/compliance", **parar imediatamente** — cada retry adicional reforça o flag (TTL 12-24h).

Recovery se IP flagueado: aguardar 12-24h. Se persistir, trocar IP (modem off 1h) e recriar profile. Detalhes em [`BUGS.md`](BUGS.md#2026-05-15--ip-residencial-flagueado-pela-cloudflare-bot-management).

## Recovery após reboot acidental

Com systemd ativo (após 2026-05-15), o stack do bridge sobe sozinho no boot. Validar:

1. **Pool**: `curl -s http://localhost:8080/pool/status | python3 -m json.tool` — esperar 2/2 healthy.
2. **Status systemd**: `systemctl --user is-active xvfb-bridge chrome-bridge cpes-bridge` — esperar 3× active.
3. **WAHA intacto**: `docker ps | grep waha` (auto-restart Docker).
4. **CPES container**: `docker ps | grep cpes-main` (auto-restart Docker).
5. Se algum service falhou: `journalctl --user -u <service> -n 50 --no-pager` pra diagnosticar.

Se systemd não subiu (extremamente raro): seguir "Subir bridge manualmente (fallback de emergência)" acima.

## Restart preventivo Brave do pool (danewell)

Brave do pool degrada após ~24-40h de uptime — `fetch()` interno retorna
`TypeError: Failed to fetch` mesmo com CDP `/json/version` respondendo OK
(visto 3× em 2026-05-15 a 17). Renewer retorna **HTTP 502** silencioso,
P5 bloqueia todos os sinais até manutenção manual.

**Mitigação P4 quick-win (2026-05-17): cron a cada 12h**

- Script: `/home/danewell/restart-brave.sh` (snapshot em `docs/setup/danewell-brave-restart.sh`)
- Crontab: `0 4,16 * * *` (04:00 e 16:00 BRT — madrugada + pré-jogos noturnos)
- Log: `/tmp/brave-cron.log`
- Preserva profile (`/home/danewell/brave-betano-profile/`) → cookies CF intactos
- Downtime: ~15-20s por restart × 2 dia = ~40s/dia (0.05%)

**Restart manual ad-hoc** (qualquer momento, se renewer 502):
```bash
ssh danewell 'bash /home/danewell/restart-brave.sh'
# Validar:
curl -s --max-time 30 -o /dev/null -w "HTTP %{http_code}\n" \
  http://192.168.1.5:8081/danae/event/85162739/state
# Esperado: HTTP 200
```

**Pendência P4 PARTE 1** (supervisor reativo): `/health/deep` no renewer +
`BraveSupervisor` daemon (30s interval, 2 threshold, 10min cooldown). Cobre
o gap entre os 12h preventivos — degradação imprevista. Quick-win cron
resolve ~90% dos casos enquanto supervisor não chega.

## Troubleshooting comum

**"Fixture descoberto via D.2 mas com poucas capturas em `odds_history`"**

Provavelmente está em `pre_janela` (minuto < 50 E corners < 7). Não é bug — `adaptive_polling` decide não gastar requisição nessa fase. Validar:

```bash
# Checar minuto atual do fixture
docker exec cpes-main python -c "
import asyncio
from data.api_client import APIFootballClient
from utils.rate_limiter import RateLimiter
from config import API_FOOTBALL_KEY, API_DAILY_LIMIT, LIGAS_MONITORADAS
async def main():
    rl = RateLimiter(max_requests_per_day=API_DAILY_LIMIT, max_requests_per_minute=30)
    client = APIFootballClient(API_FOOTBALL_KEY, rl)
    live = await client.get_live_fixtures([l['id'] for l in LIGAS_MONITORADAS])
    for f in live:
        if f['fixture']['id'] in {<FIXTURE_IDS>}:
            print(f\"{f['fixture']['id']} | {f['fixture']['status']['short']} elapsed={f['fixture']['status'].get('elapsed')}min\")
asyncio.run(main())
"
```

Se `elapsed < 50` e corners < 7, aguardar — capturas escalam pra 50+ automaticamente quando entrar em `na_janela`. Detalhes em [`BUGS.md`](BUGS.md#2026-05-16--falso-bug-discovery-sem-capturas-iniciais-é-normal).

## tests/ não monta no container `cpes-api` / `cpes-main` (Fase E.1)

**Sintoma:** `docker exec cpes-api ls /app/tests` → "No such file or directory".
Tentativas de rodar `pytest` dentro do container falham.

**Causa:** `corner-pressure-elite/.dockerignore` (linha `tests`) **exclui o
diretório do build context**. O `COPY . .` do Dockerfile não copia tests, e
docker-compose.yml **não tem bind mount** pra tests/.

**Por que está assim:** decisão consciente — imagem prod fica menor (sem
suite de testes). Mas atrapalha debugging on-host pelo container.

**Workaround pra dev/debug** (não comitar — só local):

```bash
# Opção A: copiar pontual via docker cp (sumirá no próximo rebuild)
docker cp corner-pressure-elite/tests cpes-api:/app/tests
docker exec cpes-api python -m pytest /app/tests/test_public_ticker.py

# Opção B: adicionar bind volume só no override local
cat > docker-compose.override.yml <<'YAML'
services:
  api:
    volumes:
      - ./corner-pressure-elite/tests:/app/tests:ro
  main:
    volumes:
      - ./corner-pressure-elite/tests:/app/tests:ro
YAML
docker compose up -d --force-recreate api main
```

**Recomendação canônica:** rodar pytest **no host** (não no container).
`python3 -m pytest corner-pressure-elite/tests/` funciona porque toda
dependência do CPES já está instalada globalmente no odin (`python3 -c
"import asyncpg, fastapi" → ok`).

## Fase E.1 — Stats Betano operacional

Pipeline canônico de stats agora consome `bridge:8080/event/<id>/state` (Betano /danae-webapi) com fallback automático API-Football via Composite cascade. Ativado em produção 2026-05-17.

### Toggle `USE_BETANO_STATS`

Ativar (default produção desde 2026-05-17):
```bash
grep -q "^USE_BETANO_STATS" corner-pressure-elite/.env || \
  echo 'USE_BETANO_STATS=true' >> corner-pressure-elite/.env
docker compose up -d --force-recreate main
```

Reverter pra AF puro (modo degradado, debug):
```bash
sed -i '/^USE_BETANO_STATS/d' corner-pressure-elite/.env
docker compose up -d --force-recreate main
```

Confirmar wiring ativo:
```bash
docker logs cpes-main 2>&1 | grep -E "BetanoStatsWorker|bridge_stats enabled" | head -3
# Esperado: 3 linhas (factory + bridge_stack + Worker ativo)
```

### Monitoramento

Capturas por source na última hora (saudável: `bridge_betano > apifootball` 5-10×):
```bash
docker exec cpes-postgres psql -U cpes_user -d cpes -c \
  "SELECT source, COUNT(*) FROM stats_history
   WHERE captured_at > NOW() - INTERVAL '1 hour'
   GROUP BY source;"
```

Alerta: `apifootball >> bridge_betano` em janela longa → bridge degradado ou Brave precisa de warmup.

Latência do bridge nos últimos polls:
```bash
tail -200 ~/cpes-bridge/bridge.log | grep "event_state" | tail -10
# elapsed=7-10s normal; >15s consistente = degradação
```

### Warmup do Brave pool

Após restart do `danewell-renewer` ou Brave, aguardar **~10min** antes de validar bridge_betano. Durante warmup, Composite cai em AF naturalmente (não é bug — Brave precisa aquecer cookies CF + sessão).

Sinais de warmup em andamento:
```bash
docker logs cpes-main 2>&1 | grep "bridge_stats.http_error" | tail -10
# Status 502/503 consistente em primeiros ciclos = warmup
```

Confirmar primário operacional:
```bash
tail -50 ~/cpes-bridge/bridge.log | grep "event_state.*status=200" | tail -5
# Mix 200 OK = bridge ok
```

### Renewer 502 troubleshooting (`/danae/event/<id>/state`)

**Sintoma:** body do 502 contém `"fetch falhou no Chrome: TypeError: Failed to fetch"`.

**Diagnóstico em ordem:**

1. `/health` do renewer responde?
   ```bash
   curl -s http://192.168.1.5:8081/health | jq
   ```
2. `/danae/live` (D.1) também afetado? (Se sim, escopo > E.1)
   ```bash
   curl -s -w "\nHTTP %{http_code}\n" "http://192.168.1.5:8081/danae/live?sport=FOOT" | tail -3
   ```
3. Chrome/Brave responsivos via CDP?
   ```bash
   curl -s http://192.168.1.5:9223/json/version | jq .Browser
   ```
4. Cookies `_cfuvid` stale? (3+ dias = provável)

**Fixes possíveis (em ordem):**
1. Aguardar 10min warmup
2. SSH danewell + `systemctl --user restart danewell-renewer`
3. Refresh cookies CF (warmup manual via SPA)
4. Restart Brave (último recurso) + aguardar warmup

### Limites operacionais

| Parâmetro | Default | Notas |
|---|---|---|
| `STATS_POLL_INTERVAL_SEC` | 15 | Base do worker. Bridge cache TTL=3s << poll, cache 304 hoje é dead-code (otimização futura). |
| `STATS_WINDOW_HISTORY_SIZE` | 120 | ~30min em memória @ 15s/poll. Cobre janelas 5/10min com folga. |
| `STATS_BOOTSTRAP_LOOKBACK_MIN` | 20 | Lookback pra hidratar calculator em restart. |
| Capacidade segura | **8-10 jogos simultâneos** | Sem ajuste. Acima: aumentar poll_interval pra 20-30s OU adicionar Chrome ao pool. |

### Stats history — schema rápido

`stats_history` (migration `0005_stats_history.sql`) tem 29 colunas:
- canonical: `fixture_id`, `source`, `minute`, `score_*`, `corners_*`, `yellow_cards_*`, `red_cards_*` etc.
- Fase E.1: `version` (snapshot Betano), `second_since_start` (clock granular), `corners_last_5/10min`, `yellow_last_5/10min` (janelas calculadas pelo `StatsWindowCalculator`)
- `raw->>'freshness'` ∈ `{'fresh', 'cached'}` pra auditoria de cache hits
- UNIQUE parcial `(fixture_id, source, version) WHERE version IS NOT NULL` previne dup de mesma versão Betano (defesa contra race do bridge cache).

## Fase F — Events Betano operacional

`BetanoEventsWorker` captura `event.incidents[]` do mesmo endpoint
`/event/<id>/state` usado pelo `BridgeStatsAdapter` (E.1). **Dataset puro**
— `decision_engine` NÃO consome, persistência paralela alimenta Quant
H1-H4. Ativado em produção 2026-05-17.

### Toggle `USE_BETANO_EVENTS`

Ativar:
```bash
grep -q "^USE_BETANO_EVENTS" corner-pressure-elite/.env || \
  echo 'USE_BETANO_EVENTS=true' >> corner-pressure-elite/.env

# IMPORTANTE: configs novas em config.py exigem REBUILD (não só recreate)
docker compose up -d --build main
```

Reverter:
```bash
sed -i '/^USE_BETANO_EVENTS/d' corner-pressure-elite/.env
docker compose up -d --force-recreate main
```

Confirmar wiring ativo:
```bash
docker logs cpes-main 2>&1 | grep -E "BetanoEventsWorker|providers.events_stack" | head -3
# Esperado:
# providers.events_stack primary=bridge_betano fallback=apifootball bridge_url=...
# BetanoEventsWorker ativo — events via bridge (Fase F)
```

### Monitoramento

Capturas por source × type na última hora:
```bash
docker exec cpes-postgres psql -U cpes_user -d cpes -c \
  "SELECT source, event_type, COUNT(*) AS events
   FROM events_history
   WHERE captured_at > NOW() - INTERVAL '1 hour'
   GROUP BY source, event_type
   ORDER BY source, event_type;"
```

Saudável: `bridge_betano` dominante quando renewer alive, `apifootball`
durante warmup ou degradação.

Dedup funcionando (sempre 0 duplicates):
```bash
docker exec cpes-postgres psql -U cpes_user -d cpes -c \
  "SELECT fixture_id, source, event_type, event_minute, team_side, COUNT(*) AS dups
   FROM events_history
   WHERE captured_at > NOW() - INTERVAL '1 hour'
   GROUP BY 1,2,3,4,5
   HAVING COUNT(*) > 1;"
# Esperado: zero linhas
```

### Rebuild vs recreate (gotcha)

**Configs novas em `config.py` exigem rebuild da imagem.** `docker compose
up -d --force-recreate main` só recria o container com a mesma imagem —
configs novas no `config.py` ficam invisíveis (`AttributeError: module
'config' has no attribute 'USE_BETANO_EVENTS'`).

Sintoma típico: container sobe sem erro, mas `BetanoEventsWorker ativo`
não aparece nos logs apesar de `USE_BETANO_EVENTS=true` no env. Validação:
```bash
docker exec cpes-main python3 -c "import config; print(config.USE_BETANO_EVENTS)"
# Se AttributeError: precisa rebuild
```

**Fix:**
```bash
docker compose up -d --build main
```

### Throttle 30s e implicação

`EVENTS_POLL_INTERVAL_SEC=30` (default) significa: evento individual pode
aparecer em `events_history` com defasagem de até 30s do real-time.
Aceitável pra dataset histórico (auditoria pós-jogo, H2-H4). Insuficiente
se `decision_engine` futuro precisar reagir a eventos em tempo real —
exigirá refactor (poll dedicado, intervalo menor, OU WebSocket Fase E.2).

### Events history schema rápido

`events_history` (migration `0006_events_history.sql`) tem 11 colunas:
- `fixture_id`, `source`, `event_type`, `event_minute`, `event_second` (opt)
- `team_side` ∈ `{home, away, NULL}` (CHECK constraint)
- `player_name` (opt — só AF preenche atualmente)
- `props` JSONB, `raw` JSONB (incident original preservado)
- `captured_at`
- UNIQUE dedup `(fixture, source, type, minute, side, player)` — dedup
  natural via `ON CONFLICT DO NOTHING` no `upsert_batch`.

Types canônicos: `GOAL`, `YELL`, `RCRD`, `CRNR`, `OFFS`, `SUBS`, `PENL`,
`PBEG`, `PEND`, `EBEG`, `StoppageTime`, `Aggregated`, `VAR`, `CGOL`
(gol cancelado). Mapping AF → canônico em
`data/providers/apifootball/events_adapter.py::_AF_TYPE_MAP`. Combinações
não mapeadas viram fallback `af_type.upper()` + log WARNING — review
semanal pra detectar tipos novos AF.


## Fase G.1 — Lineups Betano operacional

`BetanoLineupsWorker` captura `event.roster` (formation + startXI +
benchPlayers + squad) do **mesmo** endpoint `/event/<id>/state` usado
por E.1 e F (CASO α puro — zero nova request HTTP). **Dataset puro**
— `decision_engine` NÃO consome; alimenta Quant H2-H4 (formation,
qualidade XI, profundidade bench). Ativado em produção 2026-05-17.

### Toggle `USE_BETANO_LINEUPS`

Ativar:
```bash
grep -q "^USE_BETANO_LINEUPS" corner-pressure-elite/.env || \
  echo 'USE_BETANO_LINEUPS=true' >> corner-pressure-elite/.env

docker compose up -d --build main   # configs novas exigem REBUILD
```

Reverter:
```bash
sed -i '/^USE_BETANO_LINEUPS/d' corner-pressure-elite/.env
docker compose up -d --force-recreate main
```

Confirmar wiring ativo:
```bash
docker logs cpes-main 2>&1 | grep -E "BetanoLineupsWorker|providers.lineups_stack" | head -3
# Esperado:
# providers.lineups_stack primary=bridge_betano fallback=apifootball bridge_url=...
# BetanoLineupsWorker ativo — lineups via bridge (Fase G.1) max_minute=5
```

### Estratégia de captura (única vez por fixture, early-game)

Lineups são **estáveis pós-confirmação** — worker captura no PRIMEIRO
tick com `jogo.minuto <= LINEUPS_MAX_MINUTE` (default 5) e marca o
fixture como capturado. Todos polls seguintes são no-op rápido
(cache in-memory + `repo.exists_for_fixture` cobre restart).

UNIQUE constraint `(fixture_id, source, team_side)` no schema 0007 é
a última linha de defesa contra race (worker chamado 2× antes do
cache popular). `upsert_batch` retorna `(inserted, skipped_dup)`.

### Monitoramento

Capturas das últimas 6h por source:
```bash
docker exec cpes-postgres psql -U cpes_user -d cpes -c \
  "SELECT
     source,
     COUNT(*) AS rows,
     COUNT(DISTINCT fixture_id) AS fixtures,
     COUNT(*) FILTER (WHERE formation IS NOT NULL) AS with_formation,
     COUNT(*) FILTER (WHERE coach_name IS NOT NULL) AS with_coach
   FROM lineups_history
   WHERE captured_at > NOW() - INTERVAL '6 hours'
   GROUP BY source ORDER BY source;"
```

Saudável: `bridge_betano` dominante quando renewer alive. `coach_name`
sempre NULL pra `bridge_betano` (gap conhecido — `BETANO_GAPS_LINEUPS`),
preenchido apenas em entries com `source=apifootball`.

Cobertura por liga + formation distribution:
```bash
docker exec cpes-postgres psql -U cpes_user -d cpes -c \
  "SELECT source, formation, COUNT(*) AS n
   FROM lineups_history
   WHERE captured_at > NOW() - INTERVAL '24 hours'
   GROUP BY source, formation ORDER BY n DESC LIMIT 20;"
```

Dedup funcionando (sempre 0 duplicates):
```bash
docker exec cpes-postgres psql -U cpes_user -d cpes -c \
  "SELECT fixture_id, source, team_side, COUNT(*) AS dups
   FROM lineups_history
   GROUP BY 1,2,3 HAVING COUNT(*) > 1;"
# Esperado: zero linhas
```

### Troubleshooting

**Worker não aparece nos logs** (`BetanoLineupsWorker ativo` ausente):
- Validar config visível no container: `docker exec cpes-main python3 -c "import config; print(config.USE_BETANO_LINEUPS)"`. Se `AttributeError`, rebuild com `docker compose up -d --build main`.

**lineups_history vazia em jogo live:**
- Worker só age em `minuto <= LINEUPS_MAX_MINUTE`. Verificar se o fixture chegou em alguma janela early (raro pra jogos que entram em monitoramento depois de min 5). Logs `betano_lineups_worker.skip_late` indicam fixture vindo tarde — comportamento esperado, NÃO bug.
- Cobertura zero Betano (ex: ligas regionais sem `homeLineup`): Composite cai pra AF. Verificar log `composite_lineups.zero_coverage source=bridge_betano fixture=...`.

**Player com `name='<unknown>'`** persistido (entries com `<unknown>` em `starting_eleven`):
- Comportamento esperado (AJUSTE 1) — payload Betano teve entry sem `playerId` E sem `unknownPlayerId`. Logs `lineups.player_no_id fixture=...` indicam ocorrência. Investigar se virou padrão, pode sinalizar drift de schema.

**Partial coverage warning** (`lineups.partial_coverage source=... home_ok=True away_ok=False`):
- Esperado em alguns fixtures Betano onde só 1 lado tem `homeLineup` confirmado. NÃO aciona fallback (decisão de design) — AF teria mesma cobertura provavelmente. Monitorar frequência; se >20%, considerar refinar política Composite.

### Lineups history schema rápido

`lineups_history` (migration `0007_lineups_history.sql`) tem 12 colunas:
- `fixture_id`, `source`, `team_side` ∈ `{home, away}` (CHECK)
- `formation` (TEXT — "4-3-3", "5-4-1"; NULL se cobertura zero)
- `coach_name` (TEXT — sempre NULL pra `bridge_betano`)
- `starting_eleven` JSONB (`list[{player_id, name, position, position_display, shirt_number, is_substitute}]`)
- `substitutes` JSONB (mesma shape, `is_substitute=true`)
- `tactical_grid` JSONB (Betano `lineup[][]` preservando linhas táticas — `list[list[player_id]]`)
- `version` INTEGER (snapshot version do payload)
- `captured_at` TIMESTAMPTZ, `raw` JSONB (roster original preservado)
- UNIQUE dedup `(fixture_id, source, team_side)` — 1 lineup por lado.

## A2 shadow discovery (validação pré-cutover)

Mede o que o cutover `sofa_event_id` ganharia/perderia se trocasse o discovery
do AF pro SofaScore — **sem mudar o que é monitorado**. Roda `discover_scheduled`
em paralelo ao AF e loga a cobertura. Usar pra acumular evidência ANTES de
promover o discovery a fonte real (passo do A2). Ver CLAUDE.md §13.17.

### Toggle `SOFASCORE_DISCOVERY_ENABLED`

Ativar:
```bash
grep -q "^SOFASCORE_DISCOVERY_ENABLED" corner-pressure-elite/.env || \
  echo 'SOFASCORE_DISCOVERY_ENABLED=true' >> corner-pressure-elite/.env

# config nova em config.py exige REBUILD (não só recreate)
docker compose up -d --build main
```

Reverter:
```bash
sed -i '/^SOFASCORE_DISCOVERY_ENABLED/d' corner-pressure-elite/.env
docker compose up -d --force-recreate main
```

> Pré-requisito: `USE_SOFASCORE=true` (o shadow usa o `SofaScoreClient` já
> inicializado). Se `USE_SOFASCORE=false`, o shadow é no-op silencioso.

### Observar a cobertura

Roda 1×/dia (no refresh da agenda) + quando o dia vira. Acompanhar ao longo de
vários dias — decisão de cutover exige `af_only` consistentemente baixo:
```bash
docker logs cpes-main 2>&1 | grep "A2-SHADOW" | tail -20
# Linha-resumo:
#   [A2-SHADOW] discovery vs AF: af=12 sofa=14 matched=11 (92% do AF) af_only=1 sofa_only=3
# WARNING por jogo que o cutover PERDERIA (AF vê, Sofa não):
#   [A2-SHADOW] AF-only (cutover PERDERIA): liga=39 Arsenal vs Chelsea
# INFO por jogo que o cutover GANHARIA (só Sofa vê):
#   [A2-SHADOW] Sofa-only (cutover GANHARIA): liga=39 sofa=... Brentford vs Fulham status=notstarted
```

**Interpretação:** `af_only` alto = SofaScore não cobre ligas/jogos que o AF
cobre → cutover regrediria a agenda (não flipar). `af_only ≈ 0` por dias com
volume real = seguro promover o discovery a fonte. `sofa_only` alto pode ser
cobertura extra (bom) ou ruído de torneio (revisar nomes/ligas).
