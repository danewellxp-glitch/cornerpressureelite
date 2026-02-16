# Sprints de Melhoria — CPES

> Planejamento de evolucao do Corner Pressure Elite System
> Atualizado: 15/02/2026

---

## Estado Atual do Sistema

| Componente | Status |
|------------|--------|
| Score Engine | Completo |
| Projection Engine | Completo |
| Decision Engine | Completo |
| API Client (API-Football) | Completo |
| WhatsApp (WAHA) | Completo |
| Dashboard Next.js | Completo |
| Adaptive Polling + Sleep Schedule | Completo |
| Database SQLite | Completo |
| Testes unitarios | Completo (57 testes) |
| **Odds ao vivo** | Completo (Sprint 1) |
| **Resultado automatico + ROI** | Completo (Sprint 2) |
| **Backtest (coleta organica)** | Completo (Sprint 3) |
| **CI/CD** | Nao implementado |

---

## Sprint 1 — Odds ao Vivo + Edge Real (Prioridade Alta)

**Objetivo:** Buscar odds/linhas de escanteios ao vivo da API-Football e usar no calculo de edge real.

### Tarefas

- [x] **1.1** Metodo `get_live_odds(fixture_id)` no `api_client.py`
  - Endpoint: `/odds/live` com fallback para `/odds` pre-match
  - Parser unificado `_parse_corners_odds()` para ambos formatos
  - Filtro por keywords: "corner", "escanteio"

- [x] **1.2** Modelo `OddsAoVivo` em `data/models.py`

- [x] **1.3** Integracao no fluxo de analise em `main.py`

- [x] **1.4** Mensagem WhatsApp com odds

- [x] **1.5** Odds salvas no banco (tabela `sinais`)

- [x] **1.6** Dashboard mostra odds e linha

- [x] **1.7** Testes de parsing de odds (10 testes em `test_odds.py`)

**Arquivos:** `api_client.py`, `models.py`, `main.py`, `message_formatter.py`, `database.py`, `dashboard/src/app/page.tsx`
**Estimativa:** 3-4 dias
**Reqs API:** +1 req por jogo analisado (odds endpoint)

---

## Sprint 2 — Resultado Automatico + ROI (Prioridade Alta)

**Objetivo:** Apos o jogo terminar, buscar resultado final automaticamente e marcar sinal como GREEN/RED.

### Tarefas

- [x] **2.1** Metodo `get_fixture_result(fixture_id)` no `api_client.py`
  - Contagem via statistics + events (pega o maior valor)

- [x] **2.2** Job `_verificar_resultados()` no `main.py`
  - Roda a cada ciclo, filtra sinais com mais de 2h
  - Expira sinais com mais de 24h sem resultado

- [x] **2.3** Calcular ROI por sinal (GREEN: odd-1, RED: -1)

- [x] **2.4** Resumo de resultados via WhatsApp

- [x] **2.5** Dashboard com badges GREEN/RED e ROI

- [x] **2.6** Filtro de antiguidade no banco (`get_sinais_pendentes` limita a 24h)

- [x] **2.7** Testes de resultados (14 testes em `test_resultados.py`)

**Arquivos:** `api_client.py`, `main.py`, `database.py`, `notification_manager.py`, `message_formatter.py`

---

## Sprint 3 — Backtest com Dados Reais (Coleta Organica) ✅

**Objetivo:** Validar a estrategia com dados reais coletados durante analise ao vivo.

**Abordagem:** Em vez de buscar dados historicos (que so tem stats finais), o sistema salva snapshots completos durante a analise ao vivo. O backtest roda o decision engine sobre esses snapshots com parametros diferentes.

### Tarefas

- [x] **3.1** Tabela `snapshots` no banco principal (`database.py`)
  - Salva estado completo do JogoAoVivo em cada analise
  - Metodos: `salvar_snapshot`, `atualizar_snapshot_resultado`, `get_snapshots`, `get_snapshot_stats`

- [x] **3.2** Integrar coleta de snapshots no `main.py`
  - Salva snapshot em `_analisar_jogo` (antes do decision engine)
  - Atualiza resultado em `_verificar_resultados` (quando jogo termina)

- [x] **3.3** Modulo `backtest/simulator.py`
  - Replay do decision engine sobre snapshots com parametros customizados
  - Suporta grid search de parametros (optimize)
  - Calcula: winrate, ROI, drawdown maximo

- [x] **3.4** Modulo `backtest/reporter.py`
  - Gera relatorio markdown com metricas por liga
  - Relatorio de otimizacao (top 10 configs)

- [x] **3.5** CLI `python -m backtest` com comandos: `status`, `simulate`, `optimize`, `report`

- [x] **3.6** Testes (14 testes em `test_backtest.py`)

**Arquivos:** `backtest/`, `storage/database.py`, `main.py`
**Reqs API:** 0 (dados coletados organicamente)

---

## Sprint 4 — Mais Ligas + Config Dinamica (Prioridade Media)

**Objetivo:** Adicionar mais ligas e permitir ajustes sem reiniciar o robo.

### Tarefas

- [ ] **4.1** Adicionar ligas
  - La Liga (Espanha) — ID 140
  - Serie A (Italia) — ID 135
  - Ligue 1 (Franca) — ID 61
  - Eredivisie (Holanda) — ID 88
  - Liga Portugal — ID 94
  - MLS (EUA) — ID 253

- [ ] **4.2** Criar endpoint `POST /api/config/leagues` no `api_server.py`
  - Habilitar/desabilitar ligas sem reiniciar
  - Persistir em banco

- [ ] **4.3** Criar endpoint `POST /api/config/thresholds`
  - Ajustar score, edge, filtros em tempo real
  - Ex: diminuir MIN_SCORE_NORMAL de 6 para 5 via API

- [ ] **4.4** Adicionar pagina de configuracao no dashboard
  - Toggle de ligas
  - Sliders para thresholds
  - Botao salvar

**Arquivos:** `config.py`, `api_server.py`, `database.py`, `dashboard/src/`
**Estimativa:** 3-4 dias

---

## Sprint 5 — Dashboard Avancado (Prioridade Media)

**Objetivo:** Melhorar visualizacao com graficos e analytics.

### Tarefas

- [ ] **5.1** Grafico de ROI acumulado ao longo do tempo
  - Linha de evolucao: dia a dia

- [ ] **5.2** Grafico de winrate por liga
  - Barra comparativa entre ligas

- [ ] **5.3** Heatmap de horarios mais lucrativos
  - Quais horarios geram mais sinais GREEN

- [ ] **5.4** Filtros de periodo no dashboard
  - Hoje, ultima semana, ultimo mes, custom

- [ ] **5.5** Detalhes do sinal (modal)
  - Clicar no sinal → ver stats completas do jogo

**Arquivos:** `dashboard/src/`, `api_server.py` (novos endpoints)
**Estimativa:** 4-5 dias

---



---

## Sprint 7 — CI/CD + Monitoramento (Prioridade Baixa)

**Objetivo:** Automacao de testes e deploy + alertas de saude do sistema.

### Tarefas

- [ ] **7.1** GitHub Actions para rodar testes em cada push
- [ ] **7.2** Health check endpoint com metricas detalhadas
- [ ] **7.3** Alerta WhatsApp se o robo parar por mais de 5 min
- [ ] **7.4** Dashboard de metricas (uptime, latencia API, erros/hora)
- [ ] **7.5** Auto-restart do container se health check falhar

**Estimativa:** 3-4 dias

---

## Resumo de Prioridades

| Sprint | Nome | Prioridade | Estimativa | Impacto |
|--------|------|-----------|------------|---------|
| **1** | Odds ao Vivo | Alta | 3-4 dias | Edge real, sinais mais precisos |
| **2** | Resultado Automatico | Alta | 2-3 dias | ROI real, validacao do sistema |
| **3** | Backtest | Media | 5-7 dias | Validacao historica da estrategia |
| **4** | Mais Ligas + Config | Media | 3-4 dias | Mais oportunidades, flexibilidade |
| **5** | Dashboard Avancado | Media | 4-5 dias | Melhor visualizacao e analise |
| **6** | Telegram | Baixa | 2 dias | Canal alternativo |
| **7** | CI/CD + Monitoramento | Baixa | 3-4 dias | Estabilidade e automacao |

**Total estimado:** ~25-30 dias de desenvolvimento
**Recomendacao:** Comecar pela Sprint 1 (odds) + Sprint 2 (resultados) — juntas dao o maior impacto no sistema.
