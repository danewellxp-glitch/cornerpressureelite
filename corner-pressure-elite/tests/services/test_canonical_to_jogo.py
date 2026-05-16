"""Unit tests do mapper canonical_to_jogo + recalc_minute_if_cached (Fase E.1 PARTE F')."""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from data.models import JogoAoVivo
from data.services.canonical_to_jogo import canonical_to_jogo, recalc_minute_if_cached
from data.stats_provider import CanonicalStats


def _jogo_base() -> JogoAoVivo:
    return JogoAoVivo(
        id=999,
        liga_id=39,
        liga_nome="Premier League",
        time_casa="Home",
        time_fora="Away",
        placar_casa=0,
        placar_fora=0,
        minuto=0,
        escanteios_total=0,
        escanteios_casa=0,
        escanteios_fora=0,
        media_historica_combinada=9.5,
        media_historica_cartoes=4.5,
        faltas_total=12,
        faltas_casa=7,
        faltas_fora=5,
        linha_atual=10.5,
        odd_atual=1.85,
        odds_source="betano_bridge",
    )


def _stats(**overrides) -> CanonicalStats:
    base = dict(
        fixture_id=999, source="bridge_betano", minute=67,
        score_home=1, score_away=1,
        corners_home=5, corners_away=3,
        yellow_cards_home=1, yellow_cards_away=2,
        red_cards_home=0, red_cards_away=0,
        shots_on_target_home=4, shots_on_target_away=3,
        dangerous_attacks_home=0, dangerous_attacks_away=0,
        possession_home=0, possession_away=0,
        x_goals_home=0.5, x_goals_away=0.3,
    )
    base.update(overrides)
    return CanonicalStats(**base)


def test_mapper_overrides_score_minute_corners_yellow_shots():
    """Campos que Betano sempre cobre: canonical sempre vence."""
    jogo = canonical_to_jogo(_jogo_base(), _stats())
    assert jogo.minuto == 67
    assert jogo.placar_casa == 1
    assert jogo.placar_fora == 1
    assert jogo.escanteios_total == 8
    assert jogo.escanteios_casa == 5
    assert jogo.escanteios_fora == 3
    assert jogo.cartoes_amarelos_total == 3
    assert jogo.cartoes_amarelos_casa == 1
    assert jogo.cartoes_amarelos_fora == 2
    assert jogo.finalizacoes_recentes == 7


def test_mapper_preserves_metadata_and_history_and_odds():
    """id, liga, time, kickoff, media_historica, odds NUNCA são tocados."""
    base = _jogo_base()
    jogo = canonical_to_jogo(base, _stats())
    assert jogo.id == base.id
    assert jogo.liga_id == base.liga_id
    assert jogo.liga_nome == base.liga_nome
    assert jogo.time_casa == base.time_casa
    assert jogo.time_fora == base.time_fora
    assert jogo.media_historica_combinada == 9.5
    assert jogo.media_historica_cartoes == 4.5
    assert jogo.linha_atual == 10.5
    assert jogo.odd_atual == 1.85
    assert jogo.odds_source == "betano_bridge"
    # Faltas (gap canonical) preservadas integralmente.
    assert jogo.faltas_total == 12
    assert jogo.faltas_casa == 7
    assert jogo.faltas_fora == 5


def test_mapper_preserves_gap_fields_when_canonical_zero():
    """red_cards/dangerous_attacks/possession só sobrescrevem se canonical > 0."""
    base = _jogo_base()
    base = JogoAoVivo(
        **{
            **{
                k: getattr(base, k) for k in base.__dataclass_fields__.keys()
            },
            "cartoes_vermelhos_total": 1,
            "cartoes_vermelhos_casa": 1,
            "ataques_perigosos_ultimos_10min": 42,
            "posse_ultimos_10min": 60.0,
        }
    )
    jogo = canonical_to_jogo(base, _stats())  # canonical zerado nesses 3
    assert jogo.cartoes_vermelhos_total == 1   # preservado
    assert jogo.ataques_perigosos_ultimos_10min == 42  # preservado
    assert jogo.posse_ultimos_10min == 60.0  # preservado


def test_mapper_overrides_gap_fields_when_canonical_has_value():
    """red_cards/dangerous_attacks/possession sobrescrevem se canonical > 0."""
    jogo = canonical_to_jogo(
        _jogo_base(),
        _stats(red_cards_home=1, dangerous_attacks_home=20, possession_home=55),
    )
    assert jogo.cartoes_vermelhos_total == 1
    assert jogo.ataques_perigosos_ultimos_10min == 20
    assert jogo.posse_ultimos_10min == 55.0


def test_mapper_window_fields_only_set_when_canonical_has_value():
    """corners_last/yellow_last: None do canonical = preserva jogo_base."""
    base = _jogo_base()
    base = JogoAoVivo(
        **{
            **{k: getattr(base, k) for k in base.__dataclass_fields__.keys()},
            "escanteios_ultimos_5min": 3,
            "cartoes_ultimos_10min": 5,
        }
    )
    jogo = canonical_to_jogo(base, _stats())  # canonical sem janelas (None)
    assert jogo.escanteios_ultimos_5min == 3
    assert jogo.cartoes_ultimos_10min == 5


def test_recalc_minute_returns_input_when_not_cached():
    stats = _stats(minute=67)
    out = recalc_minute_if_cached(stats, now_ts=1778900000.0)
    assert out is stats  # mesmo objeto, frozen dataclass replace skipped


def test_recalc_minute_projects_when_cached():
    """Snapshot cached: minuto += (now - captured_at_ts) // 60."""
    stats = _stats(minute=67, is_cached=True, captured_at_ts=1778900000.0)
    # 180s = 3min depois
    out = recalc_minute_if_cached(stats, now_ts=1778900180.0)
    assert out.minute == 70
    assert out.is_cached is True  # flag preservada


def test_recalc_minute_handles_missing_captured_at_ts():
    """Cached mas captured_at_ts=None: retorna inalterado."""
    stats = _stats(minute=67, is_cached=True, captured_at_ts=None)
    out = recalc_minute_if_cached(stats, now_ts=1778900180.0)
    assert out is stats
