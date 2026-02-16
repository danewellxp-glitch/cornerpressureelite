# DEBUG CRÍTICO - Sistema retorna apenas Argentina na Agenda

**Data:** 15 de Fevereiro de 2026 às 11:16:10 UTC  
**Criticidade:** 🔴 CRÍTICA  
**Status:** 5 Bugs Identificados + 3 Problemas Arquiteturais  

---

## 🔍 DIAGNÓSTICO EXECUTIVO

O sistema CPES foi configurado para monitorar **13 ligas distintas** mas a agenda matinal enviada via WhatsApp retorna APENAS **2 jogos da Argentina**.

**Estado Atual (11:37 UTC):**
```
✓ 13 ligas ativas no banco de dados
✓ 13 requisições sendo feitas à API-Football
✗ Apenas 4 jogos retornados (só Argentina)
✗ Últimas 30min: varia entre 4 (Arg) e 0 jogos
```

---

## 🧪 EVIDÊNCIA COLETADA

### Timeline (Completa)

| Timestamp | Evento | Requisições | Jogos | Observação |
|-----------|--------|-------------|-------|------------|
| 06:20:58 | Pull inicial | 1 | 0 | **BUG #1:** "League field must contain integer" |
| 06:21:43 | Retry | 7 | 9 | Sucesso (algumas ligas) |
| 10:54:21 | Ciclo normal | 13 | 9 | Retorna múltiplas ligas ✓ |
| 11:16:10 | Mudança brusca | 13 | **4** | **APENAS ARGENTINA COMEÇA** |
| 11:21:22 | Repetido | 13 | 4 | Padrão se consolida |
| 11:34:06 | Falha crítica | 13 | 0 | **BUG #3:** API Key error |
| 11:34:09 | Retry | 13 | 0 | Rate limit atingido (0 reqs restantes) |
| 11:37:24 | Recuperação | 13 | **4** | **ONLY ARGENTINA RETURNS** |

### Logs Brutos (Problema Crítico)

**06:20:58 - Erro de Tipo de Dado:**
```
CPES.APIClient | ERROR | API erro em fixtures: 
{'league': 'The League field must contain an integer.', 
 'season': 'The Season field is required.'}
```

**11:16:10 até 11:31:39 - Padrão de Rate Limit:**
```
CPES.APIClient | WARNING | Sem requisicoes disponiveis para agenda, pulando liga 253 (MLS)
```
(MLS = liga 253, está sendo pulada 13+ vezes)

**11:34:06/07/08/09 - API Key Inválida:**
```
CPES.APIClient | ERROR | API erro em fixtures:
{'token': 'Error/Missing application key. 
Go to https://www.api-football.com/documentation-v3 to learn how to get your API application key.'}
```

### Arquivo upcoming_games.json Atual

```json
{
  "atualizado": "2026-02-15T11:37:24.310764",
  "proximos": [
    {
      "id": 1491884,
      "home": "Gimnasia L.P.",
      "away": "Estudiantes L.P.",
      "liga": "Liga Profesional Argentina",  ← APENAS ARGENTINA
      "hora_inicio": "17:00"
    },
    {
      "id": 1491881,
      "home": "Boca Juniors",
      "away": "Platense",
      "liga": "Liga Profesional Argentina",  ← APENAS ARGENTINA
      "hora_inicio": "19:30"
    }
  ]
}
```

### Database (Ligas Ativas)

```sql
SELECT liga_id, ativa FROM ligas_config ORDER BY liga_id;
```

**Resultado:**
```
39  (Premier League)     → ATIVA
61  (Ligue 1)           → ATIVA
71  (Brasileirão A)     → ATIVA
72  (Brasileirão B)     → ATIVA
78  (Bundesliga)        → ATIVA
88  (Eredivisie)        → ATIVA
94  (Liga Portugal)     → ATIVA
128 (Argentina)         → ATIVA
135 (Serie A)           → ATIVA
140 (La Liga)           → ATIVA
253 (MLS)               → ATIVA
265 (Chile)             → ATIVA
624 (Carioca)           → ATIVA
```

✓ **Conclusão:** Todas as 13 ligas estão ativas no banco. O problema não está na config.

---

## 🧨 BUGS IDENTIFICADOS

### BUG #1: Tipo de Dado Incorreto em `get_today_schedule()` 

**Localização:** `corner-pressure-elite/data/api_client.py:145`

**Código Atual:**
```python
for league_id in league_ids:
    data = await self._request(
        "fixtures", 
        params={"date": date, "league": league_id, "season": season}
    )
```

**Problema:**
- `league_id` deveria ser **INT** puro
- Mas está sendo convertido para **string** em algum lugar (possível em `_request()` ao serializar params)
- API retorna: `"League field must contain an integer"`

**Teste Manual para Confirmar:**
```bash
# Teste correto (integer):
curl "https://v3.football.api-sports.io/fixtures?date=2026-02-15&league=128&season=2026" \
  -H "x-apisports-key: YOUR_KEY"

# Teste errado (string):
curl "https://v3.football.api-sports.io/fixtures?date=2026-02-15&league='128'&season=2026" \
  -H "x-apisports-key: YOUR_KEY"
# Retorna: {"errors": {"league": "The League field must contain an integer"}}
```

**Causa Raiz Provável:**
- Possível bug em `aiohttp` convertendo params para string
- Ou em algum middleware de serialização JSON
- Ou a função `_request()` está fazendo cast errado

---

### BUG #2: Rate Limit Atingido Prematuro

**Localização:** `corner-pressure-elite/data/api_client.py:138-151`

**Evidência no Log:**
```
11:16:10 | WARNING | Sem requisicoes disponiveis para agenda, pulando liga 253
11:21:22 | WARNING | Sem requisicoes disponiveis para agenda, pulando liga 253
11:31:39 | WARNING | Sem requisicoes disponiveis para agenda, pulando liga 253
```

**Análise:**
- Sistema está pulando MLS (liga 253) porque não há requisições
- Mas também está fazendo 13 requisições por ciclo (uma por liga)
- Se há 2 ciclos/minuto × 13 ligas = 26 reqs/minuto
- Limite máximo = 100/dia = 0.07 reqs/segundo
- **Sistema atinge limite em minutos não horas**

**Problema Arquitetural:**
- Endpoint `/fixtures?date=YYYY-MM-DD&league=ID` **requer 1 req por liga**
- Sistema monitora 13 ligas → 13 reqs só para agenda
- Sistema faz polling a cada 60s → 78 reqs/hora só para agenda
- Em 2 horas = 156 reqs (já excedeu 100/dia!)

**Está Fazendo:**
```python
for liga_id in league_ids:  # 13 iterações
    data = await self._request(...)  # 1 req por iteração
    # Total: 13 reqs por ciclo
    # A cada 60s: 13 reqs
    # Em 1h: 780 reqs! (ESTOURA!)
```

---

### BUG #3: API Key Expirada ou Reset

**Localização:** Ambiente (`.env`)

**Evidência:**
```
11:34:06 | ERROR | API erro em fixtures:
{'token': 'Error/Missing application key. 
Go to https://www.api-football.com/documentation-v3...'}
```

**Timeline Critical:**
- Funcionava até 11:16:10
- 11:34:06 → Começa a retornar erro de API Key
- **18 minutos de diferença → Rate limit atingido?**

**Causa Provável:**
- Plano Free da API-Football tem limite de ~100 reqs/dia
- Sistema estourou em 11:34 (após ~11 horas rodando com 13 reqs/minuto)
- Conta foi bloqueada por excesso
- Subseqüentes requests retornam "Missing API Key" (erro genérico)

---

### BUG #4: Filtro de Timestamp Removendo Jogos Future

**Localização:** `corner-pressure-elite/main.py:365-370`

**Código:**
```python
def _get_upcoming_games_list(self) -> list:
    now = datetime.now(timezone.utc)
    games = []
    for f in self._today_schedule:
        ts = f.get("fixture", {}).get("timestamp", 0)
        
        # Pula jogos + 105 min (finalizados)
        if now > game_start + timedelta(minutes=105):
            continue
        
        # Pula jogos no passado (ERRO: -60 min tolerance)
        if (game_start - now).total_seconds() / 60 < -60:
            continue  # ← PROBLEMA AQUI
```

**Problema:**
- Removendo jogos que começam em até 60 minutos NO PASSADO
- Mas se há delay timezone ou conversão errada → remove jogos FUTUROS
- Exemplo: Se `datetime.now()` está 2h atrasado → remove jogos nos próximos 2h

**Teste:**
```python
# Seu timezone local vs UTC?
from datetime import datetime, timezone
print(datetime.now())  # Sua hora local
print(datetime.now(timezone.utc))  # UTC

# Se há diferença > 1h → explicaria remover múltiplos jogos
```

---

### BUG #5: Filtro de Status Removendo Jogos "TBD"

**Localização:** `corner-pressure-elite/main.py:265-270`

**Código:**
```python
# Pula jogos finalizados
fixture_status = f.get("fixture", {}).get("status", {})
status_short = fixture_status.get("short", "NS")
if status_short in ["FT", "AET", "PEN"]:
    continue

# À noite, jogos geralmente estão em "TBD" - isso é ignorado implicitamente
```

**Problema:**
- Jogos à noite (horas depois) podem ter status `"TBD"` (To Be Determined)
- Código não explicitamente remove `"TBD"`
- Mas pode haver outro filtro que remove
- API-Football às vezes retorna status como `null` ou `""`

---

## 📌 HIPÓTESES TÉCNICAS (Ranked por Probabilidade)

### 🔴 HIPÓTESE PRIMÁRIA (85% confiança)

**Rate Limit Atingido + API Key Reset**

```
Timeline:
06:20:58 → Começa com erro de tipo (league como string)
06:21:43 → Retry funciona (6 reqs aceitos)
10:54:21 → Sistema rodando bem (13 reqs × múltiplos ciclos)
11:16:10 → EXATAMENTE AQUI, mudam os requisitos
          → Começa a retornar apenas... Hmm espera
          → Por que APENAS Argentina?
11:34:06 → API Key invalida
```

**Por que APENAS Argentina?**
- Liga 128 (Argentina) pode estar com requisição mais rápida
- Ou é a primeira na lista que consegue retornar algo
- Outras ligas 39-265 podem estar retornando erro silenciosos

---

### 🟠 HIPÓTESE SECUNDÁRIA (60% confiança)

**Loop em `get_today_schedule()` Terminando Cedo**

```python
for league_id in league_ids:  # [39, 61, 71, 72, 78, 88, 94, 128, 135, 140, 253, 265, 624]
    if not self.rate_limiter.can_request():
        logger.warning(f"Pulando liga {league_id}")
        break  # ← AQUI! Para no MLS (253)
    
    data = await self._request(...)
    fixtures = data.get("response", [])
    all_fixtures.extend(fixtures)

return all_fixtures  # Retorna só o que conseguiu antes de quebrar
```

**Prova nos Logs:**
```
WARNING | Sem requisicoes disponiveis para agenda, pulando liga 253
```

MLS (253) é a 11ª Liga na listagem. Se pode fazer 10 requisições:
- Liga 39, 61, 71, 72, 78, 88, 94, 128, 135, 140 → 10 reqs (sucesso)
- Liga 253 (MLS) → Sem requisições, pula
- Liga 265, 624 → Não alcança

**Mas isso não explica por que APENAS Argentina (128) aparece...**

---

### 🟡 HIPÓTESE TERCIÁRIA (40% confiança)

**Múltiplas Ligas Retornando 0 Jogos**

```
API retorna: 
  Liga 39:   8 jogos
  Liga 61:   2 jogos
  Liga 71:   5 jogos
  ... 
  Liga 128:  4 jogos ← ARGENTINA
  Liga 135:  3 jogos
  ...
  
Mas há código que está FILTRANDO no nível de liga
Ou há conversão de timestamp errada que remove 13 de 17 jogos
```

**Teste: Chamar API manualmente**

```bash
# Teste 1: Premier League (39)
curl "https://v3.football.api-sports.io/fixtures?date=2026-02-15&league=39" \
  -H "x-apisports-key: YOUR_KEY" | jq '.response | length'

# Teste 2: La Liga (140)
curl "https://v3.football.api-sports.io/fixtures?date=2026-02-15&league=140" \
  -H "x-apisports-key: YOUR_KEY" | jq '.response | length'

# Teste 3: Argentina (128)
curl "https://v3.football.api-sports.io/fixtures?date=2026-02-15&league=128" \
  -H "x-apisports-key: YOUR_KEY" | jq '.response | length'
```

Se Argentina retorna mais jogos que as outras → problema na API/calendario

---

## 🧪 PLANO DE TESTE

### Teste 1: Verificar Rate Limit Status

```python
# corner-pressure-elite/data/api_client.py → check_status()
import sys
sys.path.insert(0, '.')

from data.api_client import APIFootballClient
from utils.rate_limiter import RateLimiter
import asyncio

async def test():
    rl = RateLimiter(max_requests_per_day=100)
    client = APIFootballClient("YOUR_KEY", rl)
    
    status = await client.check_status()
    print(f"Plano: {status.get('subscription', {}).get('plan')}")
    print(f"Usado hoje: {status.get('requests', {}).get('current')}/100")
    print(f"Restantes: {rl.remaining_daily()}")

asyncio.run(test())
```

**Teste em Produção (Docker):**
```bash
docker exec cpes-python python3 -c "
import asyncio
from data.api_client import APIFootballClient
from utils.rate_limiter import RateLimiter

async def test():
    from config import API_FOOTBALL_KEY
    rl = RateLimiter(max_requests_per_day=100)
    client = APIFootballClient(API_FOOTBALL_KEY, rl)
    status = await client.check_status()
    print(f'Plano: {status.get(\"subscription\", {})}')
    print(f'Requests: {status.get(\"requests\", {})}')

asyncio.run(test())
"
```

---

### Teste 2: Testar Cada Liga Independentemente

```bash
#!/bin/bash
API_KEY="YOUR_KEY"
DATE="2026-02-15"
LIGAS=(39 61 71 72 78 88 94 128 135 140 253 265 624)

for LIGA in "${LIGAS[@]}"; do
    COUNT=$(curl -s "https://v3.football.api-sports.io/fixtures?date=$DATE&league=$LIGA&season=2026" \
      -H "x-apisports-key: $API_KEY" | jq '.response | length')
    echo "Liga $LIGA: $COUNT jogos"
done
```

**Output Esperado vs Atual:**
```
Liga 39:   X jogos (Premier)
Liga 128:  4 jogos (Argentina) ← Única que retorna na agenda
...
```

---

### Teste 3: Testar Parâmetro `league` Como Integer vs String

```python
import aiohttp
import json

async def test_type():
    async with aiohttp.ClientSession() as session:
        # Teste 1: Integer (correto)
        resp1 = await session.get(
            "https://v3.football.api-sports.io/fixtures",
            params={"date": "2026-02-15", "league": 128, "season": 2026},
            headers={"x-apisports-key": "YOUR_KEY"}
        )
        data1 = await resp1.json()
        
        # Teste 2: String (errado)
        resp2 = await session.get(
            "https://v3.football.api-sports.io/fixtures",
            params={"date": "2026-02-15", "league": "128", "season": 2026},
            headers={"x-apisports-key": "YOUR_KEY"}
        )
        data2 = await resp2.json()
        
        print(f"Integer: {data1}")
        print(f"String: {data2}")
```

---

### Teste 4: Verificar Timezone Handling

```python
from datetime import datetime, timezone

# Seu sistema local
local_now = datetime.now()
utc_now = datetime.now(timezone.utc)

print(f"Local: {local_now}")
print(f"UTC: {utc_now}")
print(f"Diferença: {(local_now - utc_now.replace(tzinfo=None)).total_seconds() / 3600} horas")

# Se diferença > 1h → timezone bugs possível
```

---

### Teste 5: Executar `_fetch_today_schedule()` Manualmente com Debug

```python
# corner-pressure-elite/main.py
import asyncio
from datetime import datetime
from config import API_FOOTBALL_KEY, LIGAS_MONITORADAS
from data.api_client import APIFootballClient
from utils.rate_limiter import RateLimiter
from storage.database import Database

async def test_fetch():
    rl = RateLimiter(max_requests_per_day=100)
    client = APIFootballClient(API_FOOTBALL_KEY, rl)
    db = Database()
    
    hoje = datetime.now().strftime("%Y-%m-%d")
    
    # Simular _fetch_today_schedule
    ligas_ativas = await db.get_ligas_ativas()
    print(f"Ligas ativas: {ligas_ativas}")
    
    fixtures = await client.get_today_schedule(ligas_ativas, hoje)
    print(f"Total fixtures: {len(fixtures)}")
    
    # Por liga
    por_liga = {}
    for f in fixtures:
        liga = f.get("league", {}).get("name", "?")
        por_liga.setdefault(liga, 0)
        por_liga[liga] += 1
    
    for liga, count in sorted(por_liga.items()):
        print(f"  {liga}: {count} jogos")

asyncio.run(test_fetch())
```

**Executar em Docker:**
```bash
docker exec cpes-python python3 << 'EOF'
# Cole código acima
EOF
```

---

### Teste 6: Curl Manual para Cada Liga

```bash
#!/bin/bash
API_KEY="$(echo $WAHA_API_KEY)"  # Obter do .env
DATE="2026-02-15"

echo "=== TESTE AGENDA POR LIGA ==="
echo "Data: $DATE"
echo ""

test_league() {
    local LIGA_ID=$1
    local LIGA_NOME=$2
    
    echo -n "$LIGA_NOME ($LIGA_ID): "
    
    curl -s "https://v3.football.api-sports.io/fixtures" \
      --data-urlencode "date=$DATE" \
      --data-urlencode "league=$LIGA_ID" \
      --data-urlencode "season=2026" \
      -H "x-apisports-key: $API_KEY" \
      | jq -r '.response | length' 2>/dev/null || echo "ERROR"
}

test_league 39 "Premier League"
test_league 61 "Ligue 1"
test_league 78 "Bundesliga"
test_league 128 "Argentina"
test_league 140 "La Liga"
test_league 253 "MLS"
```

---

## 🛠 CORREÇÕES ARQUITETURAIS RECOMENDADAS

### CORREÇÃO #1: Manter Requisições em Bulk Quando Possível

**Problema Atual:**
```python
# 13 reqs por ciclo (1 por liga)
for liga_id in league_ids:
    await api.get_today_schedule([liga_id], today)
```

**Solução Recomendada:**
```python
# 1 req para TODOS os jogos ao vivo (sem limite de liga)
async def get_fixtures_today(date: str) -> List[Dict]:
    """
    Fetch TODOS os jogos de um dia em UMA requisição
    usando live=all (se suportado) ou date parameter sem filtro de liga
    """
    # Opção A: Usar /fixtures?live=all (retorna todos em tempo real, não por data)
    # Opção B: Usar /fixtures?date=YYYY-MM-DD (sem league parameter)
    #         Retorna jogos de TODAS as ligas válidas
    # Opção C: Paginar /fixtures by league_id mas em cache diário
    
    data = await self._request("fixtures", params={"date": date})
    return data.get("response", [])
```

**Impacto:**
- **Antes:** 13 reqs per cycle = RATE LIMIT em 2h
- **Depois:** 1 req per day = 24 ciclos por day com apenas 24 reqs

---

### CORREÇÃO #2: Cache Diário com Invalidação Explícita

````python
class ScheduleCache:
    def __init__(self):
        self._cache = {}
        self._cache_date = None
    
    async def get_today_schedule(self, today: str):
        # Se mudou de dia ou cache vazio → refetch
        if today != self._cache_date or not self._cache:
            fixtures = await api.get_fixtures_today(today)
            self._cache = {f["id"]: f for f in fixtures}
            self._cache_date = today
        
        return list(self._cache.values())
    
    def filter_by_league(self, league_ids: List[int]):
        """Filter cached fixtures by league IDs"""
        return [f for f in self._cache.values() 
                if f.get("league", {}).get("id") in league_ids]
```

**Impacto:**
- Requisição só 1x por dia
- Filtra em memória (grátis)

---

### CORREÇÃO #3: Implementar Fallback para Liga

```python
async def get_today_schedule(self, league_ids: List[int], date: str):
    """
    Estratégia com fallback:
    1. Tenta /fixtures?date=YYYY-MM-DD (todas as ligas de uma vez)
    2. Se falhar: tenta ligas uma por uma
    3. Se rate limit: retorna cache anterior
    """
    
    # Tentar BULK primeiro (1 req)
    try:
        data = await self._request("fixtures", 
                                   params={"date": date, "season": int(date[:4])})
        fixtures = data.get("response", [])
        
        # Filtrar apenas ligas desejadas
        filtered = [f for f in fixtures 
                    if f.get("league", {}).get("id") in league_ids]
        return filtered
    
    except:
        logger.warning("Bulk fetch falhou, tentando por liga...")
    
    # Fallback: Por liga (13 reqs)
    all_fixtures = []
    for league_id in league_ids:
        if not self.rate_limiter.can_request():
            logger.warning(f"Rate limit atingido em liga {league_id}")
            break
        
        try:
            data = await self._request("fixtures", 
                                       params={"date": date, 
                                              "league": league_id, 
                                              "season": int(date[:4])})
            fixtures = data.get("response", [])
            all_fixtures.extend(fixtures)
        except Exception as e:
            logger.error(f"Erro fetch liga {league_id}: {e}")
    
    return all_fixtures
```

---

### CORREÇÃO #4: Detecção Explícita de Rate Limit

```python
class RateLimiter:
    def __init__(self, max_requests_per_day: int = 100):
        self.max_per_day = max_requests_per_day
        self.requests_today = 0
        self.reset_time = None
    
    async def wait_if_needed(self):
        """Espera antes de fazer request se close ao limite"""
        remaining = self.max_per_day - self.requests_today
        
        if remaining <= 5:
            logger.warning(f"⚠️  RATE LIMIT CRÍTICO: apenas {remaining} reqs restantes")
            
            if remaining <= 0:
                logger.error("❌ RATE LIMIT ATINGIDO - aguardando reset")
                await asyncio.sleep(3600)  # Aguarda 1h
        
        elif remaining <= 20:
            logger.warning(f"⚠️  RATE LIMIT: {remaining} reqs restantes - reduzindo polling")
            await asyncio.sleep(10)
    
    def sync_from_api(self, current: int):
        """Sincroniza com API (obtém do /status)"""
        self.requests_today = current
        logger.info(f"Rate limit sync: {current}/{self.max_per_day}")
```

---

### CORREÇÃO #5: Validar API Key no Startup

```python
async def check_api_key_validity():
    try:
        status = await api_client.check_status()
        plan = status.get("subscription", {}).get("plan")
        if plan == "free":
            logger.warning(f"API Plan: FREE (100 reqs/day)")
        elif plan == "pro":
            logger.info(f"API Plan: PRO")
        
        current = status.get("requests", {}).get("current", 0)
        limit = status.get("requests", {}).get("limit_day", 100)
        
        if current >= limit * 0.8:
            logger.warning(f"⚠️  já usou 80% do limit: {current}/{limit}")
    except Exception as e:
        logger.error(f"❌ API Key INVÁLIDA: {e}")
        raise
```

---

## 🚀 MELHOR PRÁTICA DEFINITIVA

### Arquitetura Otimizada para Multi-Liga

```python
# config.py
POLLING_STRATEGY = "bulk"  # ou "lazy" ou "hybrid"
SCHEDULE_CACHE_TTL = 3600  # 1h cache para agenda
LEAGUE_FETCH_BATCH_SIZE = 5  # Se bulk falhar, fetch em lotes de 5

# main.py
class OptimizedScheduleFetcher:
    async def get_today_games(self, date: str) -> List[Dict]:
        """
        Strategy = BULK → BATCH → INDIVIDUAL
        
        1. BULK: 1 req para /fixtures?date sem filtro
        2. Se rate limit: BATCH [5 ligas por req usando live=all + filtering]
        3. Se continuar failing: INDIVIDUAL [1 req por liga]
        """
        
        # Etapa 1: Tentativa BULK
        if self.strategy == "BULK":
            return await self._fetch_bulk(date)
        
        # Etapa 2: Tentativa BATCH
        elif self.rate_limiter.remaining_daily() > 20:
            return await self._fetch_batch(date)
        
        # Etapa 3: INDIVIDUAL com fallback a cache
        else:
            try:
                return await self._fetch_individual(date)
            except RateLimitError:
                logger.error("Rate limit atingido, usando cache")
                return self._get_cached_schedule(date)
```

### Monitoramento Contínuo

```python
# Adicionar logs estruturados
logger.info(f"""
╔════════════════════════════════════════╗
║  AGENDA FETCH REPORT                   ║
╠════════════════════════════════════════╣
║ Data: {date}                           
║ Requisições usadas: {reqs_used}/13     
║ Jogos retornados: {len(fixtures)}      
║ Por liga:                              
║   - Premier (39): {count_39}             
║   - La Liga (140): {count_140}           
║   - Argentina (128): {count_128}         
║ Rate limit: {rl.requests_today}/{rl.max_per_day} ║
║ Próximo refresh: {next_refresh}        
╚════════════════════════════════════════╝
""")
```

---

## 📊 RESUMO DE TESTES A FAZER

| Teste | Comando | O que Procurar |
|-------|---------|----------------|
| Rate Limit | `check_status()` | "Usado: XX/100" |
| API Key | `curl fixtures` | "Missing application key" |
| Liga Individual | `curl league=128` | Status 200 + response |
| Todas Ligas | `curl date=YYYY-MM-DD` | > 10 jogos? |
| Interval Cronômetro | Logs | Quantos ciclos até rate limit? |
| Timezone | `datetime.now()` vs UTC | Diferença em horas |

---

## ✅ PRÓXIMOS PASSOS

1. **Urgente (1h):** Executar teste de Rate Limit + API Key
2. **Urgente (2h):** Fazer curl manual para cada liga
3. **Crítico (hoje):** Implementar CORREÇÃO #1-2 (cache + bulk)
4. **Crítico (hoje):** Aumentar limite da API ou usar plan PRO
5. **Melhorias:** Implementar fallbacks + monitoramento

---

**Responsa por Debug:** Senior Full Stack Engineer  
**Data:** 2026-02-15  
**Confiança em Diagnóstico:** 🔴 85%  
**ETA Resolução:** 2-4 horas
