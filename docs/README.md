# CPES Documentation

> Corner Pressure Elite System — Indice de Documentacao

---

## Architecture

Especificacoes tecnicas completas do sistema.

| Documento | Descricao |
|-----------|-----------|
| [**Sistema Completo**](architecture/sistema-completo.md) | Documentacao completa e atualizada: stack, infra, engines, filtros, formulas, dashboard, WhatsApp, banco, backtest, parametros |
| [Full Spec V2 — WAHA](architecture/full-spec-v2-waha.md) | Especificacao tecnica completa com integracao WhatsApp/WAHA |
| [Full Spec V1](architecture/full-spec-v1.md) | Especificacao tecnica original (pre-WAHA) |
| [Upcoming Games Polling](architecture/upcoming-games-polling.md) | Sistema inteligente de polling adaptativo para proximos jogos |

## Analises

Analises de componentes, modelos de decisao, estudos, debugging do sistema.

| Documento | Descricao |
|-----------|-----------|
| [📍 Resumo Executivo - Debug](analises/resumo-executivo-debug.md) | Leia PRIMEIRO: diagnóstico em 2 min, bugs identificados, cronograma de 30min para fix |
| [DEBUG CRÍTICO - Agenda Apenas Argentina](analises/debug-agenda-argentina.md) | Análise profunda: 5 bugs identificados, 3 problemas arquiteturais, timeline completa, testes propostos, correções |
| [Checklist DEBUG Rápido](analises/checklist-debug-agranda.md) | Quick diagnosis em 5 min, testes imediatos, correções prioritizadas, checklist de produção |
| [Testes Manuais - Agenda](analises/testes-manuais-agenda.md) | 7 testes passo a passo runáveis agora, matriz de diagnóstico, interpretar resultados |
| [Sistema - Funcionamento Completo](analises/sistema-funcionamento-completo.md) | Documentacao completa: visao geral, arquitetura, componentes, fluxos, executacao, persistencia e troubleshooting |
| [Analise Completa do Sistema](analises/analise-completa-sistema.md) | Analise tecnica e funcional completa: arquitetura, fluxos, componentes, limitacoes |
| [Analise de Cobertura de Requisicoes](analises/analise-cobertura-requisicoes.md) | Analise de cobertura de requisicoes API-Football e consumo diario |
| [Calculo de Requisicoes por Jogo](analises/calculo-requisicoes-per-jogo.md) | Calculo detalhado de requisicoes por jogo na janela |
| [Executive Analysis](analises/executive-analysis.md) | Visao geral do sistema, arquitetura, componentes |
| [Decision Model](analises/decision-model.md) | Pressure Score, projecao hibrida, calculo de edge |
| [**Auditoria Completa 2026-02-15**](analises/2026-02-15-auditoria-completa.md) | Auditoria de 8 fases: BUG CRITICO encontrado (0 sinais gerados), fix aplicado, analise de estrategia, avaliacao de linhas, gargalos, recomendacoes |

## Resumo

Resumos executivos, relatorios de performance, snapshots do sistema.

| Documento | Descricao |
|-----------|-----------|
| [WAHA Session Fix — 2-Min Summary](resumo/2026-02-15-waha-session-fix-summary.md) | ✅ Leia isto PRIMEIRO. Problema: webhook retornava ok mas WhatsApp não recebia. Root cause: session era fechada após cada call. Solução: gerenciador persistente. Validação: 5min. |

## Sprints

Planejamento de evolucao, roadmap, tarefas futuras.

| Documento | Descricao |
|-----------|-----------|
| [**Next Steps: Production Validation**](sprints/2026-02-15-next-steps.md) | ⏭️ LEIA ISTO AGORA: Checklist do que fazer para validar e rodar em produção (testes WhatsApp, dashboard, troubleshooting) |
| [Sprints de Melhoria](sprints/SPRINTS.md) | Roadmap: odds ao vivo, resultado automatico, backtest, mais ligas, dashboard avancado |

## Setup & Deploy

Como rodar, fazer deploy e configurar o sistema.

| Documento | Descricao |
|-----------|-----------|
| [**Validation Testing Guide**](setup/validation-testing.md) | ✅ 5-min checklist para validar webhook WhatsApp funcionando, testes sequenciais, checklist pré-produção, regression testing |
| [Docker Setup](setup/docker-setup.md) | Docker Compose, scripts shell, variaveis de ambiente |
| [Cloudflare Setup](setup/cloudflare-setup.md) | Deploy no Cloudflare Workers para odontoschultz.online |
| [Dashboard](setup/dashboard.md) | Portas do dashboard, proxy config, endpoints da API |
| [Dashboard Deploy](setup/dashboard-deploy.md) | Guia de deploy do Dashboard em localhost e Cloudflare |
| [Dashboard Quick Start](setup/dashboard-quick-start.md) | Quick start do Dashboard v2 |
| [WAHA Plus - API Key](setup/waha-plus-api-key.md) | Como gerar nova API Key para WAHA Plus |
| [WAHA - API Key web_dev](setup/waha-api-key-web-dev.md) | Criar API Key "web_dev" para localhost:3000 |

## Changelog

Registros de mudancas significativas no sistema.

| Documento | Descricao |
|-----------|-----------|
| [2026-02-15 Fix: WAHA Session STOPPED - Webhook Não Respondia](changelog/2026-02-15-fix-waha-session-stopped.md) | 🔴 CRÍTICA: Webhook recebia ok mas WhatsApp não recebia resposta. Root cause: cliente WebappClient era criado/destruído a cada requisição, deixando session em STOPPED. Solução: gerenciador persistente de sessão com reutilização de cliente. |
| [2026-02-15 Files Changed Summary](changelog/2026-02-15-files-changed.md) | Referência completa: quais arquivos foram modificados/criados (notifier/waha_manager.py, api_server.py, docs, scripts) |
| [2026-02-15 Fix: WhatsApp Webhook e Comandos /status /jogos](changelog/2026-02-15-fix-whatsapp-webhook.md) | ✅ Resolvido: Comandos /status /jogos não respondiam. Causas: session name "cpes-alerts" incompatível com WAHA Core, API key descasada, webhook não registrado. Solução: mudar para session "default", sincronizar keys, registrar webhook em docker-compose. |
| [2026-02-15 Fix Crítico: Agenda Retornava 0 Ligas](changelog/2026-02-15-fix-agenda-retornava-zero-ligas.md) | 🔴 CRÍTICA: Sistema retornava apenas 2 jogos da Argentina (bug: season 2026 aplicado globalmente). Solução: adicionar config season por liga, usar season_map dinâmico. Resultado: 0 → 13 jogos. |
| [2026-02-15 Strategy Tuning](changelog/2026-02-15-strategy-tuning.md) | Reducao dos limiares de decisao para capturar mais sinais |

---

## Adicionando novos documentos

Consulte o [CLAUDE.md](../CLAUDE.md) para regras de posicionamento de documentos.
Toda documentacao gerada por AI deve seguir a estrutura de categorias abaixo.

| Categoria | Pasta | O que vai aqui |
|-----------|-------|----------------|
| Architecture | `docs/architecture/` | Specs tecnicas completas, codigo-fonte documentado |
| Analises | `docs/analises/` | Analises de componentes, modelos de decisao, estudos, avaliacoes |
| Resumo | `docs/resumo/` | Resumos executivos, relatorios de performance, snapshots |
| Sprints | `docs/sprints/` | Planejamento, roadmap, tarefas futuras, evolucao do sistema |
| Setup | `docs/setup/` | Guias de deploy, config de ambiente, infra, como rodar |
| Changelog | `docs/changelog/` | Registros de mudancas. Nomear como `YYYY-MM-DD-slug.md` |

**Convencao de nomes:** kebab-case em minusculo (ex: `decision-model.md`, nao `DecisionModel.md`)
