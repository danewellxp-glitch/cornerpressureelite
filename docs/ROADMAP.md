# ROADMAP

Fases planejadas + estado atual. Atualizado quando fase fecha ou nova é planejada.

> **Escopo:** visão geral (1 linha por fase). Detalhes operacionais por sprint vão em `docs/sprints/`.

## Concluído

- **Fase 1** — Bridge inicial (HTTP /quote, /health)
- **Fase 2a** — Catálogo completo /markets, política central 1.50-1.70
- **Fase 2a.1** — Otimização latência (24s → 8.5s)
- **Fase 3** — Refactor Protocol OddsProvider
- **Fase 2bc** — Composite wired no pipeline real
- **Fase D.0** — Telemetria full coverage com catálogo + contexto rico
- **Bridge Pool** — Pool distribuído (odin local + danewell LAN)
- **Fase D.1** — Bridge `/events/live` via Brave do pool danewell (renewer + danae API)
- **Fase D.2** — Worker `BetanoFixtureDiscovery` no cpes-main (matcher fuzzy + UPSERT auto). BETANO_EVENT_MAP virou override opcional.
- **Fase D.2 PARTE A** — Catálogo de teams 1×/dia: danewell `/danae/teams` (agrega live + upcoming) → bridge `/teams` (cache 24h) → worker refresh popula `betano_team_map` proativamente
- **Proxy residencial** — Brave do pool sai por IP RJ (ML Telecom) pra diversificar fingerprint
- **Systemd units** — Bridge resilient a crash + reboot
- **Fase E.0** — Investigação técnica stats Betano (mapeamento `/danae-webapi/api/live/events/<id>/latest`, gotchas `X-Operator/X-Language`) — commit `5553934` 2026-05-16
- **Fase E.1** — Stats Betano via bridge + Composite cascade Betano→AF. `USE_BETANO_STATS=true` em produção, smoke real validado (6 capturas bridge_betano + 12 AF fallback, version polling 4133→4222, latência 7-7.5s, decision_engine consumindo Score=7) — commit `1e3efca` 2026-05-17
- **Fase F** — Eventos Betano via `event.incidents[]` (dataset puro). `BetanoEventsWorker` persiste em `events_history` paralelo ao pipeline live. CompositeEventsProvider Betano→AF. Smoke real validou 18 events via fallback AF (bridge renewer em warmup intermitente, source bridge_betano flippa quando recupera — mesma dinâmica E.1). Dedup UNIQUE comprovado, throttle 30s, decision_engine intocado. `USE_BETANO_EVENTS=true` ativo — commit `a65bfe6` 2026-05-17
- **Fase G.0** — Investigação técnica lineups Betano + validação saúde renewer 24h. Schema descoberto inspecionando `event.roster` do `/event/<id>/state` (já capturado pela E.1) — CASO α puro confirmado, zero novo endpoint — commit `508147b` 2026-05-17
- **Fase G.1** — Lineups Betano via `event.roster` (dataset puro). 6 commits: migration 0007 (`86da575`), Protocol+adapters+Composite (`4d388ab` + ajustes pós-review `a4ceb97`), Worker+configs+wiring (`223368d` + fix VAL 4 `9de2829`), suite 48 testes (`63cfd3a`). Decision_engine intocado, `USE_BETANO_LINEUPS=true` ativo. Smoke leve verde; smoke real assíncrono (sem jogos live no momento, capturas acontecem quando próximo lote começar) — 2026-05-17
- **Sprint M** (2026-05-17) — Multi-tenant: banca per-user (migration 0011) + decisões por sinal opt-in (0012) + dashboard limpo per-user. Ver CLAUDE.md §13.14.
- **Sprint M.2** (2026-05-19) — Multi-leg + bonus turbinada + settle automático (single) / manual (multi) + sistema de unidades. Migrations 0014 (FK fix), 0015 (legs+bonus), 0016 (unidades). Resolve pendência do settle da Sprint M. Layout "Minhas Apostas" estilo Betano. Ver CLAUDE.md §13.16.
- **Fase K + K.1** (2026-05-17) — SofaScore na cascata (stats/events/lineups, Betano→SofaScore→AF) em produção. Ver CLAUDE.md §13.2.
- **Fase H A1** (2026-05-17→20) — Dual-key `sofa_event_id` (migration 0013) + dual-write + **fix do gargalo (2026-05-20)**: workers do bridge não chamavam o resolver live → fill 0% no `bridge_betano`. Corrigido (`get_or_resolve` + `resolve_by_fixture_id` + filtro de competição). **Validado em produção: 0% → 100%** com jogos ao vivo. Ver BUGS.md 2026-05-20.
- **Ligas CONMEBOL** (2026-05-20) — Libertadores + Sul-Americana (config + SofaScore map). Fix timezone na agenda (4→13 jogos).
- **Sprint N** (2026-05-20) — Achados do capture .mitm + implementação (ver abaixo "Cutover sofa_event_id").

## Em progresso

- **Cutover sofa_event_id (A2)** — pré-requisitos prontos: A1 validado (fill ~100%) + filtro de competição (anti-FP) + discovery nativo (Sprint N). Falta wiring no loop. Ver seção dedicada abaixo.
- **Smoke real D.0 + D.2** — Validar telemetria + matches em jogo de liga monitorada ao vivo (Conmebol ao vivo agora dá a janela).

## Próximas fases (Caminho A soft restante)

### Fase E.2 — WebSocket push stats (opcional, ~6-10h)
- `wss://www.betano.bet.br/sbpitches/statsstream/matchhub` (SignalR)
- Substitui polling 15s por push real-time
- **Não bloqueia caminho A** — só se polling ficar lento pra decisões críticas

### Fase F.2 — Substituição `api_client.get_events` interno (~1-2h)
- Único caller (`api_client.get_fixture_result`, post-FT corner fallback) ainda usa AF.
- Substituir por `EventsHistoryRepo.get_by_type_in_window(fixture, 'CRNR')` quando dataset Betano comprovar cobertura ≥ AF empíricamente (~1-2 semanas de capturas).
- Sem urgência — post-FT é cold path, AF cota baixa.

### Fase H — Refactor remover `api_client.*` de runtime (~4-6h)
- E.1 + F + G entregues. F.2 pendente. AF residual = discovery + resultado FT.

### Fase I — Otimização + cache + testes integração (~8-15h)

TODOs registrados durante fases anteriores (consolidar em sprint dedicado):

- **Cache compartilhado `/event/<id>/state`** entre `BetanoStatsWorker`
  (Fase E.1) e `BetanoEventsWorker` (Fase F) via store in-memory
  (TTL ≈ 10s, key=event_id). Reduz ~50% chamadas ao renewer. Volume
  atual sustentável (~5.4 MB/min ao danewell, infra local). Implementar
  quando volume escalar (> 15 jogos simultâneos).
- **Cache 304 do bridge dead-code em produção** — bridge TTL=3s <<
  worker poll=15s. Reavaliar TTL ou frequência de poll.
- **AF unmapped types**: review semanal dos logs `events_adapter.af.unmapped_type`
  + `unmapped_var` pra detectar tipos novos AF não cobertos (`_AF_TYPE_MAP`
  em `data/providers/apifootball/events_adapter.py`).
- **Cleanup TTL nos dicts de throttle**: evictar fixtures não-acessados há
  > 2h (containers long-running vazam memória lenta sem isso). Dicts
  afetados:
  * `main.py::_last_capture_at` (odds telemetria — Fase D.0)
  * `main.py::_last_events_capture_at` (events captura — Fase F)
  * `BridgeStatsAdapter::_version_cache` + `_last_stats_cache` (Fase E.1)
  * `BridgeEventsAdapter::_event_id_cache` (Fase F)

**Total Caminho A soft restante:** ~13-25h em 3-5 sessões (após G entregue: F.2 + H + I + cache compartilhado).

## Caminho A hard — Cutover `sofa_event_id` (eliminar AF completamente)

Branch `feat/remove-af-completely`. Plano de 3 etapas (migration 0013): A1 dual-key
→ A2 cutover (sofa vira primária) → A3 deprecar `fixture_id` (AF sai). Fase K
(SofaScore na cascata) ✅ em produção é o pré-requisito de dados.

### A1 — Dual-key `sofa_event_id` ✅ VALIDADO (2026-05-20)
Shadow column em 6 tabelas + `af_sofa_fixture_map`. Fill estava 0% no `bridge_betano`
(gargalo: workers não chamavam o resolver live). Corrigido + **validado em produção
0% → 100%** com jogos Conmebol ao vivo. Filtro de competição no resolver mata FP
cross-competição. Ver BUGS.md 2026-05-20.

### Sprint N — Achados SofaScore (capture .mitm 2026-05-20) + componentes do A2
Capturado via F12+mitmproxy, analisado, **testado ao vivo**:
- 🟢 **WebSocket NATS** (`wss://ws.sofascore.com:9222`) — push em tempo real de
  placar/status/**FT**/cardsCode. Cliente `data/providers/sofascore/ws_client.py`
  (curl_cffi impersonate, thread+asyncio.Queue, parser NATS testado). **NÃO é
  fonte de stats** (sem escanteios/posse) — é notificador-de-mudança + FT.
- 🟢 **Discovery por torneio** (`/unique-tournament/{tid}/scheduled-events/{date}`)
  — `SofaScoreClient.get_tournament_scheduled_events` + `discovery.py`. Testado:
  28 jogos das 13 ligas hoje, keyed por `sofa_event_id`, sem AF.
- 🔴 **Odds SofaScore descartadas** — `/event/{id}/odds/{provider}/all` só tem
  "Full time" (1X2), provider BR = bet365. Sem escanteios/cartões. Odds continuam
  no bridge Betano.
- Flags `SOFASCORE_WS_ENABLED` / `SOFASCORE_DISCOVERY_ENABLED` (default OFF — código
  pronto e testado, não fiado no loop ainda).

### A2 — Cutover (próximo) — `sofa_event_id` vira chave primária
Pré-requisitos prontos (A1 validado + filtro anti-FP + discovery + WS).

**Já fiado (atrás de flags, default OFF):**
- ✅ **Shadow discovery** (`SOFASCORE_DISCOVERY_ENABLED`) — `_shadow_discovery_compare` roda `discover_scheduled` em paralelo ao AF e loga `[A2-SHADOW]` (matched/af_only/sofa_only) via `discovery.compare_coverage`. NÃO muda o que é monitorado; gera o dado de validação do passo 4. Ativar e observar logs antes de promover a fonte.
- ✅ **WS FT→settle** (`SOFASCORE_WS_ENABLED`) — `_ws_settle_loop` no `main.py` dispara settle imediato no FT do firehose NATS (parte do passo 2).

**Falta:**
1. Promover `discovery.discover_scheduled` a **fonte** da agenda (hoje só shadow), AF como fallback — depende do passo 3 (loop navega por `fixture_id` AF).
2. Smart-polling: re-buscar `/statistics` só no delta do WS (reduz poll cego 30s).
3. Promover `sofa_event_id` a chave de leitura nas queries (hoje ainda `fixture_id`).
4. Validar FP/cobertura com volume real (via `[A2-SHADOW]`) antes de flipar as flags.

### A3 — Deprecar `fixture_id` / remover AF do runtime
Quando A2 estável: `get_live_fixtures` + `get_today_schedule` saem (substituídos por
WS firehose + discovery por torneio); `get_fixture_result*` sai (FT via WS). AF
residual zero no runtime quente.

## On Hold

### Fase J — Pré-jogo + Estudo de Times (~75-105h, 3-4 sprints)

**Status:** aprovada conceitualmente, aguarda fundação. Mapeamento em andamento com colaborador externo (2026-05-17).

**Objetivo:** trazer análises pré-jogo estilo SportyTrader pro dashboard CPES + página de estudo de times. Diferencial competitivo vs tipsters genéricos: análise embasada no próprio dataset capturado (E.1 + F + G).

**Escopo:**
1. **Página "Análise Pré-Jogo" por fixture** — últimos N jogos cada time (casa/fora), H2H histórico, palpite principal com confiança %, lista de palpites secundários, estatísticas resumidas, texto narrativo (template + AI leve opcional).
2. **Página "Estudo de Times"** — performance casa vs fora, padrões detectados (queries pré-computadas), histórico H2H matriz, próximos jogos com palpites, gráficos temporais.
3. **Importação histórico AF** (10-15h) — 2-3 temporadas das ligas monitoradas, popula tabelas existentes, ~1000-3000 jogos por liga.
4. **Heurística de palpite** (15-25h) — cálculo de confiança via regras, pré-computado (não em tempo real), atualiza a cada novo jogo capturado.
5. **Texto narrativo** — opção (a) templates puros, zero AI; opção (b) AI leve (Claude Haiku) ~$30/mês.

**Pré-requisitos:**
- Fase H entregue (AF residual)
- Fase I entregue (otimização)
- V2 Dashboard entregue (Minhas Apostas + Banca)
- Dataset com 4-6 semanas de captura própria + import histórico AF

**Por que ON HOLD:**
- V2 Dashboard tem prioridade pra monetização Max R$89,90
- Caminho A soft precisa fechar primeiro (Fase H, I)
- Dataset precisa amadurecer
- 75-105h é peça grande, merece sequenciamento dedicado

**Retomar quando:**
- Primeiros 50+ clientes Pro/Max ativos
- Caminho A soft completo
- Dataset estável > 1000 jogos capturados

**Valor comercial esperado:**
- Tier Pro: análises básicas (templates simples)
- Tier Max: análises premium (AI texto + padrões avançados)
- Potencial novo tier "Quant Pro" R$199,90: estudo de times completo + todas análises + export de dados

## Fases Quant (longo prazo)

### Fase H1 — Telemetria refinada (4-6 semanas após Fase D.0 ligada)
Dataset acumulado, schema enriquecido se faltar.

### Fase H2 — Modelo de pricing
Treinar com dataset. LightGBM/XGBoost. Prevê odd futura baseado em stats.

### Fase H3 — Modelo de projeção
Projeta evento futuro (escanteios/cartões/gols) com intervalos de confiança.

### Fase H4 — Backtest engine
Roda estratégia hipotética sobre dataset histórico. Calibra parâmetros.

## Fases Quant Avançadas — Sinais Valor (H_VALOR)

**Status:** documentado, **ON HOLD** (aguarda fundação). Visão mestre completa em
`docs/architecture/sinais-valor-vision.md`; regras no `CLAUDE.md` §14; ADR em
`docs/DECISIONS.md` (2026-05-22).

Nova categoria de sinais focada em edge matemático sustentável em múltiplos mercados
(1X2, BTTS, Over/Under, AH, etc), via dataset acumulado + modelos LightGBM. Sinais
raros (1-5/semana), odds 1.40-1.70 ("linhas maduras"), stake 20-50% banca (decisão
Daniel — alto risco assumido). 3 pilares: Histórico 40% + Contexto 30% + Live 30%.

- **H_VALOR.0 — Investigação (~6-10h):** catalogar 10-15 mercados Betano, validar cobertura histórica SofaScore, features por pilar, thresholds preliminares.
- **H_VALOR.1 — Schema + captura (~15-25h):** tabelas novas (`team_form_history`, `team_context_snapshots`, `odds_pre_match_history`, `sinais_valor`, `sinais_valor_features` — renumerar a migration, 0017 está usado) + workers de captura. Dataset começa a acumular.
- **H_VALOR.2 — Modelo Histórico (~25-40h):** LightGBM por mercado (3-5 inicial), walk-forward, calibração de probabilidade.
- **H_VALOR.3 — Pilares 2+3 + integração (~30-50h):** modelos Contexto + Live, composição multi-pilar, `SinaisValorEmitter`.
- **H_VALOR.4 — Backtest + tier comercial (~20-35h):** engine de backtest, dashboard Quant Pro, tier R$199,90 (proposta).

**TOTAL:** ~95-160h em 6-12 meses.

**Pré-requisitos bloqueantes:** Fase H A3 completa (`sofa_event_id` chave única) ·
V2 Dashboard estável · dataset 4-6 meses · 50+ clientes Pro/Max ativos.

**Pendências de decisão Daniel (antes de H_VALOR.0):** rankear mercados prioritários ·
confirmar tier comercial · validar nome final.

**Captura de dados antecipada (~18h, opcional):** workers leves de pre-match odds +
team form + contexto podem começar em paralelo — **mas só pós-A3 estável**. Não é
"em progresso": é candidato a iniciar depois que o cutover `sofa_event_id` fechar.

> **Próxima ação de engenharia continua sendo Fase H A2** — não tocar H_VALOR ainda.
