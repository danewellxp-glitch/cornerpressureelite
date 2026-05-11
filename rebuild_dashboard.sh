#!/bin/bash

# Script para rebuild e reiniciar o Dashboard com as novas configurações
# Uso: ./rebuild_dashboard.sh

set -e

echo "🔄 Parando containers antigos..."
docker compose down 2>/dev/null || true

echo "🏗️  Rebuilding dashboard image..."
docker compose build dashboard

echo "🚀 Iniciando sistema completo..."
docker compose up -d

echo "⏳ Aguardando inicialização..."
sleep 5

echo ""
echo "✅ Dashboard reconstruído e reiniciado!"
echo ""
echo "📍 Acessar em:"
echo "   • Localhost: http://localhost:3001"
echo "   • Produção: https://iqpressure.online"
echo ""
echo "📊 Verificar logs:"
echo "   docker compose logs -f dashboard"
