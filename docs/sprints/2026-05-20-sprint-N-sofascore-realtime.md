# Sprint N — SofaScore real-time (WS NATS) + discovery nativa

**Data:** 2026-05-20
**Branch:** `feat/remove-af-completely`
**Origem:** análise do capture `sofascoreeee.json` (148 chamadas) + `sofascoreeee.mitm` (29MB, F12+mitmproxy).

## Contexto

Caçando o que faltava pra eliminar o AF (A2/A3), analisei um capture cru do SofaScore.
Achei 2 coisas novas de alto valor (e descartei 1).

## Achados

### 🟢 WebSocket NATS em tempo real — `wss://ws.sofascore.com:9222/`
Broker NATS-over-WS, sem auth (`user:none`). O browser faz:
```
CONNECT {...}\r\n  PING\r\n
SUB sport.football <sid>\r\n     # firehose de TODOS os jogos
SUB event.<sofa_id> <sid>\r\n    # por-evento
```
e recebe `MSG <subject> <sid> <nbytes>\r\n<payload>`, com deltas achatados:
```json
{"homeScore.current":2,"homeScore.period1":2,"id":15832136}
{"status.type":"finished","statusDescription":"FT","id":15551983}
{"cardsCode":"00","id":16146899}
```
**Não traz** contagem de escanteios/posse — é notificador-de-mudança + placar/status/FT.

**Valor:** FT em tempo real (substitui cold-check de 2h via AF) + smart-polling
(re-buscar `/statistics` só no delta, em vez de pollar cego 30s).

### 🟢 Discovery por torneio — `/unique-tournament/{tid}/scheduled-events/{date}`
Jogos de UM torneio numa data (vs o global `/scheduled-events/{date}` que puxa o
mundo). Base do discovery nativo do A2 — itera os tids monitorados.

### 🔴 Odds SofaScore — descartadas
`/event/{id}/odds/{provider}/all` só tem mercado "Full time" (1X2); provider BR é
"Betano Brazil" mas `oddsFrom: bet365`. Sem escanteios/cartões → inútil pra CPES.
Odds continuam vindo do bridge Betano. (Bom ter cravado.)

Outras rotas novas mas baixo valor: `/sport/football/live-tournaments`,
`/sport/{tzoffset}/event-count` (helpers de discovery), standings, votes, news, etc.

## Implementação (testada, atrás de flag OFF)

| Componente | Arquivo | Teste |
|---|---|---|
| Cliente WS NATS | `data/providers/sofascore/ws_client.py` (`SofaScoreLiveFeed` + `parse_nats`) | 7 unit (parser) + live (deltas reais: placar Boston River, cartão, FT) |
| Discovery por torneio | `SofaScoreClient.get_tournament_scheduled_events` + `data/providers/sofascore/discovery.py` | live: 28 jogos / 13 ligas, keyed por sofa_event_id |
| Flags | `SOFASCORE_WS_ENABLED`, `SOFASCORE_DISCOVERY_ENABLED` (default OFF) | — |

**Validação ao vivo (2026-05-20, Conmebol rolando):**
- WS conectou via curl_cffi impersonate; recebeu deltas reais incl. 2 jogos terminando (FT).
- Discovery por torneio cobriu o slate Conmebol (Boston River, Santos, Flamengo×Estudiantes…) sem AF.

**Disciplina:** componentes NÃO fiados no loop de produção. Cutover = A2 (ver ROADMAP).

## Próximo passo (A2)
1. Wire discovery como fonte da agenda (flag), AF fallback.
2. Wire `SofaScoreLiveFeed`: smart-polling + FT em tempo real (conserta tb `get_fixture_result_cards`).
3. Promover `sofa_event_id` a chave de leitura.
4. Smoke + validação FP antes de flipar flags.
