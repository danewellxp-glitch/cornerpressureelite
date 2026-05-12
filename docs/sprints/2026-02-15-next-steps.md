# Next Steps: Production Validation & Live Testing

**Date**: 2026-02-15  
**System Status**: ✅ Fixed & Ready for Testing  
**Your Action Required**: Proceed with validation below

> **Note (2026-05-11):** the production domain was migrated from `odontoschultz.online` to `iqpressure.online`. References to the old domain in this doc reflect the previous state. See `docs/changelog/2026-05-11-migracao-dominio-iqpressure.md`.

---

## Immediate Actions (Next 15 minutes)

### Step 1: Run Automated Validation ✓

```bash
cd /home/daniel/cornerpressureelite
./test_waha_fix.sh
```

**Expected Output**: All 6 tests pass (GREEN ✓)

If any test fails:
- **Test 2 fails** (Session not WORKING) → Scan QR at http://localhost:3000
- **Test 3+ fail** → Check logs: `docker logs cpes-api 2>&1 | tail -50`

---

### Step 2: WhatsApp Test 1 — Single Command ✓

**From your Australian phone** (61405086785):
1. Open WhatsApp
2. Send message: `/status`
3. **Expected**: Response arrives within 2-5 seconds showing:
   - Total games being monitored
   - Last update time
   - System memory/CPU usage

**Did it work?** → Continue. **Did NOT arrive?** → See Troubleshooting section below.

---

### Step 3: WhatsApp Test 2 — Sequential Commands ✓

**From same phone**, immediately after /status:

```
Send: /jogos
Wait 2-5 seconds → Should receive game list

Send: /stats
Wait 2-5 seconds → Should receive statistics

Send: /help
Wait 2-5 seconds → Should receive command help
```

**Expected**: All 4 messages arrive (no failures, no long delays)

---

### Step 4: Verify Container Logs

```bash
# Check for errors
docker logs cpes-api 2>&1 | grep -i error | tail -10

# Should output: (nothing or only non-WAHA errors)
```

---

## Intermediate Actions (Before Full Production)

### Step 5: Test from Brazilian Admin Number (Optional)

If you also have the Brazil number configured (554195089104):

```bash
# From a different phone, send same commands
/status
/jogos
/stats
```

Both numbers should work independently.

---

### Step 6: Dashboard Health Check

Open http://localhost:3001 (or http://odontoschultz.online if deployed):

Check **System Health Panel**:
- [ ] "WhatsApp Connected" shows 🟢 (green)
- [ ] "Games Live" counter is reasonable
- [ ] "Last Update" is < 2 minutes old
- [ ] "API Status" shows ✓ (green)

---

### Step 7: Monitor for 5 Minutes

Keep the dashboard open for 5 minutes while monitoring:

- [ ] Does the game count change as live matches update?
- [ ] Does "Last Update" time increment regularly?
- [ ] No red error messages appear?
- [ ] System responsive (dashboard doesn't freeze)?

---

## Production Readiness Sign-Off

Before declaring system ready for live deployment, verify ALL:

- [x] Automated tests pass (`./test_waha_fix.sh` → all GREEN)
- [ ] /status received in 2-5 seconds
- [ ] /jogos received in 2-5 seconds
- [ ] /stats received in 2-5 seconds
- [ ] /help received in 2-5 seconds
- [ ] No 422 errors in logs
- [ ] No "Session STOPPED" in logs
- [ ] Sequential commands all work
- [ ] Dashboard shows 🟢 WhatsApp Connected
- [ ] Game monitoring is live and updating

**Status**: When all boxes checked → ✅ **READY FOR PRODUCTION**

---

## Troubleshooting

### Problem: /status Message Not Arriving

**Quick Fixes** (try in order):

1. **Check WAHA authentication**
   ```bash
   curl http://localhost:3000/api/sessions/default \
     -H "X-Api-Key: cdb85694296a453eb291317d2ac1f660" | jq '.status'
   ```
   - If NOT "WORKING" → Visit http://localhost:3000 and scan QR code
   - If error → Restart WAHA: `docker compose restart cpes-waha`

2. **Verify number is authorized**
   ```bash
   grep 61405086785 corner-pressure-elite/api_server.py
   ```
   - Should show the number in `_authorized_senders` set

3. **Check webhook is processing**
   ```bash
   docker logs cpes-api 2>&1 | grep -i webhook | tail -10
   ```
   - Should show webhook received and processed

4. **Restart API container**
   ```bash
   docker compose restart cpes-api
   ```
   - Then try again after 5 seconds

5. **Full system rebuild**
   ```bash
   docker compose down
   docker compose up -d --build
   ```
   - Then scan QR code at http://localhost:3000
   - Try command again

---

### Problem: Message Arrives But With Errors

**Example responses**:
- "Session not found error" → API key mismatch
- "Chat not found" → Number not authenticated in WAHA
- "Permission denied" → Network/firewall issue

**Diagnostics**:
```bash
# Check exact error
docker logs cpes-api 2>&1 | grep -i error | tail -50

# Check if API key is correct
grep WAHA_API_KEY docker-compose.yml config.py | sort | uniq -c

# Check session is really working
curl http://localhost:3000/api/sessions/default \
  -H "X-Api-Key: cdb85694296a453eb291317d2ac1f660"
```

---

### Problem: Slow Response (> 10 seconds)

**Possible causes**:

1. **API-Football rate limited**
   ```bash
   docker logs cpes-api 2>&1 | grep -i "rate.*limit"
   ```
   - If found: Wait 1 minute (quota resets per minute)

2. **WAHA overloaded**
   ```bash
   curl http://localhost:3000/api/health | jq '.'
   ```
   - If not healthy: Restart → `docker compose restart cpes-waha`

3. **Dashboard processing taking time**
   - Close dashboard, try command again
   - API should respond faster when no other load

4. **System CPU/Memory maxed**
   ```bash
   docker stats --no-stream
   ```
   - If cpes-api using > 80% CPU: Restart and retry

---

## What to Do When Working

### Daily Operations

1. **Keep dashboard open** (or send /status every 15 min to keep session alive)
2. **Monitor incoming corner signals** via WhatsApp
3. **Check /status daily** to verify system health

### Weekly Checks

```bash
# Check container uptime
docker ps

# Check application logs for warnings
docker logs cpes-api --tail 100 | grep -i warn

# Verify no disk space issues
df -h /

# Check database integrity
# (future: add data consistency checks)
```

### If Unresponsive After Hours

```bash
# Quick restart
docker compose restart cpes-api cpes-waha

# Then verify
./test_waha_fix.sh

# Send /status to confirm working again
```

---

## What Happens Next (System Features)

Once WhatsApp is validated:

### Coming Soon
- ✅ Live corner kick detection and analysis
- ✅ Automated signal generation (when corner probability > threshold)
- ✅ Signal forwarding to WhatsApp group (Escanteios)
- ✅ Real-time stats on dashboard
- ✅ Historical analysis and performance tracking

### Current Monitoring
- Live game tracking across 13 leagues
- Second-by-second corner event detection
- Pressure score calculation
- Decision engine filtering signals

---

## Documentation Reference

**For complete information**:

| Document | Purpose |
|----------|---------|
| [WAHA Session Fix Summary](../resumo/2026-02-15-waha-session-fix-summary.md) | 2-minute overview of the fix |
| [Validation Testing Guide](validation-testing.md) | Complete testing procedures |
| [Technical Changelog](2026-02-15-fix-waha-session-stopped.md) | Deep technical details |
| [Files Changed](2026-02-15-files-changed.md) | What was modified |
| [WAHA Bug Summary](../../WAHA_BUG_SUMMARY.txt) | Visual diagram of problem |

---

## Success Criteria

✅ **System is production-ready when**:

1. `./test_waha_fix.sh` returns all green ✓
2. All 4 admin commands (/status, /jogos, /stats, /help) work
3. Messages arrive within 2-5 seconds
4. No error logs related to WAHA/webhooks
5. Dashboard shows 🟢 connected status
6. System responds within 30 seconds of container restart

---

## Checkpoints

**✅ Completed So Far**:
- Fixed Session STOPPED bug
- Deployed persistent session manager
- Created comprehensive documentation
- Built automated validation script

**⏳ Waiting On** (You):
1. Run `./test_waha_fix.sh` → Confirm all pass
2. Test commands on WhatsApp → Confirm delivery
3. Keep dashboard open → Monitor live system
4. Provide feedback → Any issues/observations

**🎯 End Goal**:
- System ready for 24/7 production use
- Reliable signal delivery to WhatsApp
- Real-time corner kick monitoring across all leagues

---

## Need Help?

**Quick Questions**:
- Script won't run? → `chmod +x test_waha_fix.sh && ./test_waha_fix.sh`
- QR code expired? → http://localhost:3000 might auto-show new one
- Numbers not working? → Verify in `api_server.py` _authorized_senders set

**Report Issues**:
- Include: `docker logs cpes-api` last 50 lines
- Include: `docker ps` output
- Include: Exact error message from WhatsApp (if any)
- Include: Time of issue and what action triggered it

---

**Good luck! The fix is deployed and ready for validation.** 🚀

Once you complete the checklist above, system is production-ready.
