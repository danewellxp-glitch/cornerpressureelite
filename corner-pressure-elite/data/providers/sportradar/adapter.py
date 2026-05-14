"""Adaptação dos schemas Sportradar para os campos que `JogoAoVivo`
espera (`data/models.py`).

Esta camada **não** depende de `JogoAoVivo` em si — devolve um `dict` com
as chaves esperadas. O caller (Fase C) decide se atualiza um `JogoAoVivo`
existente ou constrói um novo.

Mapeamento (harness Fase A §3 capability 6):

| JogoAoVivo                       | Origem Sportradar                       |
|----------------------------------|-----------------------------------------|
| placar_casa / placar_fora        | MatchInfo.score_home/away               |
| minuto                           | MatchInfo.minute ou Details.minute      |
| escanteios_casa/fora/total       | MatchDetailsExtended.corners_*          |
| cartoes_amarelos_casa/fora/total | MatchDetailsExtended.yellowcards_*      |
| cartoes_vermelhos_casa/fora/tot. | MatchDetailsExtended.redcards_*         |
| finalizacoes_recentes            | shots_total_home + shots_total_away     |
| ataques_perigosos_ultimos_10min  | situation.dangerous_attack_home+away    |
| posse_ultimos_10min              | max(situation.possession_home, away)    |
| escanteios_ultimos_{5,10}min     | estimativa via corner rate (sem janelas)|
| cartoes_ultimos_{5,10}min        | idem para cartões                       |

Quando `cornerson=False` na coverage, devolvemos só placar/minuto/etc; o
caller cai para fallback API-Football (harness §4.5).
"""
from typing import Any, Optional

from .schemas import (
    MatchDetailsExtended,
    MatchInfo,
    MatchSituation,
    TimelineEvent,
)


def _estimate_window(total: int, minute: int, window_min: int) -> int:
    """Estima eventos numa janela recente via taxa por minuto.

    Mesma lógica de `utils/helpers.parse_fixture_to_jogo` (que opera sobre
    API-Football) — mantemos consistência para que score/decision engines
    enxerguem o mesmo formato vindo de qualquer provider.
    """
    if minute <= 0:
        return total if total <= 2 else 0
    if minute <= 5:
        return min(total, 2 if window_min == 5 else total)
    rate = total / minute
    estimate = round(rate * window_min + 0.3)
    return min(total, max(0, estimate))


def to_jogo_ao_vivo_fields(
    match_info: Optional[MatchInfo],
    situation: Optional[MatchSituation],
    details: Optional[MatchDetailsExtended],
    last_events: Optional[list[TimelineEvent]] = None,
) -> dict[str, Any]:
    """Devolve dict com as chaves que `JogoAoVivo` reconhece.

    Todos os argumentos são opcionais — campos sem fonte ficam ausentes do
    dict retornado, deixando o caller decidir entre default ou fallback.
    `last_events` está reservado para uso futuro (contagem real de janelas
    quando o spike confirmar a granularidade do timelinedelta).
    """
    out: dict[str, Any] = {}

    if match_info is not None:
        if match_info.score_home is not None:
            out["placar_casa"] = match_info.score_home
        if match_info.score_away is not None:
            out["placar_fora"] = match_info.score_away
        if match_info.minute is not None:
            out["minuto"] = match_info.minute

    if details is not None:
        if details.minute:
            out["minuto"] = details.minute  # mais fresco que match_info

        total_corners = details.corners_home + details.corners_away
        out["escanteios_casa"] = details.corners_home
        out["escanteios_fora"] = details.corners_away
        out["escanteios_total"] = total_corners

        minute_for_est = out.get("minuto") or 0
        out["escanteios_ultimos_5min"] = _estimate_window(
            total_corners, minute_for_est, 5
        )
        out["escanteios_ultimos_10min"] = _estimate_window(
            total_corners, minute_for_est, 10
        )

        total_yellows = details.yellowcards_home + details.yellowcards_away
        out["cartoes_amarelos_casa"] = details.yellowcards_home
        out["cartoes_amarelos_fora"] = details.yellowcards_away
        out["cartoes_amarelos_total"] = total_yellows
        out["cartoes_ultimos_5min"] = _estimate_window(
            total_yellows, minute_for_est, 5
        )
        out["cartoes_ultimos_10min"] = _estimate_window(
            total_yellows, minute_for_est, 10
        )

        out["cartoes_vermelhos_casa"] = details.redcards_home
        out["cartoes_vermelhos_fora"] = details.redcards_away
        out["cartoes_vermelhos_total"] = (
            details.redcards_home + details.redcards_away
        )

        # JogoAoVivo.finalizacoes_recentes hoje é total — usamos shots_total
        out["finalizacoes_recentes"] = (
            details.shots_total_home + details.shots_total_away
        )

    if situation is not None:
        if (situation.dangerous_attack_home_pct is not None
                or situation.dangerous_attack_away_pct is not None):
            out["ataques_perigosos_ultimos_10min"] = int(round(
                (situation.dangerous_attack_home_pct or 0.0)
                + (situation.dangerous_attack_away_pct or 0.0)
            ))
        if (situation.possession_home_pct is not None
                and situation.possession_away_pct is not None):
            out["posse_ultimos_10min"] = max(
                situation.possession_home_pct,
                situation.possession_away_pct,
            )

    return out
