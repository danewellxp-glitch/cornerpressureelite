import logging
from typing import Dict, List, Optional

from data.models import JogoAoVivo
from config import LIGAS_MONITORADAS

logger = logging.getLogger("CPES.Helpers")


def get_liga_nome(liga_id: int) -> str:
    for liga in LIGAS_MONITORADAS:
        if liga["id"] == liga_id:
            return liga["nome"]
    return f"Liga {liga_id}"


def get_liga_media(liga_id: int) -> float:
    for liga in LIGAS_MONITORADAS:
        if liga["id"] == liga_id:
            return liga["media_esperada"]
    return 10.0


def extrair_estatistica(stats: List[Dict], team_index: int, stat_type: str) -> Optional[str]:
    """Extrai um valor de estatistica da resposta da API."""
    if not stats or team_index >= len(stats):
        return None

    team_stats = stats[team_index].get("statistics", [])
    for stat in team_stats:
        if stat.get("type") == stat_type:
            return stat.get("value")
    return None


def parse_fixture_to_jogo(fixture: Dict, stats: List[Dict], liga_id: int) -> JogoAoVivo:
    """Converte dados da API em JogoAoVivo."""
    fixture_info = fixture.get("fixture", {})
    teams = fixture.get("teams", {})
    goals = fixture.get("goals", {})
    score_data = fixture.get("score", {})

    # Minuto atual
    status = fixture_info.get("status", {})
    minuto_raw = status.get("elapsed", 0)
    minuto = minuto_raw if minuto_raw else 0

    # Escanteios de cada time
    corners_home = _parse_int(extrair_estatistica(stats, 0, "Corner Kicks"))
    corners_away = _parse_int(extrair_estatistica(stats, 1, "Corner Kicks"))

    # Ataques perigosos
    dangerous_home = _parse_int(extrair_estatistica(stats, 0, "Dangerous Attacks"))
    dangerous_away = _parse_int(extrair_estatistica(stats, 1, "Dangerous Attacks"))

    # Posse de bola
    possession_home = _parse_percentage(extrair_estatistica(stats, 0, "Ball Possession"))
    possession_away = _parse_percentage(extrair_estatistica(stats, 1, "Ball Possession"))

    # Finalizacoes
    shots_home = _parse_int(extrair_estatistica(stats, 0, "Shots on Goal"))
    shots_away = _parse_int(extrair_estatistica(stats, 1, "Shots on Goal"))

    return JogoAoVivo(
        id=fixture_info.get("id", 0),
        liga_id=liga_id,
        liga_nome=get_liga_nome(liga_id),
        time_casa=teams.get("home", {}).get("name", "???"),
        time_fora=teams.get("away", {}).get("name", "???"),
        placar_casa=goals.get("home", 0) or 0,
        placar_fora=goals.get("away", 0) or 0,
        minuto=minuto,
        escanteios_total=corners_home + corners_away,
        escanteios_casa=corners_home,
        escanteios_fora=corners_away,
        ataques_perigosos_ultimos_10min=dangerous_home + dangerous_away,
        posse_ultimos_10min=max(possession_home, possession_away),
        finalizacoes_recentes=shots_home + shots_away,
        media_historica_combinada=get_liga_media(liga_id),
    )


def _parse_int(value) -> int:
    if value is None:
        return 0
    try:
        return int(value)
    except (ValueError, TypeError):
        return 0


def _parse_percentage(value) -> float:
    if value is None:
        return 0.0
    if isinstance(value, str):
        value = value.replace("%", "").strip()
    try:
        return float(value)
    except (ValueError, TypeError):
        return 0.0
