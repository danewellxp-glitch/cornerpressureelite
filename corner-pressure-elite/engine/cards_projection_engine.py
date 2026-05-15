import logging

from data.models import JogoAoVivo
from config import (
    CARTOES_PROJECAO_MINUTO_TOTAL,
    CARTOES_AJUSTE_TENSAO_FATOR,
    CARTOES_AJUSTE_HISTORICO_THRESHOLD,
    CARTOES_AJUSTE_HISTORICO_VALOR,
)

logger = logging.getLogger("CPES.CardsProjection")


class CardsProjectionEngine:
    """
    Modelo hibrido de projecao de cartoes amarelos.

    Combina 3 componentes:
    1. Ritmo base (cartoes/minuto * 95)
    2. Ajuste de tensao (tension_score * 0.15)
    3. Ajuste historico (+0.3 se media > 4.0)
    """

    def calcular_projecao(self, jogo: JogoAoVivo, tension_score: int) -> float:
        # 1. Ritmo base
        ritmo = self._calcular_ritmo_base(jogo.cartoes_amarelos_total, jogo.minuto)

        # 2. Ajuste de tensao
        ajuste_tensao = tension_score * CARTOES_AJUSTE_TENSAO_FATOR

        # 3. Ajuste historico
        ajuste_historico = self._calcular_ajuste_historico(
            jogo.media_historica_cartoes
        )

        projecao = ritmo + ajuste_tensao + ajuste_historico

        logger.debug(
            f"Projecao cartoes {jogo.descricao}: "
            f"ritmo={ritmo:.2f} + tensao={ajuste_tensao:.2f} + "
            f"hist={ajuste_historico:.2f} = {projecao:.2f}"
        )

        return round(projecao, 2)

    @staticmethod
    def _calcular_ritmo_base(cartoes: int, minuto: int) -> float:
        if minuto <= 0:
            return 0.0
        ritmo_por_minuto = cartoes / minuto
        return ritmo_por_minuto * CARTOES_PROJECAO_MINUTO_TOTAL

    @staticmethod
    def _calcular_ajuste_historico(media_historica: float) -> float:
        if media_historica > CARTOES_AJUSTE_HISTORICO_THRESHOLD:
            return CARTOES_AJUSTE_HISTORICO_VALOR
        return 0.0
