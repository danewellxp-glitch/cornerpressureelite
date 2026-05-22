#!/usr/bin/env bash
# PostToolUse(Edit|Write) — roda pytest focado quando arquivos do CAMINHO DO
# DINHEIRO / decisao sao editados (banca, decisions, engine). CLAUDE.md §7:
# "Toda mudanca no fluxo de decisao precisa de teste." Pega regressao na hora.
# Advisory (nunca bloqueia): so reporta pass/fail pro Claude.
set -uo pipefail
input=$(cat)
fp=$(printf '%s' "$input" | python3 -c "import json,sys
try: print(json.load(sys.stdin).get('tool_input',{}).get('file_path',''))
except Exception: print('')" 2>/dev/null || true)

case "$fp" in
  *engine/*.py|*data/repositories/banca.py|*data/repositories/user_signal_decisions.py|*data/repositories/blocked_signals.py)
    proj="${CLAUDE_PROJECT_DIR:-$(pwd)}"
    cd "$proj/corner-pressure-elite" 2>/dev/null || exit 0
    echo "[test-on-edit] arquivo critico editado ($fp) — rodando pytest focado..." >&2
    out=$(PYTHONPATH=. timeout 90 python3 -m pytest tests/ -k "settle or banca or decision or score or payout" -q -p no:cacheprovider 2>&1 | tail -4 || true)
    echo "$out" >&2
    ;;
esac
exit 0
