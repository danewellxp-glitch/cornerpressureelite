# BUGS ENCONTRADOS E CORRIGIDOS

Cada bug catalogado: **sintoma + causa raiz + fix + lição**. Cresce dia a dia, evita repetição.

**Formato:**
```
YYYY-MM-DD — Título curto
Sintoma: o que se observava
Causa raiz: o que estava errado
Fix: o que foi mudado
Lição: o que aprendemos / como prevenir
Commit: hash (se aplicável)
```

---

## 2026-05-17 — Login não entra no dashboard (redirect loop)

**Sintoma:** Usuário logava em `iqpressure.online/login` com sucesso (API retornava 200 + token), cookie `cpes-auth` era setado, mas qualquer navegação pra `/dashboard` redirecionava de volta pro `/login` infinitamente.

**Causa raiz:** O middleware do Next.js (`dashboard/src/middleware.ts`) verifica o JWT com `process.env.JWT_SECRET || "cpes-jwt-secret-key-2026-super-secure"`. O serviço `dashboard` em `docker-compose.yml` não passava `JWT_SECRET` no environment, e `dashboard/.env.production` (que tem o valor correto) está bloqueado pelo `.dockerignore` (`.env*`). Resultado: middleware caía no fallback `"cpes-jwt-secret-key-2026-super-secure"` enquanto API assinava com `changeme_please_generate_a_secure_random_string_12345` → `jwtVerify` lançava → redirect pra `/login`.

**Fix:** Adicionar `env_file: ./corner-pressure-elite/.env` ao serviço `dashboard` no `docker-compose.yml`. Mesma fonte da API, garante simetria do segredo.

**Lição:** `.env*` no `.dockerignore` é boa prática, mas exige que segredos cheguem ao container por outro caminho (env_file no compose ou Docker secrets). Se middleware tem fallback embutido pra segredo, ele esconde silenciosamente esse tipo de erro — preferir `throw` quando env crítica está ausente.

---

## 2026-05-14 — Deadlock circular gate de cartões

**Sintoma:** Bridge nunca era chamado pra cartões. Nenhum sinal de cartões emitido em ~3 semanas.

**Causa raiz:** `_analisar_jogo` em main.py usava `decision_engine.avaliar()` como gate da busca de odds. Mas `avaliar()` exige `jogo.linha_cartoes > 0`, e `linha_cartoes` só é populado APÓS busca de odds. Deadlock circular.

**Fix:** Trocar gate pra `pre_avaliar()` (não exige linha). Padrão simétrico do path de escanteios. Commit `6673f2a`.

**Lição:** Quando código tem aparente "ordem natural" mas algum estado depende de outro circularmente, repensar. Sempre adicionar smoke real em jogo ao vivo antes de declarar feature pronta — unit tests passaram falsos por mockar estado.

---

## 2026-05-14 — Bridge bindando em 127.0.0.1

**Sintoma:** Container CPES não alcançava bridge. `ConnectError [Errno 111] Connection refused` em todas chamadas.

**Causa raiz:** `server.py` usava `uvicorn.run(host="127.0.0.1")`. Loopback do host, inacessível do container.

**Fix:** Mudar pra `host="0.0.0.0"`. Commit `2847deb` (cpes-bridge).

**Lição:** Default pra `0.0.0.0` em serviços que vão ser chamados de containers/outras máquinas. `127.0.0.1` parece "seguro" mas vira armadilha em arquitetura distribuída.

---

## 2026-05-14 — cartoes_amarelos vs cartoes_amarelos_total

**Sintoma:** Após Sinal CARTOES #113 sair, todos ciclos seguintes crashavam com `'JogoAoVivo' object has no attribute 'cartoes_amarelos'`.

**Causa raiz:** `cards_state_manager.py:78` acessava `jogo.cartoes_amarelos`. Atributo real é `cartoes_amarelos_total`. Bug latente revelado pelo fix do deadlock (antes desse fix, `deve_reavaliar` nunca era alcançado).

**Fix:** Renomear acesso. Commit `5fa4264`.

**Lição:** Fix de bug pode revelar outros bugs latentes em paths nunca exercitados. Smoke real em jogo ao vivo até FIM é mais revelador que smoke de 5min.

---

## 2026-05-15 — odds_persistence_worker=None silencioso

**Sintoma:** Schema, repo, worker tudo implementado. Mas `odds_history` tinha 0 linhas. Telemetria parecia funcionar (logs ok) mas nada persistia.

**Causa raiz:** `main.py:175` hardcoded `odds_persistence_worker=None` em build_providers. Worker nunca era instanciado.

**Fix:** Instanciar `OddsPersistenceWorker(OddsHistoryRepo(pool))` em `iniciar()`, passar como kwarg. Commit `417c367`.

**Lição:** Trabalho de sessão anterior pode deixar peças "implementadas mas desconectadas". Sempre validar end-to-end com dado real chegando ao DB.

---

## 2026-05-15 — Cookies cf_clearance bound a IP+TLS+UA do Chrome originador

**Sintoma:** Após descobrir endpoint `/danae-webapi/api/live/overview/latest`, primeira tentativa de implementar `/events/live` no bridge da odin foi: extrair cookies frescos via `/cookies/last` do renewer (no danewell) e usar em httpx puro na odin. Sempre 403, mesmo com:
- Cookies <1min de idade (válidos no Brave que originou)
- UA exato do Chrome 148 que emitiu o cookie
- IP da casa idêntico (NAT compartilhado entre odin e danewell)
- Headers Sec-Fetch-* completos
- Testado IPv4 e IPv6 separadamente
- Tentado urllib (stdlib) também — mesmo 403

**Causa raiz:** `cf_clearance` da Cloudflare é **bound a tripla (IP cliente + TLS fingerprint do client + UA exato)**. Replicar 2 dos 3 não é suficiente. Cliente HTTP Python tem TLS handshake (cipher order, extensions) diferente do Chrome — Cloudflare detecta mismatch entre cookie issuer e client atual, rejeita.

Validações que provaram:
- Cookies do .mitm (capturados do Firefox humano do Daniel) funcionavam em urllib na odin imediatamente, mas pararam após ~30min (não foi expiração — algo no estado do Cloudflare/IP).
- Cookies do `/cookies/last` do renewer **nunca** funcionaram em curl/httpx/urllib externos.
- `Playwright.connect_over_cdp` no Chrome do pool danewell + `page.goto` disparou Splash imediato (`__playwright__binding__` detectável).
- **Único caminho que funciona**: `fetch()` DENTRO do mesmo browser (Brave, no caso) que tem o cookie, via CDP raw (sem Playwright bindings).

**Fix:** Arquitetura D.1 final usa proxy via danewell renewer:
- Bridge da odin (`/events/live`) → danewell renewer (`/danae/live`) → Brave do pool faz `fetch()` interno → JSON normalizado de volta
- Bridge não toca em cookies, TLS ou Chrome — só HTTP simples na LAN
- Detalhes em [DECISIONS.md sessão 4](DECISIONS.md#2026-05-15-sessão-4--d1-final-bridge-proxy-ao-danewell-renewer) e [betano-danae-api.md §4](architecture/betano-danae-api.md)

**Lição:** Cookies de Cloudflare **não são portáteis entre clients HTTP**. Pra usar a sessão de um Chrome aquecido, a request HTTP tem que sair daquele mesmo Chrome. Patterns válidos:
1. `fetch()` dentro do browser via CDP raw (`Runtime.evaluate` com `awaitPromise: true`)
2. Proxy do tráfego inteiro pelo browser (mais complexo, não fizemos)

**Lição adicional descoberta no caminho:** **TLS fingerprint do Chrome 148 desktop Linux x86_64 está discriminado** especificamente em `/danae-webapi/*` da Betano. Mesmo profile fresco + flags stealth, Chrome 148 retorna Splash. **Brave 1.90.122 (Chromium 148, mas TLS diferente + `navigator.brave` exposto) passa**. Solução: instalar Brave em paralelo no danewell, usar dele pra Danae API. Chrome continua útil pra `/odds/<id>/` (mercados via Playwright) que não passam por `/danae-webapi/*`.

---

## 2026-05-15 — IP residencial flagueado pela Cloudflare Bot Management

**Sintoma:** Após investigação D.1 via Playwright, todas as URLs da Betano (incluindo páginas de jogo individuais que sempre funcionaram) começaram a retornar **"Betano Splash Screen"** com `body.innerText: 0 chars`. Mensagem visível: *"Access to this page is restricted due to security and compliance measures"*. Pool 2/2 ainda mostrava `healthy` (CDP responde), mas Chrome ambos endpoints recebiam Splash. Bridge `/markets` retornava `text_len=0, page_title="Betano Splash Screen"`.

**Causa raiz:** Combinação de sinais que disparou Cloudflare Bot Management no IP residencial:
1. **Burst** — ~30 navegações em 10min num IP que normalmente faz 0
2. **URLs 404** — script `investigate_betano_v3.py` testou 10 URLs candidatas, 7 não existem (ex: `/inplay/`, `/sport/futebol/jogos-de-hoje/`). Bater 404s em sequência é assinatura clássica de scraper recon
3. **Sem interação humana** — Playwright vai pra próxima URL sem mouse/scroll/focus events
4. **Profile com mudança de padrão** — perfil tinha cookies de scraping de mercados, mudou pra navegação em listagens
5. **Mesmo IP pra ambos endpoints** (odin localhost + danewell LAN) — flag foi no IP residencial, ambos caíram juntos

**Fix:** Não há fix imediato. Cloudflare WAF block tem TTL ~12-24h, deve desbloquear sozinho. Estratégias defensivas pra próximas sessões em [DECISIONS.md](DECISIONS.md#2026-05-15-sessão-3--d1-vai-usar-api-http-nativa-não-dom-scrape):
- D.1 vai usar API HTTP nativa (Danae) em vez de DOM scrape, eliminando bursts de page navigations
- Polling baixo (60s+) e nunca testar URLs sem validação prévia
- Mitmproxy do PC do daniel (não-flagueado) usado pra investigações futuras de schema

**Lição:** Investigação técnica via Playwright em IP residencial **é caminho de mão única** — qualquer burst dispara flag global no IP. Pra exploração, preferir mitmproxy + navegador real do user, **nunca** scripts Playwright em sequência rápida no IP de produção. Se precisar Playwright pra investigar, usar VPN/proxy descartável (não o IP do bridge).

Checklist defensivo consolidado em [`docs/architecture/playwright-anti-bot-checklist.md`](architecture/playwright-anti-bot-checklist.md) — ler antes de qualquer sessão futura de scraping.

---

## 2026-05-15 — Bridge sem auto-restart (reboot da odin)

**Sintoma:** Odin reiniciou de madrugada. Containers Docker subiram automaticamente (auto-start). Bridge ficou DESLIGADO.

**Causa raiz:** Bridge rodava via `nohup python server.py & disown`. Sem systemd unit. Quando shell de sessão SSH fechou no reboot, processo morreu sem auto-restart.

**Fix:** 3 systemd user units encadeadas (`xvfb-bridge.service` → `chrome-bridge.service` → `cpes-bridge.service`) com `Restart=always` e `Requires/After`. `loginctl enable-linger daniel` pra services sobreviverem a logoff e subirem no boot. Units versionadas em `~/cpes-bridge/systemd/`. Cenário A (kill bridge → auto-restart em <14s) validado; Cenário B (reboot real) pendente. Ver `OPERATIONS.md` seção "Stack systemd".

**Lição:** Toda dependência crítica precisa ser systemd-managed. `nohup` é gambiarra pra dev, não pra produção. **Detalhe importante:** `Restart=on-failure` NÃO restarta em SIGTERM (kill manual considerado "graceful"). Pra resiliência real contra kill externo, usar `Restart=always`.

---

## 2026-05-16 — [FALSO-BUG] Discovery sem capturas iniciais é normal

**Sintoma:** Fixtures descobertos via D.2 BetanoFixtureDiscovery aparecem em `betano_fixture_map` com `confidence=1.00`, mas `odds_history` mostra só **1-3 capturas em burst único** logo após o match e depois zero. Comparado com fixtures antigos no mesmo intervalo (50-79 capturas), parece bug grave.

**Causa raiz:** **Não é bug.** Comportamento por design do `adaptive_polling`. Os fixtures novos descobertos estavam no **minuto 26 do 1T** — fase `pre_janela` (min < 50 E corners < 7, ver `main.py:692-693` e `config.py:19,27`). Nessa fase o polling adaptativo decide não gastar requisição. As 1-3 capturas iniciais foram burst do primeiro ciclo logo após o discovery popular o mapa, antes do `adaptive_polling` reconhecer a fase. Fixtures antigos com 50+ capturas já estavam em `na_janela` (min 50+) ou no fim do jogo.

**Fix:** Nenhum. Sistema funcionando como projetado. Capturas escalam automaticamente quando fixture entra em `na_janela` (min ≥ 50 OU corners ≥ 7).

**Sinais que confirmam comportamento correto:**
- `_main_loop` loga `[DEBUG LIVE] X live → Y fixtures` continuamente
- `betano_discovery` continua casando event_ids em ciclos (a cada ~2-3min)
- `betano_fixture_map` tem o mapeamento gravado com `resolved_via=discovery_team_id_lookup`
- Bridge silencioso pros novos = `adaptive_polling` decidiu não chamar (não é erro, é decisão)

**Como validar (próxima vez que aparentar o mesmo "sintoma"):**
1. Checar minuto do jogo via API-Football (ver `OPERATIONS.md` → "Listar jogos elegíveis pra smoke")
2. Se minuto < 50 e corners < 7 → comportamento correto, aguardar
3. Quando fixture cruzar pra `na_janela`, capturas escalam pra 50+ automaticamente

**Lição:** Comparar "fixture novo (min 26)" com "fixture antigo (min 75)" no mesmo snapshot de `odds_history` é falsa equivalência — cada fixture passa por `pre → na → pos` sequencialmente. Antes de declarar bug em pipeline com polling adaptativo, sempre **checar a fase atual** do fixture, não só contar linhas no DB.


## 2026-05-17 — fetchSignalsList(limit=2000) → backend rejeita 400

**Sintoma:** `/dashboard`, `/performance`, `/aprenda` aparecem **sem dados nenhum** (loading state + error banner). `/escanteios` e `/cartoes-amarelos` na mesma sessão funcionam normais.

**Causa raiz:** Backend `/api/signals/list` valida `limit 1..500` (`api_server.py`). Três páginas frontend chamavam `fetchSignalsList("all", 2000)`. Resposta 400 com `{"detail":"limit 1..500"}`. Catch silencioso (`.catch(() => {})` em aprenda/performance, `console.error` em dashboard), `allSignals=[]`, render normal mas vazio. As outras páginas (MarketPage, sinais-historico) pediam 500 — passavam.

**Fix:** `2000 → 500` nos 3 callers (`dashboard/page.tsx:97`, `performance/page.tsx:57`, `aprenda/page.tsx:24`). Commit `8cfa970`.

**Lição:** Backend caps silenciosos viram bug de UX invisível quando frontend tem error handling fraco. Validações de range devem aparecer em swagger/types, e catches devem mostrar erro visível em DEV mode pelo menos.

## 2026-05-17 — Cloudflare gzip quebra SSE EventSource

**Sintoma:** `/jogos-ao-vivo` (e qualquer página com `useDashboard()` hook) ficava com status `connected` mas `data === null` eternamente. Backend retornava 200 OK no `/api/stream/dashboard` (logs confirmavam), mas `onmessage` no client nunca disparava.

**Causa raiz:** Cloudflare adicionava `Content-Encoding: gzip` em respostas `text/event-stream` no edge. Backend direto NÃO comprimia (verificado via curl interno), mas via CF o header `content-encoding: gzip` aparecia. gzip bufferiza dados antes de emitir o primeiro chunk — SSE manda eventos pequenos (~1KB) a cada 2s, então o primeiro byte gzipped nunca chegava ao cliente.

Tentativa 1 (falhou): `fetch` com `Accept-Encoding: identity` header. Chrome **ignora** silenciosamente — é "forbidden header name" no spec WHATWG. Request continuou indo com `accept-encoding: gzip, deflate, br, zstd` mesmo após meu override.

**Fix correto:** Route handler local `dashboard/src/app/api/sse/dashboard/route.ts` que server-side faz fetch ao backend com `Accept-Encoding: identity` (server-side fetch NÃO tem essa restrição) e devolve a resposta com:
- `Cache-Control: no-cache, no-store, no-transform` (no-transform = CDN não comprime)
- `Content-Encoding: identity` (declara explicitamente uncompressed)
- `X-Accel-Buffering: no` (anti-buffer em proxies)

CF respeita `no-transform` e não re-comprime no edge. Cliente conecta na rota local com `EventSource` normal. Commits `c0f4abb` (errado, fetch client-side), `22f9a70` (correto, route proxy).

**Lição:**
- `Accept-Encoding`, `Content-Length`, etc. são forbidden header names — fetch client-side não pode setar.
- CF Auto-compress trata `text/event-stream` como qualquer text e quebra streaming.
- `Cache-Control: no-transform` é a forma canônica de dizer "nenhum proxy modifica isso".
- Sempre testar SSE via curl externo (passa por CDN) e não só localhost.

## 2026-05-17 — Banca: backend endpoints inexistentes

**Sintoma:** Click em "Iniciar Banca" em `/banca` retornava `{"detail":"Not Found"}` (HTTP 404). Frontend chamava 5 endpoints (`/api/banca`, `/api/banca/setup`, `/api/banca/movements`, `/api/banca/series`, `/api/banca/reset`).

**Causa raiz:** Backend nunca implementou nenhum endpoint `/banca/*`. Frontend `dashboard/src/lib/api.ts` foi escrito antecipando o contrato.

**Fix:** Migration `0011_banca.sql` (tabelas `banca` 1:1 user + `banca_movements` 1:N), `data/repositories/banca.py` (BancaRepo), 6 endpoints no `api_server.py`. Commits `feat(banca): migration 0011 + BancaRepo` + `feat(api): endpoints /api/banca/*`.

**Lição:** Frontend e backend evoluíram desincronizados. Próxima vez: contrato via OpenAPI gerado, ou pelo menos um issue com checklist amarrando os 2 lados antes de mergear lib/api.ts.
