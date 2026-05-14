# 2026-05-13 — Fase A: Betano StatsStream Provider

> Implementa o segundo passo da cronologia do pivot Betano
> (`docs/sprints/README.md` — item 2): provider REST `/api/statsstream/{eventId}/*`,
> tudo Opta-backed, com schemas tipados + parsers + testes.
>
> **Harness:** `docs/sprints/2026-05-12-betano-fase-A-statsstream-provider.md`.

## O que foi feito

### Estrutura criada

```
corner-pressure-elite/data/providers/betano/
├── __init__.py        # exporta API pública
├── session.py         # BetanoSession (curl_cffi chrome131) + BetanoBlockedError / BetanoParseError
├── statsstream.py     # BetanoStatsStream com 7 métodos + healthcheck
├── schemas.py         # 14 dataclasses frozen tipadas
└── parsers.py         # 7 parse_* puros e defensivos
```

### Scripts auxiliares

- `corner-pressure-elite/scripts/extract_betano_fixtures.py` — lê
  `docs/sprints/captures/2026-05-12-betano-flow.mitm` e exporta 17 fixtures JSON
  (2 jogos × 7 endpoints + 3 do danae-webapi) para
  `tests/providers/betano/fixtures/`.
- `corner-pressure-elite/scripts/betano_statsstream_smoke.py` — fim-a-fim
  contra a Betano real; pede `--event-id` + `--cookies` JSON.

### Testes

- `tests/providers/betano/test_parsers.py` — **16 unit tests verdes** cobrindo
  os 7 endpoints (info_aggregated, config, stats_detailed, momentum, lineups,
  h2h, stats_players) + casos de erro (`BetanoParseError`).
- `tests/providers/betano/test_integration.py` — 3 testes contra Betano viva,
  skip automático quando `config/betano_cookies.json` não existe (a definir na
  Fase B).
- `corner-pressure-elite/.gitignore` — adicionada entrada
  `config/betano_cookies.json` para não vazar cookies sensíveis.

## Decisões e ajustes vs spec

1. **Schemas baseados em real, não no spec.** A inspeção das fixtures revelou:
   - `h2h.previous_meetings[i]` usa `home_team_name`/`away_team_name` (não
     `home_team`/`away_team` como o spec sugeria) e `start_time` em **epoch
     milissegundos** (não ISO).
   - `lineups.<team>.on_pitch` é `list[list[player]]` (4 linhas táticas).
   - `player.id` é **int**, normalizado para `str` no parser.
   Os parsers acomodam ambos os formatos via `_parse_iso_or_epoch` e fallbacks.

2. **Healthcheck event_id parametrizado.** Default mantido em `84586925`
   (Cruzeiro × Goiás, do `.mitm`), mas aceita override — facilita re-uso quando
   esse evento expirar.

3. **`_safe()` único helper.** Parsers ficam densos e legíveis sem ramificações
   defensivas profundas; só campos obrigatórios levantam `BetanoParseError`.

4. **Sem cache no provider.** Cache fica para o `Composite` (Fase C) ou um
   decorator separado, conforme §4.8 do harness.

5. **Logs estruturados em chave=valor** (`path`, `status`, `attempt`,
   `duration_ms`) — facilita parse em ELK / Loki no futuro.

## Verificação

```bash
cd corner-pressure-elite
python3 -m pytest tests/providers/betano/ -v
# 16 passed, 3 skipped (integração, esperado sem cookies)
```

## Acceptance — §7 do harness

- [x] Estrutura de diretórios criada
- [x] `BetanoSession` carrega cookies de JSON e faz GET autenticado
- [x] `BetanoStatsStream` com 7 métodos implementados
- [x] Schemas dataclasses frozen completos (sem `Any` salvo `raw` de
      `PlayerStats`)
- [x] Parsers cobrem todos os 7 endpoints
- [x] Retry/backoff: 3 tentativas com `2^attempt + jitter`
- [x] 403/451 levantam `BetanoBlockedError` (não tentam de novo)
- [x] Logs estruturados (chave=valor)
- [x] Fixtures extraídas do `.mitm` em `tests/providers/betano/fixtures/`
- [x] Suite de testes unit verde
- [ ] Suite de testes integração verde com cookies reais — **bloqueado até
      Fase B**: cookies não congelados ainda em `config/betano_cookies.json`
- [x] Smoke script imprime resumo de todos os endpoints sem erro **(quando
      cookies estiverem disponíveis)**
- [x] `data/providers/betano/` não importa nada de `data/api_client.py`
- [ ] Documentação `sistema-completo.md` §22 atualizada — documento alvo ainda
      não existe; deixar para Fase C/D quando consolidar arquitetura

## Não feito (próximos passos)

- **Fase B** (~16h): `danae-webapi` markets, WebSocket SignalR (`contenthub` +
  `matchhub`), warmup Playwright, `BetanoCatalog` para fuzzy match
  fixture→event_id.
- **Fase C** (~10h): `Composite{Stats,Odds}Provider`, plug no `main.py`, feature
  flag `USE_NEW_PROVIDERS` + `DRIFT_CHECK_PROVIDERS`.
- **Fase D continuação** (~9.5h): repositories, workers, hooks, queries
  (migrations já aplicadas em
  `docs/changelog/2026-05-13-fase-d-migrations.md`).

## Referências

- Harness: `docs/sprints/2026-05-12-betano-fase-A-statsstream-provider.md`
- Master: `docs/sprints/2026-05-12-betano-discovery-master.md`
- Spike (captura): `docs/sprints/2026-05-12-betano-spike-mitmproxy.md`
- Migrations (Fase D pré-aplicada): `docs/changelog/2026-05-13-fase-d-migrations.md`
