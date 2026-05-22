# Sinais Valor — Visão Mestre

> **Status:** documentado, **ON HOLD** (aguarda fundação — ver pré-requisitos).
> **Data:** 2026-05-22. **Fonte das decisões:** Daniel.
> **Cross-docs:** resumo de fase no `docs/ROADMAP.md` (seção H_VALOR), regras no
> `CLAUDE.md` §14, ADR em `docs/DECISIONS.md` (2026-05-22 Sinais Valor).

> **Notas de editor (consistência com o repo):**
> - O documento original citava "Migration 0017" para as tabelas novas. **`0017_manual_bets.sql`
>   já existe** — a migration de H_VALOR.1 será renumerada (próximo número livre) quando
>   implementada. Os nomes de tabela abaixo seguem válidos.
> - O original pedia "§15" no CLAUDE.md; a última seção é §13, então entrou como **§14**
>   (sem buraco de numeração).
> - **Nada foi implementado.** Este doc é registro de intenção. A próxima ação de
>   engenharia continua sendo a Fase H A2 (cutover `sofa_event_id`), não H_VALOR.

---

## 1. Contexto e objetivo

### O que é "Sinais Valor"

Nova categoria de sinais do CPES focada em **apostas de alto valor estatístico**
(edge matemático sustentável) em **múltiplos mercados além de escanteios/cartões**.
Usa o dataset acumulado + modelos ML/quant (LightGBM) pra identificar **brechas
reais** nas linhas oferecidas pela Betano.

### Diferença vs sinais atuais

| Aspecto | Sinais Atuais (corners/cards) | Sinais Valor (NOVO) |
|---------|-------------------------------|---------------------|
| Mercados | Corners + Cards | Multi-mercado (1X2, BTTS, Over/Under, AH, etc) |
| Frequência | Múltiplos/dia | Raros (1-5/semana) |
| Odd típica | 1.50-2.50 | 1.40-1.70 ("linhas maduras") |
| Análise | Determinística (regras) | ML/quant (LightGBM + validação) |
| Base | Stats live | Histórico + Contexto + Live (3 pilares) |
| Stake recomendada | 1u por sinal | 20-50% banca (decisão Daniel) |
| Tier comercial | Pro/Max | Quant Pro R$199,90 (proposta) |

### Por que documentar agora e esperar implementar

**Documentar agora:** fundação técnica já existe (E.1 + F + G + K.1); dataset
crescendo (~21k rows); bridge captura 260+ mercados Betano/jogo; SofaScore
enrichment cobre stats avançados (xG, posse, etc).

**Esperar pra implementar modelos:** dataset precisa amadurecer (mín. 4-6 meses);
Fase H A3 deve completar primeiro (`sofa_event_id` chave única); V2 Dashboard
estável; modelos ML exigem fundação determinística sólida.

**Decisão estratégica:** começar **captura de dados** quando fizer sentido (pós-A3),
implementação de **modelos** depois do dataset maduro.

---

## 2. Visão estratégica

### Lógica de negócio (palavras do Daniel)

> "Antes do jogo começar o sistema sabe que time A vs time B vão jogar pela
> Libertadores, ele pega os stats dos últimos 10 jogos daquele time NA COMPETIÇÃO
> ESPECÍFICA."

> "Se o jogo é na quarta e o time jogou Brasileirão no domingo, analisar esse jogo
> de domingo pra ver se jogou com titulares ou reserva, analisar as formações
> táticas."

> "Se for Brasileirão por exemplo, ver os jogos atrás se teve Libertadores ou ver o
> próximo jogo desse time pra ver se não é Libertadores/Sudamericana — ligas mais
> fortes ou prioridade do time."

> "Stats é só um pilar de peso. Outros pesos: pressão de jogo, se time precisa ganhar
> pra se classificar, sair da zona de rebaixamento, entrar no G4. Durante o jogo:
> cartões, chutes no gol, faltas, posse de bola."

> "Histórico bom > stats bom > jogo ao vivo a favor de alguma odd boa = enviar sinal."

### Conceito de "Alavancagem" (terminologia interna)

Daniel define como: *"Apostar a banca toda ou quase toda em odds confiáveis e ir
usando o valor que ganhou em outras odds boas que o sistema vai lançar."*

- **Stake aprovada:** 20-50% da banca por sinal (decisão consciente — alto risco assumido).
- **Premissa:** odds 1.40-1.70 são "linhas maduras", estatisticamente mais previsíveis.
  Sistema só emite quando confiança é alta.

### Terminologia recomendada (interno vs cliente)

| Termo interno | Termo comercial |
|---|---|
| Sinais Valor | Sinais Premium |
| Edge matemático | Alta confiança |
| Stake recomendada | Sugestão de aposta |
| Modelo quant | Análise inteligente |

> **EVITAR "Alavancagem" pro cliente** — associação negativa no Brasil (telegram
> traders, golpes).

---

## 3. Arquitetura multi-pilar

```
PILAR 1: HISTÓRICO (peso 40%)
  - Últimos 10 jogos NA COMPETIÇÃO ESPECÍFICA · Casa vs Fora · H2H direto
  - Formação tática histórica vs atual · Rotação de elenco esperada
        ↓
PILAR 2: CONTEXTO (peso 30%)
  - Motivação (rebaixamento/G4/decisão) · Stage do torneio · Tempo de descanso
  - Próximo jogo importante (poupar elenco?) · Lesões/suspensões · Clássico/rivalidade
        ↓
PILAR 3: LIVE (peso 30%, gatilho)
  - Pressão acumulada · Stats em tempo real (Betano + SofaScore) · Momentum · Subs
        ↓
  SE TODOS PILARES > THRESHOLD → CALCULAR EDGE
        ↓
  SE EDGE > MÍNIMO + ODD 1.40-1.70 → EMITIR SINAL
```

### Pilar 1 — Histórico (peso 40%)

Features-chave: forma **por competição específica** (`wins_pct_in_competition`,
`goals_for/against_avg`, `over_2_5_pct`, `btts_pct`), casa vs fora
(`home/away_form_last_5`), H2H (`h2h_last_5_results`, `h2h_goals_avg`), tática
(`formation_modal_last_10`, `formation_current`, `tactical_consistency`), rotação
(`last_lineup_titulares_pct`, `rotation_expected_pct`).

**Captura (zero scraping, ~95% via API SofaScore):**
- SofaScore `/unique-tournament/{tid}/season/{sid}/standings` (já temos)
- SofaScore `/team/{id}/events/last/{n}` (filtra por competição localmente)
- SofaScore `/event/{id}/lineups` (formação + jogadores)
- SofaScore `/event/{id}/h2h` (confrontos diretos)
- Bridge Betano lineups (primary) · AF residual (fallback)

### Pilar 2 — Contexto (peso 30%)

**Objetivas (cálculo automático):** posição/motivação (`position_in_table`,
`points_to_relegation`, `points_to_g4`, `relegation_risk_score`, `g4_chase_score`),
stage (`tournament_stage` ∈ GROUP/KO/FINAL, `is_decision_game`, `aggregate_score`),
calendário (`home/away_rest_days`, `home/away_next_match_important`,
`home/away_last_match_competition`), lesões (`home/away_starters_injured`,
`home/away_key_player_missing`).

**Semi-subjetivas (hardcoded inicial):** `classicos_brasil`, `classicos_europa`,
`rivalidades_internacionais` (listas crescentes de pares de times).

### Pilar 3 — Live (peso 30%, gatilho)

Já temos via `stats_history` + `events_history`: stats acumulados (corners, cartões,
chutes, `shots_on_target`, posse, `big_chances`, xG — enrichment SofaScore),
derivados (`pressure_score`, `tension_score`, `corners_last_5/10min`), momentum
(`momentum_5min`, `shot_efficiency`), eventos (`minute`, placar,
`score_changed_last_10min`, `red_card_last_15min`).

---

## 4. Decisões do Daniel (CRÍTICO)

```yaml
decisoes_sinais_valor:
  stake_strategy:
    valor: "20-50% da banca"
    fonte: Daniel (decisão consciente após alerta de risco)
    risco_assumido: alto
    alternativa_recomendada: Kelly Fractional 2-5% (DESCARTADA pelo Daniel)
  modelo_decisao:
    valor: "ML/Quant (LightGBM com validação rigorosa)"
    razao: "Quer modelo aprendendo padrões, não regras fixas"
    fallback: heurísticas até modelos amadurecerem
  faixa_odds:
    valor: "1.40 - 1.70"
    razao: "Linhas maduras, alta probabilidade implícita"
    implicacao: "odd 1.40 ⇒ 71.4% impl. · 1.70 ⇒ 58.8% · modelo precisa estimar >75% pra edge real"
  estrutura_pilares:
    pilar_1_historico: { peso: 40%, por_competicao: true, janela: "últimos 10 NA COMPETIÇÃO" }
    pilar_2_contexto:  { peso: 30%, inclui_rotacao: true, inclui_motivacao: true }
    pilar_3_live:      { peso: 30%, papel: "gatilho confirmador" }
  mercados_prioritarios:
    definido: false
    sugestao: [Over/Under Goals, BTTS, 1X2, Asian Handicap, O/U Corners, O/U Cards]
    PENDENTE_DANIEL: "rankear quando começar H_VALOR.0"
  tier_comercial:
    definido: false
    sugestao: "Quant Pro R$199,90/mês (separado de Pro/Max)"
    PENDENTE_DANIEL: "confirmar tier separado ou incluir no Max"
  fontes_de_dados:
    primary: "SofaScore API (curl_cffi)"
    secondary: "Betano bridge (live + lineups)"
    residual: "AF (só se SofaScore falhar)"
    scraping: "NÃO USAR (descartado por Daniel)"
```

### Diálogo crítico (preservar)

```
Daniel sobre stake:
  "aqui pode ser de 20 a 50% da banca, por isso quero odds maduras e com alta
   probabilidade, sim eu sei que nenhuma aposta é 100% CONFIÁVEL"

Claude alertou:
  - Stake 30% banca + accuracy 65% (realista) ⇒ -67% banca em 20 sinais
  - Profissionais raramente ultrapassam 60% accuracy sustentável
  - Kelly Fractional (2-5%) é o padrão conservador

Daniel manteve a decisão: 20-50%.
  Razão: "Foco em odds maduras 1.40-1.70 com alta probabilidade."

REGISTRADO: stake 20-50% sob responsabilidade total do Daniel. Sistema EMITE
sinal com stake_sugerida; cliente decide o tamanho real. Comunicação ao cliente
deve ser educativa sobre risco — sem promessa de ROI.
```

---

## 5. Implementação faseada (~95-160h em 6-12 meses)

- **H_VALOR.0 — Investigação (~6-10h):** catalogar 10-15 mercados Betano (via
  `/event/{id}/state`), validar cobertura histórica SofaScore, definir features por
  pilar (JSON), thresholds preliminares (`score_historico_min` 0.6, `score_contexto_min`
  0.5, `score_live_min` 0.5, `edge_minimo` 0.08). Entregável: este doc + design detalhado.
- **H_VALOR.1 — Schema + captura (~15-25h):** migration novas tabelas
  (`team_form_history`, `team_context_snapshots`, `odds_pre_match_history`,
  `sinais_valor`, `sinais_valor_features` — **renumerar a migration**, 0017 está usado).
  Workers `PreMatchOddsSnapshotWorker` (6h/3h/1h/15min antes), `TeamContextWorker`,
  `TeamFormHistoryWorker`, cron `EnrichmentScheduler`. Dataset começa a acumular.
- **H_VALOR.2 — Modelo Histórico (~25-40h):** ETL treino, feature engineering,
  LightGBM por mercado (3-5 inicial), validação **walk-forward** (temporal), calibração
  de probabilidade (Platt/Isotonic — prob real, não só ranking).
- **H_VALOR.3 — Pilares 2+3 + integração (~30-50h):** modelos Contexto + Live,
  composição `score_final = w1·hist + w2·ctx + w3·live`, `edge = prob_modelo/prob_impl − 1`,
  decision threshold (edge ≥ 8%, score mín por pilar, odd 1.40-1.70), worker
  `SinaisValorEmitter` + notifier WhatsApp diferenciado.
- **H_VALOR.4 — Backtest + produção (~20-35h):** engine de backtest (ROI, Sharpe,
  max drawdown, accuracy por mercado/liga/período), walk-forward contínuo (re-treino
  mensal), dashboard tier Quant Pro (justificativa textual + SHAP), comunicação cliente
  (disclaimer de risco, sem promessa de ROI).

---

## 6. Captura de dados imediata (paralelo, ~18h — só pós-A3 estável)

- `PreMatchOddsSnapshotWorker` (~4h) — movimento de linha pre-match → `odds_pre_match_history`.
- `TeamFormHistoryWorker` (~6h) — cron 1×/dia, forma por competição (SofaScore) → `team_form_history`.
- `TeamContextWorker` (~8h) — pré-jogo calcula contexto (standings + lineups) → `team_context_snapshots`.

Zero impacto no pipeline atual. **Decisão:** avaliar início desses workers **depois**
da Fase H A3 estável, possivelmente em paralelo com V2 Dashboard.

---

## Pré-requisitos bloqueantes

- Fase H A3 completa (`sofa_event_id` chave única)
- V2 Dashboard estável em produção
- Dataset 4-6 meses capturado
- 50+ clientes Pro/Max ativos (validação comercial)

## Pendências de decisão do Daniel (antes de H_VALOR.0)

- [ ] Rankear mercados prioritários
- [ ] Confirmar tier comercial (separado R$199,90 ou dentro do Max)
- [ ] Validar nome final ("Sinais Valor" interno)

## Riscos identificados

1. **Sample bias** — modelo pega ruído → mitigação: walk-forward.
2. **Mercados eficientes** — edge é raro → ~1-5 sinais/semana esperado.
3. **Sobreajuste** — passado ≠ futuro → regularização + atualização contínua.
4. **Comunicação cliente** — expectativa de ROI irreal → educação + disclaimer.
5. **Streak de losses** — variância natural → bankroll management explícito (agrava com stake 20-50%).

---

## Resumo compacto (memória)

```yaml
sinais_valor:
  status: documentado_on_hold
  conceito: "categoria nova multi-mercado, odds 1.40-1.70, 3 pilares (Hist 40% + Ctx 30% + Live 30%)"
  decisoes_imutaveis:
    stake: "20-50% banca (Daniel, risco assumido)"
    modelo: "LightGBM + walk-forward"
    odds: "1.40-1.70"
    edge_minimo: "8%"
    historico_por_competicao: true   # CRÍTICO — não misturar Brasileirão com Libertadores
    sem_scraping: true               # SofaScore API cobre ~95%
  pendencias_daniel: [rankear_mercados, confirmar_tier, validar_nome]
  bloqueantes: [fase_h_a3, v2_dashboard, dataset_4_6_meses, 50_clientes]
  proxima_acao: "NÃO implementar agora — seguir Fase H A2. Captura de dados só pós-A3."
```
