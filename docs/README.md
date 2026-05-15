# PressureIQ / CPES — Documentação

> Bem-vindo. Este índice cobre toda a documentação do **Corner Pressure Elite System**
> (interno) / **PressureIQ** (público). Sempre que adicionar um doc novo, linke aqui.

---

## 🧭 Comece por aqui (sempre atualizado)

- **[Estado Real do Sistema (2026-05-10)](analises/2026-05-10-estado-real-do-sistema.md)** —
  auditoria completa do que existe e funciona hoje. **Leia primeiro.**
- **[Plano Mestre de Produto](PRODUCT_MASTER_PLAN.md)** — visão executiva, marketing e arquitetura.
- **[/CLAUDE.md](../CLAUDE.md)** — instruções para qualquer agente AI mexendo no repo.

---

## 📋 Meta-docs ativos (ler todo início de sessão)

| Doc | Quando ler | Quando atualizar |
|---|---|---|
| [CHANGELOG.md](CHANGELOG.md) | Início de sessão (última entrada) | Antes de fechar sessão |
| [ROADMAP.md](ROADMAP.md) | Início de sessão (estado atual) | Quando fase fecha ou nova é planejada |
| [DECISIONS.md](DECISIONS.md) | Quando questionar uma escolha arquitetural | Após decisão arquitetural significativa |
| [BUGS.md](BUGS.md) | Quando bug parecido aparecer | Após corrigir bug |
| [OPERATIONS.md](OPERATIONS.md) | Quando algo quebra (recovery, deploy) | Quando descobrir nova procedure |

Regras completas em [/CLAUDE.md §12](../CLAUDE.md).

---

## 🚀 Começando

| Doc | Descrição |
|---|---|
| [manuals/DEPLOYMENT.md](manuals/DEPLOYMENT.md) | Guia de instalação e deploy |
| [manuals/USER_GUIDE.md](manuals/USER_GUIDE.md) | Guia do usuário do dashboard |
| [setup/docker-setup.md](setup/docker-setup.md) | Subir ambiente via Docker Compose |
| [setup/cloudflare-setup.md](setup/cloudflare-setup.md) | DNS, Tunnel e SSL |

---

## 🏗 Arquitetura

| Doc | Descrição |
|---|---|
| [architecture/full-spec-v2-waha.md](architecture/full-spec-v2-waha.md) | Especificação técnica original (WAHA + engine) |
| [architecture/sistema-completo.md](architecture/sistema-completo.md) | **Referência canônica ponta-a-ponta** — call chains, schema, odds pipeline, plano Betano scraping (atualizado 2026-05-12) |
| [architecture/upcoming-games-polling.md](architecture/upcoming-games-polling.md) | Polling adaptativo |
| [architecture/waha-webhook-architecture.md](architecture/waha-webhook-architecture.md) | Webhook PUSH do WAHA Plus |
| [api/ENDPOINTS.md](api/ENDPOINTS.md) | Referência da API REST |

---

## 🔬 Análises e estudos

| Doc | Descrição |
|---|---|
| **[2026-05-10-estado-real-do-sistema.md](analises/2026-05-10-estado-real-do-sistema.md)** | Auditoria completa atual |
| [analises/decision-model.md](analises/decision-model.md) | Modelo de decisão (escanteios) |
| [analises/sistema-funcionamento-completo.md](analises/sistema-funcionamento-completo.md) | (legado: cita SQLite) |
| [analises/analise-completa-sistema.md](analises/analise-completa-sistema.md) | Estudo inicial |
| [analises/2026-02-15-auditoria-completa.md](analises/2026-02-15-auditoria-completa.md) | Auditoria de fevereiro |
| [analises/calculo-requisicoes-per-jogo.md](analises/calculo-requisicoes-per-jogo.md) | Custo de API por jogo |
| [analises/analise-cobertura-requisicoes.md](analises/analise-cobertura-requisicoes.md) | Capacidade por liga |
| [analises/executive-analysis.md](analises/executive-analysis.md) | Visão executiva |
| [analises/debug-agenda-argentina.md](analises/debug-agenda-argentina.md) | Bug seasons + agenda |
| [analises/checklist-debug-agranda.md](analises/checklist-debug-agranda.md) | Checklist de debug agenda |
| [analises/testes-manuais-agenda.md](analises/testes-manuais-agenda.md) | Roteiros manuais |
| [analises/resumo-executivo-debug.md](analises/resumo-executivo-debug.md) | Resumo dos bugs investigados |

---

## 📋 Sprints e roadmap

| Doc | Descrição |
|---|---|
| [sprints/SPRINTS.md](sprints/SPRINTS.md) | Roadmap geral |
| [sprints/2026-02-15-next-steps.md](sprints/2026-02-15-next-steps.md) | Próximos passos pós-fevereiro |
| [sprints/2026-05-11-bugs-fluxo-compra.md](sprints/2026-05-11-bugs-fluxo-compra.md) | Bugs pendentes do fluxo de compra Asaas (7 itens com prioridade) |
| [sprints/2026-05-11-roadmap-7-features.md](sprints/2026-05-11-roadmap-7-features.md) | Roadmap de 7 features UX/produto com harness completo |
| [sprints/2026-05-11-robo-auto-roadmap.md](sprints/2026-05-11-robo-auto-roadmap.md) | **Mestre** — Robô Auto-Aposta (visão, decisões, índice das 4 fases) |
| [sprints/2026-05-11-robo-fase-1-plumbing.md](sprints/2026-05-11-robo-fase-1-plumbing.md) | Robô Fase 1 — Plumbing (schema, adapter contract, cifragem, UI esqueleto) |
| [sprints/2026-05-11-robo-fase-2-paper-trading.md](sprints/2026-05-11-robo-fase-2-paper-trading.md) | Robô Fase 2 — Paper Trading (orchestrator simulando apostas) |
| [sprints/2026-05-11-robo-fase-3-execucao-real.md](sprints/2026-05-11-robo-fase-3-execucao-real.md) | Robô Fase 3 — Execução Real (Betano/Bet365/KTO adapters, cashout, sanity) |
| [sprints/2026-05-11-robo-fase-4-bankroll-ml.md](sprints/2026-05-11-robo-fase-4-bankroll-ml.md) | Robô Fase 4 — Bankroll, Cashout matemático, ML de qualidade |
| [sprints/2026-05-11-robo-ux-dashboard.md](sprints/2026-05-11-robo-ux-dashboard.md) | Robô UX — gate MAX-only, sidebar, wizard de setup, telas, animações, a11y |
| [sprints/2026-05-11-migracao-dominio-iqpressure.md](sprints/2026-05-11-migracao-dominio-iqpressure.md) | Harness passo a passo da migração `odontoschultz.online` → `iqpressure.online` (Hostinger, Cloudflare Tunnel, Resend, Asaas, CORS) |
| [sprints/2026-05-12-landing-page-apex.md](sprints/2026-05-12-landing-page-apex.md) | Landing page pública no apex `iqpressure.online/` (hero, features, pricing, CTA). Middleware host-aware pra `membros.*` redirecionar pro login. |

---

## 📜 Changelog

| Data | Mudança |
|---|---|
| [2026-05-13-fase-d-persistencia-completa.md](changelog/2026-05-13-fase-d-persistencia-completa.md) | Pivot Betano: Fase D completa — 3 repositories, 3 workers async (odds/incidents/cleanup), hooks no Composite e WS, healthcheck + queries SQL + 16 tests verdes |
| [2026-05-13-fase-c-pipeline-refactor.md](changelog/2026-05-13-fase-c-pipeline-refactor.md) | Pivot Betano: Fase C — `Composite{Odds,Stats}Provider`, adapters AF+Betano, factory feature-flagged, drift logger + 20 tests verdes (`main.py` adiado) |
| [2026-05-13-fase-b-betano-markets-ws.md](changelog/2026-05-13-fase-b-betano-markets-ws.md) | Pivot Betano: Fase B — `BetanoMarkets` (CNOU/TCOU), `BetanoCatalog` com fuzzy match, `BetanoWSClient` (SignalR Core), warmup Playwright + 21 unit tests verdes |
| [2026-05-13-fase-a-betano-statsstream.md](changelog/2026-05-13-fase-a-betano-statsstream.md) | Pivot Betano: Fase A — `BetanoStatsStream` (7 endpoints Opta-backed), schemas tipados, parsers + 16 unit tests verdes, 17 fixtures extraídas do `.mitm` |
| [2026-05-13-fase-d-migrations.md](changelog/2026-05-13-fase-d-migrations.md) | Pivot Betano: aplicadas as 3 migrations da Fase D (`betano_fixture_map`, `odds_history`, `incidents_history`) + loader idempotente em `Database.init()` |
| [2026-05-11-migracao-dominio-iqpressure.md](changelog/2026-05-11-migracao-dominio-iqpressure.md) | Migração de domínio público: `odontoschultz.online` → `iqpressure.online` (apex agora serve dashboard; WAHA em `wa.`) |
| [2026-05-11-fluxo-compra-pre-golive.md](changelog/2026-05-11-fluxo-compra-pre-golive.md) | Fluxo de compra: refund, dedup de webhooks, checkout idempotente, UX pós-verify |
| [2026-05-10-adapter-permission-policy-claude-local.md](changelog/2026-05-10-adapter-permission-policy-claude-local.md) | Política de permissão migrou do adapter para o harness (PREA-22/23) |
| [2026-05-10-waha-healthcheck-periodico.md](changelog/2026-05-10-waha-healthcheck-periodico.md) | Healthcheck WAHA periódico + alerta admin |
| [2026-02-15-strategy-tuning.md](changelog/2026-02-15-strategy-tuning.md) | Tuning de thresholds |
| [2026-02-15-fix-waha-session-stopped.md](changelog/2026-02-15-fix-waha-session-stopped.md) | Fix Session STOPPED (singleton) |
| [2026-02-15-fix-whatsapp-webhook.md](changelog/2026-02-15-fix-whatsapp-webhook.md) | Fix registro de webhook PUT |
| [2026-02-15-fix-agenda-retornava-zero-ligas.md](changelog/2026-02-15-fix-agenda-retornava-zero-ligas.md) | Fix seasons por liga |
| [2026-02-15-files-changed.md](changelog/2026-02-15-files-changed.md) | Arquivos alterados na release |

---

## 🛠 Setup específico

| Doc | Descrição |
|---|---|
| [setup/dashboard.md](setup/dashboard.md) | Dashboard (Next.js) |
| [setup/dashboard-deploy.md](setup/dashboard-deploy.md) | Deploy do dashboard |
| [setup/dashboard-quick-start.md](setup/dashboard-quick-start.md) | Quick start |
| [setup/GERAR-WAHA-API-KEY.md](setup/GERAR-WAHA-API-KEY.md) | Gerar API key WAHA |
| [setup/waha-api-key-web-dev.md](setup/waha-api-key-web-dev.md) | API key via WAHA Web |
| [setup/waha-plus-api-key.md](setup/waha-plus-api-key.md) | API key WAHA Plus |
| [setup/whatsapp-testing-guide.md](setup/whatsapp-testing-guide.md) | Testes WhatsApp |
| [setup/validation-testing.md](setup/validation-testing.md) | Validação ponta a ponta |

---

## 📂 Estrutura de pastas

- `/corner-pressure-elite/` — Backend Python (FastAPI + robô)
- `/dashboard/` — Frontend Next.js
- `/docs/` — Documentação (você está aqui)
- `/docs/credenciais/` — **Não commitar** (segredos)
- `/docs/legacy/` — Eventualmente: snapshots antigos consolidados

## 🔄 Status do Sistema

5 containers Docker (Postgres é compartilhado):

1. **waha** — Gateway WhatsApp Plus (porta 3000)
2. **cpes-api** — FastAPI (porta 8000)
3. **cpes-dashboard** — Next.js (porta 3001)
4. **cpes-main** — Robô de análise (sem porta)
5. **cpes-postgres** — PostgreSQL 15 (interno)

---

*Última atualização: 2026-05-10.*
