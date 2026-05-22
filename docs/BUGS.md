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

## 2026-05-20 — Fase H A1: dual-write `sofa_event_id` em 0% nos registros bridge_betano (o provider primário)

**Sintoma:** Validação do A1 (pause 3-7 dias) parecia parada. Fill de `sofa_event_id` agregado ~2-10% nas 6 tabelas shadow. Por source: `sofascore` = 100% (22/22 stats, 86/86 events), `bridge_betano` = **0%** (0/208 stats, 0/4561 events). Como bridge_betano é o PRIMÁRIO da cascata K.1 (~90% do volume), o agregado afundava. `af_sofa_fixture_map` só tinha 1 entrada `provider_native` viva desde 05-18 (resto era backfill one-shot de 05-17).

**Causa raiz:** Os 3 workers do bridge (`betano_stats_worker`, `betano_events_worker`, `betano_lineups_worker`), quando o snapshot vinha sem `sofa_event_id` (sempre, no caso do bridge), faziam **só** `af_sofa_map.get_sofa_id(fixture_id)` — lookup no banco. Como `af_sofa_fixture_map` só era populada por upsert oportunístico quando um snapshot SofaScore passava, fixtures que só capturavam via bridge (ex: Arsenal, Chelsea, Torreense) **nunca** entravam no mapa → `sofa_event_id` NULL pra sempre (chicken-and-egg). O passo de fallback pro **resolver live** — descrito no próprio docstring de `af_sofa_map.py` (linhas 6-13) — nunca foi implementado nos workers.

Sub-bug encontrado junto: `FixtureMapRepo` não tinha `get_by_fixture_id`, mas `SofaScoreEventResolver._resolve_names` chamava exatamente esse método → caía sempre no `except` e perdia os names canônicos do `betano_fixture_map` (degradava o match, mas o SofaScore path mascarava porque já passava names no CanonicalFixture).

**Fix:**
1. `FixtureMapRepo.get_by_fixture_id()` — retorna row completa (home/away/league/kickoff). Conserta o resolver E habilita resolução por fixture_id.
2. `SofaScoreEventResolver.resolve_by_fixture_id()` — puxa names+kickoff do `betano_fixture_map` e faz o mesmo fuzzy match em `/events/live`. Reusa o cache de `resolve()`.
3. `AfSofaFixtureMapRepo.get_or_resolve(fixture_id, resolver=...)` — lookup → se NULL, cai pro resolver live → upsert `mapped_via='realtime_live'`.
4. 3 workers passam a injetar `event_resolver` e usar `get_or_resolve`.
5. `main.py` passa `event_resolver=self.sofa_event_resolver` aos 3 workers.

**Validação:** Testado ao vivo — Torreense vs Casa Pia (Liga Portugal, ao vivo) resolveu pra sofa `16197899` e persistiu `realtime_live`. 120 testes dos módulos tocados passam. Pós-deploy, fill esperado deve saltar pra ~90%+ nos fixtures live no SofaScore.

**Lição:**
- Dual-write/shadow-key precisa cobrir **todos os write-paths**, não só o do provider que "naturalmente" conhece a chave. O primário (bridge) era justamente o que não conhecia → tinha que ter o fallback de resolução desde o A1.3.
- Quando um docstring descreve o uso correto (`get_sofa_id` → `live_resolver` → `upsert`), confira se TODOS os call-sites seguem — aqui o passo do meio foi omitido em 3 lugares.
- Validar feature de propagação exige **fill rate por source**, não só agregado. O agregado escondia o split 100%/0%.

**Commits:** edits `data/repositories/fixture_map.py`, `data/repositories/af_sofa_map.py`, `data/providers/sofascore/event_resolver.py`, `workers/betano_{stats,events,lineups}_worker.py`, `main.py`.

---

## 2026-05-20 — Pré-existente: `get_fixture_result_cards` não existe no APIFootballClient (cards nunca apuram resultado)

**Sintoma:** No boot do `cpes-main`, loop de verificação de resultados logava `ERROR Erro ao verificar resultados: 'APIFootballClient' object has no attribute 'get_fixture_result_cards'` (main.py:1682).

**Causa raiz:** `main.py::_verificar_resultados` chama `self.api_client.get_fixture_result_cards(jogo_id)` mas `data/api_client.py` só tem `get_fixture_result` (corners/placar). Bug commitado (HEAD), não é da Fase H — exposto ao olhar os logs durante o deploy do A1. Significa que sinais de **cartões nunca são marcados GREEN/RED** → settle de apostas de cartões (Sprint M.2) também não dispara pra esse tipo.

**Fix:** PENDENTE — precisa decidir se `get_fixture_result` serve pra cartões (basta extrair total de amarelos do FT) ou se precisa fetch dedicado. Não corrigido nesta sessão (fora do escopo A1; toca o path de settle/banca, exige cuidado).

**Lição:** Erro estava sendo engolido pelo `try/except` do loop e ninguém via — só apareceu por inspeção ativa dos logs no deploy. Vale um alerta WAHA/Netdata pra ERROR recorrente no resolver de resultados.

---

## 2026-05-19 — Sprint M.2: settle nunca rodava → decisions ficavam eternamente em "EM ANDAMENTO" + banca sem credit

**Sintoma:** User registrou aposta (decision 121: signal 138 Bournemouth, R$40 @4.05). Jogo terminou — `sinais.resultado=GREEN`, `escanteios_final=13` ✅. Porém: `user_signal_decisions.resultado=NULL`, `payout_cents=NULL`, `settled_at=NULL`. UI mostrava ResultPill "GREEN" (fallback pra `signal_resultado`) mas card ficava na aba "EM ANDAMENTO" (tabOf usa só `decision.resultado`). Banca não recebia o payout. Stats: 0G/0R, ROI 0%.

**Causa raiz:** `main.py::_verificar_resultados` (linha 1572) chamava `database.atualizar_resultado(jogo_id, resultado, ...)` que atualiza `sinais` mas NUNCA tocava `user_signal_decisions` nem `banca_movements`. CLAUDE.md §13.14 já listava como pendência pós-Sprint M. Resultado: cada GREEN/RED do sistema deixava as decisions dos users penduradas; só seriam "fechadas" via UPSERT no decide() (nunca aconteceria pra entered).

Agravante: mesmo se houvesse wire, single bets do CPES batem com sinal automaticamente, mas multi bets (mercados que CPES não conhece — gols, 1X2, marcador exato) não dão pra auto-settle. Tinha que ter caminho manual.

**Fix:**
1. `_propagar_settle_decisions(jogo_id, tipo_analise, resultado)` novo em `main.py`: query signal_ids resolvidos do jogo+tipo, itera, chama `UserSignalDecisionsRepo.settle_auto()` (SO single bets) + `BancaRepo.credit_payout()` (idempotente por decision_id).
2. `settle_auto(signal_id, resultado)` filtra `requires_manual_confirmation = FALSE` — multi nao toca.
3. `confirm_manual_result(decision_id, resultado)` + endpoint `POST /api/signals/{id}/decision/confirm` pra multi (e override em single se CPES errou).
4. `credit_payout` cria `bet_win +(stake + payout_cents)` em GREEN (estorna stake reservation + adiciona lucro líquido com bonus). RED: no-op (bet_loss já contou). PUSH/VOID: `bet_void +stake` (só estorna).
5. Migration `0015_user_signal_decisions_multi_bonus.sql`: bonus_pct, is_multi, requires_manual_confirmation + tabela user_decision_legs.

**Lição:**
- Cada nova feature Sprint M (decisions, banca) ficou silently broken porque o resolver de resultado é em `main.py` (worker) e não chamava o repo novo. **Wire end-to-end deveria ser validado por smoke test antes de merge** — não tinha teste cobrindo "signal vira GREEN → decision atualiza".
- Convenção `bet_loss otimista → bet_win pós-resolução` só fecha quando ambos rodam. Sem o segundo lado, banca fica permanentemente debitada em GREEN. Sempre escrever os dois caminhos juntos (ou usar pattern de "reserva temporária" com timeout).
- Multi vs Single auto-settle: o sistema só conhece os mercados que ele opera (escanteios, cartões). Tudo fora disso requer confirm manual — não dá pra inferir.

**Commits:** migration 0015 + edits `main.py:1656,1700`, `data/repositories/user_signal_decisions.py` (reescrito), `data/repositories/banca.py` (`credit_payout`), `api_server.py:2230+` (endpoints novos), `dashboard/src/components/minhas-apostas/MinhasApostasPanel.tsx` (reescrito layout Betano).

---

## 2026-05-19 — Sprint M: FK errada em banca_movements.bet_id quebrava registro de entrada

**Sintoma:** Modal "Registrar Entrada" no dashboard retornava `500 Internal Server Error` ao confirmar (signal #138, Bournemouth vs Manchester City). Decision row era criada (`user_signal_decisions.id=121` com `entered, 4.05, R$40`) mas banca_atual nunca debitava.

**Causa raiz:** Migration `0011_banca.sql` declarou `bet_id BIGINT` sem FK explícita (comentário: "FK opcional p/ user_signal_decisions.id (0012)"), mas uma versão anterior do schema legado tinha criado `banca_movements_bet_id_fkey` apontando pra `bets(id)` — tabela do robô auto-aposta. Quando Sprint M passa `result["id"]` (que é `user_signal_decisions.id`) como `bet_id`, FK viola: `ForeignKeyViolationError`. Endpoint `/api/signals/{id}/decision` captura só `(LookupError, ValueError)` — `asyncpg.exceptions.ForeignKeyViolationError` borbulha como 500.

Agravante secundário: re-POST da mesma decision criava bet_loss duplicado (UPSERT na decision é idempotente, mas `add_movement` sempre INSERT-a) — debit duplo da banca em retry.

**Fix:**
1. Migration `0014_fix_banca_movements_bet_fk.sql`: `DROP CONSTRAINT banca_movements_bet_id_fkey` + `UPDATE ... bet_id=NULL WHERE bet_id NOT IN (SELECT id FROM user_signal_decisions)` (limpa órfãos) + `ADD FOREIGN KEY ... REFERENCES user_signal_decisions(id) ON DELETE SET NULL`
2. `api_server.py::api_signal_decide`: antes de `add_movement`, query `SELECT 1 FROM banca_movements WHERE bet_id=$1 AND tipo='bet_loss'` — pula INSERT se já existe (idempotência)

**Lição:**
- Migrations que só declaram colunas sem checar/recriar FKs herdadas podem causar "FK ghosts" — sempre fazer `DROP CONSTRAINT IF EXISTS` antes de `ADD CONSTRAINT` em refactors de schema.
- Endpoints que orquestram 2 mutations (decision + banca movement) em conexões separadas precisam ser **explicitamente idempotentes** ou unificadas em uma transação. Hoje estão em conexões distintas — fica como dívida.
- Try/except deve catchar `asyncpg.exceptions.*` ao tocar em FK, ou propagar como 4xx legível.

**Pendência relacionada (não fix aqui):** `UserSignalDecisionsRepo.settle()` ainda não cria `bet_win` movement quando signal vira GREEN — banca permanece debitada mesmo em wins (CLAUDE.md §13.14 já lista como aberto).

**Commits:** migration 0014 + edit em `api_server.py:2257-2280`.

---

## 2026-05-18 — Dual-write Fase H A1.3 perdia sofa_event_id de SofaScore

**Sintoma:** Netdata custom collector `cpes_metrics.dual_write` mostrou cobertura de `sofa_event_id` por fonte muito abaixo do esperado:
- `sofascore` em `stats_history`: **54.8%** (esperado ~100%)
- `sofascore` em `events_history`: **53.2%** (esperado ~100%)
- `bridge_betano` em 3 tabelas: 63-70% (esperado >85% via mapping)

**Causa raiz:** Os 3 adapters SofaScore (`events_adapter.py:172`, `stats_adapter.py:140`, `lineups_adapter.py:143`) resolviam `sofa_event_id` em runtime pra fazer a chamada à API, mas **descartavam** ele no `return CanonicalEvent/Stats/Lineup(...)` — os dataclasses não tinham o campo. Workers então caíam em `af_sofa_map.get_sofa_id(fixture_id)` como ÚNICA fonte, que só conhece via `af_sofa_fixture_map` table (cobertura parcial — limitada pelo `betano_team_map` de 29% por §13.6 do CLAUDE.md). Resultado: ~45% das capturas SofaScore persistiam sem chave de join apesar do provider ter ACABADO de resolver o ID.

**Fix:**
1. `CanonicalEvent/Stats/Lineup` ganharam `sofa_event_id: Optional[int] = None`
2. Os 3 SofaScore adapters populam no return
3. Os 3 workers (`betano_events/stats/lineups_worker.py`) preferem `entity.sofa_event_id` sobre lookup, com **opportunistic upsert** em `af_sofa_fixture_map` (`mapped_via="provider_native"`) — 1 hit SofaScore alimenta a map pra futuras capturas de bridge/AF do mesmo fixture
4. Backward-compat preservada (worker com `af_sofa_map=None` segue caminho legado)

Commit `aeff17a`. Tests: 104/104 passam.

**Lição:**
- Quando um adapter resolve um ID externamente pra fazer uma chamada API, esse ID é DADO valioso — propagar até a persistência por padrão, não tratar como detalhe interno
- Dual-write coverage só é avaliável com observabilidade granular por fonte (que essa sessão acabou de instalar via Netdata) — sem chart `cpes_metrics.sources_*` o bug ficaria escondido até A2 cutover
- Opportunistic upsert (escrita em cache de mapeamento quando provider RESOLVE) é padrão útil — converte uma resolução pontual em melhoria sistêmica de cobertura

---

## 2026-05-18 — Alerta `cpes_af_odds_usage_high` semanticamente errado (agregado 24h)

**Sintoma:** Logo após instalar Netdata, alerta `cpes_af_odds_usage_high` disparou CRITICAL (473 reqs AF). Confuso porque P4-B (`REMOVE_AF_FROM_ODDS_RUNTIME=true`) está ativo desde ~18:15 UTC de 17/05.

**Causa raiz:** O collector `cpes_metrics` agrega `COUNT(*) FROM odds_history WHERE source='apifootball' AND captured_at > NOW() - INTERVAL '24 hours'`. O alerta `lookup average -10m of odds` lê esse valor mas o NÚMERO em si é uma janela de 24h. Resultado: alerta dispara mesmo quando AF caiu pra zero hoje — porque os 473 reqs das 3h antes do cutover ainda estão na janela de 24h.

**Fix proposto** (não aplicado nesta sessão): refactor collector pra exportar:
- `af_odds_1h`: capturas última 1h (esperado: 0 pós-P4-B)
- `af_odds_24h`: capturas 24h (chart histórico, sem alerta)
- Alerta usa `af_odds_1h` em vez de `odds` (que vira `af_odds_24h`)

Workaround atual: ignorar CRITICAL desse alerta nas primeiras 24h pós-deploy de qualquer mudança em fluxo AF. Vai limpar sozinho passando 18:15 UTC + 24h.

**Lição:**
- Alertas precisam medir **janelas curtas** (1h, 5m), não agregados longos (24h). Agregados servem pra TENDÊNCIA (histórico), não pra DECISÃO (warn/crit ON/OFF)
- Quando criar métricas pra Netdata, separar `metric_24h` (chart bonito, sem alarme) de `metric_1h` (chart com alarme rápido) — naming explícito da janela evita confusão

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
