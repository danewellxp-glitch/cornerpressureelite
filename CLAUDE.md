# CLAUDE.md — Instruções do Projeto para AI

> Este arquivo é a fonte da verdade para qualquer agente trabalhando neste repositório.
> Leia inteiro antes de editar. Nada fora dele substitui o que está aqui.

---

## 1. Identidade do Projeto

- **Nome técnico:** Corner Pressure Elite System (**CPES**)
- **Marca pública:** **PressureIQ** — usar em docs voltadas ao usuário final.
- **O que faz:** monitora futebol ao vivo via API-Football, calcula um *Pressure Score* / *Tension Score* e dispara sinais de Over Escanteios e Over Cartões Amarelos no WhatsApp via WAHA.
- **Stack atual (verificada no código):**
  - Backend Python 3.12 + FastAPI (`corner-pressure-elite/`)
  - Robô de monitoramento Python (`corner-pressure-elite/main.py`) — processo separado, não é container só dele
  - Frontend Next.js 16 + React 19 + MUI 7 + Recharts (`dashboard/`)
  - Banco: **PostgreSQL 15** (asyncpg) — *não é mais SQLite*
  - WhatsApp: **WAHA Plus** (webhook PUSH)
  - Pagamentos: **Asaas** (PIX/cartão), e-mail transacional via Resend
  - Infra: Docker Compose, Cloudflare Tunnel, Next.js no Cloudflare (OpenNext)

---

## 2. Topologia (estado real)

| Container | Imagem / Comando | Porta host | Função |
|---|---|---|---|
| `waha` | `devlikeapro/waha-plus:latest` | 3000 | Gateway WhatsApp HTTP |
| `cpes-api` | `python -m uvicorn api_server:app` | 8000 | API REST + auth + webhooks |
| `cpes-dashboard` | `next start -p 3001` | 3001 | Frontend Next.js |
| `cpes-main` | `python main.py` | — | Loop de análise (sem porta) |
| `cpes-postgres` | `postgres:15-alpine` | — | Banco compartilhado |

Todos na rede Docker `cpes-network`. Comunicação interna: `waha:3000`, `cpes-api:8000`, `postgres:5432`.

---

## 3. Estrutura do Repositório

```
corner-pressure-elite/             # Backend Python (CPES)
├── api_server.py                  # FastAPI: dashboard, auth, checkout, webhooks
├── main.py                        # Robô principal (loop infinito)
├── config.py                      # Todos os parâmetros tuneáveis
├── data_reader.py                 # Leitor de estado para a API
├── monitor.py                     # Monitor de status (auxiliar)
├── reset_db.py                    # Reseta o Postgres (uso manual)
├── data/
│   ├── api_client.py              # Cliente API-Football v3
│   ├── models.py                  # Dataclasses: JogoAoVivo, Sinal, SinalCartoes, User, Subscription
│   ├── live_state.json            # Snapshot do ciclo (legado, persistência atual é Postgres)
│   └── upcoming_games.json        # Snapshot da agenda
├── engine/                        # Núcleo de análise
│   ├── score_engine.py            # Pressure Score (escanteios)
│   ├── projection_engine.py       # Projeção híbrida de escanteios
│   ├── decision_engine.py         # Filtros + decisão Normal/Premium (escanteios)
│   ├── state_manager.py           # Re-avaliação de sinais (escanteios)
│   ├── cards_score_engine.py      # Tension Score (cartões)
│   ├── cards_projection_engine.py # Projeção de cartões
│   ├── cards_decision_engine.py   # Filtros + decisão (cartões)
│   └── cards_state_manager.py     # Re-avaliação (cartões)
├── notifier/
│   ├── whatsapp_client.py         # Cliente WAHA Plus
│   ├── waha_manager.py            # Singleton de sessão WAHA (evita STOPPED)
│   ├── notification_manager.py    # Orquestra envio (escanteios + cartões + admin)
│   ├── message_formatter.py       # Mensagens de escanteios
│   ├── cards_message_formatter.py # Mensagens de cartões
│   ├── webhook_sender.py          # Helpers de webhook
│   └── asaas_client.py            # Cliente Asaas (cobranças, assinaturas)
├── services/
│   ├── email_service.py           # Resend API (templates HTML)
│   └── email_worker.py            # Fila de eventos para e-mails transacionais
├── templates/                     # HTML de e-mail (welcome, payment, renewal, cancellation)
├── storage/
│   ├── database.py                # asyncpg + schema completo
│   └── logger.py                  # Setup do logging
├── utils/
│   ├── helpers.py                 # parse_fixture_to_jogo, enrich_jogo_with_cards
│   ├── rate_limiter.py            # Rate limit API-Football (450/min, 7500/dia)
│   ├── adaptive_polling.py        # Polling adaptativo por minuto/escanteios
│   └── config_loader.py
├── tests/                         # Pytest
├── backtest/                      # Backtester offline
├── Dockerfile
├── requirements.txt
└── .env                           # Segredos (nunca commitar)

dashboard/                         # Frontend Next.js (PressureIQ)
├── src/
│   ├── middleware.ts              # JWT verification (jose) edge-side
│   ├── app/
│   │   ├── layout.tsx             # Root layout
│   │   ├── page.tsx               # Redirect → /dashboard
│   │   ├── login/page.tsx
│   │   ├── checkout/{success,cancel}/page.tsx
│   │   ├── api/auth/{login,logout}/route.ts  # Cookie auth helpers
│   │   └── (authenticated)/       # Rotas protegidas pelo middleware
│   │       ├── layout.tsx         # Drawer + ThemeProvider (MUI)
│   │       ├── dashboard/page.tsx
│   │       ├── escanteios/page.tsx
│   │       ├── cartoes-amarelos/page.tsx
│   │       ├── settings/page.tsx
│   │       └── logs/page.tsx
│   └── lib/{api.ts,theme.ts,utils.ts}
├── public/
└── package.json                   # Next 16, React 19, MUI 7, Recharts

docs/                              # Documentação (regras na §6)
├── PRODUCT_MASTER_PLAN.md         # Plano de produto/marketing/arquitetura
├── architecture/                  # Specs técnicas
├── analises/                      # Estudos, modelos, auditorias
├── api/ENDPOINTS.md               # Referência da API
├── changelog/YYYY-MM-DD-*.md      # Mudanças datadas
├── manuals/                       # DEPLOYMENT.md, USER_GUIDE.md
├── resumo/                        # Snapshots executivos
├── setup/                         # Guias de ambiente, WAHA, Cloudflare
├── sprints/                       # Roadmap, próximos passos
└── credenciais/                   # ATENÇÃO: contém users.txt — não commitar
```

---

## 4. Pipeline de Análise (passo a passo, código real)

A cada ciclo (`POLLING_INTERVAL = 60s`, ajustado por polling adaptativo):

1. **Agenda** (`api_client.get_today_schedule`) — 1 req/liga, 1×/dia, com season correto (Europa=2025, Brasil/Argentina=2026).
2. **Live fetch** (`api_client.get_live_fixtures`) — chama `fixtures?live=all` global e filtra localmente por liga (workaround de bug da API que não retorna nada com `live=all + multi-league`).
3. **Classificação por fase** (`main.py`):
   - `pre_janela` (< min 50, < 7 escanteios)
   - `na_janela` (≥ min 50 OU 7+ escanteios — *early window*)
   - `pos_janela` (> min 90)
   - Polling adaptativo decide se vale gastar requisição.
4. **Stats** (`get_statistics`) — 1 req por jogo. **Importante:** a API retorna **totais do jogo**, não janelas. `helpers.parse_fixture_to_jogo` *estima* `escanteios_ultimos_5min` e `_10min` a partir do corner rate. Mesma lógica para cartões em `enrich_jogo_with_cards`.
5. **Pré-avaliação** (`decision_engine.pre_avaliar`) — filtros + score, sem buscar odds (economia de 1-2 reqs).
6. **Odds** (`get_live_odds_multi_bookmaker`) — só se passou na pré-avaliação. Tenta Betano (id 46) e Bet365 (id 8); fallback para genérico.
7. **Avaliação completa** (`decision_engine.avaliar`):
   - Filtros estruturais → Pressure Score → Projeção híbrida → Edge → Decisão.
   - Sinal = `(score, edge) ≥ thresholds`.
8. **Análise de Cartões** (paralelo, mesmas stats — 0 req extra): `cards_decision_engine.avaliar`. Odds de cartões só se houver sinal.
9. **Notificação**: `notification_manager.send_signal` → WAHA → grupo configurado.
   - Re-avaliação após 3 min se `Δedge ≥ 0.7` ou `Δscore ≥ 1`.
   - Entrada adicional opcional via `state_manager.deve_sugerir_entrada_adicional`.
10. **Persistência**: `database.salvar_snapshot` (snapshot do ciclo) + `registrar_sinal` (sinal emitido).
11. **Resultado**: 2h depois da última stats, `_verificar_resultados` busca FT/AET/PEN e marca GREEN/RED.

---

## 5. Parâmetros-chave (origem: `config.py`)

### Escanteios
| Parâmetro | Valor | Onde |
|---|---|---|
| Janela | min 50–90 (early se ≥7 esc) | `JANELA_ANTECIPADA_INICIO`, `ESCANTEIOS_EARLY_WINDOW` |
| Score Normal / Premium | 6 / 8 | `MIN_SCORE_NORMAL`, `MIN_SCORE_PREMIUM` |
| Edge Normal / Premium | 1.2 / 1.5 | `MIN_EDGE_NORMAL`, `MIN_EDGE_PREMIUM` |
| Linha máxima | 12.5 | `MAX_LINHA_ASIATICA` |
| Re-avaliação | 3 min, Δedge 0.7, Δscore 1 | `REAVALIACAO_*` |

### Cartões (controlado por `ANALISE_CARTOES_ATIVA`)
| Parâmetro | Valor | Onde |
|---|---|---|
| Janela | min 40+ (early se ≥4 cartões) | `CARTOES_MINUTO_INICIO`, `CARTOES_EARLY_WINDOW` |
| Score Normal / Premium | 5 / 8 | `CARTOES_MIN_SCORE_*` |
| Edge Normal / Premium | 0.5 / 1.2 | `CARTOES_MIN_EDGE_*` |

### Polling
| Parâmetro | Valor |
|---|---|
| `POLLING_INTERVAL` | 60s (ativo) |
| Intervalo idle | 15min/1h/2h conforme proximidade do próximo jogo |
| `API_DAILY_LIMIT` | 7500 (Pro) — atualmente **inativa**, key vencida |

---

## 6. Regras de Documentação

Toda documentação vive em `docs/`. **Nunca crie .md na raiz do projeto** (exceto este `CLAUDE.md`). Arquivos `.txt` de relatório/checklist legados na raiz (`WAHA_*.txt`, `START_HERE.txt`) não devem ser fonte de verdade — preferir `docs/`.

| Categoria | Pasta | Conteúdo |
|---|---|---|
| Architecture | `docs/architecture/` | Specs técnicas, diagramas, decisões de design |
| Análises | `docs/analises/` | Estudos, auditorias, modelo de decisão |
| Resumo | `docs/resumo/` | Snapshots executivos, relatórios curtos |
| Sprints | `docs/sprints/` | Roadmap, planejamento, próximos passos |
| Setup | `docs/setup/` | Deploy, WAHA, Cloudflare, ambiente |
| Manuals | `docs/manuals/` | DEPLOYMENT.md, USER_GUIDE.md (público) |
| API | `docs/api/` | Referência de endpoints |
| Changelog narrativo | `docs/CHANGELOG.md` | 1 entrada por sessão (regra atual — ver §12) |
| Changelog histórico | `docs/changelog/` | `YYYY-MM-DD-slug.md` (entregas anteriores a 2026-05-15) |
| Credenciais | `docs/credenciais/` | **Não versionar.** Adicionar a `.gitignore`. |

**Convenções:**
- kebab-case minúsculo: `decision-model.md`, não `DecisionModel.md`.
- Changelogs prefixados com data ISO: `2026-02-15-fix-waha-session-stopped.md`.
- Após criar um doc, **atualizar `docs/README.md`** linkando-o.
- Não duplicar: se já existe, edite ao invés de criar novo.

---

## 7. Boas Práticas de Código

### Geral
- Não criar arquivos novos quando dá para editar um existente.
- Não escrever comentários óbvios (já cobertos por nomes claros). Só comentar *por que*, nunca *o que*.
- Não introduzir abstrações para casos hipotéticos. Se três blocos parecem similares, tudo bem; só extrair quando houver quarto caso real.
- Não adicionar `try/except` defensivo dentro do sistema; só em fronteiras (API externa, I/O, webhook).
- Erros de pre-commit hooks devem ser corrigidos, nunca pulados (`--no-verify` proibido).

### Backend (Python)
- Tudo `async`. Não misturar `requests` com `aiohttp`.
- Usar `asyncpg` direto via `storage.database.Database`, não criar wrappers redundantes.
- Logs com `logger = logging.getLogger("CPES.<Modulo>")`.
- Parâmetros novos → adicionar em `config.py` com default seguro, não hardcode.
- Mudanças em modelos (`data/models.py`) devem refletir no schema (`storage/database.py`).
- Toda mudança no fluxo de decisão precisa de teste em `corner-pressure-elite/tests/`.

### Frontend (Next.js)
- App Router. Páginas autenticadas em `src/app/(authenticated)/`.
- Auth via cookie `cpes-auth` (JWT), validado no `middleware.ts` com `jose`.
- API base via `process.env.NEXT_PUBLIC_CPES_API` ou proxy `/api/cpes`.
- MUI v7 + tema custom em `src/lib/theme.ts`. Não misturar com Tailwind para componentes — Tailwind só para utilitários globais (`globals.css`).
- Sempre que adicionar página nova autenticada, criá-la dentro de `(authenticated)` para herdar o layout.

### Notificações WhatsApp
- **Nunca** criar `WhatsAppClient` novo a cada mensagem — sempre passar pelo `waha_manager.WAHASessionManager` (singleton). Histórico: criar/fechar repetido → `Session STOPPED`. Ver `docs/changelog/2026-02-15-fix-waha-session-stopped.md`.
- Webhooks WAHA Plus precisam ser registrados via `PUT /api/sessions/default` no startup. Variáveis de ambiente `WAHA_WEBHOOK_*` não bastam.
- Mensagens usam `*negrito*`, emojis Unicode (não shortcodes), e quebras `\n`. Ver `cards_message_formatter.py` como referência canônica.

---

## 8. Comandos Operacionais

```bash
# Subir tudo (Docker)
docker compose up -d --build

# Subir tudo (nativo, fora de Docker)
./start_all.sh

# Parar
docker compose down
./kill_all.sh

# Logs
docker logs -f cpes-api
docker logs -f cpes-main
docker logs -f cpes-dashboard
docker logs -f waha

# Reset banco (DESTRUTIVO — pede confirmação)
docker exec -it cpes-api python reset_db.py

# Registrar webhook WAHA manualmente (se startup falhou)
curl -X PUT http://localhost:3000/api/sessions/default \
  -H "X-Api-Key: $WAHA_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"config":{"webhooks":[{"url":"http://cpes-api:8000/api/webhook/whatsapp","events":["message"]}]}}'

# Forçar QR (primeira conexão WhatsApp)
xdg-open "http://localhost:3000/api/sessions/default/auth/qr"
```

---

## 9. Domínios e Endpoints Externos

Topologia real do tunnel (`~/.cloudflared/config.yml`, tunnel `ssh-tunnel` id `b763eef0-…`):

| Hostname | Origem local | Serviço |
|---|---|---|
| `iqpressure.online` / `www.` | `http://localhost:3001` | Dashboard Next.js (site principal) |
| `membros.iqpressure.online` | `http://localhost:3001` | Dashboard — área de membros |
| `api.iqpressure.online` | `http://localhost:8000` | API FastAPI (CPES) |
| `wa.iqpressure.online` | `http://localhost:3000` | WAHA Plus (gateway WhatsApp) |
| `ssh.iqpressure.online` | `ssh://localhost:22` | SSH |

> **Migração 2026-05-11:** o domínio público foi trocado de `odontoschultz.online` (legado, herança do consultório) para `iqpressure.online`. Os hostnames legados ainda estão no `config.yml` e no CORS durante a janela de transição (remoção planejada após 72h verde). Ver `docs/sprints/2026-05-11-migracao-dominio-iqpressure.md` e `docs/changelog/2026-05-11-migracao-dominio-iqpressure.md`.

Endpoints externos consumidos:
- `https://v3.football.api-sports.io` — API-Football v3 (`API_FOOTBALL_KEY`)
- `https://sandbox.asaas.com/api/v3` — Asaas SANDBOX (`ASAAS_API_KEY`, `ASAAS_WALLET_ID`). Em produção: `https://api.asaas.com/v3`. Webhook: `https://api.iqpressure.online/api/webhook/asaas` (validado pelo header `asaas-access-token` = `ASAAS_WEBHOOK_TOKEN`). O domínio do site precisa estar cadastrado em **Minha Conta → Dados Comerciais → Site** no painel Asaas — sem isso, criação de subscription retorna 400.
- `https://api.resend.com` — Resend (`RESEND_API_KEY`). Domínio `iqpressure.online` verificado (region `sa-east-1`); `EMAIL_FROM=PressureIQ <no-reply@iqpressure.online>`. Registros DNS (MX/SPF/DKIM) ficam em `send.iqpressure.online` e `resend._domainkey.iqpressure.online` — todos **DNS only** no Cloudflare.

Para apontar um subdomínio novo para o tunnel: `cloudflared tunnel route dns ssh-tunnel <sub>.iqpressure.online` (adicione `--overwrite-dns` se já existir DNS quebrado). Se o cert.pem do `cloudflared` não cobrir a zona alvo, rode `cloudflared tunnel login` antes (interativo, OAuth) e marque a zona certa.

---

## 10. Riscos Conhecidos / Estado Atual

> ⚠️ **MUITA COISA MUDOU NA FASE K (2026-05-15 a 2026-05-17).** §4 (pipeline) e §5 (parâmetros) descrevem o **passado AF-centric**. Pra estado atual pós-Fase K (cascade SofaScore, AF removido de runtime odds, cache stale, refetch, bridge `/event/state` etc.), **LEIA §13 PRIMEIRO**.

- **API-Football**: key Pro ATIVA até 2026-06-11 (`Daniel Lopes`, `hardtechdaniel@gmail.com`, plano Pro 7500 req/dia). AF continua usado pra **discovery** (`get_today_schedule`, `get_live_fixtures`, `get_teams`) e **cold checks** (resultado FT), mas FOI REMOVIDO do runtime de odds (P4-B, ver §13.4). Versão CLAUDE.md anterior dizia "vencida" — desatualizado.
- **Cobertura de teste**: limitada. Antes de mexer em `score_engine`, `decision_engine` ou `projection_engine`, rode `pytest corner-pressure-elite/tests/` e adicione casos.
- **Estimativas de janela**: `escanteios_ultimos_5min`/`_10min` são **estimativas via taxa**, não janelas reais. Idem para cartões. Os filtros e thresholds foram calibrados pensando nisso.
- **Auto-memory legada**: a memória do agente ainda referencia "SQLite at data/cpes.db" — isto é **falso desde a migração para Postgres**. Tratar `storage/database.py` (asyncpg) como fonte da verdade.
- **Arquivos legados na raiz**: vários `.txt` (`WAHA_BUG_SUMMARY.txt`, `START_HERE.txt`, etc.) e scripts soltos (`test_*.py`) sobreviveram de iterações antigas. Não usar como referência sem cruzar com o código atual.

---

## 11. Quando Em Dúvida

1. Antes de mudar lógica de decisão, leia primeiro o documento mestre em `docs/architecture/visao-geral-do-sistema.md` (se existir) ou `docs/PRODUCT_MASTER_PLAN.md`.
2. Antes de mexer em WAHA, leia `docs/changelog/2026-02-15-fix-waha-session-stopped.md` e `docs/architecture/waha-webhook-architecture.md`.
3. Antes de criar arquivos de doc, releia §6 e §12 deste arquivo.
4. Se for ação destrutiva (drop tabela, force push, reset DB), **pergunte ao usuário antes** mesmo que pareça óbvio.
5. **Antes de testar URL/endpoint/schema da Betano (ou qualquer alvo Cloudflare) via Playwright/bridge sem certeza** — peça ao usuário pra rodar mitmproxy no PC dele e capturar. Cada URL especulativa via Playwright conta como sinal de bot e pode flagar o IP residencial (downtime 12-24h). Detalhes e template de mensagem em `docs/architecture/playwright-anti-bot-checklist.md` §3 "Regra de incerteza".

---

## 12. Sistema de Documentação Ativa

O projeto mantém documentação ativa em `docs/`. **TODA sessão deve manter esses arquivos atualizados** conforme regras abaixo.

> **Nota sobre §6:** as regras desta seção §12 **superam** a linha "Changelog | docs/changelog/ | 1 arquivo por entrega" da tabela §6. Changelogs novos vão em `docs/CHANGELOG.md` (monolítico, narrativo, 1 entrada por sessão). A pasta `docs/changelog/` permanece como leitura histórica de entregas anteriores a 2026-05-15.

### Arquivos meta-doc (raiz `docs/`)

- `docs/DECISIONS.md` — Decisões arquiteturais (ADRs curtos: contexto, razão, trade-offs). Specs longas continuam em `docs/architecture/`.
- `docs/BUGS.md` — Bugs encontrados (sintoma, causa, fix, lição).
- `docs/CHANGELOG.md` — Resumo narrativo por sessão (substitui convenção antiga de `docs/changelog/YYYY-MM-DD-*.md`).
- `docs/OPERATIONS.md` — Runbook quick-reference (subir, derrubar, recovery). Setup detalhado fica em `docs/setup/`; deploy completo em `docs/manuals/DEPLOYMENT.md`.
- `docs/ROADMAP.md` — Fases planejadas + estado atual (1 linha por fase). Detalhes operacionais por sprint continuam em `docs/sprints/`.
- `CLAUDE.md` (este) — Convenções, regras, topologia.

### Regras de manutenção

**Toda sessão DEVE:**
1. **Ao começar:** Ler `CHANGELOG.md` (última entrada) + `ROADMAP.md` (estado atual) pra contexto rápido.
2. **Quando encontrar bug:** Adicionar entrada em `BUGS.md` após fix (sintoma + causa + fix + lição).
3. **Quando tomar decisão arquitetural:** Adicionar entrada em `DECISIONS.md` (contexto + razão + trade-offs).
4. **Antes de fechar sessão:** Adicionar entrada em `CHANGELOG.md` resumindo o que foi feito.
5. **Quando fase fechar ou nova for planejada:** Atualizar `ROADMAP.md`.
6. **Quando descobrir procedure operacional:** Adicionar em `OPERATIONS.md` (recovery, deploy, validação).
7. **Quando convenção/regra/topologia mudar:** Atualizar este `CLAUDE.md`.

### Princípios

- **Conciso > exaustivo.** Cada entrada deve ser lida em <60s.
- **Narrativo > tabular.** Explica "porquê", não só "o quê".
- **Atualizar conforme acontece.** Não acumular pra fim de semana.
- **Linkar entre arquivos.** "Ver `BUGS.md#deadlock-cartoes`" em vez de duplicar.
- **Commits separados.** Doc commit não mistura com code commit. Padrão: `docs(<arquivo>): <descrição>`.

### Exemplo de commit de doc

```
docs(bugs): adicionar bug bridge bindando 127.0.0.1

Fase 2bc smoke revelou que container Docker não alcançava bridge.
Causa raiz, fix e lição registrados em docs/BUGS.md.
```

---

## 13. Fase K (2026-05-15 a 2026-05-17): Cascata SofaScore + Bridge state + Cache stale + Refetch + AF removido

> **Esta seção descreve o estado ATUAL do sistema pós-Fase K.** §4 e §5 descrevem o pipeline AF-centric do passado. Leia **esta seção primeiro** ao tocar em odds, stats, events, lineups, decision_engine ou notifier.

### 13.1 Visão geral

A Fase K substituiu **API-Football como fonte primária runtime** por uma cascata 3 camadas com **SofaScore + Bridge Betano (Danae API nativa)**. Decisão crítica D4: **ZERO AF em runtime de odds** — sistema fica silente em outage extremo (filosofia "silêncio é melhor que sinal errado").

**O que AF AINDA FAZ:**
- Discovery (`get_today_schedule`, `get_live_fixtures`, `get_teams`)
- Cold checks (`get_fixture_result` pra FT após 2h)
- Stats fallback de último recurso na cascata (raramente acionado)
- Suporte ao discovery do `BetanoFixtureDiscovery` (cross-reference)

**O que AF DEIXOU DE FAZER (runtime):**
- ❌ `get_live_odds_*` em runtime (cascata só usa Betano + cache stale)
- ❌ Stats live (foi pra cascata `bridge_betano → sofascore → apifootball`)
- ❌ Events live (cascata)
- ❌ Lineups (cascata + enriquecimento SofaScore)

### 13.2 Cascata K.1 (Stats + Events + Lineups + Enrichment)

Configurada via `USE_SOFASCORE=true` (default em produção):

```
composite_stats.k1_mode primary=bridge_betano intermediate=sofascore final=apifootball enrichment=True
composite_events.k1_cascade providers=['bridge_betano', 'sofascore', 'apifootball']
composite_lineups.k1_enricher providers=['bridge_betano', 'apifootball'] enricher=sofascore
```

**SofaScoreClient** (`data/providers/sofascore/client.py`) usa `curl_cffi` com `impersonate=chrome120` pra bypass de TLS fingerprint (Cloudflare bloqueia HTTP clients normais com 403 Varnish). Rate limit 10 req/s.

**SofaScoreEventResolver** (`data/providers/sofascore/event_resolver.py`) faz fuzzy match `fixture_id` (AF) → `sofa_event_id` via team_id_lookup (AF teams → SofaScore teams). Depende de `betano_team_map.api_football_team_id` populado.

**Enrichment**: snapshot bridge_betano é o primário; SofaScore preenche gaps (`shots_on_target`, `possession`, `dangerous_attacks`, `coach_name`, `missing_players`). Campo `stats_history.enriched_by JSONB` lista providers que enriqueceram (ex: `["sofascore"]`).

**Distribuição típica em produção (medida 2026-05-17):**
- Stats: ~60% sofascore, ~23% bridge_betano (enriched 100%), ~20% AF residual
- Events: ~87% bridge_betano, ~8% AF, ~5% sofascore
- Lineups: 100% bridge_betano (enriquecidas via SofaScore — 54% com `coach_name` + `missing_players`)
- Odds: 100% betano_bridge (após P4-B), `apifootball` ZERO em runtime

### 13.3 P1 — Bridge `/event/<id>/state` (cutover odds)

Rota legada `/markets` no bridge foi **nuked por anti-bot Cloudflare** em 2026-05-17 (`text_len=0` consistente). Migração pra rota nova `/event/<id>/state` que proxia o JSON nativo `/danae-webapi/api/live/events/<id>/latest` da Betano.

**Componentes:**
- `~/cookie-renewer/server.py` no danewell: endpoint `/danae/event/<id>/state` (criado em E.1 PARTE A, requer headers `X-Operator: 8` + `X-Language: 5` — sem eles Betano retorna 200 silencioso com payload vazio).
- `~/cpes-bridge/server.py` no odin: endpoint `/event/<id>/state` (cache 3s LRU + ETag via `if_version` retorna 304).
- `data/providers/betano_bridge/state_markets_parser.py`: filtra markets por type code (CNOU/COU1=corners, TCOU/1COU=cards) e extrai `{line, over_price, under_price}`.
- `BetanoBridgeOddsAdapter` ganhou `use_state_endpoint: bool` — quando true, lê markets via `/event/state` em vez de `/markets`.

**Configs:** `USE_NEW_MARKETS_ROUTE=true` (default false; em prod = true desde 2026-05-17).

**Validado em smoke:** 78-100% odds via `betano_bridge` (vs 0% antes; Bug 1 do user resolvido).

**Bug crítico do meu /event/state (corrigido):** `JSONResponse(status_code=304, content=None)` causava `RuntimeError: Response content longer than Content-Length`. Fix: `Response(status_code=304)` bare (commit `12d1017` no bridge).

### 13.4 P4-B — Cache stale + AF removido runtime odds

Quando bridge `/event/state` falha, em vez de cair pra AF, sistema agora cai pra **cache local com TTL adaptativo**:

| Mercado | TTL | Stale (entre TTL e 2×TTL) | Expirado (>2×TTL) |
|---|---|---|---|
| corners | 30s | retorna com `is_stale=True` | retorna None |
| cards | 30s | idem | idem |
| over_under_goals | 20s | idem | idem |
| match_winner | 15s | idem | idem |

**Componentes:**
- `data/providers/betano_bridge/odds_cache.py`: `OddsCache` in-memory com TTL por mercado.
- `data/providers/betano_bridge/cached_odds_provider.py`: `CachedBetanoOddsProvider` envolve `BetanoBridgeOddsAdapter` + cache. Implementa `OddsProvider` Protocol (drop-in replacement do composite com AF).
- Atenção: `CachedBetanoOddsProvider.name = "betano_bridge"` (não `betano_bridge_cached`!) — `CompositeOddsProvider._dispatch` só passa contexto rico (`persist_telemetry=True`) pra providers com nome exato `betano_bridge`. Renomear quebra persist silenciosamente.
- `CanonicalOverUnder` ganhou `is_stale: bool = False` + `age_seconds: int = 0` (back-compat).
- `OddsHistoryEntry` idem + 2 colunas novas no SQL (migration 0009).
- `BetanoBridgeClient.event_state` ganhou **reconnect agressivo**: 4 attempts em ~3.5s com backoff `[0, 0.5, 1, 2]s`. Log `bridge.event_state.recovered` quando retry pega recuperação.

**Configs:** `REMOVE_AF_FROM_ODDS_RUNTIME=true` (default false; em prod = true desde 2026-05-17).

**Filosofia D4 aprovada:** sistema fica silente em outage extremo. Bridge down + cache expirado = `None` retornado, decision engine não emite. **Silêncio é melhor que sinal errado.**

### 13.5 P5 — Refetch just-before-send + blocked_signals + timestamp WhatsApp

Latência entre captura odds → DB → WAHA → user_abre_betano (5-65s) deixa odd defasada. Solução: **refetch obrigatório antes de cada `notifier.send_signal`**.

**Componentes:**
- `engine/odds_refetch.py`: `refetch_validate_corners` / `refetch_validate_cards`. Refaz chamada `composite_odds.get_<market>`, valida 5 condições. Se qualquer condição falhar → ABORTA emit + registra em `blocked_signals`.
- 5 condições de abort: `refetch_none` (bridge falhou + cache vazio), `refetch_stale` (cache age > TTL), `line_changed` (mercado fechou linha), `odd_drift` (>15% movimento), `refetch_exception`.
- `data/repositories/blocked_signals.py`: `BlockedSignalsRepo.insert` (telemetria swallow-on-error).
- `JogoAoVivo` ganhou `odds_is_stale` + `odds_age_seconds` (corners + cartoes).
- `main.py`: gate em corners (linha ~1380) e cards (~1450). Se `jogo.odds_is_stale`: log + skip send_signal + DM + registrar_sinal.
- `notifier/message_formatter.py`: mensagem WhatsApp agora inclui `⏱️ *Odd capturada:* HH:MM:SS (snapshot — odd pode variar segundo-a-segundo)` no bloco MERCADO.

**Configs:** `ODDS_REFETCH_BEFORE_EMIT=true` (default true, fail-safe) + `ODDS_REFETCH_MAX_DRIFT_PCT=0.15` (15% tolerância).

**Bridge cache 3s** geralmente faz refetch ser instantâneo (cache hit) — overhead 0ms quando cache válido, ~5-8s quando cache miss.

### 13.6 P2 — Team_map populado

`betano_team_map` tinha 18.8% cobertura (98/521 times com `api_football_team_id`). Script `data/scripts/populate_team_map.py` cruza `AF /teams?league=X&season=Y` (12 ligas top: Premier, La Liga, Serie A, Bundesliga, Ligue 1, Eredivisie, Liga Portugal, Champions, Europa, MLS, Argentina, Brasileirão B) contra `betano_team_name` sem AF, fuzzy match com rapidfuzz (ratio + token_sort — sem partial, causa falsos positivos).

**Resultado pós-P2 (2026-05-17):** cobertura 29.0% (151/521 times). Discovery match rate 7% → 11% (1 ciclo). Issue C resolvido (Newcastle, West Ham, Atletico Bilbao, Celta Vigo, etc. agora mapeados).

**Como rodar de novo (ligas novas, temporadas):**
```bash
docker exec -e PYTHONPATH=/app -w /app cpes-main python data/scripts/populate_team_map.py
# Output: /tmp/team_map_proposed.json + /tmp/team_map_updates.sql
# Manual review entries com needs_review=true antes de apply
docker cp cpes-main:/tmp/team_map_updates.sql /tmp/
docker exec -i cpes-postgres psql -U cpes_user -d cpes < /tmp/team_map_updates.sql
```

### 13.7 P4 (renewer Brave) — PARTE 1 PENDENTE

**Achado importante (2026-05-17):** P4 quick-win (cron 12h restart Brave) é **INÚTIL** porque `brave-betano.service` no danewell já tem `Restart=always`. Cron desinstalado, script `restart-brave.sh` deprecated.

**Problema real:** Brave do pool **degrada silenciosamente** após algum tempo (`fetch()` interno retorna `TypeError: Failed to fetch` mas processo continua vivo, `/health` superficial responde OK). `Restart=always` só pega crash real.

**Hipótese (sem evidência forte):** JS runtime accumulation em pages live da Betano (SignalR + Vue + handlers WebSocket) ou cookies CF expirando, ou proxy 8888 ML Telecom flagueando.

**Solução planejada (não implementada):** `/health/deep` endpoint no renewer que faz fetch real e valida JSON parseável, + daemon `BraveSupervisor` que monitora 30s/2-threshold/10min-cooldown e restart via `sudo systemctl restart brave-betano.service` (precisa sudoers NOPASSWD entry pro user `danewell`).

**Estado atual:** P5 mitiga (sinais bloqueados em outage), mas restart manual via `ssh danewell 'sudo systemctl restart brave-betano.service'` ainda é necessário em outages prolongados.

### 13.8 Infraestrutura no danewell (192.168.1.5)

**Topologia 4-service systemd:**

| Service | Função |
|---|---|
| `xvfb-display101.service` | Xvfb :101 (display headless pra Brave) |
| `tinyproxy-betano.service` | tinyproxy 127.0.0.1:8888 → proxy residencial RJ (ML Telecom, autenticado) |
| `brave-betano.service` | Brave headed under :101, CDP `:9224`, `--proxy-server=http://127.0.0.1:8888` |
| `chrome-betano.service` | Chrome headed under :100, CDP `:9222` (legado, `/odds/<id>/` via Playwright) |
| `cdp-proxy.service` | socat TCP `0.0.0.0:9223` → `127.0.0.1:9222` (Chrome CDP exposto pro odin) |
| `cookie-renewer.service` | FastAPI `:8081` — endpoints `/danae/live`, `/danae/event/<id>/state`, `/cookies/last`, `/health` |

**Por que Brave + Chrome dois browsers separados:** Chrome 148 é bloqueado pela Cloudflare em `/danae-webapi/*` (TLS fingerprint discriminado). Brave 1.90.122 (Chromium 148 mas TLS diferente + `navigator.brave` exposto) passa. Chrome continua útil pra `/odds/<id>/` (mercados via Playwright) que não passam por `/danae-webapi/*`.

**Egress isolado por browser:**
- Brave → tinyproxy 8888 → proxy residencial RJ `200.234.172.57` (ML Telecom AS10704)
- Chrome → IP casa Curitiba `200.181.212.29`

**SSH ao danewell:** alias `danewell` em `~/.ssh/config` (User `danewell`, IdentityFile `~/.ssh/id_ed25519_danewell`). Não usar `ssh daniel@192.168.1.5` — usuário errado.

### 13.9 Novas tabelas e migrations (2026-05-15+)

| Migration | Tabela | Função |
|---|---|---|
| `0001_betano_fixture_map.sql` | `betano_fixture_map` | fixture_id (AF) ↔ betano_event_id (Danae) |
| `0002_odds_history.sql` | `odds_history` | telemetria odds capturadas |
| `0003_incidents_history.sql` | `incidents_history` | eventos do jogo (GOAL/YELL/CRNR etc.) |
| `0004_betano_team_map.sql` | `betano_team_map` | betano_team_id ↔ api_football_team_id (fuzzy match) |
| `0005_stats_history.sql` | `stats_history` | snapshots de stats por fixture (cada ciclo) |
| `0006_events_history.sql` | `events_history` | eventos de partida (dedup via UNIQUE) |
| `0007_lineups_history.sql` | `lineups_history` | lineups (home/away por fixture) |
| `0008_sofascore_enrichment.sql` | adds `stats_history.enriched_by` + `lineups_history.missing_players` JSONB | Fase K.1 |
| `0009_odds_stale_tracking.sql` | adds `odds_history.is_stale` + `source_age_seconds` | Fase P4-B |
| `0010_blocked_signals.sql` | `blocked_signals` | sinais abortados pelo refetch P5 (telemetria) |

Migrations rodam idempotentes via `storage/database.py::_apply_sql_migrations` no boot.

### 13.10 Configs novos em `.env` (estado prod 2026-05-17)

| Variável | Valor prod | Default |
|---|---|---|
| `USE_BETANO_BRIDGE` | `true` | `false` |
| `USE_SOFASCORE` | `true` | `false` |
| `USE_BETANO_STATS` | `true` | `false` |
| `USE_BETANO_EVENTS` | `true` | `false` |
| `USE_BETANO_LINEUPS` | `true` | `false` |
| `USE_NEW_MARKETS_ROUTE` | `true` | `false` |
| `REMOVE_AF_FROM_ODDS_RUNTIME` | `true` | `false` |
| `ODDS_REFETCH_BEFORE_EMIT` | (sem setar → default true) | `true` |
| `ODDS_REFETCH_MAX_DRIFT_PCT` | (sem setar → default 0.15) | `0.15` |
| `BETANO_BRIDGE_URL` | `http://192.168.1.18:8080` | `http://localhost:8080` |
| `DANEWELL_RENEWER_URL` | `http://192.168.1.5:8081` | idem |

### 13.11 Workers ativos em `corner-pressure-elite/workers/`

| Worker | Função |
|---|---|
| `betano_discovery.py` | Roda em loop, casa eventos Betano (Danae overview) com fixtures AF via team_id_lookup + fuzzy. Popula `betano_fixture_map`. |
| `betano_stats_worker.py` | Poll por fixture, enriquece via SofaScore, persiste `stats_history`. |
| `betano_events_worker.py` | Captura eventos Betano (timeline) + dedup. |
| `betano_lineups_worker.py` (se existir) | Captura lineups + enriquecimento. |

### 13.12 Bugs documentados na Fase K (ler `docs/BUGS.md` pra detalhes)

- 2026-05-15 — Cookies cf_clearance bound a IP+TLS+UA (cliente HTTP externo SEMPRE retorna 403)
- 2026-05-15 — IP residencial flagueado pela Cloudflare Bot Management (Playwright burst)
- 2026-05-16 — Falso-bug: adaptive polling em pre-janela (capturas baixas iniciais são normais)
- 2026-05-17 — `CachedBetanoOddsProvider.name` precisa ser exato `"betano_bridge"` (persist quebra silencioso senão)
- 2026-05-17 — `/event/state` 304 com `JSONResponse(content=None)` causa RuntimeError no uvicorn
- 2026-05-17 — `brave-betano.service` já tem `Restart=always` — cron preventivo é redundante; problema é degradação silenciosa
- 2026-05-17 — Endpoint Betano `/events/<id>/latest` exige headers `X-Operator: 8` + `X-Language: 5` (sem eles retorna 200 com payload vazio)

### 13.13 Pendências conhecidas pós-Fase K

- **P4 PARTE 1** (supervisor reativo Brave) — único item operacional crítico aberto
- Tab leak no Brave (visto 5 tabs `betano.bet.br/` simultâneas) — investigar se é real ou artefato
- Sudoers NOPASSWD entry pra `danewell` rodar `systemctl restart brave-betano.service` (pré-requisito do supervisor)
- AF runtime cleanup (Fase H planejada) — remover código AF não usado depois que P4 estabilizar
