"""Testes do Decision Engine."""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from data.models import JogoAoVivo
from engine.decision_engine import DecisionEngine


def _jogo_base(**kwargs) -> JogoAoVivo:
    defaults = dict(
        id=1, liga_id=39, liga_nome="Premier League",
        time_casa="TeamA", time_fora="TeamB",
        placar_casa=1, placar_fora=1,
        minuto=63, escanteios_total=8,
        escanteios_casa=4, escanteios_fora=4,
        escanteios_ultimos_10min=0,
        escanteios_ultimos_5min=1,
        ataques_perigosos_ultimos_10min=0,
        posse_ultimos_10min=50.0,
        finalizacoes_recentes=0,
        linha_atual=10.5,
        odd_atual=1.80,
        media_historica_combinada=10.0,
    )
    defaults.update(kwargs)
    return JogoAoVivo(**defaults)


def test_filtro_minuto_baixo():
    """Bloqueia jogo antes do minuto 55."""
    engine = DecisionEngine()
    jogo = _jogo_base(minuto=40)
    assert engine.avaliar(jogo) is None


def test_filtro_minuto_alto():
    """Bloqueia jogo depois do minuto 78."""
    engine = DecisionEngine()
    jogo = _jogo_base(minuto=85)
    assert engine.avaliar(jogo) is None


def test_filtro_diferenca_gols():
    """Bloqueia jogo com diferenca > 2 gols."""
    engine = DecisionEngine()
    jogo = _jogo_base(placar_casa=4, placar_fora=0)
    assert engine.avaliar(jogo) is None


def test_filtro_poucos_escanteios():
    """Bloqueia jogo com menos de 5 escanteios."""
    engine = DecisionEngine()
    jogo = _jogo_base(escanteios_total=3, escanteios_casa=2, escanteios_fora=1)
    assert engine.avaliar(jogo) is None


def test_filtro_jogo_morno():
    """Bloqueia 0x0 apos min 60 com poucos escanteios."""
    engine = DecisionEngine()
    jogo = _jogo_base(
        placar_casa=0, placar_fora=0,
        minuto=65, escanteios_total=5,
        escanteios_casa=3, escanteios_fora=2,
    )
    assert engine.avaliar(jogo) is None


def test_filtro_jogo_morto():
    """Bloqueia jogo se time tem 0 escanteios no 1o tempo."""
    engine = DecisionEngine()
    jogo = _jogo_base(
        minuto=60,
        escanteios_casa=0, escanteios_fora=5,
        escanteios_total=5,
    )
    assert engine.avaliar(jogo) is None


def test_sinal_normal():
    """Deve gerar sinal NORMAL com score 8+ e edge 1.3+."""
    engine = DecisionEngine()
    jogo = _jogo_base(
        minuto=63,
        placar_casa=0, placar_fora=1,          # +2 (perdendo por 1)
        escanteios_total=9,
        escanteios_casa=5, escanteios_fora=4,
        escanteios_ultimos_10min=3,             # +3
        escanteios_ultimos_5min=1,              # +1
        ataques_perigosos_ultimos_10min=7,      # +2
        posse_ultimos_10min=55.0,
        finalizacoes_recentes=1,
        linha_atual=10.5,
        odd_atual=1.80,
        media_historica_combinada=9.0,
    )
    # Score = 2+3+1+2 = 8
    # Proj = (9/63)*95 + 8*0.25 + 0 = 13.57 + 2.0 = 15.57
    # Edge = 15.57 - 10.5 = 5.07
    sinal = engine.avaliar(jogo)
    assert sinal is not None, "Deveria gerar sinal"
    assert sinal.tipo in ("NORMAL", "PREMIUM")


def test_sinal_premium():
    """Deve gerar sinal PREMIUM com score 9+ e edge 2.0+."""
    engine = DecisionEngine()
    jogo = _jogo_base(
        minuto=60,
        placar_casa=0, placar_fora=1,          # +2
        escanteios_total=9,
        escanteios_casa=5, escanteios_fora=4,
        escanteios_ultimos_10min=3,             # +3
        escanteios_ultimos_5min=1,              # +1
        ataques_perigosos_ultimos_10min=7,      # +2
        posse_ultimos_10min=65.0,               # +1
        finalizacoes_recentes=1,
        linha_atual=10.5,
        odd_atual=1.95,
        media_historica_combinada=11.0,
    )
    # Score = 2+3+1+2+1 = 9
    # Proj = (9/60)*95 + 9*0.25 + 0.5 = 14.25 + 2.25 + 0.5 = 17.0
    # Edge = 17.0 - 10.5 = 6.5
    sinal = engine.avaliar(jogo)
    assert sinal is not None, "Deveria gerar sinal"
    assert sinal.tipo == "PREMIUM", f"Esperado PREMIUM, obtido {sinal.tipo}"


def test_sem_sinal_score_baixo():
    """Nao deve gerar sinal com score < 8."""
    engine = DecisionEngine()
    jogo = _jogo_base(
        escanteios_total=8,
        escanteios_casa=4, escanteios_fora=4,
        escanteios_ultimos_10min=0,
        escanteios_ultimos_5min=1,
        ataques_perigosos_ultimos_10min=2,
        linha_atual=8.0,
    )
    sinal = engine.avaliar(jogo)
    assert sinal is None


if __name__ == "__main__":
    test_filtro_minuto_baixo()
    test_filtro_minuto_alto()
    test_filtro_diferenca_gols()
    test_filtro_poucos_escanteios()
    test_filtro_jogo_morno()
    test_filtro_jogo_morto()
    test_sinal_normal()
    test_sinal_premium()
    test_sem_sinal_score_baixo()
    print("Todos os testes de decisao passaram!")
