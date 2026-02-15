"""Testes do Projection Engine."""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from data.models import JogoAoVivo
from engine.projection_engine import ProjectionEngine


def _jogo_base(**kwargs) -> JogoAoVivo:
    defaults = dict(
        id=1, liga_id=39, liga_nome="Premier League",
        time_casa="TeamA", time_fora="TeamB",
        placar_casa=1, placar_fora=1,
        minuto=60, escanteios_total=8,
        escanteios_casa=4, escanteios_fora=4,
        media_historica_combinada=10.0,
    )
    defaults.update(kwargs)
    return JogoAoVivo(**defaults)


def test_projecao_basica():
    """Projecao basica: (8/60)*95 = 12.67"""
    engine = ProjectionEngine()
    jogo = _jogo_base(
        escanteios_total=8, minuto=60,
        media_historica_combinada=9.0,  # sem ajuste historico
    )
    proj = engine.calcular_projecao(jogo, pressure_score=0)
    # Ritmo: (8/60)*95 = 12.67 + 0 + 0 = 12.67
    assert abs(proj - 12.67) < 0.01, f"Esperado ~12.67, obtido {proj}"


def test_projecao_com_pressao():
    """Projecao com ajuste de pressao: score * 0.25"""
    engine = ProjectionEngine()
    jogo = _jogo_base(
        escanteios_total=8, minuto=60,
        media_historica_combinada=9.0,
    )
    proj = engine.calcular_projecao(jogo, pressure_score=8)
    # Ritmo: 12.67 + Pressao: 8*0.25=2.0 + Hist: 0 = 14.67
    assert abs(proj - 14.67) < 0.01, f"Esperado ~14.67, obtido {proj}"


def test_projecao_exemplo_documento():
    """Exemplo do documento: min 58, 7 escanteios, score 8, media 11.2"""
    engine = ProjectionEngine()
    jogo = _jogo_base(
        escanteios_total=7, minuto=58,
        media_historica_combinada=11.2,
    )
    proj = engine.calcular_projecao(jogo, pressure_score=8)
    # Ritmo: (7/58)*95 = 11.47
    # Pressao: 8*0.25 = 2.0
    # Hist: +0.5 (media > 10.5)
    # Total: 11.47 + 2.0 + 0.5 = 13.97
    assert abs(proj - 13.97) < 0.1, f"Esperado ~13.97, obtido {proj}"


def test_projecao_ajuste_historico():
    """Ajuste historico: +0.5 se media > 10.5"""
    engine = ProjectionEngine()

    jogo_alta = _jogo_base(media_historica_combinada=11.0)
    jogo_baixa = _jogo_base(media_historica_combinada=10.0)

    proj_alta = engine.calcular_projecao(jogo_alta, pressure_score=0)
    proj_baixa = engine.calcular_projecao(jogo_baixa, pressure_score=0)

    assert abs(proj_alta - proj_baixa - 0.5) < 0.01


def test_projecao_minuto_zero():
    """Projecao com minuto 0 nao deve dar erro."""
    engine = ProjectionEngine()
    jogo = _jogo_base(minuto=0, escanteios_total=0)
    proj = engine.calcular_projecao(jogo, pressure_score=0)
    assert proj == 0.0


if __name__ == "__main__":
    test_projecao_basica()
    test_projecao_com_pressao()
    test_projecao_exemplo_documento()
    test_projecao_ajuste_historico()
    test_projecao_minuto_zero()
    print("Todos os testes de projecao passaram!")
