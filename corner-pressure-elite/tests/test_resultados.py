"""Testes da logica de verificacao de resultados (Sprint 2)."""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


# --- Testes de logica GREEN/RED ---

def test_green_escanteios_acima_da_linha():
    """Escanteios finais > linha = GREEN."""
    escanteios_final = 12
    linha = 9.5
    resultado = "GREEN" if escanteios_final > linha else "RED"
    assert resultado == "GREEN"


def test_red_escanteios_abaixo_da_linha():
    """Escanteios finais < linha = RED."""
    escanteios_final = 8
    linha = 9.5
    resultado = "GREEN" if escanteios_final > linha else "RED"
    assert resultado == "RED"


def test_red_escanteios_iguais_a_linha():
    """Escanteios finais == linha = RED (nao superou)."""
    escanteios_final = 10
    linha = 10.0
    resultado = "GREEN" if escanteios_final > linha else "RED"
    assert resultado == "RED"


def test_green_escanteios_apenas_acima():
    """Escanteios 10 vs linha 9.5 = GREEN (por 0.5)."""
    escanteios_final = 10
    linha = 9.5
    resultado = "GREEN" if escanteios_final > linha else "RED"
    assert resultado == "GREEN"


# --- Testes de calculo de ROI ---

def test_roi_green():
    """GREEN com odd 1.85: ROI = 0.85u."""
    odd = 1.85
    resultado = "GREEN"
    roi = (odd - 1.0) if resultado == "GREEN" else -1.0
    assert abs(roi - 0.85) < 0.001


def test_roi_red():
    """RED: ROI = -1.0u (perda de 1 unidade)."""
    odd = 1.85
    resultado = "RED"
    roi = (odd - 1.0) if resultado == "GREEN" else -1.0
    assert roi == -1.0


def test_roi_green_odd_alta():
    """GREEN com odd 3.50: ROI = 2.50u."""
    odd = 3.50
    resultado = "GREEN"
    roi = (odd - 1.0) if resultado == "GREEN" else -1.0
    assert abs(roi - 2.50) < 0.001


def test_roi_odd_nula():
    """Odd nula (0 ou None): usar 1.0 como fallback, ROI GREEN = 0."""
    odd = None
    resultado = "GREEN"
    odd_safe = odd or 1.0
    roi = (odd_safe - 1.0) if resultado == "GREEN" else -1.0
    assert roi == 0.0


def test_roi_red_odd_nula():
    """Odd nula + RED: ROI = -1.0u."""
    odd = None
    resultado = "RED"
    odd_safe = odd or 1.0
    roi = (odd_safe - 1.0) if resultado == "GREEN" else -1.0
    assert roi == -1.0


# --- Testes de cenarios de borda ---

def test_escanteios_zero():
    """0 escanteios finais vs qualquer linha = RED."""
    escanteios_final = 0
    linha = 9.5
    resultado = "GREEN" if escanteios_final > linha else "RED"
    assert resultado == "RED"


def test_linha_zero():
    """Linha 0 com qualquer escanteio = GREEN."""
    escanteios_final = 5
    linha = 0.0
    resultado = "GREEN" if escanteios_final > linha else "RED"
    assert resultado == "GREEN"


def test_roi_acumulado_multiplos_sinais():
    """Calculo de ROI acumulado com multiplos sinais."""
    sinais = [
        {"resultado": "GREEN", "odd": 1.85},
        {"resultado": "RED", "odd": 2.00},
        {"resultado": "GREEN", "odd": 1.95},
        {"resultado": "RED", "odd": 1.75},
    ]
    roi_total = 0.0
    for s in sinais:
        odd = s["odd"] or 1.0
        roi = (odd - 1.0) if s["resultado"] == "GREEN" else -1.0
        roi_total += roi

    # 0.85 + (-1.0) + 0.95 + (-1.0) = -0.20
    assert abs(roi_total - (-0.20)) < 0.001


def test_winrate_calculo():
    """Calculo de winrate."""
    greens = 6
    reds = 4
    winrate = (greens / (greens + reds) * 100) if (greens + reds) > 0 else 0
    assert winrate == 60.0


def test_winrate_sem_resultados():
    """Winrate com 0 resultados = 0."""
    greens = 0
    reds = 0
    winrate = (greens / (greens + reds) * 100) if (greens + reds) > 0 else 0
    assert winrate == 0


if __name__ == "__main__":
    test_green_escanteios_acima_da_linha()
    test_red_escanteios_abaixo_da_linha()
    test_red_escanteios_iguais_a_linha()
    test_green_escanteios_apenas_acima()
    test_roi_green()
    test_roi_red()
    test_roi_green_odd_alta()
    test_roi_odd_nula()
    test_roi_red_odd_nula()
    test_escanteios_zero()
    test_linha_zero()
    test_roi_acumulado_multiplos_sinais()
    test_winrate_calculo()
    test_winrate_sem_resultados()
    print("Todos os testes de resultados passaram!")
