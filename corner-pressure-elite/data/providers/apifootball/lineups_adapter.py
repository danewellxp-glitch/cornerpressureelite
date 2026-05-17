"""APIFootballLineupsAdapter — fallback de lineups via API-Football (Fase G.1).

Encapsula `api_client.get_lineups` legado como `LineupsProvider`.

# Schema response AF (`GET /fixtures/lineups?fixture=ID`)

```json
{
  "response": [
    {
      "team": {"id": 33, "name": "Manchester United", "logo": "..."},
      "formation": "4-2-3-1",
      "coach": {"id": 2407, "name": "E. ten Hag"},
      "startXI": [
        {"player": {"id": 882, "name": "D. de Gea", "number": 1, "pos": "G", "grid": "1:1"}}
      ],
      "substitutes": [
        {"player": {"id": 2935, "name": "T. Heaton", "number": 22, "pos": "G", "grid": null}}
      ]
    },
    { ...away team... }
  ]
}
```

# Mapping AF → Canonical

| AF                              | CanonicalLineup     |
|---------------------------------|---------------------|
| `formation`                     | `formation`         |
| `coach.name`                    | `coach_name` ⭐     |
| `startXI[].player.{name,id,number,pos}` | `starting_eleven[PlayerEntry]` |
| `substitutes[].player`          | `substitutes[PlayerEntry]` (is_substitute=True) |
| AF `pos` G/D/M/F                | canonical `position` GK/DF/MF/FW |

Resolução de `team_side` requer `home_team_id` hint (igual events adapter).
Pra `LineupsProvider` esse hint vem opcional via kwarg `home_team_id` — adapter
extrai do response AF se possível (response geralmente tem 2 items com
team.id; primeiro = home convencionalmente OR via lookup com hint).

Se AF não cobrir o fixture (response vazio), retorna `[]` (caller decide).
"""
from __future__ import annotations

import logging
from typing import Any, Optional

from data.lineups_provider import CanonicalLineup, PlayerEntry

log = logging.getLogger("cpes.providers.apifootball.lineups")


# AF pos one-letter → canonical 2-letter.
_AF_POS_MAP: dict[str, str] = {
    "G": "GK",
    "D": "DF",
    "M": "MF",
    "F": "FW",
}


def _map_position(af_pos: Optional[str]) -> Optional[str]:
    """AF pos one-letter → canonical 2-letter. Fallback upper() com log warning."""
    if not isinstance(af_pos, str) or not af_pos:
        return None
    mapped = _AF_POS_MAP.get(af_pos.upper())
    if mapped:
        return mapped
    log.warning(
        "lineups_af.unmapped_position pos=%r — using upper() fallback",
        af_pos,
    )
    return af_pos.upper()


class APIFootballLineupsAdapter:
    """Provider AF via APIFootballClient. Implementa `LineupsProvider`."""

    name = "apifootball"

    def __init__(self, api_client: Any):
        self._client = api_client

    async def get_lineups(
        self,
        fixture_id: int,
        *,
        betano_event_id: Optional[int] = None,
        home_team_id: Optional[int] = None,
    ) -> Optional[list[CanonicalLineup]]:
        """Busca lineups via AF.

        - `betano_event_id`: ignorado (compat Protocol).
        - `home_team_id`: hint pra resolver `team_side`. AF response tem 2
          entries com `team.id` — quando hint passado, casa por id; quando
          ausente, cai na convenção `response[0]=home, [1]=away` (bug
          latente, log debug).
        """
        try:
            raw = await self._client.get_lineups(fixture_id)
        except AttributeError:
            # api_client legado não tem get_lineups — retorna None silencioso
            # (worker registra warning genérico). Esperado durante transição.
            log.debug(
                "apifootball_lineups.client_missing_method fixture=%d", fixture_id
            )
            return None
        except Exception as e:
            log.warning(
                "apifootball_lineups.client_error fixture=%d err=%s",
                fixture_id, e,
            )
            return None
        if not isinstance(raw, list) or len(raw) == 0:
            return []

        home_block: Optional[dict] = None
        away_block: Optional[dict] = None

        if home_team_id is not None:
            # Resolução defensiva via team.id (correto).
            for block in raw:
                if not isinstance(block, dict):
                    continue
                team = block.get("team") or {}
                tid = team.get("id") if isinstance(team, dict) else None
                if tid == home_team_id and home_block is None:
                    home_block = block
                elif tid != home_team_id and away_block is None:
                    away_block = block
        else:
            # Fallback: convenção response[0]=home, [1]=away (frágil).
            log.debug(
                "lineups_af.using_order_convention fixture=%d home_team_id missing",
                fixture_id,
            )
            home_block = raw[0] if isinstance(raw[0], dict) else None
            away_block = raw[1] if len(raw) > 1 and isinstance(raw[1], dict) else None

        out: list[CanonicalLineup] = []
        if home_block is not None:
            out.append(self._normalize_team(fixture_id, "home", home_block))
        if away_block is not None:
            out.append(self._normalize_team(fixture_id, "away", away_block))
        return out

    async def healthcheck(self) -> bool:
        try:
            status = await self._client.check_status()
            return isinstance(status, dict) and status.get("requests") is not None
        except Exception as e:
            log.warning("apifootball_lineups.healthcheck.error err=%s", e)
            return False

    def _normalize_team(
        self, fixture_id: int, team_side: str, block: dict
    ) -> CanonicalLineup:
        formation = block.get("formation") if isinstance(block.get("formation"), str) else None
        coach = block.get("coach") or {}
        coach_name = coach.get("name") if isinstance(coach, dict) else None
        if not isinstance(coach_name, str):
            coach_name = None

        starting_eleven = [
            p
            for p in (
                self._normalize_player(item, is_substitute=False)
                for item in (block.get("startXI") or [])
            )
            if p is not None
        ]
        substitutes = [
            p
            for p in (
                self._normalize_player(item, is_substitute=True)
                for item in (block.get("substitutes") or [])
            )
            if p is not None
        ]

        return CanonicalLineup(
            fixture_id=fixture_id,
            source=self.name,
            team_side=team_side,
            formation=formation,
            coach_name=coach_name,
            starting_eleven=starting_eleven,
            substitutes=substitutes,
            tactical_grid=None,    # AF não traz lineup[][] (só startXI flat)
            version=None,
            raw=block,
        )

    @staticmethod
    def _normalize_player(
        item: Any, *, is_substitute: bool
    ) -> Optional[PlayerEntry]:
        if not isinstance(item, dict):
            return None
        player = item.get("player") or {}
        if not isinstance(player, dict):
            return None
        name = player.get("name")
        if not isinstance(name, str) or not name:
            return None
        pid = player.get("id")
        number = player.get("number")
        return PlayerEntry(
            name=name,
            player_id=pid if isinstance(pid, int) else None,
            position=_map_position(player.get("pos")),
            position_display=None,  # AF não traz localizado
            shirt_number=number if isinstance(number, int) else None,
            is_substitute=is_substitute,
        )
