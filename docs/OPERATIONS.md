# RUNBOOK OPERACIONAL

Comandos pra subir, derrubar, validar, fazer recovery. **Quando algo quebra às 3am, segue runbook sem pensar.**

> **Escopo:** quick-reference operacional. Setup detalhado de ambiente vai em `docs/setup/`. Deploy completo vai em `docs/manuals/DEPLOYMENT.md`.

## Subir bridge do zero

```bash
# 1. Xvfb :100 (se já vivo, pula)
if ! pgrep -f "Xvfb.*:100" > /dev/null; then
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

## Recovery após reboot acidental

1. Verifica estado:
   `ps aux | grep -E "Xvfb|chrome.*9223|server.py" | grep -v grep`
2. Se algo faltando, segue "Subir bridge do zero" acima.
3. Verifica WAHA não foi afetado:
   `docker ps | grep waha`
4. Container CPES auto-restartou:
   `docker ps | grep cpes-main`
