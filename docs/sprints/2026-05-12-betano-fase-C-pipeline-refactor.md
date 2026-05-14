# Fase C — Pipeline Refactor com Composite Providers

> **Mestre:** [`2026-05-12-betano-discovery-master.md`](2026-05-12-betano-discovery-master.md)
>
> **Pré-requisitos:** [Fase A](2026-05-12-betano-fase-A-statsstream-provider.md) e [Fase B](2026-05-12-betano-fase-B-markets-ws-provider.md) concluídas.
>
> **Duração estimada:** ~10h

---

## 1. Objetivo

Integrar os providers Betano no pipeline principal (`main.py:796`) via
abstrações Composite, sem quebrar o caminho atual (API-Football). Feature flag
`USE_NEW_PROVIDERS=true` ativa o novo modo; off mantém comportamento legado.

**Princípio:** caller (orquestrador) chama um único provider; abstração decide
se é Betano primary, API-Football fallback, ou ambos para drift check.

---

## 2. Pré-requisitos

- [x] Fase A: `BetanoStatsStream` operacional
- [x] Fase B: `BetanoMarkets`, `BetanoCatalog`, `BetanoWSClient` operacionais
- [x] `api_client.py` da API-Football funcional (legado)
- [ ] Acesso ao Postgres pra healthcheck de DB (já existe)

---

## 3. Capabilities entregues

1. **Protocols (interfaces)** — `data/odds_provider.py` e
   `data/stats_provider.py` com `OddsProvider`, `StatsProvider`.
2. **Adapters da API-Football** — wrappers finos sobre `api_client.py` que
   implementam os Protocols (`APIFootballOddsProvider`,
   `APIFootballStatsProvider`).
3. **Adapters do Betano** — equivalentes (`BetanoOddsProvider`,
   `BetanoStatsProvider`).
4. **Composite providers** — `CompositeOddsProvider` e
   `CompositeStatsProvider` com lógica de fallback em cascata.
5. **Trigger condicional** — `BetanoOddsProvider` só fetch quando
   `score >= MIN_SCORE_TO_FETCH_ODDS` (configurável).
6. **Feature flag** — `USE_NEW_PROVIDERS` em `config.py` ou env. Default
   `false` no merge inicial.
7. **Drift check em modo dual** — flag `DRIFT_CHECK_PROVIDERS=true` chama os
   dois providers e loga divergências, sem afetar decisão de sinal.
8. **Healthcheck consolidado** — `scripts/providers_healthcheck.py` lista
   status de cada provider.
9. **Refactor de `main.py`** — orquestrador passa a usar `CompositeOddsProvider`
   e `CompositeStatsProvider`; injeção de dependência via construtor da
   classe orquestradora.
10. **Testes E2E** — fluxo completo simulado com mocks dos providers.

---

## 4. Decisões críticas

### 4.1 Não tocar em `api_client.py` (legado intocado)

Manter `data/api_client.py` exatamente como está. A camada de adapter
(`APIFootballOddsProvider`) chama `api_client.get_live_odds_multi_bookmaker`,
`get_live_odds_cards`, etc. Isso permite rollback total via feature flag.

### 4.2 Score como gatilho do BetanoOddsProvider

```python
class BetanoOddsProvider:
    def __init__(self, ..., min_score: int = 0):
        self._min_score = min_score   # default 0 = sempre fetcha

    async def get_corners(self, fixture, current_score) -> OverUnder | None:
        if current_score < self._min_score:
            return None  # composite cai pro próximo
        # ... fetch ...
```

`MIN_SCORE_TO_FETCH_ODDS` em config: para escanteios usar 0 (sempre fetch),
para cartões usar 0 também. Pode ser ajustado pra economia (ex. 6 corners),
mas Betano é leve.

### 4.3 Composite: ordem fixa, fallback automático

```python
class CompositeOddsProvider:
    def __init__(self, providers: list[OddsProvider]):
        self._providers = providers

    async def get_corners(self, fixture, current_score):
        for p in self._providers:
            try:
                result = await p.get_corners(fixture, current_score)
                if result is not None:
                    return result
            except Exception as e:
                log.warning("provider.%s.error: %s", p.name, e)
        return None  # nenhum provider entregou
```

**Sem timeout global** no composite — cada provider gerencia o seu (já tem na
sessão Betano). Composite só faz cascata.

### 4.4 Drift check: log only, não muda decisão

```python
class CompositeOddsProvider:
    def __init__(self, providers, drift_check: bool = False):
        self._drift_check = drift_check

    async def get_corners(self, fixture, score):
        results = []
        for p in self._providers:
            try:
                r = await p.get_corners(fixture, score)
                results.append((p.name, r))
            except Exception as e:
                log.warning("provider.%s.error: %s", p.name, e)
                results.append((p.name, None))

        primary_result = next((r for _, r in results if r is not None), None)

        if self._drift_check and len([r for _, r in results if r]) >= 2:
            self._log_drift("corners", fixture.fixture_id, results)

        return primary_result
```

**Drift log** salva em `logs/provider_drift.jsonl`:
```json
{"ts":"2026-05-13T...","fixture_id":12345,"market":"corners",
 "primary":"betano","primary_linha":9.5,"primary_over":1.85,"primary_under":1.95,
 "fallback":"apifootball","fallback_linha":9.5,"fallback_over":1.83,"fallback_under":1.97,
 "drift_pct_over":0.011}
```

### 4.5 Trigger de pré-fetch: só quando score >= MIN

`main.py:796` antes do chamado de get_live_odds_multi_bookmaker, inserir:

```python
if int(score_home) + int(score_away) < settings.MIN_SCORE_TO_FETCH_ODDS:
    # provavelmente sem mercado caro a buscar
    odds = await composite_odds.get_corners(fixture, score=0)
else:
    odds = await composite_odds.get_corners(fixture, score=score_total)
```

Para escanteios isso pouco importa (Betano serve sempre). Para mercados
caros futuros (ex. live streams), o pattern já está em pé.

### 4.6 Resolução de event_id: cache em memória + DB

```python
class BetanoOddsProvider:
    async def get_corners(self, fixture, current_score):
        event_id = await self._resolve_event_id(fixture)
        if not event_id:
            return None
        ou = await self._markets.fetch_corners(event_id)
        return self._to_canonical_overunder(ou, fixture) if ou else None

    async def _resolve_event_id(self, fixture):
        # 1. cache em memória
        if fixture.fixture_id in self._event_id_cache:
            return self._event_id_cache[fixture.fixture_id]
        # 2. DB (Fase D adiciona betano_fixture_map)
        if self._fixture_repo:
            ev = await self._fixture_repo.get_betano_event_id(fixture.fixture_id)
            if ev:
                self._event_id_cache[fixture.fixture_id] = ev
                return ev
        # 3. fuzzy match via catalog
        ev = await self._catalog.find_event_by_fixture(
            fixture.fixture_id, fixture.home_team, fixture.away_team,
            fixture.starts_at_utc, league_id_hint=fixture.league_id,
        )
        if ev:
            self._event_id_cache[fixture.fixture_id] = ev
            # Fase D salva no DB
            if self._fixture_repo:
                await self._fixture_repo.upsert(fixture.fixture_id, ev)
        return ev
```

### 4.7 Feature flag default OFF no merge inicial

Em `settings.py` ou `config.py`:

```python
USE_NEW_PROVIDERS = os.getenv("USE_NEW_PROVIDERS", "false").lower() == "true"
DRIFT_CHECK_PROVIDERS = os.getenv("DRIFT_CHECK_PROVIDERS", "false") == "true"
MIN_SCORE_TO_FETCH_ODDS = int(os.getenv("MIN_SCORE_TO_FETCH_ODDS", "0"))
```

Plano de rollout:
1. Merge com `USE_NEW_PROVIDERS=false` (caminho legado)
2. Em staging: `=true` + `DRIFT_CHECK_PROVIDERS=true` por 24h
3. Análise dos drift logs
4. Produção: `=true` em jogos selecionados (whitelist de leagues)
5. Rollout total

---

## 5. Componentes novos

### 5.1 `data/odds_provider.py`

```python
"""Abstrações de provider de odds. Versão canônica que o orquestrador usa."""
from __future__ import annotations
import logging
from dataclasses import dataclass
from typing import Protocol, runtime_checkable
from datetime import datetime

log = logging.getLogger("cpes.providers.odds")


@dataclass(frozen=True)
class CanonicalFixture:
    fixture_id: int
    home_team: str
    away_team: str
    league_id: int
    starts_at_utc: datetime
    score_home: int = 0
    score_away: int = 0


@dataclass(frozen=True)
class CanonicalOverUnder:
    source: str
    market_kind: str        # "corners" | "cards"
    market_code: str        # "CNOU", "TCOU", ou ""
    linha: float
    odd_over: float
    odd_under: float


@runtime_checkable
class OddsProvider(Protocol):
    name: str

    async def get_corners(
        self, fixture: CanonicalFixture, current_score: int
    ) -> CanonicalOverUnder | None: ...

    async def get_cards(
        self, fixture: CanonicalFixture, current_score: int
    ) -> CanonicalOverUnder | None: ...

    async def healthcheck(self) -> bool: ...


class CompositeOddsProvider:
    name = "composite"

    def __init__(
        self, providers: list[OddsProvider],
        drift_check: bool = False,
    ):
        self._providers = providers
        self._drift_check = drift_check

    async def get_corners(self, fixture, score):
        return await self._dispatch("get_corners", fixture, score, "corners")

    async def get_cards(self, fixture, score):
        return await self._dispatch("get_cards", fixture, score, "cards")

    async def healthcheck(self):
        return any([await p.healthcheck() for p in self._providers])

    async def _dispatch(self, method, fixture, score, market):
        results = []
        for p in self._providers:
            try:
                r = await getattr(p, method)(fixture, score)
                results.append((p.name, r))
            except Exception as e:
                log.warning("provider.%s.%s.error: %s", p.name, method, e)
                results.append((p.name, None))

        primary = next((r for _, r in results if r is not None), None)

        if self._drift_check and sum(1 for _, r in results if r) >= 2:
            self._log_drift(market, fixture.fixture_id, results)

        return primary

    def _log_drift(self, market, fixture_id, results):
        import json
        from pathlib import Path
        entry = {
            "ts": datetime.utcnow().isoformat(),
            "fixture_id": fixture_id,
            "market": market,
            "providers": [
                {
                    "name": name,
                    "linha": r.linha if r else None,
                    "over": r.odd_over if r else None,
                    "under": r.odd_under if r else None,
                }
                for name, r in results
            ],
        }
        try:
            with open("logs/provider_drift.jsonl", "a") as f:
                f.write(json.dumps(entry) + "\n")
        except Exception:
            pass
```

### 5.2 `data/stats_provider.py`

Análogo a `odds_provider.py`. Esqueleto:

```python
@dataclass(frozen=True)
class CanonicalStats:
    fixture_id: int
    source: str               # "betano" | "apifootball"
    minute: int
    score_home: int
    score_away: int
    corners_home: int
    corners_away: int
    yellow_cards_home: int
    yellow_cards_away: int
    red_cards_home: int
    red_cards_away: int
    shots_on_target_home: int
    shots_on_target_away: int
    dangerous_attacks_home: int
    dangerous_attacks_away: int
    possession_home: int
    possession_away: int
    x_goals_home: float
    x_goals_away: float
    pressure_score_provider: float | None  # de Opta/Betano momentum
    raw: dict


@runtime_checkable
class StatsProvider(Protocol):
    name: str

    async def get_stats(
        self, fixture: CanonicalFixture
    ) -> CanonicalStats | None: ...

    async def healthcheck(self) -> bool: ...


class CompositeStatsProvider:
    # ... espelho de CompositeOddsProvider ...
```

### 5.3 `data/providers/apifootball/__init__.py`

```python
"""Adapters da API-Football pra interfaces canônicas. NÃO modifica api_client.py."""
from .odds_adapter import APIFootballOddsProvider
from .stats_adapter import APIFootballStatsProvider
```

### 5.4 `data/providers/apifootball/odds_adapter.py`

```python
import logging
from data.api_client import APIClient  # legado
from data.odds_provider import OddsProvider, CanonicalOverUnder, CanonicalFixture

log = logging.getLogger("cpes.providers.apifootball.odds")


class APIFootballOddsProvider:
    name = "apifootball"

    def __init__(self, api_client: APIClient):
        self._c = api_client

    async def get_corners(
        self, fixture: CanonicalFixture, current_score: int
    ) -> CanonicalOverUnder | None:
        # api_client.get_live_odds_multi_bookmaker (api_client.py:316)
        raw = await self._c.get_live_odds_multi_bookmaker(
            fixture.fixture_id, market="corners",
        )
        return self._to_canonical(raw, "corners")

    async def get_cards(
        self, fixture: CanonicalFixture, current_score: int
    ) -> CanonicalOverUnder | None:
        # api_client.get_live_odds_cards (api_client.py:574)
        raw = await self._c.get_live_odds_cards(fixture.fixture_id)
        return self._to_canonical(raw, "cards")

    def _to_canonical(self, raw, market_kind) -> CanonicalOverUnder | None:
        if not raw:
            return None
        try:
            return CanonicalOverUnder(
                source="apifootball",
                market_kind=market_kind,
                market_code="",
                linha=float(raw["linha"]),
                odd_over=float(raw["odd_over"]),
                odd_under=float(raw["odd_under"]),
            )
        except (KeyError, ValueError, TypeError):
            log.warning("apifootball.odds.parse_error market=%s raw=%s",
                        market_kind, raw)
            return None

    async def healthcheck(self) -> bool:
        try:
            # ping leve — exemplo: fixtures live
            r = await self._c.get_live_fixtures()
            return r is not None
        except Exception:
            return False
```

### 5.5 `data/providers/apifootball/stats_adapter.py`

Espelho do anterior, chamando `api_client.get_live_fixture_stats` ou
equivalente.

### 5.6 `data/providers/betano/odds_adapter.py`

```python
import logging
from data.providers.betano import BetanoSession, BetanoMarkets, BetanoCatalog
from data.odds_provider import OddsProvider, CanonicalOverUnder, CanonicalFixture

log = logging.getLogger("cpes.providers.betano.odds")


class BetanoOddsProvider:
    name = "betano"

    def __init__(
        self,
        session: BetanoSession,
        markets: BetanoMarkets,
        catalog: BetanoCatalog,
        min_score: int = 0,
        fixture_repo=None,    # Fase D injeta repository
    ):
        self._session = session
        self._markets = markets
        self._catalog = catalog
        self._min_score = min_score
        self._fixture_repo = fixture_repo
        self._event_id_cache: dict[int, int] = {}

    async def get_corners(self, fixture, current_score):
        if current_score < self._min_score:
            return None
        event_id = await self._resolve_event_id(fixture)
        if not event_id:
            return None
        ou = await self._markets.fetch_corners(event_id)
        return self._to_canonical(ou, "corners") if ou else None

    async def get_cards(self, fixture, current_score):
        if current_score < self._min_score:
            return None
        event_id = await self._resolve_event_id(fixture)
        if not event_id:
            return None
        ou = await self._markets.fetch_cards(event_id)
        return self._to_canonical(ou, "cards") if ou else None

    def _to_canonical(self, ou, market_kind):
        return CanonicalOverUnder(
            source="betano",
            market_kind=market_kind,
            market_code=ou.market_code,
            linha=ou.handicap,
            odd_over=ou.odd_over,
            odd_under=ou.odd_under,
        )

    async def _resolve_event_id(self, fixture):
        if fixture.fixture_id in self._event_id_cache:
            return self._event_id_cache[fixture.fixture_id]
        if self._fixture_repo:
            ev = await self._fixture_repo.get_betano_event_id(fixture.fixture_id)
            if ev:
                self._event_id_cache[fixture.fixture_id] = ev
                return ev
        ev = await self._catalog.find_event_by_fixture(
            fixture.fixture_id, fixture.home_team, fixture.away_team,
            fixture.starts_at_utc, league_id_hint=fixture.league_id,
        )
        if ev:
            self._event_id_cache[fixture.fixture_id] = ev
            if self._fixture_repo:
                try:
                    await self._fixture_repo.upsert(fixture.fixture_id, ev)
                except Exception:
                    log.warning("fixture_repo.upsert.fail fixture=%d",
                                fixture.fixture_id)
        return ev

    async def healthcheck(self) -> bool:
        try:
            events = await self._catalog.list_live_events()
            return len(events) > 0
        except Exception:
            return False
```

### 5.7 `data/providers/betano/stats_adapter.py`

Análogo, usando `BetanoStatsStream.get_stats_detailed` + `get_momentum` para
preencher `CanonicalStats`. Pressure score da Opta vai pro
`pressure_score_provider`.

### 5.8 Factory de wiring — `data/providers/factory.py`

```python
"""Factory que decide qual stack de providers usar (feature flag)."""
import logging
from data.odds_provider import CompositeOddsProvider
from data.stats_provider import CompositeStatsProvider

log = logging.getLogger("cpes.providers.factory")


async def build_providers(settings):
    """Constrói os Composite providers conforme settings.

    Retorna: (odds_provider, stats_provider, shutdown_callable)
    """
    api_client = _build_api_client(settings)
    from data.providers.apifootball import (
        APIFootballOddsProvider, APIFootballStatsProvider,
    )
    af_odds = APIFootballOddsProvider(api_client)
    af_stats = APIFootballStatsProvider(api_client)

    if not settings.USE_NEW_PROVIDERS:
        log.info("providers.legacy: apenas API-Football")
        return (
            CompositeOddsProvider([af_odds]),
            CompositeStatsProvider([af_stats]),
            lambda: None,
        )

    # New stack: Betano primary
    from data.providers.betano import (
        BetanoSession, BetanoStatsStream, BetanoMarkets, BetanoCatalog,
    )
    from data.providers.betano.odds_adapter import BetanoOddsProvider
    from data.providers.betano.stats_adapter import BetanoStatsProvider

    proxies = settings.WEBSHARE_PROXIES.split(",") if settings.WEBSHARE_PROXIES else []
    session = BetanoSession.from_file(settings.BETANO_COOKIES_PATH)
    session._proxies = proxies
    await session.warmup_if_needed()  # noop se cookies fresh

    bet_stats = BetanoStatsProvider(session, BetanoStatsStream(session))
    bet_odds = BetanoOddsProvider(
        session,
        BetanoMarkets(session),
        BetanoCatalog(session),
        min_score=settings.MIN_SCORE_TO_FETCH_ODDS,
    )

    composite_odds = CompositeOddsProvider(
        [bet_odds, af_odds],
        drift_check=settings.DRIFT_CHECK_PROVIDERS,
    )
    composite_stats = CompositeStatsProvider(
        [bet_stats, af_stats],
        drift_check=settings.DRIFT_CHECK_PROVIDERS,
    )

    async def shutdown():
        await session.close()

    log.info("providers.new_stack: Betano primary + API-Football fallback")
    return composite_odds, composite_stats, shutdown
```

### 5.9 Refactor de `main.py` (orchestrator) — diff conceitual

```python
# antes (main.py:796 aproximadamente)
odds_raw = await api_client.get_live_odds_multi_bookmaker(fixture_id, market="corners")
# ... parsing local ...

# depois
odds_canonical = await odds_provider.get_corners(
    canonical_fixture, current_score=score_home + score_away
)
if odds_canonical:
    # uso direto dos campos canônicos
    linha = odds_canonical.linha
    odd_over = odds_canonical.odd_over
    odd_under = odds_canonical.odd_under
```

`odds_provider` é construído no startup do orquestrador via
`build_providers(settings)` e injetado.

### 5.10 `scripts/providers_healthcheck.py`

```python
"""Healthcheck consolidado de todos os providers ativos."""
import asyncio
import sys
from config import settings
from data.providers.factory import build_providers


async def main():
    odds, stats, shutdown = await build_providers(settings)
    try:
        odds_ok = await odds.healthcheck()
        stats_ok = await stats.healthcheck()
        print(f"odds: {'OK' if odds_ok else 'FAIL'}")
        print(f"stats: {'OK' if stats_ok else 'FAIL'}")
        sys.exit(0 if (odds_ok and stats_ok) else 1)
    finally:
        await shutdown()


if __name__ == "__main__":
    asyncio.run(main())
```

---

## 6. Edge cases

| Caso | Comportamento |
|---|---|
| Betano blocked (403 persistente após warmup) | Composite cai pro AF; logs com tag `provider=betano error=blocked` |
| Fixture sem match no Betano catalog | Composite cai pro AF; entry em log com `unmatched=true` |
| Ambos providers retornam None | Caller recebe None; sinal não é gerado (comportamento atual) |
| Drift logged mas decisão é só do primary | Drift é métrica, não muda decisão |
| `MIN_SCORE_TO_FETCH_ODDS=2` e score=0 | Betano retorna None; cai pro AF; AF responde normal |
| Provider em "modo aquecimento" (warmup em curso) | Lock async espera; composite tem timeout interno por chamada (15s) |
| Provider Betano funciona pra escanteios mas não pra cartões | Permitido — cada método independente |
| Race: dois calls simultâneos pra _resolve_event_id mesmo fixture | Lock leve por fixture_id ou aceitar duplo lookup (idempotente) |

---

## 7. Testes

### 7.1 Unit

- [ ] `test_composite_returns_primary_when_available`
- [ ] `test_composite_falls_back_when_primary_returns_none`
- [ ] `test_composite_falls_back_when_primary_raises`
- [ ] `test_composite_returns_none_when_all_fail`
- [ ] `test_betano_odds_respects_min_score_threshold`
- [ ] `test_betano_odds_caches_event_id_after_first_resolve`
- [ ] `test_betano_odds_to_canonical_preserves_market_code`
- [ ] `test_apifootball_adapter_handles_missing_keys_in_raw`
- [ ] `test_drift_check_writes_jsonl_when_two_providers_differ`
- [ ] `test_drift_check_skips_when_only_one_provider_responds`
- [ ] `test_factory_returns_legacy_stack_when_flag_off`
- [ ] `test_factory_returns_new_stack_when_flag_on`

### 7.2 Integração

- [ ] `test_full_pipeline_with_betano_primary` (mocked)
- [ ] `test_full_pipeline_with_only_apifootball` (mocked)
- [ ] `test_orchestrator_continues_when_betano_warmup_fails` (mocked)

### 7.3 Smoke

- [ ] `providers_healthcheck.py` retorna exit 0 com `USE_NEW_PROVIDERS=false`
- [ ] Idem com `=true` (precisa cookies válidos)

---

## 8. Acceptance

- [ ] `data/odds_provider.py` define Protocol + Composite + dataclass canônica
- [ ] `data/stats_provider.py` idem para stats
- [ ] `data/providers/apifootball/` com 2 adapters NÃO modifica `api_client.py`
- [ ] `data/providers/betano/odds_adapter.py` + `stats_adapter.py` implementados
- [ ] `data/providers/factory.py` resolve stack via feature flag
- [ ] `main.py` (orquestrador) usa `CompositeOddsProvider` + `CompositeStatsProvider`
- [ ] `MIN_SCORE_TO_FETCH_ODDS`, `USE_NEW_PROVIDERS`, `DRIFT_CHECK_PROVIDERS` em settings
- [ ] `logs/provider_drift.jsonl` populado quando flag drift ativa
- [ ] `providers_healthcheck.py` retorna OK em prod-like
- [ ] Suite de testes E2E verde (15+ testes)
- [ ] Documentação `sistema-completo.md` §9 atualizada com a nova abstração
- [ ] Plano de rollout (gradual) documentado

---

## 9. Pilares cobertos

| Pilar | Contribuição |
|---|---|
| **Multi-fonte** | Composite real com cascata + drift check |
| **Conformidade** | Feature flag protege rollout, fallback automático |
| **Resiliência** | Falha de Betano não derruba pipeline (cai pro AF) |
| **Determinismo** | Dataclasses canônicas; adapter pattern |
| **Observabilidade** | Drift log + healthcheck consolidado |
| **Custo** | Trigger condicional (MIN_SCORE) protege chamadas caras |

---

## 10. Esforço estimado

| Sub-task | Horas |
|---|---|
| `odds_provider.py` (Protocol + Composite + canonical) | 1.0 |
| `stats_provider.py` (idem) | 1.0 |
| `apifootball/` adapters (2) | 1.5 |
| `betano/odds_adapter.py` + `stats_adapter.py` | 1.5 |
| `factory.py` + wiring | 1.0 |
| Refactor `main.py` para usar Composite | 1.5 |
| Drift logger | 0.5 |
| Healthcheck consolidado | 0.5 |
| Testes E2E (15+) | 1.5 |
| **Total** | **10h** |

---

## 11. Bloqueios potenciais

| Bloqueio | Resolução |
|---|---|
| `api_client.py` tem campos não óbvios pra mapear pra canonical | Inspecionar com cuidado, mas adapter é fino — sem reescrita |
| Orchestrator atual está acoplado a `api_client` em N lugares | Refactor em camadas: primeiro Composite no caminho principal, depois sub-fluxos |
| Testes E2E pedem mocks complexos | Usar `AsyncMock` da stdlib; fixtures por provider |
| Feature flag estiver `false` mas alguém quer testar Betano local | `scripts/betano_*_smoke.py` continua funcional independente |

---

## 12. Out of scope

- ❌ Persistência (Fase D)
- ❌ Sportradar provider real (eventualmente Fase E opcional)
- ❌ Migration entre formatos de odds históricos
- ❌ Detecção automática de "fixture com Betano disponível ou não" (cabe ao
     catalog na Fase B)
- ❌ Cache compartilhado entre orchestrator instances (single-instance por
     enquanto)
