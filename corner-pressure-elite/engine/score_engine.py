import logging

from data.models import JogoAoVivo

logger = logging.getLogger("CPES.ScoreEngine")


class PressureScoreEngine:
    """
    Calcula o Pressure Score baseado em multiplos indicadores de pressao ofensiva.

    Pontuacao maxima teorica: ~10 pontos
    Minimo para sinal NORMAL: 8
    Minimo para sinal PREMIUM: 9
    """

    def calcular(self, jogo: JogoAoVivo) -> int:
        score = 0
        detalhes = []

        # Escanteios nos ultimos 10 minutos (+3)
        if jogo.escanteios_ultimos_10min >= 2:
            score += 3
            detalhes.append(f"+3 (escanteios_10min={jogo.escanteios_ultimos_10min})")

        # Escanteio nos ultimos 5 minutos (+1)
        if jogo.escanteios_ultimos_5min >= 1:
            score += 1
            detalhes.append(f"+1 (escanteio_5min={jogo.escanteios_ultimos_5min})")

        # Ataques perigosos nos ultimos 10 minutos (+2)
        if jogo.ataques_perigosos_ultimos_10min >= 6:
            score += 2
            detalhes.append(
                f"+2 (ataques_perigosos={jogo.ataques_perigosos_ultimos_10min})"
            )

        # Time perdendo por 1 gol (+2)
        if self._time_perdendo_por_1(jogo):
            score += 2
            detalhes.append("+2 (time perdendo por 1)")

        # Posse de bola dominante (+1)
        if jogo.posse_ultimos_10min > 60:
            score += 1
            detalhes.append(f"+1 (posse={jogo.posse_ultimos_10min}%)")

        # Finalizacoes recentes (+1)
        if jogo.finalizacoes_recentes >= 3:
            score += 1
            detalhes.append(f"+1 (finalizacoes={jogo.finalizacoes_recentes})")

        logger.debug(
            f"Pressure Score {jogo.descricao}: {score}/10 | {', '.join(detalhes)}"
        )

        return score

    @staticmethod
    def _time_perdendo_por_1(jogo: JogoAoVivo) -> bool:
        return jogo.diferenca_gols == 1
