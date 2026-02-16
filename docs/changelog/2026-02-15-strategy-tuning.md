# Changelog — Ajuste de Estratégia CPES

**Data:** 15/02/2026
**Objetivo:** Diminuir a régua dos indicadores e limiares de decisão para capturar mais oportunidades de sinal, sem exigir que o jogo esteja em condições extremas.

---

## Problema

Os parâmetros anteriores eram muito conservadores — o sistema só emitia sinal quando o jogo estava "pegando fogo" (pressão máxima, edge altíssimo). Isso resultava em pouquíssimos sinais durante rodadas completas.

---

## Arquivos Alterados

| Arquivo | O que mudou |
|---------|-------------|
| `corner-pressure-elite/engine/score_engine.py` | Thresholds dos indicadores do Pressure Score |
| `corner-pressure-elite/config.py` | Limiares de Score, Edge e filtro de escanteios mínimos |
| `ANALISE_MODELO_DECISAO.md` | Documentação atualizada para refletir os novos valores |

---

## 1. Indicadores do Pressure Score (`score_engine.py`)

| Indicador | Antes | Depois | Pontos |
|-----------|-------|--------|--------|
| Ataques perigosos (últimos 10 min) | >= 6 | **>= 3** | +2 |
| Posse de bola dominante | > 60% | **> 50%** | +1 |
| Finalizações recentes | >= 3 | **>= 2** | +1 |

**Indicadores mantidos (sem alteração):**

| Indicador | Condição | Pontos |
|-----------|----------|--------|
| Escanteios últimos 10 min | >= 2 | +3 |
| Escanteio últimos 5 min | >= 1 | +1 |
| Time perdendo por 1 gol | Sim | +2 |

**Impacto:** O score acumula pontos com mais facilidade. Antes, era necessário 6 ataques perigosos em 10 minutos (ritmo muito alto); agora, 3 já pontua. Posse de 51% já conta como domínio, e 2 finalizações já contribuem.

---

## 2. Limiares de Decisão (`config.py`)

### Score mínimo para sinal

| Tipo de sinal | Antes | Depois |
|---------------|-------|--------|
| NORMAL | >= 8 | **>= 6** |
| PREMIUM | >= 9 | **>= 8** |

### Edge mínimo para sinal

| Tipo de sinal | Antes | Depois |
|---------------|-------|--------|
| NORMAL | >= 1.3 | **>= 0.8** |
| PREMIUM | >= 2.0 | **>= 1.5** |

### Filtro estrutural

| Filtro | Antes | Depois |
|--------|-------|--------|
| Escanteios totais mínimos | >= 5 | **>= 3** |

---

## 3. Matriz de Decisão Atualizada

| Score | Edge | Resultado |
|-------|------|-----------|
| < 6 | Qualquer | Sem sinal |
| 6–7 | < 0.8 | Sem sinal |
| 6–7 | >= 0.8 | **SINAL NORMAL** |
| >= 8 | < 1.5 | NORMAL (se edge >= 0.8) |
| >= 8 | >= 1.5 | **SINAL PREMIUM** |

---

## 4. Exemplo Prático

### Cenário: Jogo moderado no minuto 60

| Dado | Valor |
|------|-------|
| Escanteios últimos 10 min | 2 |
| Escanteio últimos 5 min | 1 |
| Ataques perigosos (10 min) | 4 |
| Posse de bola | 55% |
| Finalizações recentes | 2 |
| Time perdendo por 1 | Não |

**Score:** +3 (esc 10min) + 1 (esc 5min) + 2 (ataques >= 3) + 1 (posse > 50%) + 1 (finalizações >= 2) = **8 pontos**

- **Antes:** Score 8 >= 8 → passava, mas ataques perigosos = 4 < 6 → NÃO pontuava os +2 → score real seria **5** → sem sinal
- **Agora:** Score **8** com edge favorável → **SINAL PREMIUM** possível

---

## 5. Parâmetros que NÃO mudaram

| Parâmetro | Valor | Motivo |
|-----------|-------|--------|
| Janela de monitoramento | 50–90 min | Faixa adequada para análise |
| Max diferença de gols | 2 | Evitar jogos muito desequilibrados |
| Min escanteios 5 min | 1 | Atividade recente necessária |
| Jogo morno (0x0 após 60) | < 7 escanteios | Filtro de segurança válido |
| Projeção minuto total | 95 | Cálculo de projeção correto |
| Ajuste pressão fator | 0.25 | Peso adequado |
| Ajuste histórico threshold | 10.5 | Liga ofensiva |
| Reavaliação intervalo | 3 min | Evitar spam de alertas |
