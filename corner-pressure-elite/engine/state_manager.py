import logging
from typing import Dict, Optional
from datetime import datetime

from data.models import Sinal
from config import (
    REAVALIACAO_MIN_INTERVALO,
    REAVALIACAO_EDGE_DELTA,
    REAVALIACAO_SCORE_DELTA,
)

logger = logging.getLogger("CPES.StateManager")


class AlertState:
    """Estado de um alerta ja enviado para um jogo."""

    def __init__(self, sinal: Sinal):
        self.jogo_id = sinal.jogo.id
        self.primeiro_sinal = sinal
        self.ultimo_sinal = sinal
        self.ultimo_alerta_time = datetime.now()
        self.num_alertas = 1


class StateManager:
    """Gerencia estado dos jogos ja alertados e logica de re-avaliacao."""

    def __init__(self):
        self._alertas: Dict[int, AlertState] = {}

    def ja_alertou(self, jogo_id: int) -> bool:
        return jogo_id in self._alertas

    def registrar_alerta(self, sinal: Sinal):
        jogo_id = sinal.jogo.id
        self._alertas[jogo_id] = AlertState(sinal)
        logger.info(f"Alerta registrado: jogo {jogo_id} ({sinal.jogo.descricao})")

    def deve_reavaliar(self, jogo_id: int, novo_sinal: Sinal) -> bool:
        """Verifica se deve enviar re-avaliacao."""
        if jogo_id not in self._alertas:
            return False

        state = self._alertas[jogo_id]

        # Intervalo minimo entre alertas
        agora = datetime.now()
        delta_minutos = (agora - state.ultimo_alerta_time).total_seconds() / 60
        if delta_minutos < REAVALIACAO_MIN_INTERVALO:
            return False

        anterior = state.ultimo_sinal

        # Linha mudou
        linha_mudou = novo_sinal.jogo.linha_atual != anterior.jogo.linha_atual

        # Edge aumentou significativamente
        edge_aumentou = (novo_sinal.edge - anterior.edge) >= REAVALIACAO_EDGE_DELTA

        # Score aumentou
        score_aumentou = (
            novo_sinal.pressure_score - anterior.pressure_score
        ) >= REAVALIACAO_SCORE_DELTA

        if linha_mudou or edge_aumentou or score_aumentou:
            logger.info(
                f"Re-avaliacao aprovada: jogo {jogo_id} | "
                f"linha_mudou={linha_mudou} edge_delta={novo_sinal.edge - anterior.edge:.2f} "
                f"score_delta={novo_sinal.pressure_score - anterior.pressure_score}"
            )
            return True

        return False

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
        """Remove jogos que nao estao mais ao vivo."""
        encerrados = [jid for jid in self._alertas if jid not in jogos_ativos_ids]
        for jid in encerrados:
            logger.info(f"Removendo jogo encerrado do estado: {jid}")
            del self._alertas[jid]
