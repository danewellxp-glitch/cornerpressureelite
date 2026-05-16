import logging
from datetime import datetime
from typing import Dict, List, Optional

from data.models import JogoAoVivo
from config import LIGAS_MONITORADAS, LIGAS_MEDIA_CARTOES

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

    # Kickoff em ISO 8601 com timezone (ex. "2026-05-13T16:30:00+00:00")
    kickoff_at = None
    kickoff_raw = fixture_info.get("date")
    if kickoff_raw:
        try:
            kickoff_at = datetime.fromisoformat(kickoff_raw)
        except (ValueError, TypeError):
            kickoff_at = None

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
        kickoff_at=kickoff_at,
    )


def enrich_jogo_with_cards(jogo: JogoAoVivo, stats: List[Dict], liga_id: int) -> None:
    """Popula campos de cartoes no JogoAoVivo a partir das MESMAS stats (0 API calls extras).

    Extrai Yellow Cards, Red Cards, Fouls via extrair_estatistica().
    Estima rolling windows a partir da taxa por minuto.
    Modifica jogo in-place.
    """
    # Cartoes amarelos
    yellows_home = _parse_int(extrair_estatistica(stats, 0, "Yellow Cards"))
    yellows_away = _parse_int(extrair_estatistica(stats, 1, "Yellow Cards"))
    total_yellows = yellows_home + yellows_away

    # Cartoes vermelhos
    reds_home = _parse_int(extrair_estatistica(stats, 0, "Red Cards"))
    reds_away = _parse_int(extrair_estatistica(stats, 1, "Red Cards"))
    total_reds = reds_home + reds_away

    # Faltas
    fouls_home = _parse_int(extrair_estatistica(stats, 0, "Fouls"))
    fouls_away = _parse_int(extrair_estatistica(stats, 1, "Fouls"))
    total_fouls = fouls_home + fouls_away

    jogo.cartoes_amarelos_total = total_yellows
    jogo.cartoes_amarelos_casa = yellows_home
    jogo.cartoes_amarelos_fora = yellows_away
    jogo.cartoes_vermelhos_total = total_reds
    jogo.cartoes_vermelhos_casa = reds_home
    jogo.cartoes_vermelhos_fora = reds_away
    jogo.faltas_total = total_fouls
    jogo.faltas_casa = fouls_home
    jogo.faltas_fora = fouls_away

    # Estimar cartoes em janelas de tempo (mesma logica dos escanteios)
    minuto = jogo.minuto
    if minuto > 5:
        card_rate = total_yellows / minuto
        jogo.cartoes_ultimos_5min = min(total_yellows, max(0, round(card_rate * 5 + 0.2)))
        jogo.cartoes_ultimos_10min = min(total_yellows, max(0, round(card_rate * 10 + 0.2)))
    elif total_yellows > 0:
        jogo.cartoes_ultimos_5min = min(total_yellows, 1)
        jogo.cartoes_ultimos_10min = total_yellows
    else:
        jogo.cartoes_ultimos_5min = 0
        jogo.cartoes_ultimos_10min = 0

    # Media historica de cartoes da liga
    jogo.media_historica_cartoes = LIGAS_MEDIA_CARTOES.get(liga_id, 4.0)

    desc = jogo.descricao
    logger.debug(
        f"[CARDS] {desc} min={minuto} | "
        f"yellows={total_yellows} (H:{yellows_home} A:{yellows_away}) | "
        f"reds={total_reds} | fouls={total_fouls} | "
        f"est_5min={jogo.cartoes_ultimos_5min} est_10min={jogo.cartoes_ultimos_10min}"
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
