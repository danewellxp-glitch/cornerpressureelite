# API Pública — `/api/v1/public`

Endpoints sem autenticação, destinados à landing page `iqpressure.online`
e a qualquer outro consumidor externo.

**Princípio de privacidade:** sinais frescos são proteção competitiva
(concorrente pode copiar). Por isso `recent_signals` aplica delay
de **15 minutos** via SQL. Estado de jogos ao vivo é informação pública
(visível no site da casa) e não tem delay.

## Endpoints

### `GET /api/v1/public/ticker`

Snapshot agregado para ticker da landing.

**Query params:**

| Param  | Tipo    | Default | Range  | Descrição                              |
|--------|---------|---------|--------|----------------------------------------|
| `limit`| inteiro | `10`    | 1..20  | Aplica a cada lista (`live`, `signals`)|

**Response 200:**

```json
{
  "generated_at": "2026-05-16T20:54:11.199812+00:00",
  "live": [
    {
      "match": "Real Madrid × Barcelona",
      "league": "La Liga",
      "minute": 78,
      "score": "2-2",
      "pressure_score": 9,
      "tension_score": 5
    }
  ],
  "recent_signals": [
    {
      "emitted_at": "2026-05-16T20:18:00+00:00",
      "match": "Real Madrid × Barcelona",
      "league": "La Liga",
      "market": "Mais 4.5 cartões amarelos",
      "odd": 1.88,
      "delta_pct": null,
      "result": null
    }
  ]
}
```

**Campos:**

- `live[].pressure_score` / `tension_score` — vêm do sinal mais recente
  para aquele fixture (ESCANTEIOS → `pressure_score`, CARTOES → `tension_score`).
  `null` se ainda não houve sinal naquele jogo.
- `recent_signals[].emitted_at` — sempre `>= NOW() - 15min`. Garantido por
  `WHERE timestamp < NOW() - INTERVAL '15 minutes'` na query.
- `recent_signals[].delta_pct` — reservado para movimento de odd. Hoje
  retorna `null`; implementar requer join com `odds_history`.
- `recent_signals[].result` — `"GREEN"`, `"RED"` ou `null` (em andamento /
  pendente de fechamento).

**Ordenação:**

- `live` por `minute` decrescente.
- `recent_signals` por `emitted_at` decrescente.

### `GET /api/v1/public/health`

Probe de disponibilidade. Sem cache, sem rate limit.

**Response 200:**

```json
{
  "status": "ok",
  "version": "0.1.0",
  "uptime_seconds": 1234
}
```

`version` vem da env `CPES_VERSION` (default `0.1.0`).

## Cache

- TTL 60s in-memory (`api.public._cache`), keyed por `ticker:<limit>`.
- Header `X-Cache: HIT|MISS` na resposta.

## Rate limit

- 60 requisições por minuto, por IP.
- IP é extraído de `X-Forwarded-For` (primeiro item) se presente —
  Cloudflare Tunnel já passa isso.
- Headers em toda resposta sucesso:
  - `X-RateLimit-Limit: 60`
  - `X-RateLimit-Remaining: <N>`
- Excedido → `HTTP 429` com header `Retry-After: <segundos>`.

## CORS

Origens permitidas (configuradas em `api_server.py`):

- `https://iqpressure.online` / `https://www.iqpressure.online`
- `https://membros.iqpressure.online`
- `http://localhost:3000` / `http://localhost:3001` (dev)

## URLs de produção

- Health: `https://api.iqpressure.online/api/v1/public/health`
- Ticker: `https://api.iqpressure.online/api/v1/public/ticker`

## Exemplos curl

```bash
# Health
curl -s https://api.iqpressure.online/api/v1/public/health | jq

# Ticker default (limit=10)
curl -s https://api.iqpressure.online/api/v1/public/ticker | jq

# Ticker com limit reduzido
curl -s "https://api.iqpressure.online/api/v1/public/ticker?limit=5" | jq

# Validar CORS para origem da landing
curl -I -H "Origin: https://iqpressure.online" \
  https://api.iqpressure.online/api/v1/public/ticker
```

## Notas de implementação

- Router em `corner-pressure-elite/api/public.py`, montado em `api_server.py`
  via `app.include_router(public_router)`.
- Queries usam o pool asyncpg compartilhado (`Database._shared_pool`).
- Live games lidos de `data/live_state.json` (mesma fonte que
  `/api/live-games`); fallback `[]` se arquivo ausente/corrompido.
- Testes em `corner-pressure-elite/tests/test_public_ticker.py` (9 casos).
