# TESTES MANUAIS - Confirmar Diagnóstico da Agenda

Este documento fornece testes passo a passo que você pode rodar **agora** para confirmar qual é o exato problema com a agenda (apenas Argentina retorna).

---

## TESTE 1: Verificar Rate Limit (2 min)

### Passo 1.1: Conectar ao Container

```bash
cd /home/daniel/cornerpressureelite
docker ps | grep cpes
```

Procure por algo como: `cpes-python` ou `corner-pressure-elite_backend`

### Passo 1.2: Rodar Status Check

```bash
docker exec cpes-python python3 << 'EOF'
import asyncio
from config import API_FOOTBALL_KEY
from data.api_client import APIFootballClient
from utils.rate_limiter import RateLimiter

async def test():
    rl = RateLimiter(max_requests_per_day=100)
    client = APIFootballClient(API_FOOTBALL_KEY, rl)
    
    try:
        status = await client.check_status()
        req = status.get("requests", {})
        sub = status.get("subscription", {})
        
        current = req.get("current", "?")
        limit = req.get("limit_day", 100)
        plan = sub.get("plan", "?")
        
        print(f"\n{'='*50}")
        print(f"  API-FOOTBALL STATUS")
        print(f"{'='*50}")
        print(f"Plano: {plan}")
        print(f"Usado hoje: {current}/{limit}")
        remaining = limit - current if isinstance(current, int) else "?"
        print(f"Restante: {remaining}")
        
        if isinstance(current, int) and current >= limit:
            print(f"\n🔴 CRÍTICO: Rate limit ATINGIDO!")
        elif isinstance(current, int) and current >= limit * 0.8:
            print(f"\n⚠️  AVISO: 80% do limit usado")
        else:
            print(f"\n✓ OK - requisições disponíveis")
        print(f"{'='*50}\n")
    except Exception as e:
        print(f"❌ ERRO ao conectar: {e}")

asyncio.run(test())
EOF
```

### Passo 1.3: Interpretar Resultado

| Resultado | Status | Próximo Passo |
|-----------|--------|-----------------|
| "Restante: > 20" | ✓ OK | Teste 2 |
| "Restante: 5-20" | ⚠️ AVISO | Teste 2 (cuidado) |
| "Restante: 0" ou "CRÍTICO" | 🔴 PROBLEMA | Ir para FIX #1 |
| "ERRO ao conectar" | ❌ FALHA | Verificar API KEY |

---

## TESTE 2: Testar Requisição para Cada Liga (5 min)

### Passo 2.1: Criar Script Teste

```bash
cat > /tmp/test_leagues.sh << 'SCRIPT'
#!/bin/bash

API_KEY="YOUR_KEY_HERE"
DATE="2026-02-15"
SEASON="2026"

# Ler API_KEY do container
API_KEY=$(docker exec cpes-python python3 -c "from config import API_FOOTBALL_KEY; print(API_FOOTBALL_KEY)")

if [ -z "$API_KEY" ] || [ "$API_KEY" == "None" ]; then
    echo "❌ ERRO: API_FOOTBALL_KEY não configurada"
    exit 1
fi

echo ""
echo "════════════════════════════════════════════════════"
echo "TESTE DE LIGAS - Data: $DATE"
echo "════════════════════════════════════════════════════"
echo ""

test_league() {
    local ID=$1
    local NAME=$2
    
    echo -n "Liga $ID ($NAME)... "
    
    RESULT=$(curl -s \
        -X GET "https://v3.football.api-sports.io/fixtures" \
        -H "x-apisports-key: $API_KEY" \
        --data-urlencode "date=$DATE" \
        --data-urlencode "league=$ID" \
        --data-urlencode "season=$SEASON" \
        2>/dev/null)
    
    # Verificar erro
    if echo "$RESULT" | grep -q "Missing application key"; then
        echo "❌ API KEY inválida"
        return
    fi
    
    if echo "$RESULT" | grep -q "error\|Error"; then
        echo "❌ Erro na API"
        return
    fi
    
    # Contar jogos
    COUNT=$(echo "$RESULT" | python3 -c "import sys, json; data=json.load(sys.stdin); print(len(data.get('response', [])))" 2>/dev/null)
    
    if [ -z "$COUNT" ]; then
        COUNT="?"
    fi
    
    printf "%-3s jogos\n" "$COUNT"
}

# Big 5
test_league 39 "Premier League"
test_league 61 "Ligue 1"
test_league 78 "Bundesliga"
test_league 135 "Serie A"
test_league 140 "La Liga"

# Secundárias
test_league 88 "Eredivisie"
test_league 94 "Liga Portugal"

# Brasil
test_league 71 "Brasileirão A"
test_league 72 "Brasileirão B"
test_league 624 "Carioca"

# Americas
test_league 128 "Argentina"
test_league 265 "Chile"
test_league 253 "MLS"

echo ""
echo "════════════════════════════════════════════════════"

SCRIPT

chmod +x /tmp/test_leagues.sh
```

### Passo 2.2: Rodar Script

```bash
/tmp/test_leagues.sh
```

### Passo 2.3: Esperado vs Atual

**Esperado:**
```
Liga 39 (Premier League)... 3 jogos
Liga 61 (Ligue 1)... 2 jogos
Liga 78 (Bundesliga)... 2 jogos
...
Liga 128 (Argentina)... 2 jogos
...
```

**Atual (PROBLEMA):**
```
Liga 39 (Premier League)... ? jogos
Liga 61 (Ligue 1)... ? jogos
...
Liga 128 (Argentina)... 2 jogos ← APENAS ESTA RETORNA
...
```

---

## TESTE 3: Testar Requisição BULK (1 liga) vs INDIVIDUAL (13 ligas)

### Passo 3.1: Teste BULK (Sem Filtro de Liga)

```bash
API_KEY=$(docker exec cpes-python python3 -c "from config import API_FOOTBALL_KEY; print(API_FOOTBALL_KEY)")

echo "Teste BULK (1 requisição, sem league parameter):"
echo "=================================================="

RESULT=$(curl -s \
    -X GET "https://v3.football.api-sports.io/fixtures" \
    -H "x-apisports-key: $API_KEY" \
    --data-urlencode "date=2026-02-15" \
    --data-urlencode "season=2026" \
    2>/dev/null)

TOTAL=$(echo "$RESULT" | python3 -c "import sys, json; data=json.load(sys.stdin); print(len(data.get('response', [])))")

echo "✓ Total de jogos retornados: $TOTAL"

# Contar por liga
echo ""
echo "Distribuição por liga:"
echo "$RESULT" | python3 << 'PYSCRIPT'
import sys, json
data = json.load(sys.stdin)
by_league = {}
for fixture in data.get('response', []):
    league = fixture.get('league', {}).get('name', 'Unknown')
    by_league[league] = by_league.get(league, 0) + 1

for league in sorted(by_league.keys()):
    print(f"  {league}: {by_league[league]} jogos")
PYSCRIPT
```

### Passo 3.2: Teste INDIVIDUAL (13 requisições, com league=ID)

```bash
echo ""
echo "Teste INDIVIDUAL (13 requisições, loop por liga):"
echo "=================================================="

LIGAS=(39 61 71 72 78 88 94 128 135 140 253 265 624)
TOTAL=0

for LIGA in "${LIGAS[@]}"; do
    RESULT=$(curl -s \
        -X GET "https://v3.football.api-sports.io/fixtures" \
        -H "x-apisports-key: $API_KEY" \
        --data-urlencode "date=2026-02-15" \
        --data-urlencode "league=$LIGA" \
        --data-urlencode "season=2026" \
        2>/dev/null)
    
    COUNT=$(echo "$RESULT" | python3 -c "import sys, json; data=json.load(sys.stdin); print(len(data.get('response', [])))" 2>/dev/null || echo "0")
    
    TOTAL=$((TOTAL + COUNT))
done

echo "✓ Total somado de 13 requisições: $TOTAL"
```

### Passo 3.3: Comparar

```
BULK (1 req): 15 jogos
INDIVIDUAL (13 reqs): 15 jogos
→ Números iguais? OK, problema em outro lugar
→ INDIVIDUAL retorna menos? BUG no loop
```

---

## TESTE 4: Verificar upcoming_games.json vs _today_schedule

### Passo 4.1: Checar Atual JSON

```bash
echo "Conteúdo de upcoming_games.json:"
echo "================================"
cd /home/daniel/cornerpressureelite
cat corner-pressure-elite/data/upcoming_games.json | python3 -m json.tool | head -50

echo ""
echo "Contagem por liga:"
cat corner-pressure-elite/data/upcoming_games.json | \
python3 -c "import sys, json; data=json.load(sys.stdin); \
by_league = {}; \
[by_league.setdefault(g.get('liga', '?'), 0).__add__(1) \
 for g in data.get('proximos', [])]; \
[print(f'{l}: {by_league[l]}') for l in sorted(by_league.keys())]"
```

**Esperado:** Múltiplas ligas  
**Atual:** Apenas Argentina

---

## TESTE 5: Simular _fetch_today_schedule() Manualmente

### Passo 5.1: Rodar Coleta

```bash
docker exec cpes-python python3 << 'EOF'
import asyncio
from datetime import datetime
from config import API_FOOTBALL_KEY, LIGAS_MONITORADAS
from data.api_client import APIFootballClient
from utils.rate_limiter import RateLimiter
from storage.database import Database

async def test_fetch():
    print("\n" + "="*60)
    print("  SIMULANDO _fetch_today_schedule()")
    print("="*60)
    
    rl = RateLimiter(max_requests_per_day=100)
    client = APIFootballClient(API_FOOTBALL_KEY, rl)
    db = Database()
    
    today = datetime.now().strftime("%Y-%m-%d")
    
    print(f"\nData: {today}")
    print(f"Ligas configuradas: {len(LIGAS_MONITORADAS)}")
    
    # Ligas ativas do banco
    ligas_ativas = await db.get_ligas_ativas()
    print(f"Ligas ativas (do banco): {len(ligas_ativas)} = {ligas_ativas}\n")
    
    # Call fetch
    print(f"Chamando get_today_schedule({len(ligas_ativas)} ligas)...")
    fixtures = await client.get_today_schedule(ligas_ativas, today)
    
    print(f"\n✓ Total fixtures retornado: {len(fixtures)}")
    
    # Agrupar por liga
    por_liga = {}
    for f in fixtures:
        liga = f.get("league", {}).get("name", "Unknown")
        por_liga[liga] = por_liga.get(liga, 0) + 1
    
    print(f"\nPor liga:")
    for liga in sorted(por_liga.keys()):
        count = por_liga[liga]
        print(f"  {liga}: {count} jogos")
    
    print("\n" + "="*60)

asyncio.run(test_fetch())
EOF
```

---

## TESTE 6: Verificar Logs em Tempo Real

### Passo 6.1: Acompanhar Agenda Matcher

```bash
docker logs -f cpes-python 2>&1 | grep -E "Agenda|upcoming|schedule|agenda" | head -20
```

**Procure por:**
```
✓ "Agenda 2026-02-15: 15 jogos programados (13 reqs)" → OK
❌ "Agenda 2026-02-15: 4 jogos programados (13 reqs)" → Problema
❌ "The League field must contain an integer" → BUG #1
```

---

## TESTE 7: Log Estruturado de Rate Limit

### Passo 7.1: Habilitar DEBUG

```bash
# Parar container
docker-compose down

# Editar .env
echo "LOG_LEVEL=DEBUG" >> .env

# Rodar
docker-compose up -d

# Acompanhar
docker logs -f cpes-python 2>&1 | grep -i "rate\|requisic\|api" | head -30
```

---

## 📊 MATRIZ DE DIAGNÓSTICO

| Teste | Resultado OK | Resultado PROBLEMA | Causa Provável |
|-------|--------------|-------------------|-----------------|
| Teste 1 | > 20 reqs | < 5 reqs | Rate limit atingido |
| Teste 2 | > 10 ligas retornam | Apenas Argentina | API-Football bug ou permissões |
| Teste 3 | BULK ≈ INDIVIDUAL | INDIVIDUAL < BULK | Loop termina cedo |
| Teste 4 | Múltiplas ligas | Apenas Argentina | Filtro em _save_upcoming_games() |
| Teste 5 | > 10 fixtures | < 5 fixtures | collect_today_schedule() filtra |
| Teste 6 | "15 jogos (13 reqs)" | "4 jogos (13 reqs)" | Em algum filtro/conversão |

---

## ✅ CHECKLIST DE EXECUÇÃO

- [ ] Teste 1 rodou: Rate Limit Status verificado
- [ ] Teste 2 rodou: Cada liga testada via curl
- [ ] Teste 3 rodou: BULK vs INDIVIDUAL comparados
- [ ] Teste 4 rodou: upcoming_games.json inspecionado
- [ ] Teste 5 rodou: _fetch_today_schedule() simulado
- [ ] Teste 6 rodou: Logs analisados
- [ ] Teste 7 rodou: DEBUG logging ativo

---

## 🔍 SE TODOS OS TESTES FALHAREM

Se nenhum dos testes acima confirma o problema:

1. **Coletar mais logs:**
```bash
docker logs cpes-python > /tmp/cpes_full_log.txt
cat /tmp/cpes_full_log.txt | grep -E "liga|liga|league|request" > /tmp/cpes_liga_log.txt
```

2. **Inspecionar JSON responses:**
```bash
# Adicionar debug log em api_client.py
# Linhas ~150: print(json.dumps(data, indent=2))
```

3. **Rodar com strace:**
```bash
docker exec cpes-python python3 -c "..." 2>&1 | strace -e write
```

---

**Duração Estimada:** 15-20 minutos para todos os testes  
**Dificuldade:** Baixa (copiar/colar)  
**Resultado:** 100% identificação do problema
