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
    """Converte dados da API em JogoAoVivo.

    NOTA: A API-Football retorna estatísticas TOTAIS do jogo, não janelas de tempo.
    Os campos escanteios_ultimos_5min e escanteios_ultimos_10min são ESTIMADOS
    a partir da taxa de escanteios/minuto (corner rate).
    Os campos ataques_perigosos e finalizacoes são totais do jogo.
    """
    fixture_info = fixture.get("fixture", {})
    teams = fixture.get("teams", {})
    goals = fixture.get("goals", {})

    # Minuto atual
    status = fixture_info.get("status", {})
    minuto_raw = status.get("elapsed", 0)
    minuto = minuto_raw if minuto_raw else 0

    # Escanteios de cada time
    corners_home = _parse_int(extrair_estatistica(stats, 0, "Corner Kicks"))
    corners_away = _parse_int(extrair_estatistica(stats, 1, "Corner Kicks"))
    total_corners = corners_home + corners_away

    # Estimar escanteios em janelas de tempo a partir do corner rate.
    # A API não fornece dados windowed — esta é a melhor aproximação disponível.
    if minuto > 5:
        corner_rate = total_corners / minuto  # corners por minuto
        est_corners_5min = min(total_corners, max(0, round(corner_rate * 5 + 0.3)))
        est_corners_10min = min(total_corners, max(0, round(corner_rate * 10 + 0.3)))
    elif total_corners > 0:
        # Inicio do jogo: se há escanteios, considerar recentes
        est_corners_5min = min(total_corners, 2)
        est_corners_10min = total_corners
    else:
        est_corners_5min = 0
        est_corners_10min = 0

    # Ataques perigosos (total do jogo)
    dangerous_home = _parse_int(extrair_estatistica(stats, 0, "Dangerous Attacks"))
    dangerous_away = _parse_int(extrair_estatistica(stats, 1, "Dangerous Attacks"))

    # Posse de bola (% geral)
    possession_home = _parse_percentage(extrair_estatistica(stats, 0, "Ball Possession"))
    possession_away = _parse_percentage(extrair_estatistica(stats, 1, "Ball Possession"))

    # Finalizacoes (total do jogo)
    shots_home = _parse_int(extrair_estatistica(stats, 0, "Shots on Goal"))
    shots_away = _parse_int(extrair_estatistica(stats, 1, "Shots on Goal"))

    desc = f"{teams.get('home', {}).get('name', '???')} vs {teams.get('away', {}).get('name', '???')}"
    logger.debug(
        f"[PARSE] {desc} min={minuto} | "
        f"corners={total_corners} (H:{corners_home} A:{corners_away}) | "
        f"est_5min={est_corners_5min} est_10min={est_corners_10min} | "
        f"rate={total_corners/max(1,minuto):.3f}/min"
    )

    return JogoAoVivo(
        id=fixture_info.get("id", 0),
        liga_id=liga_id,
        liga_nome=get_liga_nome(liga_id),
        time_casa=teams.get("home", {}).get("name", "???"),
        time_fora=teams.get("away", {}).get("name", "???"),
        placar_casa=goals.get("home", 0) or 0,
        placar_fora=goals.get("away", 0) or 0,
        minuto=minuto,
        escanteios_total=total_corners,
        escanteios_casa=corners_home,
        escanteios_fora=corners_away,
        escanteios_ultimos_10min=est_corners_10min,
        escanteios_ultimos_5min=est_corners_5min,
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
