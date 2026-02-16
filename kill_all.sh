#!/usr/bin/env bash
# kill_all.sh - Encerra todos os serviços do CPES
# Corner Pressure Elite System - Linux/Mac

echo "=== Encerrando serviços CPES ==="

# Função para matar processo na porta
kill_port() {
  local port=$1
  local pids
  if command -v lsof &>/dev/null; then
    pids=$(lsof -ti ":$port" 2>/dev/null)
  elif command -v ss &>/dev/null; then
    pids=$(ss -tlnp 2>/dev/null | grep ":$port " | grep -oP 'pid=\K[0-9]+' 2>/dev/null || true)
  elif command -v fuser &>/dev/null; then
    fuser -k "$port/tcp" 2>/dev/null || true
    return
  fi
  if [ -n "$pids" ]; then
    echo "$pids" | xargs kill -9 2>/dev/null || true
    echo "Porta $port: encerrado"
  else
    echo "Porta $port: nada rodando"
  fi
}

# Portas
kill_port 3001  # Dashboard
kill_port 3000  # WAHA (se rodando fora do Docker)
kill_port 8000  # FastAPI

# Python (main.py, monitor.py)
pypids=$(pgrep -f "python.*(main|monitor|api_server)" 2>/dev/null || true)
if [ -n "$pypids" ]; then
  echo "$pypids" | xargs kill -9 2>/dev/null || true
  echo "Python (main/monitor/api): encerrado"
else
  echo "Python: nada rodando"
fi

# Node (Next.js)
nodepids=$(pgrep -f "next.*dev" 2>/dev/null || true)
if [ -n "$nodepids" ]; then
  echo "$nodepids" | xargs kill -9 2>/dev/null || true
  echo "Next.js: encerrado"
fi

# Docker WAHA
if command -v docker &>/dev/null; then
  if docker ps -q --filter "name=waha" 2>/dev/null | grep -q .; then
    docker stop waha 2>/dev/null || true
    echo "Docker WAHA: encerrado"
  else
    echo "Docker WAHA: não rodando"
  fi
fi

# Docker Compose (se em uso)
if [ -f "$(dirname "${BASH_SOURCE[0]}")/docker-compose.yml" ]; then
  cd "$(dirname "${BASH_SOURCE[0]})"
  docker compose down 2>/dev/null || true
fi

echo ""
echo "=== Serviços encerrados ==="
echo "Banco SQLite (data/cpes.db): arquivo mantido"
