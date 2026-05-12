# Analise Completa do Sistema CPES

**Versao:** 1.0  
**Data:** 15/02/2026  
**Tipo:** Documento de analise tecnica e funcional

> **Nota (2026-05-11):** o dominio publico foi migrado de `odontoschultz.online` para `iqpressure.online`. Referencias ao dominio antigo neste doc refletem o estado anterior. Topologia atual em `CLAUDE.md` §9; ver tambem `docs/changelog/2026-05-11-migracao-dominio-iqpressure.md`.

---

## 1. Resumo Executivo

O **Corner Pressure Elite System (CPES)** e um motor automatizado de analise de escanteios ao vivo para apostas esportivas. O sistema monitora jogos em tempo real, calcula indicadores de pressao ofensiva e emite sinais quando identifica edge (vantagem) sobre a linha de escanteios do mercado Over/Under.

### Caracteristicas Principais

| Aspecto | Descricao |
|---------|-----------|
| **Objetivo** | Identificar jogos com pressao elevada que tendem a ultrapassar a linha de escanteios |
| **Mercado** | Escanteios totais (Over) em futebol ao vivo |
| **Fonte de dados** | API-Football v3 (api-sports.io) |
| **Notificacoes** | WhatsApp via WAHA (WhatsApp HTTP API) |
| **Economia** | Polling adaptativo reduz 70–90% das requisicoes em dias com muitos jogos |
| **Interfaces** | Dashboard web (Next.js), API REST (FastAPI), Monitor CLI |

---

## 2. Arquitetura do Sistema

### 2.1 Diagrama de Alto Nivel

```
                                    ┌─────────────────────────────────────────┐
                                    │         CORNER PRESSURE ELITE            │
                                    └─────────────────────────────────────────┘
                                                     │
     ┌──────────────────┐     ┌──────────────────────┴──────────────────────┐
     │  API-Football v3 │────▶│              Main Loop (main.py)             │
     │  (dados live)    │     │  • Agenda do dia  • Jogos ao vivo  • Stats   │
     └──────────────────┘     └──────────────────────┬──────────────────────┘
                                                     │
     ┌──────────────────┐     ┌──────────────────────┴──────────────────────┐
     │ Adaptive Polling │◀───▶│  Jogos por fase: pre_janela | na_janela |   │
     │ (economia 70-90%)│     │  pos_janela (reta final)                     │
     └──────────────────┘     └──────────────────────┬──────────────────────┘
                                                     │
     ┌──────────────────┐     ┌──────────────────────┴──────────────────────┐
     │ Decision Engine  │     │  Filtros → Pressure Score → Projecao → Edge  │
     │ (score_engine,   │◀───▶│  → Sinal NORMAL ou PREMIUM                   │
     │ projection_engine)     └──────────────────────┬──────────────────────┘
     └──────────────────┘                            │
                                                     ▼
     ┌──────────────────┐     ┌─────────────────────────────────────────────┐
     │ State Manager    │     │  Notification Manager → WAHA → WhatsApp      │
     │ (reavaliacao)    │     │  Database (SQLite) → live_state.json         │
     └──────────────────┘     └─────────────────────────────────────────────┘
                                                     │
     ┌──────────────────┐     ┌──────────────────────┴──────────────────────┐
     │ Dashboard Web    │◀───▶│  API Server (FastAPI :8000)                 │
     │ (Next.js :3001)  │     │  data_reader (stats, sinais, live_state)     │
     └──────────────────┘     └─────────────────────────────────────────────┘
```

### 2.2 Stack Tecnologico

| Camada | Tecnologia |
|--------|------------|
| Runtime | Python 3.12, asyncio |
| API Backend | FastAPI |
| HTTP Client | aiohttp |
| Banco | SQLite (aiosqlite) |
| Notificacoes | WAHA (WhatsApp HTTP API) |
| Dashboard | Next.js 16, React 19, TypeScript, Tailwind CSS 4 |
| Infra | Docker Compose, Cloudflare Tunnel |
| Dados externos | API-Football v3 |

---

## 3. Fluxo de Operacao

### 3.1 Ciclo Principal (~60 segundos)

1. **Agenda do dia** — Busca jogos programados (1 req por liga, 1x por dia)
2. **Sleep inteligente** — Se proximo jogo em &gt; 15 min, dorme ate 10 min antes
3. **Jogos ao vivo** — `get_live_fixtures()` (1 req para todas as ligas)
4. **Classificacao por fase**:
   - **Pre-janela** (0–50 min): Polling 5 min (0–30) ou 3 min (31–50); early trigger 7+ esc
   - **Na janela** (50–90 min): Polling 1 min
   - **Pos-janela** (90+): Polling 30 s (acrescimos)
5. **Analise seletiva** — Apenas jogos com `should_poll() == True`
6. **Decision Engine** — Filtros → Score → Projecao → Edge → Sinal
7. **Notificacao** — Primeiro sinal ou reavaliacao via WhatsApp
8. **Persistencia** — `live_state.json` (dashboard), SQLite (sinais)
9. **Resumo diario** — Enviado as 23:00 (configuravel)

### 3.2 Polling Adaptativo

| Fase | Intervalo | Descricao |
|------|-----------|-----------|
| 0–30 min | 5 min | Primeiro tempo inicial |
| 31–50 min | 3 min | Pre-janela |
| 31–50 min (7+ esc) | 1 min | **Early trigger** — entra na janela |
| 50–90 min | 1 min | Janela principal |
| 90+ min | 30 s | Acrescimos (critico) |

**Early trigger:** 7+ escanteios antes do min 50 → jogo passa a ser analisado a cada 1 min.

---

## 4. Componentes Detalhados

### 4.1 Main (`main.py`)

- Classe `CornerPressureElite`: orquestra o sistema
- Inicializa: RateLimiter, APIFootballClient, DecisionEngine, StateManager, NotificationManager, AdaptivePolling
- Loop `_main_loop()`: agenda → jogos ao vivo → classificacao → analise → notificacao
- `_analisar_jogo()`: busca stats, converte para `JogoAoVivo`, avalia com DecisionEngine, registra sinal
- Sleep otimizado: 30 min se nenhum jogo restante; acorda 10 min antes do proximo jogo

### 4.2 API Client (`data/api_client.py`)

- `APIFootballClient`: cliente assincrono para API-Football v3
- Integracao com `RateLimiter` para controle de requisicoes
- Endpoints: `check_status`, `get_live_fixtures`, `get_today_schedule`, `get_statistics`, `get_events`, `get_fixture_by_id`
- Tratamento de 503 e respostas nao-JSON (manutencao API)
- `get_live_fixtures`: uma requisicao para todas as ligas (`league=39-78-71-...`)

### 4.3 Decision Engine (`engine/decision_engine.py`)

Fluxo sequencial: **Filtros → Pressure Score → Projecao → Edge → Decisao**

#### Filtros Estruturais (bloqueio)

| Filtro | Condicao | Motivo |
|--------|----------|--------|
| Janela | min &lt; 50 (exceto early 7+ esc) | Fora da janela |
| Goleada 1T | 3+ gols diff no 1T | Jogo morto |
| Diff gols | &gt; 3 | Desequilibrio |
| Escanteios total | &lt; 3 | Poucos dados |
| Escanteio 5 min | &lt; 1 | Sem atividade recente |
| Jogo morno | 0x0 apos 60 com &lt; 7 esc | Baixa dinamica |
| Time sem esc 1T | min &gt; 45 e um time com 0 esc | Jogo morto |

#### Matriz de Decisao

| Score | Edge | Resultado |
|-------|------|-----------|
| &lt; 6 | Qualquer | Sem sinal |
| 6–7 | &lt; 0,8 | Sem sinal |
| 6–7 | ≥ 0,8 | **NORMAL** |
| ≥ 8 | &lt; 1,5 | NORMAL (se edge ≥ 0,8) |
| ≥ 8 | ≥ 1,5 | **PREMIUM** |

### 4.4 Score Engine (`engine/score_engine.py`)

**Pressure Score (0–10):**

| Indicador | Condicao | Pontos |
|-----------|----------|--------|
| Escanteios ultimos 10 min | ≥ 2 | +3 |
| Escanteios ultimos 5 min | ≥ 1 | +1 |
| Ataques perigosos 10 min | ≥ 3 | +2 |
| Time perdendo por 1 gol | Sim | +2 |
| Posse dominante | &gt; 50% | +1 |
| Finalizacoes recentes | ≥ 2 | +1 |

*Nota: API-Football retorna estatisticas agregadas do jogo; `escanteios_ultimos_10min` e `5min` dependem de eventos ou heuristica. A API nao oferece breakdown temporal nativo.*

### 4.5 Projection Engine (`engine/projection_engine.py`)

**Projecao Hibrida:**

```
Projecao = Ritmo base + Ajuste pressao + Ajuste historico
```

- **Ritmo base:** (escanteios / minuto) × 95
- **Ajuste pressao:** Pressure Score × 0,25
- **Ajuste historico:** +0,5 se media da liga &gt; 10,5

**Edge:** `Projecao - Linha atual`

### 4.6 State Manager (`engine/state_manager.py`)

- Controla alertas ja enviados por `jogo_id`
- **Reavaliacao:** envia novo alerta se:
  - intervalo ≥ 3 min desde ultimo
  - linha mudou **ou** edge aumentou ≥ 0,7 **ou** score aumentou ≥ 1
- Armazena dados do primeiro alerta para mensagem de reavaliacao

### 4.7 API Server (`api_server.py`)

- FastAPI na porta 8000
- Endpoints: `/api/stats`, `/api/signals/recent`, `/api/status`, `/api/logs`, `/api/polling-stats`, `/api/live-games`, `/api/config`, `/api/dashboard`
- CORS para localhost e odontoschultz.online
- `data_reader`: funcoes puras para ler SQLite, `live_state.json`, logs

### 4.8 Persistencia

- **SQLite** (`data/cpes.db`): tabela `sinais` com timestamp, jogo, score, projecao, edge, resultado, roi
- **live_state.json**: estado em tempo real (pre_janela, na_janela, pos_janela, ids_observados, polling_stats)

---

## 5. Modelos de Dados

### JogoAoVivo

| Campo | Tipo | Descricao |
|-------|------|-----------|
| id, liga_id, liga_nome | int, str | Identificacao |
| time_casa, time_fora | str | Times |
| placar_casa, placar_fora | int | Placar |
| minuto | int | Minuto atual |
| escanteios_total, casa, fora | int | Escanteios |
| linha_atual, odd_atual | float | Mercado (linha informada) |
| escanteios_ultimos_10min, 5min | int | Atividade recente |
| ataques_perigosos_ultimos_10min | int | Pressao |
| posse_ultimos_10min | float | Posse % |
| finalizacoes_recentes | int | Chutes a gol |
| media_historica_combinada | float | Media da liga |

### Sinal

| Campo | Tipo | Descricao |
|-------|------|-----------|
| tipo | str | NORMAL ou PREMIUM |
| jogo | JogoAoVivo | Snapshot do jogo |
| pressure_score, projecao, edge | int, float | Metricas |
| reavaliacao | bool | Se e atualizacao |
| primeiro_* | Optional | Dados do 1o alerta (reavaliacao) |

---

## 6. Configuracao (`config.py`)

| Parametro | Valor | Descricao |
|-----------|-------|-----------|
| MIN_SCORE_NORMAL | 6 | Score minimo sinal NORMAL |
| MIN_SCORE_PREMIUM | 8 | Score minimo sinal PREMIUM |
| MIN_EDGE_NORMAL | 0,8 | Edge minimo NORMAL |
| MIN_EDGE_PREMIUM | 1,5 | Edge minimo PREMIUM |
| MIN_ESCANTEIOS_TOTAL | 3 | Minimo de escanteios |
| MAX_DIFERENCA_GOLS | 3 | Bloqueia goleadas |
| JANELA_ANTECIPADA_INICIO | 50 | Minuto inicio janela |
| REAVALIACAO_MIN_INTERVALO | 3 | Min entre reavaliacoes |
| REAVALIACAO_EDGE_DELTA | 0,7 | Delta edge para reavaliar |
| PROJECAO_MINUTO_TOTAL | 95 | Minutos para projecao |
| AJUSTE_PRESSAO_FATOR | 0,25 | Peso do score na projecao |

### Ligas Monitoradas

| Liga | ID | Media esperada |
|------|----|----------------|
| Premier League | 39 | 10,8 |
| Bundesliga | 78 | 11,2 |
| Brasileirao A | 71 | 9,8 |
| Brasileirao B | 72 | 9,5 |
| Carioca A | 624 | 9,5 |
| Liga Profesional Argentina | 128 | 10,2 |
| Primera Division Chile | 265 | 10,0 |

---

## 7. Infraestrutura

### Portas

| Servico | Porta | URL |
|---------|-------|-----|
| WAHA | 3000 | http://localhost:3000 |
| Dashboard | 3001 | http://localhost:3001 |
| API | 8000 | http://localhost:8000 |

### Dominio (Cloudflare Tunnel)

- https://odontoschultz.online — Dashboard
- https://api.odontoschultz.online — API
- ssh.odontoschultz.online — SSH

### Variaveis de Ambiente

| Variavel | Descricao |
|----------|-----------|
| API_FOOTBALL_KEY | Chave API-Football (obrigatorio) |
| API_DAILY_LIMIT | Limite diario (default 100) |
| WAHA_URL | URL do WAHA |
| WHATSAPP_GROUP_ID | Grupo para sinais |
| WHATSAPP_ADMIN | Numero admin (erros/status) |
| DB_PATH | Caminho SQLite |
| DAILY_SUMMARY_TIME | Horario resumo (23:00) |

---

## 8. Pontos Fortes

| Aspecto | Descricao |
|---------|-----------|
| Economia de API | Polling adaptativo reduz 70–90% requisicoes |
| Modelo quantitativo | Score + projecao + edge bem definidos |
| Reavaliacao | Atualiza alertas quando condicoes evoluem |
| Interfaces multiplas | Dashboard, API REST, Monitor CLI |
| Integracao WhatsApp | Sinais diretos via WAHA |
| Sleep inteligente | Dorme entre jogos, acorda antes |
| Tratamento de erros | 503, rate limit, WAHA desconectado |

---

## 9. Limitacoes e Riscos

### Limitacoes Conhecidas

| Limitacao | Impacto | Mitigacao |
|-----------|---------|-----------|
| Linha do mercado | `linha_atual` informada manualmente; nao busca odds automaticamente | Evolucao: API de odds em tempo real |
| Escanteios 10/5 min | API retorna totais; sistema usa proxies (ex: ataques perigosos totais) | API-Football nao oferece breakdown temporal |
| Resultado do jogo | Atualizacao manual de GREEN/RED no banco | Evolucao: resultado automatico via API |
| Sem backtest | Parametros ajustados empiricamente | Evolucao: modulo de backtest |

### Riscos e Mitigacoes

| Risco | Mitigacao |
|-------|-----------|
| Limite diario API | Rate limiter, polling adaptativo, pausa ao atingir limite |
| API 503 | Tratamento de erro, retry no proximo ciclo |
| WAHA desconectado | Erro ao admin, sistema continua |
| Muitos jogos simultaneos | Polling escalona analise; economia por fase |

---

## 10. Evolucoes Futuras (Roadmap)

1. **Integracao com API de odds** — Buscar linha de escanteios em tempo real
2. **Resultado automatico** — Atualizar GREEN/RED via API apos o fim do jogo
3. **Backtest** — Calibracao de parametros com historico
4. **Mais ligas** — Filtros por liga ativa
5. **Dashboard avancado** — Graficos, filtros, export
6. **Metricas de latencia** — Tempo entre deteccao e envio do sinal

---

## 11. Referencias

- [Executive Analysis](executive-analysis.md) — Visao geral e fluxos
- [Decision Model](decision-model.md) — Detalhes do modelo de decisao
- [Changelog 2026-02-15](changelog/2026-02-15-strategy-tuning.md) — Ajuste de limiares
- [Full Spec V2 WAHA](../architecture/full-spec-v2-waha.md) — Especificacao tecnica completa

---

*Documento gerado com base na analise do codigo-fonte do CPES (fevereiro 2026).*
