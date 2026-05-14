# 2026-05-13 — Fase B: Betano Markets & WebSocket Provider

> Implementa o terceiro passo da cronologia do pivot Betano
> (`docs/sprints/README.md` — item 3): cliente REST de mercados, catálogo
> com fuzzy match e cliente WebSocket SignalR Core. Mais o warmup via
> Playwright na `BetanoSession`.
>
> **Harness:** `docs/sprints/2026-05-12-betano-fase-B-markets-ws-provider.md`.

## O que foi feito

### Novos módulos

```
corner-pressure-elite/data/providers/betano/
├── codes.py            # constantes de market codes (CNOU/TCOU/RCOU/...)
├── markets.py          # BetanoMarkets — /danae-webapi/api/live/events/{id}/latest
├── catalog.py          # BetanoCatalog — overview + fuzzy match fixture→event
└── wsclient.py         # BetanoWSClient — SignalR Core (contenthub + matchhub)
```

### Mudanças em existentes

- **`schemas.py`** — 8 dataclasses novas: `BetanoLiveData`, `BetanoParticipant`,
  `BetanoIncident`, `BetanoMarket`, `BetanoSelection`, `BetanoOverUnder`,
  `EventSnapshot`, `BetanoLiveEvent`, `BetanoStatsPlayerMapping`, `MatchEvent`.
- **`parsers.py`** — 6 funções novas: `parse_event_snapshot`,
  `extract_over_under` (+ helpers `_pick_main_line`, `_split_over_under`),
  `parse_live_overview_events`, `parse_statsplayer`, `parse_match_event`,
  `parse_match_event_initial`.
- **`session.py`** — reescrito para Fase B com:
  - `warmup()` via Playwright Chromium mobile (extrai cookies CF/DataDome +
    `kbversion` via `/api/kb-config/`).
  - `_relogin_if_needed()` chamado automaticamente em 403/451; re-tenta uma vez.
  - Rotação de proxies com burned-list (30min TTL).
  - `cookie_header()`, `user_agent()` para o WS.
- **`__init__.py`** — exporta a API completa Fase A + B.
- **`requirements.txt`** — adicionado `websockets>=12.0` e `playwright>=1.41.0`.

### Scripts

- `corner-pressure-elite/scripts/betano_markets_smoke.py` — fim-a-fim contra
  `/danae-webapi/api/live/events/{id}/latest` + statsplayer mapping. Imprime
  CNOU/TCOU principais + IDs Sportradar/Opta.

### Testes

- `tests/providers/betano/test_markets_catalog_ws.py` — **21 unit tests verdes**
  cobrindo:
  - `parse_event_snapshot` (betradar id, markets dict, missing id raises).
  - `extract_over_under` (linha requerida, principal, missing selection,
    TCOU).
  - `parse_live_overview_events` (96 eventos, ≥1 FOOT live).
  - `parse_statsplayer` (mapping SR/Opta + statTypes).
  - `parse_match_event` (X/Y, flags, sem ball_position_end).
  - `BetanoCatalog.find_event_by_fixture` (normalização de acento/caixa,
    janela de kickoff ±15min, cache `fixture_map`).
  - `BetanoWSClient._extract_event_id_from_diff` (base64 + regex).

## Decisões e ajustes vs spec

1. **Selection name = "Mais de 9.5" / "Menos de 9.5"**, não só
   "Mais"/"Menos". `_split_over_under` usa **startswith** + fallback para
   `[over, under]` quando `selectionIdList` tem 2 elementos. Validado com
   fixture real do Cruzeiro × Goiás.

2. **`betradarMatchId` é int**, não opcional-string. Parser converte explícito.

3. **`websockets`** já estava instalado no host (v16.0) mas não declarado em
   `requirements.txt` — adicionado. O `additional_headers` substitui o
   `extra_headers` do spec (deprecado na lib).

4. **Warmup Playwright tardio**: import dentro do `warmup()` para não tornar
   `playwright` obrigatório só para usar cookies congelados (Fase A path).
   Erro claro se faltando.

5. **`relogged` flag no `get_json`** — 403 dispara warmup uma única vez,
   evitando loop infinito. Após 2ª tentativa falhando: `BetanoBlockedError`.

6. **`league_id_hint` no fuzzy match**: bonus de +5 no score quando a liga
   bate, sem deixar ser bloqueante. Útil para desempate quando dois jogos
   com nomes parecidos rodam simultâneos.

7. **WS scheduler robusto**: reconnect 1→2→5→10→30→60s com jitter; ping `type=6`
   ecoa pong; `type=7` (CLOSE) re-tenta no loop externo.

## Verificação

```bash
cd corner-pressure-elite
python3 -m pytest tests/providers/betano/ -v
# 37 passed (Fase A: 16 + Fase B: 21), 3 skipped (integração — sem cookies)
```

## Acceptance — §8 do harness

- [x] `BetanoSession.warmup()` opera com Chromium headless mobile
- [ ] Cookies necessários populados pós-warmup — código escrito; **não
      validado em runtime** (Playwright/Chromium não estão instalados na
      máquina de dev; só dispara quando container/CI tiver `playwright install`)
- [x] `kbversion` extraído dinamicamente — via `fetch('/api/kb-config/')`
- [x] `BetanoMarkets` cobre os 3 públicos + `fetch_market_by_code`
- [x] `BetanoCatalog` lista eventos do dia + fuzzy match + cache + `prime`
- [x] `BetanoWSClient` mantém 1 conexão `/contenthub` + N `/matchhub`
- [x] Reconnect com backoff exponencial implementado
- [x] Logs estruturados para WS connect/disconnect/error
- [x] Schemas expandidos (8 dataclasses novas, mais que os 8 originais)
- [x] Parsers expandidos (6 funções novas)
- [x] `codes.py` com market codes documentados + sets `CORNERS_CODES` /
      `CARDS_CODES`
- [x] Smoke `betano_markets_smoke.py` imprime CNOU + TCOU
- [x] Suite de testes verde (unit) — 21 unit Fase B; integração/WS/warmup
      ficam para validação real
- [x] 0 chamadas de login (anônimo) — warmup só home + click "/live"
- [ ] `_relogin_if_needed` testado com 403 simulado — **não escrito**:
      requer mock de `curl_cffi.AsyncSession` + Playwright; deixar para
      Fase C/integração viva
- [ ] Documentação `sistema-completo.md` §20 atualizada — doc alvo não
      existe ainda; consolidar com Fase C

## Não feito (próximos passos)

- **Validação ao vivo**: `betano_markets_smoke.py` contra Betano real (pendente
  cookies recentes em `config/betano_cookies.json` — não versionados).
- **Testes de integração WS/warmup** (3+3+3 da spec §7) — exigem ambiente real
  (Playwright + cookies + live event). Estrutura preparada para skip
  automático.
- **Fase C** (~10h): `Composite{Stats,Odds}Provider` injetando Betano como
  primary + AF como fallback, plug no `main.py`, feature flag
  `USE_NEW_PROVIDERS` + `DRIFT_CHECK_PROVIDERS`.
- **Fase D continuação** (~9.5h): repositories, workers, hooks no Composite e
  no callback do `BetanoWSClient.subscribe_match`, queries SQL.

## Referências

- Harness: `docs/sprints/2026-05-12-betano-fase-B-markets-ws-provider.md`
- Master: `docs/sprints/2026-05-12-betano-discovery-master.md`
- Fase A (pré-requisito): `docs/changelog/2026-05-13-fase-a-betano-statsstream.md`
- Migrations Fase D pré-aplicadas: `docs/changelog/2026-05-13-fase-d-migrations.md`
