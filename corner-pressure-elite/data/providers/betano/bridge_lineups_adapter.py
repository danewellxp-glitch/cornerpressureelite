"""BridgeLineupsAdapter — lineups via bridge Betano (Fase G.1).

Reusa endpoint `/event/<id>/state` do bridge (mesmo da E.1 + F). Extrai
`event.roster` do payload — ZERO nova request HTTP.

# Schema do `event.roster` (do doc G.0 §1)

```json
{
  "homeRoster": { "id": int, "name": str, "players": { player_id: {...} } },
  "awayRoster": { ...análogo... },
  "unknownPlayers": { "<uuid>": {name, ...} },
  "lineups": {
    "homeLineup": { teamId, formation, lineup[][], benchPlayers[] },
    "awayLineup": { ...análogo... }
  }
}
```

# Política de normalização

- `formation`: `lineups.homeLineup.formation` direto.
- `starting_eleven`: flatten de `lineups.homeLineup.lineup[][]`. Cada item
  vira `PlayerEntry` cruzando com `homeRoster.players[playerId]` (pra
  pegar `shirtNumber`, `position`, `positionDisplayName`).
- `substitutes`: `lineups.homeLineup.benchPlayers[]`. Mesmo cross-ref.
- `coach_name`: sempre `None` (gap Betano).
- `unknownPlayerId` UUID → `player_id=None`, mantém nome.
- Cobertura zero (sem `homeLineup` ou `players` vazio): retorna
  `CanonicalLineup` com `starting_eleven=[]` (Composite cai pra AF).
"""
from __future__ import annotations

import logging
from typing import Any, Optional

import aiohttp

from data.lineups_provider import CanonicalLineup, PlayerEntry

log = logging.getLogger("cpes.providers.betano.bridge_lineups")


class BridgeLineupsAdapter:
    """Provider lineups via bridge HTTP. Implementa `LineupsProvider`."""

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
        self._injected_session = session
        self._owned_session: Optional[aiohttp.ClientSession] = None
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

    async def get_lineups(
        self,
        fixture_id: int,
        *,
        betano_event_id: Optional[int] = None,
        home_team_id: Optional[int] = None,
    ) -> Optional[list[CanonicalLineup]]:
        # home_team_id ignorado — Betano `roster.homeRoster`/`awayRoster` já vem
        # rotulado. Aceita kwarg pra compat com `LineupsProvider` Protocol.
        del home_team_id
        event_id = betano_event_id or await self._resolve_event_id(fixture_id)
        if not event_id:
            log.debug("bridge_lineups.no_event_id fixture=%d", fixture_id)
            return None

        url = f"{self._bridge_url}/event/{event_id}/state"
        try:
            session = await self._session_instance()
            async with session.get(url) as resp:
                if resp.status == 304:
                    # 304 = sem mudança no payload. Lineups são estáveis, mas
                    # adapter não tem cache próprio (worker desiste após gravar).
                    # Retorna [] pra worker tratar como "sem novidade".
                    return []
                if resp.status >= 400:
                    log.warning(
                        "bridge_lineups.http_error fixture=%d event=%d status=%s",
                        fixture_id, event_id, resp.status,
                    )
                    return None
                payload = await resp.json()
        except aiohttp.ClientError as e:
            log.warning(
                "bridge_lineups.client_error fixture=%d event=%d err=%s",
                fixture_id, event_id, e,
            )
            return None

        return self._parse(fixture_id, payload)

    async def healthcheck(self) -> bool:
        url = f"{self._bridge_url}/health"
        try:
            session = await self._session_instance()
            async with session.get(url) as resp:
                return resp.status == 200
        except aiohttp.ClientError as e:
            log.warning("bridge_lineups.healthcheck.error err=%s", e)
            return False

    async def _resolve_event_id(self, fixture_id: int) -> Optional[int]:
        cached = self._event_id_cache.get(fixture_id)
        if cached:
            return cached
        if self._fixture_repo is None:
            return None
        try:
            ev = await self._fixture_repo.get_betano_event_id(fixture_id)
        except Exception as e:
            log.warning(
                "bridge_lineups.repo_lookup_error fixture=%d err=%s",
                fixture_id, e,
            )
            return None
        if ev:
            self._event_id_cache[fixture_id] = int(ev)
            return int(ev)
        return None

    def _parse(self, fixture_id: int, payload: dict) -> list[CanonicalLineup]:
        """Extrai `event.roster` + monta 2 CanonicalLineup (home + away).

        Cobertura zero (sem lineups OR players vazios) retorna lineups
        com `starting_eleven=[]` — Composite usa pra cair pra fallback.
        """
        data = payload.get("data") or {}
        event = data.get("event") or {}
        roster = event.get("roster") or {}
        version = data.get("version") if isinstance(data.get("version"), int) else None

        sides = [
            self._build_side(
                fixture_id=fixture_id,
                team_side="home",
                team_roster=roster.get("homeRoster") or {},
                lineup_obj=(roster.get("lineups") or {}).get("homeLineup") or {},
                version=version,
                raw=roster,
            ),
            self._build_side(
                fixture_id=fixture_id,
                team_side="away",
                team_roster=roster.get("awayRoster") or {},
                lineup_obj=(roster.get("lineups") or {}).get("awayLineup") or {},
                version=version,
                raw=roster,
            ),
        ]
        # AJUSTE 4c — coach gap log DEBUG (não polui INFO).
        for ln in sides:
            if ln.coach_name is None:
                log.debug(
                    "lineups_betano.coach_missing fixture=%d team_side=%s "
                    "(gap conhecido — BETANO_GAPS_LINEUPS)",
                    fixture_id, ln.team_side,
                )
        return sides

    def _build_side(
        self,
        *,
        fixture_id: int,
        team_side: str,
        team_roster: dict,
        lineup_obj: dict,
        version: Optional[int],
        raw: dict,
    ) -> CanonicalLineup:
        # Squad lookup map (player_id -> dict de detalhes)
        players_map = team_roster.get("players") or {}
        if not isinstance(players_map, dict):
            players_map = {}

        # Starting XI: flatten do lineup[][] tactical_grid
        tactical_grid_raw = lineup_obj.get("lineup") or []
        starting_eleven: list[PlayerEntry] = []
        tactical_grid: list[list[int]] = []
        for row in tactical_grid_raw:
            if not isinstance(row, list):
                continue
            row_ids: list[int] = []
            for entry in row:
                if not isinstance(entry, dict):
                    continue
                player = self._resolve_player(
                    entry, players_map, is_substitute=False, fixture_id=fixture_id,
                )
                if player is None:
                    continue
                starting_eleven.append(player)
                if player.player_id is not None:
                    row_ids.append(player.player_id)
            tactical_grid.append(row_ids)

        # Bench
        bench_raw = lineup_obj.get("benchPlayers") or []
        substitutes: list[PlayerEntry] = []
        for entry in bench_raw:
            if not isinstance(entry, dict):
                continue
            player = self._resolve_player(
                entry, players_map, is_substitute=True, fixture_id=fixture_id,
            )
            if player is not None:
                substitutes.append(player)

        return CanonicalLineup(
            fixture_id=fixture_id,
            source=self.name,
            team_side=team_side,
            formation=lineup_obj.get("formation") if isinstance(lineup_obj.get("formation"), str) else None,
            coach_name=None,                     # gap Betano (documentado em BETANO_GAPS_LINEUPS)
            starting_eleven=starting_eleven,
            substitutes=substitutes,
            tactical_grid=tactical_grid if tactical_grid else None,
            version=version,
            raw=raw,
        )

    @staticmethod
    def _resolve_player(
        entry: dict,
        players_map: dict,
        *,
        is_substitute: bool,
        fixture_id: Optional[int] = None,
    ) -> Optional[PlayerEntry]:
        """entry vem do lineup[][] OR benchPlayers[].
        Cross-ref com players_map pra detalhes ricos.

        AJUSTE 1 pós-review: NUNCA descartar entry — preserva lineup com 11
        entries mesmo quando ID falta (descartar mascarava cobertura). Sem
        nome E sem ID retorna `PlayerEntry(name='<unknown>', player_id=None)`.
        """
        player_id_raw = entry.get("playerId")
        unknown_id = entry.get("unknownPlayerId")
        raw_name = entry.get("name")
        name = raw_name if isinstance(raw_name, str) and raw_name else None

        player_id: Optional[int] = None
        details: dict = {}

        if isinstance(player_id_raw, int):
            player_id = player_id_raw
            # Cross-ref no roster pra detalhes ricos.
            details = (
                players_map.get(str(player_id))
                or players_map.get(player_id)
                or {}
            )
            # Se entry sem nome, tenta do roster.players[id].
            if name is None:
                roster_name = details.get("name")
                if isinstance(roster_name, str) and roster_name:
                    name = roster_name
        elif isinstance(unknown_id, str):
            # Unknown — sem detalhes ricos. Persiste só nome.
            player_id = None
        else:
            # Nem playerId nem unknownPlayerId — anômalo mas não descarta.
            # Log WARNING pra investigação futura (schema Betano mudou?).
            log.warning(
                "lineups.player_no_id fixture=%s entry_keys=%s",
                fixture_id, list(entry.keys()),
            )
            player_id = None

        return PlayerEntry(
            name=name or "<unknown>",
            player_id=player_id,
            position=details.get("position")
            if isinstance(details.get("position"), str)
            else None,
            position_display=details.get("positionDisplayName")
            if isinstance(details.get("positionDisplayName"), str)
            else None,
            shirt_number=details.get("shirtNumber")
            if isinstance(details.get("shirtNumber"), int)
            else None,
            is_substitute=is_substitute,
        )
