#!/bin/bash

##############################################
# Script para registrar webhooks em WAHA Plus
# Executado ao iniciar o container da API
##############################################

set -e

WAHA_URL="${WAHA_URL:-http://localhost:3000}"
WAHA_SESSION="${WAHA_SESSION_NAME:-default}"
WAHA_API_KEY="${WAHA_API_KEY}"
WEBHOOK_URL="${WAHA_WEBHOOK_URL:-http://cpes-api:8000/api/webhook/whatsapp}"
MAX_RETRIES=30
RETRY_DELAY=2

echo "[WEBHOOK] Aguardando WAHA ficar disponível..."

# Aguardar WAHA ficar disponível
for i in $(seq 1 $MAX_RETRIES); do
    if curl -s -f -H "X-Api-Key: $WAHA_API_KEY" "$WAHA_URL/api/sessions" > /dev/null 2>&1; then
        echo "[WEBHOOK] ✓ WAHA disponível após $((i * RETRY_DELAY))s"
        break
    fi
    
    if [ $i -eq $MAX_RETRIES ]; then
        echo "[WEBHOOK] ✗ WAHA não respondeu após $((MAX_RETRIES * RETRY_DELAY))s"
        exit 1
    fi
    
    echo "[WEBHOOK] Tentativa $i/$MAX_RETRIES. Aguardando ${RETRY_DELAY}s..."
    sleep $RETRY_DELAY
done

echo "[WEBHOOK] Registrando webhook em sessão: $WAHA_SESSION"

# Registrar webhook
RESPONSE=$(curl -s -X PUT \
  "$WAHA_URL/api/sessions/$WAHA_SESSION" \
  -H "X-Api-Key: $WAHA_API_KEY" \
  -H "Content-Type: application/json" \
  -d "{
    \"config\": {
      \"webhooks\": [
        {
          \"url\": \"$WEBHOOK_URL\",
          \"events\": [\"message\"]
        }
      ]
    }
  }")

echo "[WEBHOOK] Resposta: $RESPONSE"

# Verificar se webhook foi registrado
if echo "$RESPONSE" | grep -q "$WEBHOOK_URL"; then
    echo "[WEBHOOK] ✓ Webhook registrado com sucesso em $WEBHOOK_URL"
    exit 0
else
    echo "[WEBHOOK] ✗ Falha ao registrar webhook"
    echo "[WEBHOOK] Response: $RESPONSE"
    exit 1
fi
