# SofaScore API — Investigação K.0

**Data:** 2026-05-17  
**Branch:** `feat/sofascore-integration`  
**Status:** investigação fechada — CASO α PURO confirmado  
**Decisão:** seguir K.1 implementação direta via `curl_cffi` (impersonate Chrome)

---

## TL;DR

- **Anti-bot:** TLS fingerprint (JA3) — bloqueia curl/requests/aiohttp simples (403 Varnish).
- **Bypass validado:** biblioteca Python `curl_cffi` com `impersonate='chrome120'` passa 200 OK direto do servidor CPES (mesmo IP residencial 200.181.212.29 que bloqueava com curl simples). **Zero infraestrutura adicional.**
- **Rate limit:** 70 reqs em <1.5s (~47 req/s) → 100% 200 OK. Sem rate limit visível no volume CPES.
- **Cobertura:** 31/38 endpoints validados via captura de browser real (mitmproxy). Inclui stats ricas (3 períodos × 7 grupos), lineups com `missingPlayers` (lesões/suspensões), `/managers` endpoint dedicado (**resolve gap `coach_name` do Betano**), standings completa Brasileirão (20 times com posição/pontos/G+/G-/promotion).
- **Endpoints novos vs AF:** coach, standings com promotion (Libertadores/relegation), missingPlayers (lesões+suspensões com expectedEndDate), team-performance-graph (gráfico temporal), best-players summary, pregame-form, average-positions, win-probability graph.
- **Estimativa K.1:** ~25-35h (CASO α puro), 4 novos adapters + 1 worker novo (standings) + integração 3 Composites existentes (Betano primary → SofaScore fallback, AF sai do runtime quente).

---

## 1. Anti-bot

### 1.1 Sintoma

Curl simples retorna `403 Forbidden` (server: Varnish) em todos endpoints, incluindo `https://www.sofascore.com/` home page. Vale pra qualquer header convencional (User-Agent Firefox/Chrome, Origin, Referer corretos).

```
HTTP:403 | server: Varnish | body: {"error":{"code":403,"reason":"Forbidden"}}
```

### 1.2 Causa raiz: JA3 fingerprint

SofaScore (provavelmente via [DataDome](https://datadome.co) ou similar) inspeciona o **TLS Client Hello** e bloqueia fingerprints conhecidos de bibliotecas automatizadas (curl, Python requests, aiohttp, etc). Browser real tem cifras + extensões TLS + ordem específica que não é replicável por essas libs.

Evidência: Daniel acessou normal pelo Firefox no mesmo IP/máquina onde curl dava 403. Headers HTTP idênticos não passam — diferença é só na camada TLS.

### 1.3 Bypass: `curl_cffi`

`curl_cffi` ([repo](https://github.com/lexiforest/curl_cffi)) é binding Python pra `libcurl-impersonate`, fork do libcurl que replica TLS handshake de Chrome/Firefox/Safari. API estilo `requests`:

```python
from curl_cffi import requests as cr
r = cr.get(url, impersonate='chrome120', timeout=10)
```

Validado do servidor CPES (Ubuntu 22.04, mesmo IP que dava 403 com curl):

```
GET /api/v1/sport/football/events/live       → HTTP:200, 47 jogos live
GET /api/v1/event/15171563                   → HTTP:200, 8K
GET /api/v1/event/15171563/statistics        → HTTP:200, 24K
GET /api/v1/event/15171563/lineups           → HTTP:200, 65K
GET /api/v1/event/15171563/incidents         → HTTP:200, 34K
GET /api/v1/event/15171563/managers          → HTTP:200, 584B
GET /api/v1/event/15171563/best-players/...  → HTTP:200, 5K
GET /api/v1/event/15171563/pregame-form      → HTTP:200, 189B
GET /api/v1/unique-tournament/325/season/87678/standings/total → HTTP:200, 19K
GET /api/v1/team/5133/events/next/0          → HTTP:200, 92K
GET /api/v1/team/5133/events/last/0          → HTTP:200, 129K
```

10/10 endpoints testados passaram. Sem cookies prévios, sem warmup, sem nada.

### 1.4 Rate limit empírico

Stress test do servidor CPES (sequencial, sem paralelo):

| Volume | Tempo | Throughput | Status |
|---|---|---|---|
| 20 reqs | 0.4s | 46.5 req/s | 20× 200 |
| 50 reqs | 1.0s | 47.7 req/s | 50× 200 |

Sem rate limit detectado nesse volume. Pra contexto: CPES atualmente faz ~1 req / 15s por fixture × ~5 fixtures simultâneos = ~0.3 req/s. Margem >150×.

Sugestão K.1: throttle defensivo cliente-side de 10 req/s (= 600/min, ainda 6× sobra). Reavaliar se 429 começar a aparecer.

### 1.5 Headers funcionais (browser captura)

Do HAR (995 requests 200 OK), browser sempre manda:

```
user-agent: Mozilla/5.0 (X11; Linux x86_64; rv:150.0) Gecko/20100101 Firefox/150.0
accept: */*
accept-language: en-US,en;q=0.9
accept-encoding: gzip, deflate, br, zstd
referer: https://www.sofascore.com/ (ou /pt, /football/...)
sec-fetch-dest: empty
sec-fetch-mode: cors
sec-fetch-site: same-origin
```

`curl_cffi` cuida do TLS e header `accept-encoding` (zstd suportado). Adapter deve setar `referer` válido pra evitar 403 anti-leech futuro. `user-agent` é redundante com `impersonate=` mas pode reforçar.

`x-requested-with: ecd1c6` aparece em ~30% dos 200s — **não é universal**, parece interno do app SPA. Não precisa replicar.

---

## 2. Endpoints mapeados

Path base: `https://www.sofascore.com/api/v1/`

### 2.1 Discovery / live (4 endpoints)

| Endpoint | Status | Tamanho | Conteúdo |
|---|---|---|---|
| `/sport/football/events/live` | 200 | 192K | Todos jogos rolando agora (47 no momento da captura) — id, slug, tournament, homeTeam, awayTeam, status, time, scores |
| `/sport/football/scheduled-events/{date}/page/{n}` | 200 | — | Agenda do dia (paginada) |
| `/sport/football/categories/all` | 200 | 103K | Catálogo de países/competições |
| `/sport/football/live-tournaments` | 200 | 352B | IDs das competições com jogos live agora |

### 2.2 Evento individual (10+ endpoints)

| Endpoint | Status | Tamanho | Conteúdo / chaves principais |
|---|---|---|---|
| `/event/{id}` | 200 | 8K | Detalhe: tournament, season, roundInfo, venue, referee, homeTeam, awayTeam, scores, status, time |
| `/event/{id}/statistics` | 200 | 24K | **3 períodos** (ALL, 1ST, 2ND) × **7 grupos** (Match overview, Shots, Attack, Passes, Duels, Defending, Goalkeeping). Inclui xG live, ball possession, total shots, on target, hit woodwork, blocked, big chances scored/missed, through balls, touches in penalty area, fouled in final third, offsides, ground duels, aerial duels, dribbles, tackles, interceptions, blocks, recoveries, saves, goalkeeper saves |
| `/event/{id}/lineups` | 200 | 65K | `confirmed`, `home/away`: `formation`, `players[]` (player.name, jerseyNumber, position, captain, substitute, **statistics**), `supportStaff[]`, **`missingPlayers[]`** (★ lesões+suspensões), `playerColor`, `goalkeeperColor`, `statisticalVersion` |
| `/event/{id}/incidents` | 200 | 34K | Timeline de eventos: gols, cartões, escanteios, substituições, VAR. Schema diferente do Betano `event.incidents` |
| `/event/{id}/managers` | 200 | 584B | **★★★ `homeManager`/`awayManager`** = `{name, slug, shortName, id, fieldTranslations}`. **Resolve gap BETANO_GAPS_LINEUPS** |
| `/event/{id}/best-players/summary` | 200 | 5K | Top jogadores do jogo com ratings |
| `/event/{id}/graph` | 200 | 2K | Gráfico temporal de ataque/pressão (xG ao longo do tempo?) |
| `/event/{id}/graph/win-probability` | 200/404 | — | Probabilidade de vitória ao longo do tempo (não tem pra todo jogo) |
| `/event/{id}/average-positions` | 200 | 31K | Posição média de cada jogador no campo (heatmap-light) |
| `/event/{id}/heatmap/{playerId}` | 200 | — | Heatmap individual do jogador |
| `/event/{id}/pregame-form` | 200 | 189B | Forma recente de cada time (W/D/L últimas 5) |
| `/event/{id}/h2h` | 200 | 69B | Head-to-head sumário |
| `/event/{id}/highlights` | 200 | 920B | Vídeos curtos do jogo |
| `/event/{id}/odds/{provider}/all` | 200 | 1K | Odds (markets diversos) |
| `/event/{id}/ai-insights/pt` | varia | — | Insights AI em pt-BR (★ útil pra narração K-Fase J) |

### 2.3 Time individual (5+ endpoints)

| Endpoint | Status | Conteúdo |
|---|---|---|
| `/team/{id}/players` | 200 | Squad completo (com `marketValueRaw`, `dateOfBirth`, `country`, `position`, `jerseyNumber`) |
| `/team/{id}/events/next/{page}` | 200 | Próximos N jogos do time |
| `/team/{id}/events/last/{page}` | 200 | Últimos N jogos |
| `/team/{id}/unique-tournament/{tid}/season/{sid}/statistics/overall` | varia | Stats acumuladas temporada (cobertura parcial) |
| `/team/{id}/unique-tournament/{tid}/season/{sid}/goal-distributions` | 200 | Distribuição de gols por minuto |
| `/team/{id}/team-statistics/seasons` | varia | Histórico de stats por temporada |
| `/team/{id}/standings/seasons` | 200 | Temporadas em que o time apareceu em standings |

**Não existe endpoint dedicado `/injuries`** — lesões vêm via `event/{id}/lineups.{side}.missingPlayers[]` (escopo: jogo específico, não geral). `type` ∈ {`missing`, `doubtful`}, `reason` numérico (mapping a investigar K.1), `expectedEndDate` timestamp.

### 2.4 Torneio / liga (5 endpoints)

| Endpoint | Status | Conteúdo |
|---|---|---|
| `/unique-tournament/{id}/seasons` | 200 | Lista temporadas (atual + históricas) |
| `/unique-tournament/{id}/season/{sid}/standings/total` | 200 | **★ Tabela completa**: position, matches, wins, draws, losses, scoresFor, scoresAgainst, points, scoreDiffFormatted, **`promotion`** (`text: "Copa Libertadores"`, `id: 19`) |
| `/unique-tournament/{id}/season/{sid}/info` | 200 | Info da temporada (formato, equipes) |
| `/unique-tournament/{id}/season/{sid}/cuptrees` | varia | Chaveamento mata-mata (não aplicável a liga regular) |
| `/unique-tournament/{id}/season/{sid}/team/{teamId}/team-performance-graph-data` | 200 | **Gráfico temporal de performance do time** (rating + posição ao longo de rodadas) |
| `/unique-tournament/{id}/scheduled-events/{YYYY-MM-DD}` | 200 | Agenda do dia daquela liga |
| `/tournament/{id}/season/{sid}/standings/total` | 200 | Alternativa pra `unique-tournament` (geralmente usar `unique-tournament`) |
| `/tournament/{id}/season/{sid}/team-events/total` | 200 | Todos jogos da temporada (matriz completa) |

### 2.5 Misc / config

| Endpoint | Conteúdo |
|---|---|
| `/config/top-unique-tournaments/BR/football` | Top ligas pra usuário BR |
| `/config/country-sport-priorities/country/BR` | Prioridade de esportes BR |
| `/odds/providers/BR/web` | Lista de operadoras de aposta BR (Betano incluído) |
| `/sofascore-news/pt/posts` | News em pt-BR |
| `/sport/football/trending-top-players` | Players trending |

---

## 3. Mapping IDs (descoberto via HAR)

| Liga | `uniqueTournament.id` | Season exemplo |
|---|---|---|
| **Brasileirão Série A** | **325** | 87678 (atual) |
| **Premier League** | **17** | (a confirmar) |
| **MLS** | **242** | 86668 (atual) |
| **(outras a mapear via /seasons em K.1)** | | |

Mapping completo K.1: query `/api/v1/unique-tournament/{candidato}/seasons` pra cada liga monitorada (CPES tem 11 hoje). Salvar em `data/sofascore_league_map.json` ou tabela.

---

## 4. Comparativa de cobertura (Betano vs SofaScore vs AF)

| Campo / Dado | Betano (bridge) | SofaScore | AF (residual) |
|---|---|---|---|
| corners_total | ✅ | ✅ | ✅ |
| yellow_cards | ✅ | ✅ | ✅ |
| red_cards | ✅ (via incidents) | ✅ | ✅ |
| shots_total | ✅ | ✅ (sep. 1ST/2ND/ALL) | ✅ |
| shots_on_target | ❌ (gap) | ✅ | ✅ |
| shots_off_target | ❌ | ✅ | ✅ |
| blocked_shots | ❌ | ✅ | parcial |
| hit_woodwork | ❌ | ✅ | ❌ |
| ball_possession | ✅ | ✅ | ✅ |
| xG live | ✅ | ✅ | ❌ |
| big_chances | ❌ | ✅ | ❌ |
| dangerous_attacks | ✅ (provider_pressure) | parcial | ✅ |
| Stats por **período** (1H/2H/ALL) | ❌ | ✅ ★ | ❌ |
| Lineup formation | ✅ | ✅ | ✅ |
| Lineup players + shirt/pos | ✅ (com gap unknown) | ✅ | ✅ |
| **Coach name** | ❌ (BETANO_GAP) | **✅ /managers** | ✅ |
| **Lesões/suspensões** | ❌ | **✅ /lineups.missingPlayers** | ✅ parcial (/injuries) |
| **Standings (classificação)** | ❌ | **✅ rich (com `promotion`)** | ✅ |
| H2H histórico | ❌ | ✅ | ✅ |
| Próximos jogos team | ❌ | ✅ | ✅ |
| Team season stats | ❌ | ✅ parcial | ✅ |
| **Team performance graph** | ❌ | **✅ (NOVO)** | ❌ |
| **Best players / ratings** | ❌ | **✅ (NOVO)** | ❌ |
| **Pregame form (W/D/L últ 5)** | ❌ | **✅ (NOVO)** | parcial |
| **Average positions** | ❌ | **✅ (NOVO)** | ❌ |
| **Win probability graph** | ❌ | **✅ (NOVO)** | ❌ |
| **AI insights pt-BR** | ❌ | **✅ (NOVO — útil pra Fase J narrativa)** | ❌ |
| Highlights vídeo | ❌ | ✅ | ❌ |

**Conclusão:** SofaScore preenche 100% do que AF preenche + 6 categorias novas que nenhum dos dois cobre + resolve `coach_name` gap do Betano.

---

## 5. Estratégia K.1 (proposta)

### 5.1 Cascata atualizada

```
Stats:    bridge_betano  →  sofascore         (Composite existente, troca fallback)
Events:   bridge_betano  →  sofascore         (Composite existente, troca fallback)
Lineups:  bridge_betano  →  sofascore         (Composite existente, troca fallback)
                              + coach via /managers (gap Betano resolvido)
                              + missingPlayers (lesões — NOVO no schema CanonicalLineup)

NOVOS workers (dataset puro):
  - StandingsWorker (1 captura por liga/dia)
  - TeamFormWorker  (pregame-form ao iniciar fixture)
  - BestPlayersWorker (pós-FT, ratings)
```

AF runtime sai (Fase K renumerada vira "M" se quiser; ou K.2). Vira super-residual:
- Discovery `get_today_schedule` (1 req/liga/dia)
- Resultado FT cross-check (cold path)

### 5.2 Arquitetura adapter

`SofaScoreClient`: wrapper async sobre `curl_cffi.AsyncSession(impersonate='chrome120')`. Métodos:
- `get_live_events()`, `get_event(id)`, `get_statistics(id)`, `get_lineups(id)`, `get_incidents(id)`, `get_managers(id)`, `get_standings(unique_tid, season_id)`, `get_team_next(team_id)`, `get_team_form(event_id)`, etc.

Adapters canônicos:
- `SofaScoreStatsAdapter` → `CanonicalStats` (preenche shots_on_target/etc que Betano não cobre — vira upgrade da Composite, não só fallback)
- `SofaScoreEventsAdapter` → `CanonicalEvent`
- `SofaScoreLineupsAdapter` → `CanonicalLineup` (preenche `coach_name` via `/managers` + `missing_players` extensão schema)

Persistência:
- `standings_history` (migration 0008)
- `team_form_history` (migration 0009)
- `best_players_history` (migration 0010 — pós-FT)

### 5.3 Estimativa K.1: 25-35h

| PARTE | Escopo | Esforço |
|---|---|---|
| A | SofaScoreClient + mapping leagues + auth/rate-limit guard | 4-6h |
| B | 3 adapters Composite (stats/events/lineups) + extensão CanonicalLineup (coach_name preenchido + missingPlayers) | 6-8h |
| C | 3 workers novos + migrations + repos (standings, team-form, best-players) | 6-9h |
| D | Wiring main.py + retirada AF runtime (preserva discovery/FT) | 3-4h |
| E | ~30 testes | 4-5h |
| F | Smoke leve + real + docs | 2-3h |

---

## 6. Riscos identificados

| Risco | Severidade | Mitigação |
|---|---|---|
| `curl_cffi` exige `libcurl-impersonate-chrome` (binário C) no container | Médio | Adicionar ao `Dockerfile` (1 linha apt install OU pip wheel já traz binário). Validar em rebuild. |
| SofaScore mudar JA3 fingerprint (atualização anti-bot) | Médio | `impersonate=` aceita versões (chrome116, chrome120, chrome124). Trocar version se necessário. Sentry alert em 403 burst. |
| Rate limit subir (4 sources × N fixtures) | Baixo | Throttle defensivo 10 req/s. SemPhore async. |
| Cobertura SofaScore por liga regional inconsistente (ex: Liga Panamá) | Baixo | Mesma dinâmica E.1/G.1 (zero coverage → cai pra... AF? OU mantém zero). Decisão K.1. |
| Cookies de bootstrap necessários no futuro | Baixo | Adicionar warmup via `/` HTML antes de batch (igual Brave). |

---

## 7. Artefatos da investigação (preservados)

- `/tmp/sofa-samples/*.json` — 31 sample responses (uma por endpoint chave)
- `/home/daniel/cornerpressureelite/sofa-fixed.har` — HAR recuperado (3179 requests, 82MB)
- `sofa.har` original em 71MB (truncado no meio da captura por mitmweb ainda escrevendo)
- `/tmp/sofa-capture/RUNBOOK.md` — instruções de captura via mitmweb (caso precise re-capturar)

Re-execução do test: `python3 -c "from curl_cffi import requests as cr; print(cr.get('https://www.sofascore.com/api/v1/sport/football/events/live', impersonate='chrome120').status_code)"`

---

## 8. Próxima ação

PR K.0: doc + ADR + commit. **NÃO toca código de produção.**

Pausar antes de K.1 pra revisão da estratégia + estimativa.

K.1 abre PR separado em `feat/sofascore-integration`. Merge em `feat/betano-bridge-adapter` (branch atual de prod) só depois de smoke real validado.
