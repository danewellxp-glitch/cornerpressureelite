#!/bin/bash
# Coleta telemetria P4 quick-win (cron preventivo Brave). Roda a cada 6h
# (00h/06h/12h/18h BRT). 4 snapshots/dia × 36h = 6 snapshots de validação.
#
# Decisão pós-coleta:
#   refetch_none/6h | classificação | ação
#   0               | cron suficiente | fechar Fase K
#   1-2             | tolerável | P4 PARTE 1 vira "P6 opcional"
#   3+              | urgente | P4 PARTE 1 imediato
#
# Logs em /tmp/p4-monitoring-YYYY-MM-DD_HH-MM.log

set -u
TS=$(date +'%Y-%m-%d_%H-%M')
LOG="/tmp/p4-monitoring-${TS}.log"

{
  echo "═══ P4 MONITORING — ${TS} BRT ═══"
  echo ""
  echo "## Brave uptime (alvo: resetar a cada 12h via cron)"
  ssh -o ConnectTimeout=5 danewell \
    "ps -o etime= -p \$(pgrep -f 'brave-browser.*betano-profile' | head -1) 2>/dev/null | xargs" \
    2>&1
  echo ""

  echo "## Odds distribuição últimas 6h (AF deve ser 0%)"
  docker exec cpes-postgres psql -U cpes_user -d cpes -c \
    "SELECT source, COUNT(*) AS captures,
            ROUND(100.0 * COUNT(*) FILTER (WHERE is_stale=true) / NULLIF(COUNT(*), 0), 2) AS pct_stale
     FROM odds_history WHERE captured_at > NOW() - INTERVAL '6 hours'
     GROUP BY source ORDER BY captures DESC;" 2>&1
  echo ""

  echo "## Sinais bloqueados últimas 6h (refetch_none = outage Brave)"
  docker exec cpes-postgres psql -U cpes_user -d cpes -c \
    "SELECT reason, COUNT(*) AS total
     FROM blocked_signals WHERE blocked_at > NOW() - INTERVAL '6 hours'
     GROUP BY reason ORDER BY total DESC;" 2>&1
  echo ""

  echo "## Cron Brave — últimas 3 entradas de restart OK"
  ssh -o ConnectTimeout=5 danewell \
    "grep -E 'restart OK|ERRO' /tmp/brave-cron.log 2>/dev/null | tail -3" 2>&1
  echo ""

  echo "## /event/state health (fixture sample 85162739)"
  curl -s --max-time 30 -o /dev/null \
    -w "  HTTP %{http_code} elapsed=%{time_total}s\n" \
    "http://localhost:8080/event/85162739/state" 2>&1
  echo ""

  echo "## Fixtures ativos últimos 15min (proxy live)"
  docker exec cpes-postgres psql -U cpes_user -d cpes -c \
    "SELECT COUNT(DISTINCT fixture_id) AS active
     FROM stats_history WHERE captured_at > NOW() - INTERVAL '15 minutes';" 2>&1
} > "$LOG" 2>&1

echo "saved: $LOG"
