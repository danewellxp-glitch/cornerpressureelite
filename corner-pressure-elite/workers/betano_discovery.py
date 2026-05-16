"""Worker assíncrono que descobre fixtures Betano automaticamente.

Loop:
  1. Pega eventos ao vivo da Betano via bridge `/events/live` (sport=FOOT).
  2. Pega fixtures candidatos via api_client.get_today_schedule.
  3. Pra cada evento Betano, chama FixtureMatcher.match_event.
  4. Se match (>= threshold), UPSERT em betano_fixture_map via FixtureMapRepo.
  5. Sleep BETANO_DISCOVERY_POLL_SEC, repete.

ADIADO até PARTE A: refresh do catálogo Betano via bridge /teams 1×/dia.
Sem isso, betano_team_map populado SOMENTE on-demand pelos matches fuzzy.

Padrão de start/stop espelha OddsPersistenceWorker (asyncio.Task + CancelledError).
"""
from __future__ import annotations

import asyncio
import logging
import time
from datetime import datetime, timezone
from typing import Optional

import httpx

from data.discovery.fixture_matcher import FixtureMatcher
from data.repositories.betano_team_map import BetanoTeamMapRepo
from data.repositories.fixture_map import FixtureMapRepo

log = logging.getLogger("cpes.worker.betano_discovery")


class BetanoFixtureDiscovery:
    def __init__(
        self,
        bridge_url: str,
        api_client,
        matcher: FixtureMatcher,
        fixture_repo: FixtureMapRepo,
        team_repo: BetanoTeamMapRepo,
        league_ids: list[int],
        poll_sec: int = 150,
        request_timeout: float = 30.0,
        sport: str = "FOOT",
    ):
        self._bridge_url = bridge_url.rstrip("/")
        self._api_client = api_client
        self._matcher = matcher
        self._fixture_repo = fixture_repo
        self._team_repo = team_repo
        self._league_ids = list(league_ids)
        self._poll_sec = int(poll_sec)
        self._timeout = float(request_timeout)
        self._sport = sport
        self._task: Optional[asyncio.Task] = None
        # Cache simples por ciclo do schedule (evita re-fetch desnecessário)
        self._schedule_cache: list[dict] = []
        self._schedule_cache_date: Optional[str] = None

    async def start(self) -> None:
        if self._task and not self._task.done():
            log.warning("BetanoFixtureDiscovery já está rodando")
            return
        self._task = asyncio.create_task(self._loop(), name="betano-discovery")
        log.info(
            "BetanoFixtureDiscovery iniciado (poll=%ds, sport=%s, ligas=%d)",
            self._poll_sec, self._sport, len(self._league_ids),
        )

    async def stop(self) -> None:
        if not self._task:
            return
        self._task.cancel()
        try:
            await self._task
        except asyncio.CancelledError:
            pass
        self._task = None
        log.info("BetanoFixtureDiscovery parado")

    async def _loop(self) -> None:
        while True:
            try:
                await self._tick()
            except asyncio.CancelledError:
                raise
            except Exception:
                log.exception("Erro no ciclo de descoberta — continua")
            await asyncio.sleep(self._poll_sec)

    async def _tick(self) -> None:
        """1 ciclo de descoberta. Fail-soft: 1 erro não para o loop."""
        # 1. Pega eventos do bridge
        events = await self._fetch_bridge_events()
        if not events:
            log.debug("nenhum evento Betano FOOT retornado pelo bridge")
            return

        # 2. Pega candidate fixtures (com cache por dia)
        fixtures = await self._get_today_schedule()
        if not fixtures:
            log.warning("get_today_schedule retornou vazio — sem candidatos pra match")
            return

        # 3. Match + UPSERT por evento
        matched = 0
        skipped = 0
        for ev in events:
            try:
                result = await self._matcher.match_event(ev, fixtures)
            except Exception:
                log.exception("matcher falhou em event_id=%s", ev.get("event_id"))
                skipped += 1
                continue

            if result is None:
                skipped += 1
                continue

            try:
                await self._fixture_repo.upsert(
                    fixture_id=result.fixture_id,
                    betano_event_id=result.betano_event_id,
                    home_team=result.home_team,
                    away_team=result.away_team,
                    league_id=result.league_id,
                    kickoff_utc=result.kickoff_utc,
                    resolved_via=f"discovery_{result.method}",
                )
                matched += 1
                log.info(
                    "MATCH event_id=%s → fixture_id=%s method=%s confidence=%.2f (%s x %s)",
                    result.betano_event_id, result.fixture_id, result.method,
                    result.confidence, result.home_team, result.away_team,
                )
            except Exception:
                log.exception("UPSERT fixture_map falhou pra fixture_id=%s", result.fixture_id)

        log.info(
            "ciclo descoberta: %d eventos, %d matches, %d skipped",
            len(events), matched, skipped,
        )

    async def _fetch_bridge_events(self) -> list[dict]:
        """GET /events/live no bridge da odin. Retorna lista de eventos ou []."""
        url = f"{self._bridge_url}/events/live"
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                r = await client.get(url, params={"sport": self._sport})
            r.raise_for_status()
            data = r.json()
            return data.get("events", []) or []
        except httpx.HTTPError as e:
            log.warning("bridge /events/live falhou: %s", e)
            return []
        except Exception:
            log.exception("erro inesperado ao buscar /events/live")
            return []

    async def _get_today_schedule(self) -> list[dict]:
        """Cache simples por dia. Re-fetch só quando muda o dia (UTC)."""
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        if self._schedule_cache_date == today and self._schedule_cache:
            return self._schedule_cache
        try:
            fixtures = await self._api_client.get_today_schedule(self._league_ids, today)
        except Exception:
            log.exception("api_client.get_today_schedule falhou")
            return self._schedule_cache  # devolve cache stale se houver
        self._schedule_cache = fixtures or []
        self._schedule_cache_date = today
        log.info(
            "schedule do dia atualizado: %d fixtures candidatos (date=%s, ligas=%d)",
            len(self._schedule_cache), today, len(self._league_ids),
        )
        return self._schedule_cache
