# Master — Descoberta Betano (REESCRITO pós-spike)

> **Atualizado em 2026-05-13** após análise completa do `.mitm` capturado em
> 2026-05-12. Substitui versão anterior que assumia Sportradar gismo como
> fonte primária — premissa **incorreta**, corrigida abaixo.

---

## 1. Resumo executivo

A Betano BR é um cliente **Kaizen Gaming**. Stack interno:

- **Stats (live):** **Opta**, via endpoints REST proprietários
  `/api/statsstream/{eventId}/*` + WebSocket SignalR
- **Mercados (odds):** dados próprios da Betano via REST
  `/danae-webapi/api/live/events/{eventId}/latest` + WebSocket SignalR
- **Sportradar gismo:** **não está em uso**. Token `availabletokens` retorna
  vazio. CDN externa nunca é chamada.
- **Mapping Sportradar opcional:** `event.betradarMatchId` vem inline no
  payload da Betano (free), mas não consumimos a gismo de qualquer forma.

**Pivot dentro do pivot:**

- Antes: provider Sportradar + provider Betano (dois clientes + token assinado).
- Agora: **provider único Betano** (REST + WS), tudo cookies-authenticated.

Resultado: arquitetura mais simples, menos pontos de falha, ~46h totais para
implementar todas as fases.

---

## 2. Endpoints REST descobertos (Betano-only)

### 2.1 Stats live — `/api/statsstream/{eventId}/...`

| Sub-endpoint | Retorna | Tamanho | Cache sugerido |
|---|---|---|---|
| `info/aggregated/?lang=pt_BR` | Match meta (times, liga, kaizen_match_id) + lineups | 5.2KB | até FT |
| `config/` | `provider_type` (Opta), `momentum_enabled`, disabled_tabs | 331B | até FT |
| `stats/detailed/` | Stats por time × half × 35 campos | 3.9KB | 15s |
| `stats/players/` | Stats por jogador | ~890B | 15-30s |
| `momentum/` | Array minuto×pressure score (calculado pela Opta) | 5KB | 30s |
| `lineups/` | Escalações + cartões + substituições | 10.5KB | 30s |
| `h2h/` | Head to head (jogos anteriores) | 16KB | 1h+ |

**Cookies necessários:** `cf_clearance`, `__cflb`, `_cfuvid`, `datadome`,
`sticky_sb`. **NÃO precisa de login** (`GAUTH` opcional).

**Headers obrigatórios:**
- `Referer: https://www.betano.bet.br/`
- `x-kbversion: 3.41.0` (extrair de `/api/kb-config/`)
- User-Agent realista (mobile iOS preferível)

### 2.2 Mercados completos — `/danae-webapi/api/live/events/{eventId}/latest`

**281KB** em uma resposta. Estrutura top-level:

```
{
  "version": 1554,
  "syncedAtUtc": 1778633731257,
  "sport": {"id":"FOOT","sportId":1,...},
  "zone": {"code":"brazil","id":10004,...},
  "league": {...},
  "event": {
    "id": 84586925,
    "marketIdList": [...279 ids...],
    "totalMarketsAvailable": 279,
    "statistics": {...},
    "liveData": {"score":{"home":"0","away":"0"}, "clock":{"secondsSinceStart":...}},
    "incidents": [...],
    "participants": [{"name":"Cruzeiro","isHome":true,"teamId":...},...],
    "betradarMatchId": 70401308,   ← matchId Sportradar inline (free)
    "isLive": true,
    "url": "/live/cruzeiro-goias/84586925/",
    "startTime": 1778632200000,
    ...
  },
  "markets": { "<marketId>": {market_object}, ... },     ← 279 entries
  "selections": { "<selectionId>": {selection_object}, ... }  ← 1153 entries
}
```

### 2.3 Lista de eventos do dia — `/danae-webapi/api/live/overview/latest`

```
{
  "events": { "<eventId>": {event_object_short}, ... },   ← 96 eventos
  "leagues": {...},
  "zones": {...},
  "sports": {...},
  "markets": {...},
  "selections": {...}
}
```

Usado para **fuzzy match** `fixture_id (API-Football) → event_id (Betano)`.
Cada evento tem `participants[].name`, `startTime`, `leagueId`, `sportId`,
`isLive`. Match por (nome normalizado, kickoff ±10min, leagueId).

### 2.4 Mapping eventId → matchId Sportradar (não essencial)

```
GET /api/liveevent/statsplayer?id=84586925
→ {"data":{"statPlayerModels":[
    {"statType": 7},
    {"matchId":"70401308", "stageId":"70401308", "statType":4},  // Sportradar
    {"matchId":"55n9jqpc9lsi0nxt4zpw29ez8", "statType":6}        // Opta
  ]}}
```

Mas `betradarMatchId` (na seção 2.2) já entrega isso inline. Esse endpoint
fica como fallback/duplo-check.

---

## 3. Mercados de odds — catálogo confirmado via .mitm

### 3.1 Escanteios — Total Mais/Menos (`CNOU`, typeId 34)

Uma entry por linha. Para Cruzeiro × Goiás capturamos linhas
**8.5, 9.5, 10.5, 11.5, 12.5**. Estrutura:

```json
"2755039772": {
  "type": "CNOU",
  "typeId": 34,
  "handicap": 9.5,         ← LINHA
  "name": "Escanteios Mais/Menos",
  "selectionIdList": [9583302702, 9583302703]
}
```

Selections (price = odd):
```json
"9583302702": {"price": 1.85, "name": "Mais", "fullName": "Mais de 9.5"}
"9583302703": {"price": 1.95, "name": "Menos", "fullName": "Menos de 9.5"}
```

### 3.2 Cartões — Total Mais/Menos (`TCOU`, typeId 65)

```json
"2756504499": {
  "type": "TCOU",
  "typeId": 65,
  "handicap": 5.5,
  "name": "Total de Cartões Mais/Menos",
  "selectionIdList": [9589204012, 9589204013]
}
```

### 3.3 Outros codes confirmados para escanteios e cartões

| Code | typeId | Nome | Uso |
|---|---|---|---|
| `CNOU` | 34 | Escanteios Mais/Menos | **Principal escanteios** |
| `NCNT` | 32 | Próxima equipe a cobrar escanteio | Side market |
| `TCOU` | 65 | Total de Cartões Mais/Menos | **Principal cartões** |
| `RCOU` | 49 | Total de Cartões Vermelhos | Side market |
| `HRED` | 51 | Casa Cartão vermelho | Side market |
| `ARED` | 52 | Fora Cartão vermelho | Side market |
| `1RED` | 53 | Cartão vermelho 1° tempo | Side market |
| `PTRC` | 62 | Receber um cartão (por jogador) | Mercado especial |
| `4022` | 4022 | Corrida até X Cartões | Side market |

**Regra principal:** filtrar markets por `type in ("CNOU","TCOU")` e
`handicap == linha_desejada`.

---

## 4. WebSockets — SignalR Core (3 hubs)

3 conexões WS distintas, todas SignalR Core moderno. Protocolo conhecido.

### 4.1 `/contenthub?platformType=1` — push de odds + score

Handshake cliente: `{"protocol":"json","version":1}\x1e`

Subscribe:
```json
{"arguments":[{"language":5,"platformType":1,"includeVirtuals":true}],
 "invocationId":"0","target":"joinLiveOverviewGroupWithOptions","type":1}\x1e
```

Push do servidor (tipo 1, target=`NewLiveOverviewDiffs`):

```json
{"type":1,"target":"NewLiveOverviewDiffs","arguments":["BCJNGEBAwFcHAAD..."]}
```

**O argumento é payload binário+JSON intercalado** (formato proprietário
Kaizen). Header binário 4-6 bytes, depois JSON UTF-8 com diffs. Marcadores de
bloco em `\x00\xa5..\xf1`.

**Estratégia recomendada para o cliente:** **não parsear o payload custom**.
Usar o WS apenas como **gatilho** (sinal "evento X mudou") e re-puxar
`/danae-webapi/api/live/events/{eventId}/latest` (REST) quando relevante.
Mais simples, igualmente eficaz.

### 4.2 `/sbpitches/statsstream/matchhub` — push de eventos Opta

Cliente subscribe:
```json
{"arguments":["84586925"],"invocationId":"0","target":"Subscribe","type":1}\x1e
```

Push do servidor (tipo 1, target=`MatchEvent`):

```json
{
  "event_data": {
    "ball_position": {"x":67.2,"y":12.4},
    "ball_position_end": {"x":65.7,"y":39.1},
    "team_id": "bd6vujl7jfv4wtc8gvo1o1t5y",
    "player_id": "19154029",
    "is_possession": false,
    "is_attack": true,
    "is_dangerous_attack": false
  },
  "event_match_id": "55n9jqpc9lsi0nxt4zpw29ez8",
  "sportsbook_match_id": "84586925",
  "event_provider_id": "",
  "event_type": 0,
  "event_period_id": 2,
  "event_match_minute": 24,
  "event_match_second": 29,
  "event_provider_type": "Opta"
}
```

**Granularidade de scouting profissional** — cada toque relevante com X/Y na
escala 0-100, player_id, flags `is_attack`/`is_dangerous_attack`. Fonte
principal de pressão em tempo real, latência <2s.

### 4.3 `/customerhub_2` — user state (não primário)

Notifications de saldo, depósitos, missões. Não usado pelo produto.

### 4.4 SignalR Classic `/signalr/connect` (não primário)

Hub `sportsbookhub.subscribeliveVisualizationsInfo` — dados pro widget de
quadra animada. Ignorar.

---

## 5. Cookies do warmup (ordem cronológica confirmada)

```
 1. _cfuvid                       ← GET / (Cloudflare anonymizer)
 2. sticky_sb                     ← GET /api/home/top-events-v2/ (LB sticky)
 3. cf_clearance                  ← POST /cdn-cgi/challenge-platform/...
 4. datadome                      ← GET /myaccount/login
 5. FPGSID                        ← Google Analytics
 6. _fbp                          ← Facebook Pixel
 7. kz_trusted_device_<accountId> ← POST /myaccount/login (login completou)
 8. pocaauth                      ← idem
 9. PrefferedLoginType            ← idem
10. GAUTH                         ← GET /api/balance
11. cntps_id                      ← GET /signalr/negotiate
12. __cflb                        ← idem
```

**Para leitura anônima** (que é o que o produto faz), bastam cookies 1-5.
Login (passos 7-10) **opcional** — não usar reduz superfície de detecção.

---

## 6. Stack de anti-bot — observado em ação

| Camada | Vendor | Manifestação no flow |
|---|---|---|
| **Cloudflare** | CF | `cf_clearance` via challenge JS; `__cflb`, `_cfuvid` |
| **DataDome** | DataDome | Cookie `datadome`; calls em `obseu.tostarsbuilding.com/mon` (~30/sessão) |
| **ThreatMetrix** | LexisNexis | Não observado nesta sessão (provavelmente só em place_bet) |
| **GeoComply** | GeoComply | `cdn.geocomply.com`, `br1-es.geocomply.com` |

Mesma stack esperada. Mantém recomendação de warmup browser + cookies +
proxy residencial BR em produção.

---

## 7. Arquitetura revisada

```
data/providers/betano/
├── __init__.py
├── session.py          ← warmup Cloudflare+DataDome+cookies; HTTP wrapper
├── statsstream.py      ← REST /api/statsstream/{id}/*  (stats Opta)
├── markets.py          ← REST /danae-webapi/api/live/events/{id}/latest
├── catalog.py          ← REST /danae-webapi/api/live/overview/latest (fuzzy)
├── wsclient.py         ← SignalR Core: contenthub + matchhub
├── parsers.py          ← Parsers JSON → schemas
├── schemas.py          ← Dataclasses: BetanoMarket, OptaStats, MatchEvent
└── codes.py            ← Mapeamento de market codes → constantes
```

**Não criamos** `data/providers/sportradar/` agora. Fica para enrichment
futuro se quisermos cruzar com Sportradar gismo via token de outro operador
(complexidade extra sem ganho claro — Opta já entrega o necessário).

---

## 8. Cadências propostas

| Camada | Cadência | Rationale |
|---|---|---|
| `statsstream/stats/detailed/` | 15s polling | Stats principais |
| `statsstream/momentum/` | 30s polling | Pressure Opta |
| `statsstream/info/aggregated/` | 1x por jogo + on goal | Mata + lineups |
| `danae-webapi/.../events/{id}/latest` | **On-demand: só quando `score >= MIN`** | 281KB cada |
| `danae-webapi/.../overview/latest` | 1x/min | Lista global |
| WS `/contenthub` | 1 conexão persistente | Gatilho de mudanças |
| WS `/matchhub` | 1 conexão por jogo ativo | Eventos Opta granulares |

**Footprint Betano estimado** (30 jogos ao vivo simultâneos): ~200 reqs/dia
(REST) + 30 WS conexões persistentes. Dentro do floor confortável.

---

## 9. Política de fallback

```python
stats_provider = CompositeStatsProvider([
    BetanoStatsProvider(...),       # primary (Opta)
    APIFootballStatsProvider(...),  # fallback
])

odds_provider = CompositeOddsProvider([
    BetanoOddsProvider(..., min_score=MIN_SCORE_TO_FETCH_ODDS),
    APIFootballOddsProvider(...),
])
```

Composite cai para próximo em falha (None ou exception). Caller nunca recebe
exception. Princípio CLAUDE.md: try/except só em fronteiras.

---

## 10. Persistência (Fase D)

3 tabelas, idempotentes:

```sql
CREATE TABLE betano_fixture_map (
  fixture_id        INT PRIMARY KEY,
  betano_event_id   BIGINT UNIQUE NOT NULL,
  sr_match_id       TEXT,          -- de event.betradarMatchId
  opta_match_id     TEXT,
  home_team         TEXT,
  away_team         TEXT,
  resolved_at       TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE odds_history (
  id            BIGSERIAL PRIMARY KEY,
  fixture_id    INT NOT NULL,
  source        TEXT NOT NULL,
  market_kind   TEXT NOT NULL,
  market_code   TEXT,
  linha         NUMERIC(5,2),
  odd_over      NUMERIC(6,2),
  odd_under     NUMERIC(6,2),
  minute        INT,
  pressure_score   NUMERIC(5,2),
  tension_score    NUMERIC(5,2),
  captured_at   TIMESTAMPTZ DEFAULT NOW(),
  raw           JSONB
);

CREATE TABLE incidents_history (
  id              BIGSERIAL PRIMARY KEY,
  fixture_id      INT NOT NULL,
  opta_match_id   TEXT NOT NULL,
  event_uid       TEXT NOT NULL,
  event_type      INT NOT NULL,
  team_id         TEXT,
  player_id       TEXT,
  minute           INT,
  seconds         INT,
  period_id       INT,
  x               REAL,
  y               REAL,
  x_end           REAL,
  y_end           REAL,
  is_attack       BOOLEAN,
  is_dangerous_attack BOOLEAN,
  is_possession   BOOLEAN,
  raw             JSONB,
  UNIQUE (opta_match_id, event_uid)
);
```

---

## 11. Fases revisadas

| Fase | Foco | Duração | Doc |
|---|---|---|---|
| ~~Spike mitmproxy~~ | ✅ Concluído | — | `2026-05-12-betano-spike-mitmproxy.md` |
| **A** — Betano StatsStream Provider | REST `statsstream/*`, schemas, parsers, testes | ~10h | `2026-05-12-betano-fase-A-statsstream-provider.md` |
| **B** — Betano Markets & WS Provider | REST `danae-webapi/*` + WS SignalR + warmup browser | ~16h | `2026-05-12-betano-fase-B-markets-ws-provider.md` |
| **C** — Pipeline refactor | Composite + trigger condicional + feature flag | ~10h | `2026-05-12-betano-fase-C-pipeline-refactor.md` |
| **D** — Persistência | 3 tabelas + workers + queries | ~10h | `2026-05-12-betano-fase-D-persistencia-historica.md` |

**Total revisto: ~46h.**

---

## 12. Decisões pendentes

1. **Captura de cookies via Playwright vs replay de cookies congelados** —
   recomendação: Playwright só pra refresh (1x a cada 12h ou após 403).

2. **WebSocket: 1 conexão única vs pool por evento** —
   recomendação: 1 WS contenthub global + 1 WS matchhub por evento monitorado
   (até N=20 simultâneos).

3. **Parser do NewLiveOverviewDiffs** — recomendação: **não parsear**, usar
   apenas como gatilho.

4. **Login da Betano** — recomendação: **não logar** em produção. Cookies
   anônimos (passos 1-5) bastam.

5. **Sportradar gismo no futuro?** — não bloqueia nada. Pode reentrar como
   "Fase E" se houver demanda por enrichment cruzado.

---

## 13. Mudanças que vale destacar

### 13.1 `get_live_odds_cards` da API-Football era impreciso
`api_client.py:574` **não** faz multi-bookmaker (linha 606 hardcode
`bookmaker="1"`). Quando BetanoOdds entrar, ganho relativo em **cartões será
maior** que em escanteios.

### 13.2 `kb-config` documenta cadências oficiais
```
liveOverviewSettings.fallbackPollIntervalMillis: 5000
liveEventSettings.fallbackPollIntervalMillis: 6000
```

### 13.3 `betradarMatchId` já vem inline
Não precisamos chamar `statsplayer` para mapping. Reduz 1 chamada por evento.

### 13.4 Opta dá pressure score pronto
`/api/statsstream/{id}/momentum/` tem `pressure` por minuto. Comparar com
`pressure_score` do CPES = sanity check + feature pro `quality_model.py`
futuro.

---

## 14. Links cruzados

- `docs/sprints/2026-05-12-betano-spike-mitmproxy.md` (concluído)
- `docs/sprints/2026-05-12-betano-fase-A-statsstream-provider.md`
- `docs/sprints/2026-05-12-betano-fase-B-markets-ws-provider.md`
- `docs/sprints/2026-05-12-betano-fase-C-pipeline-refactor.md`
- `docs/sprints/2026-05-12-betano-fase-D-persistencia-historica.md`
- `CLAUDE.md` (princípios de coding)
- `docs/architecture/sistema-completo.md` (antigo — superado por este doc)
