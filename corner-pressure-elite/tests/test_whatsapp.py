"""Testes do modulo WhatsApp (formatacao e logica - sem conexao real)."""

import sys
import os
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from data.models import JogoAoVivo, Sinal
from notifier.whatsapp_client import WhatsAppClient
from notifier.message_formatter import MessageFormatter


def _jogo_teste():
    return JogoAoVivo(
        id=12345,
        liga_id=39,
        liga_nome="Premier League",
        time_casa="Manchester City",
        time_fora="Arsenal",
        placar_casa=1,
        placar_fora=1,
        minuto=63,
        escanteios_total=8,
        escanteios_casa=5,
        escanteios_fora=3,
        linha_atual=11.5,
        odd_atual=1.78,
    )


def _sinal_normal():
    return Sinal(
        tipo="NORMAL",
        jogo=_jogo_teste(),
        pressure_score=8,
        projecao=13.2,
        edge=1.7,
        timestamp=datetime(2026, 2, 14, 15, 30, 0),
    )


def _sinal_premium():
    return Sinal(
        tipo="PREMIUM",
        jogo=_jogo_teste(),
        pressure_score=9,
        projecao=15.1,
        edge=3.6,
        timestamp=datetime(2026, 2, 14, 15, 35, 0),
    )


def test_format_chat_id_completo():
    assert WhatsAppClient.format_chat_id("5511999999999") == "5511999999999@c.us"


def test_format_chat_id_sem_codigo_pais():
    assert WhatsAppClient.format_chat_id("11999999999") == "5511999999999@c.us"


def test_format_chat_id_com_caracteres():
    assert WhatsAppClient.format_chat_id("+55 (11) 99999-9999") == "5511999999999@c.us"


def test_format_signal_normal():
    msg = MessageFormatter.format_signal(_sinal_normal())
    assert "OVER ESCANTEIOS" in msg
    assert "NORMAL" in msg
    assert "Manchester City vs Arsenal" in msg
    assert "63'" in msg
    assert "11.5" in msg
    assert "13.2" in msg
    assert "8/10" in msg
    assert "1.78" in msg
    assert "15:30:00" in msg


def test_format_signal_premium():
    msg = MessageFormatter.format_signal(_sinal_premium())
    assert "PREMIUM" in msg
    assert "9/10" in msg


def test_format_reevaluation():
    ant = _sinal_normal()
    novo = Sinal(
        tipo="NORMAL",
        jogo=JogoAoVivo(
            id=12345, liga_id=39, liga_nome="Premier League",
            time_casa="Manchester City", time_fora="Arsenal",
            placar_casa=1, placar_fora=1,
            minuto=68, escanteios_total=10,
            escanteios_casa=6, escanteios_fora=4,
            linha_atual=12.5, odd_atual=1.85,
        ),
        pressure_score=9,
        projecao=14.8,
        edge=2.3,
        timestamp=datetime(2026, 2, 14, 15, 38, 0),
    )
    msg = MessageFormatter.format_reevaluation(novo, ant)
    assert "RE-EVALUATION" in msg
    assert "68'" in msg
    assert "63'" in msg  # alerta inicial
    assert "8 \u2192 10" in msg  # escanteios mudaram
    assert "Sem sugest\u00e3o de stake" in msg


def test_format_summary():
    stats = {
        "total": 10,
        "greens": 6,
        "reds": 4,
        "winrate": 60.0,
        "roi_total": 3.5,
    }
    msg = MessageFormatter.format_summary(stats)
    assert "RESUMO" in msg
    assert "60.0%" in msg


def test_format_error():
    msg = MessageFormatter.format_error("API timeout")
    assert "ERRO" in msg
    assert "API timeout" in msg


def test_format_status():
    status = {
        "online": True,
        "api_requests": 50,
        "api_limit": 100,
        "jogos_ativos": 3,
        "sinais_hoje": 2,
        "ultima_atualizacao": "15:30:00",
    }
    msg = MessageFormatter.format_status(status)
    assert "Online" in msg
    assert "50/100" in msg


if __name__ == "__main__":
    test_format_chat_id_completo()
    test_format_chat_id_sem_codigo_pais()
    test_format_chat_id_com_caracteres()
    test_format_signal_normal()
    test_format_signal_premium()
    test_format_reevaluation()
    test_format_summary()
    test_format_error()
    test_format_status()
    print("Todos os testes de WhatsApp passaram!")
