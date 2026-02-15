import logging

from data.models import JogoAoVivo
from config import (
    PROJECAO_MINUTO_TOTAL,
    AJUSTE_PRESSAO_FATOR,
    AJUSTE_HISTORICO_THRESHOLD,
    AJUSTE_HISTORICO_VALOR,
)

logger = logging.getLogger("CPES.ProjectionEngine")


class ProjectionEngine:
    """
    Modelo hibrido de projecao de escanteios.

    Combina 3 componentes:
    1. Ritmo base (escanteios/minuto * 95)
    2. Ajuste de pressao (score * 0.25)
    3. Ajuste historico (+0.5 se media > 10.5)
    """

    def calcular_projecao(self, jogo: JogoAoVivo, pressure_score: int) -> float:
        # 1. Ritmo base
        ritmo = self._calcular_ritmo_base(jogo.escanteios_total, jogo.minuto)

        # 2. Ajuste de pressao
        ajuste_pressao = pressure_score * AJUSTE_PRESSAO_FATOR

        # 3. Ajuste historico
        ajuste_historico = self._calcular_ajuste_historico(
            jogo.media_historica_combinada
        )

        projecao = ritmo + ajuste_pressao + ajuste_historico

        logger.debug(
            f"Projecao {jogo.descricao}: "
            f"ritmo={ritmo:.2f} + pressao={ajuste_pressao:.2f} + "
            f"hist={ajuste_historico:.2f} = {projecao:.2f}"
        )

        return round(projecao, 2)

    @staticmethod
    def _calcular_ritmo_base(escanteios: int, minuto: int) -> float:
        if minuto <= 0:
            return 0.0
        ritmo_por_minuto = escanteios / minuto
        return ritmo_por_minuto * PROJECAO_MINUTO_TOTAL

    @staticmethod
    def _calcular_ajuste_historico(media_historica: float) -> float:
        if media_historica > AJUSTE_HISTORICO_THRESHOLD:
            return AJUSTE_HISTORICO_VALOR
        return 0.0
