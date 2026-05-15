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
