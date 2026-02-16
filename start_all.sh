#!/usr/bin/env bash
# start_all.sh - Inicia todos os serviços do CPES
# Corner Pressure Elite System - Linux/Mac

BASE_PATH="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
API_PATH="$BASE_PATH/corner-pressure-elite"
DASH_PATH="$BASE_PATH/dashboard"

echo "=== Iniciando Corner Pressure Elite System ==="

# 0. Preparar .env se não existir
if [ ! -f "$API_PATH/.env" ]; then
  if [ -f "$API_PATH/.env.example" ]; then
    cp "$API_PATH/.env.example" "$API_PATH/.env"
    echo "[0/5] .env criado a partir de .env.example - edite com suas chaves" 
  fi
else
  echo "[0/5] .env encontrado"
fi

# 1. Docker - WAHA
echo ""
echo "[1/5] Verificando Docker e WAHA (porta 3000)..."
if command -v docker &>/dev/null; then
  if docker info &>/dev/null; then
    if ! docker ps --filter "name=waha" --format "{{.Names}}" | grep -q waha; then
      echo "Iniciando WAHA..."
      docker run -d --name waha -p 3000:3000 -v ~/.waha:/app/.sessions devlikeapro/waha-plus:latest
      sleep 3
    else
      echo "WAHA já está rodando"
    fi
  else
    echo "Docker não está rodando. Inicie o Docker e execute novamente."
    echo "Ou rode manualmente: docker run -d --name waha -p 3000:3000 -v ~/.waha:/app/.sessions devlikeapro/waha-plus:latest"
    read -p "Pressione Enter para continuar ou Ctrl+C para sair..."
  fi
else
  echo "Docker não instalado. Instale: https://docs.docker.com/get-docker/"
  read -p "Pressione Enter para continuar sem WAHA ou Ctrl+C para sair..."
fi

# 2. Opção: Docker Compose (tudo em containers) ou modo nativo
if [ "${CPES_USE_DOCKER:-0}" = "1" ]; then
  echo ""
  echo "[2/5] Iniciando via Docker Compose..."
  cd "$BASE_PATH"
  docker compose up -d
  sleep 5
  echo ""
  echo "=== Sistema Iniciado (Docker Compose) ==="
  echo "Dashboard: http://localhost:3001"
  echo "API:       http://localhost:8000"
  echo "WAHA:      http://localhost:3000"
  exit 0
fi

# Modo nativo: Python + Node
# 2. FastAPI
echo ""
echo "[2/5] Iniciando FastAPI (porta 8000)..."
cd "$API_PATH"
uvicorn api_server:app --host 127.0.0.1 --port 8000 &
API_PID=$!
sleep 5

# 3. Dashboard
echo ""
echo "[3/5] Iniciando Dashboard Next.js (porta 3001)..."
cd "$DASH_PATH"
npm run dev &
DASH_PID=$!
sleep 8

# 4. Verificar serviços
echo ""
echo "[4/5] Verificando serviços..."

check_url() {
  local url="$1"
  local name="$2"
  if curl -s -f -o /dev/null "$url" 2>/dev/null; then
    echo "  [OK] $name"
    return 0
  else
    echo "  [ERRO] $name - não respondeu"
    return 1
  fi
}

check_url "http://localhost:3000/" "WAHA (3000)"
check_url "http://localhost:8000/api/health" "FastAPI (8000)"
check_url "http://localhost:3001" "Dashboard (3001)"

echo ""
echo "=== Sistema Iniciado ==="
echo "Dashboard: http://localhost:3001"
echo "API:       http://localhost:8000"
echo "WAHA:      http://localhost:3000"
echo ""
echo "Pressione Enter para iniciar o Monitor (ou Ctrl+C para manter só os serviços)..."
read -r

# 5. Monitor
echo ""
echo "[5/5] Iniciando Monitor..."
cd "$API_PATH"
python monitor.py
