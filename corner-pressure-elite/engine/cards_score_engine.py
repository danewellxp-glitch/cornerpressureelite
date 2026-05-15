import logging

from data.models import JogoAoVivo

logger = logging.getLogger("CPES.TensionScore")


class TensionScoreEngine:
    """
    Calcula o Tension Score para cartoes amarelos.

    Pontuacao maxima teorica: 11 pontos
    Minimo para sinal NORMAL: 5
    Minimo para sinal PREMIUM: 8

    Componentes:
      - Ritmo cartoes (est. 10min >= 2):    0 ou +3
      - Cartao recente (est. 5min >= 1):    0 ou +1
      - Faltas rate (graduado):             0, +1, +2 ou +3
      - Diferenca 1 gol (tensao tatica):    0 ou +2
      - Cartao vermelho (jogo esquentou):   0 ou +1
      - Minuto >= 70 (tensao final):        0 ou +1
    """

    # Thresholds para faltas (combined rate por minuto)
    # Typical: 20-30 fouls em 90 min = 0.22-0.33/min
    FOUL_RATE_HIGH = 0.40    # >= 24 em 60min -> muito agressivo
    FOUL_RATE_MEDIUM = 0.30  # >= 18 em 60min -> acima da media
    FOUL_RATE_LOW = 0.20     # >= 12 em 60min -> moderado

    # Minuto de tensao final
    MINUTO_TENSAO_FINAL = 70

    def calcular(self, jogo: JogoAoVivo, log: bool = True) -> int:
        score = 0
        detalhes = []
        minuto = max(1, jogo.minuto)

        # 1. Ritmo cartoes nos ultimos 10 minutos (estimado): +3
        if jogo.cartoes_ultimos_10min >= 2:
            score += 3
            detalhes.append(f"+3 (cartoes_10min={jogo.cartoes_ultimos_10min})")

        # 2. Cartao recente nos ultimos 5 minutos (estimado): +1
        if jogo.cartoes_ultimos_5min >= 1:
            score += 1
            detalhes.append(f"+1 (cartao_5min={jogo.cartoes_ultimos_5min})")

        # 3. Faltas — GRADUADO por taxa/minuto: 0, +1, +2 ou +3
        foul_rate = jogo.faltas_total / minuto
        if foul_rate >= self.FOUL_RATE_HIGH:
            score += 3
            detalhes.append(f"+3 (faltas rate={foul_rate:.2f}/min ALTO)")
        elif foul_rate >= self.FOUL_RATE_MEDIUM:
            score += 2
            detalhes.append(f"+2 (faltas rate={foul_rate:.2f}/min MEDIO)")
        elif foul_rate >= self.FOUL_RATE_LOW:
            score += 1
            detalhes.append(f"+1 (faltas rate={foul_rate:.2f}/min BAIXO)")
        else:
            detalhes.append(f"+0 (faltas rate={foul_rate:.2f}/min INATIVO)")

        # 4. Diferenca 1 gol (tensao tatica): +2
        if jogo.diferenca_gols == 1:
            score += 2
            detalhes.append("+2 (diferenca 1 gol)")

        # 5. Cartao vermelho (jogo esquentou): +1
        if jogo.cartoes_vermelhos_total >= 1:
            score += 1
            detalhes.append(f"+1 (vermelho={jogo.cartoes_vermelhos_total})")

        # 6. Minuto >= 70 (tensao final do jogo): +1
        if jogo.minuto >= self.MINUTO_TENSAO_FINAL:
            score += 1
            detalhes.append(f"+1 (min={jogo.minuto} >= {self.MINUTO_TENSAO_FINAL})")

        if log:
            logger.info(
                f"[TENSION] {jogo.descricao}: {score}/11 | {', '.join(detalhes)}"
            )

        return score
