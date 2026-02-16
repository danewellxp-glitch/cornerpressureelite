import logging

from data.models import JogoAoVivo

logger = logging.getLogger("CPES.ScoreEngine")


class PressureScoreEngine:
    """
    Calcula o Pressure Score baseado em multiplos indicadores de pressao ofensiva.

    Pontuacao maxima teorica: 11 pontos
    Minimo para sinal NORMAL: 5 (Cenario B)
    Minimo para sinal PREMIUM: 8

    Componentes:
      - Ritmo de escanteios (est. 10min): 0 ou +3
      - Escanteio recente (est. 5min):    0 ou +1
      - Ataques perigosos (graduado):     0, +1, +2 ou +3
      - Time perdendo por 1 gol:          0 ou +2
      - Posse dominante (>= 60%):         0 ou +1
      - Finalizacoes (graduado):          0 ou +1

    NOTA: ataques_perigosos e finalizacoes sao TOTAIS do jogo (API nao fornece
    dados windowed). Normalizamos por taxa/minuto para discriminar jogos ativos
    de jogos mortos, evitando pontos inflados.
    """

    # Thresholds para ataques perigosos (combined rate por minuto)
    # Typical: 40-80 attacks em 90 min = 0.44-0.89/min
    ATK_RATE_HIGH = 1.0     # >= 60 em 60min -> muito agressivo
    ATK_RATE_MEDIUM = 0.7   # >= 42 em 60min -> acima da media
    ATK_RATE_LOW = 0.4      # >= 24 em 60min -> moderado

    # Thresholds para finalizacoes (combined rate por minuto)
    # Typical: 4-12 shots on goal em 90 min = 0.04-0.13/min
    SHOT_RATE_HIGH = 0.10   # >= 6 em 60min -> bom volume de finalizacoes

    # Threshold para posse dominante
    POSSE_DOMINANT = 60.0   # >= 60% = dominio claro (era 50%, sempre passava)

    def calcular(self, jogo: JogoAoVivo, log: bool = True) -> int:
        score = 0
        detalhes = []
        minuto = max(1, jogo.minuto)  # evitar divisao por zero

        # 1. Escanteios nos ultimos 10 minutos (estimado via rate): +3
        if jogo.escanteios_ultimos_10min >= 2:
            score += 3
            detalhes.append(f"+3 (escanteios_10min={jogo.escanteios_ultimos_10min})")

        # 2. Escanteio nos ultimos 5 minutos (estimado via rate): +1
        if jogo.escanteios_ultimos_5min >= 1:
            score += 1
            detalhes.append(f"+1 (escanteio_5min={jogo.escanteios_ultimos_5min})")

        # 3. Ataques perigosos — GRADUADO por taxa/minuto: 0, +1, +2 ou +3
        #    (dados sao TOTAL do jogo, normalizado para rate)
        atk_rate = jogo.ataques_perigosos_ultimos_10min / minuto
        if atk_rate >= self.ATK_RATE_HIGH:
            score += 3
            detalhes.append(f"+3 (ataques rate={atk_rate:.2f}/min ALTO)")
        elif atk_rate >= self.ATK_RATE_MEDIUM:
            score += 2
            detalhes.append(f"+2 (ataques rate={atk_rate:.2f}/min MEDIO)")
        elif atk_rate >= self.ATK_RATE_LOW:
            score += 1
            detalhes.append(f"+1 (ataques rate={atk_rate:.2f}/min BAIXO)")
        else:
            detalhes.append(f"+0 (ataques rate={atk_rate:.2f}/min INATIVO)")

        # 4. Time perdendo por 1 gol: +2
        if self._time_perdendo_por_1(jogo):
            score += 2
            detalhes.append("+2 (time perdendo por 1)")

        # 5. Posse de bola dominante (>= 60%): +1
        #    (dado e % geral do jogo; 60% indica dominio real)
        if jogo.posse_ultimos_10min >= self.POSSE_DOMINANT:
            score += 1
            detalhes.append(f"+1 (posse={jogo.posse_ultimos_10min:.0f}% >= {self.POSSE_DOMINANT:.0f}%)")
        else:
            detalhes.append(f"+0 (posse={jogo.posse_ultimos_10min:.0f}% < {self.POSSE_DOMINANT:.0f}%)")

        # 6. Finalizacoes — GRADUADO por taxa/minuto: 0 ou +1
        #    (dados sao TOTAL do jogo, normalizado para rate)
        shot_rate = jogo.finalizacoes_recentes / minuto
        if shot_rate >= self.SHOT_RATE_HIGH:
            score += 1
            detalhes.append(f"+1 (finalizacoes rate={shot_rate:.3f}/min ALTO)")
        else:
            detalhes.append(f"+0 (finalizacoes rate={shot_rate:.3f}/min BAIXO)")

        if log:
            logger.info(
                f"[SCORE] {jogo.descricao}: {score}/11 | {', '.join(detalhes)}"
            )

        return score

    @staticmethod
    def _time_perdendo_por_1(jogo: JogoAoVivo) -> bool:
        return jogo.diferenca_gols == 1
