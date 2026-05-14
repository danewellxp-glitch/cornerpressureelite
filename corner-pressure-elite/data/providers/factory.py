"""Factory que monta os Composite providers conforme feature flags.

Uso:
    odds_provider, stats_provider, shutdown = await build_providers(config_module)
    try:
        odds = await odds_provider.get_corners(fixture, score)
    finally:
        await shutdown()

Default (`USE_NEW_PROVIDERS=false`): só API-Football. Caminho idêntico ao
legado em `main.py`, com a única diferença de passar pelo Composite — útil
para ganhar drift_check e hooks de persistência mesmo sem ativar o Betano.
"""
from __future__ import annotations

import inspect
import logging
from pathlib import Path
from typing import Any, Awaitable, Callable, Tuple

from data.odds_provider import CompositeOddsProvider
from data.stats_provider import CompositeStatsProvider

log = logging.getLogger("cpes.providers.factory")

ShutdownFn = Callable[[], Awaitable[None]]


async def _noop_shutdown() -> None:
    return None


async def build_providers(
    settings: Any,
    api_client: Any,
    *,
    fixture_repo: Any = None,
    odds_persistence_worker: Any = None,
) -> Tuple[CompositeOddsProvider, CompositeStatsProvider, ShutdownFn]:
    """Constrói os Composite providers e retorna `(odds, stats, shutdown)`.

    `api_client` deve ser uma instância de `APIFootballClient` já inicializada
    (orquestrador é dono do ciclo de vida). `fixture_repo` e
    `odds_persistence_worker` vêm da Fase D quando habilitada.
    """
    from data.providers.apifootball import (
        APIFootballOddsProvider,
        APIFootballStatsProvider,
    )

    af_odds = APIFootballOddsProvider(api_client)
    af_stats = APIFootballStatsProvider(api_client)

    use_bridge = bool(getattr(settings, "USE_BETANO_BRIDGE", False))
    use_new = bool(getattr(settings, "USE_NEW_PROVIDERS", False))
    drift = bool(getattr(settings, "DRIFT_CHECK_PROVIDERS", False))

    if use_bridge:
        if use_new:
            log.warning(
                "providers.bridge.coexists USE_BETANO_BRIDGE e USE_NEW_PROVIDERS=True — bridge ganha"
            )
        from .betano_bridge import BetanoBridgeClient, BetanoBridgeOddsAdapter

        bridge_client = BetanoBridgeClient(
            base_url=getattr(settings, "BETANO_BRIDGE_URL", "http://localhost:8080"),
            timeout_sec=float(getattr(settings, "BETANO_BRIDGE_TIMEOUT_SEC", 25.0)),
            capture_sec=float(getattr(settings, "BETANO_BRIDGE_CAPTURE_SEC", 15.0)),
            retries=int(getattr(settings, "BETANO_BRIDGE_RETRIES", 1)),
        )
        min_score = int(getattr(settings, "MIN_SCORE_TO_FETCH_ODDS", 0))
        bridge_odds = BetanoBridgeOddsAdapter(
            client=bridge_client,
            fixture_repo=fixture_repo,
            min_score=min_score,
            odd_min=float(getattr(settings, "BETANO_BRIDGE_PREFERRED_ODD_MIN", 1.50)),
            odd_max=float(getattr(settings, "BETANO_BRIDGE_PREFERRED_ODD_MAX", 1.70)),
        )

        async def _bridge_shutdown() -> None:
            await bridge_client.close()

        log.info(
            "providers.bridge_stack primary=betano_bridge fallback=apifootball drift=%s min_score=%d",
            drift, min_score,
        )
        return (
            CompositeOddsProvider(
                [bridge_odds, af_odds],
                drift_check=drift,
                persistence_worker=odds_persistence_worker,
            ),
            CompositeStatsProvider([af_stats], drift_check=drift),
            _bridge_shutdown,
        )

    if not use_new:
        log.info("providers.legacy stack=apifootball-only drift=%s", drift)
        return (
            CompositeOddsProvider(
                [af_odds],
                drift_check=drift,
                persistence_worker=odds_persistence_worker,
            ),
            CompositeStatsProvider([af_stats], drift_check=drift),
            _noop_shutdown,
        )

    # ----- Stack nova: Betano primary + AF fallback -----
    from .betano import (
        BetanoCatalog,
        BetanoMarkets,
        BetanoSession,
        BetanoStatsStream,
    )
    from .betano.odds_adapter import BetanoOddsProvider
    from .betano.stats_adapter import BetanoStatsProvider

    cookies_path = Path(getattr(settings, "BETANO_COOKIES_PATH", "config/betano_cookies.json"))
    proxies_csv = getattr(settings, "WEBSHARE_PROXIES", "") or ""
    proxies = [p.strip() for p in proxies_csv.split(",") if p.strip()] or None

    if cookies_path.exists():
        session = BetanoSession.from_file(cookies_path)
        if proxies:
            session._proxies = proxies
    else:
        log.warning(
            "providers.betano.cookies_missing path=%s — Betano vai falhar até warmup",
            cookies_path,
        )
        session = BetanoSession(cookies={}, proxies=proxies)

    stream = BetanoStatsStream(session)
    markets = BetanoMarkets(session)
    catalog = BetanoCatalog(session)

    min_score = int(getattr(settings, "MIN_SCORE_TO_FETCH_ODDS", 0))

    bet_odds = BetanoOddsProvider(
        session=session,
        markets=markets,
        catalog=catalog,
        min_score=min_score,
        fixture_repo=fixture_repo,
    )
    bet_stats = BetanoStatsProvider(
        session=session,
        stream=stream,
        catalog=catalog,
        fixture_repo=fixture_repo,
    )

    composite_odds = CompositeOddsProvider(
        [bet_odds, af_odds],
        drift_check=drift,
        persistence_worker=odds_persistence_worker,
    )
    composite_stats = CompositeStatsProvider(
        [bet_stats, af_stats],
        drift_check=drift,
    )

    async def shutdown() -> None:
        await session.close()

    log.info(
        "providers.new_stack primary=betano fallback=apifootball drift=%s min_score=%d",
        drift, min_score,
    )
    # garante que callers possam aguardar mesmo se shutdown for não-async no futuro
    if not inspect.iscoroutinefunction(shutdown):  # defesa contra refactor futuro
        async def _wrap():
            shutdown()  # type: ignore[func-returns-value]
        return composite_odds, composite_stats, _wrap
    return composite_odds, composite_stats, shutdown
