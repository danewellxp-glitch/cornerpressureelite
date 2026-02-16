# Auditoria Completa do CPES - 2026-02-15

> Auditoria de 8 fases executada sobre todo o codebase do Corner Pressure Elite System.

---

## FASE 1 - DEBUG DO WHATSAPP

### Fluxo do Webhook (Completo)

```
Mensagem do usuario
  -> WAHA (porta 3000) recebe
  -> WAHA faz POST para http://cpes-api:8000/api/webhook/whatsapp
  -> api_server.py:webhook_whatsapp() recebe body JSON
  -> Verifica event == "message"
  -> Extrai payload.from (sender) e payload.body (texto)
  -> Verifica sender em _authorized_senders
  -> Parseia comando (remove /, lowercase)
  -> Chama _handle_admin_command(command)
  -> Chama send_whatsapp_message(sender, response_text) via waha_manager.py
  -> waha_manager.py cria/reutiliza WhatsAppClient singleton
  -> WhatsAppClient faz POST para WAHA /api/sendText
  -> WAHA entrega mensagem ao usuario
```

### Problemas Identificados

| # | Problema | Arquivo | Linha | Severidade |
|---|---------|---------|-------|------------|
| 1 | Sem check `fromMe` - bot processa proprias mensagens | api_server.py | 408 | MEDIO |
| 2 | Sem retry em falha de envio | api_server.py | 461-476 | ALTO |
| 3 | Webhook URL hardcoded para Docker | api_server.py | 104 | BAIXO |
| 4 | WAHASessionManager cria Lock em class scope | waha_manager.py | 22 | BAIXO (Python 3.12 ok) |
| 5 | Dupla config de webhook (env + startup PUT) | docker-compose + api_server | - | INFO |

### Patches Aplicados

1. **Adicionado check `fromMe`** - Ignora mensagens enviadas pelo proprio bot, evitando loops
2. **Adicionado retry com 2 tentativas** - Se a primeira falha, aguarda 1s e tenta novamente
3. **Logging aprimorado** - Cada etapa do webhook agora loga com prefixo `[WEBHOOK]`

### Status Final

- Webhook URL: Correto para Docker (`http://cpes-api:8000/api/webhook/whatsapp`)
- Authorized senders: `554195089104@c.us` (admin) + `61405086785@c.us` (updates)
- Comandos reconhecidos: `/status`, `/jogos`, `/stats`, `/help` (+ aliases)
- Envio: Via WAHASessionManager singleton com retry

---

## FASE 2 - VISIBILIDADE DOS JOGOS NA JANELA

### Funcao que define jogos na janela

- **Arquivo**: `main.py:460-520` (loop principal)
- **Criterio de tempo**: `MINUTO_INICIO=50`, `MINUTO_FIM=90`
- **Early trigger**: 7+ escanteios antes do min 50 -> entra na janela

### Fases do jogo

| Fase | Minutos | Polling | Descricao |
|------|---------|---------|-----------|
| Primeiro tempo | 0-30 | 5 min | Monitoramento passivo |
| Pre-janela | 31-50 | 3 min (1 min se 7+ esc) | Preparacao |
| **Janela de analise** | **50-90** | **30 seg** (corrigido de 60s) | **Analise ativa** |
| Reta final | 90+ | 30 seg | Acrescimos |

### Logging Instrumentado

Cada jogo analisado agora loga (via `decision_engine.py`):

```
[ANALISE] Premier League | Arsenal vs Chelsea | Min 65 | Placar 1-0 |
  Escanteios: 8 (H:5 A:3) | Rate: 0.123/min |
  Est5min: 1 Est10min: 2 |
  Ataques: 45 Posse: 62% Finalizacoes: 7 |
  Linha: 10.5 Odd: 1.85
```

### Relatorio de Ciclo

Ao final de cada ciclo, o sistema agora gera:

```
[AUDIT] === RELATORIO DO CICLO ===
[AUDIT] Total analisados: 12
[AUDIT] Passaram filtros:  5
[AUDIT] Score suficiente:  3
[AUDIT] Edge suficiente:   2
[AUDIT] SINAIS emitidos:   2 (1P + 1N)
[AUDIT] --- Motivos de exclusao ---
[AUDIT]   Fora da janela: 4
[AUDIT]   Poucos escanteios: 2
[AUDIT]   Score insuficiente: 2
[AUDIT]   Edge insuficiente: 1
[AUDIT] === FIM DO RELATORIO ===
```

---

## FASE 3 - AVALIACAO DA ESTRATEGIA

### BUG CRITICO ENCONTRADO

**Localizacao**: `utils/helpers.py:parse_fixture_to_jogo` (linhas 64-80)

**O que acontecia**: Os campos `escanteios_ultimos_5min` e `escanteios_ultimos_10min` do `JogoAoVivo` **NUNCA eram preenchidos**. A API-Football retorna estatisticas TOTAIS do jogo, nao janelas de tempo. Os campos ficavam no valor default `0`.

**Impacto em cascata**:

```
helpers.py
  escanteios_ultimos_5min = 0  (NUNCA preenchido)
  escanteios_ultimos_10min = 0 (NUNCA preenchido)
    |
    v
decision_engine.py:122
  if jogo.escanteios_ultimos_5min < MIN_ESCANTEIOS_5MIN (1):
    0 < 1 -> SEMPRE TRUE -> TODOS OS JOGOS BLOQUEADOS
    |
    v
  ZERO sinais gerados. Sistema completamente inoperante.
    |
    v
score_engine.py:22-29
  escanteios_ultimos_10min >= 2 -> 0 >= 2 -> SEMPRE FALSE -> +3 pontos NUNCA
  escanteios_ultimos_5min >= 1  -> 0 >= 1 -> SEMPRE FALSE -> +1 ponto NUNCA
    |
    v
  Score maximo possivel = 6 (sem estes 4 pontos)
  Apenas jogos com time perdendo (6/10) atingem MIN_SCORE_NORMAL=6
  MAS todos ja foram bloqueados pelo filtro anterior.
```

**Conclusao**: O sistema estava **estruturalmente quebrado** desde a implementacao. Nenhum sinal jamais foi ou poderia ser gerado.

### Parametros Atuais

| Parametro | Valor | Funcao |
|-----------|-------|--------|
| `MIN_SCORE_NORMAL` | 6 | Score minimo para sinal NORMAL |
| `MIN_SCORE_PREMIUM` | 8 | Score minimo para sinal PREMIUM |
| `MIN_EDGE_NORMAL` | 0.8 | Edge minimo para sinal NORMAL |
| `MIN_EDGE_PREMIUM` | 1.5 | Edge minimo para sinal PREMIUM |
| `MIN_ESCANTEIOS_TOTAL` | 3 | Minimo de escanteios no jogo |
| `MIN_ESCANTEIOS_5MIN` | 1 | Minimo de escanteios recentes (estimado) |
| `MIN_ESCANTEIOS_JOGO_MORNO` | 7 | Minimo para jogo 0x0 apos min 60 |
| `MAX_DIFERENCA_GOLS` | 3 | Maximo de diferenca de gols |
| `ESCANTEIOS_EARLY_WINDOW` | 7 | Escanteios para abrir janela antecipada |
| `MINUTO_INICIO` | 50 | Inicio da janela de analise |
| `MINUTO_FIM` | 90 | Fim da janela de analise |

### Composicao do Pressure Score (0-10)

| Componente | Pontos | Threshold | Dados usados | Status |
|-----------|--------|-----------|--------------|--------|
| Escanteios 10min | +3 | >= 2 escanteios | **Estimado via corner rate** | CORRIGIDO |
| Escanteio 5min | +1 | >= 1 escanteio | **Estimado via corner rate** | CORRIGIDO |
| Ataques perigosos | +2 | >= 3 ataques | Total do jogo (sempre passa) | FUNCIONAL |
| Time perdendo | +2 | Diferenca = 1 gol | Dado real | FUNCIONAL |
| Posse dominante | +1 | > 50% | Overall (sempre passa) | FUNCIONAL |
| Finalizacoes | +1 | >= 2 finalizacoes | Total do jogo (sempre passa) | FUNCIONAL |

### Score Baseline Apos Fix

Todo jogo ativo recebe automaticamente +4 pontos (ataques +2, posse +1, finalizacoes +1).
A discriminacao real vem de:
- Corner rate: 0 a +4 pontos
- Time perdendo: 0 ou +2 pontos

Range efetivo: 4-10.

### Projecao de Elegibilidade (estimada pos-fix)

Com os parametros atuais e o bug corrigido:

| Cenario | Score estimado | Passa? |
|---------|---------------|--------|
| 8 corners min 60, time perdendo | 4+3+1+2 = 10 | SIM (PREMIUM) |
| 8 corners min 60, empate | 4+3+1 = 8 | SIM (PREMIUM se edge ok) |
| 6 corners min 60, time perdendo | 4+1+2 = 7 | SIM (NORMAL se edge ok) |
| 6 corners min 60, empate | 4+1 = 5 | NAO (score 5 < 6) |
| 4 corners min 60, time perdendo | 4+0+2 = 6 | SIM (NORMAL se edge ok) |
| 4 corners min 60, empate | 4+0 = 4 | NAO |

**Taxa estimada de elegibilidade**: 15-25% dos jogos na janela passam os filtros.

### Simulacao Validada (11 cenarios realistas)

```
  SINAL PREMIUM  | Arsenal vs Chelsea - Perdendo 8esc       | Score=10 Edge=+4.19
  SINAL PREMIUM  | Real vs Barca - Empate 10esc             | Score=8  Edge=+4.07
  BLOQUEADO      | Flamengo vs Palmeiras - 0x0 4esc         | Jogo morno
  BLOQUEADO      | Bayern vs Dortmund - Goleada 4x0         | Diferenca gols
  SINAL PREMIUM  | Liverpool vs Man City - 12esc            | Score=10 Edge=+5.70
  BLOQUEADO      | Juve vs Milan - 0x0 morno 3esc           | Jogo morno
  BLOQUEADO      | PSG vs Lyon - time sem corner fora        | Time sem escanteio
  SINAL PREMIUM  | Ajax vs PSV - Animado 2x2 9esc           | Score=8  Edge=+5.07
  BLOQUEADO      | Boca vs River - Sem odds                  | Sem linha de mercado
  BLOQUEADO      | Man Utd vs Wolves - 5esc empate           | Score insuficiente
  SINAL NORMAL   | Inter vs Napoli - Perdendo 6esc           | Score=7  Edge=+1.94

  Total: 11 | Sinais: 5 | Elegibilidade: 45%
```

Nota: 45% e acima do esperado porque os cenarios foram escolhidos para cobrir diversidade. Em producao, com jogos reais, estimamos 15-25%.

### Filtros Restritivos (por ordem de impacto)

1. **Time sem escanteio** (`decision_engine.py:139-142`): Se um time tem 0 escanteios apos min 45, bloqueia. Isso e razoavel mas restritivo - jogos equilibrados onde um time ataca por fora (sem corners) sao excluidos.

2. **Jogo morno** (`decision_engine.py:128-136`): 0x0 apos min 60 com < 7 escanteios. Razoavel.

3. **MIN_ESCANTEIOS_5MIN** (`decision_engine.py:122-125`): Agora estimado via corner rate. Jogos com < 3 corners total no min 60+ serao bloqueados (rate muito baixa).

---

## FASE 4 - SIMULACAO RETROATIVA

### Dados Disponiveis

O sistema possui um modulo de backtest completo em `corner-pressure-elite/backtest/`:
- `simulator.py`: Replay do decision engine sobre snapshots
- `reporter.py`: Geracao de relatorios markdown
- `__main__.py`: CLI para simulacao e otimizacao

### Comandos para Executar

```bash
# Status dos dados coletados
cd corner-pressure-elite && python -m backtest status

# Simular com parametros atuais
python -m backtest simulate

# Simular com parametros relaxados (-10%)
python -m backtest simulate --min-score 5 --min-edge 0.7

# Simular com parametros relaxados (-20%)
python -m backtest simulate --min-score 5 --min-edge 0.6

# Grid search otimizado
python -m backtest optimize --save
```

### Limitacao

**CRITICA**: Como o bug de `escanteios_ultimos_5min=0` afetava tambem os snapshots salvos, TODOS os snapshots historicos tem este campo zerado. Portanto:
- O backtest sobre dados existentes reproduzira o mesmo bug
- Os snapshots precisam ser RE-coletados apos o fix para backtest valido
- O fix no `helpers.py` resolve o problema para snapshots FUTUROS

### Recomendacao

1. Redeployar com o fix aplicado
2. Aguardar 2-3 dias de coleta de novos snapshots
3. Rodar `python -m backtest optimize --save` para encontrar config otima

---

## FASE 5 - AVALIACAO DE LINHAS

### Cenarios de Teste

| Cenario | min_score | min_edge | Efeito esperado |
|---------|-----------|----------|-----------------|
| A (Atual) | 6 | 0.8 | Base: 15-25% elegibilidade |
| B (-10%) | 5 | 0.7 | Mais sinais, risco levemente maior |
| C (-20%) | 5 | 0.6 | Volume alto, risco moderado |

### Analise por Cenario

**Cenario A (Atual - min_score=6, min_edge=0.8)**:
- Volume: 1-3 sinais por dia (com jogos ativos)
- Risco: Conservador
- Ideal para: Operacao com bankroll limitado

**Cenario B (min_score=5, min_edge=0.7)**:
- Volume: 3-5 sinais por dia
- Risco: Moderado
- Ideal para: Volume sustentavel com bom filtro
- **RECOMENDADO como ponto de partida pos-fix**

**Cenario C (min_score=5, min_edge=0.6)**:
- Volume: 5-8 sinais por dia
- Risco: Agressivo
- Ideal para: Fase de coleta de dados (backtest)

### Recomendacao de Ajuste

Para a fase inicial (primeiras 2 semanas pos-fix), recomendo **Cenario B**:

```python
# config.py - Ajuste sugerido (temporario para coleta de dados)
MIN_SCORE_NORMAL = 5   # de 6 para 5
MIN_EDGE_NORMAL = 0.7  # de 0.8 para 0.7
```

Apos 2 semanas com dados reais, rodar o backtester para encontrar os valores otimos.

---

## FASE 6 - ANALISE DE GARGALOS

### 1. Rate Limiter

- **Status**: Funcional, bem instrumentado
- **Limite diario**: 7500 req (API_DAILY_LIMIT)
- **Limite por minuto**: 50 req
- **Impacto**: Baixo. Com 13 ligas e polling adaptativo, consumo estimado de 200-400 req/dia
- **Gargalo**: NAO

### 2. Delay de Atualizacao

- **Polling na janela**: Reduzido de 60s para 30s (fix aplicado)
- **Tempo entre deteccao e envio**: < 2s (webhook instantaneo)
- **Gargalo**: CORRIGIDO (era 60s, agora 30s)

### 3. Jogos Saindo da Janela

- **Risco**: Jogos no min 89 podem sair antes de serem avaliados
- **Mitigacao**: Polling de 30s garante avaliacao a cada 30s
- **Impacto**: Minimo apos fix

### 4. Loop de Analise

- **Cada jogo requer**: 1 req (statistics) + 1 req (odds)
- **Com 5 jogos na janela**: 10 req por ciclo
- **Ciclo de 30s**: 1200 req/hora (abaixo do limite de 3000/hora)
- **Gargalo**: NAO

### 5. Concorrencia

- **Status**: Analise sequencial (jogo a jogo)
- **Impacto**: Com 5 jogos, cada ciclo demora ~5-10s (IO-bound)
- **Melhoria futura**: `asyncio.gather()` para analise paralela
- **Gargalo**: BAIXO (melhoravel mas nao critico)

### 6. Webhook Reliability

- **Problema**: Envio sem retry
- **Fix aplicado**: Retry de 2 tentativas com 1s de intervalo
- **Gargalo**: CORRIGIDO

### 7. Dados Incorretos (CRITICO - CORRIGIDO)

- **Problema**: `escanteios_ultimos_5min = 0` sempre
- **Impacto**: 100% dos jogos bloqueados
- **Fix aplicado**: Estimacao via corner rate
- **Gargalo**: ERA O PRINCIPAL - CORRIGIDO

---

## FASE 7 - DASHBOARD DE VISIBILIDADE

### Estado Atual

O dashboard Next.js em `dashboard/` ja possui:
- Status do sistema (online/offline, ciclo, API usage)
- Jogos ao vivo por fase (pre_janela, na_janela, pos_janela)
- Sinais recentes
- Logs em tempo real
- Configuracao de ligas

### Sugestao: Painel de Auditoria

Adicionar ao dashboard (endpoint `/api/audit`):

```json
{
  "jogos_ativos": {
    "total": 12,
    "na_janela": 5,
    "analisados": 5,
    "elegíveis": 2,
    "sinais_emitidos": 1
  },
  "filtros": {
    "fora_da_janela": 4,
    "poucos_escanteios": 2,
    "score_insuficiente": 1,
    "edge_insuficiente": 0
  },
  "ultimo_sinal": {
    "jogo": "Arsenal vs Chelsea",
    "tipo": "NORMAL",
    "score": 7,
    "edge": 1.2,
    "projecao": 11.7,
    "linha": 10.5,
    "timestamp": "2026-02-15T14:32:00"
  },
  "taxa_elegibilidade_dia": "18.5%",
  "sinais_hoje": 3,
  "historico_7d": {
    "sinais": 15,
    "greens": 9,
    "reds": 6,
    "winrate": "60.0%",
    "roi": "+2.45u"
  }
}
```

### Implementacao Sugerida

1. Expor `decision_engine._ciclo_stats` via endpoint `/api/audit`
2. Acumular stats diarios em memoria
3. Componente React para visualizacao

---

## FASE 8 - RELATORIO FINAL

### 1. Status do WhatsApp

| Item | Status |
|------|--------|
| WAHA configurado | OK (docker-compose) |
| Webhook registrado | OK (startup + env) |
| Authorized senders | OK (admin + updates) |
| Check fromMe | CORRIGIDO (adicionado) |
| Retry de envio | CORRIGIDO (2 tentativas) |
| Logging completo | CORRIGIDO (cada etapa logada) |

### 2. Status da Sessao

- WAHA Plus: `devlikeapro/waha-plus:latest`
- Session name: `default`
- API Key: Configurada
- Webhook URL: `http://cpes-api:8000/api/webhook/whatsapp`

### 3. Fluxo Completo (webhook -> envio)

```
WAHA (recebe msg) -> POST webhook -> api_server.py
  -> Check event=message ✓
  -> Check fromMe=false ✓ (NOVO)
  -> Check sender autorizado ✓
  -> Parse comando ✓
  -> Gera resposta ✓
  -> Envia via waha_manager (com retry) ✓ (NOVO)
  -> Loga resultado ✓
```

### 4. Quantidade Real de Jogos Analisados

**Antes do fix**: 0 jogos geravam sinal (100% bloqueados pelo filtro quebrado).

**Apos o fix (estimado)**:
- Jogos ao vivo por dia nas 13 ligas: 5-15
- Jogos na janela (50-90 min): 2-8
- Passam filtros estruturais: 1-5
- Score suficiente: 1-3
- Edge suficiente: 1-2 sinais por dia

### 5. Taxa Real de Elegibilidade

| Metrica | Antes | Apos Fix |
|---------|-------|----------|
| Passam filtro escanteios_5min | 0% | ~70% |
| Passam todos os filtros | 0% | 15-25% |
| Score >= 6 | 0% | 10-20% |
| Edge >= 0.8 | 0% | 8-15% |
| **Sinais emitidos** | **0%** | **5-10%** |

### 6. Pontos Fracos da Estrategia

1. **Stats infladas**: `ataques_perigosos`, `finalizacoes`, `posse` sao totais do jogo, nao janelas de 10 min. Isso da +4 pontos gratis a todo jogo.
2. **Corner rate como proxy**: A estimativa de escanteios recentes via taxa media nao captura picos/vales de atividade.
3. **Sem odds default**: Se a API nao retorna odds, `linha_atual=0` gera edge artificial infinito.
4. **Filtro "time sem escanteio"**: Bloqueia jogos validos onde um time ataca sem corners.

### 7. Parametros Excessivamente Rigidos

| Parametro | Valor | Avaliacao |
|-----------|-------|-----------|
| MIN_SCORE_NORMAL=6 | OK | Razoavel com baseline de +4 |
| MIN_SCORE_PREMIUM=8 | ALTO | Requer corner rate alta + time perdendo |
| MIN_EDGE_NORMAL=0.8 | MODERADO | Funciona para maioria dos jogos |
| MIN_EDGE_PREMIUM=1.5 | ALTO | Poucos jogos atingem |
| MIN_ESCANTEIOS_JOGO_MORNO=7 | OK | Razoavel |
| Filtro "time sem escanteio" | RESTRITIVO | Considerar relaxar para >= 1 apos min 60 |

### 8. Ajustes Recomendados

**Imediato (aplicar agora)**:
- [x] Fix escanteios_ultimos_5min/10min (FEITO)
- [x] Polling 30s na janela (FEITO)
- [x] Webhook retry + fromMe check (FEITO)
- [x] Logging de auditoria (FEITO)

**Fase 2 (apos 2 semanas de dados)**:
- [ ] Rodar backtest optimize para calibrar thresholds
- [ ] Ajustar score engine para usar dados reais de eventos (API events endpoint)
- [ ] Adicionar painel de auditoria ao dashboard
- [ ] Implementar analise paralela de jogos (asyncio.gather)

**Fase 3 (otimizacao)**:
- [ ] Tracking real de corners delta entre polls (estado entre ciclos)
- [ ] Normalizar ataques/finalizacoes por minuto (em vez de total)
- [ ] Default de linha por liga quando odds nao disponiveis
- [ ] Relaxar filtro "time sem escanteio" para >= 1 corner apos min 60

### 9. Patches Aplicados

| Arquivo | Mudanca | Impacto |
|---------|---------|---------|
| `utils/helpers.py` | Estimacao de escanteios_5min/10min via corner rate | CRITICO - Desbloqueia toda a geracao de sinais |
| `engine/decision_engine.py` | Logging completo por jogo + relatorio de ciclo + filtro sem odds | ALTO - Visibilidade total + evita falsos positivos |
| `api_server.py` | fromMe check + retry + logging webhook | ALTO - Confiabilidade WhatsApp |
| `utils/adaptive_polling.py` | Janela 60s -> 30s | MEDIO - Mais responsivo |
| `api_server.py` | Textos de polling stats atualizados | BAIXO - Consistencia |

### 10. Melhorias Estruturais

1. **Backtest com dados limpos**: Redeployar, coletar 2 semanas de snapshots pos-fix, rodar otimizacao.
2. **Corner delta tracking**: Armazenar `{fixture_id: (corners, timestamp)}` entre ciclos para calcular corners REAIS nos ultimos N minutos.
3. **Analise paralela**: `asyncio.gather(*[self._analisar_jogo(f) for f in jogos_para_analisar])` para analisar todos os jogos simultaneamente.
4. **Odds fallback**: Usar `media_esperada` da liga como linha default quando API nao retorna odds.
5. **Alertas de saude**: Endpoint `/api/health/detailed` com status de cada componente (API, WAHA, DB, ultimo sinal).

---

## Resumo Executivo

O CPES estava **completamente inoperante** devido a um bug critico em `helpers.py` onde os campos `escanteios_ultimos_5min` e `escanteios_ultimos_10min` nunca eram preenchidos (valor 0). Isso causava o bloqueio de 100% dos jogos pelo filtro `MIN_ESCANTEIOS_5MIN=1` no decision engine.

**Patches aplicados resolvem o problema fundamental**. O sistema agora:
- Estima corners recentes via corner rate (melhor aproximacao disponivel)
- Loga cada jogo analisado com todos os detalhes
- Gera relatorio de auditoria por ciclo
- Envia mensagens WhatsApp com retry e protecao contra loops
- Analisa a cada 30s na janela (em vez de 60s)

**Proximo passo**: Redeployar com `docker compose up -d --build` e monitorar logs para confirmar geracao de sinais.
