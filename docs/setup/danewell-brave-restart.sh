#!/bin/bash
# Restart preventivo Brave do pool Betano (P4 quick-win, 2026-05-17).
#
# Roda via cron a cada 12h pra evitar degradação JS runtime que faz
# fetch() interno retornar TypeError: Failed to fetch (visto 3x).
# Preserva profile em /home/danewell/brave-betano-profile/.
#
# Uso direto manual: bash /home/danewell/restart-brave.sh

set -u
LOG=/tmp/brave-cron.log
echo "==== $(date -Iseconds) — restart-brave.sh iniciando ====" >> "$LOG"

# 1. SIGTERM
pkill -TERM -f "brave-browser.*betano-profile" 2>/dev/null
pkill -TERM -f "/opt/brave.com/brave/brave" 2>/dev/null
sleep 5

# 2. SIGKILL se persistir
if pgrep -u danewell -f "/opt/brave.com/brave/brave" > /dev/null 2>&1; then
  echo "$(date -Iseconds) — SIGKILL fallback" >> "$LOG"
  pkill -KILL -f "brave-browser.*betano-profile" 2>/dev/null
  pkill -KILL -f "/opt/brave.com/brave/brave" 2>/dev/null
  sleep 2
fi

# 3. Respawn preservando profile (DISPLAY :101 = Xvfb daewell)
setsid -f env DISPLAY=:101 /usr/bin/brave-browser \
  --user-data-dir=/home/danewell/brave-betano-profile \
  --no-first-run \
  --no-default-browser-check \
  --remote-debugging-port=9224 \
  --window-size=1920,1080 \
  --disable-gpu \
  --disable-dev-shm-usage \
  --lang=pt-BR \
  --disable-blink-features=AutomationControlled \
  --proxy-server=http://127.0.0.1:8888 \
  https://www.betano.bet.br/ < /dev/null >> "$LOG" 2>&1

sleep 15  # warmup

# 4. Validar restart funcionou via /json/version do CDP
if curl -s --max-time 5 http://localhost:9224/json/version > /dev/null 2>&1; then
  echo "$(date -Iseconds) — restart OK (CDP 9224 responde)" >> "$LOG"
  exit 0
else
  echo "$(date -Iseconds) — ERRO: CDP 9224 não responde pós-restart" >> "$LOG"
  exit 1
fi
