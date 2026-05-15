# Betano Danae Web API — Mapeamento

> Base URL: `https://www.betano.bet.br`
>
> **Não documentado oficialmente** — descoberto via captura mitmproxy 2026-05-15. Schema pode mudar sem aviso.

## 1. Auth

A API aceita requests HTTP simples desde que o cliente apresente um cookie `_cfuvid` válido (Cloudflare bypass token). **Sem Bearer / sem CSRF / sem API key custom.**

Headers mínimos confirmados (capturados de browser real):

```http
GET /danae-webapi/api/live/overview/latest?... HTTP/1.1
Host: www.betano.bet.br
User-Agent: Mozilla/5.0 (X11; Linux x86_64; rv:150.0) Gecko/20100101 Firefox/150.0
Accept: */*
Accept-Language: en-US,en;q=0.9
Accept-Encoding: gzip, deflate, br, zstd
Referer: https://www.betano.bet.br/
Cookie: _cfuvid=<token>
Sec-Fetch-Dest: empty
Sec-Fetch-Mode: cors
Sec-Fetch-Site: same-origin
```

**Como obter `_cfuvid`:** abrir `https://www.betano.bet.br/` num navegador real (ou Chrome via Playwright) e ler o cookie do contexto. TTL desconhecido, mas observado `>30min`. Renovação periódica via Chrome aquecido é a estratégia recomendada.

## 2. Endpoints descobertos

### 2.1 `/danae-webapi/api/live/overview/latest` ⭐

Lista TODOS os eventos AO VIVO no momento, em todos os esportes.

**Query params:**

| Param | Valor observado | Notas |
|---|---|---|
| `includeVirtuals` | `true` ou `false` | Inclui esports/virtuais |
| `queryLanguageId` | `5` | Português brasileiro |
| `queryOperatorId` | `8` | Operador Brasil |

**Response:** ~900 KB JSON (gzip/zstd reduz pra ~150 KB), `application/json; charset=utf-8`.

**Schema (top-level):**

```json
{
  "events":      {<event_id>: <Event>},        // 301 chaves no snapshot
  "leagues":     {<league_id>: <League>},      // 110 chaves
  "zones":       {<zone_id>: <Zone>},          // 76 chaves (países/regiões)
  "sports":      {byId: {...}, allIds: [...], byIdLeagueIdList: {...}},
  "markets":     {<market_id>: <Market>},      // 954 chaves
  "selections":  {<sel_id>: <Selection>},      // 3111 chaves
  "version":             261350001181792,       // increment a cada update
  "contentVersion":      261350000385670,
  "availabilitiesVersion": 77178
}
```

**Event:**

```json
{
  "id": 85762410,
  "zoneId": 189315,
  "leagueId": 200420,
  "sportId": "GOLF",                          // FOOT|TENN|BASK|VOLL|HAND|...
  "ardSportId": 40,
  "marketIdList": [2762201542],
  "version": 32,
  "contentVersion": 1,
  "name": "Round 2 Chris Kirk / Max Greyserman / Kristoffer Reitan",
  "totalMarketsAvailable": 5,
  "url": "/live/round-2-chris-kirk-max-greyserman-kristoffer-reitan/85762410/",
  "participants": [],                          // vazio em outrights; preenchido em jogos times-vs-times
  "isOutrightEvent": true,
  "willGoLive": true,
  "startTime": 1778866680000,                  // ms unix
  "displayOrder": 0
}
```

**League / Zone / Sport:**

```json
// leagues[<id>]
{"id": 215, "name": "Ligue 1", "eventIdList": [85656558], "displayOrder": 660}

// zones[<id>]
{"id": 10004, "name": "Brasil", "leagueIdList": [198998], "code": "brazil", "displayOrder": -59350}

// sports.byId[<sport_code>]
{"id": "FOOT", "sportId": 1, "name": "Futebol", "zoneIdList": [10004, 1, 2, ...], "displayOrder": 1}
```

**Distribuição típica (snapshot 18:30 BRT):** 109 Futebol, 75 Golfe, 27 T. Mesa, 26 Basquete, 20 Tênis, 30 outros. Total 301 ao vivo.

### 2.2 `/api/home/upcoming-coupons`

Eventos AGENDADOS organizados por esporte e dia.

**Query params:**

| Param | Valor observado |
|---|---|
| `req` | `s,stnf,c,mb,mbl` (campos a incluir) |

**Schema:**

```json
{
  "data": {
    "coupons": [
      {
        "id": "FOOT",
        "name": "Futebol",
        "type": "sport",
        "url": "/upcomingcoupon/?sid=FOOT",
        "headers": [...],                       // config UI de markets/columns
        "layout": 2,
        "subNavItems": [                        // 1 entry por DIA
          {
            "id": "Friday",
            "name": "sexta-feira, 15/05",
            "type": "date",
            "url": "/upcomingcoupon/?sid=FOOT&day=Friday",
            "totalEvents": 105,
            "events": [
              {
                "id": "83582089",
                "name": "Waterford FC - Derry City",
                "shortName": "Waterford FC - Derry City",
                "sportId": "FOOT",
                "leagueId": "17041",
                "leagueName": "Primeira divisão",
                "leagueDescription": "Primeira divisão",
                "regionId": "11367",
                "regionName": "Irlanda",
                "betRadarId": 66854052,           // ⭐ Sportradar ID — bridge p/ outras fontes
                "startTime": 1778870700000,
                "url": "/odds/waterford-fc-derry-city/83582089/",
                "matchComboUrl": "/odds/.../criar-aposta/83582089/",
                "totalMarketsAvailable": 167,
                "hasOptaStats": true,
                "hasLineupsAvailability": true,
                "willGoLive": true,
                "streamingAvailable": true,
                "tvChannel": "",
                "stats": [
                  {"url": "https://s5.sir.sportradar.com/betano/br/match/66854052", "providerId": 1}
                ],
                "markets": [...]                  // alguns markets pré-jogo
              }
            ]
          }
        ]
      },
      // ... outros esportes
    ]
  }
}
```

**Achado importante:** `betRadarId` (ID do Sportradar) está disponível por evento. Isso pode ser usado em D.2 pra fuzzy match com fontes externas (Sportradar é fornecedor global; muitas APIs de futebol expõem mapping).

### 2.3 `/api/home/top-events-v2/`

Top eventos da home (popular). Retorna 50 IDs por chamada (UI mostra 10 paginando client-side).

```json
{
  "data": {
    "topEventsV2": {
      "eventIdList": [50 IDs],
      "events": {25 keys},     // Subset com detalhes
      "leagues": {27 keys},
      "markets": {175 keys},
      "selections": {400 keys},
      ...
    }
  }
}
```

### 2.4 `/danae-webapi/api/live/events/{event_id}/latest`

Estado completo de UM evento (~134 KB). Provavelmente substitui o que `/markets` do bridge faz hoje via Playwright, mas como JSON nativo. Pra investigar em D.0+.

### 2.5 `/api/statsstream/{event_id}/info/aggregated/`

**Estatísticas agregadas do evento (Opta-backed)**. Phase E (Stats adapter) pode usar isso.

### 2.6 `/api/static-content/assets/leagues` e `/api/static-content/assets/teams`

Catálogo estático de **todas** ligas (200 KB) e **todos** times (8.8 MB). Útil pra:
- D.2 fuzzy match (resolver league/team Betano ↔ API-Football)
- Cache local com TTL longo (atualiza 1× por dia)

### 2.7 Sync delta

`/danae-webapi/api/live/overview/{version}` e `/danae-webapi/api/live/overview/sync/{event_id}` — provavelmente usados pelo SignalR pra updates incrementais a partir de uma versão. Não inspecionado a fundo.

## 3. SignalR (suspeita confirmada, não capturada)

A página live carrega:
- `HubConnectionBuilder.CBkYTUOq.js`
- `signalr-hub-connection.service.DDDyAlkx.js`
- `DanaeHubConnectionContainer.CUPSIzbd.js`
- `LiveOverviewDanaeSubscriptionsContainer.BDU2Bp8V.js`

A captura mitm não pegou WebSocket frames (tipo `websocket` aparece como 0 no .mitm — provavelmente porque mitmweb default não captura WS sem flag explícita). Pra atualizar o overview em tempo real, a página subscribe via SignalR; pra polling simples, basta refazer `/danae-webapi/api/live/overview/latest` periodicamente (response inclui `version` pra detectar mudança).

## 4. Implicações pra arquitetura do bridge

Hoje o bridge usa Playwright via CDP pra abrir `/live/_/<id>/` e regex no `body.innerText`. Latência típica 8s/captura.

Com a Danae API:
- **Listagem** (D.1): HTTP request direta, latência ~150ms
- **Estado de evento individual** (D.0): pode evoluir de Playwright pra HTTP request via 2.4 — testar se cobre todos os mercados que a página renderiza
- **Catálogos** (D.2): cache de leagues/teams atualizado 1×/dia
- **Stats** (Phase E): novo endpoint de stats nativo

**Chrome continua necessário só pra:**
1. Renovar `_cfuvid` cookie periodicamente (warmup loop ~30min)
2. Casos onde JSON não cobre (mercados específicos, ainda a investigar)

## 5. Riscos

| Risco | Mitigação |
|---|---|
| Cookie `_cfuvid` expira | Warmup loop com Chrome aquecido (compartilhar cookie via context) |
| Endpoint não documentado pode mudar | Versionado por `?queryLanguageId=5` e `version` no response — alertar quando schema diverge |
| Rate limit desconhecido | Começar com polling 60s (1× por minuto). Medir headers `X-RateLimit-*` se aparecer. Backoff exponencial em 429 |
| Cloudflare WAF pode flagar IP em volume | Já vimos hoje — IP residencial flagado após ~10 requests automatizadas. Manter polling baixo + reusar cookie do Chrome |
| Múltiplos cookies necessários (não só `_cfuvid`)? | Header capturado mostra só `_cfuvid` enviado, mas browser tem outros (`cf_clearance`, `_cq_*`). Em produção, enviar TODOS os cookies do Chrome warmup |

## 6. Captura de referência

- Arquivo: `/home/daniel/cornerpressureelite/betano-capture-20260515-152323.mitm` (22 MB)
- Capturado em: 2026-05-15 15:23 BRT, mitmweb no PC do daniel (não-flagueado)
- Total: 1134 flows (672 betano-related)
