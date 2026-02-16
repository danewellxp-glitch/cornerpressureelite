# Análise Executiva — Corner Pressure Elite System (CPES)

**Versão:** 1.0  
**Data:** Fevereiro 2025  
**Tipo:** Documento Executivo

---

## 1. Resumo Executivo

O **Corner Pressure Elite System (CPES)** é um sistema automatizado de análise estatística em tempo real para apostas esportivas no mercado de **escanteios** em partidas de futebol ao vivo. O sistema monitora jogos de ligas selecionadas, calcula indicadores de pressão ofensiva e gera sinais quando identifica oportunidades (edge) acima da linha de apostas disponível.

### Principais Características

| Aspecto | Descrição |
|---------|-----------|
| **Objetivo** | Identificar jogos com pressão ofensiva elevada que tendem a ultrapassar a linha de escanteios do mercado |
| **Mercado** | Escanteios totais (Over/Under) em futebol ao vivo |
| **Dados** | API-Football v3 (estatísticas em tempo real) |
| **Notificações** | WhatsApp via WAHA (WhatsApp HTTP API) |
| **Economia** | Polling adaptativo reduz ~70–90% das requisições em relação à análise contínua de todos os jogos |

---

## 2. Arquitetura do Sistema

### 2.1 Visão Geral

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         CORNER PRESSURE ELITE SYSTEM                         │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐    ┌───────────┐ │
│  │ API-Football │───▶│  Main Loop   │───▶│   Decision   │───▶│ WhatsApp  │ │
│  │ (dados live) │    │ (ciclo 60s)  │    │   Engine     │    │ (WAHA)    │ │
│  └──────────────┘    └──────────────┘    └──────────────┘    └───────────┘ │
│         │                     │                    │                        │
│         │                     ▼                    ▼                        │
│         │             ┌──────────────┐    ┌──────────────┐                   │
│         │             │  Adaptive    │    │  SQLite DB   │                   │
│         │             │  Polling     │    │  (sinais)    │                   │
│         │             └──────────────┘    └──────────────┘                   │
│         │                     │                    │                        │
│         └─────────────────────┴────────────────────┘                        │
│                               │                                             │
│                               ▼                                             │
│  ┌──────────────────────────────────────────────────────────────────────┐  │
│  │  Dashboard Web (Next.js)  │  API Server (FastAPI)  │  Monitor (CLI)   │  │
│  │  http://localhost:3001    │  http://localhost:8000 │  python monitor  │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 2.2 Componentes Principais

| Componente | Tecnologia | Função |
|------------|------------|--------|
| **main.py** | Python 3, asyncio | Loop principal: busca jogos, classifica fases, analisa, envia alertas |
| **api_client.py** | aiohttp | Cliente assíncrono para API-Football v3 |
| **decision_engine.py** | Python | Motor de decisão: filtros estruturais + Pressure Score + projeção + edge |
| **score_engine.py** | Python | Cálculo do Pressure Score (0–10) |
| **projection_engine.py** | Python | Projeção híbrida de escanteios até o fim do jogo |
| **state_manager.py** | Python | Controle de alertas enviados e lógica de reavaliação |
| **notification_manager.py** | Python | Envio de sinais e reavaliações via WhatsApp (WAHA) |
| **database.py** | aiosqlite | Persistência de sinais e resultados (SQLite) |
| **api_server.py** | FastAPI | API REST para dashboard e integrações |
| **monitor.py** | Python | Dashboard em tempo real no terminal |
| **dashboard/** | Next.js 16, React 19 | Interface web de acompanhamento |

---

## 3. Fluxo de Operação

### 3.1 Ciclo Principal (≈60 segundos)

1. **Verificação de status** (a cada 5 min): Sincroniza uso da API com o plano da conta.
2. **Busca jogos ao vivo**: `get_live_fixtures()` para cada liga monitorada.
3. **Classificação por fase**:
   - **Pre-janela** (&lt; min 50): Aguardando janela — não analisa (economia).
   - **Na janela** (50–90): Janela principal — analisa conforme Adaptive Polling.
   - **Pós-janela** (90+): Acréscimos — polling intenso (30 s).
4. **Análise seletiva**: Apenas jogos em janela/pós-janela e com `should_poll == True`.
5. **Decision Engine**: Filtros → Pressure Score → Projeção → Edge → Decisão (NORMAL ou PREMIUM).
6. **Notificação**: Sinais enviados ao grupo WhatsApp e, opcionalmente, a número de updates.
7. **Persistência**: `live_state.json` para dashboard; SQLite para sinais.

### 3.2 Polling Adaptativo

| Fase do jogo | Intervalo | Descrição |
|--------------|-----------|-----------|
| 0–30 min | 5 min | Primeiro tempo inicial |
| 31–50 min | 3 min | Pre-janela primeiro tempo |
| 31–50 min (7+ esc) | 1 min | **Early trigger**: 7+ escanteios → entra na janela |
| 50–90 min | 1 min | Janela de análise principal |
| 90+ min | 30 s | Acréscimos (crítico) |

**Early trigger:** Se o jogo tiver 7+ escanteios antes do min 50 (ex.: 22 min com 7 esc), passa a ser analisado a cada 1 min e entra em "Na janela (sendo analisados)".

**Efeito:** Em dias com muitos jogos, apenas ~10–30% são analisados a cada ciclo, gerando economia de 70–90% nas requisições da API.

---

## 4. Modelo de Decisão

### 4.1 Filtros Estruturais (bloqueio)

| Filtro | Condição | Motivo |
|--------|----------|--------|
| Janela | min &lt; 50 | Fora da janela de análise |
| Diferença de gols | &gt; 2 | Jogo desequilibrado |
| Escanteios totais | &lt; 5 | Insuficiente para análise |
| Escanteios últimos 5 min | &lt; 1 | Sem escanteio recente |
| Jogo morno | 0x0 após 60 min com &lt; 7 esc. | Baixa dinâmica |
| Time sem escanteio no 1º tempo | min &gt; 45 e um time com 0 esc. | Jogo morto |

### 4.2 Pressure Score (0–10)

Pontos somados com base em indicadores de pressão:

| Indicador | Pontos | Condição |
|-----------|--------|----------|
| Escanteios últimos 10 min | +3 | ≥ 2 |
| Escanteios últimos 5 min | +1 | ≥ 1 |
| Ataques perigosos últimos 10 min | +2 | ≥ 6 |
| Time perdendo por 1 gol | +2 | Sim |
| Posse de bola dominante | +1 | &gt; 60% |
| Finalizações recentes | +1 | ≥ 3 |

**Mínimos para sinal:**
- **NORMAL**: Score ≥ 8 e Edge ≥ 1.3
- **PREMIUM**: Score ≥ 9 e Edge ≥ 2.0

### 4.3 Projeção Híbrida

\[
\text{Projeção} = \text{Ritmo base} + \text{Ajuste pressão} + \text{Ajuste histórico}
\]

- **Ritmo base:** (escanteios / minuto) × 95
- **Ajuste pressão:** Pressure Score × 0,25
- **Ajuste histórico:** +0,5 se média da liga &gt; 10,5

### 4.4 Edge

\[
\text{Edge} = \text{Projeção} - \text{Linha atual}
\]

A linha atual representa o total de escanteios oferecido pelo mercado (Over/Under).

---

## 5. Ligações Monitoradas

| Liga | País | Média esperada |
|------|------|----------------|
| Premier League | Inglaterra | 10,8 |
| Bundesliga | Alemanha | 11,2 |
| Brasileirão A | Brasil | 9,8 |
| Brasileirão B | Brasil | 9,5 |
| Carioca A | Brasil | 9,5 |
| Liga Profesional Argentina | Argentina | 10,2 |
| Primera División Chile | Chile | 10,0 |

---

## 6. Infraestrutura e Portas

| Serviço | Porta | URL |
|---------|-------|-----|
| WAHA (WhatsApp API) | 3000 | http://localhost:3000 |
| Dashboard (Next.js) | 3001 | http://localhost:3001 |
| FastAPI (Backend) | 8000 | http://localhost:8000 |

### Scripts de Operação

- **start_all.ps1**: Inicia WAHA (Docker), FastAPI, Dashboard e Monitor.
- **kill_all.ps1**: Encerra todos os processos do sistema.

---

## 7. Configuração (variáveis de ambiente)

| Variável | Descrição | Padrão |
|----------|-----------|--------|
| API_FOOTBALL_KEY | Chave da API-Football | (obrigatório) |
| API_DAILY_LIMIT | Limite diário de requisições | 100 |
| WAHA_URL | URL do WAHA | http://localhost:3000 |
| WAHA_SESSION_NAME | Nome da sessão WhatsApp | cpes-alerts |
| WAHA_API_KEY | Chave de API do WAHA | (opcional) |
| WHATSAPP_GROUP_ID | ID do grupo para sinais | (obrigatório) |
| WHATSAPP_ADMIN | Número admin para erros | (recomendado) |
| WHATSAPP_UPDATES | Número adicional para updates | (opcional) |
| DB_PATH | Caminho do SQLite | data/cpes.db |
| DAILY_SUMMARY_TIME | Horário do resumo diário | 23:00 |

---

## 8. Dashboard Web

### Funcionalidades

- **Jogos ao vivo por fase**: Pre-janela, Na janela, Após janela (com escanteios quando disponível)
- **Status do sistema**: Uso da API, janela de minuto, jogos ao vivo
- **Performance**: Total de sinais, greens, reds, pendentes, winrate, ROI
- **Sinais recentes**: Tabela com hora, jogo, tipo, score, edge, resultado
- **Ligas monitoradas**: Lista com média esperada
- **Log**: Últimas linhas do arquivo de log
- **Atualização**: Polling a cada 10 segundos

### Tecnologias

- Next.js 16, React 19, Tailwind CSS 4, TypeScript

---

## 9. Fluxo de Notificações

| Evento | Destino | Formato |
|--------|---------|---------|
| Sinal NORMAL/PREMIUM | Grupo + Updates | Mensagem formatada (jogo, score, edge, projeção, linha) |
| Reavaliação | Grupo + Updates | Mensagem com dados do primeiro alerta + novos valores |
| Erro crítico | Admin | Alerta de erro |
| Status ao iniciar | Admin | Resumo do sistema |
| Resumo diário | Grupo | Estatísticas (total, greens, reds, winrate, ROI) |

---

## 10. Persistência de Dados

### SQLite (`data/cpes.db`)

- **Tabela `sinais`**: timestamp, jogo_id, jogo_descricao, minuto, placar, escanteios_total, linha, odd, projeção, edge, pressure_score, tipo_sinal, reavaliação, resultado, escanteios_final, roi
- **Tabela `detalhes_jogo`**: sinal_id, ataques_perigosos, finalizações, posse, escanteios por time, média histórica

### live_state.json

Arquivo JSON com estado em tempo real para o dashboard: pre_janela, na_janela, pos_janela, ids_observados, escanteios por jogo (cache), polling_stats.

---

## 11. Pontos Fortes

| Aspecto | Descrição |
|---------|-----------|
| **Economia de API** | Polling adaptativo reduz drasticamente o consumo |
| **Modelo quantitativo** | Pressure Score + projeção + edge bem definidos |
| **Reavaliação** | Atualiza alertas quando edge/score/linha evoluem |
| **Múltiplas interfaces** | Dashboard web, API REST e monitor CLI |
| **Integração WhatsApp** | Sinais diretos para grupo e admin |
| **Resumo diário** | Performance consolidada ao fim do dia |

---

## 12. Considerações e Riscos

| Risco | Mitigação |
|-------|-----------|
| Limite diário da API | Rate limiter, polling adaptativo, pausa ao atingir limite |
| API indisponível (503, etc.) | Tratamento de resposta não-JSON, retry implícito no próximo ciclo |
| WAHA desconectado | Mensagens de erro ao admin, sistema continua em execução |
| Linha do mercado | Sistema usa linha informada; integração com odds seria evolução |

---

## 13. Evoluções Futuras Sugeridas

1. **Integração com API de odds**: Buscar linha de escanteios em tempo real
2. **Backtest**: Histórico de sinais vs resultados para calibração
3. **Filtros por liga**: Ativar/desativar ligas dinamicamente
4. **Alertas por Telegram**: Canal alternativo ao WhatsApp
5. **Métricas de latência**: Tempo entre detecção e envio do sinal

---

## 14. Conclusão

O CPES é um sistema modular e bem estruturado para identificação de oportunidades no mercado de escanteios em tempo real. A combinação de polling adaptativo, modelo de decisão baseado em pressão e integração com WhatsApp permite operação automatizada com controle de custos de API e boa usabilidade para o usuário final.

---

*Documento gerado com base na análise do código-fonte do sistema Corner Pressure Elite (CPES).*
