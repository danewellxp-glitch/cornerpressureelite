# Guia Rápido: Testando Comandos WhatsApp /status /jogos

## Como Testar Agora

### 1. Via Curl (Simular Webhook)

```bash
# Teste /status
curl -X POST "http://localhost:8000/api/webhook/whatsapp" \
  -H "Content-Type: application/json" \
  -d '{
    "event": "message",
    "payload": {
      "from": "554195089104@c.us",
      "body": "/status"
    }
  }'

# Resposta esperada:
# { "status": "ok", "command": "status" }
```

```bash
# Teste /jogos
curl -X POST "http://localhost:8000/api/webhook/whatsapp" \
  -H "Content-Type: application/json" \
  -d '{
    "event": "message",
    "payload": {
      "from": "554195089104@c.us",
      "body": "/jogos"
    }
  }'

# Resposta esperada:
# { "status": "ok", "command": "jogos" }
```

### 2. Via WhatsApp Real

1. Abra o WhatsApp e envie para o **número do admin** (554195089104):
   ```
   /status
   ```
   
2. Você deve receber uma resposta com:
   - 🤖 STATUS DO SISTEMA
   - 🟢 Online / 🔴 Offline
   - 📈 API Football usage
   - ⚽ Jogos ao vivo
   - Etc.

3. Teste também:
   ```
   /jogos
   /stats
   /help
   ```

### 3. Via Script de Diagnóstico

```bash
docker exec cpes-api python3 /app/diagnose_whatsapp.py
```

Resultado esperado: `✅ SISTEMA PRONTO! Comandos /status e /jogos devem funcionar no WhatsApp.`

## Monitorando Sinais para o Grupo

### 1. Verificar se Sinais estão sendo Enviados

```bash
# Veja sinais recentes na API
curl http://localhost:8000/api/signals/recent | python3 -m json.tool

# Resultado exemplo:
# [
#   {
#     "timestamp": "2026-02-15T14:30:00",
#     "jogo_descricao": "Team A vs Team B",
#     "tipo_sinal": "corner_burst",
#     "pressure_score": 8.5,
#     ...
#   }
# ]
```

### 2. Verificar Jogos ao Vivo

```bash
# Veja jogos ao vivo e situação da janela
curl http://localhost:8000/api/live-games | python3 -m json.tool

# Resultado exemplo:
# {
#   "status": "analisando",
#   "jogos_ao_vivo": 3,
#   "jogos_na_janela": 1,
#   "jogos": [
#     {
#       "liga": "La Liga",
#       "descricao": "Team A vs Team B",
#       "minuto": 65,
#       "escanteios": 8,
#       "status": "na_janela"
#     }
#   ]
# }
```

### 3. Verificar Próximos Jogos

```bash
# Veja agenda dos próximos jogos
curl http://localhost:8000/api/upcoming-games | python3 -m json.tool

# Resultado exemplo:
# {
#   "proximos": [
#     {
#       "hora_inicio": "14:30",
#       "home": "Team A",
#       "away": "Team B",
#       "liga": "La Liga",
#       "minutos_ate": 5,
#       "status": "NS"
#     }
#   ]
# }
```

## Troubleshooting

### Problema: `/status` não responde no WhatsApp

**1. Confirme que a sessão WAHA está ativa:**
```bash
curl -X GET "http://localhost:3000/api/sessions/default" \
  -H "X-Api-Key: cdb85694296a453eb291317d2ac1f660"

# Esperado: { "status": "WORKING", ... }
```

**2. Confirme que o webhook endpoint está respondendo:**
```bash
curl -X POST "http://localhost:8000/api/webhook/whatsapp" \
  -H "Content-Type: application/json" \
  -d '{"event":"message","payload":{"from":"554195089104@c.us","body":"/status"}}'

# Esperado: { "status": "ok", "command": "status" }
```

**3. Verifique logs da API:**
```bash
docker logs cpes-api --follow
# Procure por "webhook" ou "whatsapp"
```

### Problema: Sinais não chegam no grupo WhatsApp

**1. Confirme que o grupo está configurado:**
```bash
docker exec cpes-api python3 -c "
from config import WHATSAPP_GROUP_ID
print(f'Group ID configurado: {WHATSAPP_GROUP_ID}')
"

# Esperado: Group ID configurado: 120363424218619609@g.us
```

**2. Teste envio manual para o grupo:**
```bash
curl -X POST "http://localhost:3000/api/sendText" \
  -H "X-Api-Key: cdb85694296a453eb291317d2ac1f660" \
  -H "Content-Type: application/json" \
  -d '{
    "session": "default",
    "chatId": "120363424218619609@g.us",
    "text": "🧪 Teste de envio para grupo"
  }'
```

**3. Verifique logs do sistema principal:**
```bash
docker logs cpes-main --follow | grep -i "signal\|group\|notif"
```

### Problema: Dashboard mostra jogos mas WhatsApp diz "nenhum jogo"

Possível causa: **Timeout ao enviar mensagem**

```bash
# Enviar comando com timeout maior
curl -X POST "http://localhost:8000/api/webhook/whatsapp" \
  -H "Content-Type: application/json" \
  --max-time 30 \
  -d '{"event":"message","payload":{"from":"554195089104@c.us","body":"/jogos"}}'
```

---

**Status**: ✅ Tudo funcionando

Leia o [Changelog Completo](../changelog/2026-02-15-fix-whatsapp-webhook.md) para detalhes técnicos.
