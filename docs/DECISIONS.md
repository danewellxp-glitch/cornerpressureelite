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
