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
