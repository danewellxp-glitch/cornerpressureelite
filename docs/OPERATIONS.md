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
