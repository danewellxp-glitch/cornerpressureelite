# 📊 Análise de Cobertura — Requisições API-Football

**Limite diário:** 7.500 requisições
**Ligas monitoradas:** 7 (PL, Bundesliga, Brasileirão A, Brasileirão B, Carioca, Arg, Chile)

---

## 🔢 Consumo por Operação (com Sprints 1 & 2)

### Estágio 1: Inicialização (1x por dia)
```
Buscar agenda do dia: 1 req/liga × 7 ligas = 7 reqs
Total: 7 reqs
```

### Estágio 2: Ciclo de Polling
```
Buscar jogos ao vivo (multi-liga): 1 req
Total por ciclo: 1 req
```

### Estágio 3: Por Jogo Analisado (na janela/pré-janela)
```
get_statistics():        1 req
get_live_odds() [Sprint 1]:  1 req
─────────────────────────────
Total por jogo:          2 reqs
```

### Estágio 4: Por Verificação de Resultado [Sprint 2]
```
get_fixture_result():    1 req (inclui fixture + eventos)
─────────────────────────────
Total por jogo:          1 req
```

---

## 📈 Cenários Realistas

### Cenário 1: Dia Típico de Liga

**Suposições:**
- 8-10 jogos ao vivo por dia (múltiplas ligas, spread de horários)
- 40-50% entram na janela (50-90 min): **4-5 jogos**
- Polling adaptativo: médio de **2 ciclos por jogo na janela**
- 60% dos jogos finalizados requerem verificação

**Cálculo:**

| Operação | Quantidade | Reqs/un | Total |
|----------|-----------|---------|-------|
| Agenda (1x) | 1 | 7 | 7 |
| Ciclos polling | 30 | 1 | 30 |
| Jogos pré-janela (0-50 min) | 4 | 2 × 2 ciclos | 16 |
| Jogos na janela (50-90 min) | 5 | 2 × 3 ciclos | 30 |
| Jogos reta final (90+ min) | 3 | 2 × 1 ciclo | 6 |
| **Verificação resultados** | 5 | 1 | 5 |
| | | **SUBTOTAL** | **94 reqs** |
| | | **MARGEM** | 6.400+ restantes |

✅ **Total com margem confortável: ~600 reqs/dia | 7 dias x 75 reqs por dia max**

---

### Cenário 2: Dia de Clássicos (Pior Caso)

**Suposições:**
- 15-18 jogos ao vivo (fim de semana com mata-matas)
- 50-60% na janela: **8-10 jogos**
- Polling mais frequente (1 min na janela): **4-5 ciclos por jogo**

| Operação | Quantidade | Reqs/un | Total |
|----------|-----------|---------|-------|
| Agenda | 1 | 7 | 7 |
| Ciclos polling | 50 | 1 | 50 |
| Jogos pré-janela | 6 | 2 × 2 | 24 |
| Jogos na janela | 8 | 2 × 5 | 80 |
| Jogos reta final | 4 | 2 × 2 | 16 |
| Verificação resultados | 8 | 1 | 8 |
| | | **SUBTOTAL** | **185 reqs** |
| | | **MARGEM** | 7.315+ |

✅ **Mesmo em pior caso: ~260 reqs/dia max**

---

### Cenário 3: Fim de Semana Completo

**7 dias × (3 dias normais + 2 dias picos + 2 dias offline)**

| Dia | Tipo | Reqs |
|-----|------|------|
| Seg | Normal | 100 |
| Ter | Normal | 100 |
| Qua | Normal | 100 |
| Qui | Normal | 100 |
| Sex | Normal | 100 |
| Sab | Pico | 250 |
| Dom | Pico | 250 |
| **TOTAL** | | **~1.000 reqs/semana** |

✅ **7.500 reqs ÷ 1.000/semana = 7-8 semanas de operação contínua**

---

## 🎯 Quantos Jogos Consigo Cobrir?

### Diariamente
| Métrica | Quantidade |
|---------|-----------|
| Jogos ao vivo | 8-15 |
| Na janela (50-90 min) | **4-8** ✅ |
| Com análise completa | **100%** |
| Com odds ao vivo | **100%** (Sprint 1) |
| Com resultado auto | **100%** (Sprint 2) |

### Semanalmente
| Métrica | Quantidade |
|---------|-----------|
| Jogos monitorados | **40-60 jogos** |
| Sinais emitidos (est.) | **15-25 sinais** |
| Resultados verificados | **100%** |

### Mensalmente
| Métrica | Quantidade |
|---------|-----------|
| Jogos monitorados | **150-200 jogos** |
| Com cobertura **100% completa** (stats + odds + resultado) | **150-200** ✅ |

---

## 💡 Otimizações (Se Necessário)

### 1️⃣ Reduzir Ligas
```
7 ligas → 5 ligas (remover Carioca + Série B)
Impacto: -100 reqs/semana
Novo limite: 8-9 semanas contínuas
```

### 2️⃣ Verificar Resultados Menos Frequentemente
```
Hoje: verificar resultados a cada ciclo
Otimizado: verificar 1x após jogo terminar + 1x no dia seguinte
Impacto: -50% das reqs de verificação
```

### 3️⃣ Desabilitar Odds para Ligas Menores
```
Odds apenas para Big 5 (PL, Bundesliga, LaLiga)
Impacto: -200 reqs/semana (menos 1 liga × 30 ciclos/dia)
```

### 4️⃣ Polling Menos Frequente na Pré-Janela
```
0-50 min: 5 min em vez de 3 min
Impacto: -30% das reqs de pré-janela
```

---

## 📋 Conclusão

| Pergunta | Resposta |
|----------|----------|
| **Quantos jogos/dia?** | 4-8 jogos na janela (100% cobertos) |
| **Requisições/dia?** | 100-200 reqs (1.3-2.6% do limite) |
| **Cobertura contínua?** | **8-25 semanas sem restrições** ✅ |
| **Antes de otimizar?** | Nenhuma urgência — margens confortáveis |
| **Pior caso?** | Mesmo com 15 clássicos/dia = ~250 reqs |

### 🟢 Status: **VERDE**
Seu limite de 7.500 reqs é mais que suficiente para cobrir todas as ligas com *análise completa* (stats + odds ao vivo + resultado automático).

---

## 📝 Recomendações

1. ✅ **Manter as 7 ligas** — nenhuma pressão de requisições
2. ✅ **Ativar Sprint 3 (Backtest)** — usa extras quando ocioso
3. ⏭️ **Próximo passo**: Adicionar mais ligas conforme crescimento
   - La Liga (Espanha) — +30 reqs/semana
   - Serie A (Itália) — +30 reqs/semana
   - **Total com + 2 ligas: ~1.150 reqs/semana ainda confortável**

---

**Última atualização:** 15/02/2026 | Sprints 1 & 2 ativas
