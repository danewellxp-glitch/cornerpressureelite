"""BridgeStatsAdapter — provider de stats Betano via bridge HTTP (Fase E.1, CASO α).

Substitui o `BetanoStatsProvider` legado (Opta REST direto, bloqueado por 403 CF).
Caminho:
    bridge:8080/event/<id>/state
      → renewer (cookie `_cfuvid` + headers X-Operator/X-Language)
      → www.betano.bet.br/danae-webapi/api/live/events/<id>/latest

Schema do bridge: `{captured_at, event_id, version, from_cache, data: <full payload>}`.

Política de janelas: este adapter **não** calcula `corners_last_5/10min` nem
`yellow_last_5/10min`. Quem faz isso é `data.services.stats_window_calculator`
(Fase E.1 PARTE E'), a partir do histórico em `stats_history`. Aqui só preenche
o snapshot atual + `version` + `second_since_start`.

Cache de version por fixture: usado pra mandar `?if_version=N` no próximo
poll. Se bridge devolve 304, reaproveita o último `CanonicalStats` armazenado
em `_last_stats_cache`. Economiza ~134 KB de payload por poll quando nada
mudou.
"""
from __future__ import annotations

import logging
from dataclasses import replace
from typing import Any, Optional

import aiohttp

from data.odds_provider import CanonicalFixture
from data.stats_provider import CanonicalStats

log = logging.getLogger("cpes.providers.betano.bridge_stats")


class BridgeStatsAdapter:
    """Provider Betano via bridge HTTP. Implementa `StatsProvider` Protocol."""

    name = "bridge_betano"

    def __init__(
        self,
        bridge_url: str,
        fixture_repo: Any = None,
        timeout_seconds: float = 30.0,
        session: Optional[aiohttp.ClientSession] = None,
    ):
        self._bridge_url = bridge_url.rstrip("/")
        self._fixture_repo = fixture_repo
        self._timeout = aiohttp.ClientTimeout(total=timeout_seconds)
        self._owned_session: Optional[aiohttp.ClientSession] = (
            None if session is not None else None
        )
        self._injected_session = session

        # Cache de version + último CanonicalStats por fixture (pra 304).
        self._version_cache: dict[int, int] = {}
        self._last_stats_cache: dict[int, CanonicalStats] = {}
        # Cache fixture_id → event_id (resolvido via repo).
        self._event_id_cache: dict[int, int] = {}

    async def _session_instance(self) -> aiohttp.ClientSession:
        if self._injected_session is not None:
            return self._injected_session
        if self._owned_session is None or self._owned_session.closed:
            self._owned_session = aiohttp.ClientSession(timeout=self._timeout)
        return self._owned_session

    async def close(self) -> None:
        if self._owned_session is not None and not self._owned_session.closed:
            await self._owned_session.close()

    async def get_stats(self, fixture: CanonicalFixture) -> Optional[CanonicalStats]:
        """Busca snapshot do fixture via bridge `/event/<id>/state`.

        **Contrato de retorno**:

        | Cenário bridge / resolução | Retorno | `is_cached` | Semântica |
        |---|---|---|---|
        | HTTP 200 com payload válido | `CanonicalStats` | `False` | snapshot fresco |
        | HTTP 304 Not Modified, cache interno HIT | `CanonicalStats` cached | `True` | sem mudança; caller usa stats com minute possivelmente "frio" |
        | HTTP 304 Not Modified, cache interno MISS | re-fetch sem if_version → 200/erro | `False` ou `None` | edge case (cache externo > interno) |
        | `fixture_repo` não tem mapping | `None` | — | jogo não está em produção Betano |
        | HTTP 4xx/5xx | `None` | — | erro temporário — caller pode retry adaptativo |
        | Timeout / `aiohttp.ClientError` | `None` | — | erro temporário |
        | Payload sem `data.event.liveData` | `None` | — | schema inválido / cobertura zero |

        Orquestrador (PARTE F') usa `is_cached=True` pra:
        - **Recalcular minute** via `captured_at_ts` + clock próprio (snapshot frio).
        - **Não duplicar** no `StatsWindowCalculator` (não muda janelas).
        - **Persistir com flag** `source_freshness='cached'` (opcional, auditoria).

        Cache interno de `version` por fixture é usado pra mandar `if_version=N`
        no próximo poll (304 economiza ~134 KB de payload).
        """
        event_id = await self._resolve_event_id(fixture)
        if not event_id:
            log.debug(
                "bridge_stats.no_event_id fixture=%d", fixture.fixture_id,
            )
            return None

        cached_version = self._version_cache.get(fixture.fixture_id)
        url = f"{self._bridge_url}/event/{event_id}/state"
        params: dict[str, Any] = {}
        if cached_version is not None:
            params["if_version"] = cached_version

        try:
            session = await self._session_instance()
            async with session.get(url, params=params) as resp:
                if resp.status == 304:
                    cached_stats = self._last_stats_cache.get(fixture.fixture_id)
                    if cached_stats is not None:
                        log.debug(
                            "bridge_stats.unchanged fixture=%d event=%d version=%s cached_age=%ss",
                            fixture.fixture_id, event_id, cached_version,
                            _cached_age_seconds(cached_stats),
                        )
                        return replace(cached_stats, is_cached=True)
                    # Cache interno MISS + 304 externo: re-pede sem if_version
                    # pra repopular o cache. Edge case (acontece pós-restart).
                    log.info(
                        "bridge_stats.cache_miss_on_304 fixture=%d event=%d — refetching",
                        fixture.fixture_id, event_id,
                    )
                    async with session.get(url) as resp2:
                        if resp2.status != 200:
                            log.warning(
                                "bridge_stats.refetch_unexpected_status fixture=%d "
                                "event=%d status=%s",
                                fixture.fixture_id, event_id, resp2.status,
                            )
                            return None
                        payload = await resp2.json()
                else:
                    if resp.status >= 400:
                        log.warning(
                            "bridge_stats.http_error fixture=%d event=%d status=%s",
                            fixture.fixture_id, event_id, resp.status,
                        )
                        return None
                    payload = await resp.json()
        except aiohttp.ClientError as e:
            log.warning(
                "bridge_stats.client_error fixture=%d event=%d err=%s",
                fixture.fixture_id, event_id, e,
            )
            return None

        stats = self._parse(fixture, event_id, payload)
        if stats is None:
            return None

        # Atualiza caches (fresh — is_cached fica False, default do dataclass).
        if stats.version is not None:
            self._version_cache[fixture.fixture_id] = stats.version
        self._last_stats_cache[fixture.fixture_id] = stats
        return stats

    async def healthcheck(self) -> bool:
        url = f"{self._bridge_url}/health"
        try:
            session = await self._session_instance()
            async with session.get(url) as resp:
                return resp.status == 200
        except aiohttp.ClientError as e:
            log.warning("bridge_stats.healthcheck.error err=%s", e)
            return False

    async def _resolve_event_id(self, fixture: CanonicalFixture) -> Optional[int]:
        cached = self._event_id_cache.get(fixture.fixture_id)
        if cached:
            return cached
        if self._fixture_repo is None:
            return None
        try:
            ev = await self._fixture_repo.get_betano_event_id(fixture.fixture_id)
        except Exception as e:
            log.warning(
                "bridge_stats.repo_lookup_error fixture=%d err=%s",
                fixture.fixture_id, e,
            )
            return None
        if ev:
            self._event_id_cache[fixture.fixture_id] = int(ev)
            return int(ev)
        return None

    def _parse(
        self,
        fixture: CanonicalFixture,
        event_id: int,
        payload: dict,
    ) -> Optional[CanonicalStats]:
        """Normaliza payload do bridge em CanonicalStats.

        Robusto contra keys ausentes (cobertura varia por liga — ver
        `docs/architecture/betano-stats-api.md §5.2`).
        """
        data = payload.get("data") or {}
        event = data.get("event") or {}
        live = event.get("liveData") or {}
        results = live.get("results") or {}
        score = live.get("score") or {}
        clock = live.get("clock") or {}

        captured_at_raw = payload.get("captured_at")
        captured_at_ts: Optional[float] = None
        if isinstance(captured_at_raw, (int, float)):
            captured_at_ts = float(captured_at_raw)

        version = payload.get("version")
        if isinstance(version, str):
            try:
                version = int(version)
            except ValueError:
                version = None

        second_since_start = clock.get("secondsSinceStart")
        if isinstance(second_since_start, str):
            try:
                second_since_start = int(second_since_start)
            except ValueError:
                second_since_start = None

        minute = 0
        if isinstance(second_since_start, int) and second_since_start > 0:
            minute = second_since_start // 60

        corners = results.get("corners") or {}
        yellow = results.get("yellow") or {}
        shots = results.get("shots") or {}
        xgoals = results.get("xGoals") or {}

        return CanonicalStats(
            fixture_id=fixture.fixture_id,
            source=self.name,
            minute=minute,
            score_home=_safe_int(score.get("home"), fallback=fixture.score_home),
            score_away=_safe_int(score.get("away"), fallback=fixture.score_away),
            corners_home=_safe_int(corners.get("home")),
            corners_away=_safe_int(corners.get("away")),
            yellow_cards_home=_safe_int(yellow.get("home")),
            yellow_cards_away=_safe_int(yellow.get("away")),
            # Bridge /latest não traz red cards no liveData.results — só em incidents.
            # Deixa zero por ora; janela RCRD pode vir depois via incidents parser.
            red_cards_home=0,
            red_cards_away=0,
            # Betano não expõe shots_on_target / dangerous_attacks / possession
            # no liveData.results — gap aceitável pro MVP (ver §3 architecture doc).
            shots_on_target_home=_safe_int(shots.get("home")),
            shots_on_target_away=_safe_int(shots.get("away")),
            dangerous_attacks_home=0,
            dangerous_attacks_away=0,
            possession_home=0,
            possession_away=0,
            x_goals_home=_safe_float(xgoals.get("home")),
            x_goals_away=_safe_float(xgoals.get("away")),
            provider_pressure=None,  # Pressure score vem do score_engine, não daqui
            raw={
                "event_id": event_id,
                "from_cache": payload.get("from_cache", False),
                "captured_at": payload.get("captured_at"),
            },
            version=version if isinstance(version, int) else None,
            second_since_start=second_since_start
            if isinstance(second_since_start, int)
            else None,
            # Janelas — preenchidas a posteriori por StatsWindowCalculator.
            corners_last_5min=None,
            corners_last_10min=None,
            yellow_last_5min=None,
            yellow_last_10min=None,
            captured_at_ts=captured_at_ts,
            # is_cached default False (override no caller pra 304 HIT).
        )


def _safe_int(value: Any, *, fallback: int = 0) -> int:
    if value is None:
        return fallback
    try:
        return int(value)
    except (TypeError, ValueError):
        return fallback


def _safe_float(value: Any, *, fallback: float = 0.0) -> float:
    if value is None:
        return fallback
    try:
        return float(value)
    except (TypeError, ValueError):
        return fallback


def _cached_age_seconds(stats: CanonicalStats) -> str:
    """Idade do snapshot cached em segundos. Usado só pra log."""
    if stats.captured_at_ts is None:
        return "?"
    import time
    return f"{int(time.time() - stats.captured_at_ts)}"
