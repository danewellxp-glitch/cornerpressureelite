"""
Sistema de polling adaptativo baseado no minuto do jogo e escanteios.
- 0-24 min: 5 min | 25-50 min: 3 min (ou 1 min se 7+ escanteios - early trigger)
- 50-90 min: 1 min (janela) | 90+ min: 30 seg (acréscimos)
"""
from typing import Dict, List, Optional
from datetime import datetime, timedelta

from config import ESCANTEIOS_EARLY_WINDOW


class AdaptivePolling:
    """
    Gerencia intervalos de polling baseado na fase do jogo.
    Early trigger: 7+ escanteios antes do min 50 -> entra em 1 min (na janela).
    """

    ESCANTEIOS_EARLY_TRIGGER = ESCANTEIOS_EARLY_WINDOW

    INTERVALS = {
        "primeiro_tempo_inicial": 300,  # 5 min (0-30)
        "pre_janela": 180,  # 3 min (31-50) sem 7 esc
        "pre_janela_early": 60,  # 1 min (31-50 com 7+ esc) - early trigger
        "janela_analise": 30,  # 30 seg (50-90) - JANELA PRINCIPAL
        "reta_final": 30,  # 30 seg (90+ acréscimos) - FASE CRITICA
    }

    def __init__(self):
        self._last_poll: Dict[int, datetime] = {}

    def should_poll(
        self, jogo_id: int, minuto: int, escanteios: Optional[int] = None
    ) -> bool:
        """
        Determina se deve fazer polling (buscar stats e analisar) para este jogo.
        escanteios: do cache; se >= 7 e min < 50, usa intervalo 1 min (early trigger).
        """
        now = datetime.now()

        if jogo_id not in self._last_poll:
            self._last_poll[jogo_id] = now
            return True

        elapsed = (now - self._last_poll[jogo_id]).total_seconds()
        required = self._get_interval_for_minute(minuto, escanteios)

        if elapsed >= required:
            self._last_poll[jogo_id] = now
            return True

        return False

    def _get_interval_for_minute(
        self, minuto: int, escanteios: Optional[int] = None
    ) -> int:
        esc = escanteios if escanteios is not None else 0
        early_trigger = esc >= self.ESCANTEIOS_EARLY_TRIGGER

        if minuto <= 30 and not early_trigger:
            return self.INTERVALS["primeiro_tempo_inicial"]
        elif minuto < 50:
            if early_trigger:
                return self.INTERVALS["pre_janela_early"]
            return self.INTERVALS["pre_janela"]
        elif 50 <= minuto <= 90:
            return self.INTERVALS["janela_analise"]
        else:
            return self.INTERVALS["reta_final"]

    def get_next_poll_time(
        self, jogo_id: int, minuto: int, escanteios: Optional[int] = None
    ) -> str:
        """Retorna quando sera o proximo poll para este jogo."""
        if jogo_id not in self._last_poll:
            return "Agora"

        interval = self._get_interval_for_minute(minuto, escanteios)
        next_poll = self._last_poll[jogo_id] + timedelta(seconds=interval)
        seconds_until = (next_poll - datetime.now()).total_seconds()

        if seconds_until <= 0:
            return "Agora"

        minutes = int(seconds_until / 60)
        seconds = int(seconds_until % 60)
        return f"{minutes}m {seconds}s"

    def clear_finished_games(self, active_game_ids: List[int]):
        """Remove jogos finalizados do cache."""
        finished = [gid for gid in self._last_poll if gid not in active_game_ids]
        for gid in finished:
            del self._last_poll[gid]

    def get_stats(self) -> Dict:
        return {
            "jogos_monitorados": len(self._last_poll),
            "intervalos": self.INTERVALS,
        }
