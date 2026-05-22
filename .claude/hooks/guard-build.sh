#!/usr/bin/env bash
# PreToolUse(Bash) — bloqueia `docker compose ... build dashboard` quando ha
# mudancas nao-commitadas em dashboard/. Motivo: em 2026-05-20 um rebuild a
# partir da arvore suja deployou WIP nao-intencional e regrediu o layout
# (ver docs/BUGS.md). Forca um checkpoint deliberado.
#
# Override: commite (ou stashe) as mudancas, OU rode o build voce mesmo no
# terminal (`! docker compose ...`), OU o usuario confirma e o Claude refaz.
set -euo pipefail
input=$(cat)
cmd=$(printf '%s' "$input" | python3 -c "import json,sys
try: print(json.load(sys.stdin).get('tool_input',{}).get('command',''))
except Exception: print('')" 2>/dev/null || true)

proj="${CLAUDE_PROJECT_DIR:-$(pwd)}"
case "$cmd" in
  *docker*compose*build*dashboard*|*docker-compose*build*dashboard*)
    if ! git -C "$proj" diff --quiet -- dashboard/ 2>/dev/null \
       || ! git -C "$proj" diff --cached --quiet -- dashboard/ 2>/dev/null; then
      echo "GUARD: ha mudancas NAO-COMMITADAS em dashboard/ e voce vai rodar 'docker compose --build dashboard'." >&2
      echo "O rebuild empacota a arvore atual inteira (risco de deployar WIP nao-intencional e mudar o layout — incidente de 2026-05-20)." >&2
      echo "Antes de prosseguir: rode 'git status dashboard/' e confirme que TODA a WIP deve ir pra imagem. Se sim, o usuario confirma e voce refaz; se nao, commite/reverta o que nao quer." >&2
      exit 2
    fi
    ;;
esac
exit 0
