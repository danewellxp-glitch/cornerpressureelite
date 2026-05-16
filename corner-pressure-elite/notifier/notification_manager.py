"""
Gerenciador de notificacoes WhatsApp via WAHA.
- Sinais e re-avaliacoes -> grupo WhatsApp
- Broadcast filtrado por tier -> DM dos users elegíveis
- Erros e status -> admin pessoal
- Resumo diario -> grupo WhatsApp
"""

import asyncio
import logging
from datetime import datetime
from typing import Optional

from data.models import Sinal, SinalCartoes
from notifier.whatsapp_client import WhatsAppClient, WAHAConfig
from notifier.message_formatter import MessageFormatter
from notifier.cards_message_formatter import CardsMessageFormatter
from engine.strategy_config import CORNER_STRATEGIES, CARD_STRATEGIES

logger = logging.getLogger("CPES.NotifManager")


class NotificationManager:
    """Gerencia envio de notificacoes via WhatsApp."""

    def __init__(
        self,
        waha_config: WAHAConfig,
        group_id: str,
        admin_number: str,
        updates_number: str = "",
        cards_group_id: str = "",
        database=None,
    ):
        self.client = WhatsAppClient(waha_config)
        self.group_id = group_id  # ex: 120363424218619609@g.us
        self.cards_group_id = cards_group_id
        self.admin_chat_id = (
            WhatsAppClient.format_chat_id(admin_number) if admin_number else ""
        )
        self.formatter = MessageFormatter()
        self.cards_formatter = CardsMessageFormatter()
        self.database = database

        # Cache de sinais para re-avaliacao
        self._sinais_enviados: dict[int, Sinal] = {}
        self._last_notification_time: dict[int, datetime] = {}
        self._min_interval_seconds = 180  # 3 minutos

    async def start(self):
        await self.client.start()
        logger.info(
            f"NotificationManager iniciado | "
            f"Grupo: {self.group_id[:20]}... | "
            f"Admin: {self.admin_chat_id[:15]}..."
        )

    async def close(self):
        await self.client.close()
        logger.info("NotificationManager encerrado")

    # --- Sinais (vao para o GRUPO) ---

    async def send_signal(self, sinal: Sinal) -> bool:
        try:
            message = self.formatter.format_signal(sinal)
            success = await self._send_to_group(message)

            if success:
                self._sinais_enviados[sinal.jogo.id] = sinal
                self._last_notification_time[sinal.jogo.id] = datetime.now()
                logger.info(
                    f"Sinal {sinal.tipo} enviado ao grupo: {sinal.jogo.descricao}"
                )
            return success

        except Exception as e:
            logger.error(f"Erro ao enviar sinal: {e}")
            return False

    async def send_signal_to_user(
        self,
        sinal: Sinal,
        user_id: int,
        user_whatsapp: str,
        market: str = "corners",
    ) -> bool:
        """Envia sinal de escanteios para um usuario apenas se o tier dele bate.

        Busca a preferencia do usuario via `database.get_user_strategy(user_id, market)`
        (default 'moderate'). Se o tier estiver em `sinal.matching_tiers`, envia
        com prefixo do label da estrategia; caso contrario, pula e loga.
        """
        if self.database is None:
            logger.warning("Database nao configurado - pulando envio per-user")
            return False
        if not user_whatsapp:
            logger.info(f"Sinal pulado para user {user_id}: sem WhatsApp cadastrado")
            return False

        tier = await self.database.get_user_strategy(user_id, market)
        matching = sinal.matching_tiers or []

        if tier not in matching:
            logger.info(
                f"Sinal {sinal.tipo} pulado para user {user_id}: "
                f"tier={tier}, matching={matching}"
            )
            return False

        label = CORNER_STRATEGIES[tier].label
        body = self.formatter.format_signal(sinal)
        message = f"*[{label}]*\n{body}"

        chat_id = WhatsAppClient.format_chat_id(user_whatsapp)
        try:
            await self.client.send_text(chat_id, message)
            logger.info(
                f"Sinal {sinal.tipo} enviado para user {user_id} (tier={tier}): "
                f"{sinal.jogo.descricao}"
            )
            return True
        except Exception as e:
            logger.error(f"Falha ao enviar sinal para user {user_id}: {e}")
            return False

    def commit_corner_signal(self, sinal: Sinal) -> None:
        """Atualiza cache interno pós-broadcast per-user de sinal de escanteios.

        Necessário para que `send_reevaluation_to_user` consiga recuperar o
        sinal anterior. Chame UMA vez por sinal, após o loop de envio per-user
        terminar.
        """
        self._sinais_enviados[sinal.jogo.id] = sinal
        self._last_notification_time[sinal.jogo.id] = datetime.now()

    def commit_cards_signal(self, sinal: SinalCartoes) -> None:
        """Idem `commit_corner_signal` para o mercado de cartões."""
        key = ("cards", sinal.jogo.id)
        self._sinais_enviados[key] = sinal
        self._last_notification_time[key] = datetime.now()

    async def send_reevaluation_to_user(
        self,
        sinal_novo: Sinal,
        user_id: int,
        user_whatsapp: str,
        market: str = "corners",
        entrada_adicional: bool = False,
    ) -> bool:
        """Reavaliação per-user (filtra por tier matching). Não atualiza cache —
        use commit_corner_signal após o loop.

        Se `entrada_adicional=True`, formata a re-avaliação com a tag de
        oportunidade de entrada adicional (segunda aposta opcional).
        """
        jogo_id = sinal_novo.jogo.id
        sinal_anterior = self._sinais_enviados.get(jogo_id)
        if not sinal_anterior:
            return False
        if self.database is None or not user_whatsapp:
            return False
        tier = await self.database.get_user_strategy(user_id, market)
        if tier not in (sinal_novo.matching_tiers or []):
            return False
        label = CORNER_STRATEGIES[tier].label
        body = self.formatter.format_reevaluation(
            sinal_novo, sinal_anterior, entrada_adicional=entrada_adicional
        )
        message = f"*[{label}]*\n{body}"
        chat_id = WhatsAppClient.format_chat_id(user_whatsapp)
        try:
            await self.client.send_text(chat_id, message)
            return True
        except Exception as e:
            logger.error(f"Falha reavaliação user {user_id}: {e}")
            return False

    async def send_cards_reevaluation_to_user(
        self,
        sinal_novo: SinalCartoes,
        user_id: int,
        user_whatsapp: str,
        market: str = "cards",
    ) -> bool:
        """Reavaliação cartões per-user."""
        key = ("cards", sinal_novo.jogo.id)
        sinal_anterior = self._sinais_enviados.get(key)
        if not sinal_anterior:
            return False
        if self.database is None or not user_whatsapp:
            return False
        tier = await self.database.get_user_strategy(user_id, market)
        if tier not in (sinal_novo.matching_tiers or []):
            return False
        label = CARD_STRATEGIES[tier].label
        body = self.cards_formatter.format_reevaluation(sinal_novo, sinal_anterior)
        message = f"*[{label}]*\n{body}"
        chat_id = WhatsAppClient.format_chat_id(user_whatsapp)
        try:
            await self.client.send_text(chat_id, message)
            return True
        except Exception as e:
            logger.error(f"Falha reavaliação cartões user {user_id}: {e}")
            return False

    async def send_reevaluation(
        self,
        sinal_novo: Sinal,
        entrada_adicional: bool = False,
    ) -> bool:
        try:
            jogo_id = sinal_novo.jogo.id

            if not self._can_send_reevaluation(jogo_id):
                logger.debug(f"Re-avaliacao bloqueada (intervalo): jogo {jogo_id}")
                return False

            sinal_anterior = self._sinais_enviados.get(jogo_id)
            if not sinal_anterior:
                return False

            message = self.formatter.format_reevaluation(
                sinal_novo, sinal_anterior, entrada_adicional=entrada_adicional
            )
            success = await self._send_to_group(message)

            if success:
                # NÃO atualizar _sinais_enviados aqui — DMs per-user precisam ler
                # o mesmo `sinal_anterior` que o grupo usou. Atualização final fica
                # com commit_corner_signal após o loop de envio terminar.
                self._last_notification_time[jogo_id] = datetime.now()
                tag = " (+ entrada adicional)" if entrada_adicional else ""
                logger.info(
                    f"Re-avaliacao enviada ao grupo{tag}: {sinal_novo.jogo.descricao}"
                )

            return success

        except Exception as e:
            logger.error(f"Erro ao enviar re-avaliacao: {e}")
            return False

    async def send_daily_summary(self, stats: dict) -> bool:
        try:
            message = self.formatter.format_summary(stats)
            return await self._send_to_group(message)
        except Exception as e:
            logger.error(f"Erro ao enviar resumo: {e}")
            return False

    # --- Mensagem generica (grupo) ---

    async def send_message(self, message: str) -> bool:
        """Envia mensagem generica para o grupo."""
        try:
            return await self._send_to_group(message)
        except Exception as e:
            logger.error(f"Erro ao enviar mensagem: {e}")
            return False

    async def send_upcoming_games(self, games: list) -> bool:
        """Envia agenda de proximos jogos para o grupo."""
        try:
            message = self.formatter.format_upcoming_games(games)
            return await self._send_to_group(message)
        except Exception as e:
            logger.error(f"Erro ao enviar proximos jogos: {e}")
            return False

    async def send_pre_game_alert(self, games: list) -> bool:
        """Envia alerta de jogos prestes a comecar."""
        try:
            message = self.formatter.format_pre_game_alert(games)
            return await self._send_to_group(message)
        except Exception as e:
            logger.error(f"Erro ao enviar alerta pre-jogo: {e}")
            return False

    # --- Sinais de CARTOES (vao para CARDS_GROUP) ---

    async def send_cards_signal(self, sinal: SinalCartoes) -> bool:
        try:
            message = self.cards_formatter.format_signal(sinal)
            success = await self._send_to_cards_group(message)

            if success:
                self._sinais_enviados[("cards", sinal.jogo.id)] = sinal
                self._last_notification_time[("cards", sinal.jogo.id)] = datetime.now()
                logger.info(
                    f"Sinal CARTOES {sinal.tipo} enviado: {sinal.jogo.descricao}"
                )
            return success

        except Exception as e:
            logger.error(f"Erro ao enviar sinal cartoes: {e}")
            return False

    async def send_cards_signal_to_user(
        self,
        sinal: SinalCartoes,
        user_id: int,
        user_whatsapp: str,
        market: str = "cards",
    ) -> bool:
        """Envia sinal de cartoes para um usuario apenas se o tier dele bate.

        Mesma logica de `send_signal_to_user`, mas para o mercado de cartoes.
        """
        if self.database is None:
            logger.warning("Database nao configurado - pulando envio per-user cartoes")
            return False
        if not user_whatsapp:
            logger.info(f"Sinal cartoes pulado para user {user_id}: sem WhatsApp cadastrado")
            return False

        tier = await self.database.get_user_strategy(user_id, market)
        matching = sinal.matching_tiers or []

        if tier not in matching:
            logger.info(
                f"Sinal cartoes {sinal.tipo} pulado para user {user_id}: "
                f"tier={tier}, matching={matching}"
            )
            return False

        label = CARD_STRATEGIES[tier].label
        body = self.cards_formatter.format_signal(sinal)
        message = f"*[{label}]*\n{body}"

        chat_id = WhatsAppClient.format_chat_id(user_whatsapp)
        try:
            await self.client.send_text(chat_id, message)
            logger.info(
                f"Sinal cartoes {sinal.tipo} enviado para user {user_id} (tier={tier}): "
                f"{sinal.jogo.descricao}"
            )
            return True
        except Exception as e:
            logger.error(f"Falha ao enviar sinal cartoes para user {user_id}: {e}")
            return False

    async def send_cards_reevaluation(self, sinal_novo: SinalCartoes) -> bool:
        try:
            jogo_key = ("cards", sinal_novo.jogo.id)

            if not self._can_send_reevaluation_key(jogo_key):
                logger.debug(f"Re-avaliacao cartoes bloqueada (intervalo): jogo {sinal_novo.jogo.id}")
                return False

            sinal_anterior = self._sinais_enviados.get(jogo_key)
            if not sinal_anterior:
                return False

            message = self.cards_formatter.format_reevaluation(sinal_novo, sinal_anterior)
            success = await self._send_to_cards_group(message)

            if success:
                # Mesmo cuidado de send_reevaluation: deixar commit_cards_signal
                # fazer o update final, depois dos DMs lerem o sinal anterior.
                self._last_notification_time[jogo_key] = datetime.now()
                logger.info(f"Re-avaliacao cartoes enviada: {sinal_novo.jogo.descricao}")

            return success

        except Exception as e:
            logger.error(f"Erro ao enviar re-avaliacao cartoes: {e}")
            return False

    async def send_cards_daily_summary(self, stats: dict) -> bool:
        try:
            message = self.cards_formatter.format_summary(stats)
            return await self._send_to_cards_group(message)
        except Exception as e:
            logger.error(f"Erro ao enviar resumo cartoes: {e}")
            return False

    async def send_cards_message(self, message: str) -> bool:
        """Envia mensagem genérica para o grupo de cartões."""
        try:
            return await self._send_to_cards_group(message)
        except Exception as e:
            logger.error(f"Erro ao enviar mensagem cartoes: {e}")
            return False

    # --- Erros e status (vao para o ADMIN) ---

    async def send_error_alert(self, error_message: str) -> bool:
        try:
            message = self.formatter.format_error(error_message)
            return await self._send_to_admin(message)
        except Exception as e:
            logger.error(f"Erro ao enviar alerta de erro: {e}")
            return False

    async def send_status(self, status: dict) -> bool:
        try:
            message = self.formatter.format_status(status)
            return await self._send_to_admin(message)
        except Exception as e:
            logger.error(f"Erro ao enviar status: {e}")
            return False

    # --- Internos ---

    async def _send_to_group(self, message: str) -> bool:
        """Envia mensagem para o grupo Escanteios."""
        if not self.group_id:
            logger.warning("Group ID nao configurado - apenas console")
            print("\n" + "=" * 50)
            print(message)
            print("=" * 50 + "\n")
            return True

        try:
            await self.client.send_text(self.group_id, message)
            return True
        except Exception as e:
            logger.error(f"Falha ao enviar para grupo: {e}")
            return False

    async def _send_to_admin(self, message: str) -> bool:
        """Envia mensagem privada para o admin."""
        if not self.admin_chat_id:
            logger.debug("Admin nao configurado - apenas console")
            print(message)
            return True

        try:
            await self.client.send_text(self.admin_chat_id, message)
            return True
        except Exception as e:
            logger.error(f"Falha ao enviar para admin: {e}")
            return False

    async def _send_to_cards_group(self, message: str) -> bool:
        """Envia mensagem para o grupo de cartoes."""
        if not self.cards_group_id:
            logger.debug("Grupo de cartoes nao configurado - mensagem descartada")
            return True

        try:
            await self.client.send_text(self.cards_group_id, message)
            return True
        except Exception as e:
            logger.error(f"Falha ao enviar para grupo cartoes: {e}")
            return False

    def _can_send_reevaluation(self, jogo_id: int) -> bool:
        if jogo_id not in self._last_notification_time:
            return False
        last = self._last_notification_time[jogo_id]
        elapsed = (datetime.now() - last).total_seconds()
        return elapsed >= self._min_interval_seconds

    def _can_send_reevaluation_key(self, key) -> bool:
        """Mesmo que _can_send_reevaluation mas aceita chave generica (tuple)."""
        if key not in self._last_notification_time:
            return False
        last = self._last_notification_time[key]
        elapsed = (datetime.now() - last).total_seconds()
        return elapsed >= self._min_interval_seconds

    def clear_game_cache(self, jogo_id: int):
        self._sinais_enviados.pop(jogo_id, None)
        self._last_notification_time.pop(jogo_id, None)

    def clear_all_cache(self):
        self._sinais_enviados.clear()
        self._last_notification_time.clear()
