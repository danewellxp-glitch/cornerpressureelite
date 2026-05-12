# CPES — Documentacao Completa do Sistema

> Corner Pressure Elite System — Motor automatizado de analise de escanteios ao vivo para sinais de apostas esportivas.

**Ultima atualizacao:** 2026-02-16

---

## Indice

1. [Visao Geral](#1-visao-geral)
2. [Stack Tecnologico](#2-stack-tecnologico)
3. [Infraestrutura e Deploy](#3-infraestrutura-e-deploy)
4. [Arquitetura de Dados](#4-arquitetura-de-dados)
5. [Loop Principal do Robo](#5-loop-principal-do-robo)
6. [Motor de Decisao](#6-motor-de-decisao)
7. [Score Engine](#7-score-engine)
8. [Projection Engine](#8-projection-engine)
9. [Filtros Estruturais](#9-filtros-estruturais)
10. [Polling Adaptativo](#10-polling-adaptativo)
11. [Rate Limiter](#11-rate-limiter)
12. [Integracao API-Football](#12-integracao-api-football)
13. [Notificacoes WhatsApp](#13-notificacoes-whatsapp)
14. [Dashboard](#14-dashboard)
15. [API Server (FastAPI)](#15-api-server-fastapi)
16. [Banco de Dados](#16-banco-de-dados)
17. [Backtest](#17-backtest)
18. [Re-avaliacao de Sinais](#18-re-avaliacao-de-sinais)
19. [Verificacao de Resultados](#19-verificacao-de-resultados)
20. [Ligas Monitoradas](#20-ligas-monitoradas)
21. [Parametros Tuneaveis](#21-parametros-tuneaveis)
22. [Arvore de Arquivos](#22-arvore-de-arquivos)

---

## 1. Visao Geral

O CPES monitora partidas de futebol ao vivo em 13 ligas, analisa a pressao ofensiva via escanteios e emite sinais de aposta (Over Escanteios) quando detecta **edge positivo** entre a projecao estatistica e a linha de mercado.

**Fluxo resumido:**

```
API-Football (dados ao vivo)
       |
       v
  Parse / Filtros ──> Jogo fora da janela? ──> Descarta
       |
       v
  Pressure Score (0-11 pontos)
       |
       v
  Score < 5? ──> Descarta
       |
       v
  Projecao Hibrida (corners projetados a 95 min)
       |
       v
  Edge = Projecao - Linha de Mercado
       |
       v
  Edge < 0.7? ──> Descarta
       |
       v
  SINAL (NORMAL ou PREMIUM) ──> WhatsApp + DB
```

---

## 2. Stack Tecnologico

| Camada | Tecnologia | Versao |
|--------|-----------|--------|
| Backend (robo + API) | Python + FastAPI | 3.12 |
| Frontend (dashboard) | Next.js + TypeScript | 15.x |
| Notificacoes | WAHA Plus (WhatsApp HTTP API) | 2026.2.1 |
| Banco de dados | SQLite (via aiosqlite) | — |
| Containers | Docker Compose | — |
| CDN / Tunnel | Cloudflare Workers + Tunnel | — |
| API de dados | API-Football v3 | Pro |

**Dependencias Python principais:** `aiohttp`, `fastapi`, `uvicorn`, `python-dotenv`, `pydantic`, `aiosqlite`, `requests`

---

## 3. Infraestrutura e Deploy

### 3.1 Servicos Docker

```yaml
services:
  waha:          # WhatsApp API (WAHA Plus)
    image: devlikeapro/waha-plus:latest
    port: 3000

  api:           # FastAPI (api_server.py)
    build: ./corner-pressure-elite
    port: 8000
    command: uvicorn api_server:app --host 0.0.0.0 --port 8000

  main:          # Robo principal (main.py)
    build: ./corner-pressure-elite
    command: python main.py

  dashboard:     # Next.js
    build: ./dashboard
    port: 3001
```

Todos os containers compartilham a rede `cpes-network`. O WAHA e acessado internamente como `http://waha:3000`, a API como `http://cpes-api:8000`.

### 3.2 Volumes

| Volume | Caminho | Descricao |
|--------|---------|-----------|
| `waha-sessions` | `/app/.sessions` | Sessoes WhatsApp persistentes |
| `data/` | `/app/data` | SQLite + JSONs de estado |
| `logs/` | `/app/logs` | Arquivos de log diarios |

### 3.3 Dominios

| URL | Servico |
|-----|---------|
| `https://iqpressure.online` | Dashboard (Cloudflare Tunnel) |
| `https://api.iqpressure.online` | API FastAPI |
| `ssh.iqpressure.online` | SSH via Cloudflare Tunnel |

### 3.4 Variaveis de Ambiente

```env
API_FOOTBALL_KEY=<chave_api>
API_DAILY_LIMIT=100
WAHA_URL=http://waha:3000
WAHA_SESSION_NAME=default
WAHA_API_KEY=<bearer_token>
WHATSAPP_GROUP_ID=<id>@g.us
WHATSAPP_ADMIN=<telefone>
WHATSAPP_UPDATES=<telefone>
DB_PATH=/app/data/cpes.db
LOG_LEVEL=INFO
TZ=America/Sao_Paulo
```

### 3.5 Comandos

```bash
# Subir tudo
docker compose up -d

# Rebuild apos mudanca de codigo
docker compose build api main --no-cache
docker compose up -d api main

# Parar tudo
docker compose down

# Logs do robo
docker logs cpes-main --tail 100 -f
```

---

## 4. Arquitetura de Dados

### 4.1 Modelo `JogoAoVivo`

Representa um jogo ao vivo com todas as metricas necessarias para analise.

```
JogoAoVivo
├── id                              # fixture_id da API-Football
├── liga_id, liga_nome              # Identificacao da liga
├── time_casa, time_fora            # Nomes dos times
├── placar_casa, placar_fora        # Placar atual
├── minuto                          # Minuto atual do jogo
├── escanteios_total                # Total de escanteios (soma dos dois times)
├── escanteios_casa                 # Escanteios do time da casa
├── escanteios_fora                 # Escanteios do time visitante
├── escanteios_ultimos_10min        # ESTIMADO via corner rate (nao vem da API)
├── escanteios_ultimos_5min         # ESTIMADO via corner rate (nao vem da API)
├── ataques_perigosos_ultimos_10min # TOTAL do jogo (nome legado, e game total)
├── posse_ultimos_10min             # % do time com mais posse (game total)
├── finalizacoes_recentes           # Total de finalizacoes no gol (game total)
├── media_historica_combinada       # Media de corners da liga
├── linha_atual                     # Linha de mercado (ex: 10.5)
├── odd_atual                       # Odd do Over
├── descricao (property)            # "Time Casa vs Time Fora"
├── placar (property)               # "1-0"
└── diferenca_gols (property)       # abs(placar_casa - placar_fora)
```

**NOTA CRITICA:** A API-Football retorna estatisticas como **totais acumulados do jogo**, nao janelas de tempo. Os campos `escanteios_ultimos_5min` e `escanteios_ultimos_10min` sao **estimados** via formula:

```python
corner_rate = total_corners / minuto
est_5min  = min(total, round(rate * 5 + 0.3))
est_10min = min(total, round(rate * 10 + 0.3))
```

Os campos `ataques_perigosos`, `posse` e `finalizacoes` sao totais do jogo, normalizados por taxa/minuto no Score Engine.

### 4.2 Modelo `Sinal`

```
Sinal
├── tipo                    # "NORMAL" ou "PREMIUM"
├── jogo: JogoAoVivo        # Dados completos do jogo
├── pressure_score          # Score calculado (0-11)
├── projecao                # Corners projetados a 95 min
├── edge                    # projecao - linha_atual
├── timestamp               # Momento da emissao
├── reavaliacao             # True se e re-avaliacao
├── primeiro_minuto         # Minuto do primeiro alerta
├── primeiro_escanteios     # Corners no primeiro alerta
├── primeiro_linha          # Linha no primeiro alerta
├── primeiro_projecao       # Projecao no primeiro alerta
├── primeiro_edge           # Edge no primeiro alerta
└── primeiro_score          # Score no primeiro alerta
```

### 4.3 Arquivos JSON de Estado

| Arquivo | Conteudo | Atualizado |
|---------|----------|------------|
| `data/live_state.json` | Jogos ao vivo por fase, ciclo, polling stats | A cada ciclo |
| `data/upcoming_games.json` | Agenda do dia com countdown | A cada refresh |
| `data/audit_state.json` | Funil de analise do ultimo ciclo | A cada ciclo |

---

## 5. Loop Principal do Robo

**Arquivo:** `main.py` — classe `CornerPressureElite`

### 5.1 Inicializacao

```
1. Verifica API_FOOTBALL_KEY
2. Inicializa banco de dados (SQLite)
3. Carrega ligas ativas do banco
4. Inicializa thresholds
5. Conecta ao WAHA (WhatsApp)
6. Verifica status da API-Football (plano, requisicoes usadas)
7. Envia status inicial via WhatsApp
8. Inicia loop principal
```

### 5.2 Ciclo do Loop

```
LOOP:
  ┌─ Buscar agenda do dia (1 req, cacheia por dia)
  │
  ├─ Calcular minutos ate proximo jogo
  │
  ├─ Se proximo jogo > 15 min ─────────────────────────────┐
  │    Modo idle (sleep progressivo):                       │
  │    > 120 min: dorme 2h                                  │
  │    60-120 min: dorme 1h                                 │
  │    30-60 min: dorme 15min                               │
  │    15-30 min: dorme 5min                                │
  │    Atualiza agenda se refresh_schedule=True              │
  │    Verifica resultados pendentes                         │
  │    Verifica resumo diario e alertas pre-jogo             │
  │    continue ───────────────────────────────────────────>┘
  │
  ├─ Modo ativo (jogo em < 15 min ou ao vivo):
  │    1. Buscar jogos ao vivo (1 req global, filtra 13 ligas)
  │    2. Classificar cada jogo por fase:
  │       - pre_janela (0-50 min, sem early trigger)
  │       - na_janela (50-90 min OU 7+ corners antes de 50)
  │       - pos_janela (90+ min)
  │    3. Filtrar por adaptive_polling.should_poll()
  │    4. Para cada jogo que deve ser analisado:
  │       a. Buscar estatisticas (1 req)
  │       b. Buscar odds ao vivo (1 req)
  │       c. Converter para JogoAoVivo (parse_fixture_to_jogo)
  │       d. Salvar snapshot no banco (para backtest)
  │       e. Executar decision_engine.avaliar(jogo)
  │       f. Se sinal gerado:
  │          - Primeiro alerta: enviar WhatsApp + salvar no DB
  │          - Re-avaliacao: enviar update WhatsApp + salvar
  │    5. Gerar relatorio de auditoria do ciclo
  │    6. Salvar live_state.json + audit_state.json
  │    7. Verificar resultados pendentes
  │    8. Verificar resumo diario e alertas
  │    9. Sleep POLLING_INTERVAL (60s)
  │
  └─ Tratar excecoes (log + enviar alerta de erro via WhatsApp)
```

### 5.3 Tarefas Agendadas

| Tarefa | Horario | Destino |
|--------|---------|---------|
| Resumo matinal (agenda do dia) | 08:00 UTC | Grupo + Updates + Admin |
| Alerta pre-jogo | 30 min antes | Grupo + Updates |
| Resumo diario (performance) | 23:00 UTC | Updates + Grupo |

---

## 6. Motor de Decisao

**Arquivo:** `engine/decision_engine.py`

O motor de decisao e o coracao do sistema. Recebe um `JogoAoVivo` e decide se emite sinal.

### 6.1 Pipeline de Decisao

```
JogoAoVivo
    │
    ├─ [1] Filtros Estruturais ──> BLOQUEADO? ──> return None
    │
    ├─ [2] Pressure Score ──> Score < 5? ──> return None
    │
    ├─ [3] Verificar Odds ──> Sem linha? ──> return None
    │
    ├─ [4] Projecao Hibrida
    │
    ├─ [5] Edge = Projecao - Linha
    │
    └─ [6] Decisao:
         Score >= 8 AND Edge >= 1.5 ──> SINAL PREMIUM
         Score >= 5 AND Edge >= 0.7 ──> SINAL NORMAL
         Senao ──> return None (Edge insuficiente)
```

### 6.2 Sistema de Auditoria

Cada ciclo rastreia:

```
Funil:
  total_analisados ──> passou_filtros ──> score_ok ──> edge_ok ──> sinais_emitidos

Breakdown de filtros:
  "Fora da janela": N
  "Poucos escanteios": N
  "Sem escanteio recente": N
  ...

Detalhes por jogo:
  descricao, liga, minuto, placar, todos os inputs, score, projecao, edge, status, motivo
```

O relatorio e logado a cada ciclo e salvo em `data/audit_state.json` para o dashboard.

---

## 7. Score Engine

**Arquivo:** `engine/score_engine.py`

### 7.1 Componentes (max 11 pontos)

| Componente | Condicao | Pontos | Fonte |
|-----------|----------|--------|-------|
| Ritmo de escanteios 10min | `est_10min >= 2` | **+3** | Estimado via rate |
| Escanteio recente 5min | `est_5min >= 1` | **+1** | Estimado via rate |
| Ataques perigosos (HIGH) | `rate >= 1.0/min` | **+3** | Total jogo / minuto |
| Ataques perigosos (MEDIO) | `rate >= 0.7/min` | **+2** | Total jogo / minuto |
| Ataques perigosos (BAIXO) | `rate >= 0.4/min` | **+1** | Total jogo / minuto |
| Time perdendo por 1 gol | `diferenca_gols == 1` | **+2** | Placar |
| Posse dominante | `posse >= 60%` | **+1** | % do jogo |
| Finalizacoes (HIGH) | `rate >= 0.10/min` | **+1** | Total jogo / minuto |

### 7.2 Thresholds de Taxa

**Ataques perigosos** (tipico: 40-80 ataques em 90 min = 0.44-0.89/min):

| Faixa | Rate | Equivalente | Pontos |
|-------|------|-------------|--------|
| HIGH | >= 1.0/min | 60+ em 60min | +3 |
| MEDIO | >= 0.7/min | 42+ em 60min | +2 |
| BAIXO | >= 0.4/min | 24+ em 60min | +1 |
| INATIVO | < 0.4/min | < 24 em 60min | 0 |

**Finalizacoes** (tipico: 4-12 chutes no gol em 90 min):

| Faixa | Rate | Equivalente | Pontos |
|-------|------|-------------|--------|
| HIGH | >= 0.10/min | 6+ em 60min | +1 |
| BAIXO | < 0.10/min | < 6 em 60min | 0 |

### 7.3 Cenarios Tipicos

| Cenario | Corners | Score | Motivo |
|---------|---------|-------|--------|
| Jogo com muita pressao, perdendo por 1 | 8 em 60min | 8-11 | Todos componentes positivos |
| Jogo movimentado, empate | 6 em 60min | 5-7 | Sem bonus "perdendo" |
| Jogo morno, pouca atividade | 3 em 70min | 1-3 | Rate baixo, poucos ataques |
| Jogo com muitos corners, 0x0 | 10 em 55min | 6-8 | Bom rate mas sem "perdendo" |

---

## 8. Projection Engine

**Arquivo:** `engine/projection_engine.py`

### 8.1 Formula

```
Projecao = Ritmo_Base + Ajuste_Pressao + Ajuste_Historico
```

**Ritmo Base** — Projecao linear do ritmo atual:
```
ritmo_por_minuto = escanteios_total / minuto
ritmo_base = ritmo_por_minuto × 95
```

**Ajuste de Pressao** — Bonus por score alto:
```
ajuste_pressao = pressure_score × 0.25
```

**Ajuste Historico** — Bonus para ligas com media alta:
```
if media_historica > 10.5:
    ajuste_historico = 0.5
else:
    ajuste_historico = 0.0
```

### 8.2 Exemplos

| Jogo | Corners | Min | Rate | Score | Media | Projecao |
|------|---------|-----|------|-------|-------|----------|
| 8 corners em 65min | 8 | 65 | 0.123 | 7 | 10.3 | 11.69 + 1.75 + 0 = **13.44** |
| 10 corners em 60min | 10 | 60 | 0.167 | 9 | 11.2 | 15.83 + 2.25 + 0.5 = **18.58** |
| 4 corners em 55min | 4 | 55 | 0.073 | 5 | 9.8 | 6.91 + 1.25 + 0 = **8.16** |

### 8.3 Edge

```
Edge = Projecao - Linha_de_Mercado
```

| Tipo Sinal | Score Minimo | Edge Minimo |
|-----------|-------------|-------------|
| NORMAL | 5 | 0.7 |
| PREMIUM | 8 | 1.5 |

---

## 9. Filtros Estruturais

**Arquivo:** `engine/decision_engine.py` — metodo `_verificar_filtros()`

Os filtros sao aplicados ANTES do calculo de score/projecao para economizar processamento.

### 9.1 Lista de Filtros

| # | Filtro | Condicao de Bloqueio | Motivo |
|---|--------|---------------------|--------|
| 1 | Janela de monitoramento | `minuto < 50` E `corners < 7` | Fora da janela (muito cedo) |
| 2 | Goleada no 1T | `minuto <= 45` E `dif_gols >= 3` | Jogo morto no primeiro tempo |
| 3 | Diferenca de gols | `dif_gols > 3` (qualquer momento) | Goleada, sem incentivo para corners |
| 4 | Minimo de escanteios | `corners_total < 3` | Poucos escanteios, jogo sem ritmo |
| 5 | Escanteio recente | `est_5min < 1` | Sem atividade recente de corners |
| 6 | Jogo morno 0x0 | `placar == 0-0` E `min >= 60` E `corners < 7` | Empate sem gols, jogo travado |
| 7 | Time sem escanteio | `min > 45` E (`esc_casa == 0` OU `esc_fora == 0`) | Um time nao esta pressionando |

### 9.2 Excecao: Early Trigger

Se um jogo tem **7+ escanteios antes do minuto 50**, ele entra na janela de analise antecipadamente (bypassa o filtro 1). Isso captura jogos com ritmo muito alto no primeiro tempo.

### 9.3 Filtros Pos-Score

Alem dos filtros estruturais, existem mais dois gates:

| Gate | Condicao | Resultado |
|------|----------|-----------|
| Score | `score < MIN_SCORE_NORMAL (5)` | Descartado |
| Odds | `linha_atual <= 0` | Descartado (sem mercado disponivel) |

---

## 10. Polling Adaptativo

**Arquivo:** `utils/adaptive_polling.py`

O sistema usa intervalos de polling variaveis por fase do jogo para economizar requisicoes da API.

### 10.1 Intervalos por Fase

| Fase | Minutos | Intervalo | Reqs/hora |
|------|---------|-----------|-----------|
| Primeiro tempo (0-30) | 0-30 | 300s (5min) | 12 |
| Pre-janela (31-50) | 31-50 | 180s (3min) | 20 |
| Pre-janela + early (31-50, 7+ esc) | 31-50 | 60s (1min) | 60 |
| Janela de analise (50-90) | 50-90 | 30s | 120 |
| Reta final (90+) | 90+ | 30s | 120 |

### 10.2 Idle Scaling (sem jogos ao vivo)

| Distancia do proximo jogo | Intervalo |
|---------------------------|-----------|
| Sem jogos hoje | 2h |
| > 120 min | 2h |
| 60-120 min | 1h |
| 30-60 min | 15min |
| 15-30 min | 5min |
| < 15 min | 60s (polling normal) |

### 10.3 Economia

O sistema rastreia a economia de requisicoes:
```
Total jogos ao vivo: 7
Jogos processados: 3
Economia: 57% das requisicoes economizadas
```

---

## 11. Rate Limiter

**Arquivo:** `utils/rate_limiter.py`

### 11.1 Limites

| Limite | Valor | Janela |
|--------|-------|--------|
| Diario | 100 requisicoes | Resetado pela API (nao local) |
| Por minuto | 50 requisicoes | Janela deslizante de 60s |

### 11.2 Sincronizacao

O rate limiter sincroniza com o uso real reportado pela API-Football no endpoint `/status`. Isso evita drift entre o contador local e o uso real.

### 11.3 Custo por Ciclo

| Operacao | Requisicoes | Frequencia |
|----------|-------------|-----------|
| Buscar jogos ao vivo | 1 | A cada ciclo (60s) |
| Estatisticas por jogo | 1 | Por jogo analisado |
| Odds ao vivo por jogo | 1 | Por jogo analisado |
| Agenda do dia | 1 por liga | 1x por dia |
| Verificar resultado | 1-2 | Por sinal pendente |

**Estimativa com 5 jogos na janela:** ~11 req/ciclo = ~660 req/hora

---

## 12. Integracao API-Football

**Arquivo:** `data/api_client.py`

### 12.1 Endpoints Utilizados

| Endpoint | Metodo | Uso | Reqs |
|----------|--------|-----|------|
| `fixtures?live=all` | GET | Todos os jogos ao vivo, filtro local | 1/ciclo |
| `fixtures/statistics?fixture={id}` | GET | Estatisticas completas do jogo | 1/jogo |
| `odds/live?fixture={id}` | GET | Odds in-play de escanteios | 1/jogo |
| `fixtures?date={d}&league={id}&season={s}` | GET | Agenda diaria por liga | 1/liga/dia |
| `fixtures?id={id}` | GET | Resultado final | 1/sinal |
| `fixtures/events?fixture={id}` | GET | Eventos (fallback corners) | 1/sinal |
| `fixtures/status` | GET | Status da conta (nao conta) | periodico |

### 12.2 Dados Retornados por Jogo

**Estatisticas** (`statistics` endpoint):

| Campo | Tipo | Observacao |
|-------|------|-----------|
| Corner Kicks | int | Por time, TOTAL do jogo |
| Dangerous Attacks | int | Por time, TOTAL do jogo |
| Ball Possession | "XX%" | Por time, % geral |
| Shots on Goal | int | Por time, TOTAL do jogo |

### 12.3 Seasons por Liga

Ligas europeias usam `season=2025` (calendario jul-jun). Ligas sul-americanas usam `season=2026` (calendario jan-dez). O sistema mantem um `season_map` extraido de `LIGAS_MONITORADAS`.

### 12.4 Parsing de Odds

O sistema busca odds de escanteios nesta ordem:
1. `/odds/live` — odds in-play (preferencial)
2. `/odds` — odds pre-match (fallback)

Filtra pelo mercado "Corners Over/Under" e extrai:
- `linha`: linha central (ex: 10.5)
- `odd_over`: odd do Over (ex: 1.85)
- `odd_under`: odd do Under

---

## 13. Notificacoes WhatsApp

### 13.1 Arquitetura

```
NotificationManager
├── WAHAClient (HTTP client para WAHA API)
├── MessageFormatter (formata mensagens)
├── Canais:
│   ├── group_id: Grupo principal (sinais)
│   ├── admin_chat_id: Admin (erros/status)
│   └── updates_chat_id: Updates (tudo)
```

**Arquivo WAHA Client:** `notifier/whatsapp_client.py`
**Arquivo Notification Manager:** `notifier/notification_manager.py`
**Arquivo Message Formatter:** `notifier/message_formatter.py`

### 13.2 Tipos de Mensagem

#### Sinal de Entrada

```
🔥 OVER ESCANTEIOS – PREMIUM

🏆 Liga: La Liga
⚽ Jogo: FC Barcelona vs Real Madrid
⏱️ Minuto: 62'
📊 Placar: 1-0

📈 ANÁLISE:
Escanteios atuais: 8
Linha (mercado): 10.5
Projeção (CPES): 14.4
Edge: +3.94

🔥 Pressure Score: 11/10

💰 MERCADO (Odds ao vivo):
Over: 1.85x
Linha: 10.5
Stake sugerida: 1u

⚠️ Tipo: PREMIUM ENTRADA 🚀
⏰ 15:32:10
```

**Destino:** Grupo + Updates

#### Re-avaliacao

```
🔄 RE-EVALUATION – SCENARIO IMPROVED

🏆 Liga: La Liga
⚽ Jogo: FC Barcelona vs Real Madrid
⏱️ Minuto: 68' (Alerta inicial: 62')

📈 MUDANÇAS:
Escanteios: 8 → 10
Linha: 10.5 → 10.5
Projeção: 14.4 → 16.2
Edge: +3.94 → +5.70
Score: 11 → 11

💡 Cenário melhorou significativamente
⚠️ Re-avaliação informativa apenas
   (Sem sugestão de stake adicional)
⏰ 15:38:22
```

**Destino:** Grupo + Updates

#### Resultados Finais

```
📊 RESULTADOS FINAIS

✅ FC Barcelona vs Real Madrid
   12 escanteios vs linha 10.5
   Odd 1.85x → +0.85u

❌ Bayern vs Dortmund
   9 escanteios vs linha 10.5
   Odd 1.90x → -1.00u

📈 RESUMO:
✅ Greens: 1
❌ Reds: 1
💰 ROI: -0.15u
```

**Destino:** Grupo + Updates

#### Resumo Matinal (Agenda)

```
📅 AGENDA DO DIA - CPES

⚽ 8 jogos programados:

🏆 La Liga
  ⏰ 17:00 - Girona vs Barcelona

🏆 Serie A
  ⏰ 16:45 - Cagliari vs Lecce

🏆 Liga Portugal
  ⏰ 17:15 - Rio Ave vs Moreirense
...

🔍 Sistema monitorando automaticamente.
```

**Destino:** Grupo + Updates + Admin

#### Alerta Pre-Jogo

```
⚽ JOGO EM BREVE!

🏆 La Liga
⏰ 17:00 - Girona vs Barcelona
   Começa em 28 minutos

🔍 Monitoramento ativo.
```

**Destino:** Grupo + Updates

#### Status do Sistema

```
🤖 STATUS DO SISTEMA

🟢 Online
📡 API Football: 398/7500
👁️ Jogos monitorados: 3
📊 Sinais hoje: 1
⏰ Última atualização: 15:32:10
```

**Destino:** Updates + Admin

#### Resumo Diario (Performance)

```
📊 RESUMO DIÁRIO - CPES

📈 PERFORMANCE:
Total de sinais: 3
✅ Greens: 2
❌ Reds: 1
📊 Winrate: 66.7%
💰 ROI: +0.70u
```

**Destino:** Updates + Grupo

### 13.3 Comandos Admin via WhatsApp

O sistema aceita comandos via webhook do WAHA. Admin envia mensagem e recebe resposta:

| Comando | Descricao |
|---------|-----------|
| `/status` ou `/saude` | Status do sistema |
| `/jogos` ou `/agenda` | Proximos jogos |
| `/stats` ou `/resultado` | Performance |
| `/help` ou `/?` | Lista de comandos |

---

## 14. Dashboard

**Diretorio:** `dashboard/`

### 14.1 Paineis

O dashboard e uma pagina Next.js que consulta a API a cada 10 segundos.

#### Painel 1: Metricas Principais (MetricCard)

```
┌──────────┬──────────┬──────────┬──────────┬──────────┐
│  Total   │  Greens  │   Reds   │ Winrate  │   ROI    │
│    3     │    2     │    1     │  66.7%   │ +0.70u   │
└──────────┴──────────┴──────────┴──────────┴──────────┘
```

#### Painel 2: Status do Sistema (SystemStatus)

```
Ciclo: #42
API: 398/7500 requests
Status: Monitorando 5 jogos ao vivo
Próximo check: 60s
```

#### Painel 3: Jogos ao Vivo (LiveGamesSection)

Jogos separados por fase com cores:

```
🟡 PRE-JANELA (3)
  Leipzig vs Wolfsburg | Min 34 | 4 esc | 0-0

🟢 NA JANELA (2)
  Rayo vs Atletico | Min 82 | 11 esc | 3-0
  Nacional vs FC Porto | Min 65 | 10 esc | 0-1

🔵 POS-JANELA (1)
  U. Concepcion vs Concepcion | Min 90 | 9 esc | 2-1
```

#### Painel 4: Proximos Jogos (UpcomingGames)

```
Cagliari vs Lecce | 16:45 | em 2h15
Girona vs Barcelona | 17:00 | em 2h30
Rio Ave vs Moreirense | 17:15 | em 2h45
```

#### Painel 5: Sinais Recentes (RecentSignals)

```
PREMIUM | Rayo vs Atletico | Score 9 | Edge +2.3 | 15:32
NORMAL  | Nacional vs Porto | Score 6 | Edge +1.1 | 15:35
```

#### Painel 6: Polling Stats (PollingStats)

```
Fase              | Intervalo | Jogos
0-30 min          |    5min   |   2
31-50 min         |    3min   |   1
Janela (50-90)    |   30s     |   2
Reta final (90+)  |   30s     |   1
─────────────────────────────────────
Economia: 57% das requisições economizadas
```

#### Painel 7: Auditoria (AuditPanel)

```
FUNIL DE ANÁLISE:
Total analisados:  5
Passou filtros:    3
Score suficiente:  2
Edge suficiente:   1
SINAIS emitidos:   1 (1P + 0N)

MOTIVOS DE EXCLUSÃO:
Fora da janela: 2
Score insuficiente: 1
Edge insuficiente: 1
```

#### Painel 8: Ligas Monitoradas (MonitoredLeagues)

Lista de 13 ligas com toggle on/off.

#### Painel 9: Logs do Sistema (SystemLogs)

Ultimas 50 linhas de log em formato terminal.

### 14.2 Settings Page

Pagina `/settings` permite:
- Ativar/desativar ligas individuais
- Ajustar thresholds (min_score, min_edge) via API

---

## 15. API Server (FastAPI)

**Arquivo:** `api_server.py`

### 15.1 Endpoints

| Metodo | Path | Descricao |
|--------|------|-----------|
| GET | `/` | Info do sistema |
| GET | `/api/health` | Health check |
| GET | `/api/stats` | Performance (total, greens, reds, winrate, roi) |
| GET | `/api/signals/recent?limit=10` | Ultimos N sinais |
| GET | `/api/status` | Status do sistema (log parsing) |
| GET | `/api/logs?lines=50` | Ultimas N linhas de log |
| GET | `/api/polling-stats` | Intervalos de polling por fase |
| GET | `/api/live-games` | Jogos ao vivo por fase (live_state.json) |
| GET | `/api/upcoming-games` | Agenda com countdown |
| GET | `/api/config/leagues` | Ligas ativas |
| POST | `/api/config/leagues` | Ativar/desativar ligas |
| GET | `/api/config/thresholds` | Thresholds atuais |
| POST | `/api/config/thresholds` | Atualizar thresholds |
| GET | `/api/audit` | Dados completos de auditoria |
| GET | `/api/dashboard` | Todos os dados em uma chamada |
| POST | `/api/webhook/whatsapp` | Webhook WAHA (comandos admin) |

### 15.2 Endpoint `/api/dashboard`

Retorna tudo que o dashboard precisa em uma unica requisicao:

```json
{
  "stats": { "total": 3, "greens": 2, "reds": 1, "winrate": 66.7, "roi_total": 0.70 },
  "recent_signals": [...],
  "live_games": { "pre_janela": [...], "na_janela": [...], "pos_janela": [...] },
  "upcoming_games": [...],
  "polling_stats": { "jogos_monitorados": 5, "economia_pct": 57.0 },
  "status": { "ciclo": 42, "api_used": 398, "api_limit": 7500 },
  "audit": { "funil": {...}, "filtros_breakdown": {...}, "jogos": [...] },
  "leagues": [...]
}
```

---

## 16. Banco de Dados

**Arquivo:** `storage/database.py`
**Caminho:** `data/cpes.db` (SQLite)

### 16.1 Tabela `sinais`

Registra cada sinal emitido e seu resultado.

| Coluna | Tipo | Descricao |
|--------|------|-----------|
| id | INTEGER PK | Auto-increment |
| timestamp | DATETIME | Momento da emissao |
| liga_id | INTEGER | ID da liga |
| liga_nome | VARCHAR | Nome da liga |
| jogo_id | INTEGER | fixture_id da API-Football |
| jogo_descricao | VARCHAR | "Time A vs Time B" |
| minuto | INTEGER | Minuto do sinal |
| placar | VARCHAR | "1-0" |
| escanteios_total | INTEGER | Corners no momento |
| linha | DECIMAL | Linha de mercado |
| odd | DECIMAL | Odd do Over |
| projecao | DECIMAL | Corners projetados |
| edge | DECIMAL | projecao - linha |
| pressure_score | INTEGER | Score calculado |
| tipo_sinal | VARCHAR(20) | "NORMAL" ou "PREMIUM" |
| reavaliacao | BOOLEAN | Se e re-avaliacao |
| resultado | VARCHAR(10) | "GREEN", "RED", "EXPIRADO", NULL |
| escanteios_final | INTEGER | Corners totais finais |
| roi | DECIMAL | Retorno (+odd-1 ou -1) |

### 16.2 Tabela `detalhes_jogo`

Dados extras do momento do sinal.

| Coluna | Tipo |
|--------|------|
| sinal_id | FK -> sinais |
| ataques_perigosos | INTEGER |
| finalizacoes | INTEGER |
| posse_time_casa | DECIMAL |
| posse_time_fora | DECIMAL |
| escanteios_time_casa | INTEGER |
| escanteios_time_fora | INTEGER |
| media_historica | DECIMAL |

### 16.3 Tabela `ligas_config`

| Coluna | Tipo | Descricao |
|--------|------|-----------|
| liga_id | INTEGER PK | ID da liga |
| ativa | BOOLEAN | Ativa ou desativada |

### 16.4 Tabela `thresholds_config`

| Coluna | Tipo | Descricao |
|--------|------|-----------|
| chave | VARCHAR(50) PK | Nome do parametro |
| valor | DECIMAL | Valor atual |
| descricao | VARCHAR(200) | Descricao |

Chaves: `min_score_normal`, `min_score_premium`, `min_edge_normal`, `min_edge_premium`

### 16.5 Tabela `snapshots` (Backtest)

Salva estado completo de cada jogo analisado para replay posterior.

| Coluna | Tipo | Descricao |
|--------|------|-----------|
| id | INTEGER PK | Auto-increment |
| timestamp | DATETIME | Momento do snapshot |
| fixture_id | INTEGER | fixture_id |
| liga_id, liga_nome | — | Liga |
| time_casa, time_fora | VARCHAR | Times |
| minuto | INTEGER | Minuto |
| placar_casa, placar_fora | INTEGER | Placar |
| escanteios_total/casa/fora | INTEGER | Corners |
| escanteios_ultimos_10min/5min | INTEGER | Estimados |
| ataques_perigosos | INTEGER | Total |
| posse_dominante | DECIMAL | % |
| finalizacoes | INTEGER | Total |
| media_historica | DECIMAL | Liga avg |
| linha_atual, odd_atual | DECIMAL | Mercado |
| corners_final | INTEGER | Preenchido apos fim |
| resultado_final | VARCHAR | GREEN/RED |

### 16.6 Queries Principais

| Metodo | Descricao |
|--------|-----------|
| `get_estatisticas()` | Total, greens, reds, winrate, roi, pendentes |
| `registrar_sinal(sinal)` | Salva novo sinal + detalhes |
| `get_sinais_pendentes()` | Sinais < 24h sem resultado |
| `atualizar_resultado(jogo_id, resultado, escs, roi)` | Preenche resultado |
| `expirar_sinais_antigos()` | Marca > 24h como EXPIRADO |
| `salvar_snapshot(jogo)` | Salva estado para backtest |
| `get_ligas_ativas()` | IDs de ligas ativas |
| `set_ligas_ativas(ids)` | Atualiza ligas |
| `get_thresholds()` / `set_thresholds()` | CRUD thresholds |

---

## 17. Backtest

**Diretorio:** `corner-pressure-elite/backtest/`

### 17.1 Comandos

```bash
python -m backtest status                     # Dados coletados
python -m backtest simulate                   # Roda com config atual
python -m backtest simulate --min-score 5     # Parametros custom
python -m backtest optimize                   # Grid search (top 5)
python -m backtest report                     # Gera relatorio .md
```

### 17.2 Simulador

O simulador:
1. Carrega snapshots do banco de dados
2. Reconstroi `JogoAoVivo` de cada snapshot
3. Roda `decision_engine.avaliar()` com parametros customizados
4. Calcula resultados: greens, reds, winrate, roi, drawdown

### 17.3 Otimizacao

Grid search sobre:
- `min_score`: [4, 5, 6, 7, 8]
- `min_edge`: [0.5, 0.7, 0.8, 1.0, 1.2, 1.5]

Retorna top 5 combinacoes por ROI com winrate minimo.

### 17.4 Resultado (BacktestRun)

```
BacktestRun
├── sinais: int                  # Total de sinais emitidos
├── sinais_com_resultado: int    # Sinais com resultado final
├── greens, reds: int            # Acertos e erros
├── winrate: float               # % de acerto
├── roi_total: float             # Soma de ROI
├── drawdown_maximo: float       # Maior sequencia de perda
├── resultados: List[BacktestResult]  # Detalhes por sinal
```

---

## 18. Re-avaliacao de Sinais

**Arquivo:** `engine/state_manager.py`

Apos o primeiro sinal, o sistema continua monitorando e pode emitir re-avaliacoes se o cenario **melhorou significativamente**.

### 18.1 Condicoes para Re-avaliacao

Todas devem ser atendidas:

| Condicao | Valor |
|----------|-------|
| Intervalo minimo | 3 minutos desde ultimo alerta |
| Linha mudou OU Edge aumentou | `edge_delta >= 0.7` |
| OU Score aumentou | `score_delta >= 1` |

### 18.2 Dados Comparativos

A re-avaliacao inclui dados do primeiro alerta para comparacao:
- Minuto: 62' → 68'
- Corners: 8 → 10
- Projecao: 14.4 → 16.2
- Edge: +3.94 → +5.70

---

## 19. Verificacao de Resultados

**Arquivo:** `main.py` — metodo `_verificar_resultados()`

### 19.1 Fluxo

```
1. Buscar sinais pendentes (< 24h sem resultado)
2. Filtrar: so verificar sinais > 2h (jogo provavelmente encerrado)
3. Para cada sinal:
   a. Buscar resultado final da API (corners totais)
   b. Comparar com linha de aposta:
      - corners_final > linha → GREEN
      - corners_final <= linha → RED
   c. Calcular ROI:
      - GREEN: odd - 1
      - RED: -1
   d. Atualizar banco de dados
4. Enviar resumo via WhatsApp
```

### 19.2 Expiracao

Sinais com mais de 24h sem resultado sao marcados como `EXPIRADO` automaticamente.

---

## 20. Ligas Monitoradas

### 20.1 Tabela Completa

| ID | Liga | Pais | Media Corners | Season |
|----|------|------|---------------|--------|
| 39 | Premier League | England | 10.8 | 2025 |
| 78 | Bundesliga | Germany | 11.2 | 2025 |
| 135 | Serie A | Italy | 10.5 | 2025 |
| 140 | La Liga | Spain | 10.3 | 2025 |
| 88 | Eredivisie | Netherlands | 10.6 | 2025 |
| 94 | Liga Portugal | Portugal | 10.0 | 2025 |
| 71 | Brasileirao A | Brazil | 9.8 | 2026 |
| 72 | Brasileirao B | Brazil | 9.5 | 2026 |
| 128 | Liga Prof. Argentina | Argentina | 10.2 | 2026 |

### 20.2 Gerenciamento

Ligas podem ser ativadas/desativadas via:
- Dashboard (pagina Settings)
- API: `POST /api/config/leagues`
- Banco de dados (tabela `ligas_config`)

---

## 21. Parametros Tuneaveis

### 21.1 Parametros Atuais (config.py)

| Parametro | Valor | Descricao |
|-----------|-------|-----------|
| `POLLING_INTERVAL` | 60s | Intervalo entre ciclos |
| `MINUTO_INICIO` | 50 | Inicio da janela de analise |
| `MINUTO_FIM` | 90 | Fim da janela |
| `ESCANTEIOS_EARLY_WINDOW` | 7 | Early trigger (corners) |
| `MIN_ESCANTEIOS_TOTAL` | 3 | Minimo de corners para analise |
| `MIN_ESCANTEIOS_5MIN` | 1 | Minimo de corners recentes (est.) |
| `MIN_ESCANTEIOS_JOGO_MORNO` | 7 | Minimo em jogo 0x0 apos min 60 |
| `MAX_DIFERENCA_GOLS` | 3 | Bloqueia goleada |
| `MAX_DIFERENCA_GOLS_1T` | 3 | Bloqueia goleada no 1T |
| `MIN_SCORE_NORMAL` | 5 | Score minimo sinal NORMAL |
| `MIN_SCORE_PREMIUM` | 8 | Score minimo sinal PREMIUM |
| `MIN_EDGE_NORMAL` | 0.7 | Edge minimo sinal NORMAL |
| `MIN_EDGE_PREMIUM` | 1.5 | Edge minimo sinal PREMIUM |
| `PROJECAO_MINUTO_TOTAL` | 95 | Projecao ate 95 min |
| `AJUSTE_PRESSAO_FATOR` | 0.25 | Score × 0.25 na projecao |
| `AJUSTE_HISTORICO_THRESHOLD` | 10.5 | Liga avg para bonus |
| `AJUSTE_HISTORICO_VALOR` | 0.5 | Bonus por liga alta |
| `REAVALIACAO_MIN_INTERVALO` | 3 min | Min entre re-alertas |
| `REAVALIACAO_EDGE_DELTA` | 0.7 | Delta edge para re-alerta |
| `REAVALIACAO_SCORE_DELTA` | 1 | Delta score para re-alerta |
| `API_DAILY_LIMIT` | 100 | Limite diario de requisicoes |

### 21.2 Parametros Ajustaveis via Dashboard

Via `POST /api/config/thresholds`:
- `min_score_normal`
- `min_score_premium`
- `min_edge_normal`
- `min_edge_premium`

---

## 22. Arvore de Arquivos

```
cornerpressureelite/
├── CLAUDE.md                              # Instrucoes para AI
├── docker-compose.yml                     # Orquestracao de containers
├── start_all.sh                           # Script para subir tudo
├── kill_all.sh                            # Script para parar tudo
│
├── corner-pressure-elite/                 # Backend Python
│   ├── Dockerfile                         # Imagem Python 3.12-slim
│   ├── requirements.txt                   # Dependencias
│   ├── .env                               # Variaveis de ambiente (gitignore)
│   ├── config.py                          # Todos os parametros
│   ├── main.py                            # Loop principal do robo
│   ├── api_server.py                      # FastAPI + webhooks
│   ├── data_reader.py                     # Caminhos de JSONs + leitura
│   │
│   ├── engine/                            # Logica de analise
│   │   ├── score_engine.py                # Pressure Score (0-11)
│   │   ├── decision_engine.py             # Filtros + decisao + auditoria
│   │   ├── projection_engine.py           # Projecao hibrida de corners
│   │   └── state_manager.py              # Re-avaliacao de sinais
│   │
│   ├── data/                              # Dados e modelos
│   │   ├── api_client.py                  # Client API-Football
│   │   ├── models.py                      # JogoAoVivo, Sinal, etc.
│   │   ├── cpes.db                        # Banco SQLite
│   │   ├── live_state.json                # Estado ao vivo (por fase)
│   │   ├── upcoming_games.json            # Agenda formatada
│   │   └── audit_state.json               # Auditoria do ciclo
│   │
│   ├── notifier/                          # WhatsApp
│   │   ├── whatsapp_client.py             # WAHA HTTP client
│   │   ├── notification_manager.py        # Despacho de mensagens
│   │   ├── message_formatter.py           # Formatacao das mensagens
│   │   └── waha_manager.py               # Helpers WAHA
│   │
│   ├── storage/                           # Persistencia
│   │   ├── database.py                    # SQLite ORM (aiosqlite)
│   │   └── logger.py                      # Setup de logging
│   │
│   ├── utils/                             # Utilitarios
│   │   ├── helpers.py                     # parse_fixture_to_jogo()
│   │   ├── rate_limiter.py                # Controle de requisicoes
│   │   └── adaptive_polling.py            # Intervalos por fase
│   │
│   ├── backtest/                          # Simulacao historica
│   │   ├── __main__.py                    # CLI (status/simulate/optimize/report)
│   │   ├── simulator.py                   # Motor de replay
│   │   └── reporter.py                    # Geracao de relatorio
│   │
│   ├── tests/                             # Testes
│   │   ├── test_backtest.py
│   │   ├── test_odds.py
│   │   └── test_resultados.py
│   │
│   └── logs/                              # Logs diarios
│       └── cpes_YYYYMMDD.log
│
├── dashboard/                             # Frontend Next.js
│   ├── Dockerfile                         # Build Next.js
│   ├── package.json
│   ├── next.config.ts                     # Proxy rewrite -> API:8000
│   ├── src/
│   │   ├── app/
│   │   │   ├── page.tsx                   # Pagina principal
│   │   │   ├── layout.tsx                 # Layout (dark theme)
│   │   │   ├── globals.css                # Estilos
│   │   │   └── settings/
│   │   │       └── page.tsx               # Configuracoes
│   │   ├── components/
│   │   │   ├── Header.tsx                 # Cabecalho + refresh
│   │   │   ├── MetricCard.tsx             # Cards de metricas
│   │   │   ├── LiveGames/
│   │   │   │   └── LiveGamesSection.tsx   # Jogos por fase
│   │   │   ├── RecentSignals.tsx          # Ultimos sinais
│   │   │   ├── MonitoredLeagues.tsx       # Ligas ativas
│   │   │   ├── SystemStatus.tsx           # Status do sistema
│   │   │   ├── SystemLogs.tsx             # Terminal de logs
│   │   │   ├── PollingStats.tsx           # Economia de polling
│   │   │   ├── AuditPanel.tsx             # Funil de analise
│   │   │   └── UpcomingGames.tsx          # Agenda com countdown
│   │   └── lib/
│   │       ├── api.ts                     # API client (fetch)
│   │       └── utils.ts                   # Utilidades
│   └── public/
│       └── _headers                       # Cloudflare headers
│
└── docs/                                  # Documentacao
    ├── README.md                          # Indice
    ├── architecture/                      # Specs tecnicas
    ├── analises/                          # Analises e estudos
    ├── resumo/                            # Resumos executivos
    ├── sprints/                           # Roadmap e planejamento
    ├── setup/                             # Deploy e configuracao
    └── changelog/                         # Registros de mudancas
```
