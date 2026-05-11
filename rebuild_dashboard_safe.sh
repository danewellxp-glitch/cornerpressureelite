#!/bin/bash
set -e

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
REPO_ROOT="$SCRIPT_DIR"

echo "🔄 Corner Pressure Elite - Dashboard v2 Rebuild"
echo "================================================"
echo ""

# Cores
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Step 1: Verificar Docker
echo -e "${BLUE}[1/5]${NC} Verificando Docker..."
if ! command -v docker &> /dev/null; then
    echo -e "${RED}❌ Docker não está instalado!${NC}"
    exit 1
fi
echo -e "${GREEN}✅ Docker encontrado${NC}"
echo ""

# Step 2: Parar containers
echo -e "${BLUE}[2/5]${NC} Parando containers antigos..."
cd "$REPO_ROOT"
sudo docker compose down 2>/dev/null || echo "⚠️  Nenhum container ativo"
echo -e "${GREEN}✅ Containers parados${NC}"
echo ""

# Step 3: Build dashboard
echo -e "${BLUE}[3/5]${NC} Building nova imagem do dashboard..."
sudo docker compose build dashboard
echo -e "${GREEN}✅ Build completo${NC}"
echo ""

# Step 4: Iniciar sistema
echo -e "${BLUE}[4/5]${NC} Iniciando sistema completo (WAHA, API, Dashboard, Main)..."
sudo docker compose up -d waha api dashboard main
echo -e "${GREEN}✅ Containers iniciados${NC}"
echo ""

# Step 5: Aguardar inicialização
echo -e "${BLUE}[5/5]${NC} Aguardando inicialização (10s)..."
sleep 10
echo -e "${GREEN}✅ Sistema pronto${NC}"
echo ""

# Verificar status
echo -e "${YELLOW}📊 Status dos Containers:${NC}"
sudo docker compose ps
echo ""

echo -e "${GREEN}✨ Dashboard v2 está LIVE!${NC}"
echo ""
echo -e "${BLUE}📍 Acessos:${NC}"
echo "   • Localhost:  http://localhost:3001"
echo "   • Produção:   https://iqpressure.online"
echo ""
echo -e "${BLUE}📊 Para ver logs:${NC}"
echo "   sudo docker compose logs -f dashboard"
echo ""
echo -e "${BLUE}🚀 Para parar:${NC}"
echo "   sudo docker compose down"
