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
