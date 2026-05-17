# Betano Lineups API — Mapeamento (Fase G.0)

> **Investigação:** 2026-05-17, sem nova captura mitm — schema já estava
> embutido no payload `/event/<id>/state` capturado pela Fase E.1.
> Achado feito inspecionando JSONs já em cache de produção (`/tmp/test_*.json`,
> 5 fixtures de 4 ligas distintas).
>
> **Continuação direta de** [`betano-stats-api.md`](betano-stats-api.md)
> — usa exatamente o mesmo endpoint + transport.

## 1. Endpoint — `event.roster` no `/event/<id>/state`

**Sem novo endpoint necessário.** O `BridgeStatsAdapter` da Fase E.1 já
busca `GET /danae-webapi/api/live/events/<id>/latest` (via bridge
`/event/<id>/state`). O field `event.roster` no payload retornado contém
lineups completas.

Conclusão pra Fase G.1: implementação **CASO α puro** — só precisa
extrator + persistência. Zero novo trabalho de bridge/renewer.

### 1.1 Estrutura top-level

```json
{
  "event": {
    "roster": {
      "homeRoster": { "id": int, "name": str, "players": {...} },
      "awayRoster": { "id": int, "name": str, "players": {...} },
      "unknownPlayers": { "<uuid>": {...}, ... },
      "lineups": {
        "homeLineup": { "teamId": int, "formation": str, "lineup": [...], "benchPlayers": [...] },
        "awayLineup": { ...análogo... }
      }
    }
  }
}
```

### 1.2 `roster.homeRoster.players` — squad completo

Dict keyed por `player_id` (int). 26-38 players por time em ligas
profissionais. Cada player:

```json
{
  "id": 19243751,
  "name": "Zach Booth",
  "shortName": "Z. Booth",
  "shirtNumber": 23,
  "extraProps": {},
  "position": "DF",                       // GK | DF | MF | FW
  "positionDisplayName": "Zagueiro"       // localizado pt-BR
}
```

### 1.3 `roster.lineups.homeLineup` — lineup tática confirmada

```json
{
  "teamId": 108636,
  "formation": "5-4-1",                   // string convencional ⭐
  "lineup": [                             // list of lists — linhas táticas
    [ {"playerId": 19197510, "name": "R. Cabral"} ],            // GK (1)
    [ ...5 defenders... ],
    [ ...4 midfielders... ],
    [ ...1 forward... ]
  ],
  "benchPlayers": [                       // substitutos
    {"playerId": 19246179, "name": "G. Dillon"},
    ...
    {"unknownPlayerId": "<uuid>", "name": "Rodrigues dos Santos Lineker"}  // fallback
  ]
}
```

**`lineup` rows** correspondem à formation: `5-4-1` = 4 rows (GK + 5 + 4 + 1).
Cada player em `lineup[]` traz só `playerId + name` — cruza com
`roster.homeRoster.players[playerId]` pra detalhes (shirtNumber, position, etc).

**`unknownPlayerId`** aparece em players sem ID Betano confirmado — UUID
local + name string. Tratamento: tentar resolver via name match futuramente
OU persistir como NULL.

### 1.4 Coverage level

Linha de cobertura idêntica à E.1 (mesma fonte Opta):

| Tipo de liga | `roster.players` | `lineups.formation` + `lineup` | `benchPlayers` |
|---|---|---|---|
| MLS, MLB, La Liga, Bundesliga (full) | ✅ 26-38 | ✅ formation + 4-5 rows | ✅ 6-9 jogadores |
| Brasileirão / Argentina / Premier (esperado) | ✅ extrapolando | ✅ extrapolando | ✅ extrapolando |
| Liga 1 Peru | ✅ confirmado | ✅ formation 4-2-3-1 | ✅ |
| Ligas pequenas (Panamá amador) | ❌ players=0 | ❌ formation=None | ❌ vazio |
| Esoccer (eSports) | ❌ players=0 | ❌ formation=None | ❌ vazio |

**Cobertura ≈ E.1.** Se `liveData.results` tem dados, `roster.lineups`
provavelmente também tem.

## 2. Cobertura comparativa vs API-Football

| Campo | Betano `event.roster` | API-Football `/fixtures/lineups` | Notas |
|---|---|---|---|
| Team id + name | ✅ | ✅ | Equivalente |
| Formation | ✅ string ("5-4-1") | ✅ string | Equivalente |
| Starting eleven (com player names) | ✅ via `lineup[][]` | ✅ via `startXI[]` | Equivalente |
| Substitutos (bench) | ✅ via `benchPlayers[]` | ✅ via `substitutes[]` | Equivalente |
| Player position (GK/DF/MF/FW) | ✅ em `roster.players[id].position` | ✅ em `startXI[].player.pos` | Equivalente |
| Shirt number | ✅ em `roster.players[id].shirtNumber` | ✅ em `startXI[].player.number` | Equivalente |
| Position localizada (pt-BR) | ✅ `positionDisplayName` | ❌ | ⭐ **Betano tem, AF não** |
| Squad completo (não-titulares fora bench) | ✅ via `roster.players` (todos 26-38) | ❌ só XI + bench | ⭐ **Betano tem, AF não** |
| Coach (técnico) | ❌ | ✅ via `coach.name` | ❌ **AF tem, Betano não** |
| Confirmed vs presumed | ⚠️ não distingue explicitamente | ⚠️ AF marca `confirmed: bool` | Gap menor |

**Gap principal Betano:** coach. **Ganhos Betano:** squad completo + position localizada.

Pro pipeline atual: lineups NÃO são consumidas pelo decision_engine (igual events Fase F). **Dataset puro** — alimenta Quant H1-H4 (modelos de pricing que precisam de formation, qualidade de XI titular, profundidade do bench).

## 3. Decisão arquitetural — CASO α puro

Implementação Fase G.1:
- Adapter extrai `payload.event.roster` no parse (zero nova request HTTP).
- Cache de version+roster reaproveitável com a infra E.1 (304 cache hit já existe).
- Persistência em `lineups_history` (snapshot por captura — lineup pode mudar pré-jogo conforme treinador atualiza).
- Worker stateless similar ao `BetanoEventsWorker`.

**Estimativa G.1:** ~5h (CASO α puro, padrão E.1+F reusado).

## 4. Limitações reconhecidas

### 4.1 Coach não vem
Pra dataset que precisa de "qual técnico estava em campo no jogo X",
precisa de fallback AF OU scraping extra. Pra MVP de pricing (H2-H4),
formation + qualidade do XI cobre 90% do uso.

### 4.2 Cobertura zero em ligas pequenas
Mesma limitação E.1 — `coverage_level` da Opta varia. Não há mitigação
do lado Betano. Worker deve normalizador tratar `lineups=None` graciosamente.

### 4.3 Confirmed vs presumed
Betano não distingue explicitamente. Risco: persistir lineup "presumed"
que muda 30min antes do jogo. Mitigação:
- Polling continua (mesmo workflow E.1/F)
- UNIQUE constraint dedup permite reinserções com novo `version` quando
  lineup é atualizada
- Worker compara último snapshot persistido vs novo — se difere, persiste
  novo registro (não vira UNIQUE conflict porque schema deve incluir
  version OR captured_at granular)

### 4.4 `unknownPlayers` (UUID em vez de ID)
Players sem ID Betano confirmado aparecem com `unknownPlayerId` UUID +
name. Persistir como `player_id=NULL, player_name=<str>`. Quando ID for
resolvido em sessão futura, dataset pode ser backfilled via name match.

## 5. Captura de referência

Schemas inspecionados em produção 2026-05-17:
- `/tmp/test_81381172.json` — Real Salt Lake × Colorado Rapids (MLS) — full coverage
- `/tmp/test_81383743.json` — San Diego FC × FC Cincinnati (MLS) — full coverage
- `/tmp/test_84523572.json` — Sport Boys × Cusco FC (Liga 1 Peru) — full coverage
- `/tmp/test_85773981.json` — Atletico Rio Abajo × FC Panama Norte (Liga Panamá) — zero coverage
- `/tmp/state.json` — Esoccer fixture pré-kickoff — zero coverage

Mesmo padrão `coverage_level` da E.1.
