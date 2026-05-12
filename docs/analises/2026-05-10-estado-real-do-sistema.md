# CPES / PressureIQ — Estado Real do Sistema (2026-05-10)

> Auditoria completa feita lendo todo o código (`corner-pressure-elite/`, `dashboard/`),
> a documentação de `docs/` e os artefatos de configuração (`docker-compose.yml`,
> `.env`, schema do Postgres). Este documento substitui em conteúdo qualquer
> divergência encontrada em docs anteriores — quando houver conflito, **vale o que
> está aqui ou no código**, não em docs antigas.

Autor: análise automática (Claude). Data: 2026-05-10.

> **Nota (2026-05-11):** depois desta auditoria o domínio público foi migrado de `odontoschultz.online` para `iqpressure.online` (ver `docs/changelog/2026-05-11-migracao-dominio-iqpressure.md`). Referências a `odontoschultz.online` neste doc refletem o estado anterior; estado atual em `CLAUDE.md` §9.

---

## 1. Resumo Executivo

O CPES (também conhecido como PressureIQ) é um motor de decisão de apostas ao
vivo em escanteios e cartões amarelos do futebol, com:

- ingestão da API-Football v3,
- duas pipelines de análise paralelas (escanteios + cartões),
- entrega via WhatsApp usando WAHA Plus,
- dashboard Next.js para acompanhamento dos sinais,
- backend FastAPI para auth, pagamentos (Asaas) e e-mail transacional (Resend),
- persistência em PostgreSQL.

Está **funcional em código** mas **fora do ar agora** porque a chave da
API-Football não está renovada. Nenhum container está rodando atualmente.
Reativar exige: renovar API-Football, subir Postgres+WAHA+API+main+dashboard,
escanear QR no WhatsApp, registrar webhook.

---

## 2. O Que Existe e Funciona

### 2.1 Backend Python (`corner-pressure-elite/`)

| Componente | Arquivo | Status |
|---|---|---|
| Loop principal | `main.py` (1122 linhas) | ✅ Implementado, com polling adaptativo, agenda matinal, alerta pré-jogo, resumo diário |
| API REST | `api_server.py` (≈900 linhas) | ✅ FastAPI com auth JWT, dashboard, checkout Asaas, webhooks WAHA + Asaas |
| Cliente API-Football | `data/api_client.py` | ✅ Live fixtures, agenda por season, statistics, events, odds (live + pré-match), odds multi-bookmaker (Betano 46, Bet365 8), odds de cartões, resultados finais |
| Pressure Score (escanteios) | `engine/score_engine.py` | ✅ 6 componentes graduados, máx 11 |
| Tension Score (cartões) | `engine/cards_score_engine.py` | ✅ 6 componentes graduados, máx 11 |
| Projeção escanteios | `engine/projection_engine.py` | ✅ Híbrida: ritmo + pressão (×0.25) + histórico (+0.5) |
| Projeção cartões | `engine/cards_projection_engine.py` | ✅ Híbrida: ritmo + tensão (×0.15) + histórico (+0.3) |
| Decisão escanteios | `engine/decision_engine.py` | ✅ Filtros + score + odds + edge + auditoria por ciclo |
| Decisão cartões | `engine/cards_decision_engine.py` | ✅ Igual ao de escanteios, parâmetros próprios |
| State manager | `engine/state_manager.py` + `cards_state_manager.py` | ✅ Re-avaliação, entrada adicional, deduplicação |
| Cliente WAHA | `notifier/whatsapp_client.py` | ✅ aiohttp, suporte a WAHA Plus (X-Api-Key) |
| Singleton WAHA | `notifier/waha_manager.py` | ✅ Resolve bug de Session STOPPED |
| Notification manager | `notifier/notification_manager.py` | ✅ Roteia para grupo escanteios, grupo cartões e admin |
| Formatadores | `notifier/message_formatter.py`, `cards_message_formatter.py` | ✅ Mensagens com markdown WhatsApp e emojis |
| Asaas | `notifier/asaas_client.py` | ✅ Integração de cobrança/assinatura |
| E-mail transacional | `services/email_service.py`, `email_worker.py` | ✅ Resend + 4 templates HTML (welcome, payment, renewal, cancellation) |
| Banco | `storage/database.py` | ✅ Postgres via asyncpg, schema completo |
| Helpers | `utils/helpers.py` | ✅ Parser fixture→jogo, enrichment de cartões, estimativas de janela |
| Rate limit | `utils/rate_limiter.py` | ✅ 7500/dia + 450/min |
| Polling adaptativo | `utils/adaptive_polling.py` | ✅ Frequência variável por minuto/escanteios |
| Backtest | `backtest/` | ⚠️ Existe estrutura mas dependeu de SQLite e snapshot histórico — precisa revisão pós-migração Postgres |
| Testes | `tests/` | ⚠️ Cobertura limitada; testes existentes em `test_decision`, `test_score`, `test_whatsapp` |

### 2.2 Frontend Next.js (`dashboard/`)

Estado atual (após refatoração que apagou os componentes antigos `LiveGames/`, `MetricCard.tsx`, `RecentSignals.tsx`, etc):

```
src/
├── middleware.ts                       # JWT em cookie cpes-auth via jose
├── app/
│   ├── layout.tsx                      # html/body raiz
│   ├── page.tsx                        # redirect → /dashboard
│   ├── globals.css
│   ├── login/page.tsx                  # form de login
│   ├── checkout/{success,cancel}/page.tsx
│   ├── api/auth/{login,logout}/route.ts
│   └── (authenticated)/
│       ├── layout.tsx                  # Drawer MUI + ThemeProvider + nav
│       ├── dashboard/page.tsx          # KPIs + gráfico Recharts + próximos jogos
│       ├── escanteios/page.tsx         # Lista de sinais de escanteios
│       ├── cartoes-amarelos/page.tsx   # Lista de sinais de cartões
│       ├── settings/page.tsx           # Configurações do robô
│       └── logs/page.tsx               # Streaming de logs
└── lib/{api.ts,theme.ts,utils.ts}
```

Stack: Next 16.1.6 + React 19.2.3 + MUI 7.3.8 + Recharts 3.7.0 + jose 6.1.3 + bcryptjs 3.0.3.
Build alvo Cloudflare via `@opennextjs/cloudflare`.

Observação: o git mostra muitos componentes antigos como **deletados** (não substituídos). A nova UI usa as 5 páginas autenticadas listadas acima — ela é mais enxuta e baseada em MUI, sem componentes próprios reutilizáveis significativos. Funciona, mas o `dashboard/src/components/` está hoje vazio.

### 2.3 Banco de Dados (Postgres 15)

Schema (extraído de `storage/database.py`):

- **`sinais`** — sinais emitidos. Inclui colunas para escanteios e cartões (campo `tipo_analise`).
- **`detalhes_jogo`** — dados de pressão por sinal (`ataques_perigosos`, `finalizacoes`, `posse`, etc).
- **`ligas_config`** — quais ligas estão ativas (toggle no dashboard).
- **`thresholds_config`** — parâmetros de score/edge ajustáveis em runtime.
- **`snapshots`** — fotografia de cada jogo a cada ciclo (para backtest e auditoria, agora também com cartões).
- **`users`** — usuários com `is_verified`, `verification_code`, role.
- **`subscriptions`** — assinaturas Asaas (plan basic/max, status pending/active/overdue/canceled).
- **`email_logs`** — auditoria dos e-mails transacionais.
- Estado serializado (`live_state`, `audit_state`, `upcoming_games`) é persistido via `upsert_state` em uma tabela genérica de KV.

A migração de SQLite → Postgres já aconteceu. Os arquivos `data/cpes.db` e `data/cpes_backup_20260218.db` são **legado** e podem ser removidos com segurança após verificação manual.

### 2.4 WhatsApp via WAHA Plus

Imagem: `devlikeapro/waha-plus:latest`. Sessão `default`. Auth via `X-Api-Key` no header.

Configurações importantes:

- `WAHA_DASHBOARD_USERNAME=admin`
- `WAHA_DASHBOARD_PASSWORD=Cpes2026@WhatsApp!Secure`
- Webhook **registrado em runtime** via `PUT /api/sessions/default` (não funciona via env var).
- Singleton de sessão (`waha_manager.WAHASessionManager`) garante que `client.start()` só seja chamado uma vez — corrige histórico de erros 422 (Session STOPPED).

Roteamento de mensagens:
- Grupo principal (`WHATSAPP_GROUP_ID`): sinais de escanteios, re-avaliações, agenda matinal, alerta pré-jogo, resumo diário.
- Grupo de cartões (`WHATSAPP_GROUP_CARTOES`): sinais e resumos diários de cartões — só ativa se `ANALISE_CARTOES_ATIVA=true`.
- Admin (`WHATSAPP_ADMIN`): erros de runtime, status de boot, status sob demanda.
- Updates (`WHATSAPP_UPDATES`): número adicional, por exemplo do cofundador.

Comandos no WhatsApp recebidos via webhook (`/api/webhook/whatsapp`): `/status`, `/jogos`, `/stats`, `/help`. Apenas senders na lista `_authorized_senders` do `api_server.py` são respondidos.

### 2.5 Pagamentos (Asaas) + E-mail (Resend)

- Cliente Asaas em `notifier/asaas_client.py`. Webhook em `POST /api/webhook/asaas` no FastAPI.
- Eventos publicados em fila interna (`services/email_worker.py`): `EVENT_USER_REGISTERED`, `EVENT_PAYMENT_CONFIRMED`, `EVENT_SUBSCRIPTION_CANCELLED`, `EVENT_SUBSCRIPTION_RENEWED`.
- E-mails enviados pela Resend, templates em `corner-pressure-elite/templates/{welcome,payment,renewal,cancellation}.html`.
- Planos: `basic` (Pro) e `max`.

---

## 3. Lógica do WAHA — Resumido

```
[boot] cpes-api inicia
  └─ on_event("startup")
       ├─ aguarda WAHA responder em GET /api/sessions (até 60s)
       └─ PUT /api/sessions/default { config: { webhooks: [...]} }
              └─ webhook = http://cpes-api:8000/api/webhook/whatsapp, events=["message"]

[runtime] usuário envia mensagem para o número do WAHA
  └─ WAHA dispara POST /api/webhook/whatsapp para cpes-api
       └─ api_server parseia { event:"message", payload: { from, body } }
            ├─ valida sender em _authorized_senders
            ├─ parse comando (/status, /jogos, /stats, /help)
            ├─ busca dados no Postgres
            ├─ formata resposta (MessageFormatter)
            └─ envia via send_whatsapp_message() (singleton)
                  └─ POST /api/sendText no WAHA → WhatsApp

[outbound: sinal emitido pelo robô]
  cpes-main → DecisionEngine.avaliar()
    └─ NotificationManager.send_signal()
         └─ WhatsAppClient.send_text(group_id, msg)
              └─ POST /api/sendText no WAHA → grupo VIP
```

Lições aprendidas (já refletidas no código):
1. **Não fechar a sessão depois do envio.** Cada `client.close()` levava a `Session STOPPED` no próximo request. Resolvido com `WAHASessionManager` (singleton, asyncio.Lock).
2. **Variáveis `WAHA_WEBHOOK_*` no docker-compose não bastam** para registrar o webhook; é preciso `PUT /api/sessions/default`.
3. **WAHA Plus tem dashboard próprio** em `http://localhost:3000/` (basic auth). Usar para checar QR, sessão, histórico de webhook.

---

## 4. Lógica de Sinais de Escanteios

### 4.1 Filtros estruturais (`decision_engine._verificar_filtros`)

Bloqueia o jogo se qualquer um:
- minuto < 50 **e** `escanteios_total < 7` (early window não acionada);
- minuto ≤ 45 e `diferenca_gols ≥ 3` (goleada no 1T);
- `diferenca_gols > 3` em qualquer momento;
- `escanteios_total < 3`;
- `escanteios_ultimos_5min < 1` (estimado via taxa);
- 0×0 com minuto ≥ 60 e `escanteios_total < 7` (jogo morno);
- minuto > 45 e algum dos times com 0 escanteios (passivo).

### 4.2 Pressure Score (máx 11)

| Componente | Pontos | Condição |
|---|---|---|
| Escanteios estimados em 10 min | +3 | `escanteios_ultimos_10min ≥ 2` |
| Escanteio recente (5 min) | +1 | `escanteios_ultimos_5min ≥ 1` |
| Ataques perigosos (taxa/min) | +3 / +2 / +1 / 0 | `≥1.0 / ≥0.7 / ≥0.4 / <0.4` |
| Time perdendo por 1 gol | +2 | `diferenca_gols == 1` |
| Posse dominante | +1 | `posse ≥ 60%` |
| Finalizações (taxa/min) | +1 / 0 | `≥0.10 / <0.10` |

Threshold mínimo: 6 (Normal) ou 8 (Premium). Os campos `ataques_perigosos`, `posse`, `finalizacoes` são *totais do jogo* (a API não fornece janela), normalizados em taxa/minuto para evitar inflar pontos em jogos parados.

### 4.3 Projeção híbrida

```
projecao = (escanteios_total / minuto) * 95
         + pressure_score * 0.25
         + (0.5 se media_historica_combinada > 10.5 senão 0)
```

### 4.4 Edge e decisão

```
edge = projecao - linha_atual
sinal = PREMIUM se score ≥ 8 e edge ≥ 1.5
      NORMAL  se score ≥ 6 e edge ≥ 1.2
      None    caso contrário
```

Linha máxima aceita: `MAX_LINHA_ASIATICA = 12.5` (acima disso o mercado é considerado inalcançável).

### 4.5 Re-avaliação

Após o primeiro sinal:
- Se `Δedge ≥ 0.7` **ou** `Δscore ≥ 1` **e** já passaram 3 minutos → manda re-avaliação no grupo.
- Se cenário melhorar substancialmente, sugere entrada adicional (0.5u) via `state_manager.deve_sugerir_entrada_adicional`.

---

## 5. Lógica de Sinais de Cartões Amarelos

A análise de cartões reaproveita a chamada de stats da API (0 reqs extras) usando `helpers.enrich_jogo_with_cards`. Os campos populados são `cartoes_amarelos_*`, `cartoes_vermelhos_*`, `faltas_*`, `cartoes_ultimos_5min/10min` (estimados via taxa, mesma lógica dos escanteios).

### 5.1 Filtros (`cards_decision_engine._verificar_filtros`)

- minuto < 40 **e** `cartoes_amarelos_total < 4` (sem early window);
- `diferenca_gols > 3`;
- `cartoes_amarelos_total < 1`;
- `cartoes_ultimos_5min < 1`;
- 0×0 minuto ≥ 60 e `cartoes_amarelos_total < 3`.

### 5.2 Tension Score (máx 11)

| Componente | Pontos | Condição |
|---|---|---|
| Cartões estimados em 10 min | +3 | `cartoes_ultimos_10min ≥ 2` |
| Cartão recente (5 min) | +1 | `cartoes_ultimos_5min ≥ 1` |
| Faltas (taxa/min) | +3 / +2 / +1 / 0 | `≥0.40 / ≥0.30 / ≥0.20 / <0.20` |
| Diferença de 1 gol (tensão tática) | +2 | `diferenca_gols == 1` |
| Cartão vermelho (jogo esquentou) | +1 | `cartoes_vermelhos_total ≥ 1` |
| Minuto ≥ 70 (tensão final) | +1 | `minuto ≥ 70` |

### 5.3 Projeção e edge

```
projecao = (cartoes_amarelos_total / minuto) * 95
         + tension_score * 0.15
         + (0.3 se media_historica_cartoes > 4.0 senão 0)

edge = projecao - linha_cartoes
sinal = PREMIUM se score ≥ 8 e edge ≥ 1.2
      NORMAL  se score ≥ 5 e edge ≥ 0.5
```

Médias históricas por liga (em `LIGAS_MEDIA_CARTOES`):

| Liga | Média de cartões/jogo |
|---|---|
| Premier League | 3.8 |
| Bundesliga | 4.2 |
| Serie A (Itália) | 4.8 |
| La Liga | 5.0 |
| Eredivisie | 4.0 |
| Liga Portugal | 4.5 |
| Brasileirão A | 4.3 |
| Brasileirão B | 4.1 |
| Argentina | 4.6 |

Re-avaliação segue a mesma regra dos escanteios (3 min, Δedge ≥ 0.7, Δscore ≥ 1) — usa parâmetros compartilhados (`REAVALIACAO_MIN_INTERVALO`, `REAVALIACAO_EDGE_DELTA`, `REAVALIACAO_SCORE_DELTA`).

Análise de cartões só roda se `ANALISE_CARTOES_ATIVA=true` no `.env` (atualmente está `true`).

---

## 6. Estado Atual do .env (segredos sensíveis)

> **Atenção**: o `.env` real do projeto contém credenciais. Esta seção mostra
> a *forma* das chaves, não os valores. Quem precisar dos valores deve usar
> o arquivo direto. Considere mover esses segredos para um secret manager
> (Cloudflare, Doppler, Vault) antes de produção real.

Chaves presentes em `corner-pressure-elite/.env`:

- `API_FOOTBALL_KEY` — vencida em 2026-05; **renovar antes de reativar**.
- `WAHA_API_KEY` — gerada em `2026-02-15`, formato `waha_sk_…`.
- `WAHA_SESSION_NAME=default`.
- `WHATSAPP_GROUP_ID` — id no formato `…@g.us`.
- `WHATSAPP_ADMIN`, `WHATSAPP_UPDATES` — dois números administrativos.
- `ASAAS_API_KEY` — chave **PROD** (`$aact_prod_…`). Tratar como crítica.
- `JWT_SECRET` — atualmente `changeme_…`; **trocar por valor gerado** antes de subir em produção.
- `RESEND_API_KEY` (`re_…`) e `EMAIL_FROM=onboarding@resend.dev` (domínio default da Resend).
- `APP_URL=https://odontoschultz.online`.
- `ANALISE_CARTOES_ATIVA=true`.

---

## 7. Como Reativar o Sistema (passo a passo)

1. **Renovar API-Football** em https://www.api-football.com (plano Pro, 7500 req/dia). Atualizar `API_FOOTBALL_KEY` no `.env`.
2. **Trocar segredos placeholder** se for produção:
   - `JWT_SECRET=$(openssl rand -hex 32)`
   - revisar `WAHA_DASHBOARD_PASSWORD` e `WAHA_API_KEY`.
3. **Subir Docker**:
   ```bash
   cd /home/daniel/cornerpressureelite
   docker compose up -d --build
   docker compose ps   # esperar todos UP
   ```
4. **Conectar WhatsApp** (apenas na primeira vez ou após logout):
   ```bash
   xdg-open "http://localhost:3000/dashboard"
   # login admin / Cpes2026@WhatsApp!Secure
   # escanear o QR Code com o WhatsApp do número operacional
   ```
5. **Verificar webhook registrado** (o startup do `cpes-api` faz isso, mas sanity check):
   ```bash
   curl -s http://localhost:3000/api/sessions/default \
     -H "X-Api-Key: $WAHA_API_KEY" | jq '.config.webhooks'
   ```
6. **Rodar ciclo de teste** mandando `/status` no WhatsApp do admin. Resposta deve voltar em 2-5s.
7. **Verificar dashboard** em `http://localhost:3001` (ou `https://odontoschultz.online` via Cloudflare Tunnel).
8. **Monitorar logs**: `docker logs -f cpes-main | grep ANALISE`.

Se algum passo falhar, ver `docs/changelog/2026-02-15-fix-waha-session-stopped.md` e `docs/changelog/2026-02-15-fix-whatsapp-webhook.md`.

---

## 8. Discrepâncias Encontradas (doc vs. código)

Entradas que **estão erradas em docs antigas** e foram corrigidas neste documento:

1. `docs/analises/sistema-funcionamento-completo.md` diz **SQLite** com path `data/cpes.db`. **Errado** — desde a refactor de fevereiro/2026 o banco é Postgres via `asyncpg` (`storage/database.py`). Os arquivos `cpes.db` na pasta `data/` são vestígios.
2. Mesma doc lista componentes do dashboard (`Header`, `MetricCard`, `RecentSignals`, `SystemLogs`, etc.) — esses componentes **foram deletados** na refatoração para `(authenticated)/...`. As páginas atuais são monolíticas e usam MUI direto.
3. Várias docs antigas dizem que o `MIN_SCORE_NORMAL=8` e `MIN_EDGE_NORMAL=1.3`. **Hoje no `config.py`**: `MIN_SCORE_NORMAL=6`, `MIN_EDGE_NORMAL=1.2`. Foi tunado.
4. `START_HERE.txt` na raiz e arquivos `WAHA_*.txt` legados descrevem versões antigas dos fluxos — não confiar.
5. O `docs/architecture/full-spec-v2-waha.md` traz a especificação inicial (canônica para entender intenção), mas os parâmetros, tabelas e thresholds reais são os deste documento + `config.py`.

---

## 9. Próximos Passos Recomendados

Curto prazo (para ter o sistema rodando confiavelmente):
- [ ] Renovar API-Football e validar fluxo end-to-end com 1 jogo.
- [ ] Trocar `JWT_SECRET` placeholder.
- [ ] Limpar arquivos legados na raiz (`WAHA_*.txt`, `START_HERE.txt`, scripts `test_*.py` órfãos) — ou mover para `docs/legacy/`.
- [ ] Apagar `data/cpes.db` e `data/cpes_backup_*.db` após confirmar que nenhum job ainda lê deles.

Médio prazo (qualidade):
- [ ] Cobertura de testes em `score_engine`, `decision_engine`, `cards_*` engines.
- [ ] Atualizar docs em `docs/analises/` que ainda dizem SQLite.
- [ ] Consolidar `docs/architecture/` em um doc único de arquitetura atual.
- [ ] Backtest precisa adaptar para Postgres (snapshots já existem na tabela).

Médio/longo prazo (produto):
- [ ] WebSockets/SSE para dashboard ao vivo (já há `/api/stream/dashboard` no `api_server.py`).
- [ ] Calibração automática de thresholds com base em histórico (ML leve).
- [ ] App mobile (React Native) ou PWA do dashboard.
- [ ] Backup/restore do banco e backups das sessões WAHA.

---

## 10. Apêndice — Endpoints da API (verificados em `api_server.py`)

```
GET  /                           # Health check
GET  /api/health
GET  /api/stats                  # Stats agregados
GET  /api/signals/recent         # Últimos sinais
GET  /api/status                 # Status do sistema (ciclo, rate limit)
GET  /api/logs
GET  /api/polling-stats
GET  /api/live-games
GET  /api/upcoming-games
GET  /api/config/leagues
POST /api/config/leagues
GET  /api/config/thresholds
POST /api/config/thresholds
GET  /api/audit                  # Funil + breakdown por filtro
GET  /api/dashboard              # Payload monolítico do dashboard
GET  /api/stream/dashboard       # SSE em tempo real
POST /api/auth/register
POST /api/auth/verify-email
POST /api/auth/resend-verification
POST /api/auth/login             # Retorna {access_token}
GET  /api/users/me
POST /api/subscriptions/checkout # Cria checkout Asaas
POST /api/webhook/asaas          # Webhook PAYMENT_RECEIVED, etc
POST /api/webhook/whatsapp       # Webhook WAHA Plus (PUSH)
```

---

## 11. Apêndice — Ligas Monitoradas

`config.LIGAS_MONITORADAS` em 2026-05-10:

| ID | Nome | País | Média esperada (escanteios) | Season |
|---|---|---|---|---|
| 39 | Premier League | England | 10.8 | 2025 |
| 78 | Bundesliga | Germany | 11.2 | 2025 |
| 135 | Serie A | Italy | 10.5 | 2025 |
| 140 | La Liga | Spain | 10.3 | 2025 |
| 88 | Eredivisie | Netherlands | 10.6 | 2025 |
| 94 | Liga Portugal | Portugal | 10.0 | 2025 |
| 71 | Brasileirão A | Brazil | 9.8 | 2026 |
| 72 | Brasileirão B | Brazil | 9.5 | 2026 |
| 128 | Liga Profesional | Argentina | 10.2 | 2026 |

A escolha do `season` por liga é crítica: ligas europeias estão em 2025 (calendário cruza ano civil), Brasil/Argentina em 2026.

---

**Fim do documento.** Releia este arquivo sempre que voltar a tocar no projeto.
