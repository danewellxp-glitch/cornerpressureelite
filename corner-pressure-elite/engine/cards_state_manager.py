"""
Cards State Manager — Gerencia estado dos alertas de cartoes ja enviados.

Mesmo conceito do StateManager de escanteios, mas para sinais de cartoes.
"""

import logging
from typing import Dict, Optional
from datetime import datetime

from data.models import SinalCartoes
from config import (
    CARTOES_REAVALIACAO_MIN_INTERVALO,
    CARTOES_REAVALIACAO_EDGE_DELTA,
    CARTOES_REAVALIACAO_SCORE_DELTA,
    CARTOES_REAVALIACAO_DELTA_CARTOES,
    CARTOES_MIN_SCORE_NORMAL,
)

logger = logging.getLogger("CPES.CardsStateManager")

# Espelha state_manager.ABSENCE_CYCLES_THRESHOLD — evita duplicar sinal inicial
# quando o live fetch tem soluço momentâneo.
ABSENCE_CYCLES_THRESHOLD = 3


class CardsAlertState:
    """Estado de um alerta de cartoes ja enviado para um jogo."""

    def __init__(self, sinal: SinalCartoes):
        self.jogo_id = sinal.jogo.id
        self.primeiro_sinal = sinal
        self.ultimo_sinal = sinal
        self.ultimo_alerta_time = datetime.now()
        self.num_alertas = 1
        self.absence_count = 0


class CardsStateManager:
    """Gerencia estado dos jogos ja alertados para cartoes e logica de re-avaliacao."""

    def __init__(self):
        self._alertas: Dict[int, CardsAlertState] = {}

    def ja_alertou(self, jogo_id: int) -> bool:
        return jogo_id in self._alertas

    def registrar_alerta(self, sinal: SinalCartoes):
        jogo_id = sinal.jogo.id
        self._alertas[jogo_id] = CardsAlertState(sinal)
        logger.info(f"Alerta CARTOES registrado: jogo {jogo_id} ({sinal.jogo.descricao})")

    def deve_reavaliar(self, jogo_id: int, novo_sinal: SinalCartoes) -> bool:
        """Verifica se deve enviar re-avaliacao de cartoes.

        Lógica nova (2026-05-11): exige tensão crescente real do jogo + recálculo
        significativo. Critério:
            delta_min >= CARTOES_REAVALIACAO_MIN_INTERVALO (5min)
            AND (delta_cartoes >= 1 OR delta_edge >= 1.0 OR delta_score >= 2 OR linha_mudou)
            AND novo.tension_score >= CARTOES_MIN_SCORE_NORMAL (jogo ainda qualificado)
        """
        if jogo_id not in self._alertas:
            return False

        state = self._alertas[jogo_id]

        agora = datetime.now()
        delta_minutos = (agora - state.ultimo_alerta_time).total_seconds() / 60
        if delta_minutos < CARTOES_REAVALIACAO_MIN_INTERVALO:
            return False

        if novo_sinal.tension_score < CARTOES_MIN_SCORE_NORMAL:
            return False

        anterior = state.ultimo_sinal

        delta_cartoes = (
            (novo_sinal.jogo.cartoes_amarelos_total or 0)
            - (anterior.jogo.cartoes_amarelos_total or 0)
        )
        delta_edge = novo_sinal.edge - anterior.edge
        delta_score = novo_sinal.tension_score - anterior.tension_score
        linha_mudou = novo_sinal.jogo.linha_cartoes != anterior.jogo.linha_cartoes

        tensao_real = delta_cartoes >= CARTOES_REAVALIACAO_DELTA_CARTOES
        edge_aumentou = delta_edge >= CARTOES_REAVALIACAO_EDGE_DELTA
        score_aumentou = delta_score >= CARTOES_REAVALIACAO_SCORE_DELTA

        if tensao_real or edge_aumentou or score_aumentou or linha_mudou:
            logger.info(
                f"Re-avaliacao CARTOES aprovada: jogo {jogo_id} | "
                f"delta_cartoes={delta_cartoes} delta_edge={delta_edge:+.2f} "
                f"delta_score={delta_score} linha_mudou={linha_mudou} "
                f"score_atual={novo_sinal.tension_score}"
            )
            return True

        return False

    def atualizar_reavaliacao(self, sinal: SinalCartoes):
        """Atualiza estado apos re-avaliacao de cartoes."""
        jogo_id = sinal.jogo.id
        if jogo_id in self._alertas:
            state = self._alertas[jogo_id]
            # Preencher dados do primeiro alerta
            primeiro = state.primeiro_sinal
            sinal.reavaliacao = True
            sinal.primeiro_minuto = primeiro.jogo.minuto
            sinal.primeiro_cartoes = primeiro.jogo.cartoes_amarelos_total
            sinal.primeiro_linha = primeiro.jogo.linha_cartoes
            sinal.primeiro_projecao = primeiro.projecao_cartoes
            sinal.primeiro_edge = primeiro.edge
            sinal.primeiro_score = primeiro.tension_score

            state.ultimo_sinal = sinal
            state.ultimo_alerta_time = datetime.now()
            state.num_alertas += 1
            logger.info(f"Re-avaliacao CARTOES #{state.num_alertas} registrada: jogo {jogo_id}")

    def get_state(self, jogo_id: int) -> Optional[CardsAlertState]:
        return self._alertas.get(jogo_id)

    def limpar_jogos_encerrados(self, jogos_ativos_ids: set):
        """Remove jogos que sumiram do live fetch por N ciclos seguidos.

        Mesma tolerância de `state_manager.limpar_jogos_encerrados` — evita
        que um soluço da API dispare um segundo sinal "inicial".
        """
        for jid, state in list(self._alertas.items()):
            if jid in jogos_ativos_ids:
                state.absence_count = 0
                continue
            state.absence_count += 1
            if state.absence_count >= ABSENCE_CYCLES_THRESHOLD:
                logger.info(
                    f"Removendo jogo encerrado do estado CARTOES: {jid} "
                    f"(ausente por {state.absence_count} ciclos)"
                )
                del self._alertas[jid]
