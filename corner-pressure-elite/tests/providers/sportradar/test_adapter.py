"""Testes do conversor `to_jogo_ao_vivo_fields`.

Validam o mapeamento Sportradar → dict-de-JogoAoVivo e a estimativa de
janelas via corner rate (mesma lógica de `utils/helpers.py`).
"""
from data.providers.sportradar import to_jogo_ao_vivo_fields
from data.providers.sportradar.schemas import (
    CoverageFlags,
    MatchDetailsExtended,
    MatchInfo,
    MatchSituation,
)


def _details(
    minute: int = 60,
    corners_h: int = 4,
    corners_a: int = 3,
    yellow_h: int = 2,
    yellow_a: int = 1,
    red_h: int = 0,
    red_a: int = 0,
    shots_tot_h: int = 10,
    shots_tot_a: int = 8,
) -> MatchDetailsExtended:
    return MatchDetailsExtended(
        match_id="M1", minute=minute,
        score_home=1, score_away=0,
        corners_home=corners_h, corners_away=corners_a,
        yellowcards_home=yellow_h, yellowcards_away=yellow_a,
        redcards_home=red_h, redcards_away=red_a,
        shots_on_target_home=3, shots_on_target_away=2,
        shots_total_home=shots_tot_h, shots_total_away=shots_tot_a,
        raw={},
    )


def _match_info(minute: int = 60) -> MatchInfo:
    return MatchInfo(
        match_id="M1", sport_id=1,
        league_id=None, season_id=None,
        home_team_name="Casa", home_team_id=None,
        away_team_name="Visit", away_team_id=None,
        status="live", minute=minute,
        score_home=1, score_away=0,
        coverage=CoverageFlags(cornerson=True, cardson=True),
    )


def _situation(
    poss_h: float = 55.0, poss_a: float = 45.0,
    danger_h: float = 30.0, danger_a: float = 25.0,
) -> MatchSituation:
    return MatchSituation(
        match_id="M1",
        possession_home_pct=poss_h, possession_away_pct=poss_a,
        attack_home_pct=None, attack_away_pct=None,
        dangerous_attack_home_pct=danger_h,
        dangerous_attack_away_pct=danger_a,
        ball_x=None, ball_y=None, minute=60,
    )


def test_adapter_returns_empty_when_all_inputs_none():
    out = to_jogo_ao_vivo_fields(None, None, None)
    assert out == {}


def test_adapter_scores_and_minute_from_match_info():
    out = to_jogo_ao_vivo_fields(_match_info(), None, None)
    assert out["placar_casa"] == 1
    assert out["placar_fora"] == 0
    assert out["minuto"] == 60


def test_adapter_details_overrides_minute_when_more_fresh():
    info = _match_info(minute=60)
    det = _details(minute=65)
    out = to_jogo_ao_vivo_fields(info, None, det)
    assert out["minuto"] == 65


def test_adapter_aggregates_corners():
    out = to_jogo_ao_vivo_fields(None, None, _details(corners_h=4, corners_a=3))
    assert out["escanteios_casa"] == 4
    assert out["escanteios_fora"] == 3
    assert out["escanteios_total"] == 7


def test_adapter_aggregates_cards():
    det = _details(yellow_h=3, yellow_a=2, red_h=1, red_a=0)
    out = to_jogo_ao_vivo_fields(None, None, det)
    assert out["cartoes_amarelos_total"] == 5
    assert out["cartoes_vermelhos_casa"] == 1
    assert out["cartoes_vermelhos_total"] == 1


def test_adapter_estimates_window_via_corner_rate():
    # 7 corners em 60min ≈ 0.117/min → janela 5min ≈ 0.58 → arredonda 1
    # janela 10min ≈ 1.17 → arredonda 1
    out = to_jogo_ao_vivo_fields(
        None, None, _details(minute=60, corners_h=4, corners_a=3)
    )
    assert 0 <= out["escanteios_ultimos_5min"] <= 2
    assert 1 <= out["escanteios_ultimos_10min"] <= 2


def test_adapter_window_capped_by_total():
    # min muito baixo + total alto → janela não excede total
    out = to_jogo_ao_vivo_fields(
        None, None, _details(minute=3, corners_h=1, corners_a=1)
    )
    assert out["escanteios_ultimos_5min"] <= 2
    assert out["escanteios_ultimos_10min"] <= 2


def test_adapter_possession_uses_max():
    out = to_jogo_ao_vivo_fields(
        None, _situation(poss_h=55.0, poss_a=45.0), None
    )
    assert out["posse_ultimos_10min"] == 55.0


def test_adapter_dangerous_attack_sums_both_sides():
    out = to_jogo_ao_vivo_fields(
        None, _situation(danger_h=30.0, danger_a=25.0), None
    )
    assert out["ataques_perigosos_ultimos_10min"] == 55


def test_adapter_finalizacoes_recentes_sums_shots():
    out = to_jogo_ao_vivo_fields(
        None, None, _details(shots_tot_h=10, shots_tot_a=8)
    )
    assert out["finalizacoes_recentes"] == 18


def test_adapter_dict_keys_match_JogoAoVivo_attributes():
    """Garante que o dict só usa nomes que JogoAoVivo realmente tem.

    Quebra cedo se renomearmos campos sem propagar.
    """
    from data.models import JogoAoVivo
    out = to_jogo_ao_vivo_fields(
        _match_info(), _situation(), _details()
    )
    valid_fields = {f for f in JogoAoVivo.__dataclass_fields__}
    for k in out.keys():
        assert k in valid_fields, (
            f"chave '{k}' do adapter não existe em JogoAoVivo"
        )
