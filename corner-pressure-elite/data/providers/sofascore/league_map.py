"""Mapping CPES (API-Football) league_id → SofaScore tournament/season IDs.

`unique_tournament_id` é estável (Brasileirão A = 325 sempre). `season_id`
muda a cada temporada — quando faltar (`None`), K.1 deve buscar via
`/unique-tournament/{id}/seasons` no startup ou cachear no DB.
"""
from __future__ import annotations

from typing import Optional


# {api_football_league_id: {unique_tournament_id, season_id_current, name, country}}
SOFASCORE_LEAGUE_MAP: dict[int, dict] = {
    71: {  # Brasileirão Série A
        "unique_tournament_id": 325,
        "season_id_current": 87678,
        "name": "Brasileirão Série A",
        "country": "BR",
    },
    72: {  # Brasileirão Série B
        "unique_tournament_id": 390,
        "season_id_current": None,
        "name": "Brasileirão Série B",
        "country": "BR",
    },
    73: {  # Copa do Brasil
        "unique_tournament_id": 373,
        "season_id_current": None,
        "name": "Copa do Brasil",
        "country": "BR",
    },
    39: {  # Premier League
        "unique_tournament_id": 17,
        "season_id_current": None,
        "name": "Premier League",
        "country": "EN",
    },
    140: {  # La Liga
        "unique_tournament_id": 8,
        "season_id_current": None,
        "name": "La Liga",
        "country": "ES",
    },
    135: {  # Serie A Italia
        "unique_tournament_id": 23,
        "season_id_current": None,
        "name": "Serie A",
        "country": "IT",
    },
    78: {  # Bundesliga
        "unique_tournament_id": 35,
        "season_id_current": None,
        "name": "Bundesliga",
        "country": "DE",
    },
    88: {  # Eredivisie
        "unique_tournament_id": 37,
        "season_id_current": None,
        "name": "Eredivisie",
        "country": "NL",
    },
    94: {  # Liga Portugal
        "unique_tournament_id": 238,
        "season_id_current": None,
        "name": "Liga Portugal",
        "country": "PT",
    },
    128: {  # Liga Profesional Argentina
        "unique_tournament_id": 155,
        "season_id_current": None,
        "name": "Liga Profesional Argentina",
        "country": "AR",
    },
    253: {  # MLS
        "unique_tournament_id": 242,
        "season_id_current": 86668,
        "name": "Major League Soccer",
        "country": "US",
    },
    # Champions League (não-monitorada hoje, mas mapeada pra futuro)
    2: {
        "unique_tournament_id": 7,
        "season_id_current": None,
        "name": "UEFA Champions League",
        "country": "EU",
    },
}


def get_sofascore_ids(
    af_league_id: int,
) -> Optional[tuple[int, Optional[int]]]:
    """Returns (unique_tournament_id, season_id_current) ou None se não mapeado.

    `season_id_current` pode ser None pra ligas que ainda não tiveram a
    temporada descoberta (resolução K.1 via `/seasons`).
    """
    entry = SOFASCORE_LEAGUE_MAP.get(af_league_id)
    if entry is None:
        return None
    return (entry["unique_tournament_id"], entry.get("season_id_current"))
