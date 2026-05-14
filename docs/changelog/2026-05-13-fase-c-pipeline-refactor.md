# 2026-05-13 — Fase C: Pipeline Refactor com Composite Providers

> Quarto passo da cronologia do pivot Betano
> (`docs/sprints/README.md` — item 4): abstrações `Composite{Odds,Stats}Provider`,
> adapters de API-Football e Betano para uma interface canônica, factory
> guiado por feature flag. **`main.py` não foi tocado** — caminho legado
> permanece operacional. A migração do orquestrador acontece quando
> `USE_NEW_PROVIDERS=true` for ligado.
>
> **Harness:** `docs/sprints/2026-05-12-betano-fase-C-pipeline-refactor.md`.

## O que foi feito

### Novos módulos

```
corner-pressure-elite/
├── data/
│   ├── odds_provider.py            # Protocol + Canonical{Fixture,OverUnder} + Composite
│   ├── stats_provider.py           # Protocol + CanonicalStats + Composite
│   └── providers/
│       ├── apifootball/            # adapters thin (não modifica api_client.py)
│       │   ├── __init__.py
│       │   ├── odds_adapter.py
│       │   └── stats_adapter.py
│       ├── betano/
│       │   ├── odds_adapter.py     # event_id cache + repo + fuzzy catalog
│       │   └── stats_adapter.py
│       └── factory.py              # build_providers(settings, api_client, ...)
└── scripts/
    └── providers_healthcheck.py
```

### Settings novas (`config.py`)

```python
USE_NEW_PROVIDERS        = bool from env, default False
DRIFT_CHECK_PROVIDERS    = bool from env, default False
MIN_SCORE_TO_FETCH_ODDS  = int  from env, default 0
BETANO_COOKIES_PATH      = "config/betano_cookies.json"
WEBSHARE_PROXIES         = ""   # CSV opcional
```

### Comportamento

- **`CompositeOddsProvider`**: cascata por padrão (primeiro provider com
  resultado vence). Com `drift_check=True` chama **todos**, escreve divergência
  em `logs/provider_drift.jsonl`, mas devolve sempre o `primary`.
- **`BetanoOddsProvider._resolve_event_id`**: 3 camadas — cache em memória →
  `fixture_repo` (Fase D) → fuzzy match `BetanoCatalog.find_event_by_fixture`.
  Faz upsert no repo quando a resolução é fresh.
- **`min_score`**: se `current_score < min_score`, `BetanoOddsProvider` devolve
  None sem custar chamada ao markets. Composite cai pro AF.
- **Factory legado-OFF**: `[APIFootballOddsProvider]` e
  `[APIFootballStatsProvider]` — pipeline atual segue inalterado.
- **Factory legado-ON**: `[Betano, APIFootball]` cada um.
- **`persistence_worker` opcional**: Composite recebe um worker da Fase D e
  enfileira a entrada primary após cada dispatch — desacopla persistência.

### Testes

- `tests/test_composite_providers.py` — **11 unit tests**: cascata, fallback
  em None, fallback em exception, drift JSONL escrito com 2+ providers, drift
  pulado com 1, healthcheck OR, persistence_worker hook, idem para stats.
- `tests/providers/betano/test_adapters.py` — **6 unit tests**: `min_score`
  bloqueia, `event_id` cache poupa catalog na 2ª chamada, mapeamento
  `BetanoOverUnder → CanonicalOverUnder` preserva `market_code`, repo
  precedência sobre fuzzy, upsert pós-resolução, miss.
- `tests/test_providers_factory.py` — **3 unit tests**: legacy stack, new
  stack com cookies fake, propagação de `persistence_worker`.

Total Fase C: **20 tests verdes**.

## Decisões e ajustes vs spec

1. **Não refatorei `main.py`** — o harness §4.7 diz "merge com flag default
   false". Manter o orquestrador atual significa rollback instantâneo via
   variável de ambiente. A migração das call-sites do `main.py:778/799/897`
   fica para uma sprint dedicada quando `USE_NEW_PROVIDERS=true` em staging
   por 24h estiver verde.

2. **`APIFootballClient`**, não `APIClient`. O harness usou um nome
   especulativo; o real é o do `data.api_client`. Adapter aceita duck-typing
   via parâmetro `api_client`.

3. **Drift logger interno ao módulo `odds_provider`**, não classe separada.
   Caminho do JSONL via constante `DRIFT_LOG_PATH` patchável em testes.

4. **`build_providers(settings, api_client, *, fixture_repo, odds_persistence_worker)`**
   — `api_client` injetado pelo caller (o orquestrador é dono do ciclo de
   vida); `fixture_repo` e `odds_persistence_worker` são opcionais para
   compor com a Fase D.

5. **Stack legado também passa pelo Composite** — útil para já ganhar
   persistência/drift sem ativar Betano.

## Verificação

```bash
cd corner-pressure-elite
python3 -m pytest tests/test_composite_providers.py \
                   tests/test_providers_factory.py \
                   tests/providers/betano/test_adapters.py -v
# 20 passed
```

## Acceptance — §8 do harness

- [x] `data/odds_provider.py` define Protocol + Composite + dataclass canônica
- [x] `data/stats_provider.py` idem para stats
- [x] `data/providers/apifootball/` com 2 adapters NÃO modifica `api_client.py`
- [x] `data/providers/betano/odds_adapter.py` + `stats_adapter.py` implementados
- [x] `data/providers/factory.py` resolve stack via feature flag
- [ ] `main.py` (orquestrador) usa Composite — **adiado para sprint
      dedicada**, conforme decisão acima
- [x] `MIN_SCORE_TO_FETCH_ODDS`, `USE_NEW_PROVIDERS`, `DRIFT_CHECK_PROVIDERS`
      em `config.py`
- [x] `logs/provider_drift.jsonl` populado quando flag drift ativa
- [x] `providers_healthcheck.py` script existe (validação real depende de
      `USE_NEW_PROVIDERS` + cookies)
- [x] Suite de testes verde (20+ testes)
- [ ] Documentação `sistema-completo.md` §9 — alvo ainda não existe; deixar
      para sprint de consolidação pós-rollout
- [x] Plano de rollout documentado (este changelog + harness §4.7)

## Plano de rollout

1. **Merge atual**: `USE_NEW_PROVIDERS=false`. Sem mudança de comportamento.
2. **Staging A** (~24h): `USE_NEW_PROVIDERS=true`,
   `DRIFT_CHECK_PROVIDERS=true`. Cookies Betano em
   `config/betano_cookies.json`. Análise dos drift logs em
   `logs/provider_drift.jsonl` + queries `scripts/sql/queries/drift_summary_last_24h.sql`.
3. **Staging B**: refactor das call-sites do `main.py` para usar
   `composite_odds.get_corners` / `get_cards` em vez de
   `api_client.get_live_odds*`. Roda com flag ainda `true`.
4. **Produção em whitelist**: ligar para 2–3 ligas TOP (Brasileirão, La Liga).
5. **Rollout total**: depende de zero erros 403/451 sustentados.

## Não feito (próximos passos)

- Sprint "main.py refactor": migrar `main.py:778/799/897` para Composite
  (~3h, depende de `USE_NEW_PROVIDERS` ter rodado em staging A verde).
- Validação ao vivo: rodar `providers_healthcheck.py` com cookies frescos.
- Documentação consolidada `sistema-completo.md` quando rollout estabilizar.

## Referências

- Harness: `docs/sprints/2026-05-12-betano-fase-C-pipeline-refactor.md`
- Master: `docs/sprints/2026-05-12-betano-discovery-master.md`
- Pré-requisitos: `docs/changelog/2026-05-13-fase-{a,b}-betano-*.md`
- Persistência (Fase D continuada): `docs/changelog/2026-05-13-fase-d-persistencia-completa.md`
