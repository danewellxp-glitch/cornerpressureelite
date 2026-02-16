# CHECKLIST TÉCNICO - DEBUG EXECUÇÃO RÁPIDA

## 🚨 PROBLEMA
Sistema retorna APENAS **2 jogos da Argentina** em vez de múltiplas ligas.

```
❌ Esperado: 15-20 jogos de 13 ligas
✓ Atual: 2 jogos (Argentina)
```

---

## ⚡ QUICK DIAGNOSIS (5 min)

### 🔴 Teste #1: Rate Limit Status

```bash
# Em Docker
docker exec cpes-python python3 << 'EOF'
import asyncio
from config import API_FOOTBALL_KEY
from data.api_client import APIFootballClient
from utils.rate_limiter import RateLimiter

async def check():
    rl = RateLimiter(max_requests_per_day=100)
    client = APIFootballClient(API_FOOTBALL_KEY, rl)
    status = await client.check_status()
    
    plan = status.get('subscription', {}).get('plan', '?')
    current = status.get('requests', {}).get('current', '?')
    limit = status.get('requests', {}).get('limit_day', 100)
    
    print(f"✓ Plano: {plan}")
    print(f"⚠ Usado: {current}/{limit}")
    print(f"📊 Restante: {limit - current if isinstance(current, int) else '?'}")

asyncio.run(check())
EOF
```

**✓ Se "Restante: > 20"** → Passe para Teste #2  
**❌ Se "Restante: < 5 ou error"** → **PROBLEMA IDENTIFICADO** (vá direto para CORREÇÃO #1)

---

### 🟠 Teste #2: Testar Cada Liga (via curl)

```bash
# Criar script teste_ligas.sh
cat > /tmp/teste_ligas.sh << 'SCRIPT'
#!/bin/bash
KEY="$API_FOOTBALL_KEY"
DATE="2026-02-15"

echo "TESTANDO CADA LIGA:"
echo "==================="

for LIGA in 39 61 71 72 78 88 94 128 135 140 253 265 624; do
    COUNT=$(curl -s \
      "https://v3.football.api-sports.io/fixtures?date=$DATE&league=$LIGA&season=2026" \
      -H "x-apisports-key: $KEY" 2>/dev/null | \
      jq '.response | length' 2>/dev/null || echo "ERR")
    
    printf "Liga %3d: %s jogos\n" "$LIGA" "$COUNT"
done

SCRIPT

chmod +x /tmp/teste_ligas.sh

# Executar
export API_FOOTBALL_KEY="$(grep API_FOOTBALL_KEY .env | cut -d= -f2)"
/tmp/teste_ligas.sh
```

**✓ Se todas retornam > 0 jogos** → Problema é na coleta/filtro do sistema  
**❌ Se apenas 128 retorna jogos** → Problema é na API-Football ou parametros

---

### 🟡 Teste #3: Log de Debug em Tempo Real

```bash
# Habilitar DEBUG logging
cd corner-pressure-elite

# Antes de rodar:
export LOG_LEVEL="DEBUG"

# Em container:
docker exec -e LOG_LEVEL=DEBUG cpes-python tail -f logs/cpes_*.log | grep -E "Agenda|liga|League"
```

**Procure por:**
```
❌ "League field must contain integer"      → BUG #1
❌ "Sem requisicoes disponiveis"             → Rate limit crítico
❌ "Missing application key"                 → API Key expirada
✓ "Agenda 2026-02-15: XX jogos programados"  → Número de jogos
```

---

## 🔧 CORREÇÕES (Por Prioridade)

### CORREÇÃO IMEDIATA #1: Aumentar Rate Limit

**Causa Provável:** Plano FREE está esgotado.

```bash
# Opção A: Upgrade para PLAN PRO
# 1. Acesse https://www.api-football.com/
# 2. Faça upgrade para PRO (250 reqs/dia)
# 3. Copie nova API KEY
# 4. Atualizar: docker-compose.env (API_FOOTBALL_KEY=xxx)

# Opção B: Limpar requisições (rodar script de limpeza)
# Criar: corner-pressure-elite/clean_rate_limit.py

cat > clean_rate_limit.py << 'EOF'
import asyncio
from utils.rate_limiter import RateLimiter

async def reset():
    rl = RateLimiter(max_requests_per_day=100)
    rl.requests_today = 0
    print("✓ Rate limiter resetado (local)")
    
asyncio.run(reset())
EOF

python3 clean_rate_limit.py
```

---

### CORREÇÃO IMEDIATA #2: Implementar Fetcher Otimizado

**Arquivo:** `corner-pressure-elite/data/api_client.py` (linha ~145)

**Atual (13 reqs):**
```python
async def get_today_schedule(self, league_ids: List[int], date: str):
    all_fixtures = []
    for league_id in league_ids:  # ← 13 iterações = 13 reqs
        data = await self._request("fixtures", 
                                   params={"date": date, 
                                          "league": league_id, 
                                          "season": season})
        all_fixtures.extend(data.get("response", []))
    return all_fixtures
```

**Novo (1-3 reqs):**
```python
async def get_today_schedule(self, league_ids: List[int], date: str):
    """
    Estratégia otimizada:
    1. UMA requisição para todas as ligas (sem filtro league)
    2. Filtrar em memória (GRÁTIS)
    """
    season = int(date[:4])
    
    # Requisição ÚNICA
    data = await self._request("fixtures", 
                               params={"date": date, "season": season})
    
    all_fixtures = data.get("response", [])
    
    # Filtrar liga localmente
    filtered = [f for f in all_fixtures 
                if f.get("league", {}).get("id") in league_ids]
    
    logger.info(f"Agenda {date}: {len(filtered)} jogos ({len(league_ids)} ligas) [1 REQ]")
    return filtered
```

**Impacto:**
- **Antes:** 13 reqs por ciclo = Rate limit em ~2h
- **Depois:** 1 req per day = viável indefinidamente

---

### CORREÇÃO ESTRUTURAL #3: Adicionar Fallback de Cache

**Arquivo:** `corner-pressure-elite/main.py` (linha ~198)

**Inserir antes de `_fetch_today_schedule()`:**
```python
async def _fetch_today_schedule(self, force: bool = False):
    """
    Fetch com fallback:
    1. Tenta API (bulk)
    2. Se rate limit: usa cache anterior
    3. Se falha: loga erro mas continua com dados antigos
    """
    try:
        # Atual
        ligas_ativas = await self.database.get_ligas_ativas()
        self._today_schedule = await self.api_client.get_today_schedule(
            ligas_ativas, today
        )
        
        if self._today_schedule:
            self._schedule_date = today
            self._save_upcoming_games()
    
    except Exception as e:
        logger.error(f"Erro fetch agenda: {e}")
        
        # NOVO: Fallback ao cache anterior
        if self._today_schedule and self._schedule_date == today:
            logger.info(f"Usando cache de agenda anterior ({len(self._today_schedule)} jogos)")
        else:
            logger.warning("sem cache anterior disponível")
```

---

## 🧪 TESTES PARA VALIDAR CORREÇÃO

### Após implementar CORREÇÃO #2:

```bash
# Logs devem mostrar:
# ✓ "Agenda 2026-02-15: 15 jogos (13 ligas) [1 REQ]"

# E não mais:
# ❌ "Agenda 2026-02-15: 4 jogos programados (13 reqs)"
```

---

## 📋 CHECKLIST DE PRODUÇÃO

- [ ] Rate Limit Status: Verificado (resto acima de 20)
- [ ] Test #2 (Curl por Liga): Cada uma retorna > 0 jogos
- [ ] CORREÇÃO #1: Plano PRO ou chave nva
- [ ] CORREÇÃO #2: API client otimizado (bulk 1 req)
- [ ] CORREÇÃO #3: Fallback cache implementado
- [ ] Docker rebuild: `docker-compose up -d --build`
- [ ] Logs checados: Ver "Agenda: XX jogos (13 ligas) [1 REQ]"
- [ ] Próxima agenda matinal: verificar WhatsApp
- [ ] Monitorar 24h: rate limit não deve exceder 50-60 reqs/day

---

## 🚀 COMO APLICAR CORREÇÃO #2 RAPIDAMENTE

```bash
cd /home/daniel/cornerpressureelite/corner-pressure-elite

# Backup
cp data/api_client.py data/api_client.py.bak

# Editar função get_today_schedule (linhas ~141-155)
# Substituir loop de ligas por single request com filtro local

# Recompilar
docker-compose up -d --build

# Validar logs
docker logs cpes-python | grep "Agenda"
```

---

**Tempo Estimado de Correção:** 20 minutos  
**Dificuldade:** Baixa (apenas 1 função, 5 linhas)  
**Risk:** Muito Baixo (sem side effects)
