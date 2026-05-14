import logging
from typing import Dict, Optional
from datetime import datetime

from data.models import Sinal
from config import (
    REAVALIACAO_MIN_INTERVALO,
    REAVALIACAO_EDGE_DELTA,
    REAVALIACAO_SCORE_DELTA,
    REAVALIACAO_DELTA_ESCANTEIOS,
    REAVALIACAO_EDGE_REGRESSAO_MAX,
    REAVALIACAO_MAX_POR_JOGO,
    MIN_SCORE_NORMAL,
)

logger = logging.getLogger("CPES.StateManager")

# Thresholds para sugestão de entrada adicional
ENTRADA_ADICIONAL_EDGE_DELTA = 2.0   # Edge deve ter melhorado >= 2.0 desde o primeiro alerta
ENTRADA_ADICIONAL_MIN_ODD = 1.50     # Odd mínima para valer a pena
ENTRADA_ADICIONAL_MAX_MINUTO = 80    # Só sugere até o minuto 80

# Tolerância de ausência: jogo precisa sumir do live fetch N ciclos seguidos
# antes de ser removido do estado. Evita duplicar o sinal inicial quando a
# API tem um soluço momentâneo.
ABSENCE_CYCLES_THRESHOLD = 3


class AlertState:
    """Estado de um alerta ja enviado para um jogo."""

    def __init__(self, sinal: Sinal):
        self.jogo_id = sinal.jogo.id
        self.primeiro_sinal = sinal
        self.ultimo_sinal = sinal
        self.ultimo_alerta_time = datetime.now()
        self.num_alertas = 1
        self.absence_count = 0
        self.entrada_adicional_marcada = False


class StateManager:
    """Gerencia estado dos jogos ja alertados e logica de re-avaliacao."""

    def __init__(self):
        self._alertas: Dict[int, AlertState] = {}
        self._entradas_adicionais: set = set()  # jogo_ids que ja receberam sugestao adicional

    def ja_alertou(self, jogo_id: int) -> bool:
        return jogo_id in self._alertas

    def registrar_alerta(self, sinal: Sinal):
        jogo_id = sinal.jogo.id
        self._alertas[jogo_id] = AlertState(sinal)
        logger.info(f"Alerta registrado: jogo {jogo_id} ({sinal.jogo.descricao})")

    def deve_reavaliar(self, jogo_id: int, novo_sinal: Sinal) -> bool:
        """Verifica se deve enviar re-avaliacao. Conservador para não saturar o cliente.

        Critério (todos devem valer):
            1. delta_min >= REAVALIACAO_MIN_INTERVALO
            2. Score atual >= MIN_SCORE_NORMAL (jogo ainda qualificado)
            3. Re-avaliações enviadas < REAVALIACAO_MAX_POR_JOGO (teto)
            4. Pelo menos UM critério forte:
                 delta_esc >= REAVALIACAO_DELTA_ESCANTEIOS (3)
                 OR delta_edge >= REAVALIACAO_EDGE_DELTA (1.5)
                 OR delta_score >= REAVALIACAO_SCORE_DELTA (2)
                 OR linha mudou
            5. Edge NÃO regrediu mais que REAVALIACAO_EDGE_REGRESSAO_MAX (0.3) —
               re-avaliação só faz sentido quando o cenário realmente melhorou.
        """
        if jogo_id not in self._alertas:
            return False

        state = self._alertas[jogo_id]

        if state.num_alertas - 1 >= REAVALIACAO_MAX_POR_JOGO:
            return False

        agora = datetime.now()
        delta_minutos = (agora - state.ultimo_alerta_time).total_seconds() / 60
        if delta_minutos < REAVALIACAO_MIN_INTERVALO:
            return False

        if novo_sinal.pressure_score < MIN_SCORE_NORMAL:
            return False

        anterior = state.ultimo_sinal
        delta_escanteios = novo_sinal.jogo.escanteios_total - anterior.jogo.escanteios_total
        delta_edge = novo_sinal.edge - anterior.edge
        delta_score = novo_sinal.pressure_score - anterior.pressure_score
        linha_mudou = novo_sinal.jogo.linha_atual != anterior.jogo.linha_atual

        gatilho_forte = (
            delta_escanteios >= REAVALIACAO_DELTA_ESCANTEIOS
            or delta_edge >= REAVALIACAO_EDGE_DELTA
            or delta_score >= REAVALIACAO_SCORE_DELTA
            or linha_mudou
        )
        if not gatilho_forte:
            return False

        # Cenário precisa ter MELHORADO — não enviar se edge caiu significativamente.
        if delta_edge < -REAVALIACAO_EDGE_REGRESSAO_MAX:
            logger.debug(
                f"Re-avaliacao descartada (edge regrediu): jogo {jogo_id} "
                f"delta_edge={delta_edge:+.2f}"
            )
            return False

        logger.info(
            f"Re-avaliacao aprovada: jogo {jogo_id} | "
            f"delta_esc={delta_escanteios} delta_edge={delta_edge:+.2f} "
            f"delta_score={delta_score} linha_mudou={linha_mudou} "
            f"score_atual={novo_sinal.pressure_score} "
            f"reavals_enviadas={state.num_alertas - 1}/{REAVALIACAO_MAX_POR_JOGO}"
        )
        return True

    def deve_sugerir_entrada_adicional(self, jogo_id: int, novo_sinal: Sinal) -> bool:
        """Verifica se deve sugerir uma entrada adicional (segunda aposta) durante o jogo.

        Criterios:
        - Ja foi enviado alerta para o jogo
        - Edge melhorou >= 2.0 pontos desde o PRIMEIRO alerta
        - Minuto atual < 80
        - Odd atual >= 1.50
        - Ainda nao foi sugerida entrada adicional para este jogo
        """
        if jogo_id not in self._alertas:
            return False

        if jogo_id in self._entradas_adicionais:
            return False  # Ja sugerimos entrada adicional para este jogo

        state = self._alertas[jogo_id]
        primeiro = state.primeiro_sinal

        # Verificar minuto
        if novo_sinal.jogo.minuto >= ENTRADA_ADICIONAL_MAX_MINUTO:
            return False

        # Verificar melhora de edge desde o PRIMEIRO alerta
        edge_delta = novo_sinal.edge - primeiro.edge
        if edge_delta < ENTRADA_ADICIONAL_EDGE_DELTA:
            return False

        # Odd de referência. Fonte única (CompositeOddsProvider) usa odd_atual
        # direto; caminho legado pega a melhor entre Betano/Bet365/odd_atual.
        if novo_sinal.jogo.odds_source in ("betano_bridge", "apifootball"):
            melhor_odd = novo_sinal.jogo.odd_atual
        else:
            melhor_odd = max(
                novo_sinal.jogo.odd_betano,
                novo_sinal.jogo.odd_bet365,
                novo_sinal.jogo.odd_atual,
            )
        if melhor_odd < ENTRADA_ADICIONAL_MIN_ODD:
            return False

        logger.info(
            f"Entrada adicional aprovada: jogo {jogo_id} | "
            f"edge_delta={edge_delta:.2f} | minuto={novo_sinal.jogo.minuto} | odd={melhor_odd:.2f}"
        )
        return True

    def registrar_entrada_adicional(self, jogo_id: int):
        """Marca que ja foi sugerida entrada adicional para este jogo."""
        self._entradas_adicionais.add(jogo_id)
        if jogo_id in self._alertas:
            self._alertas[jogo_id].entrada_adicional_marcada = True
        logger.info(f"Entrada adicional registrada: jogo {jogo_id}")

    def atualizar_reavaliacao(self, sinal: Sinal):
        """Atualiza estado apos re-avaliacao."""
        jogo_id = sinal.jogo.id
        if jogo_id in self._alertas:
            state = self._alertas[jogo_id]
            # Preencher dados do primeiro alerta na re-avaliacao
            primeiro = state.primeiro_sinal
            sinal.reavaliacao = True
            sinal.primeiro_minuto = primeiro.jogo.minuto
            sinal.primeiro_escanteios = primeiro.jogo.escanteios_total
            sinal.primeiro_linha = primeiro.jogo.linha_atual
            sinal.primeiro_projecao = primeiro.projecao
            sinal.primeiro_edge = primeiro.edge
            sinal.primeiro_score = primeiro.pressure_score

            state.ultimo_sinal = sinal
            state.ultimo_alerta_time = datetime.now()
            state.num_alertas += 1
            logger.info(f"Re-avaliacao #{state.num_alertas} registrada: jogo {jogo_id}")

    def get_state(self, jogo_id: int) -> Optional[AlertState]:
        return self._alertas.get(jogo_id)

    def limpar_jogos_encerrados(self, jogos_ativos_ids: set):
        """Remove jogos que sumiram do live fetch por N ciclos seguidos.

        Tolera ausência momentânea (API com hiccup) — só limpa quando o jogo
        falta `ABSENCE_CYCLES_THRESHOLD` ciclos consecutivos. Se reaparecer,
        o contador zera. Sem isso, uma única falha de live fetch dispara
        um segundo sinal "inicial" para o mesmo jogo.
        """
        removidos: list = []
        for jid, state in list(self._alertas.items()):
            if jid in jogos_ativos_ids:
                state.absence_count = 0
                continue
            state.absence_count += 1
            if state.absence_count >= ABSENCE_CYCLES_THRESHOLD:
                logger.info(
                    f"Removendo jogo encerrado do estado: {jid} "
                    f"(ausente por {state.absence_count} ciclos)"
                )
                del self._alertas[jid]
                removidos.append(jid)

        # Limpar entradas adicionais dos que foram efetivamente removidos
        if removidos:
            self._entradas_adicionais.difference_update(removidos)
