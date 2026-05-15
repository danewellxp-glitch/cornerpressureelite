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

## Recovery após reboot acidental

Com systemd ativo (após 2026-05-15), o stack do bridge sobe sozinho no boot. Validar:

1. **Pool**: `curl -s http://localhost:8080/pool/status | python3 -m json.tool` — esperar 2/2 healthy.
2. **Status systemd**: `systemctl --user is-active xvfb-bridge chrome-bridge cpes-bridge` — esperar 3× active.
3. **WAHA intacto**: `docker ps | grep waha` (auto-restart Docker).
4. **CPES container**: `docker ps | grep cpes-main` (auto-restart Docker).
5. Se algum service falhou: `journalctl --user -u <service> -n 50 --no-pager` pra diagnosticar.

Se systemd não subiu (extremamente raro): seguir "Subir bridge manualmente (fallback de emergência)" acima.
