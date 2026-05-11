#!/usr/bin/env bash
# WAHA Session Fix - Quick Checklist
# Save this as: WAHA_QUICK_CHECKLIST.sh
# Usage: cat WAHA_QUICK_CHECKLIST.sh | less

clear

cat << 'EOF'

╔═══════════════════════════════════════════════════════════════════════════╗
║                      WAHA SESSION FIX - QUICK CHECKLIST                   ║
║                                                                           ║
║              Follow this list to validate the fix is working              ║
║                                                                           ║
╚═══════════════════════════════════════════════════════════════════════════╝


┌─────────────────────────────────────────────────────────────────────────┐
│ QUICK START (5 MINUTES)                                                 │
└─────────────────────────────────────────────────────────────────────────┘

☐ Step 1: Run automated tests
  $ cd /home/daniel/cornerpressureelite
  $ ./test_waha_fix.sh
  
  Expected: All 6 tests pass (all GREEN ✓)
  Time: ~30 seconds

☐ Step 2: Test from WhatsApp
  From your Australian phone (61405086785):
  Send: /status
  
  Expected: Response arrives in 2-5 seconds
  Time: ~10 seconds

☐ Step 3: Test sequential commands
  From same phone, immediately after:
  Send: /jogos
  Expected: Arrives 2-5 seconds later
  
  Send: /stats
  Expected: Arrives 2-5 seconds later
  
  Send: /help
  Expected: Arrives 2-5 seconds later

☐ Step 4: Quick logs check
  $ docker logs cpes-api 2>&1 | grep -i "422\|session.*stopped"
  
  Expected: No output (no errors)


┌─────────────────────────────────────────────────────────────────────────┐
│ PRODUCTION VALIDATION (10 MINUTES)                                       │
└─────────────────────────────────────────────────────────────────────────┘

☐ Dashboard health check
  Open: http://localhost:3001 (or https://iqpressure.online)
  
  Verify:
  ☐ WhatsApp Connected shows 🟢 (green)
  ☐ Games Live counter > 0
  ☐ Last Update < 2 minutes ago
  ☐ API Status shows ✓ (green)

☐ Container status
  $ docker ps
  
  Expected: 5 containers running
  ☐ cpes-waha (WAHA API)
  ☐ cpes-api (FastAPI backend)
  ☐ dashboard (Next.js frontend)
  ☐ postgres (Database)
  ☐ redis (Cache)

☐ WAHA session verification
  $ curl http://localhost:3000/api/sessions/default \
    -H "X-Api-Key: cdb85694296a453eb291317d2ac1f660" | jq '.status'
  
  Expected: "WORKING"

☐ Check infrastructure logs
  $ docker logs cpes-api --tail 30 | grep -i error
  
  Expected: No WAHA-related errors


┌─────────────────────────────────────────────────────────────────────────┐
│ DETAILED VERIFICATION (OPTIONAL)                                         │
└─────────────────────────────────────────────────────────────────────────┘

Infrastructure:
☐ All Docker containers healthy
  $ docker ps --all (no containers in "Exited" state)

Configuration:
☐ API keys match everywhere
  $ grep WAHA_API_KEY docker-compose.yml config.py
  
  Expected: All instances show: cdb85694296a453eb291317d2ac1f660

☐ Session name is "default"
  $ grep WAHA_SESSION_NAME corner-pressure-elite/config.py
  
  Expected: "default" (not "cpes-alerts")

☐ Numbers authorized
  $ grep -A 5 "_authorized_senders" corner-pressure-elite/api_server.py
  
  Expected: Contains both:
  - 61405086785@c.us (Australian)
  - 554195089104@c.us (Brazilian)

Code:
☐ New session manager exists
  $ ls corner-pressure-elite/notifier/waha_manager.py
  
  Expected: File exists and is readable

☐ API server imports manager
  $ grep "from notifier.waha_manager import" corner-pressure-elite/api_server.py
  
  Expected: Import statement found

☐ Webhook uses manager
  $ grep -A 5 "async def webhook_whatsapp" corner-pressure-elite/api_server.py | grep "send_whatsapp_message"
  
  Expected: send_whatsapp_message() called (not manual client.close())

Functionality:
☐ Single webhook call works
  $ curl -X POST http://localhost:8000/api/webhook/whatsapp \
    -H "Content-Type: application/json" \
    -d '{"data": {"message": {"chatId": "61405086785@c.us", "fromMe": false, "text": "/status"}}}' \
    | jq '.message_sent'
  
  Expected: true

☐ No 422 errors in logs
  $ docker logs cpes-api 2>&1 | grep 422
  
  Expected: No output

☐ Session stays WORKING after calls
  (After previous tests)
  $ curl http://localhost:3000/api/sessions/default \
    -H "X-Api-Key: cdb85694296a453eb291317d2ac1f660" | jq '.status'
  
  Expected: Still "WORKING"

WhatsApp:
☐ Aussie number receives messages
  ☐ /status arrives in 2-5s
  ☐ /jogos arrives in 2-5s
  ☐ /stats arrives in 2-5s
  ☐ /help arrives in 2-5s

☐ Brazilian number receives messages (if configured)
  ☐ /status arrives in 2-5s
  ☐ Can authenticate if needed

☐ No duplicate messages
  (One request = one message, not 2-3)

☐ No "offline/failed" indicators in WhatsApp


┌─────────────────────────────────────────────────────────────────────────┐
│ PRODUCTION READINESS SIGN-OFF                                           │
└─────────────────────────────────────────────────────────────────────────┘

Quick Readiness (check these):
☐ test_waha_fix.sh returns all GREEN
☐ /status received from WhatsApp in 2-5 seconds
☐ No Session STOPPED errors in logs
☐ Dashboard shows 🟢 WhatsApp Connected
☐ Sequential commands all work (4 commands, all arrive)

Full Readiness (check all above):
☐ All Quick Start items pass
☐ All Production Validation items pass
☐ All Detailed Verification items pass
☐ No other issues identified

RESULT:
☐ ✅ SYSTEM READY FOR PRODUCTION
   → Deploy with confidence
   → Monitor regularly (daily /status check)
   → Keep dashboard open to maintain session


┌─────────────────────────────────────────────────────────────────────────┐
│ IF SOMETHING'S WRONG                                                     │
└─────────────────────────────────────────────────────────────────────────┘

Message not arriving?
  ☐ Check WAHA auth: http://localhost:3000 (scan QR if needed)
  ☐ Check logs: docker logs cpes-api 2>&1 | tail -50
  ☐ Check number authorized: grep 61405086785 corner-pressure-elite/api_server.py
  ☐ Restart API: docker compose restart cpes-api
  ☐ Full rebuild: docker compose down && docker compose up -d --build

Session shows STOPPED?
  ☐ Restart WAHA: docker compose restart cpes-waha  
  ☐ Visit http://localhost:3000 and scan QR code
  ☐ Wait 5 seconds, then test again

No containers running?
  ☐ Start system: docker compose up -d
  ☐ Wait 10 seconds for containers to start
  ☐ Run test again: ./test_waha_fix.sh

Response slow (> 10 seconds)?
  ☐ Check API-Football quota: docker logs cpes-api 2>&1 | grep rate
  ☐ Close dashboard to reduce load
  ☐ Check system resources: docker stats --no-stream
  ☐ Restart API container: docker compose restart cpes-api


┌─────────────────────────────────────────────────────────────────────────┐
│ DOCUMENTATION REFERENCE                                                 │
└─────────────────────────────────────────────────────────────────────────┘

For more information:
📖 2-Minute Summary: docs/resumo/2026-02-15-waha-session-fix-summary.md
🧪 Testing Guide: docs/setup/validation-testing.md
🔧 Technical Details: docs/changelog/2026-02-15-fix-waha-session-stopped.md
📋 Files Changed: docs/changelog/2026-02-15-files-changed.md
⏳ Next Steps: docs/sprints/2026-02-15-next-steps.md


═══════════════════════════════════════════════════════════════════════════

Date: 2026-02-15
System Status: ✅ Fixed and ready for validation
Your Turn: Run the checklist above and report results

═══════════════════════════════════════════════════════════════════════════

EOF
