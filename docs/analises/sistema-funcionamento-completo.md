# Sistema Completo - Como Funciona (CPES)

**Data:** 15 de Fevereiro de 2026  
**Versão:** 2.0 (Com WAHA, Dashboard, API)  
**Status:** Ativo em Produção

> **Nota (2026-05-11):** o domínio público foi migrado de `odontoschultz.online` para `iqpressure.online`. Referências ao domínio antigo neste doc refletem o estado anterior à migração. Topologia atual em `CLAUDE.md` §9; mudança detalhada em `docs/changelog/2026-05-11-migracao-dominio-iqpressure.md`.

---

## 1. Visão Geral

**Corner Pressure Elite System (CPES)** é um motor automatizado de análise de escanteios ao vivo que emite sinais de apostas esportivas em tempo real.

```
API-Football (coleta dados)
         ↓
    CPES Engine (análise)
         ↓
  Notificações WhatsApp
         ↓
    Dashboard Web
```

O sistema monitora ligas de futebol continuamente, avalia pressão ofensiva em tempo real e emite alertas quando detecta oportunidades de apostas.

---

## 2. Arquitetura de Alto Nível

### Camadas

```
┌─────────────────────────────────────┐
│    INTERFACE DO USUÁRIO             │
│  • Dashboard Web (Next.js)          │
│  • WhatsApp (Notificações)          │
└──────────────┬──────────────────────┘
               │
┌──────────────▼──────────────────────┐
│    CAMADA DE PROCESSAMENTO          │
│  • Motor de Análise (Python)        │
│  • Decision Engine                  │
│  • State Manager                    │
│  • Notifier                         │
└──────────────┬──────────────────────┘
               │
┌──────────────▼──────────────────────┐
│    CAMADA DE DADOS                  │
│  • API-Football (externa)           │
│  • Banco SQLite (local)             │
│  • WAHA API (WhatsApp)              │
└─────────────────────────────────────┘
```

### Portas

| Serviço | Porta | Tipo |
|---------|-------|------|
| WAHA (WhatsApp) | 3000 | Backend |
| FastAPI (CPES API) | 8000 | Backend |
| Next.js Dashboard | 3001 | Frontend |

### Estrutura de Diretórios

```
corner-pressure-elite/          # Backend Python
├── main.py                     # Robo principal (loop de monitoramento)
├── api_server.py               # API FastAPI
├── config.py                   # Configuracoes centralizadas
├── engine/
│   ├── decision_engine.py      # Motor de decisao (evalua sinais)
│   ├── score_engine.py         # Calcula Pressure Score
│   ├── projection_engine.py    # Projecao hibrida de escanteios
│   └── state_manager.py        # Gerencia estado/re-avaliacao
├── data/
│   ├── models.py               # Modelos de dados
│   ├── api_client.py           # Cliente da API-Football
│   ├── live_state.json         # Estado dos jogos ao vivo
│   └── upcoming_games.json     # Proximos jogos
├── notifier/
│   ├── whatsapp_client.py      # Cliente WAHA
│   ├── notification_manager.py # Gerenciador de notificacoes
│   └── message_formatter.py    # Formatacao de mensagens
├── storage/
│   ├── database.py             # SQLite
│   └── logger.py               # Logging
└── tests/                      # Testes

dashboard/                      # Frontend Next.js/TypeScript
├── src/
│   ├── app/                    # Pages (Next.js App Router)
│   ├── components/             # Componentes React
│   └── lib/api.ts              # Cliente HTTP (chamadas ao backend)
└── public/                     # Assets estaticos
```

---

## 3. Componentes Principais

### 3.1 Main Loop (main.py)

O robo principal executa em ciclos continuos:

**Ciclo de Execução:**

```python
asyncio.run(main())
    │
    ├─ CornerPressureElite() # Inicializa sistema
    │  ├─ APIFootballClient  # Acesso a API de futebol
    │  ├─ DecisionEngine     # Motor de decisao
    │  ├─ Database           # Persistencia
    │  └─ NotificationManager # Notificacoes
    │
    └─ run_cpes_loop()        # Loop infinito
       │
       ├─ [A cada POLLING_INTERVAL (60s)]
       │  ├─ Fetch upcoming_games (proximo jogo)
       │  ├─ GET fixtures em tempo real para ligas monitoradas
       │  ├─ Processar cada jogo:
       │  │  ├─ DecisionEngine.avaliar(jogo)
       │  │  ├─ Se sinal: notificar WhatsApp
       │  │  └─ Se re-avaliacao: atualizar sinal existente
       │  └─ Salvar estado em JSON (live_state.json)
       │
       ├─ [A cada STATUS_CHECK_INTERVAL (5 min)]
       │  └─ Log status: ciclos, rate limit, erros
       │
       └─ [Diariamente]
          └─ Resumo diario (stats) via WhatsApp
```

**Parametros Configuráveis (config.py):**

```python
POLLING_INTERVAL = 60              # Frequencia de verificacao
STATUS_CHECK_INTERVAL = 300        # Verificar status a cada 5 min
MINUTO_INICIO = 50                 # Inicio janela de monitoramento
MINUTO_FIM = 90                    # Fim janela (fim do regulamentar)
API_DAILY_LIMIT = 100              # Limite de requisicoes por dia
```

---

### 3.2 Decision Engine (engine/decision_engine.py)

Responsável por evaluar se deve emitir um sinal.

**Fluxo de Decisão:**

```
JogoAoVivo (entrada)
    │
    ├─ [1] Verificar Filtros Estruturais
    │   ├─ Janela de monitoramento (50-90 min)?
    │   ├─ Early window (7+ escanteios antes dos 50 min)?
    │   ├─ Goleada detectada (3+ gols de diferenca)?
    │   └─ Se bloqueado: RETORNA None
    │
    ├─ [2] Calcular Pressure Score
    │   ├─ Escanteios ultimos 10 min? (+3)
    │   ├─ Escanteio ultimos 5 min? (+1)
    │   ├─ Ataques perigosos ultimos 10 min? (+2)
    │   ├─ Time perdendo por 1? (+2)
    │   ├─ Posse dominante? (+1)
    │   └─ Finalizacoes recentes? (+1)
    │   
    │   [MAXIMA: ~10 pontos | MINIMO NORMAL: 6 | MINIMO PREMIUM: 8]
    │
    ├─ [3] Calcular Projeção Híbrida de Escanteios
    │   ├─ Taxa base (minutos restantes * media esperada)
    │   ├─ Ajuste por pressao ofensiva
    │   ├─ Ajuste por trend historico
    │   └─ Resultado: projecao final
    │
    ├─ [4] Calcular Edge
    │   └─ Edge = Projeção - Linha Atual
    │
    └─ [5] Decisão Final
        ├─ Se Score >= 8 E Edge >= 1.5: SINAL PREMIUM
        ├─ Elif Score >= 6 E Edge >= 0.8: SINAL NORMAL
        └─ Else: Sem sinal (descartar)
            │
            Sinal (saida)
```

**Filtros Estruturais (bloqueios):**

| Filtro | Condicao | Motivo |
|--------|----------|--------|
| Janela negativa | < min 50 E < 7 escanteios | Fora da janela |
| Goleada 1T | min <= 45 E diff >= 3 | Jogo morto |
| Goleada 2T | min > 45 E diff >= 4 | Jogo morto |
| Escanteios insuficientes | total < 3 | Muito pouco movimento |
| Jogo morno | 0x0 apos 60 min E escanteios < 7 | Jogo sem pressao |

---

### 3.3 Score Engine (engine/score_engine.py)

Calcula o **Pressure Score** — medida de pressão ofensiva em 0-10.

**Componentes de Pontuação:**

| Indicador | Pontos | Condicao |
|-----------|--------|----------|
| Escanteios ultimos 10 min | +3 | >= 2 escanteios |
| Escanteio ultimos 5 min | +1 | >= 1 escanteio |
| Ataques perigosos 10 min | +2 | >= 3 ataques |
| Time perdendo por 1 | +2 | Diferenca = 1 gol |
| Posse dominante | +1 | > 50% ultimos 10 min |
| Finalizacoes recentes | +1 | >= 2 finalizacoes |

**Exemplo:**

```
Jogo: Manchester City 1x1 Liverpool (min 72)
├─ Escanteios ultimos 10 min: 2 → +3 pontos
├─ Escanteio ultimos 5 min: 1 → +1 ponto
├─ Ataques perigosos: 4 → +2 pontos
├─ City perdendo por 1: Sim → +2 pontos
├─ Posse 10 min: 62% → +1 ponto
└─ Finalizacoes: 1 → 0 pontos
    ────────────────────────
    PRESSURE SCORE = 9/10 ✓ (qualifica para PREMIUM)
```

---

### 3.4 Projection Engine (engine/projection_engine.py)

Projeta a quantidade final de escanteios (linha de aposta).

**Algoritmo Híbrido:**

```python
projecao_base = (minutos_restantes / 90) * media_esperada_liga
                # Ex: 30 min restantes, media 10.8 → 30/90 * 10.8 = 3.6 escanteios

# Ajuste por pressao (Pressure Score)
ajuste_pressao = score * FATOR_PRESSAO  # FATOR = 0.25
projecao_com_pressao = projecao_base + ajuste_pressao
                       # 3.6 + (9 * 0.25) = 3.6 + 2.25 = 5.85

# Ajuste por historico (trend)
if escanteios_ate_agora > THRESHOLD (10.5):
    ajuste_historico = VALOR_AJUSTE  # 0.5
    projecao_final = projecao_com_pressao + ajuste_historico
else:
    projecao_final = projecao_com_pressao

# Resultado final
projecao_final ≈ 6.35
```

---

### 3.5 State Manager (engine/state_manager.py)

Gerencia re-avaliações de sinais ao longo do jogo.

**Lógica de Re-avaliação:**

```
Sinal emitido (min 72, Edge = +1.2)
    │
    └─ [A cada ciclo: 60s]
       ├─ Jogo ainda ativo?
       │  └─ Nao: Marcar como finalizado
       │
       ├─ Calcular novo Score e Projeção
       │  ├─ Score mudou 1+ ponto?
       │  └─ Edge mudou 0.7+?
       │
       ├─ Se mudanca significativa:
       │  ├─ Atualizar sinal em cache
       │  └─ Enviar re-avaliacao WhatsApp
       │
       └─ [Intervalo minimo entre notificacoes: 3 min]
```

---

### 3.6 Notification Manager (notifier/)

Gerencia envio de mensagens WhatsApp via WAHA API.

**Fluxo de Notificação:**

```
Sinal Emitido (Decision Engine)
    │
    ├─ send_signal(sinal)
    │  ├─ MessageFormatter.format_signal()
    │  ├─ WhatsAppClient.send_message()
    │  │  └─ POST /api/sendMessage (WAHA)
    │  ├─ Salvar em cache (_sinais_enviados)
    │  └─ Registrar timestamp
    │
    ├─ send_reevaluation(sinal_novo)
    │  ├─ Comparar com sinal anterior
    │  ├─ MessageFormatter.format_reevaluation()
    │  ├─ Enviar se intervalo >= 3 min
    │  └─ Atualizar cache
    │
    └─ Resumos Diarios
       ├─ daily_summary()
       ├─ Stats: total, greens, reds, winrate, ROI
       └─ Enviar todo dia às DAILY_SUMMARY_TIME
```

**Formatos de Mensagem:**

```
📊 SINAL NORMAL
├─ Manchester City vs Liverpool
├─ Minuto: 72 | Placar: 1x1
├─ Score: 9/10 | Linha: 10.0
├─ Projeção: 11.2 | Edge: +1.2 ✓
└─ Link: [Dashboard Link]

─────────────────────────

🔄 RE-AVALIAÇÃO (min 75)
├─ Manchester City vs Liverpool
├─ Score: 9 → 10 (+1)
├─ Edge: +1.2 → +1.5 (+0.3)
├─ Novo:  11.5 escanteios
└─ Status: MANTÉM ✓
```

---

## 4. API FastAPI (api_server.py)

Backend que expõe dados para o Dashboard.

### Endpoints

| Metodo | Endpoint | Descricao |
|--------|----------|-----------|
| GET | `/` | Health check |
| GET | `/api/dashboard` | Dados completos do dashboard |
| GET | `/api/status` | Status do sistema (ciclos, rate limit) |
| GET | `/api/signals` | Ultimos sinais emitidos |
| GET | `/api/logs` | Logs do sistema |
| GET | `/api/live-games` | Jogos ao vivo atuais |
| GET | `/api/config/leagues` | Ligas monitoradas |
| POST | `/api/config/leagues` | Atualizar ligas |
| POST | `/api/config/thresholds` | Atualizar limites (score, edge) |
| GET | `/health` | Healthcheck |

### Exemplo de Resposta (/api/dashboard)

```json
{
  "stats": {
    "total": 24,
    "greens": 18,
    "reds": 6,
    "pendentes": 0,
    "winrate": 75.0,
    "roi_total": 12.5
  },
  "status": {
    "ciclo": "2026-02-15 14:32:15",
    "jogos_ao_vivo": 8,
    "jogos_na_janela": 3,
    "api_usado": "45/100",
    "ultimo_update": "2026-02-15 14:32:10",
    "status_msg": "✓ Sistema operacional"
  },
  "signals": [
    {
      "timestamp": "2026-02-15 14:20:00",
      "jogo_descricao": "Manchester City 1x1 Liverpool",
      "tipo_sinal": "PREMIUM",
      "pressure_score": 9,
      "projecao": 11.5,
      "edge": 1.5,
      "linha": 10.0,
      "resultado": "WIN",
      "escanteios_final": 12
    }
  ],
  "ligas": [
    {
      "id": 39,
      "nome": "Premier League",
      "pais": "England",
      "media_esperada": 10.8
    }
  ]
}
```

---

## 5. Dashboard Web (dashboard/)

Frontend Next.js/TypeScript que consome a API.

### Componentes

| Componente | Funcao |
|-----------|--------|
| Header | Logo, status da API, ciclo atual |
| MetricCard | Cards de stats (total, greens, reds, winrate, ROI) |
| RecentSignals | Tabela de ultimos sinais com status |
| PollingStats | Requisicoes da API, stats de polling adaptativo |
| MonitoredLeagues | Ligas monitoradas, configuracao |
| SystemLogs | Logs em tempo real |
| Settings | Ajustes de thresholds (score, edge) |

### Fluxo de Dados

```
Next.js App Router (src/app/page.tsx)
    │
    ├─ useEffect → fetch /api/cpes/dashboard
    │  └─ Chama api.ts (wrapper de HTTP)
    │
    └─ Renderiza componentes com dados
       ├─ MetricCard (stats)
       ├─ RecentSignals (ultimos sinais)
       ├─ PollingStats (rate limit)
       └─ SystemLogs (logs)
```

---

## 6. Persistencia de Dados

### SQLite Database (storage/database.py)

Armazena sinais históricos e resultados.

**Tabelas:**

```sql
signals
├─ id INT (PK)
├─ fixture_id INT
├─ pressure_score FLOAT
├─ projecao FLOAT
├─ edge FLOAT
├─ linha FLOAT
├─ tipo VARCHAR (NORMAL/PREMIUM)
├─ timestamp DATETIME
├─ resultado VARCHAR (WIN/LOSS/PENDING)
└─ escanteios_final INT

teams
├─ team_id INT (PK)
└─ team_name VARCHAR

fixtures
├─ fixture_id INT (PK)
├─ liga_id INT
├─ home_team_id INT
├─ away_team_id INT
└─ timestamp DATETIME
```

### JSON Files

Atualizados a cada ciclo:

```json
📄 live_state.json
{
  "ciclo": "2026-02-15 14:32:15",
  "jogos_processados": 24,
  "sinais_emitidos": 3,
  "jogos_ao_vivo": [
    {
      "id": 1234567,
      "descricao": "Manchester City 1x1 Liverpool",
      "minuto": 72,
      "escanteios_total": 8,
      "escanteios_ultimos_5min": 1,
      "pressure_score": 9,
      "fase": "na_janela"
    }
  ]
}

📄 upcoming_games.json
{
  "atualizado": "2026-02-15 12:00:00",
  "proximo_jogo_min": 240,
  "jogos": [
    {
      "id": 1234568,
      "descricao": "Barcelona vs Real Madrid",
      "comeca_em_minutos": 240
    }
  ]
}
```

---

## 7. Fluxo Completo de Execução

### Cenário: Um Sinal é Emitido

```
[00:00] Sistema inicia
        ├─ Conecta API-Football
        ├─ Conecta WAHA
        ├─ Carrega config.py
        └─ Inicia loop principal

[01:00] Ciclo 1 - Fetch dados
        ├─ GET /fixtures?live=all (API-Football)
        │  └─ Retorna ~40 jogos ao vivo
        │
        ├─ Filtro liga (apenas LIGAS_MONITORADAS)
        │  └─ Retorna ~8 jogos relevantes
        │
        └─ Para cada jogo:

[01:05] Analise - Manchester City 1x1 Liverpool (min 72)
        │
        ├─ DecisionEngine.avaliar(jogo)
        │  │
        │  ├─ _verificar_filtros() → OK (min 72, na janela)
        │  │
        │  ├─ score_engine.calcular() → Score = 9/10
        │  │  └─ +3 (escanteios), +1 (recent), +2 (ataques), +2 (perdendo)
        │  │
        │  ├─ projection_engine.calcular_projecao()
        │  │  └─ Projeção = 11.5
        │  │
        │  ├─ Edge = 11.5 - 10.0 = +1.5
        │  │
        │  └─ Score >= 8 E Edge >= 1.5 → SINAL PREMIUM ✓
        │
        ├─ NotificationManager.send_signal(sinal)
        │  │
        │  ├─ MessageFormatter.format_signal()
        │  │  └─ Texto: "📊 SINAL PREMIUM..."
        │  │
        │  ├─ WhatsAppClient.send_message()
        │  │  └─ POST http://localhost:3000/api/sendMessage
        │  │     └─ WAHA envia via WhatsApp ✓
        │  │
        │  ├─ Database.salvar_sinal()
        │  │  └─ INSERT signals table
        │  │
        │  ├─ StateManager cache: _sinais_enviados[123] = sinal
        │  │
        │  └─ Log: "SINAL PREMIUM enviado"
        │
        └─ Salvar estado em live_state.json

[01:06] Re-avaliação (proximos ciclos)
        ├─ [min 75] Calcular novo score/edge
        │  ├─ Score = 10 (score nao muda)
        │  ├─ Edge = +1.8 (edge mudou 0.3)
        │  └─ re_avaliacao? Nao, delta < 0.7
        │
        └─ [min 78] Novo ciclo
           ├─ Score = 10
           ├─ Edge = +2.0 (mudanca de 0.5, total 0.5 desde envio)
           └─ Sem re-avaliacao (intervalo < 3 min)

[30:00] Dashboard acessa /api/dashboard
        ├─ Carrega dados em JSON
        ├─ API retorna ultimos sinais (incluindo o PREMIUM)
        ├─ Dashboard renderiza tabela
        └─ Usuario ve: "Manchester City - PREMIUM - WIN - +1.5"

[90:00] Jogo termina (2x2)
        ├─ API-Football marca fixture como FT (finalizado)
        ├─ CPES detecta fim
        ├─ Database.marcar_resultado()
        │  └─ UPDATE signals SET resultado='WIN' (pois 2x2 = 11 escanteios)
        │
        └─ live_state.json atualizado (jogo removido)
```

---

## 8. Ciclos de Execução

### A. Ciclo Principal (60s)

```
[A cada POLLING_INTERVAL = 60 segundos]

1. Fetch upcoming_games    ← Proximo jogo em quantos minutos?
2. GET /fixtures?live=all  ← Jogos ao vivo agora
3. Filtro por liga
4. Para cada jogo:
   ├─ Extrair dados
   ├─ DecisionEngine.avaliar()
   ├─ Se sinal: NotificationManager.send_signal()
   ├─ Se re-avaliacao: StateManager.check_reevaluation()
   └─ Salvar em database
5. Salvar live_state.json
6. Log ciclo
```

### B. Verificação de Status (5 min)

```
[A cada STATUS_CHECK_INTERVAL = 300 segundos]

1. Log status:
   ├─ Ciclos executados
   ├─ Rate limit (X/100 requisicoes)
   ├─ Sinais emitidos
   └─ Ultimos erros
```

### C. Resumo Diário (24h)

```
[Diariamente em DAILY_SUMMARY_TIME]

1. Calcular stats:
   ├─ Total de sinais
   ├─ Greens (WIN)
   ├─ Reds (LOSS)
   ├─ Winrate
   └─ ROI total
2. Montar mensagem formatada
3. NotificationManager.send_daily_summary()
```

---

## 9. Configuração Central (config.py)

Todos os parametros tuneaveis em um arquivo:

```python
# Janela de monitoramento
MINUTO_INICIO = 50         # Comeca a monitorar em min 50
MINUTO_FIM = 90            # Para em min 90

# Filtros
MAX_DIFERENCA_GOLS = 3     # Bloqueia 4x0, 5x1 etc
MIN_ESCANTEIOS_TOTAL = 3   # Minimo de escanteios no jogo

# Thresholds de Score
MIN_SCORE_NORMAL = 6       # Score para NORMAL
MIN_SCORE_PREMIUM = 8      # Score para PREMIUM

# Thresholds de Edge
MIN_EDGE_NORMAL = 0.8      # Edge minimo NORMAL
MIN_EDGE_PREMIUM = 1.5     # Edge minimo PREMIUM

# API-Football
API_DAILY_LIMIT = 100      # Requisicoes por dia

# Ligas monitoradas
LIGAS_MONITORADAS = [
    {"id": 39, "nome": "Premier League", ...},
    {"id": 71, "nome": "Brasileirão", ...},
    ...
]

# WAHA
WAHA_URL = "http://localhost:3000"
WAHA_API_KEY = "..." # Chave segura
WHATSAPP_GROUP_ID = "xxx@g.us"
WHATSAPP_ADMIN = "+55 11 9xxxx-xxxx"
```

---

## 10. Stack Tecnológico

| Area | Tecnologia |
|------|-----------|
| Backend | Python 3.10+ |
| Framework Web | FastAPI |
| Banco de Dados | SQLite |
| Frontend | Next.js 14+ |
| Linguagem Frontend | TypeScript |
| Styling | CSS/Tailwind |
| WhatsApp API | WAHA (WhatsApp HTTP API) |
| Container | Docker + Docker Compose |
| Deploy | Cloudflare Workers/Tunnel |

---

## 11. Fluxo de Deploy

```
Desenvolvimento (Local)
    ↓
docker compose up -d --build
    ├─ Backend: python corner-pressure-elite/
    ├─ API: FastAPI :8000
    ├─ WhatsApp: WAHA :3000
    └─ Frontend: Next.js :3001
    ↓
Cloudflare Tunnel
    ├─ https://odontoschultz.online → Dashboard
    ├─ https://api.odontoschultz.online → API
    └─ ssh.odontoschultz.online → SSH access
```

---

## 12. Monitoramento e Logs

### Estrutura de Logs

```
logs/
├─ cpes.main.log      # Log principal (robo)
├─ cpes.api.log       # Log API
├─ cpes.engine.log    # Log decision/score engine
├─ cpes.notifier.log  # Log notificacoes
└─ cpes.database.log  # Log database
```

### Log Levels

```
DEBUG   → Logs detalhados (Score = 8, Edge = +1.2)
INFO    → Eventos importantes (Sinal emitido, re-avaliacao)
WARNING → Avisos (Rate limit proximo)
ERROR   → Erros (API offline, falha WhatsApp)
```

---

## 13. Troubleshooting

### Problema: System nao emite sinais

```
1. Verificar config.py:
   └─ MIN_SCORE_NORMAL e MIN_EDGE_NORMAL muito altos?

2. Verificar jogo na janela:
   └─ Minuto >= 50 E Minuto < 90?

3. Verificar Score:
   └─ Executar test_score.py com dados do jogo

4. Verificar Projecao:
   └─ Executar test_projection.py com dados reais
```

### Problema: WhatsApp nao recebe notificacoes

```
1. Verificar WAHA:
   └─ curl http://localhost:3000/api/status

2. Verificar API_KEY:
   └─ WAHA_API_KEY esta configurada?

3. Verificar Group ID:
   └─ Format correto: "123456789@g.us"?

4. Verificar logs:
   └─ tail -f logs/cpes.notifier.log
```

### Problema: Dashboard vazio ou lento

```
1. Verificar API:
   └─ curl http://localhost:8000/api/dashboard

2. Verificar database:
   └─ Tem sinais salvos?

3. Verificar logs:
   └─ tail -f logs/cpes.api.log
```

---

## 14. Resumo Visual

```
┌─────────────────────────────────────────────────────────┐
│          CORNER PRESSURE ELITE SYSTEM (CPES)            │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  API-Football (v3.football.api-sports.io)              │
│         │                                              │
│         ├─→ API Football Client                        │
│         │       │                                      │
│         └──────→ Decision Engine                       │
│                  │                                     │
│                  ├─→ Score Engine (0-10)              │
│                  ├─→ Projection Engine (4-14)         │
│                  └─→ State Manager (re-eval)          │
│                      │                                │
│                      └─→ Notification Manager         │
│                          │                            │
│                          ├─→ WAHA API (WhatsApp)     │
│                          ├─→ SQLite (histórico)      │
│                          └──→ JSON (estado vivo)     │
│                              │                        │
│                              ├─→ Dashboard (Next.js)  │
│                              └─→ Metrics/Stats        │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

---

## 15. Conclusão

O CPES é um sistema completo e automatizado de análise de escanteios que:

✓ **Coleta** dados em tempo real (API-Football)  
✓ **Analisa** pressão ofensiva (Decision Engine + Score)  
✓ **Projeta** escanteios finais (Projection Engine)  
✓ **Decide** quando emitir sinais (thresholds de score/edge)  
✓ **Notifica** via WhatsApp (WAHA API)  
✓ **Monitora** através de Dashboard Web (Next.js)  
✓ **Persiste** dados em SQLite  
✓ **Re-avalia** sinais ao longo do jogo (State Manager)  

Tudo em ciclos de **60 segundos**, 24/7, monitorando **13+ ligas** principais.

---

**Proximas Melhorias Planejadas:**
- [ ] Machine learning para tunagem de thresholds
- [ ] Backtest automático de estratégias
- [ ] Integracao com APIs de odds reais
- [ ] Dashboard mobile responsivo
- [ ] Webhook de resultados automáticos
