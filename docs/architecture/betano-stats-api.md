# Betano Live Stats API — Mapeamento (Fase E.0)

> **Investigação:** 2026-05-16, sobre captura mitmproxy `betano-capture-20260515-152323.mitm` (PC do daniel, não-flagueado). 1134 flows, 4 jogos cobertos (Saudi League, Austria 2, etc.). Schema pode mudar sem aviso.
>
> **Continuação direta de** [`betano-danae-api.md`](betano-danae-api.md) — usa exatamente a mesma camada de auth/transport (cookie `_cfuvid`, pipeline Brave + danewell renewer).

## 1. Endpoint principal — `/danae-webapi/api/live/events/{event_id}/latest`

`GET https://www.betano.bet.br/danae-webapi/api/live/events/{event_id}/latest`

**Response:** ~134 KB JSON, `application/json; charset=utf-8`, encoding `zstd` (negociado via `accept-encoding`).

**Headers mínimos (capturados do Firefox real):**

```http
GET /danae-webapi/api/live/events/84220231/latest HTTP/1.1
Host: www.betano.bet.br
Accept: application/json, text/plain, */*
Accept-Language: en-US,en;q=0.9
Accept-Encoding: gzip, deflate, br, zstd
Referer: https://www.betano.bet.br/live/<slug>/<event_id>/
User-Agent: Mozilla/5.0 (X11; Linux x86_64; rv:150.0) Gecko/20100101 Firefox/150.0
Cookie: _cfuvid=<token>
Sec-Fetch-Dest: empty
Sec-Fetch-Mode: cors
Sec-Fetch-Site: same-origin
```

Auth: **só `_cfuvid`** (Cloudflare bypass). Sem Bearer, sem CSRF. Mesma estratégia do `/overview/latest`.

### 1.1 Schema top-level

```json
{
  "version": 1367,
  "versionsPerAudience": {"7": ..., "1": ..., "4": ..., "2": ..., "8": ...},
  "syncedAtUtc": 1778869885511,
  "sport":   {"id":"FOOT", "sportId":1, "name":"Futebol", ...},
  "zone":    {"id":11462, "name":"Arábia Saudita", "code":"saudi-arabia", ...},
  "league":  {"id":17766, "name":"Saudi League", ...},
  "event":   { /* 27 keys — ver §1.2 */ },
  "markets": { /* 132 entries — odds */ },
  "selections": { /* 502 entries — seleções */ }
}
```

### 1.2 `event` — keys relevantes

| Key | Tipo | Notas |
|---|---|---|
| `id` | int | sportsbook event_id (mesmo da URL e da Danae overview) |
| `betradarMatchId` | int | ⭐ Sportradar ID — bridge p/ outras fontes |
| `startTime` | int | ms unix |
| `isLive` / `willGoLive` | bool | |
| `participants` | list | `[{name, isHome, color, teamId}]` |
| `liveData` | dict | **score + clock + results agregados** — §1.3 |
| `incidents` | list | **timeline event-by-event** — §1.4 |
| `incidentFilters` | list | `[{id, tag, name}]` — IDs de filtro: 5=All, 10=Goals, 15=Corners, 20=YellowCards |
| `statistics` | dict | `{event, teams, players}` com stat IDs **numéricos opacos** — não usar (§5.1) |
| `roster` | dict | `{homeRoster, awayRoster, unknownPlayers, lineups}` — lineups básicos |
| `marketIdList` | list | IDs dos 132 markets pra cross-ref com `markets.*` |
| `url` | str | `/live/<slug>/<id>/` (slug derivável) |
| `chatChannelId` | str | UI only |
| `isPitchAvailable` / `isPrettyTechStatsAvailable` | bool | flags de cobertura |

### 1.3 `event.liveData` — fonte primária de stats ⭐

Estruturado e auto-explicativo. Exemplo (Saudi League, full coverage):

```json
{
  "score":   {"home": "0", "away": "0"},
  "clock":   {"secondsSinceStart": 1869},
  "results": {
    "corners":  {"home": "3", "away": "0"},
    "shots":    {"home": "7", "away": "4"},
    "xGoals":   {"home": "0.38", "away": "0.13"},
    "yellow":   {"home": "1", "away": "0"},
    "penalties":{"home": "0", "away": "1"},
    "sportId":  1
  }
}
```

**Cobertura varia por liga.** `results.*` adiciona keys conforme a fonte fornece. Amostras da captura:

| event_id | liga | results.keys |
|---|---|---|
| 84220231 | Saudi League | corners, xGoals, shots, sportId |
| 84389045 | Austria Regio | yellow, corners, sportId |
| 85020565 | (jogo cedo) | corners, sportId |
| 85449666 | OFB Cup | penalties, yellow, corners, sportId |

Coverage level vem no `/api/statsstream/<id>/info/aggregated/` (`match.coverage_level`, ex `"13"` para Saudi).

**Granularidade temporal:** snapshot. `version` top-level incrementa a cada update. Polling 60s + comparar version → detecta mudança sem reparsing total.

### 1.4 `event.incidents` — timeline event-by-event

Lista cronológica de eventos da partida. 11 tipos vistos na captura (88 incidents totais):

| Type | Count | Significado | Campos extras |
|---|---|---|---|
| `Aggregated` | 26 | Janela de 10min com totais ("5 Laterais, 1 Tiro livre, 2 Tiros de meta") | `props.timeRange` |
| `OFFS` | 16 | Impedimento | `teamSide`, `props.minute` |
| `CRNR` | 15 | Escanteio | `teamSide`, `props.minute`, `description="Nº Escanteio: Time"` |
| `SUBS` | 11 | Substituição | `teamSide`, `props.minute` |
| `GOAL` | 5 | Gol | `teamSide`, `props.{scoreHome, scoreAway, minute, description}` (`"com Chute"`, `"com Cabeça"`, `"com Penálti"`) |
| `EBEG` | 4 | Início de partida | — |
| `PEND` | 3 | Fim de tempo | — |
| `PBEG` | 3 | Início de tempo | — |
| `StoppageTime` | 2 | Acréscimos | `props.{injuryMinutes, overtimeMinute}` |
| `YELL` | 2 | Cartão amarelo | `teamSide`, `props.minute`, `props.overtimeMinute` (opt) |
| `PENL` | 1 | Pênalti marcado (não gol) | `teamSide`, `props.minute` |

**Não vistos na captura mas prováveis:** `RCRD` (cartão vermelho), `VAR`, `SHTG/SHTNG` (chutes no gol), etc. Confirmar quando aparecerem em jogo ao vivo.

**`teamSide`:** `0` = home, `1` = away.

**`time`:** string formato `"M'"` ou `"M'+N'"` (acréscimo). `props.minute` é int redundante.

**`filterIds`:** liga ao `incidentFilters`. Filtro `15` = corners → cliente UI usa pra filtrar a timeline por tipo.

Schema exemplo (GOAL):

```json
{
  "description": "1-3 ASK Voitsberg (com Penálti)",
  "time": "50'",
  "type": "GOAL",
  "teamSide": 1,
  "props": {
    "scoreHome": 1, "scoreAway": 3,
    "title": "Gol",
    "description": "ASK Voitsberg (com Penálti)",
    "minute": 50,
    "filterIds": [5, 10]
  }
}
```

## 2. Endpoints complementares

### 2.1 `/api/statsstream/{event_id}/info/aggregated/?lang=pt_BR`

**Response:** 4-5 KB JSON. **NÃO contém stats agregadas** apesar do nome enganador — contém apenas:

- `data.match.*` — metadata (sportsbook_id, home/away_team/color, kaizen IDs, `coverage_level`)
- `data.lineups.{home,away}.{on_pitch, substitutes}` — lineups completas com player IDs e nomes

Útil somente pra: (a) lineups detalhadas (não vêm no `/latest`), (b) confirmar `coverage_level` da partida.

### 2.2 `/api/liveevent/statsplayer?id={event_id}`

**Response:** 100-130 b. Meta-endpoint que retorna `availableStatTypes` (lista de stat types disponíveis no jogo). Sem dicionário decodificável. Provavelmente UI usa pra decidir quais widgets renderizar.

```json
{
  "data": {
    "statPlayerModels": [
      {"statType": 7},
      {"matchId": "64055881", "stageId": "64055881", "statType": 4}
    ],
    "availableStatTypes": [7, 4]
  }
}
```

Ignorar — não agrega valor sobre o `/latest`.

### 2.3 Sync delta — `/danae-webapi/api/live/events/{event_id}/?isInit=false&version={N}`

Mesma URL do `/latest` mas com query `?isInit=false&version=<int>`. **Tamanho ≈ mesmo do latest (~134 KB)** na captura — não parece ser delta verdadeiro, é full state. Provavelmente cliente compara `version` retornado para decidir re-render. Pra polling simples, usar `/latest` direto.

### 2.4 WebSocket `wss://www.betano.bet.br/sbpitches/statsstream/matchhub`

Confirmado no upgrade HTTP→WS (status 101, `sec-fetch-mode: websocket`). mitmweb default **não captura frames WS** — investigação separada (Fase E.2) se polling 60s for insuficiente.

Provavelmente SignalR (mesmo padrão da home — vimos `SignalR-Hub-Connection.js` em §3 do doc Danae). Cookie único `_cfuvid` (31 cookies enviados no upgrade).

## 3. Cobertura comparativa vs API-Football (Opta)

| Métrica | Betano `liveData.results` | API-Football | Notas |
|---|---|---|---|
| Score | ✅ string | ✅ int | Equivalente |
| Tempo (segundos) | ✅ `clock.secondsSinceStart` | ⚠️ minuto only | Betano mais granular |
| Corners | ✅ home/away | ✅ home/away | Equivalente |
| Yellow cards | ✅ home/away | ✅ home/away | Equivalente |
| Red cards | ❌ no liveData (via `incidents`) | ✅ | AF mais direto |
| Shots | ✅ home/away | ✅ home/away | Equivalente |
| Shots on target | ❌ | ✅ | **AF tem, Betano não no liveData** |
| Possession % | ❌ | ✅ | **AF tem, Betano não** |
| Fouls | ❌ | ✅ | Aparece em `incidents` agregado |
| Offsides | ❌ no liveData (via `incidents`) | ✅ | Betano via timeline |
| xG | ✅ home/away | ❌ | ⭐ **Betano tem, AF não** |
| Penalties (count) | ✅ | ⚠️ via events | Betano explicita |
| Goals timeline | ✅ rica (`com Chute/Cabeça/Penálti`) | ✅ | Equivalente |
| Substituições timeline | ✅ | ✅ | Equivalente |
| Lineups | ✅ (via `/statsstream/.../aggregated/`) | ✅ | Equivalente |

**Gaps Betano vs AF:** shots on target, possession %, fouls agregados (só timeline).
**Ganhos Betano:** xG live, clock em segundos.

**Veredito pro pipeline atual:** cobre **todas** as métricas usadas hoje pelo `score_engine` e `cards_score_engine` (corners + cards + clock + score). xG é bonus pra evolução de modelo.

## 4. Decisão arquitetural

**CASO α — API JSON disponível** (ver `DECISIONS.md` para ADR completo).

Reusa **exatamente** a infraestrutura D.1 já em produção: Brave do pool (danewell:9224) com cookie `_cfuvid` aquecido, renewer fazendo `fetch()` via CDP raw. Adapter novo só precisa adicionar rota no bridge da odin (ex: `/event/<id>/state`) que proxia o `/danae-webapi/api/live/events/<id>/latest` e devolve JSON normalizado.

**Estimativa Fase E.1:** ~6-10h (infra pronta) — não as 10-14h originalmente estimadas.

## 5. Limitações reconhecidas

### 5.1 `event.statistics` é opaco

Mapa de stat IDs numéricos (`{"239": "4", "261": "4", "259": "3 - 1", ...}`). Sem dicionário public. Provável dicionário em algum chunk JS (`PreEventOptaStats.*.js`, `LineupsCardBody.*.js`) — pode ser decodificado em sessão futura se precisar dos IDs. Pra E.1, **usar `liveData.results`** que já está estruturado e cobre o essencial.

### 5.2 Cobertura varia por liga

`liveData.results` adiciona keys conforme fonte fornece. Brasileirão/Saudi têm `coverage_level=13` (full); ligas menores podem só ter `corners`. Em produção, normalizador deve tratar keys ausentes como `0` ou `None` (consistente com como `score_engine` já lida com `escanteios_total=0`).

### 5.3 Variabilidade do campo `name`

Igual à observação em [`betano-danae-api.md §4.4`](betano-danae-api.md#44-o-field-name--atenção) — `event.name` pode não vir; reconstruir via `participants[]` + `isHome`. Já implementado no renewer.

### 5.4 Sem investigação WebSocket

Push em tempo real via `/sbpitches/statsstream/matchhub` não capturado. Se polling 60s no `/latest` ficar lento pra decisões críticas, abrir Fase E.2 separada (mitmproxy com WS capture habilitado).

## 6. Captura de referência

- Arquivo: `/home/daniel/cornerpressureelite/betano-capture-20260515-152323.mitm` (22 MB, 1134 flows)
- 4 jogos cobertos com estados diferentes (early, score 0-0; mid 1-0 com YELL; late 1-3 com PENL+GOAL+YELL)
- JSON extraídos durante análise: `/tmp/betano-event-latest-84220231.json`, `/tmp/betano-stats-aggregated-84220231.json` (recriáveis via script da Fase E.0 — não preservados em repo)
