# 🎯 Cálculo Detalhado de Requisições por Jogo

**Limite diário:** 7.500 requisições/dia
**Intervalo polling na janela:** 60 seg (1 min)

---

## 📊 Requisições Mínimas e Máximas por Jogo

### Estrutura de Requisições por Ciclo (60 seg)
```
1️⃣ get_live_fixtures()     : 1 req (COMPARTILHADO entre todos os jogos)
2️⃣ get_statistics()        : 1 req (POR JOGO que faz polling)
3️⃣ get_live_odds()  [Sprint 1]: 1 req (POR JOGO que faz polling)
4️⃣ get_fixture_result()    : 1 req (POR JOGO ao final - Sprint 2)
```

---

## 🎮 Exemplos Práticos

### Cenário A: Jogo entra na janela em min **80** (10 min restantes)

```
Min entrada  : 80
Min saída    : 90
Tempo restante: 10 min

Ciclos polling: 10 min ÷ 1 min = 10 ciclos
Análises: 10 (should_poll = True a cada ciclo)

Breakdow:
  10 ciclos × 1 stats         = 10 reqs
  10 ciclos × 1 odds          = 10 reqs
  1 verificação resultado     = 1 req
  ─────────────────────────────
  TOTAL: 21 reqs

Pool compartilhado (fixtures): ~1-2 reqs (dividido com outros jogos)
```

**➡️ Mínimo por jogo: ~20 reqs**

---

### Cenário B: Jogo entra na janela em min **50** (40 min até 90)

```
Min entrada  : 50
Min saída    : 90
Tempo restante: 40 min

Ciclos polling: 40 min ÷ 1 min = 40 ciclos
Análises: ~40 (should_poll = True a cada ciclo)

Breakdown:
  40 ciclos × 1 stats         = 40 reqs
  40 ciclos × 1 odds          = 40 reqs
  1 verificação resultado     = 1 req
  ─────────────────────────────
  TOTAL: 81 reqs

Pool compartilhado (fixtures): ~2-3 reqs (dividido com outros jogos)
```

**➡️ Máximo por jogo: ~80 reqs**

---

### Cenário C: Jogo entra na janela em min **65** (25 min restantes) ← Exemplo do usuário

```
Min entrada  : 65
Min saída    : 90
Tempo restante: 25 min

Ciclos polling: 25 min ÷ 1 min = 25 ciclos
Análises: ~25

Breakdown:
  25 ciclos × 1 stats         = 25 reqs
  25 ciclos × 1 odds          = 25 reqs
  1 verificação resultado     = 1 req
  ─────────────────────────────
  TOTAL: 51 reqs

Pool compartilhado: ~1-2 reqs
```

**➡️ Típico por jogo: ~50 reqs**

---

## 📈 Quantos Jogos por Dia?

### Distribuição Realista de Entrada na Janela

Considerando que diferentes ligas têm jogos em diferentes horários:

```
Entrada       | Tempo restante | Min reqs | Máx reqs | Jogos/dia
─────────────────────────────────────────────────────────────────
Min 50-60     |  30-40 min     |   40     |   81     |  2-3
Min 60-70     |  20-30 min     |   30     |   60     |  2-3
Min 70-80     |  10-20 min     |   20     |   40     |  2-3
Min 80-90     |   0-10 min     |   10     |   20     |  1-2
─────────────────────────────────────────────────────────────────
TOTAL DIA     |                |          |          |  8-12 jogos
```

---

## 💰 Cálculo Total de Requisições/Dia

### Caso 1: 8 Jogos (Dia Normal)

```
Cenário: Múltiplos jogos entram em momentos diferentes

Componentes fixos:
  Ciclos polling (60 seg cada):      ~80-100 ciclos
  get_live_fixtures compartilhado:   ~100 reqs (1 por ciclo)
  
Componentes variáveis (8 jogos):
  Média de 25 min por jogo na janela
  25 ciclos × 2 reqs (stats + odds) = 50 reqs por jogo
  8 jogos × 50 = 400 reqs
  
Resultados:
  Verificação de 6-8 jogos = 6-8 reqs

TOTAL: 100 + 400 + 7 = 507 reqs/dia
```

✅ **Margem: 7.500 - 507 = 6.993 reqs disponíveis**

---

### Caso 2: 12 Jogos (Fim de Semana/Pico)

```
Cenário: Muitos clássicos, alto fluxo

Ciclos polling:            ~120 ciclos
get_live_fixtures:         ~120 reqs

Media por jogo: 30 min     = 60 reqs/jogo
12 jogos × 60 = 720 reqs

Resultados: 10-12 reqs

TOTAL: 120 + 720 + 12 = 852 reqs/dia
```

✅ **Margem: 7.500 - 852 = 6.648 reqs disponíveis**

---

### Caso 3: Dia Super Pico (15 Clássicos)

```
Ciclos polling:            ~180
get_live_fixtures:         ~180 reqs

Média: 35 min por jogo     = 70 reqs/jogo
15 jogos × 70 = 1.050 reqs

Resultados: 15 reqs

TOTAL: 180 + 1.050 + 15 = 1.245 reqs/dia
```

✅ **Margem: 7.500 - 1.245 = 6.255 reqs disponíveis**

---

## 📋 Resumo Executivo

| Métrica | Valor |
|---------|-------|
| **Reqs/jogo mínimo** | 20 reqs (10 min na janela) |
| **Reqs/jogo máximo** | 80 reqs (40 min na janela) |
| **Reqs/jogo típico** | 50 reqs (25-30 min na janela) |
| **Jogos/dia normal** | 8-10 jogos |
| **Jogos/dia pico** | 12-15 jogos |
| **Reqs/dia normal** | 500-700 reqs |
| **Reqs/dia pico** | 800-1.200 reqs |
| **% do limite usado** | 6-16% |
| **Cobertura** | **100% das partidas** ✅ |

---

## 🎯 Quantos Jogos Consigo Cobrir com 7.500/dia?

### Fórmula Simplificada

```
Jogos = 7.500 reqs ÷ reqs_médio_por_jogo
Jogos = 7.500 ÷ 50 = 150 jogos por dia
```

### Na Prática

| Cenário | Jogos | Reqs/dia | Margem |
|---------|-------|----------|--------|
| Normal (8-10) | 10 | 600 | **6.900** ✅ |
| Pico (12-15) | 15 | 1.000 | **6.500** ✅ |
| Super-pico (20+) | 20 | 1.350 | **6.150** ✅ |
| **Teórico máximo** | **150** | **7.500** | **0** |

---

## 💡 Exemplos do Usuário

> *"Se entrou já com 10 min de jogo"* (min 80-85)

```
10 min restantes = 10 ciclos
10 × 2 (stats + odds) + 1 (resultado) = 21 reqs
```

> *"Quantas partidas no total por dia?"*

**Responsável:** ~10-15 partidas com **100% de cobertura completa** (stats + odds ao vivo + resultado automático)

**Teórico:** até 150 partidas se usar SOMENTE polling sem análise profunda

---

## ✅ Conclusão

Com **7.500 reqs/dia**:
- ✅ Cobrir **10-15 jogos completos** (uso real: 600-1.200 reqs/dia)
- ✅ Cada jogo: **20 to 80 reqs** dependendo de quando entra na janela
- ✅ **Margem de 6.300+ reqs/dia** para expansões futuras
- ✅ Adicionar mais 5-10 ligas sem problema

**Status: 🟢 Muito confortável | Sem pressão de requisições**

---

**Última atualização:** 15/02/2026 | Com Sprints 1 & 2 ativas
