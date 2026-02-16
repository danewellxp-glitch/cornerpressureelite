# WAHA Plus Webhook Configuration - Technical Documentation

**Última Atualização**: 2026-02-15  
**Versão**: 1.0  
**Ambiente**: Docker Compose (Development & Testing)

---

## Problema Original

### Sintomas
- Comandos `/status`, `/jogos`, `/stats`, `/help` não eram respondidos via WhatsApp
- API Backend recebia requisições corretamente
- WAHA Plus estava rodando e aceitava requisições
- Erro `No LID for user` em alguns requests para sendText
- Erro `Session name is required` em requisições sem session field

### Investigação Realizada

#### 1. Verificação WAHA Core → Plus Migration
- WAHA Core não suporta webhooks (array sempre vazio `[]`)
- Migração para WAHA Plus realizada (imagem: `devlikeapro/waha-plus:latest`)
- Ambiente configurado com variáveis:
  ```yaml
  - WAHA_WEBHOOK_URL=http://cpes-api:8000/api/webhook/whatsapp
  - WAHA_WEBHOOK_MODE=PUSH
  - WAHA_WEBHOOK_EVENTS=message
  ```

#### 2. Discovery
Apesar das variáveis de ambiente, webhooks não eram registrados:
```bash
$ curl -s http://localhost:3000/api/sessions/default | grep -A 5 webhooks
"webhooks": []  # ← SEMPRE VAZIO
```

#### 3. Root Cause
WAHA Plus não processa `WAHA_WEBHOOK_*` environment variables automaticamente. Webhooks precisam ser registrados via API PUT após a sessão estar criada.

---

## Solução Implementada

### Architecture Pattern

```
┌─────────────────────────────────────────┐
│ Docker Compose Stack                    │
├─────────────────────────────────────────┤
│                                         │
│ ┌────────────┐     ┌──────────────┐    │
│ │   WAHA     │────→│  cpes-api    │    │
│ │  PLUS      │     │  (FastAPI)   │    │
│ │ (Port 3000)│     │ (Port 8000)  │    │
│ │            │     │              │    │
│ │ Sessions   │     │ /api/webhook │    │
│ │ Messages   │     │ /whatsapp    │    │
│ └─────┬──────┘     └──────────────┘    │
│       │  WEBHOOK    ▲                   │
│       │  (push) [1] │                   │
│       │             │                   │
│       │  [2] register via PUT           │
│       │             │                   │
│       └─────────────┘                   │
│                                         │
│ ┌────────────────────────────────┐     │
│ │ cpes-dashboard (Next.js)       │     │
│ │ (Port 3001)                    │     │
│ └────────────────────────────────┘     │
│                                         │
│ ┌────────────────────────────────┐     │
│ │ cpes-main (Bot Loop)           │     │
│ └────────────────────────────────┘     │
└─────────────────────────────────────────┘

Flow:
[1] Webhook PUSH: WAHA → API (incoming message)
[2] Registration: API Startup → WAHA (register webhook config)
```

### Implementation Details

#### File: `corner-pressure-elite/api_server.py`

**Imports Added**:
```python
import asyncio
import aiohttp
```

**Startup Event**:
```python
@app.on_event("startup")
async def register_webhooks_on_startup():
    """
    Registra webhooks em WAHA Plus durante inicialização.
    
    Timing: Executa una vez quando a aplicação FastAPI inicia
    
    Steps:
    1. Valida WAHA_API_KEY (se vazio, pula)
    2. Aguarda WAHA ficar disponível (timeout: 60 segundos)
    3. Envia PUT /api/sessions/default com webhook config
    4. Valida resposta (webhooks array populado)
    5. Log de sucesso ou erro
    """
```

**Key Parameters**:
- `WAHA_URL`: `http://waha:3000` (docker network DNS)
- `WAHA_SESSION_NAME`: `default` (hardcoded)
- `WAHA_API_KEY`: From env (header `X-Api-Key`)
- `Webhook URL`: `http://cpes-api:8000/api/webhook/whatsapp`
- `Webhook Events`: `["message"]`

**Error Handling**:
- Network errors: Log warning, continue (webhook may be registered manually)
- Invalid session: Log error, continue (session may be created later)
- Max retries: 30 attempts × 2 seconds = 60 second timeout

#### Process Flow

```
Application Startup
        ↓
    [1.0 seconds]
    FastAPI initializes
        ↓
    app.on_event("startup") triggered
        ↓
    register_webhooks_on_startup() starts
        ↓
    Loop: Check if WAHA available (GET /api/sessions)
        ├─ Attempt 1: WAHA still starting... wait 2s
        ├─ Attempt 2: WAHA still starting... wait 2s
        ├─ ...
        └─ Attempt N: WAHA responds 200 OK ✅
        ↓
    Send PUT /api/sessions/default
        with webhook config
        ↓
    Parse response
        ├─ Success: "webhooks": [{"url": "...", "events": [...]}]
        │           Log: "[WEBHOOK] ✓ Webhook registrado..."
        │
        └─ Failure: {}
            Log: "[WEBHOOK] ✗ Erro ao registrar..."
        ↓
    Return from startup event
        ↓
    [1.5-3 seconds total]
    Application ready to receive requests
```

---

## API Endpoints Involved

### WAHA Plus Endpoints

#### 1. GET /api/sessions
**Purpose**: Check WAHA availability and session list  
**Auth**: X-Api-Key header  
**Response**:
```json
[
  {
    "name": "default",
    "status": "WORKING",
    "config": {
      "webhooks": []
    }
  }
]
```

#### 2. PUT /api/sessions/{sessionName}
**Purpose**: Update session configuration (register webhooks)  
**Auth**: X-Api-Key header  
**Payload**:
```json
{
  "config": {
    "webhooks": [
      {
        "url": "http://cpes-api:8000/api/webhook/whatsapp",
        "events": ["message"]
      }
    ]
  }
}
```

**Response**:
```json
{
  "name": "default",
  "status": "STARTING",
  "config": {
    "webhooks": [
      {
        "url": "http://cpes-api:8000/api/webhook/whatsapp",
        "events": ["message"]
      }
    ]
  }
}
```

### Corner Pressure Elite API Endpoints

#### 1. POST /api/webhook/whatsapp
**Purpose**: Receive webhook events from WAHA  
**Auth**: None (local Docker network)  
**Trigger**: WAHA sends when message received  
**Payload**:
```json
{
  "event": "message",
  "payload": {
    "from": "554195089104@c.us",
    "timestamp": 1771173600,
    "body": "/status"
  }
}
```

**Processing**:
1. Parse `from` and `body`
2. Validate sender in `_authorized_senders`
3. Parse command (`/status`, `/jogos`, `/stats`, `/help`)
4. Format response via `MessageFormatter`
5. Send response via `send_whatsapp_message()`

**Response**:
```json
{
  "status": "ok",
  "command": "status",
  "message_sent": true
}
```

---

## Configuration Matrix

### Environment Variables (docker-compose.yml)

```yaml
WAHA_CONTAINER:
  - WAHA_API_KEY=waha_sk_d3e9f4a1b5c7e2f8a9d1c3e5f7a9b1d3e5f7a9b1
  - WAHA_WEBHOOK_URL=http://cpes-api:8000/api/webhook/whatsapp
  - WAHA_WEBHOOK_MODE=PUSH
  - WAHA_WEBHOOK_EVENTS=message
  - WAHA_DASHBOARD_USERNAME=admin
  - WAHA_DASHBOARD_PASSWORD=Cpes2026@WhatsApp!Secure
  - WAHA_ENABLE_SWAGGER_AUTH=true

API_CONTAINER:
  - WAHA_URL=http://waha:3000
  - WAHA_SESSION_NAME=default
  - WAHA_API_KEY=waha_sk_d3e9f4a1b5c7e2f8a9d1c3e5f7a9b1d3e5f7a9b1
```

### Python Config (config.py)

```python
WAHA_URL = "http://localhost:3000"
WAHA_SESSION_NAME = os.getenv("WAHA_SESSION_NAME", "default")
WAHA_API_KEY = os.getenv("WAHA_API_KEY", "waha_sk_...")
```

### Client Configuration (whatsapp_client.py)

```python
class WAHAConfig:
    base_url: str = "http://localhost:3000"
    session_name: str = "default"  # Lido de config.py
    api_key: Optional[str] = None  # Lido de config.py
    timeout: int = 30
```

---

## Testing Procedures

### Test 1: Webhook Registration Verification

```bash
# Verify webhook is registered in WAHA
curl -s http://localhost:3000/api/sessions/default \
  -H "X-Api-Key: waha_sk_d3e9f4a1b5c7e2f8a9d1c3e5f7a9b1d3e5f7a9b1" \
  | python3 -m json.tool | grep -A 5 "webhooks"

# Expected output:
"webhooks": [
  {
    "url": "http://cpes-api:8000/api/webhook/whatsapp",
    "events": ["message"]
  }
]
```

### Test 2: Webhook Endpoint Simulation

```bash
# Simulate webhook from WAHA (test-only, not real message)
curl -X POST http://localhost:8000/api/webhook/whatsapp \
  -H "Content-Type: application/json" \
  -d '{
    "event": "message",
    "payload": {
      "from": "554195089104@c.us",
      "timestamp": 1771173600,
      "body": "/status"
    }
  }'

# Expected output:
{"status":"ok","command":"status","message_sent":true}
```

### Test 3: Real WhatsApp Message

```
Send via WhatsApp: /status
Expected timing: 2-5 seconds
Expected response: Status report with system metrics
```

### Test 4: API Logs Verification

```bash
# Check API startup logs for webhook registration
docker logs cpes-api | grep -i webhook

# Expected (if using logger):
[WEBHOOK] Registrando webhook em sessão 'default'...
[WEBHOOK] ✓ WAHA disponível após 2s
[WEBHOOK] ✓ Webhook registrado com sucesso em http://cpes-api:8000/api/webhook/whatsapp
```

---

## Troubleshooting Guide

### Issue: Webhooks Array Empty After Startup

**Symptoms**:
```json
"webhooks": []
```

**Causes**:
1. WAHA Plus not available during startup
2. API Key invalid or missing
3. Session not in correct state

**Solutions**:
```bash
# 1. Verify WAHA is running
docker ps | grep waha

# 2. Verify API Key is correct
echo $WAHA_API_KEY

# 3. Check API logs
docker logs cpes-api | grep -i webhook

# 4. Manual webhook registration
curl -X PUT http://localhost:3000/api/sessions/default \
  -H "X-Api-Key: waha_sk_d3e9f4a1b5c7e2f8a9d1c3e5f7a9b1d3e5f7a9b1" \
  -H "Content-Type: application/json" \
  -d '{
    "config": {
      "webhooks": [{
        "url": "http://cpes-api:8000/api/webhook/whatsapp",
        "events": ["message"]
      }]
    }
  }'
```

### Issue: "No LID for user" Error

**Cause**: Attempting to send to invalid/non-existent WhatsApp number

**Example**: `11111111111@c.us` (doesn't exist)

**Solution**: Use valid numbers only:
- Brazil: `554195089104@c.us` (registered and saved)
- Australia: `61405086785@c.us` (registered and saved)

### Issue: "Session name is required"  

**Cause**: POST request to `/api/sendText` missing `session` field

**Solution**: Ensure WAHA client includes:
```json
{
  "session": "default",
  "chatId": "554195089104@c.us",
  "text": "message"
}
```

### Issue: Webhook Not Triggered on Real Messages

**Symptoms**: Simulate test works, but real WhatsApp messages don't trigger

**Diagnosis**:
```bash
# Check WAHA logs for webhook dispatch
docker logs waha | grep -i "webhook\|http"

# Check API logs for webhook reception
docker logs cpes-api | tail -100

# Verify webhook URL is accessible from WAHA container
docker exec waha curl -v http://cpes-api:8000/api/webhook/whatsapp
```

**Common Causes**:
1. Network isolation: Container can't reach host network
2. Firewall: Port 8000 blocked
3. Wrong URL format in webhook config

---

## Performance Considerations

### Timing Budget

| Phase | Duration | Notes |
|-------|----------|-------|
| Container start | ~10s | Docker pulls image, starts service |
| WAHA initialization | ~5-10s | Puppeteer browser starts, connects to WhatsApp WEB |
| API startup | ~2-3s | Python, import dependencies |
| Webhook auto-registration | 1-5s | Depends on WAHA availability |
| **Total startup time** | **20-30s** | Before system ready |

### Message Processing Latency

| Step | Duration | Notes |
|------|----------|-------|
| WhatsApp → WAHA | <1s | WEB protocol |
| WAHA → API webhook | <100ms | Internal Docker network |
| API processing | 100-500ms | Parse command, format response |
| API → WAHA sendText | <100ms | Internal Docker network |
| WAHA → WhatsApp | 1-2s | WEB protocol, network latency |
| **Total end-to-end** | **2-5 seconds** | User perceives response |

---

## Security Considerations

### Authentication Layers

1. **WAHA Plus API**: X-Api-Key header (required for all requests)
2. **WAHA Dashboard**: Basic Authentication (admin:password)
3. **FastAPI Webhook**: No explicit auth (local Docker network only)

### Network Isolation

```
┌─ Docker Network: cpes-network (private)
│  ├─ waha (internal DNS: waha:3000)
│  ├─ cpes-api (internal DNS: cpes-api:8000)
│  ├─ cpes-dashboard (internal DNS: cpes-dashboard:3001)
│  └─ cpes-main (internal DNS: cpes-main)
│
└─ Host Network (external): via exposed ports
   ├─ :3000 → waha:3000 (dashboard, API)
   ├─ :8000 → cpes-api:8000 (webhook, API)
   └─ :3001 → cpes-dashboard:3001 (web dashboard)
```

### Secrets Management

**Current (Development)**:
- API Key in docker-compose.yml (visible)
- Dashboard password in docker-compose.yml (visible)

**Recommended (Production)**:
- Store in `.env` file (not committed)
- Use Docker Secrets
- Use external secret manager (AWS Secrets Manager, etc.)

---

## Deployment Best Practices

### Before Production Deployment

- [ ] Change WAHA_API_KEY to new generated value
- [ ] Change WAHA dashboard password
- [ ] Enable HTTPS (via Cloudflare Tunnel or reverse proxy)
- [ ] Enable rate limiting on webhook endpoint
- [ ] Implement webhook signature validation
- [ ] Add monitoring for webhook failures
- [ ] Configure alerting system
- [ ] Test disaster recovery (WAHA session backup/restore)
- [ ] Load test with multiple concurrent messages

### Monitoring Checklist

```bash
# Health check script (run periodically)
#!/bin/bash

# Check WAHA session status
WAHA_STATUS=$(curl -s http://localhost:3000/api/sessions/default \
  -H "X-Api-Key: $WAHA_API_KEY" | grep -o '"status":"[^"]*"')

# Check webhook registration
WEBHOOK_REGISTERED=$(curl -s http://localhost:3000/api/sessions/default \
  -H "X-Api-Key: $WAHA_API_KEY" | grep -c "http://cpes-api:8000/api/webhook")

# Check API responsiveness
API_RESPONSE=$(curl -s http://localhost:8000/api/health)

echo "WAHA: $WAHA_STATUS"
echo "Webhook Registered: $WEBHOOK_REGISTERED"
echo "API Health: $API_RESPONSE"
```

---

## References

- **WAHA Plus Docs**: https://waha.devlike.pro/
- **FastAPI Docs**: https://fastapi.tiangolo.com/
- **WhatsApp WEB JS**: https://github.com/pedrosans/whatsapp-web.js
- **Docker Compose**: https://docs.docker.com/compose/

---

**Last Updated**: 2026-02-15  
**Version**: 1.0  
**Status**: ✅ Production Ready (after security review)
