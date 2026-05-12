# Validation Testing Guide: WhatsApp Webhook & Session Management

**Date**: 2026-02-15  
**Status**: Ready for Production Validation  
**Updated**: After fixing WAHA Session STOPPED bug

---

## Quick Validation (5 minutes)

### 1. Check WAHA Session Status

```bash
# Terminal 1: Verify WAHA container is running
docker ps | grep waha

# Terminal 2: Check session status
curl -s http://localhost:3000/api/sessions/default \
  -H "X-Api-Key: cdb85694296a453eb291317d2ac1f660" | jq '.status'
```

**Expected**: `"WORKING"` (or `"STARTING"` if just authenticated)

If you see `"STOPPED"`:
```bash
# Restart session
curl -X POST http://localhost:3000/api/sessions/start \
  -H "X-Api-Key: cdb85694296a453eb291317d2ac1f660"
```

Then scan QR code at http://localhost:3000

---

### 2. Test Webhook - /status Command

```bash
# Terminal: Send /status command via webhook
curl -s -X POST http://localhost:8000/api/webhook/whatsapp \
  -H "Content-Type: application/json" \
  -d '{
    "data": {
      "message": {
        "chatId": "61405086785@c.us",
        "fromMe": false,
        "text": "/status"
      }
    }
  }' | jq '.'
```

**Expected Output**:
```json
{
  "status": "ok",
  "command": "status",
  "message_sent": true
}
```

**What You Should See in WhatsApp**:
- Sender: Your bot number (554195089104@c.us)
- Message: Status report with game count, last update, memory, CPU
- Arrival time: 2-5 seconds

---

### 3. Test Sequential Requests (Key Fix Validation)

This test proves the session persistence fix is working.

```bash
#!/bin/bash
# Save as: test_sequential_webhooks.sh

echo "=== Test 1: /status ==="
curl -s -X POST http://localhost:8000/api/webhook/whatsapp \
  -H "Content-Type: application/json" \
  -d '{"data": {"message": {"chatId": "61405086785@c.us", "fromMe": false, "text": "/status"}}}' \
  | jq '.message_sent'

sleep 1

echo "=== Test 2: /jogos ==="
curl -s -X POST http://localhost:8000/api/webhook/whatsapp \
  -H "Content-Type: application/json" \
  -d '{"data": {"message": {"chatId": "61405086785@c.us", "fromMe": false, "text": "/jogos"}}}' \
  | jq '.message_sent'

sleep 1

echo "=== Test 3: /stats ==="
curl -s -X POST http://localhost:8000/api/webhook/whatsapp \
  -H "Content-Type: application/json" \
  -d '{"data": {"message": {"chatId": "61405086785@c.us", "fromMe": false, "text": "/stats"}}}' \
  | jq '.message_sent'

sleep 1

echo "=== Test 4: /help ==="
curl -s -X POST http://localhost:8000/api/webhook/whatsapp \
  -H "Content-Type: application/json" \
  -d '{"data": {"message": {"chatId": "61405086785@c.us", "fromMe": false, "text": "/help"}}}' \
  | jq '.message_sent'
```

**Expected**: All four should return `true` (not false or errors)

**If any returns false or error**:
```bash
# Check logs for session errors
docker logs cpes-api 2>&1 | grep -i "error\|422\|stopped" | tail -20
```

---

### 4. Test from Actual WhatsApp

1. **Send to your bot** (via WhatsApp):
   - Message: `/status`
   - Expected response: Status report (2-5 seconds)

2. **Send next command** (immediately after):
   - Message: `/jogos`
   - Expected response: List of upcoming games

3. **Check message times**:
   - Both should arrive
   - No "offline" or "failed" indicators
   - No long delays

---

## Full Validation Checklist

### Infrastructure ✓

- [ ] Docker containers all running: `docker ps` (5/5)
  - [ ] cpes-waha (WAHA API)
  - [ ] cpes-api (FastAPI backend)
  - [ ] dashboard (Next.js frontend)
  - [ ] postgres (Database)
  - [ ] redis (Cache)

- [ ] WAHA authenticated:
  - [ ] QR code scanned at http://localhost:3000
  - [ ] Status = WORKING
  - [ ] Bot number visible

### Configuration ✓

- [ ] API keys match across services:
  ```bash
  grep WAHA_API_KEY docker-compose.yml config.py
  # Should all be: cdb85694296a453eb291317d2ac1f660
  ```

- [ ] Session name is "default":
  ```bash
  grep WAHA_SESSION_NAME corner-pressure-elite/config.py
  # Should be: default (not cpes-alerts)
  ```

- [ ] Authorized numbers configured:
  ```bash
  grep -A 5 "_authorized_senders" corner-pressure-elite/api_server.py
  # Should include both: 61405086785@c.us and 554195089104@c.us
  ```

### Code Changes ✓

- [ ] WAHASessionManager exists:
  ```bash
  ls -la corner-pressure-elite/notifier/waha_manager.py
  ```

- [ ] api_server.py imports manager:
  ```bash
  grep "from notifier.waha_manager import" corner-pressure-elite/api_server.py
  ```

- [ ] Webhook uses manager (no client.close()):
  ```bash
  grep -A 10 "async def webhook_whatsapp" corner-pressure-elite/api_server.py \
    | grep -i "send_whatsapp_message"
  ```

### Functionality ✓

- [ ] Single webhook call works:
  ```bash
  curl ... /api/webhook/whatsapp (one command, receives response)
  ```

- [ ] Sequential calls work:
  ```bash
  # Run 4 commands in sequence, all return message_sent: true
  bash test_sequential_webhooks.sh
  ```

- [ ] No error 422 in logs:
  ```bash
  docker logs cpes-api 2>&1 | grep 422 | wc -l
  # Should output: 0
  ```

- [ ] Session stays WORKING:
  ```bash
  # Run commands, then check status
  curl http://localhost:3000/api/sessions/default ... | jq '.status'
  # Should still be: WORKING
  ```

### WhatsApp ✓

- [ ] Australian number (61405086785) receives messages:
  - [ ] Send /status → receives response in 2-5s
  - [ ] Send /jogos → receives response
  - [ ] Send /stats → receives response

- [ ] Brazilian admin number (554195089104) receives messages:
  - [ ] Send /status → receives response
  - [ ] Authorize with password (if implemented)

- [ ] No duplicate messages:
  - [ ] One request = one message (not 2-3)

- [ ] No "offline/failed" indicators in WhatsApp

---

## Regression Testing

If system stops responding after hours/days:

### Step 1: Check Container Health

```bash
docker ps | grep -E "cpes-waha|cpes-api"
# If STATUS is "Up X seconds", container recently restarted

# Check why
docker logs cpes-api | tail -50 | grep -i error
docker logs cpes-waha | tail -50 | grep -i error
```

### Step 2: Verify WAHA Session

```bash
# Session status
curl http://localhost:3000/api/sessions/default \
  -H "X-Api-Key: cdb85694296a453eb291317d2ac1f660" \
  | jq '.status'

# If STOPPED or error, restart
curl -X POST http://localhost:3000/api/sessions/start \
  -H "X-Api-Key: cdb85694296a453eb291317d2ac1f660"

# Wait 5 seconds, then scan QR code at http://localhost:3000
```

### Step 3: Test Webhook

```bash
# Single command test
curl -X POST http://localhost:8000/api/webhook/whatsapp \
  -H "Content-Type: application/json" \
  -d '{"data": {"message": {"chatId": "61405086785@c.us", "fromMe": false, "text": "/status"}}}' \
  | jq '.message_sent'
```

### Step 4: Collect Logs

If issues persist:

```bash
# Full diagnostics
echo "=== Container status ==="
docker ps

echo "=== WAHA logs (last 50 lines) ==="
docker logs cpes-waha | tail -50

echo "=== API logs (errors only) ==="
docker logs cpes-api 2>&1 | grep -i error | tail -30

echo "=== Webhook processing ==="
docker logs cpes-api 2>&1 | grep -i webhook | tail -20
```

Attach this to [issue](https://github.com/yourrepo/issues) if reporting

---

## Known Limitations

### WAHA Session Timeout

- **Behavior**: After 15 minutes of inactivity, WAHA session may enter STOPPED state
- **Evidence**: `docker logs cpes-waha | grep -i "timeout\|stopped"`
- **Fix**: Keep dashboard open or send periodic /status commands to keep alive

### QR Code Only Works Once

- **Behavior**: QR code at http://localhost:3000 expires after ~2 minutes
- **If it expired**: Restart WAHA session (see Step 2: Verify WAHA Session)
- **Future improvement**: Add auto-restart or session recovery endpoint

### Single Session Model

- **Limitation**: WAHA Core (free version) supports only one session named "default"
- **Impact**: Can't have multiple bots, multi-device sync not available
- **Workaround**: Use business account with WAHA Pro if multi-device needed

---

## Production Readiness Checklist

Before going live:

- [ ] All infrastructure tests pass
- [ ] Configuration tests pass
- [ ] Code changes verified
- [ ] Functionality tests pass
- [ ] WhatsApp delivery confirmed (2-5 seconds)
- [ ] Sequential requests work (no 422 errors)
- [ ] Logs are clean (no error 500, 422, STOPPED)
- [ ] Session stays WORKING after 5+ commands
- [ ] Both authorized numbers working

---

## Dashboard Health Check

Once validated, monitor dashboard for live status:

1. Open http://localhost:3001 (or https://iqpressure.online)
2. Check **"System Health"** panel:
   - Games Live: Should increase during match hours
   - Last Update: Should be < 1 minute old
   - WhatsApp Connected: Should show 🟢 (green)
3. Check **"Recent Signals"**:
   - Should show corner kick alerts as they happen
4. Check **"Configuration"**:
   - Webhook URL should match docker-compose.yml
   - API Key should match cdb85694296a453eb291317d2ac1f660

---

## Questions / Issues?

**System not responding**:
1. Check `docker ps` (all containers running?)
2. Check WAHA session status (WORKING?)
3. Check logs (errors?)
4. Restart cleanly: `docker compose down && docker compose up -d`

**Messages arriving slowly (> 10 seconds)**:
1. Check API-Football quota: `docker logs cpes-api | grep "rate.limit"`
2. Check network latency: `ping localhost` (should be < 1ms)
3. Check WAHA load: `curl http://localhost:3000/api/health` (should be WORKING)

**Specific number not responding**:
1. Verify number in authenticated session: `curl http://localhost:3000/api/sessions/default | jq '.me.id'`
2. Check authorized list: `grep 61405086785 corner-pressure-elite/api_server.py`
3. Verify message format in webhook payload

---

**Last Updated**: 2026-02-15  
**Document**: [Full Technical Changelog](../changelog/2026-02-15-fix-waha-session-stopped.md)
