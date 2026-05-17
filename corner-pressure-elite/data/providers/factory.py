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
    use_betano_stats = bool(getattr(settings, "USE_BETANO_STATS", False))
    drift = bool(getattr(settings, "DRIFT_CHECK_PROVIDERS", False))

    # Foot-gun pré-PARTE F': USE_NEW_PROVIDERS=true sem caminho bridge
    # degrada stats pra AF-only. Em produção atual a chave AF tá vencida,
    # então sem Betano stats = pipeline cego. Avisa alto.
    if use_new and not (use_bridge and use_betano_stats):
        log.warning(
            "providers.foot_gun USE_NEW_PROVIDERS=true sem (USE_BETANO_BRIDGE+USE_BETANO_STATS) "
            "→ stats degradado pra apifootball-only. Se a chave AF está vencida/sem cota, "
            "score_engine vai operar sem dados frescos. Ativar BridgeStatsAdapter (PARTE F') "
            "ou setar USE_BETANO_BRIDGE=true + USE_BETANO_STATS=true antes do deploy."
        )

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
            persistence_worker=odds_persistence_worker,
        )

        # ----- Stats stack — depende de USE_BETANO_STATS (PARTE F') -----
        composite_stats: CompositeStatsProvider
        bridge_stats_adapter = None
        if use_betano_stats:
            from .betano.bridge_stats_adapter import BridgeStatsAdapter

            bridge_stats_adapter = BridgeStatsAdapter(
                bridge_url=getattr(settings, "BETANO_BRIDGE_URL", "http://localhost:8080"),
                fixture_repo=fixture_repo,
                timeout_seconds=float(
                    getattr(settings, "BETANO_BRIDGE_TIMEOUT_SEC", 25.0)
                ),
            )
            composite_stats = CompositeStatsProvider(
                [bridge_stats_adapter, af_stats], drift_check=drift,
            )
            log.info(
                "providers.bridge_stats enabled primary=bridge_betano fallback=apifootball drift=%s",
                drift,
            )
        else:
            composite_stats = CompositeStatsProvider([af_stats], drift_check=drift)
            log.info("providers.bridge_stats disabled — stats apifootball-only")

        async def _bridge_shutdown() -> None:
            await bridge_client.close()
            if bridge_stats_adapter is not None:
                await bridge_stats_adapter.close()

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
            composite_stats,
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

    # ----- Stack nova: Betano odds primary + AF stats fallback -----
    # NOTA Fase E.1: o `BetanoStatsProvider` (Opta REST direto) foi removido
    # nessa fase porque a Betano passou a bloquear o endpoint Opta com 403 CF
    # sem warmup. Stats Betano agora vêm pelo bridge (`BridgeStatsAdapter`),
    # wirado quando USE_BETANO_BRIDGE=true + USE_BETANO_STATS=true (PARTE F').
    # Enquanto esse caminho está vivo (USE_NEW_PROVIDERS=true sem bridge),
    # odds continua vindo do Betano session direto e stats degrada pra AF only.
    from .betano import (
        BetanoCatalog,
        BetanoMarkets,
        BetanoSession,
    )
    from .betano.odds_adapter import BetanoOddsProvider

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

    composite_odds = CompositeOddsProvider(
        [bet_odds, af_odds],
        drift_check=drift,
        persistence_worker=odds_persistence_worker,
    )
    composite_stats = CompositeStatsProvider([af_stats], drift_check=drift)

    async def shutdown() -> None:
        await session.close()

    log.info(
        "providers.new_stack primary_odds=betano stats=apifootball-only drift=%s min_score=%d",
        drift, min_score,
    )
    # garante que callers possam aguardar mesmo se shutdown for não-async no futuro
    if not inspect.iscoroutinefunction(shutdown):  # defesa contra refactor futuro
        async def _wrap():
            shutdown()  # type: ignore[func-returns-value]
        return composite_odds, composite_stats, _wrap
    return composite_odds, composite_stats, shutdown


# ---------------------------------------------------------------------------
# Events provider factory (Fase F — dataset puro)
# ---------------------------------------------------------------------------

async def build_events_provider(
    settings: Any,
    api_client: Any,
    *,
    fixture_repo: Any = None,
) -> Tuple["CompositeEventsProvider", ShutdownFn]:
    """Constrói `CompositeEventsProvider` (Betano bridge primary + AF fallback).

    Pré-condição: caller já checou `USE_BETANO_BRIDGE and USE_BETANO_STATS`
    (ou política equivalente) — esta função NÃO valida flags, só monta.

    Retorna `(provider, shutdown_async)`. Shutdown fecha sessions HTTP do
    bridge adapter.
    """
    from data.events_provider import CompositeEventsProvider
    from data.providers.betano.bridge_events_adapter import BridgeEventsAdapter
    from data.providers.apifootball.events_adapter import APIFootballEventsAdapter

    bridge_url = getattr(settings, "BETANO_BRIDGE_URL", "http://localhost:8080")
    timeout = float(getattr(settings, "BETANO_BRIDGE_TIMEOUT_SEC", 25.0))

    bridge_events = BridgeEventsAdapter(
        bridge_url=bridge_url,
        fixture_repo=fixture_repo,
        timeout_seconds=timeout,
    )
    af_events = APIFootballEventsAdapter(api_client)
    composite = CompositeEventsProvider([bridge_events, af_events])

    async def shutdown() -> None:
        await bridge_events.close()

    log.info(
        "providers.events_stack primary=bridge_betano fallback=apifootball bridge_url=%s",
        bridge_url,
    )
    return composite, shutdown


async def build_lineups_provider(
    settings: Any,
    api_client: Any,
    *,
    fixture_repo: Any = None,
) -> Tuple["CompositeLineupsProvider", ShutdownFn]:
    """Constrói `CompositeLineupsProvider` (Betano bridge primary + AF fallback).

    Pré-condição: caller já checou `USE_BETANO_BRIDGE and USE_BETANO_LINEUPS`.
    Mesmo padrão de `build_events_provider`.
    """
    from data.lineups_provider import CompositeLineupsProvider
    from data.providers.betano.bridge_lineups_adapter import BridgeLineupsAdapter
    from data.providers.apifootball.lineups_adapter import APIFootballLineupsAdapter

    bridge_url = getattr(settings, "BETANO_BRIDGE_URL", "http://localhost:8080")
    timeout = float(getattr(settings, "BETANO_BRIDGE_TIMEOUT_SEC", 25.0))

    bridge_lineups = BridgeLineupsAdapter(
        bridge_url=bridge_url,
        fixture_repo=fixture_repo,
        timeout_seconds=timeout,
    )
    af_lineups = APIFootballLineupsAdapter(api_client)
    composite = CompositeLineupsProvider([bridge_lineups, af_lineups])

    async def shutdown() -> None:
        await bridge_lineups.close()

    log.info(
        "providers.lineups_stack primary=bridge_betano fallback=apifootball bridge_url=%s",
        bridge_url,
    )
    return composite, shutdown
