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

- **API-Football**: a key está expirada/sem créditos no momento. O sistema cai em "sem requisições" e pausa o monitoramento. Renovar antes de tentar reativar.
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
