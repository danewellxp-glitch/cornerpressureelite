# Análise Executiva — Modelo de Decisão CPES

**Componentes:** Pressure Score · Projeção Híbrida · Edge  
**Versão:** 1.0  
**Data:** Fevereiro 2025

---

## 1. Visão Geral

O **Modelo de Decisão** do Corner Pressure Elite System (CPES) é o núcleo analítico que determina quando emitir sinais de apostas no mercado de **escanteios totais** (Over). O fluxo é sequencial: **Filtros Estruturais → Pressure Score → Projeção Híbrida → Edge → Decisão**.

```
Jogo ao vivo → Filtros → Pressure Score → Projeção → Edge → Sinal (NORMAL/PREMIUM)
```

---

## 2. Fluxo de Decisão

| Etapa | Componente | Saída |
|-------|------------|-------|
| 1 | Filtros estruturais | Passou ou motivo do bloqueio |
| 2 | Pressure Score | Pontuação 0–10 |
| 3 | Projeção híbrida | Escanteios projetados até o fim |
| 4 | Edge | Projeção − Linha |
| 5 | Regras de decisão | NORMAL, PREMIUM ou nenhum sinal |

---

## 3. Pressure Score

### 3.1 Conceito

O **Pressure Score** mede a pressão ofensiva recente do jogo. Quanto maior, maior a tendência de haver mais escanteios até o final. Escala de **0 a ~10 pontos**.

### 3.2 Indicadores e Pontuação

| Indicador | Condição | Pontos | Justificativa |
|-----------|----------|--------|---------------|
| Escanteios últimos 10 min | ≥ 2 | +3 | Alta frequência recente de escanteios |
| Escanteios últimos 5 min | ≥ 1 | +1 | Escanteio recente |
| Ataques perigosos últimos 10 min | ≥ 3 | +2 | Pressão ofensiva moderada |
| Time perdendo por 1 gol | Sim | +2 | Jogo equilibrado, tendência a ataque |
| Posse de bola dominante | > 50% | +1 | Domínio ofensivo |
| Finalizações recentes | ≥ 2 | +1 | Chutes a gol aumentam probabilidade de escanteios |

### 3.3 Pontuação Máxima

Pontuação máxima teórica: **10 pontos** (todos os critérios satisfeitos).

### 3.4 Limiares para Sinal

| Tipo | Score mínimo |
|------|--------------|
| **NORMAL** | ≥ 6 |
| **PREMIUM** | ≥ 8 |

### 3.5 Entradas do Modelo (JogoAoVivo)

- `escanteios_ultimos_10min`
- `escanteios_ultimos_5min`
- `ataques_perigosos_ultimos_10min`
- `posse_ultimos_10min`
- `finalizacoes_recentes`
- `diferenca_gols` (para “time perdendo por 1”)

---

## 4. Projeção Híbrida

### 4.1 Conceito

A **Projeção Híbrida** estima o número de escanteios ao fim do tempo regulamentar (≈95 min), combinando:

1. **Ritmo base** — extrapolação do ritmo atual  
2. **Ajuste de pressão** — peso do Pressure Score  
3. **Ajuste histórico** — média da liga  

### 4.2 Fórmula

\[
\text{Projeção} = \text{Ritmo base} + \text{Ajuste pressão} + \text{Ajuste histórico}
\]

### 4.3 Componente 1: Ritmo Base

\[
\text{Ritmo base} = \frac{\text{Escanteios atuais}}{\text{Minuto atual}} \times 95
\]

- **95**: minuto típico de fim do jogo (90 + acréscimos).
- Interpretação: se o ritmo de escanteios/min for mantido até o fim, quantos escanteios teremos?

**Exemplo:** 6 escanteios no min 55  
\[
\text{Ritmo base} = \frac{6}{55} \times 95 \approx 10{,}36
\]

### 4.4 Componente 2: Ajuste de Pressão

\[
\text{Ajuste pressão} = \text{Pressure Score} \times 0{,}25
\]

- **Fator:** `AJUSTE_PRESSAO_FATOR = 0.25`
- Quanto maior o score, mais a projeção é ajustada para cima.
- Ex.: score 8 → ajuste +2,0; score 9 → ajuste +2,25.

### 4.5 Componente 3: Ajuste Histórico

\[
\text{Ajuste histórico} = 
\begin{cases}
+0{,}5 & \text{se média da liga} > 10{,}5 \\
0 & \text{senão}
\end{cases}
\]

- **Threshold:** `AJUSTE_HISTORICO_THRESHOLD = 10.5`
- **Valor:** `AJUSTE_HISTORICO_VALOR = 0.5`
- Liga mais ofensiva (média > 10,5) recebe +0,5 na projeção.

### 4.6 Exemplo Completo

| Dado | Valor |
|------|-------|
| Escanteios | 7 |
| Minuto | 60 |
| Pressure Score | 9 |
| Média da liga | 10.8 |

\[
\begin{aligned}
\text{Ritmo base} &= \frac{7}{60} \times 95 = 11{,}08 \\
\text{Ajuste pressão} &= 9 \times 0{,}25 = 2{,}25 \\
\text{Ajuste histórico} &= +0{,}5 \quad (\text{média } 10{,}8 > 10{,}5) \\
\text{Projeção} &= 11{,}08 + 2{,}25 + 0{,}5 = 13{,}83
\end{aligned}
\]

---

## 5. Edge

### 5.1 Definição

\[
\text{Edge} = \text{Projeção} - \text{Linha atual}
\]

- **Linha atual:** total de escanteios do mercado (Over/Under).
- **Edge:** vantagem estimada em relação à linha. Valores maiores indicam mais valor no Over.

### 5.2 Limiares para Sinal

| Tipo | Edge mínimo |
|------|-------------|
| **NORMAL** | ≥ 0,8 |
| **PREMIUM** | ≥ 1,5 |

### 5.3 Interpretação

| Edge | Interpretação |
|------|---------------|
| < 0 | Projeção abaixo da linha → sem sinal |
| 0 a 0,8 | Insuficiente para NORMAL |
| 0,8 a 1,5 | Sinal NORMAL (Score ≥ 6) |
| ≥ 1,5 | Sinal PREMIUM (Score ≥ 8) |

---

## 6. Regras de Decisão

### 6.1 Matriz de Decisão

| Score | Edge | Resultado |
|-------|------|-----------|
| < 6 | Qualquer | Sem sinal |
| 6–7 | < 0,8 | Sem sinal |
| 6–7 | ≥ 0,8 | **SINAL NORMAL** |
| ≥ 8 | < 1,5 | Sem sinal (ou NORMAL se edge ≥ 0,8) |
| ≥ 8 | ≥ 1,5 | **SINAL PREMIUM** |

A lógica aplicada é:

1. **PREMIUM:** Score ≥ 8 **e** Edge ≥ 1,5
2. **NORMAL:** Score ≥ 6 **e** Edge ≥ 0,8 (e não PREMIUM)  
3. Caso contrário: sem sinal.

### 6.2 Parâmetros (config.py)

```python
# Pressure Score
MIN_SCORE_NORMAL = 6
MIN_SCORE_PREMIUM = 8

# Edge
MIN_EDGE_NORMAL = 0.8
MIN_EDGE_PREMIUM = 1.5

# Projeção
PROJECAO_MINUTO_TOTAL = 95
AJUSTE_PRESSAO_FATOR = 0.25
AJUSTE_HISTORICO_THRESHOLD = 10.5
AJUSTE_HISTORICO_VALOR = 0.5
```

---

## 7. Filtros Estruturais (Pré-requisitos)

Antes de calcular Score, Projeção e Edge, o jogo precisa passar nos filtros:

| Filtro | Condição | Motivo |
|--------|----------|--------|
| Janela | min ≥ 50 | Fora da janela de análise |
| Diferença de gols | ≤ 2 | Evitar jogos muito desequilibrados |
| Escanteios totais | ≥ 3 | Volume mínimo de dados |
| Escanteios últimos 5 min | ≥ 1 | Ao menos 1 escanteio recente |
| Jogo morno | Não (0x0 após 60 com < 7 esc) | Baixa dinâmica de escanteios |
| Jogo morto | Não (time com 0 esc no 1º tempo) | Time sem participação em escanteios |

---

## 8. Diagrama do Modelo

```
                    ┌─────────────────────────────┐
                    │     Jogo ao vivo            │
                    │  (JogoAoVivo)               │
                    └──────────────┬──────────────┘
                                   │
                                   ▼
                    ┌─────────────────────────────┐
                    │   Filtros Estruturais       │
                    │   (6 condições)             │
                    └──────────────┬──────────────┘
                                   │ passou
                                   ▼
                    ┌─────────────────────────────┐
                    │   Pressure Score (0–10)     │
                    │   • Escanteios 10/5 min     │
                    │   • Ataques perigosos       │
                    │   • Time perdendo 1         │
                    │   • Posse, finalizações     │
                    └──────────────┬──────────────┘
                                   │ score ≥ 6
                                   ▼
                    ┌─────────────────────────────┐
                    │   Projeção Híbrida          │
                    │   Ritmo + Pressão + Hist.   │
                    └──────────────┬──────────────┘
                                   │
                                   ▼
                    ┌─────────────────────────────┐
                    │   Edge = Proj − Linha       │
                    └──────────────┬──────────────┘
                                   │
                                   ▼
                    ┌─────────────────────────────┐
                    │   Decisão                   │
                    │   PREMIUM: S≥8 e E≥1.5      │
                    │   NORMAL:  S≥6 e E≥0.8      │
                    └─────────────────────────────┘
```

---

## 9. Síntese Executiva

| Componente | Função |
|------------|--------|
| **Pressure Score** | Quantifica a pressão ofensiva recente (0–10), com foco em escanteios e ataques. |
| **Projeção Híbrida** | Estima escanteios ao fim do jogo com ritmo atual + pressão + perfil da liga. |
| **Edge** | Mede a vantagem do Over em relação à linha do mercado. |

O modelo emite sinal quando há **pressão moderada a alta** (Score ≥ 6) e **Edge positivo** (≥ 0,8 ou ≥ 1,5), capturando mais oportunidades sem exigir condições extremas.

---

*Documento gerado com base no código-fonte do CPES (score_engine.py, projection_engine.py, decision_engine.py).*
