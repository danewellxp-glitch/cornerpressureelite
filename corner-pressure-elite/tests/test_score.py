"""Testes do Pressure Score Engine."""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from data.models import JogoAoVivo
from engine.score_engine import PressureScoreEngine


def _jogo_base(**kwargs) -> JogoAoVivo:
    defaults = dict(
        id=1, liga_id=39, liga_nome="Premier League",
        time_casa="TeamA", time_fora="TeamB",
        placar_casa=1, placar_fora=1,
        minuto=63, escanteios_total=8,
        escanteios_casa=4, escanteios_fora=4,
    )
    defaults.update(kwargs)
    return JogoAoVivo(**defaults)


def test_score_maximo():
    """Score maximo com todas as condicoes atendidas."""
    engine = PressureScoreEngine()
    jogo = _jogo_base(
        placar_casa=1, placar_fora=2,  # time perdendo por 1
        escanteios_ultimos_10min=3,
        escanteios_ultimos_5min=1,
        ataques_perigosos_ultimos_10min=8,
        posse_ultimos_10min=65.0,
        finalizacoes_recentes=4,
    )
    score = engine.calcular(jogo)
    assert score == 10, f"Esperado 10, obtido {score}"


def test_score_zero():
    """Score zero sem nenhuma condicao."""
    engine = PressureScoreEngine()
    jogo = _jogo_base(
        placar_casa=1, placar_fora=1,
        escanteios_ultimos_10min=0,
        escanteios_ultimos_5min=0,
        ataques_perigosos_ultimos_10min=2,
        posse_ultimos_10min=50.0,
        finalizacoes_recentes=1,
    )
    score = engine.calcular(jogo)
    assert score == 0, f"Esperado 0, obtido {score}"


def test_score_exemplo_documento():
    """Exemplo do documento: Inter 1x1 Palmeiras min 63."""
    engine = PressureScoreEngine()
    jogo = _jogo_base(
        time_casa="Internacional", time_fora="Palmeiras",
        placar_casa=1, placar_fora=1,
        minuto=63,
        escanteios_ultimos_10min=2,   # +3
        escanteios_ultimos_5min=0,    # +0
        ataques_perigosos_ultimos_10min=7,  # +2
        posse_ultimos_10min=62.0,     # +1
        finalizacoes_recentes=2,      # +0
    )
    score = engine.calcular(jogo)
    assert score == 6, f"Esperado 6, obtido {score}"


def test_score_time_perdendo():
    """Bonus de time perdendo por 1 gol."""
    engine = PressureScoreEngine()
    jogo = _jogo_base(placar_casa=0, placar_fora=1)
    score_perdendo = engine.calcular(jogo)

    jogo_empate = _jogo_base(placar_casa=1, placar_fora=1)
    score_empate = engine.calcular(jogo_empate)

    assert score_perdendo == score_empate + 2


def test_score_premium():
    """Score >= 9 para sinal premium."""
    engine = PressureScoreEngine()
    jogo = _jogo_base(
        placar_casa=0, placar_fora=1,       # +2
        escanteios_ultimos_10min=2,          # +3
        escanteios_ultimos_5min=1,           # +1
        ataques_perigosos_ultimos_10min=6,   # +2
        posse_ultimos_10min=62.0,            # +1
        finalizacoes_recentes=3,             # +1
    )
    score = engine.calcular(jogo)
    assert score >= 9, f"Esperado >= 9 (premium), obtido {score}"


if __name__ == "__main__":
    test_score_maximo()
    test_score_zero()
    test_score_exemplo_documento()
    test_score_time_perdendo()
    test_score_premium()
    print("Todos os testes de score passaram!")
