"""Testes do parsing de odds (Sprint 1)."""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from data.api_client import APIFootballClient


def _make_client():
    """Cria cliente com dados fake (nao faz requisicoes reais)."""
    from utils.rate_limiter import RateLimiter
    rl = RateLimiter(max_requests_per_day=100, max_requests_per_minute=10)
    return APIFootballClient(api_key="fake", rate_limiter=rl)


# --- Testes do _parse_corners_odds ---

def test_parse_live_odds_formato_padrao():
    """Formato padrao de odds live com Over/Under corners."""
    client = _make_client()
    odds_list = [
        {"name": "Match Winner", "values": [
            {"value": "Home", "odd": "1.50"},
            {"value": "Draw", "odd": "3.50"},
        ]},
        {"name": "Corners Over/Under", "values": [
            {"value": "Over 9.5", "odd": "1.85"},
            {"value": "Under 9.5", "odd": "2.05"},
        ]},
    ]
    result = client._parse_corners_odds(odds_list, "Live")
    assert result["linha"] == 9.5
    assert result["odd_over"] == 1.85
    assert result["odd_under"] == 2.05
    assert result["bookmaker"] == "Live"


def test_parse_prematch_odds_formato_bookmaker():
    """Formato pre-match com bets[] (mesmo parser)."""
    client = _make_client()
    bets = [
        {"name": "Goals Over/Under", "values": [
            {"value": "Over 2.5", "odd": "1.80"},
            {"value": "Under 2.5", "odd": "2.00"},
        ]},
        {"name": "Total Corners", "values": [
            {"value": "Over 10.5", "odd": "1.95"},
            {"value": "Under 10.5", "odd": "1.90"},
        ]},
    ]
    result = client._parse_corners_odds(bets, "Bet365")
    assert result["linha"] == 10.5
    assert result["odd_over"] == 1.95
    assert result["odd_under"] == 1.90
    assert result["bookmaker"] == "Bet365"


def test_parse_odds_sem_mercado_corners():
    """Retorna vazio quando nao ha mercado de corners."""
    client = _make_client()
    odds_list = [
        {"name": "Match Winner", "values": [
            {"value": "Home", "odd": "1.50"},
        ]},
        {"name": "Goals Over/Under", "values": [
            {"value": "Over 2.5", "odd": "1.80"},
        ]},
    ]
    result = client._parse_corners_odds(odds_list, "Test")
    assert result == {}


def test_parse_odds_lista_vazia():
    """Retorna vazio com lista vazia."""
    client = _make_client()
    result = client._parse_corners_odds([], "Test")
    assert result == {}


def test_parse_odds_corner_keyword_parcial():
    """Detecta mercado com 'corner' em qualquer parte do nome."""
    client = _make_client()
    odds_list = [
        {"name": "Asian Corner", "values": [
            {"value": "Over 8.5", "odd": "1.75"},
            {"value": "Under 8.5", "odd": "2.10"},
        ]},
    ]
    result = client._parse_corners_odds(odds_list, "Live")
    assert result["linha"] == 8.5
    assert result["odd_over"] == 1.75


def test_parse_odds_valores_incompletos():
    """Retorna vazio quando falta Over ou Under."""
    client = _make_client()
    odds_list = [
        {"name": "Corners Over/Under", "values": [
            {"value": "Over 9.5", "odd": "1.85"},
            # Falta Under
        ]},
    ]
    result = client._parse_corners_odds(odds_list, "Test")
    assert result == {}


def test_parse_odds_linha_invalida():
    """Retorna vazio quando linha nao e numero valido."""
    client = _make_client()
    odds_list = [
        {"name": "Corners", "values": [
            {"value": "Over abc", "odd": "1.85"},
            {"value": "Under abc", "odd": "2.05"},
        ]},
    ]
    result = client._parse_corners_odds(odds_list, "Test")
    assert result == {}


def test_parse_odds_odd_zero():
    """Retorna vazio quando odd e 0."""
    client = _make_client()
    odds_list = [
        {"name": "Corners", "values": [
            {"value": "Over 9.5", "odd": 0},
            {"value": "Under 9.5", "odd": "2.05"},
        ]},
    ]
    result = client._parse_corners_odds(odds_list, "Test")
    assert result == {}


def test_parse_odds_multiplos_mercados_pega_primeiro():
    """Quando ha multiplos mercados de corners, pega o primeiro."""
    client = _make_client()
    odds_list = [
        {"name": "Corners Over/Under", "values": [
            {"value": "Over 9.5", "odd": "1.85"},
            {"value": "Under 9.5", "odd": "2.05"},
        ]},
        {"name": "Corners 1st Half", "values": [
            {"value": "Over 4.5", "odd": "1.90"},
            {"value": "Under 4.5", "odd": "1.95"},
        ]},
    ]
    result = client._parse_corners_odds(odds_list, "Test")
    assert result["linha"] == 9.5, "Deve pegar o primeiro mercado de corners"


def test_parse_odds_keyword_escanteio():
    """Detecta mercado com keyword 'escanteio' (portugues)."""
    client = _make_client()
    odds_list = [
        {"name": "Escanteios Over/Under", "values": [
            {"value": "Over 10.5", "odd": "2.00"},
            {"value": "Under 10.5", "odd": "1.85"},
        ]},
    ]
    result = client._parse_corners_odds(odds_list, "BR")
    assert result["linha"] == 10.5


if __name__ == "__main__":
    test_parse_live_odds_formato_padrao()
    test_parse_prematch_odds_formato_bookmaker()
    test_parse_odds_sem_mercado_corners()
    test_parse_odds_lista_vazia()
    test_parse_odds_corner_keyword_parcial()
    test_parse_odds_valores_incompletos()
    test_parse_odds_linha_invalida()
    test_parse_odds_odd_zero()
    test_parse_odds_multiplos_mercados_pega_primeiro()
    test_parse_odds_keyword_escanteio()
    print("Todos os testes de odds passaram!")
