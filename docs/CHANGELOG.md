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
