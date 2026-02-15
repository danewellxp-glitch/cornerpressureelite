import logging
from typing import Optional
from datetime import datetime

from data.models import JogoAoVivo, Sinal
from engine.score_engine import PressureScoreEngine
from engine.projection_engine import ProjectionEngine
from config import (
    JANELA_ANTECIPADA_INICIO,
    MAX_DIFERENCA_GOLS,
    MIN_ESCANTEIOS_TOTAL,
    MIN_ESCANTEIOS_5MIN,
    MIN_ESCANTEIOS_JOGO_MORNO,
    MIN_SCORE_NORMAL,
    MIN_SCORE_PREMIUM,
    MIN_EDGE_NORMAL,
    MIN_EDGE_PREMIUM,
)

logger = logging.getLogger("CPES.DecisionEngine")


class DecisionEngine:
    """Motor de decisao - Avalia se deve emitir sinal."""

    def __init__(self):
        self.score_engine = PressureScoreEngine()
        self.projection_engine = ProjectionEngine()

    def avaliar(self, jogo: JogoAoVivo) -> Optional[Sinal]:
        # 1. Filtros estruturais
        motivo_bloqueio = self._verificar_filtros(jogo)
        if motivo_bloqueio:
            logger.debug(f"Bloqueado {jogo.descricao}: {motivo_bloqueio}")
            return None

        # 2. Pressure Score
        score = self.score_engine.calcular(jogo)
        if score < MIN_SCORE_NORMAL:
            logger.debug(
                f"Score insuficiente {jogo.descricao}: {score} < {MIN_SCORE_NORMAL}"
            )
            return None

        # 3. Projecao hibrida
        projecao = self.projection_engine.calcular_projecao(jogo, score)

        # 4. Edge
        edge = round(projecao - jogo.linha_atual, 2)

        # 5. Decisao
        if score >= MIN_SCORE_PREMIUM and edge >= MIN_EDGE_PREMIUM:
            sinal = Sinal(
                tipo="PREMIUM",
                jogo=jogo,
                pressure_score=score,
                projecao=projecao,
                edge=edge,
                timestamp=datetime.now(),
            )
            logger.info(
                f"SINAL PREMIUM: {jogo.descricao} | "
                f"Score={score} Edge={edge} Proj={projecao} Linha={jogo.linha_atual}"
            )
            return sinal

        elif score >= MIN_SCORE_NORMAL and edge >= MIN_EDGE_NORMAL:
            sinal = Sinal(
                tipo="NORMAL",
                jogo=jogo,
                pressure_score=score,
                projecao=projecao,
                edge=edge,
                timestamp=datetime.now(),
            )
            logger.info(
                f"SINAL NORMAL: {jogo.descricao} | "
                f"Score={score} Edge={edge} Proj={projecao} Linha={jogo.linha_atual}"
            )
            return sinal

        logger.debug(
            f"Sem sinal {jogo.descricao}: score={score} edge={edge}"
        )
        return None

    @staticmethod
    def _verificar_filtros(jogo: JogoAoVivo) -> Optional[str]:
        """Retorna motivo do bloqueio ou None se passou."""

        # Janela de monitoramento (50+ = janela antecipada + reta final)
        if jogo.minuto < JANELA_ANTECIPADA_INICIO:
            return f"Fora da janela (min {jogo.minuto})"

        # Diferenca de gols
        if jogo.diferenca_gols > MAX_DIFERENCA_GOLS:
            return f"Diferenca de gols alta ({jogo.diferenca_gols})"

        # Minimo de escanteios
        if jogo.escanteios_total < MIN_ESCANTEIOS_TOTAL:
            return f"Poucos escanteios ({jogo.escanteios_total})"

        # Escanteio recente
        if jogo.escanteios_ultimos_5min < MIN_ESCANTEIOS_5MIN:
            return "Sem escanteio nos ultimos 5 min"

        # Jogo morno (0x0 depois do min 60)
        if (
            jogo.placar_casa == 0
            and jogo.placar_fora == 0
            and jogo.minuto >= 60
            and jogo.escanteios_total < MIN_ESCANTEIOS_JOGO_MORNO
        ):
            return f"Jogo morno 0x0 com poucos escanteios ({jogo.escanteios_total})"

        # Bloqueio jogo morto (time sem escanteio no 1o tempo)
        if jogo.minuto > 45 and (jogo.escanteios_casa == 0 or jogo.escanteios_fora == 0):
            return "Time sem escanteio no 1o tempo"

        return None
