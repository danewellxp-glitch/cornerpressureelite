# CHANGELOG

Resumo narrativo do que mudou por sessão. Não substitui git log — contextualiza decisões e dores. Última coisa que sessão escreve antes de fechar.

> **Escopo:** sessões inteiras (1 entrada por sessão). Changelogs de entregas individuais antigas estão em `docs/changelog/YYYY-MM-DD-*.md` (leitura histórica — convenção descontinuada após 2026-05-15).

**Formato:**
```
YYYY-MM-DD — Título curto da sessão
Contexto: o que motivou a sessão
O que foi feito: lista alto nível
Bugs encontrados: (se houver, linkar BUGS.md)
Decisões: (se houver, linkar DECISIONS.md)
Estado final: o que ficou rodando, o que ficou pendente
Próximos passos: (opcional)
```

---

## 2026-05-17 — PRIORIDADE 4 quick-win: cron preventivo Brave (mitiga renewer 502)

**Contexto:** P5 amplificou dependência do renewer (out = TODOS sinais bloqueados). 3 ocorrências documentadas de Brave stuck (`fetch() TypeError: Failed to fetch`) com `/health` superficial retornando 200 mesmo durante outage. Hipótese root cause (PARTE 3 investigação read-only): JavaScript runtime accumulation em pages live da Betano após ~24-40h uptime — renderer Brave acumula handlers SignalR/Vue, `fetch()` interno via CDP começa a falhar mas CDP `/json/version` ainda responde.

**O que foi feito:**

- `docs/setup/danewell-brave-restart.sh` (snapshot do script `/home/danewell/restart-brave.sh` no danewell): SIGTERM + SIGKILL fallback + setsid respawn preservando profile em `/home/danewell/brave-betano-profile/` (cookies CF intactos). Valida via `/json/version` no CDP 9224 pós-restart. Log em `/tmp/brave-cron.log`. Script idempotente.
- Crontab `0 4,16 * * *` instalado em `crontab -u danewell` (04:00 e 16:00 BRT — madrugada profunda + pré-jogos noturnos pra minimizar overlap com sinais ativos). ~15-20s downtime × 2/dia = 0.05% total.
- Smoke manual executado: script roda OK (`exit_code=0`), Brave novo PID 221557, renewer responde HTTP 200 em 6.9s pós-restart.
- `docs/OPERATIONS.md` ganha seção "Restart preventivo Brave do pool" com runbook + comando manual ad-hoc.

**Investigação PARTE 3 — dados coletados:**
- Profile size: 137 MB (saudável, não inflado)
- Cache: 15 MB (sem pollution)
- Cookies CF: modificados há 4min (frescos, não é expiração)
- RAM Brave: ~22% total (~1.1 GB) — dentro do esperado pra Chromium
- GPU process: 30.5% CPU sustained (alto)
- Renderer principal: 16.5% CPU sustained (alto)
- 4 restarts do renewer.service em 24h (3 em 16/05 + 1 hoje)
- `/health` atual checa só `/json/version` (superficial — confirmado "200 OK silente")

**Pendência P4 PARTE 1 — supervisor reativo:** `/health/deep` (fetch real) + daemon `BraveSupervisor` (30s interval, 2 threshold, 10min cooldown). Cobre os ~10% residuais (degradação antes dos 12h preventivos). ~3-4h de trabalho, fica pra próxima sessão. P5 mitiga impacto residual (silêncio em vez de sinal errado).

**Estado final:** Cron preventivo ATIVO em produção. Primeiro restart automático amanhã 04:00 BRT. P5 + cron cobrem ~95% dos cenários; supervisor pendente fecha os 5% restantes.

---

## 2026-05-17 — PRIORIDADE 5: refetch just-before-send + telemetria + timestamp (fidelidade sinal)

**Contexto:** Investigação do sinal #127 (Osasuna vs Espanyol, 15:47:22, linha 9.5 odd 1.42) confirmou que linha+odd ESTAVAM corretas no momento da captura, mas a janela captura→DB→WAHA→user_abrir_betano (5-65s) deixa odd defasada. 30s depois odd já era 1.67; 4min depois linha 9.5 sumiu (10º corner saiu).

**Opção B aprovada pelo user**: refetch composite_odds antes do send_signal, aborta se mudança brusca.

**O que foi feito (2 commits):**

- `0cce1a4` — `engine/odds_refetch.py` com `refetch_validate_corners/cards`. 5 condições de ABORT (filosofia D4 silêncio>erro): `refetch_none` (bridge falhou + cache vazio), `refetch_stale` (cache TTL excedido), `line_changed` (mercado fechou aquela linha), `odd_drift > 15%` (mercado movimentou), `refetch_exception`. Se drift dentro da tolerância, atualiza `jogo.odd_atual` com odd fresh. Configs `ODDS_REFETCH_BEFORE_EMIT` (default true — fail-safe) + `ODDS_REFETCH_MAX_DRIFT_PCT` (0.15). Aplicado em main.py:1380 (corners) e 1447 (cards). 10 tests novos.
- `58e44b1` — `migrations/0010_blocked_signals.sql` (tabela telemetria com fixture, market, linha, reason, orig_odd, fresh_odd, drift_pct, metadata jsonb). `BlockedSignalsRepo.insert` swallow-on-error (telemetria não pode quebrar pipeline). Refetch ganha kwarg `blocked_repo`. main.py instancia + injeta. `message_formatter.py` adiciona `⏱️ *Odd capturada:* HH:MM:SS (snapshot — odd pode variar segundo-a-segundo)` no bloco MERCADO (Opção C complementar).

**Latência adicional:** ~0ms quando bridge cache 3s ainda válido (cache hit); ~5-8s quando cache miss (chamada bridge nova). Cache hit é o caso normal pq cycle entre captura inicial e refetch é < 3s tipicamente.

**Smoke:** 57/57 tests verde. Migration 0010 aplicada via `_apply_sql_migrations`. Mensagem WhatsApp renderiza timestamp explícito. **Zero sinais novos no smoke real** (final de domingo, decision_engine filtra agressivamente por janela/threshold), então refetch+blocked não exercitados em produção. Validação efetiva acontecerá organicamente em jogos com mais movimento na semana.

**Estado final:** P5 ✅ wireado. Próximo sinal emitido vai passar pelo refetch obrigatoriamente, blocked rows aparecerão em `blocked_signals` quando aplicável. Mensagem WhatsApp já comunica explicitamente que odd é snapshot.

**Pendências:**
- Validação real do refetch quando sinais começarem a fluir
- P4 (renewer supervisor) continua aberto — gargalo operacional principal

---

## 2026-05-17 — PRIORIDADE 4-B: cache stale TTL adaptativo + AF removido runtime odds

**Contexto:** Decisão D4 aprovada — ZERO AF no path runtime de odds. Cache stale assume quando bridge falha; cache expirado = sinal bloqueado (sistema silente em outage extremo). AF continua em discovery + cold checks.

**O que foi feito (4 commits):**

- `9ca3481` — migration `0009_odds_stale_tracking.sql` (is_stale BOOL + source_age_seconds INT idempotente, index parcial). `OddsCache` com TTL adaptativo D1 (corners/cards 30s, goals 20s, match_winner 15s). `CanonicalOverUnder` + `OddsHistoryEntry` ganham campos stale (back-compat). 11 tests cache.
- `13b1658` — `CachedBetanoOddsProvider`: wrapper sem AF (fresh bridge → cache fresh → cache stale → None outage). Reconnect agressivo no `BetanoBridgeClient.event_state` (4 attempts ~3.5s, backoff [0, 0.5, 1, 2]). Log `bridge.event_state.recovered` quando retry resgata. 9 tests cached.
- `866bf7d` — factory wire via flag `REMOVE_AF_FROM_ODDS_RUNTIME` (default OFF). `JogoAoVivo` ganha `odds_is_stale`/`odds_age_seconds` (corners + cartoes). Gate em `main.py`: `if jogo.odds_is_stale: log + skip send_signal + skip DM + skip registrar_sinal`. Aplicado pra corners (linha 1371) e cards (linha 1439).
- `(esta sessão)` — fix bug `name="betano_bridge_cached"` → `"betano_bridge"`: `CompositeOddsProvider._dispatch` só passa contexto rico (incluindo `persist_telemetry=True`) pra providers com nome exato `"betano_bridge"`. Sem o fix, persist em `odds_history` quebra silente.

**Smoke real (em produção pós-cutover):**

| Métrica | Pré-flag | Pós-flag (5min) |
|---|---|---|
| source=betano_bridge | 56 (100%) | 50 (100%) |
| source=apifootball | 0 | **0** ✅ |
| stale captures | 0 | 0 (cache se manteve fresh) |
| `cached.outage` logs | n/a | 1 absorvido (Brave caiu antes do restart) |

**Bugs encontrados:**
- Provider `name` precisa ser exato `"betano_bridge"` pro Composite passar `persist_telemetry`. Wrapper transparente: documentei em comment do `CachedBetanoOddsProvider`.
- Renewer 502 recorrente continua (Brave do pool stuck ~horas). Foi necessário restart manual durante o smoke. **P4 (healthcheck profundo + supervisor)** segue pendente — P4-B mitiga via cache, mas não resolve root cause.

**Tests:** 47/47 verde (11 cache + 9 cached + 27 outros não-tocados). Zero regressão.

**Decisões:**
- Default OFF mantido até validação ampla — flag `REMOVE_AF_FROM_ODDS_RUNTIME=true` ligada em produção pós-smoke OK.
- `CachedBetanoOddsProvider.name = "betano_bridge"` (transparência intencional).

**Estado final:** P4-B ✅ closed. AF zero em odds runtime. P4 (renewer supervisor) continua pendente — gargalo operacional restante.

---

## 2026-05-17 — PRIORIDADE 2: popular `betano_team_map` (Issue C resolvido)

**Contexto:** Discovery worker logava 8 matches / 100+ events skipped por ciclo (~7-8% cobertura). Newcastle, West Ham, Bologna FC, Athletic Bilbao, Celta Vigo e outros não estavam mapeados Betano↔AF — fallback 100% AF pra esses jogos. Bloqueador implícito também pro SofaScore Event Resolver (que depende de AF teams pra fuzzy match com SofaScore).

**O que foi feito:**

- `data/scripts/populate_team_map.py` (novo): cruza AF `/teams?league=X&season=Y` (12 ligas top: Premier, La Liga, Serie A, Bundesliga, Ligue 1, Eredivisie, Liga Portugal, Champions, Europa, MLS, Argentina, Brasileirão B) contra `betano_team_name` sem AF (filtra Esports/Snow/Dexter/Sub-). Fuzzy match com rapidfuzz (ratio + token_sort, sem partial — partial causa muito falso positivo).
- Dedup robusto: `best_for_betano: dict[bt_id, Proposal]` mantém maior confidence — DC United → DC United (1615, 0.94) **venceu** vs Auckland United FC (0.94); Inter Miami → Inter Miami (9568, 1.00) venceu vs Miami FC; Chicago Fire → Chicago Fire venceu vs Chicago Fire FC II.
- Output: `/tmp/team_map_proposed.json` (109 proposals) + `/tmp/team_map_updates.sql` (50 auto-OK ≥0.90 confidence). 59 review entries triados manualmente — 3 aprovados (Athletic Bilbao→531, Celta Vigo→538, Union Saint-Gilloise→1393), 56 descartados (CF Monterrey vs Montreal, Floresta vs Nottingham Forest, FK Liepaja vs Ajax, etc. — todos falsos positivos por similitude superficial).
- Applied: 53 UPDATEs (`af_league_fuzzy` + `af_league_fuzzy_manual`).

**Resultado:**

| métrica | antes | depois |
|---|---|---|
| Cobertura times com AF | 98/521 (18.8%) | **151/521 (29.0%)** |
| Discovery match rate (1 ciclo) | 8/100+ (~7%) | **10/91 (11%)** |
| Newcastle 1379337 | sem mapping | ✅ `discovery_team_id_lookup` conf=1.00 |
| West Ham, Atletico Bilbao, Celta, etc. | sem AF | ✅ mapeados |

Discovery worker pega map fresh em cold-start (cache); restart cpes-main aplica imediato. Cobertura efetiva de matches sobe relativamente mais do que cobertura absoluta porque jogos top têm 2 times com mapping (1 match = 1 par mapeado).

**Bugs encontrados:**
- Schema `betano_team_map` divergiu do playbook (sem `sofascore_team_id`/`league_id` cols) — script ajustado.
- `APIFootballClient.get_teams()` não existe; usei `_request("teams", ...)` direto.
- Container cpes-main sem `psql` — UPDATEs aplicados via `docker exec -i cpes-postgres`.
- Renewer/Brave caiu de novo durante smoke (Brave fetch() TypeError, 40h uptime issue recorrente — pendência P4). Restart via `setsid` resolveu.

**Estado final:** Issue C resolvido pra ligas top. Cobertura efetiva K.1 cascata em stats já passou de 33% pra ~100% enriched (medido nos 22 captures bridge_betano última hora). Pendência: re-rodar script periodicamente quando novas ligas/temporadas começam, e considerar popular `match_method='af_league_fuzzy_manual'` adicional na próxima sessão revisando os 56 descartados que possam ser revalidados em sequence.

---

## 2026-05-17 — PRIORIDADE 1: cutover odds → `/event/<id>/state` (Bug 1 user resolvido)

**Contexto:** Bug 1 (user): 100% das odds últimas 24h vinham via `apifootball` (1145 entradas). Bridge `/markets` retornava `text_len=0` consistentemente — anti-bot Cloudflare nukeou a rota legada `/live/_/<id>/`. CPES vende sinal de Over Escanteios + Cartões Amarelos; sem odds Betano = crise.

**O que foi feito:**

- **PASSO 0–1 — Mapeamento offline:** captura E.0 (Saudi League B) enganou — só 132 markets, zero corners. Daniel forneceu HAR nova (`escanteios.har`, La Liga) com **261 markets** em `/danae-webapi/api/live/events/<id>/latest`: **41 corner markets** (`CNOU`/`COU1`/`COF3`) + **28 card markets** (`TCOU`/`1COU`/`HCOU`/`ACOU`). Conclusão: endpoint canônico **já tem tudo**, basta filtrar por type code. Sem precisar endpoint novo.

- **PASSO 2 — Implementação:**
  - `data/providers/betano_bridge/state_markets_parser.py` (novo): função pura `extract_lines(payload, market_kind)` que filtra markets por type + extrai `(line, over_price, under_price)`. Dedup por handicap, ordem de selection swap-safe.
  - `BetanoBridgeClient.event_state()`: novo método consumindo `/event/<id>/state`.
  - `BetanoBridgeOddsAdapter`: novo param `use_state_endpoint` roteia `_from_catalog` pra `event_state` + parser. Path legado preservado intacto.
  - `config.USE_NEW_MARKETS_ROUTE` (default `false`): feature flag cutover.
  - `factory.py`: passa flag pro adapter.

- **PASSO 3 — Tests:** 10 testes parser + zero regressão no adapter (26/26 verde). Sanity contra HAR real: 8 corner lines (0.5→8.5) + 4 card lines (1.5→5.5) extraídos.

- **PASSO 4 — Smoke real em produção:**
  1. Renewer no danewell estava 502 (`fetch falhou no Chrome: TypeError: Failed to fetch`) — Brave do pool stuck há 40h. **Resolvido via SSH (alias `danewell`): kill + setsid respawn Brave preservando profile**. 3/3 attempts OK em 7s.
  2. Bridge `/event/state` validado live (Sevilla x Real Madrid: 260 markets, 5 corner lines, 3 card lines).
  3. Flag ativada + restart cpes-main → 0 capturas bridge_betano. Diagnóstico: container rodava `config.py` velho (não está no volume mount). `docker compose up -d --build main` resolveu.
  4. **Resultado pós-rebuild (10min smoke):**
     - `betano_bridge`: **56 captures (77.8%)** — era 0% antes
     - `apifootball`: 16 captures (22.2%) — residual quando bridge falha
     - Latência média: **0.087s** (cache hit `/event/state`)
  5. Decision engine intocado, bloqueios por janela/threshold (esperado).

**Bugs encontrados:**

- Bug D (meu, E.1 PARTE B): `Response(content=None)` com Content-Length gera `RuntimeError` no uvicorn. Fix: `Response(status_code=304)` bare. Commit `12d1017` em bridge.
- Bug operacional: Brave do pool stuck 40h sem detecção (health endpoint superficial só checa CDP, não `fetch()`). Tratável via restart manual; valeria considerar healthcheck que faz fetch real.
- Bug arquitetural: `config.py` fora do volume `docker-compose.yml` cpes-main → mudanças em config exigem `--build`, não só `--force-recreate`. Documentar.

**Decisões:**
- `USE_NEW_MARKETS_ROUTE=true` mantida ligada em produção pós-smoke.
- Path legado `/markets` preservado no adapter (zero risco de remover por enquanto, pode ajudar diagnóstico futuro).

**Estado final:** PRIORIDADE 1 ✅ closed. Bug 1 user resolvido. K.1 cascata segue OK (USE_SOFASCORE=true). Próximas prioridades pendentes: P2 (popular team_map Premier League), P3 (fix lineups merge bug), P4 (renewer 502 root cause / healthcheck profundo).

---

## 2026-05-17 — Fase K.0: Investigação SofaScore API (CASO α via curl_cffi)

**Contexto:** Caminho A soft ~75% (D.0→G.1 entregues). Fallback dos 3 Composites E.1/F/G ainda é AF — sem créditos no momento (CLAUDE.md §10). Fase K planeja substituir AF runtime por SofaScore (estável, grátis, dados ricos).

**O que foi feito (sem código de produção — só investigação + docs):**

**Setup:** branch `feat/sofascore-integration` criada partindo de `feat/betano-bridge-adapter` (commit `cabcbc4`).

**Bloqueio descoberto:** curl simples do servidor CPES retorna 403 Varnish em todos endpoints (incluindo `/`), mesmo com headers de browser real (Firefox 120, Chrome, Origin/Referer corretos). Daniel acessa SofaScore normal no PC dele (mesmo IP residencial). Conclusão: bloqueio **TLS fingerprint (JA3)**, não IP.

**Captura via mitmproxy:** Daniel rodou mitmweb no PC dele, configurou Firefox com proxy, navegou SofaScore (sequência: livescore → jogo MLS → stats → lineups → H2H → standings Brasileirão → time → matches → squad). Capturou 3179 requests no HAR (89MB, parcialmente truncado, recuperados 3179 via streaming ijson → `sofa-fixed.har`).

**Análise HAR:** 1495 requests a `www.sofascore.com/api/v1/*` — 995 status 200, 370 status 304 cache, 130 status 404 (endpoints inválidos pra eventos específicos). Zero erros anti-bot. 134 paths únicos. 31 endpoints chave extraídos como samples (`/tmp/sofa-samples/*.json`).

**Bypass validado:** lib `curl_cffi` (Python wrapper para `libcurl-impersonate-chrome`) com `impersonate='chrome120'` passa 200 OK do servidor CPES no IP residencial que bloqueia curl simples. **10/10 endpoints testados respondem 200 OK direto.**

**Stress test:** 70 reqs sequenciais em 1.5s = 47 req/s — zero 429/403. Margem >150× sobre uso CPES atual (~0.3 req/s). SofaScore aberto pra volume real.

**Descobertas críticas:**
- **Coach resolvido:** endpoint dedicado `/event/{id}/managers` traz `homeManager`/`awayManager` com `name`, `id`, `slug`. Resolve gap `BETANO_GAPS_LINEUPS = {coach_name}`.
- **Lesões/suspensões via `lineups.missingPlayers[]`:** `type` ∈ {missing, doubtful}, `reason` (numérico — mapping K.1), `expectedEndDate`. Schema mais rico que AF /injuries.
- **Stats por período:** `/statistics` traz 3 períodos (1ST, 2ND, ALL) × 7 grupos (Match overview, Shots, Attack, Passes, Duels, Defending, Goalkeeping). Inclui `shots_on_target`, `blocked_shots`, `hit_woodwork`, `big_chances`, `xG live` — TUDO o que Betano não tem.
- **Standings ricos:** 20 times com posição/pontos/V-E-D/GP/GC + `promotion.text="Copa Libertadores"` (Libertadores/Sul-Americana/Z4 sinalizadas).
- **Endpoints NOVOS sem equivalente em Betano/AF:** team-performance-graph (temporal), best-players summary (ratings), pregame-form (W/D/L 5 últ), average-positions (heatmap-light), win-probability graph, AI insights pt-BR.

**Decisão:** **CASO α puro** — `curl_cffi` direto, sem bridge dedicado. Documentado em [`DECISIONS.md`](DECISIONS.md) e [`architecture/sofascore-api.md`](architecture/sofascore-api.md) (~150 linhas, doc novo).

**Estimativa K.1:** 25-35h em ~5 sessões — adapters Composite (stats/events/lineups) + workers novos (standings + team-form + best-players) + extensão `CanonicalLineup` (coach_name + missing_players) + ~30 testes + smoke.

**Estado final:**
- Branch `feat/sofascore-integration` pushada e isolada.
- Doc arquitetural + ADR + samples preservados.
- Zero código de produção tocado.

**Próximos passos:** PAUSAR pra Daniel revisar estratégia K.1 (cascata, schemas, ordem de adapters). K.1 só inicia quando aprovado.

---

## 2026-05-17 — Fase G.1: Lineups Betano via roster (implementação completa)

**Contexto:** G.0 confirmou CASO α puro (schema em `event.roster` do `/event/<id>/state` já capturado pela E.1). G.1 implementa adapter + worker + persistência sem nova carga no renewer.

**O que foi feito (6 commits + push):**

**PARTE A — Persistência:**
- Migration `0007_lineups_history.sql`: schema com `formation`, `coach_name`, `starting_eleven JSONB`, `substitutes JSONB`, `tactical_grid JSONB`, `version`, `captured_at`. UNIQUE `(fixture_id, source, team_side)`. CHECK `team_side IN (home, away)`.
- `data/repositories/lineups_history.py`: `upsert_lineup`, `upsert_batch`, `get_by_fixture`, `exists_for_fixture`. Dedup via UNIQUE.

**PARTE B — Providers (com 5 ajustes pós-review):**
- `data/lineups_provider.py`: `PlayerEntry` + `CanonicalLineup` (com `has_starting_eleven` property) + `BETANO_GAPS_LINEUPS = frozenset({"coach_name"})` + `LineupsProvider` Protocol + `CompositeLineupsProvider` (cascade primário→fallback se `None` OU cobertura zero).
- `BridgeLineupsAdapter`: cross-ref `lineup[][]` × `roster.players[id]` pra shirtNumber/position. Reusa `/event/<id>/state` (zero nova request HTTP).
- `APIFootballLineupsAdapter`: AF `pos` G/D/M/F → canonical GK/DF/MF/FW. Coach preenchido (cobre gap Betano).
- AJUSTES pós-review:
  - AJUSTE 1: `_resolve_player` nunca descarta entry (preserva contagem de 11 mesmo sem ID), fallback `name='<unknown>'`.
  - AJUSTE 2: AF `get_lineups(home_team_id=...)` resolve `team_side` via `team.id` (correto), fallback ordem com log debug.
  - AJUSTE 3: `_map_position` loga WARNING quando posição não-mapeada (rastreia drift de schema).
  - AJUSTE 4b: Composite loga `lineups.partial_coverage` WARNING quando home_ok != away_ok.
  - AJUSTE 4c: bridge `_parse` loga DEBUG quando `coach_name=None` (gap conhecido).

**PARTE C — Worker + wiring:**
- `BetanoLineupsWorker.capture_if_needed(fixture_id, minute, home_team_id)`: cache duplo (in-memory + `repo.exists_for_fixture`), gate por `minute > max_minute`. Cache marcado SOMENTE quando: `repo.exists True` OR `insert.inserted>0`. NÃO marca em: `provider None`, `lineups []`, `inserted=0 all skipped`, `minute > max` (correção via VAL 4 — permite retry se minute vier com spike transiente).
- Configs `USE_BETANO_LINEUPS=false` + `LINEUPS_MAX_MINUTE=5`.
- Factory `build_lineups_provider`.
- main.py wiring: `_capturar_lineups` em `_analisar_jogo` (depois de `_capturar_events`), `home_team_id` extraído defensivamente. Shutdown plugado pros 3 workers (E.1+F+G).

**PARTE D — Testes:**
- 5 arquivos, **48 testes** (alvo 16-18, **+270%**). Cobertura de todos AJUSTES (1-4) + 5 cenários VAL 4 (tabela cache).
- Sanity baseline: 31 falhas em `rate_limiter/score/whatsapp/decision/backtest` são PRÉ-EXISTENTES (confirmado em HEAD~1 stashed). Zero regressão introduzida.

**PARTE E — Smoke:**
- ✅ Smoke LEVE (flag off): worker silencioso, zero capturas, stats/events continuam, migration 0007 aplicada no startup.
- ⚠️ Smoke REAL parcial: init OK (`providers.lineups_stack primary=bridge_betano fallback=apifootball` + `BetanoLineupsWorker ativo max_minute=5`), mas sem jogos live no momento ("Sem jogos restantes hoje"). Próximo lote 2026-05-17 10:30 BRT (~11h adiante).
- Decisão: **flag ON em produção**, smoke real assíncrono — capturas vão acontecer naturalmente quando jogos começarem amanhã. Worker é fire-and-forget, decision_engine intocado, risco baixo.

**Achados operacionais:**
- Bridge `/events/live` ainda intermitente (503 transient) — mesma dinâmica F. Composite cascade Betano→AF cobre transparente.
- Bridge `/health`: 2/2 endpoints healthy. Cookie `_cfuvid` válido (uptime 15766s).
- Shutdown que F deixou pendente (`_events_shutdown` armazenado mas não invocado) corrigido nesta sessão.

**Hashes (em ordem):**
- `86da575` — PARTE A migration + repo
- `4d388ab` — PARTE B inicial (Protocol + 3 adapters + Composite)
- `a4ceb97` — PARTE B ajustes 1-4
- `223368d` — PARTE C worker + configs + wiring
- `9de2829` — PARTE C fix VAL 4 (skip_late não cacheia)
- `63cfd3a` — PARTE D suite 48 testes
- `93c986e` — docs ROADMAP Fase J ON HOLD (paralelo)

**Estado final:**
- `USE_BETANO_LINEUPS=true` em produção, aguardando jogos pra primeira captura real.
- Caminho A soft ~75% completo (D.0, D.1, D.2, D.2A, E.0, E.1, F, G).
- Próximas fases: H (refactor remover AF runtime), I (otimização + cache), J ON HOLD (pré-jogo + estudo times), K (descontinuar AF).

**Próximos passos:**
- Smoke real assíncrono — review lineups_history quando jogos começarem (2026-05-17 10:30 BRT+).
- Consolidar Fase G ✅ no ROADMAP após validar 1ª captura real.

**Atualização pós-fechamento (smoke real validado com MLS Seattle×LA ao vivo):**
- Daniel apontou jogo MLS live (event 81380286). MLS não estava em `LIGAS_MONITORADAS` — adicionada (AF league_id=253, season 2026, media_esperada=10.8) + `LIGAS_MEDIA_CARTOES[253]=4.0`. Rebuild + restart: discovery matchou `event_id=81380286 → fixture_id=1490304 confidence=1.00`.
- Smoke real end-to-end via worker (jogo já em min ~84, fora do gate <=5 — captura forçada com minute=3 sintético):
  - RUN 1 (`capture_if_needed minute=3`): inserted=2 ✅
  - RUN 2 (cache hit): inserted=0, sem provider call ✅
  - RUN 3 (cache cleared, `repo.exists`): inserted=0, sem provider call ✅
  - RUN 4 (fixture novo, `minute=99`): inserted=0, **cache NÃO marcado** (fix VAL 4 confirmado em produção) ✅
- DB final: `fixture_id=1490304, source=bridge_betano`, home `4-2-3-1` 11+9, away `4-1-4-1` 11+9, coach=None, version=4521. Zero duplicatas via UNIQUE.
- **Caminho A soft Fase G PLENAMENTE entregue.**

---

## 2026-05-17 — Fase G.0: Investigação técnica lineups Betano + validação renewer

**Contexto:** Antes de implementar Fase G (lineups Betano), validar (1) saúde do renewer pós smoke instável da F, (2) endpoint real do payload de lineups.

**O que foi feito (zero código — só investigação + docs):**

**PARTE 1 — Validação saúde renewer 24h:**
- `stats_history` 24h: `apifootball` 46 (69.7%), `bridge_betano` 20 (30.3%). Janela curta — só ~1h de prod real (jogos sábado noite acabaram cedo + Brave warmup inicial).
- `events_history` 24h: 100% `apifootball` (events worker entrou em ação só na janela final, antes do bridge recuperar do warmup).
- **Teste live atual: renewer 100% saudável.** `/health` 200 OK. `/danae/live` 200 6.7s (42 events). `/danae/event/<id>/state` testado em 5 event_ids distintos (MLS, Liga 1 Peru, Liga Panamá, esports) → todos 200 OK, latência 5.5-8s, payloads válidos (versions 579-1258, scores, corners reais).
- **Decisão go/no-go:** ✅ **GO**. Métricas históricas degradadas por janela curta, não instabilidade crônica.

**PARTE 2 — Investigação endpoint lineups:**
- Plano original previa captura via mitm no danewell. **Não foi necessário.**
- Schema completo descoberto inspecionando `event.roster` dos payloads `/event/<id>/state` que `BridgeStatsAdapter` (E.1) **já captura a cada poll**.
- Schema rico: `roster.homeRoster.players` (squad completo 26-38, com `shirtNumber`, `position`, `positionDisplayName` localizado pt-BR), `roster.lineups.homeLineup` (`teamId`, `formation` "5-4-1", `lineup[][]` linhas táticas, `benchPlayers[]`). Análogo `awayRoster`/`awayLineup`. `unknownPlayers` pra players sem ID Betano (UUID + name).
- Cobertura validada em 4 ligas distintas: MLS ✅, Liga 1 Peru ✅, Liga Panamá ❌ (zero), Esoccer ❌ (zero). Mesma curva `coverage_level` Opta da E.1.
- Gap vs AF: **coach (técnico)** — não vem no Betano roster. Ganhos vs AF: squad completo + position localizada.

**Decisões:**
- [Nova ADR em DECISIONS.md](DECISIONS.md): **CASO α puro** — extrator + persistência sobre payload já capturado. Zero novo endpoint, zero novo trabalho bridge/renewer.
- Estimativa Fase G.1: **5h** (vs 6-10h originalmente — redução porque endpoint já está sendo consumido).

**Entregáveis G.0:**
- ✅ `docs/architecture/betano-lineups-api.md` (novo, ~150 linhas) — schema completo + cobertura comparativa + decisão técnica + limitações.
- ✅ ADR em `docs/DECISIONS.md` "Fase G.1 lineups Betano via event.roster (CASO α puro)".
- ✅ Métricas renewer 24h registradas nesta sessão CHANGELOG.
- ✅ JSONs de referência preservados em `/tmp/test_*.json` (recriáveis via curl).

**Estado final:**
- Renewer **saudável** (5/5 live tests 200 OK).
- Schema lineups Betano **mapeado** sem precisar mitm.
- Pronto pra implementar Fase G.1 quando Daniel der go.

**Próximos passos:** Fase G.1 implementação (~5h, padrão E.1/F reusado).

---

## 2026-05-17 — Fase F: Eventos Betano via `event.incidents[]` (dataset puro)

**Contexto:** Persistir eventos individuais (gols, cartões, escanteios, substituições, etc) capturados do `event.incidents[]` no mesmo payload `/event/<id>/state` já usado pelo `BridgeStatsAdapter` (Fase E.1). Caminho A soft progride — **dataset puro** (PASSO 0 confirmou ZERO consumidores externos de `api_client.get_events`).

**Decisão de escopo:** Opt 1 ("dataset puro") confirmada — único caller de `api_client.get_events` é interno em `get_fixture_result` (post-FT, fallback contar corners). Substituição = nicho, deferida pra Fase F.2 quando dataset Betano comprovar cobertura ≥ AF empíricamente (~1-2 semanas).

**O que foi feito (7 commits, `ef112b7` → `a65bfe6`, ~6h):**

- **PARTE A** — Migration `0006_events_history.sql` (11 colunas + 3 índices + UNIQUE dedup `(fixture_id, source, event_type, event_minute, team_side, player_name)` + CHECK constraint `team_side ∈ {home, away, NULL}`). `EventsHistoryRepo` com 4 métodos (`upsert_event`, `upsert_batch`, `get_recent_by_fixture`, `get_by_type_in_window`).
- **PARTE B** — `CanonicalEvent` frozen dataclass + `EventsProvider` Protocol + `CompositeEventsProvider` (cascata sequencial Betano→AF, `[]` = sucesso sem fallback). `BridgeEventsAdapter` reusa endpoint `/event/<id>/state` do bridge — parse `event.incidents[]` com normalização de `teamSide` (0→home/1→away/outro→None), parse de `time="50'+3'"`, drop de incidents sem minute. `APIFootballEventsAdapter` refactor do `get_events` legado com mapping `(af_type, af_detail)` → canônico (GOAL/YELL/RCRD/SUBS/VAR/PENL/CGOL). Hint `home_team_id` resolve `team_side` no AF (None graceful quando ausente). `betano_event_id` opcional no Protocol pra pular lookup no `fixture_repo` quando caller já sabe.
- **PARTE C** — `BetanoEventsWorker.capture(fixture_id, *, betano_event_id, home_team_id)` stateless. Configs `USE_BETANO_EVENTS=false` default + `EVENTS_POLL_INTERVAL_SEC=30`. Factory helper `build_events_provider` monta o Composite. Wiring `main.py::_capturar_events` fire-and-forget após telemetria odds, throttle 30s por fixture, defensivo `home_team_id` resolution. **Sem consumer substitution** (Opt 1).
- **PARTE D** — 35 testes verdes (alvo 22+): repo (6), bridge adapter (9), AF adapter (8), composite (7), worker (5). Críticos cobertos: dedup, `[]` não cai fallback, `team_side=None` graceful, provider `None/[]` zero-zero, AF unmapped warning + fallback, hints repassados.

**Ajustes pós-review aplicados:**
- (AJUSTE 1) AF mapping ganhou CGOL (`Goal/Cancelled Goal`, `Var/Goal cancelled`) + VAR (`Penalty awarded/confirmed`) + log WARNING quando type+detail cai em fallback.
- (AJUSTE 2) `betano_event_id` no Protocol; AF aceita `home_team_id` (Opção A — sem chamada extra; AF sem créditos).
- (AJUSTE 3) Composite log INFO quando primary devolve `[]` (analytics futuro).
- (AJUSTE 4) Cache compartilhado payload bridge entre stats+events workers deferido pra Fase I (ROADMAP atualizado).
- (POST-REVIEW PARTE C) Defensivo `try/except (KeyError, TypeError, AttributeError)` em `_capturar_events::home_team_id` (fixture mal-formado não crasha worker).
- (POST-REVIEW PARTE C) Docstring trade-off throttle 30s — defasagem aceitável pra dataset histórico (H2-H4); insuficiente pra reação real-time.

**Bugs encontrados:**
- AF `Goal/Cancelled Goal` antes ia pra fallback genérico (`UPPERCASE`). Agora vira `CGOL` explicitamente.
- Política heurística "só >0 sobrescreve" no mapper E.1 reaplicada como template — substituída por `BETANO_GAPS` frozenset durante refactor (zero re-aplica esse erro).

**Decisões:** ADR já cobre família CASO α em [DECISIONS.md](DECISIONS.md). F é refinamento incremental — sem ADR nova.

**Smoke real validado:**

- 18 eventos persistidos via 4 rodadas de captura em 2 fixtures (Palmeiras × Cruzeiro min 50, Cuiabá × Novorizontino min 76).
- Mix de types: GOAL/YELL/SUBS (cobertura realista).
- Source: **100% `apifootball` durante a janela do smoke** — bridge_events retornou 503 em todas as 4 tentativas (renewer warmup, mesmo pattern intermitente da Fase E.1).
- Dedup confirmado: round 3 inseriu 0 / pulou 6 (jogo sem mudança); round 4 inseriu 2 / pulou 9 (jogo evoluiu, 2 events novos).
- Throttle 30s observado: capturas mesmo fixture com ≥2min de espaço.
- Decision_engine intocado: análises normais (`[ANALISE] Palmeiras vs Cruzeiro | Min 50 | Placar 1-1`).
- Rollback test natural: Composite cascade comprovado — bridge 503 → AF assume → 18 events persistidos.

**Smoke source=bridge_betano**: aguardando próxima janela de jogos (main em sleep 2h pós-FT dos 2 fixtures). Mesma dinâmica E.1 — source flippa automaticamente quando renewer recuperar.

**Achados operacionais:**
- Background poll inicial expirou em janela de jogos curta (45min) sem capturar source=bridge_betano. Aceitável — fallback AF cobriu o gap.
- `docker compose up -d --force-recreate` ≠ rebuild de imagem. Configs novas precisam `--build`. Padrão E.1 não tinha esse problema porque eu rebuildei explícito.
- Dedup constraint funciona perfeitamente — round 3 mostrou skipped_dup=6 com total=6 (jogo estático).

**Estado final:**
- ✅ `USE_BETANO_EVENTS=true` ativo em produção
- ✅ `events_history` populando (18 events na sessão)
- ✅ Composite cascade Betano→AF funcional
- ✅ Decision_engine sem regressão
- ✅ 35/35 testes verdes, 7 commits push pra `feat/betano-bridge-adapter`
- ⏳ Fase F.2 (substituição `api_client.get_events` interno) deferida pra ~1-2 semanas após validar cobertura

**Próximos passos:** Fase G (lineups via `/api/statsstream/<id>/info/aggregated/`).

---

## 2026-05-17 — Fase E.1: Stats Betano via `/danae-webapi` (CASO α)

**Contexto:** Substituir `api_client.get_statistics` (API-Football) por pipeline canônico de stats consumindo `bridge:8080/event/<id>/state`. Caminho A soft progride — stats runtime agora **Betano-primário com fallback AF** automático via Composite cascade.

**O que foi feito (9 commits, 66ec557 → 1e3efca, ~10h):**

- **PARTE C'** — `BridgeStatsAdapter` (`data/providers/betano/bridge_stats_adapter.py`, 268 LoC). Implementa `StatsProvider` Protocol consumindo bridge `/event/<id>/state`. Cache de `version` por fixture pra mandar `if_version=N` no próximo poll. Normaliza `event.liveData.results` em `CanonicalStats`. Robusto contra cobertura ausente por liga. `CanonicalStats` estendido com 6 campos opcionais (`version`, `second_since_start`, `corners_last_5/10min`, `yellow_last_5/10min`, `captured_at_ts`, `is_cached`) — compat 100% com Fase A. Deletado `betano/stats_adapter.py` (Opta REST orfão, bloqueado por 403 CF). Foot-gun WARNING em factory se `USE_NEW_PROVIDERS=true` sem `(USE_BETANO_BRIDGE + USE_BETANO_STATS)`.
- **PARTE D** — Migration `0005_stats_history.sql` idempotente (29 colunas + 3 índices, UNIQUE parcial `(fixture_id, source, version) WHERE version IS NOT NULL`). `StatsHistoryRepo` com `insert/list_recent_for_fixture/latest_version_for_fixture`.
- **PARTE E'** — `StatsWindowCalculator` (`data/services/`, deque maxlen=120 por fixture, edge cases: empty/decreased/maxlen_eviction/concurrent). `BetanoStatsWorker` (`workers/`) com `poll(fixture)`: bootstrap → adapter → calculator → insert. Tratamento `is_cached=True` (NÃO duplica no deque, `freshness='cached'`). Configs `USE_BETANO_STATS`, `STATS_POLL_INTERVAL_SEC=15`, `STATS_WINDOW_HISTORY_SIZE=120`, `STATS_BOOTSTRAP_LOOKBACK_MIN=20`.
- **PARTE F'** — Factory 4º caminho (`USE_BETANO_BRIDGE + USE_BETANO_STATS → CompositeStatsProvider([bridge, AF])`). Mapper `canonical_to_jogo` em `data/services/canonical_to_jogo.py` com política **BETANO_GAPS frozenset explícita** (9 campos onde Betano não cobre — `cartoes_vermelhos_*`, `posse_ultimos_10min`, `faltas_*`, `ataques_perigosos_ultimos_10min`, `finalizacoes_recentes`). Wiring em `main.py:_analisar_jogo` substitui `api_client.get_statistics` por `self.stats_worker.poll(fixture)` quando flag ativo.
- **PARTE G** — 28 testes novos (`tests/services/`, `tests/workers/`, `tests/providers/betano/test_bridge_stats_adapter.py`, `tests/test_stats_history_repo.py`). Suite final: **65/65 verdes** (37 baseline + 28 novos).
- **WIP cleanup** — aplicado `helpers.enrich_jogo_with_cards` + `notification_manager.cards_group_id/database` do stash (nunca commitados; main.py importava). Dropados 2 stashes obsoletos. Removida duplicação `_build_canonical_fixture` (module-level vs class method). Assert defensivo `placar_casa/fora not None` no helper de classe.

**Bugs encontrados:**

- Política heurística "só sobrescreve se >0" no mapper era armadilha (AF zero ≠ Betano gap). Substituída por `BETANO_GAPS` frozenset explícito ([DECISIONS.md](DECISIONS.md#caso-α)).
- `finalizacoes_recentes` mapeado erroneamente como `shots_on_target` — **gap semântico** Betano `shots` ≠ AF `Shots on Goal`. Movido pra `BETANO_GAPS`.
- Cache 304 do bridge é **dead-code em produção** — bridge TTL=3s << worker poll=15s, cache HIT do bridge nunca trigger. Insight pra futura otimização.
- WIP não commitado descoberto durante smoke pré-PARTE H (auditoria PEDIDA pelo Daniel) — `enrich_jogo_with_cards` e `NotificationManager(cards_group_id=)` vivendo só em disco; container herdava de build anterior. Caso silencioso de "código em produção mas não rastreado". Corrigido.

**Decisões:** [DECISIONS.md §"CASO α"](DECISIONS.md) já documentada na E.0 (2026-05-16). Refactor BETANO_GAPS pós-review aplicado sem mudar ADR (escopo de implementação).

**Smoke real validado:**

- **6 capturas `bridge_betano` + 12 `apifootball`** em `stats_history` (Composite cascade real).
- **Version polling funcional**: 1545164 progrediu 4133 → 4195 → 4222.
- **Janelas temporais calculadas**: 1520683 yellow_last_10min cresceu 1→2.
- **Decision_engine consumindo dados live**: CardsDecision `Score=7` APROVADO em River Plate ×Rosario Central.
- **Latência 7-7.5s end-to-end** (target <10s ✓).
- **Rollback test natural**: bridge falhou nos primeiros 10min (Brave warmup), AF assumiu (12 capturas AF), bridge recuperou (6 capturas bridge_betano). Source flippa sem intervenção.

**Achados operacionais:**

- **Brave pool warmup ~10min** após restart — Composite cai em AF naturalmente durante. Não é bug.
- **Cache 304 bridge dead-code** em produção (TTL 3s << poll 15s).
- **`finalizacoes_recentes` gap semântico** shots ≠ Shots on Goal (catch da review).
- **Duplicação `_build_canonical_fixture`** eliminada (module-level vs class method).

**Estado final:**

- ✅ `USE_BETANO_STATS=true` ativo em produção
- ✅ `stats_history` populando com source mix (bridge_betano primário, AF fallback)
- ✅ decision_engine sem regressão
- ✅ 65/65 testes verdes, 9 commits push pra `feat/betano-bridge-adapter`
- ⏳ E.2 WebSocket push (futuro, opcional, não bloqueia)

**Próximos passos:** Fase F (eventos via `event.incidents[]`).

---

## 2026-05-16 (sessão 6) — Fase D.2 PARTE A: catálogo de teams via bridge

**Contexto:** Sessão 5 entregou D.2 com PARTE A pendente. Discovery rodando 100% via fuzzy match (sem catálogo prévio). PARTE A popula `betano_team_map` proativamente pra acelerar lookup determinístico.

**Achado crítico durante implementação:** `/api/static-content/assets/teams` (8.8MB, identificado em sessões anteriores como "catálogo de teams") tem só logos/cores. **Zero campos `name`**. Não serve pra popular `betano_team_map.betano_team_name`. Re-investiguei `.mitm` e descobri que `/danae/live` (já temos) + `/api/home/upcoming-coupons` agregados cobrem todos teams ativos do dia via `participants[].{name, id}`.

**O que foi feito:**

- **No danewell** (Claude lá): `/danae/teams` agrega `participants[]` de 2 endpoints em paralelo (`asyncio.gather`), normaliza team_id pra int (upcoming-coupons retorna string), dedupe por team_id com live > upcoming, marca `source` (`live`|`upcoming`|`live+upcoming`). Fail-soft pra `upcoming-coupons` (retorna só live com `upcoming_failed: true`). 152 teams total no smoke (live=140, upcoming=22, overlap=10), 5.58s. Validado pelo Daniel.
- **No bridge** (odin): `GET /teams` proxy ao danewell + cache em memória 24h, key por sport, configurável via `TEAMS_CACHE_TTL_SEC`. Suporta `?force_refresh=true`. Cache MISS 5.07s, HIT 42ms.
- **No cpes-main**: `BetanoFixtureDiscovery._refresh_teams_catalog()` chama bridge `/teams`, bulk_upsert no `betano_team_map` com `match_method='static_catalog'`. Trigger automático no `_loop` quando intervalo > 86400s. Fail-soft (erro loga warning, não para `_loop`). Filtros de input: descarta team_id inválido / name vazio.

**PARTE A.3.3 (matcher lookup) PULADA** — já estava implementada na PARTE C original (sessão 5, commit `90d7675`). Matcher tenta team_id_lookup ANTES de fuzzy.

**Validação:**
- 4 testes novos no worker (`test_refresh_teams_catalog_*`), 10 testes verdes no arquivo (era 6)
- 37 testes verdes em arquivos relacionados (era 33)
- Sem regressão

**Smoke E2E em produção:**
- `refresh catálogo OK: count=92 upserted=92 from_cache=True sport=FOOT`
- `betano_team_map`: 92 entries, todas `match_method='static_catalog'`
- Sample populado: Albirex Niigata, Vegalta Sendai, Consadole Sapporo, Tokyo Verdy, Shonan Bellmare (J-League agendados)
- Bridge cache foi usado (worker pegou from_cache=true porque eu já tinha rodado curl antes)

**Decisões:** Atualização in-place na [decisão original da sessão 5](DECISIONS.md#2026-05-16-sessão-5--fase-d2-descoberta-automática-de-fixtures-betano) com nota sobre PARTE A entregue.

**Estado final:**
- ✅ Pipeline D.2 completo: catálogo + discovery + matcher (lookup → fuzzy → cache resultado)
- ✅ `betano_team_map` populando proativamente 1×/dia
- ✅ Bridge cache 24h reduz pressão no danewell (volume baixo)
- ⏳ 0 matches reais ainda (esperando jogo de liga monitorada ao vivo — não é bug)
- ⏳ Fase E (Adapter Stats Betano) próxima

**Próximos passos:**
- Observar 24-48h: confirmar `betano_team_map` cresce com novos teams + matches reais aparecem quando overlap
- Considerar `TEAMS_CACHE_TTL_SEC` menor (6h?) se catálogo Betano flutuar muito durante o dia
- Próxima fase: Adapter Stats Betano (Phase E do roadmap)

---

## 2026-05-16 (sessão 5) — Fase D.2: discovery worker no cpes-main

**Contexto:** D.1 entregou o bridge `/events/live`. D.2 era automatizar a população do `betano_fixture_map` via matching com fixtures API-Football das ligas monitoradas, eliminando o `BETANO_EVENT_MAP` manual.

**O que foi feito (4 partes faseadas):**

- **PARTE B** — migration `0004_betano_team_map.sql` (tabela + 3 índices, incl. GIN trgm) + `BetanoTeamMapRepo` com 4 métodos (`get_by_betano_id`, `get_by_api_football_id`, `bulk_upsert` via executemany, `find_by_fuzzy_name` via pg_trgm similarity). Adicionado `rapidfuzz>=3.6.0` ao requirements. 7 testes verdes.
- **PARTE C** — `data/discovery/fixture_matcher.py` com classe `FixtureMatcher` (lookup determinístico + fuzzy fallback com rapidfuzz, normalização de nomes — lowercase, sem acentos, sem FC/SC/(F)/(M)/(esports), validação kickoff ±30min). Match fuzzy bem-sucedido auto-UPSERTa teams no map. 10 testes verdes. **Bug fix durante testes:** regex `\b(...)\b` não funciona com parens — splittei em 2 patterns (paren-tokens sem boundary, word-tokens com).
- **PARTE D** — `workers/betano_discovery.py` com `BetanoFixtureDiscovery` worker (asyncio.Task, poll 150s default, fail-soft em 3 níveis, cache schedule por dia). Wiring em `main.py` iniciar() (dentro do `if USE_BETANO_BRIDGE:`) + `_shutdown()`. 3 configs novas em `config.py`. 6 testes verdes (incluindo `test_worker_continues_when_upsert_fails`).
- **PARTE E** — `BETANO_EVENT_MAP` segue funcionando como override manual; log no startup discrimina 3 cenários (override / discovery automática / warning sem fonte).

**PARTE A adiada** (bridge `/teams` endpoint) — depende de `/danae/teams` no renewer do danewell. Sem catálogo periódico, `betano_team_map` cresce on-demand via matches fuzzy.

**Validação:**
- 24 testes novos verdes (7 + 10 + 6 + 1 sanity)
- 38 testes verdes em arquivos relacionados (sem regressão em `test_main_pipeline_integration`)
- `python -c "import main"` passa
- Suite full tem 23 failures pré-existentes (backtest, strategy_preference, whatsapp formatter, providers/betano integration) — nenhum nos arquivos novos
- Migration 0004 aplicada via `Database.init()` automático no startup (idempotente)

**Smoke E2E:**
- Worker iniciado com log: `"BetanoFixtureDiscovery iniciado (poll=150s, sport=FOOT, ligas=10)"`
- Ciclo 1: `schedule_atualizado: 27 fixtures candidatos (date=2026-05-16, ligas=10)`, depois `17 eventos, 0 matches, 17 skipped`
- Comportamento correto: bridge retorna eventos sul-americanos/USA (Liga 1 Peru, Liga de Primera Chile, NWSL EUA, etc) que não estão nas 10 ligas API-Football monitoradas (Premier/Bundesliga/Serie A/La Liga/Argentina/Brasil/etc). Discovery vai disparar matches quando jogos das ligas monitoradas estiverem ao vivo.

**Bugs encontrados nesta sessão:** Nenhum bug runtime — o `name: null` da sessão anterior já estava fixado pelo danewell antes da D.2 começar.

**Decisões:** [Fase D.2: descoberta automática de fixtures Betano](DECISIONS.md#2026-05-16-sessão-5--fase-d2-descoberta-automática-de-fixtures-betano)

**Achado operacional:** `docker-compose.yml` define `environment: USE_BETANO_BRIDGE=${USE_BETANO_BRIDGE:-false}` que tem **precedência sobre `env_file`** — pra ativar bridge precisa exportar no shell OU criar `.env` na raiz do repo (docker-compose lê automático). `.env` raiz criado nesta sessão com `USE_BETANO_BRIDGE=true`.

**Estado final:**
- ✅ Worker rodando em produção (cpes-main container, há ~3min ao escrever isso)
- ✅ Migration 0004 aplicada
- ✅ `betano_team_map` schema criado, populando on-demand
- ✅ `betano_fixture_map` ainda com 5 entries `manual_seed` legadas — `discovery_*` vai aparecer quando overlap
- ⏳ PARTE A (`/teams` endpoint) pendente pra próxima sessão
- ⏳ Validação E2E com matches reais pendente jogo de liga monitorada ao vivo

**Próximos passos:**
- PARTE A: prompt pro Claude do danewell adicionar `/danae/teams` → bridge ganha `/teams` proxy → worker chama 1×/dia pra popular catálogo
- Observar produção 24h: confirmar matches reais aparecendo quando ligas monitoradas têm jogos
- Eventualmente decommissionar `BETANO_EVENT_MAP` (quando confiança no discovery for alta)

---

## 2026-05-15 (sessão 4 — extensão proxy) — Proxy residencial no Brave

**Contexto:** Pós-D.1 funcional. Daniel comprou proxy residencial brasileiro (ML Telecom RJ, `200.234.172.57:43958`) pra diversificar IP de saída do pool Brave. Risco a mitigar: Cloudflare reflagar IP único da casa (V tal Curitiba) cortaria tudo de uma vez.

**O que foi feito:**
- Validação prévia do proxy via curl (da odin): IP brasileiro residencial real (não datacenter), latência ~800ms, aceita HTTPS
- **No danewell** (Claude lá): Chromium 148 não aceita auth inline em `--proxy-server`. Solução escalada pra Alt-B do plano original: `tinyproxy-betano.service` local em `127.0.0.1:8888` que injeta auth no upstream. Brave conecta no tinyproxy sem auth.
- Unit `brave-betano.service` ganhou `--proxy-server=http://127.0.0.1:8888`. Backup imutável da unit pré-proxy (`.pre-proxy-2026-05-15`) pra rollback rápido.
- **Chrome do pool intocado** — continua sem proxy, IP da casa, atendendo `/markets`/`/quote` pra cpes-bridge da odin via Playwright/CDP porta 9223.

**Validações:**
- `curl -x 127.0.0.1:8888 ipinfo.io` (no danewell): `200.234.172.57` ✓
- Brave fetch ipinfo via CDP: `200.234.172.57` (egress proxy) ✓
- Chrome fetch ipinfo via CDP: `200.181.212.29` (egress casa intacto) ✓
- `/danae/live?sport=FOOT`: 200, count=37, 4.66s ✓
- Bridge da odin `/events/live`: 200, count=15, 4.95s, names completos, jogos reais NWSL EUA + Liga 1 Peru ✓

**Decisões:** [Isolamento de egress por browser pool](DECISIONS.md#2026-05-15-sessão-4--extensão-proxy--isolamento-de-egress-por-browser-pool)

**Estado final:**
- ✅ 2 IPs distintos pra Betano (RJ pro Brave, Curitiba pro Chrome)
- ✅ Latência D.1 inalterada (~5s — proxy 800ms absorvido pelo wait fixo de 3s)
- ✅ Bridge da odin sem mudança (proxy é transparente do lado dela)
- ⚠️ Credenciais do proxy visíveis em `systemctl cat brave-betano` — mover pra arquivo chmod 600 em fase 2

**Próximos passos:**
- Continuar pra Fase D.2 (cpes-main consome /events/live)
- Monitorar se IP do proxy não vira flag também (alguns proxies residenciais são reciclados rápido)

---

## 2026-05-15→16 (sessão 4) — D.1 funcional end-to-end via danewell renewer

**Contexto:** Sessão 3 deixou plano de implementar D.1 com httpx + cookies extraídos do .mitm. Sessão 4 começou implementando isso e bateu em sucessivos blockers até descobrir a arquitetura final.

**O que foi descoberto (na ordem):**
1. **Cookies não transportam** — extrair `cf_clearance` e usar em httpx/curl/urllib externos sempre dá 403. Validado IPv4 e IPv6, com UA exato. Cloudflare amarra cookie a IP+TLS+UA do Chrome originador.
2. **Playwright via CDP no pool dispara Splash** — `__playwright__binding__` detectável.
3. **Chrome 148 desktop Linux x86_64 está bloqueado** especificamente em `/danae-webapi/*` da Betano, **independente de profile/cookies**. Profile recriado, flags stealth, tudo — Chrome retorna 403 Splash. SPA da Betano em `/live/` aberta nesse Chrome fica em loading vazio porque o JS dela próprio recebe 403.
4. **Brave 1.90.122 (Chromium 148) passa** — TLS fingerprint diferente + `navigator.brave` exposto. Cloudflare aceita.

**O que foi feito:**
- **No danewell** (Claude lá): instalou Brave + xvfb-display101.service + brave-betano.service. Estendeu cookie-renewer com endpoint `GET /danae/live` que faz `fetch()` à Danae API DENTRO do Brave via CDP raw (sem Playwright). Suporta `?sport=` e `?include_virtuals=` e `?browser=brave|chrome` (default brave).
- **Bug fix** no normalize: `name` retornava null porque Danae não tem campo `name` — derivado de `participants[]`. Corrigido em pouco tempo (sessão paralela). Fill rate agora 100%.
- **Na odin**: implementado `GET /events/live` no `cpes-bridge/server.py` como proxy ao danewell renewer + filtro de esports/virtuais via heurística (`zone_name in {Esoccer, Virtuais, Cyber}` ou `league_name` contém "minutos de jogo"/"esports"/"H2H GG"/"GT Leagues"). Default filtra virtuais; `?include_virtuals=true` mantém.

**Validação E2E final:**
- 18 eventos reais retornados (35 raw, 17 virtuais filtrados)
- Latência ~6s end-to-end
- Eventos com names completos: "Universitario de Deportes vs Atletico Grau" (Liga 1 Peru, 154 mercados), "Coquimbo Unido vs Audax Italiano" (Liga de Primera Chile, 154 mercados), etc.

**Bugs encontrados:** [Cookies cf_clearance bound a IP+TLS+UA](BUGS.md#2026-05-15--cookies-cf_clearance-bound-a-iptlsua-do-chrome-originador)

**Decisões:** [D.1 final: bridge proxy ao danewell renewer](DECISIONS.md#2026-05-15-sessão-4--d1-final-bridge-proxy-ao-danewell-renewer)

**Estado final:**
- ✅ `/events/live` no bridge da odin retornando dados reais
- ✅ Filtro de virtuais (esports/Esoccer) funciona — `?include_virtuals=true` desliga
- ✅ Brave pool no danewell estável (Xvfb :101, profile aquecido, CDP loopback :9224)
- ✅ Chrome pool do danewell intacto pra Playwright/CDP via porta 9223 (markets/odds)
- ✅ Documentação completa em `docs/architecture/betano-danae-api.md`
- ⏳ `cpes-main` ainda não consome `/events/live` — próxima sessão integra (Fase D.2)

**Próximos passos:**
- Fase D.2: cpes-main faz polling em `/events/live`, fuzzy match contra fixtures API-Football
- Considerar endpoint adicional `/danae/event/<id>` no danewell pra consultar mercados de 1 jogo via Brave (alternativa eventual ao `/markets` atual via Chrome)
- Plano-B documentado em `BRIEFING-ODIN-2026-05-15.md` se Brave também for bloqueado (UA override → Firefox pool → curl_cffi → proxy residencial)

---

## 2026-05-15 (sessão 3) — D.1 investigação: descoberta da Danae API + IP flagueado

**Contexto:** Investigação técnica da Fase D.1 (descoberta automática de eventos da Betano). Plano original: Playwright via bridge abrindo `/live/` e parseando DOM. Resultado: descoberta de API HTTP nativa muito superior, mas IP residencial flagueado no processo.

**O que foi feito:**
- Análise de 2 HARs exportados manualmente do navegador do daniel — descobertos endpoints `/api/home/top-events-v2/` e fragmentos
- Tentativa de DOM scrape via Playwright na home da Betano — bloqueado por Splash Screen
- Tentativa em URLs alternativas (futebol, ao-vivo, hoje) — todas retornaram Splash
- Comparativo odin localhost vs danewell LAN — danewell funcionou inicialmente (298 jogos), depois também flagueado
- Captura via mitmproxy no PC do daniel (não-flagueado) — 1134 flows, 22MB
- Análise da captura: descoberto **`/danae-webapi/api/live/overview/latest`** — 913KB JSON com 301 eventos ao vivo, schema completo (events/leagues/zones/sports/markets/selections), auth via cookie `_cfuvid`
- Descoberto também: `/api/home/upcoming-coupons` (eventos agendados por dia, com `betRadarId` por evento), `/danae-webapi/api/live/events/{id}/latest` (estado de evento individual), `/api/statsstream/{id}/info/aggregated/` (stats Opta-backed pra Phase E), catálogos estáticos de leagues/teams/regions
- Documentação completa do schema em [`docs/architecture/betano-danae-api.md`](architecture/betano-danae-api.md)

**Bugs encontrados:** [IP residencial flagueado pela Cloudflare Bot Management](BUGS.md#2026-05-15--ip-residencial-flagueado-pela-cloudflare-bot-management) — burst de ~30 navegações em 10min, 7 das quais 404. TTL ~12-24h, deve desbloquear sozinho.

**Decisões:** [D.1 vai usar API HTTP nativa, não DOM scrape](DECISIONS.md#2026-05-15-sessão-3--d1-vai-usar-api-http-nativa-não-dom-scrape) — abandona Playwright/DOM em favor de requests HTTP diretas à Danae API. Chrome continua aquecido só pra renovar cookies (warmup loop).

**Estado final:**
- ✅ Schema completo da Danae API documentado
- ✅ Captura mitm preservada pra futuras consultas (`betano-capture-20260515-152323.mitm`)
- ✅ Decisão arquitetural D.1 v2 registrada
- ❌ IP residencial flagueado — bridge `/markets` produzindo 0 captures até desbloqueio
- ⏳ Implementação D.1 v2 pendente (próxima sessão)
- ⏳ `/api/home/upcoming-coupons` mapeado mas não inspecionado a fundo (pra `/events/today`)

**Próximos passos:**
- Aguardar desbloqueio do IP (~12-24h)
- Próxima sessão: implementar `/events/live` no bridge usando Danae API + warmup loop pra cookie
- Validar contra polling de 60s sem disparar novo flag
- Investigar `/api/home/upcoming-coupons` em profundidade pra `/events/today`

---

## 2026-05-15 (sessão 2) — Systemd units pro bridge

**Contexto:** Reboot acidental da odin de madrugada derrubou bridge + Chrome + Xvfb (rodavam via `nohup`, sem auto-restart). WAHA Docker sobreviveu (auto-restart Docker). danewell sobreviveu (já tinha systemd próprio). Recuperação manual levou ~30min. Resolver tornando o stack do bridge resilient a crash + reboot.

**O que foi feito:**
- 3 user units encadeadas: `xvfb-bridge.service` → `chrome-bridge.service` → `cpes-bridge.service` (Requires/After)
- `loginctl enable-linger daniel` pra services subirem sem login
- `Restart=always` em todas (descoberto que `on-failure` não dispara em SIGTERM)
- `ExecStartPre` no chrome-bridge limpa Singleton locks órfãos automaticamente
- Logs separados: `bridge.log` (FastAPI) e `chrome-systemd.log` (Chrome)
- Units versionadas em `~/cpes-bridge/systemd/` (repo separado)
- Migração ao vivo: kill processos manuais → `systemctl start cpes-bridge.service` → pool 2/2 healthy
- Cenário A validado: kill bridge → auto-restart em <14s, pool recupera

**Bugs encontrados:** [Bridge sem auto-restart](BUGS.md#2026-05-15--bridge-sem-auto-restart-reboot-da-odin) (resolvido nesta sessão)

**Decisões:** Nenhuma nova arquitetural — execução de proposta já discutida.

**Estado final:**
- ✅ 3 user units enabled + active
- ✅ Linger habilitado
- ✅ Pool 2/2 healthy
- ✅ Cenário A (kill manual + auto-restart) passou
- ⏳ Cenário B (reboot real) **não testado** — Daniel optou por confiar no Cenário A
- ⏳ Units não commitadas no repo bridgecpe ainda

**Próximos passos:**
- Commitar `~/cpes-bridge/systemd/*.service` no repo bridgecpe
- Validar Cenário B na próxima janela de manutenção (opcional — baixa prioridade)

---

## 2026-05-15 — Fase D.0 + Bridge Pool + PC danewell

**Contexto:** Pós-Fase 2bc fechada. Telemetria de odds implementada mas desligada. Necessidade de captura full coverage pra modelagem quant. Necessidade de redundância no bridge.

**O que foi feito:**
- Fase D.0 implementada e commitada (6 commits): worker telemetria ligado, catálogo completo persistido, contexto rico (minute + scores), gate desacoplado de pre_avaliar
- PC danewell (Pop!_OS) configurado com Chrome :9223 acessível na LAN
- Bridge refatorado pra pool distribuído (pool.py novo, server.py modificado, health check + failover)
- Bridge commitado e pushed pro GitHub (github.com/danewellxp-glitch/bridgecpe)
- Smoke E2E mockado validou Fase D.0 (25 linhas persistidas)
- Sistema de documentação ativa criado (`docs/DECISIONS.md`, `docs/BUGS.md`, `docs/CHANGELOG.md`, `docs/OPERATIONS.md`, `docs/ROADMAP.md` + regras no CLAUDE.md)

**Bugs encontrados:** [odds_persistence_worker=None silencioso](BUGS.md#2026-05-15--odds_persistence_workernone-silencioso)

**Decisões:** [Telemetria full coverage desacoplada](DECISIONS.md#2026-05-15--telemetria-full-coverage-desacoplada-fase-d0), [Pool distribuído de Chromes](DECISIONS.md#2026-05-15--pool-distribuído-de-chromes-fase-bridge-pool)

**Estado final:**
- ✅ Bridge rodando com pool 2/2 healthy (odin localhost + danewell LAN)
- ✅ Container cpes-main rodando código Fase D.0
- ✅ Repos protegidos no GitHub (cpes-main + cpes-bridge)
- ⏳ Smoke real Fase D.0 pendente (aguardando jogo de liga monitorada)
- ⏳ Systemd units pendentes (bridge ainda nohup)

**Próximos passos:**
- Systemd units pro bridge + Xvfb + Chrome local
- Smoke real Fase D.0 quando jogo monitorado aparecer
- Fase D principal (descoberta automática /events/today + /events/live)
