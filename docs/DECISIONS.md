# DECISÕES ARQUITETURAIS

Registro de decisões com **contexto, razão, alternativas consideradas, trade-offs**. Não duplica git log — narra o "porquê".

> **Escopo:** ADRs curtos (1 par/decisão). Specs técnicas longas vão em `docs/architecture/`.

**Formato:**
```
YYYY-MM-DD — Título curto
Contexto: o que motivou a decisão
Decisão: o que ficou definido
Alternativas consideradas: (opcional)
Trade-offs: o que ganhamos vs o que abrimos mão
Status: ativa / superada (linkando decisão que substituiu)
```

---

## 2026-04-XX — Pivot pra Chrome real (Fase 1)

**Contexto:** API-Football descontinuada como fonte primária de odds. Betano implementou anti-bot pesado (Cloudflare Enterprise + DataDome + ThreatMetrix) inviabilizando HTTP client cru.

**Decisão:** Adotar Chrome stable real rodando em Xvfb headless + perfil aquecido + IP residencial brasileiro. Não tentar bypass de anti-bot, ser genuíno.

**Alternativas consideradas:**
- HTTP client com TLS spoofing (curl-impersonate) — falha no fingerprint comportamental
- Playwright/Puppeteer com browser stealth plugins — detectados rapidamente
- Browser automation cloud services (Browserless, Scrapfly) — caro, IPs de datacenter banidos

**Trade-offs:**
- ✅ Passa anti-bot indefinidamente (somos um Chrome real)
- ✅ Custo zero adicional (servidor próprio)
- ❌ Latência 8s/captura (vs ~500ms HTTP)
- ❌ Manutenção operacional (Xvfb, perfil, profile warm-up)

**Status:** ATIVA

---

## 2026-04-XX — Política central de linha 1.50-1.70 (Fase 2a)

**Contexto:** Mercados over/under da Betano oferecem 5-8 linhas por captura. Precisamos escolher uma pra emitir sinal.

**Decisão:** Linha central da faixa over_price 1.50-1.70. Se nenhuma cair na faixa, escolhe a mais próxima do centro 1.60 (degradação).

**Trade-offs:**
- ✅ Odd na faixa = mercado balanceado, ROI esperado positivo
- ❌ Em jogos extremos, política degrada (line_degraded log)

**Status:** ATIVA

---

## 2026-05-15 — Telemetria full coverage desacoplada (Fase D.0)

**Contexto:** Estratégia de produto evoluiu pra modelagem quant (Fases H). Captura só de "linha central de sinal emitido" insuficiente — perde forma de curva temporal do mercado.

**Decisão:** Persistir catálogo COMPLETO (5-8 linhas por captura) com contexto rico (minute, pressure_score, tension_score). Desacoplar captura de pre_avaliar (gate de SINAL, não de PERSISTÊNCIA). Captura sempre que fixture monitorada está em janela técnica do mercado.

**Trade-offs:**
- ✅ Dataset 5-8x mais denso sem aumentar requests Betano
- ✅ Contexto rico habilita modelagem quant
- ✅ Volume ~5 req/min cabe em 1 Chrome com folga
- ❌ Chrome ocupado ~70% do tempo em pico (vs ~30% antes)

**Status:** ATIVA

---

## 2026-05-15 (sessão 4) — D.1 final: bridge proxy ao danewell renewer

**Contexto:** Sessão 3 decidiu D.1 via HTTP nativo (Danae API). Sessão 4 tentou implementar isso direto da odin com httpx + cookies extraídos. **Não funcionou** — após validações exaustivas:

- Cookies `cf_clearance` da Cloudflare são bound a `(IP + TLS fingerprint + UA)` do Chrome originador. Extrair cookie e usar em outro client HTTP (httpx, urllib, curl) **sempre retorna 403**, mesmo com IP idêntico, UA exato e cookies frescos. Testado IPv4 e IPv6. Validado em 2 sessões independentes da odin (manhã e tarde de 2026-05-15).
- Tentativa de `Playwright.connect_over_cdp` no Chrome do danewell + `page.goto` disparou Splash Screen imediato (Cloudflare detecta `__playwright__binding__` no window, mesmo via CDP).
- **Descoberta crítica adicional**: o TLS fingerprint do Chrome 148 desktop Linux x86_64 está bloqueado pela Cloudflare especificamente em `/danae-webapi/*` (e talvez todo `/api/*`). Mesmo com profile recriado, Chrome do pool retorna 403 nesse path. Brave 148 (mesmo Chromium 148, TLS fingerprint diferente + `navigator.brave` exposto) **passa**.

**Decisão:** Arquitetura final D.1 em 3 camadas:

1. **Brave 148 no danewell** (Xvfb :101, CDP 9224 loopback-only, profile aquecido) — único browser que passa Cloudflare em `/danae-webapi/*`
2. **Renewer no danewell** (`http://192.168.1.5:8081/danae/live`) — endpoint HTTP que faz `fetch()` à Danae API DENTRO do Brave via CDP raw (não Playwright). Retorna JSON normalizado. Latência ~5s.
3. **Bridge na odin** (`/events/live`) — proxy HTTP simples ao endpoint do danewell + filtro de esports/virtuais via heurística (`zone_name in {Esoccer, Virtuais, Cyber}` ou `league_name` contém "minutos de jogo"/"esports"/"H2H GG"/"GT Leagues"). Latência ~6s end-to-end.

Chrome 148 do pool **continua ativo** no danewell (Xvfb :100, CDP 9223 LAN-exposed) pra coleta de mercados via Playwright/CDP — esse fluxo (`/quote`, `/markets` no bridge) não passa por `/danae-webapi/*` e não é afetado pelo bloqueio.

**Alternativas consideradas e descartadas:**
- httpx direto da odin com cookies extraídos — cookies bound, 403 garantido
- Bridge da odin connect_over_cdp ao Chrome do danewell via Playwright — bindings detectáveis
- Renovar TLS fingerprint via `curl_cffi` / `noble-tls` — não-trivial, frágil
- VPN/proxy datacenter — Cloudflare bloqueia ranges conhecidos
- Trocar UA do Chrome 148 pra UA Firefox — mismatch UA vs TLS, ainda flag

**Trade-offs:**
- ✅ Latência aceitável (~6s pra 100+ eventos)
- ✅ Zero Chrome dependency na odin pra D.1 (pra D.0 mantém)
- ✅ Sem refresh manual de cookies (Brave do pool mantém vivo + renewer cobre)
- ✅ Self-healing (Cloudflare desafia → Brave passa → fluxo continua)
- ❌ Acoplamento com danewell (1 nó SPOF pra D.1) — futura: 2º Brave numa segunda máquina
- ❌ Brave também pode ser bloqueado no futuro — fallback Firefox documentado em BRIEFING-ODIN-2026-05-15.md
- ❌ `name: null` em todos eventos no normalize do danewell (bug ativo, fix em andamento)

**Status:** ATIVA. Bridge `/events/live` deployed em commit pendente. Aguardando fix do `name` no normalizer do danewell.

---

## 2026-05-16 (sessão 5) — Fase D.2: descoberta automática de fixtures Betano

**Contexto:** Após D.1 funcional (bridge `/events/live` retornando eventos estruturados), próxima fase é eliminar o `BETANO_EVENT_MAP` manual — popular `betano_fixture_map` automaticamente fazendo match entre eventos Betano e fixtures API-Football das ligas monitoradas.

**Decisão:** 4 componentes novos, faseados em 4 partes (B, C, D, E):

- **B. Nova tabela `betano_team_map`** (migration 0004) — mapping Betano team_id ↔ API-Football team_id, com `match_method` ('static_catalog'|'fuzzy'|'manual'), `match_confidence` (0-1), índice `gin_trgm_ops` pra similarity search SQL-side.
- **C. `FixtureMatcher`** (data/discovery/) — stateless de IO, recebe `betano_event` + `candidate_fixtures` (lista API-Football). Tenta lookup determinístico via team_id; se algum team não mapeado, faz fuzzy fallback com `rapidfuzz.fuzz.ratio` em nomes normalizados (lowercase, sem acentos, sem FC/SC/CF/(F)/(M)/etc), valida kickoff ±30min, threshold 0.85. Match fuzzy bem-sucedido UPSERTa teams resolvidos no map.
- **D. `BetanoFixtureDiscovery` worker** — asyncio.Task, poll bridge `/events/live?sport=FOOT` a cada 150s (configurável), reusa `get_today_schedule` via cache diário, chama matcher por evento, UPSERT em `fixture_map` com `resolved_via='discovery_team_id_lookup'` ou `'discovery_fuzzy'`. Fail-soft em 3 níveis (bridge down → skip ciclo, matcher except → skip evento, upsert except → skip fixture).
- **E. `BETANO_EVENT_MAP` vira override opcional** — log explicitando 3 cenários (override manual, descoberta automática, ou warning se ambos desligados).

**Alternativas consideradas:**
- Receber `api_client` no matcher — descartado, prefere caller injetar fixtures pra facilitar testes
- Matcher fazer fuzzy database-side (pg_trgm) — viável mas menos flexível pra signal de scoring; rapidfuzz Python-side com normalização customizada é mais rico
- Refresh do catálogo `/teams` no worker (PARTE A) — ADIADO até bridge ganhar endpoint `/teams` que depende do danewell adicionar `/danae/teams` no renewer
- Worker em thread separada vs asyncio.Task — Task é consistente com `OddsPersistenceWorker`

**Trade-offs:**
- ✅ Eliminação progressiva do `BETANO_EVENT_MAP` (fica como override DEV/manual)
- ✅ Self-healing: matches fuzzy alimentam o team_map → próximos lookups viram determinísticos (`confidence=1.0`)
- ✅ Worker isolado (Task) — não interfere com `_main_loop` nem outros workers
- ✅ 0 requests adicionais à API-Football (reusa `get_today_schedule` cacheado)
- ✅ 24 testes novos (7 repo + 10 matcher + 6 worker + 1 verde geral)
- ❌ Sem PARTE A (`/teams` no bridge), catálogo Betano não é populado proativamente — só matches on-demand criam entries
- ❌ Validação E2E ainda sem overlap real (jogos noturnos atuais são fora das ligas monitoradas — esperado, não bug)

**Status:** ATIVA. Worker rodando em produção desde 2026-05-16 ~02h UTC.

**PARTE A entregue em sessão 6 (2026-05-16 ~03h UTC):**
- Achado: `/api/static-content/assets/teams` (8.8MB) tem só logos/cores, ZERO `name`. Não serve pra `betano_team_map.betano_team_name`.
- Solução: danewell ganha `/danae/teams` que agrega `participants[]` de `/danae/live` + `/api/home/upcoming-coupons` (fetch paralelo, dedupe por team_id, live > upcoming, source debug). Bridge ganha `/teams` proxy com cache 24h em memória (key por sport, configurável via `TEAMS_CACHE_TTL_SEC`). Worker chama 1×/dia, `bulk_upsert` com `match_method='static_catalog'`.
- Validado em produção: 92 teams populados via static_catalog. Bridge cache: 5.07s miss → 42ms hit.
- Nenhuma mudança no FixtureMatcher — lookup determinístico já estava implementado na PARTE C original (commit 90d7675).

---

## 2026-05-15 (sessão 4 — extensão proxy) — Isolamento de egress por browser pool

**Contexto:** Após D.1 funcional, comprado proxy residencial brasileiro (ML Telecom RJ, `200.234.172.57:43958`) pra diversificar IP de saída do Brave (que atende Danae API). IP da casa (V tal Curitiba, `200.181.212.29`) é único hoje pra tudo — se Cloudflare reflagar, perde tudo junto.

**Decisão:** Aplicar proxy SOMENTE no Brave do pool (rota Danae API). Chrome do pool (rota markets/quote) mantém saída pelo IP da casa. Wrapper via `tinyproxy-betano.service` local em `127.0.0.1:8888` que injeta auth no upstream — Chromium 148 não suporta auth inline em `--proxy-server` (Alt-A do plano original falhou, escalou pra Alt-B).

**Isolamento intencional:**
- Brave → proxy ML Telecom RJ → `/danae-webapi/*` (D.1 listagem)
- Chrome → IP casa V tal Curitiba → `/odds/<id>/` (D.0 markets via Playwright)

**Alternativas consideradas:**
- Proxy em ambos browsers — perde diversificação, single point of failure
- Auth inline na `--proxy-server` — Chromium 148 ignora credenciais inline em HTTP proxies (validado)
- PAC URL — overkill pra 1 proxy
- VPN sistema-wide — afetaria tudo (WAHA, dashboard, SSH, etc), inviável

**Trade-offs:**
- ✅ Diversificação: 2 IPs distintos, redução de blast radius se 1 flaguear
- ✅ Brave proxy é residencial brasileiro real (ML Telecom RJ) — Cloudflare aceita
- ✅ Chrome intacto pra `/markets` continua via IP casa (sem mudança de comportamento)
- ✅ Latência D.1 inalterada (~5s — overhead 800ms do proxy é absorvido pelo wait fixo de 3s do renewer)
- ❌ Custo recorrente do proxy
- ❌ Credenciais visíveis em `systemctl cat brave-betano` (mitigar movendo pra arquivo chmod 600 em fase 2)
- ❌ Mais infra (tinyproxy + 1 service novo), mais coisa pra monitorar

**Status:** ATIVA. Brave egress validado em ML Telecom RJ. /events/live continua retornando 15+ eventos reais em ~5s. Rollback documentado no [BRIEFING-ODIN-2026-05-15 (2).md](../BRIEFING-ODIN-2026-05-15%20(2).md) com backup imutável da unit pré-proxy.

---

## 2026-05-15 (sessão 3) — D.1 vai usar API HTTP nativa, não DOM scrape

**Contexto:** Plano original da Fase D.1 (descoberta automática de eventos) era usar Playwright via bridge pra abrir listagens (`/live/`, `/sport/futebol/`) e parsear DOM/links. Investigação via mitmproxy (capturado no PC do daniel, não-flagueado) descobriu que a Betano expõe `/danae-webapi/api/live/overview/latest` — JSON estruturado com 301 eventos ao vivo, schemas completos de leagues/zones/sports, auth só via cookie `_cfuvid`.

**Decisão:** D.1 implementa endpoints `/events/live` e `/events/today` no bridge fazendo requests HTTP diretas à Danae API, NÃO via Playwright/DOM scrape. Chrome continua aquecido apenas pra renovar cookies periodicamente (warmup loop). Ver [`docs/architecture/betano-danae-api.md`](architecture/betano-danae-api.md) pra mapeamento completo.

**Alternativas consideradas:**
- DOM scrape via Playwright (plano original) — abandonado: 8s/captura vs 150ms HTTP, frágil contra mudanças de UI, vulnerável a Splash Screen quando IP flagueado, captura limitada (sem context rico de league/zone)
- SignalR WebSocket subscribe — adiado: requer SignalR Core client em Python, e polling 60s à API HTTP cobre o caso de descoberta. SignalR fica como otimização Phase H se latência virar gargalo

**Trade-offs:**
- ✅ Latência ~50× menor (150ms vs 8s)
- ✅ Dados nativos (league_id, zone_id, betRadarId pra fuzzy match D.2)
- ✅ Não compete com anti-bot da Betano (cliente HTTP normal com cookie válido)
- ✅ Catálogos estáticos (`/api/static-content/assets/leagues|teams`) habilitam cache local
- ❌ Endpoint não documentado — pode mudar (mitigado por monitorar `version`/`contentVersion` do response)
- ❌ Dependência operacional do warmup Chrome (se cookie expira e Chrome cai, /events/* quebra)

**Status:** ATIVA, implementação D.1 v2 pendente.

---

## 2026-05-15 — Pool distribuído de Chromes (Fase Bridge Pool)

**Contexto:** Único Chrome local na odin = ponto de falha. Sem redundância. Sem capacidade pra crescer.

**Decisão:** Bridge orquestrador com pool de N endpoints CDP. Round-robin + health check + failover automático. Primeiros nós: odin localhost:9223 + danewell 192.168.1.5:9223 (mesma LAN, IPs da mesma casa).

**Alternativas consideradas:**
- Proxy residencial pago (BrightData) — caro, recorrente, futuro
- Single Chrome (status quo) — sem redundância

**Trade-offs:**
- ✅ Dobra capacidade (~12 req/min)
- ✅ Failover automático (1 Chrome cai, outro segura)
- ✅ Setup PC novo prova arquitetura distribuída
- ❌ Mesmo IP residencial em ambos nós (não diversifica IP de fato)
- ❌ Complexidade operacional (2 Chromes pra monitorar)

**Status:** ATIVA. Próxima evolução: PC em outra rede ou proxy residencial pra diversificar IP.

---

## 2026-05-16 — Fase E.1 stats Betano via `/danae-webapi/api/live/events/<id>/latest` (CASO α)

**Contexto:** Fase E exige substituir runtime de stats da API-Football pelo Betano direto (eliminar dependência do crédito AF). Antes de E.1 (implementação), E.0 mapeia endpoints disponíveis. Investigação feita 2026-05-16 sobre captura mitm 2026-05-15 já existente (zero risco, sem novo tráfego no IP residencial).

**Decisão:** **CASO α — API JSON nativa.** Adapter de stats vai consumir `/danae-webapi/api/live/events/<id>/latest` (mesma família Danae já usada por D.1 pra discovery). Reusa pipeline D.1 existente: Brave do pool (danewell:9224) com cookie `_cfuvid` aquecido, `fetch()` via CDP raw no renewer. Bridge da odin adiciona rota `/event/<id>/state` que proxia + normaliza.

Schema completo + cobertura comparativa em [`architecture/betano-stats-api.md`](architecture/betano-stats-api.md). Resumo: `event.liveData.results` cobre todas métricas usadas hoje (`corners`, `yellow`, `shots`, `score`, `clock.secondsSinceStart`) + bonus `xGoals`. `event.incidents[]` cobre timeline rica (GOAL, YELL, CRNR, OFFS, SUBS, PENL, StoppageTime, etc.) pra reconstrução fina de janelas.

**Alternativas consideradas:**
- **CASO β (page parsing DOM)** — descartado: API JSON existe e é mais robusta
- **WebSocket `/sbpitches/statsstream/matchhub`** — adiado pra E.2 (push real-time se polling 60s ficar lento)
- **API-Football mantido como primário** — descartado: objetivo da Fase E é justamente eliminar dependência

**Trade-offs:**
- ✅ Reusa **100%** da infra D.1 (Brave + renewer + cookies) — incremento marginal mínimo
- ✅ Cobre todas métricas atuais + xG (não existe na AF)
- ✅ Clock em segundos (vs minutos na AF) → janelas mais precisas
- ✅ Polling 60s no `/latest` (`version` incrementa) detecta mudanças sem reparsing
- ❌ `event.statistics.*` (16 stat IDs numéricos) é opaco — usar só `liveData.results` (cobertura suficiente)
- ❌ Cobertura varia por liga (`coverage_level`) — algumas ligas só têm `corners`. Normalizador trata como `0`/`None`
- ❌ Sem `shots_on_target` e `possession%` (AF tem) — gap aceitável pra MVP, reavaliar se modelo exigir
- ❌ Risco de schema mudar (Danae não-documentada) — mitigado por monitorar `version` no response

**Estimativa Fase E.1 atualizada:** 6-10h (vs 10-14h originalmente). Redução porque infra D.1 já está em produção e estável.

**Status:** ATIVA, implementação E.1 pendente.


## 2026-05-17 — Fase K.0 SofaScore como fallback / dataset extra (CASO α via `curl_cffi`)

**Contexto:** Após G.1 entregue (Caminho A soft ~75%), restava decidir como tratar a residual dependência de API-Football no fallback de stats/events/lineups (E.1, F, G.1 todos têm AF como segundo Composite). AF está sem créditos no momento (CLAUDE.md §10) → pipeline depende de provedor sem garantia operacional. Fase K.0 investiga SofaScore como **substituto do fallback AF + fonte de dados novos** (standings, lesões, coach, gráficos temporais).

**Decisão:** **CASO α puro — `curl_cffi` impersonate Chrome direto via aiohttp adapter, sem bridge.**

SofaScore bloqueia clientes Python (`requests`/`aiohttp`/`curl` simples) via TLS fingerprint (JA3) — 403 Varnish uniforme. Browser real passa normal. Solução: lib `curl_cffi` (Python wrapper para `libcurl-impersonate-chrome`) replica TLS handshake de Chrome. **10/10 endpoints testados respondem 200 OK do servidor CPES com IP residencial bloqueado por curl simples.**

Detalhes técnicos completos em [`architecture/sofascore-api.md`](architecture/sofascore-api.md). Resumo:

- **Anti-bot bypass:** `cr.get(url, impersonate='chrome120')` em vez de `requests.get(url)`. Zero infra adicional, lib instalável via pip.
- **Rate limit:** 70 reqs em 1.5s = 47 req/s sem 429 (sustentado). Margem >150× sobre uso CPES (~0.3 req/s).
- **Cobertura:** 31 endpoints validados via HAR. Stats por **período** (1H/2H/ALL), `coach_name` via `/managers` dedicado (★ resolve gap Betano), `missingPlayers` (★ lesões+suspensões no `/lineups`), standings completa com `promotion` (Libertadores/relegation), team-performance-graph temporal, pregame-form, best-players, average-positions, win-probability graph.

**Alternativas consideradas:**
- **CASO β — bridge dedicado com Chrome real:** rejeitado — `curl_cffi` resolve sem browser. Bridge adiciona ~25h dev + custos operacionais (renewer warmup, pool, etc).
- **CASO γ — proxy residencial rotativo:** rejeitado — IP não é o problema (Daniel acessou normal do mesmo IP via Firefox). Custo $10-50/mês desnecessário.
- **Manter AF como fallback:** rejeitado — chave AF expira, sem créditos no momento, custo recorrente $50/mês, pipeline cego quando AF down. SofaScore é grátis.

**Trade-offs:**
- ✅ Zero infra adicional (curl_cffi via pip, igual qualquer lib Python).
- ✅ Resolve gap Betano (coach, lesões, standings) + adiciona dados novos (best-players, pregame-form, performance-graph).
- ✅ Stats RICAS por período (1H/2H/ALL × 7 grupos) — superior a Betano e AF.
- ✅ Brasileirão + MLS + Premier todos cobertos (samples validados).
- ❌ Dependência de `libcurl-impersonate-chrome` binário no container (1 linha Dockerfile, comum em data-scraping).
- ❌ Risco SofaScore atualizar JA3 → trocar versão impersonate (chrome116 → chrome124 etc).
- ❌ Sem endpoint dedicado `/injuries` por time (vem via `/lineups.missingPlayers`, escopo: jogo).

**Estimativa Fase K.1:** 25-35h em ~5 sessões. Worker novo (standings) + 3 adapters Composite (stats/events/lineups com SofaScore fallback) + extensão `CanonicalLineup` (coach_name + missing_players) + ~30 testes + smoke.

**Status:** APROVADA pendente revisão. Implementação K.1 a iniciar quando Daniel der go.

---

## 2026-05-17 — Fase G.1 lineups Betano via `event.roster` (CASO α puro)

**Contexto:** Fase G originalmente prevista pra investigar endpoint dedicado
de lineups (`/api/statsstream/<id>/info/aggregated/` candidato no E.0).
Investigação G.0 (esta sessão) descobriu que **`event.roster` no payload
`/event/<id>/state` já capturado pela Fase E.1 contém lineups completas** —
zero novo endpoint, zero novo trabalho no bridge/renewer.

**Decisão:** **CASO α puro — extrator + persistência sobre payload já capturado.**
Worker `BetanoLineupsWorker` extrai `payload.event.roster` no parse,
não faz nova request HTTP. Compartilha cache de version com `BridgeStatsAdapter`
quando a otimização de cache compartilhado da Fase I for implementada.

Schema completo + cobertura comparativa em [`architecture/betano-lineups-api.md`](architecture/betano-lineups-api.md).
Resumo: `roster.lineups.{home,away}Lineup` traz `formation` (string ex `"5-4-1"`) +
`lineup[][]` (linhas táticas) + `benchPlayers[]`. `roster.{home,away}Roster.players`
traz **squad completo** (26-38 jogadores) com `shirtNumber`, `position` (GK/DF/MF/FW)
e `positionDisplayName` localizado pt-BR.

**Alternativas consideradas:**
- **CASO α — endpoint dedicado `/api/statsstream/<id>/info/aggregated/`** — investigado mas redundante (mesmo subconjunto de dados que `event.roster`). Não justifica request HTTP extra.
- **CASO β (HTML parsing)** — descartado: dados existem em API.
- **API-Football mantido como primário** — descartado por consistência com E.1/F.

**Trade-offs:**
- ✅ Zero nova request HTTP — reusa payload que worker E.1 já busca a cada poll.
- ✅ Schema rico: formation + lineup tática + bench + squad completo.
- ✅ Coverage idêntica à E.1 (mesma fonte Opta) — ligas profissionais OK, ligas pequenas/esports zero.
- ✅ `positionDisplayName` localizado em PT-BR (AF não tem).
- ❌ **Coach (técnico) não vem.** AF tem. Gap aceitável pra MVP (decision_engine não consome; H2-H4 podem usar formation+XI qualidade).
- ❌ Não distingue lineup `confirmed` vs `presumed`. Mitigação: polling continua + UNIQUE com `captured_at` permite múltiplos snapshots.
- ❌ `unknownPlayerId` (UUID local) em players sem ID Betano — persistir como `player_id=NULL`.

**Estimativa Fase G.1 atualizada:** 5h (vs 6-10h originalmente). Redução
porque endpoint já está sendo consumido — só precisa novo extrator +
schema novo + worker + ~15 testes.

**Status:** APROVADA pendente revisão, implementação G.1 a iniciar quando Daniel der go.

## 2026-05-17 — Sistema de decisão por sinal: opt-in (default = não entrou)

**Contexto:** Sistema gera signals globalmente (1 signal serve TODOS os users pagos). Mas ROI/winrate per-user devem refletir SO as apostas que o user efetivamente entrou. Antes da Sprint M, stats do `/dashboard` vinham de `get_db_stats()` global — qualquer user via "76.9% winrate" mesmo nunca tendo apostado.

**Decisão:** Sinal nasce em estado `pending` para cada user. User clica explicitamente em **[✓ ENTREI (odd X / valor Y)]** ou **[✗ PULEI]** pra mover de pending. Stats user-scoped contam SO decisões `entered` com resultado resolvido.

**Alternativas consideradas:**
- **(B) Opt-OUT (default = entrou):** Sinais auto-confirmados; user precisa "pular" pra excluir. Mais agressivo, valida o sistema rapidamente. Rejeitado: trader que pular X jogo na vida real e o sistema marcar como GREEN/RED pra ele é mentira — assume entrada quando não houve. ROI vira aspiracional, não real.
- **(C) Híbrido com timer:** Sinal pending por X minutos, depois auto-PULA. Espelha realidade do trading (timing matter). Rejeitado pra MVP: complica UX (precisa countdown visual, regras de "perdeu janela", edge cases de timezone). Pode virar feature depois.

**Trade-offs:**
- ✅ ROI real, não aspiracional. User só vê números que ele construiu.
- ✅ Cada user tem seu próprio dashboard (multi-tenant real).
- ✅ Schema simples: `user_signal_decisions(user_id, signal_id, decision, odd_entrada, valor_apostado_cents, resultado, payout_cents)`. UNIQUE(user_id, signal_id).
- ✅ Default pending preserva possibilidade futura de retroatividade ("marcar histórico").
- ❌ Friction UX: 2 cliques por signal (modal pra odd+valor). Mitigação: modal pré-preenche odd do signal e valor=banca×unit_pct.
- ❌ Stats demoram a "aparecer" para user novo. Mitigação: banner sugerindo configurar banca + entrar nos primeiros sinais.

**Implementação:** Migration `0012_user_signal_decisions.sql`, `UserSignalDecisionsRepo`, endpoints `POST /api/signals/{id}/decision` + `GET /api/users/me/{stats,signals}`, refactor `/dashboard` page. Commit `feat(decisions): migration 0012 + UserSignalDecisionsRepo` + correlatos.

## 2026-05-17 — Banca per-user (1:1) com movements imutáveis e movement-stake otimista

**Contexto:** Cada user precisa de bankroll isolado (não global) com histórico auditável. Necessidade óbvia de multi-tenancy + reconstrução histórica do saldo pra séries temporais e drawdown.

**Decisão:** Schema 2-tabelas:
- `banca` (user_id PK FK 1:1): `banca_inicial_cents`, `banca_atual_cents` (denormalizado pra evitar SUM em cada read), `currency`, `unit_pct`, limits.
- `banca_movements` (id, user_id FK 1:N): tipo `deposit|withdraw|correction|bet_win|bet_loss|bet_void|reset`, `valor_cents` (signed), `bet_id` (FK opcional pra `user_signal_decisions.id`), `saldo_apos_cents` (snapshot p/ reconstruir sem re-SUM).

**Decisão correlata — movement-stake otimista:** Quando user decide `entered`, geramos imediatamente um movement `bet_loss` negativo do valor stake (debita saldo otimisticamente). Quando o signal resolve GREEN, geramos `bet_win` positivo com `stake * (odd - 1) + stake` (devolve stake + lucro). Em RED, o `bet_loss` original já refletiu a perda — nada mais a fazer.

**Alternativas consideradas:**
- **Schema agregado único** (banca com `pnl_running`, sem movements): rejeitado — perde audit trail.
- **Bet pendente sem afetar saldo** (só debita quando settle): rejeitado — saldo "fictício" durante apostas em curso engana decisão do user sobre próximas entradas (ele acha que tem mais dinheiro que tem).
- **`stake_pendente` field separado** (não-debita banca_atual): bom mas complica leitura/escrita. Difere YAGNI até reclamarem.

**Trade-offs:**
- ✅ Audit trail completo via movements.
- ✅ `banca_atual_cents` denormalizado = O(1) read.
- ✅ Stake otimista = saldo reflete realidade (incluindo apostas em curso).
- ✅ Schema preparado pra `bet_void` (anula sem afetar PnL) e `correction` (ajuste manual c/ motivo).
- ❌ Re-trigger settle precisa cuidar pra não duplicar `bet_win`. Mitigação: `WHERE resultado IS NULL` no UPDATE.
- ❌ Se `settle` falhar entre o `bet_loss` otimista e o `bet_win` real, banca fica errada. Mitigação futura: job de reconciliação batch.

**Implementação:** Migration `0011_banca.sql`, `BancaRepo`, 6 endpoints `/api/banca/*`. Commit `feat(banca): migration 0011 + BancaRepo` + correlatos.
