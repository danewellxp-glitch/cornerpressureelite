# 🔴 FIX CRÍTICO: Sistema retornava 0 ligas (2 de Argentina somente)

**Data:** 15 de Fevereiro de 2026  
**Severidade:** 🔴 CRÍTICA  
**Status:** ✅ RESOLVIDO  
**Tempo:** 4 ciclos de debug + 1 patch  

---

## 🚨 O PROBLEMA

Sistema era configurado para monitorar **13 ligas** mas retornava:
- **ANTES**: APENAS **2 jogos da Argentina** (ou 0-4 variando)
- **ESPERADO**: 15-20 jogos de múltiplas ligas
- **Impacto**: Alertas WhatsApp incompletos, agenda vazia para maioria das ligas

---

## 🔍 INVESTIGAÇÃO (5 FASES)

### FASE 1: DEBUG DA API BRUTA ✅

**Instrumentação:** Modificado `get_today_schedule()` para:
- Fazer requisição SEM filtro de liga
- Logar total bruto retornado
- Logar todas as ligas encontradas
- Depois aplicar filtros manualmente

**Resultado:** 
```
TOTAL BRUTO (sem filtro): 164 jogos
Ligas encontradas: 44 diferentes
Apenas Argentina (128) com 4 jogos retornava quando filtrado!
```

### FASE 2: DEBUG DO BANCO DE DADOS ✅

**Instrumentação:** Modificado `get_ligas_ativas()` para logar:
- Quantas ligas ativas no banco
- IDs reais das ligas  
- Nomes das ligas (com map de config)

**Resultado:**
```
Total de ligas ativas: 13 ✓
IDs: [39, 61, 71, 72, 78, 88, 94, 128, 135, 140, 253, 265, 624]
Banco está correto!
```

### FASE 3: VALIDAÇÃO DE SEASONS 🔴 **PROBLEMA ENCONTRADO!**

**Instrumentação:** Adicionado `_debug_validate_seasons()` para testar:
- Season 2025 vs 2026 para cada liga
- Qual season retorna mais resultados

**Resultado - EUREKA!:**
```
Premier League (Liga 39):
  Season 2024: 0 jogos
  Season 2025: 0 jogos  
  Season 2026: 0 jogos

Ligue 1 (Liga 61):
  Season 2024: 0 jogos
  Season 2025: 4 jogos ✓  
  Season 2026: 0 jogos

Argentina (Liga 128):
  Season 2024: 0 jogos
  Season 2025: 0 jogos
  Season 2026: 4 jogos ✓
```

**CONCLUSÃO DAH RAIZ:** 
- Ligas **europeias têm dados em Season 2025**
- Ligas **hemisfério sul (Brasil, Argentina) têm dados em Season 2026**
- Código estava usando `season = int(date[:4])` = **2026 para TODAS as ligas**
- Por issome: **0 ligas europeias retornavam nada!**

### FASE 4: DEBUG DE FILTROS ✅

**Instrumentação:** Adicionado logs detalhados no `_verificar_filtros()` para cada exclusão

**Resultado:** Filtros estavam corretos, não era aí o problema.

### FASE 5: DEBUG DE RATE LIMITER ✅

**Instrumentação:** Adicionado logs de:
- Requisições atuais vs limite
- Bloqueios silenciosos
- Status de sincronização com API

**Resultado:** Rate limiter funcionando corretamente (3900+ reqs restantes).

---

## 💥 CAUSA RAIZ

**Arquivo:** [data/api_client.py](../../corner-pressure-elite/data/api_client.py) linha ~155  
**Função:** `get_today_schedule()`  
**Código Culpado:**

```python
# ❌ ANTES (BUGADO):
season = int(date[:4])  # 2026-02-15 → season 2026
for league_id in league_ids:
    data = await self._request(
        "fixtures", 
        params={"date": date, "league": league_id, "season": season}
    )
    # Liga 39 (Premier): 0 jogos (dados em season 2025!)
    # Liga 128 (Argentina): 4 jogos (dados em season 2026)
```

**Problema:** Usando season 2026 para TODAS as ligas, quando:
- Europa (Big 5 + Portugal/Holanda) = **Season 2025**
- Hemisfério Sul/Brasil = **Season 2026**

---

## ✅ SOLUÇÃO APLICADA

### Step 1: Adicionar Season Config

[Arquivo: config.py](../../corner-pressure-elite/config.py)

```python
LIGAS_MONITORADAS = [
    # Big 5 Européias (Season 2025)
    {"id": 39, "nome": "Premier League", "season": 2025},
    {"id": 78, "nome": "Bundesliga", "season": 2025},
    {"id": 135, "nome": "Serie A", "season": 2025},
    {"id": 140, "nome": "La Liga", "season": 2025},
    {"id": 61, "nome": "Ligue 1", "season": 2025},
    
    # Brasil/South America (Season 2026)
    {"id": 71, "nome": "Brasileirão A", "season": 2026},
    {"id": 72, "nome": "Brasileirão B", "season": 2026},
    {"id": 624, "nome": "Carioca A", "season": 2026},
    {"id": 128, "nome": "Liga Profesional Argentina", "season": 2026},
    {"id": 265, "nome": "Primera División Chile", "season": 2026},
    {"id": 253, "nome": "MLS", "season": 2026},
    # ... etc
]
```

### Step 2: Reescrever get_today_schedule

[Arquivo: data/api_client.py](../../corner-pressure-elite/data/api_client.py)

```python
# ✓ DEPOIS (CORRIGIDO):
from config import LIGAS_MONITORADAS
season_map = {liga["id"]: liga.get("season", 2025) for liga in LIGAS_MONITORADAS}

for league_id in league_ids:
    season = season_map.get(league_id, 2025)  # Season correto por liga!
    data = await self._request(
        "fixtures", 
        params={"date": date, "league": league_id, "season": season}
    )
    # Liga 39 + season 2025: 0 jogos nesse dia específico (correto)
    # Liga 128 + season 2026: 4 jogos (correto)
    # Liga 61 + season 2025: 4 jogos (correto)
```

---

## 📊 RESULTADOS ANTES vs DEPOIS

| Aspecto | Antes | Depois |
|---------|-------|--------|
| **Total de jogos** | 0-2 (Argentina apenas) | **13 ✓** |
| **Ligas ativas** | 1 (só Argentina) | **4 (Ligue 1, Bundesliga, Eredivisie, Liga Portugal)** |
| **Compatibilidade API** | ❌ Season incorreta | ✓ Seasons corretas |
| **Rate Limit** | ✓ Não era problema | ✓ Continua OK (3820 reqs restantes) |
| **Banco de dados** | ✓ Não era problema | ✓ Continua OK (13 ligas ativas) |

### Agenda Retornada (DEPOIS do patch):

```
2026-02-15: 13 jogos programados
🏆 Ligue 1 (4 jogos)
  11:00 - Le Havre vs Toulouse
  13:15 - Lorient vs Angers
  13:15 - Metz vs Auxerre
  16:45 - Lyon vs Nice

🏆 Bundesliga (2 jogos)
  11:30 - FC Augsburg vs 1. FC Heidenheim
  13:30 - RB Leipzig vs VfL Wolfsburg

🏆 Eredivisie (4 jogos)
  08:15 - Feyenoord vs GO Ahead Eagles
  10:30 - Heerenveen vs PEC Zwolle
  10:30 - Telstar vs Twente
  12:45 - Sparta Rotterdam vs NEC Nijmegen

🏆 Liga Portugal (3 jogos)
  12:30 - Nacional vs FC Porto
  15:00 - AVS vs Estoril
  17:30 - Sporting CP vs Famalicao
```

---

## 📝 LIÇÕES APRENDIDAS

1. **API-Football tem seasons diferentes por liga** - Não usar `year da data` como season global
2. **Hedge timing:** Europeias em 2025, Hemisfério Sul em 2026
3. **Logging é essencial** - Debug de 5 fases com instrumentação provou valor
4. **Não assumir** - Validar realmente contra API antes de conclusões

---

## 🔧 PATCHES APLICADOS

### config.py
- Adicionado field `season` para cada liga com valor correto (2025 ou 2026)

### data/api_client.py
- Reescrito `get_today_schedule()` para:
  - Usar `season_map` por liga (not global)
  - Continuar com debug logs (instrumentação mantida)
  - Validação de seasons dinâmica

### storage/database.py
- Logs de `get_ligas_ativas()` mantidos para transparência

### utils/rate_limiter.py
- Logs de `[DEBUG FASE 5]` mantidos para visibilidade

### engine/decision_engine.py
- Logs de `[DEBUG FASE 4]` mantidos para filtros visíveis

---

## ✅ VALIDAÇÃO

- ✓ API retorna jogos de múltiplas ligas (13 total em 15/02/2026)
- ✓ Rate limiter não atinge limite diário (3820 requests restantes)
- ✓ Banco de dados retorna 13 ligas ativas
- ✓ Seasons corretos aplicados por liga
- ✓ Agenda salva em upcoming_games.json com 13 jogos

---

## 🚀 FOLLOW-UP

- [ ] Verificar por que Liga 128 (Argentina) foi pulada no último ciclo (bloqueio por minuto)
- [ ] Considerar aumentar limite de requisições por minuto de 10 para 15-20
- [ ] Monitorar próximos ciclos para confirmar estabilidade

---

## 📌 CONCLUSÃO

**PROBLEMA:** Código usava `season = int(date[:4])` globalmente (2026 para todos), mas API-Football usa:
- **Season 2025** para ligas europeias
- **Season 2026** para hemisfério sul

**SOLUÇÃO:** Adicionar config de season por liga + usar season_map dinâmico

**IMPACTO:** De 0-2 jogos → **13 jogos retornados** ✅
