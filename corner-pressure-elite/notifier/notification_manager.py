"""
Gerenciador de notificacoes WhatsApp via WAHA.
- Sinais e re-avaliacoes -> grupo WhatsApp
- Erros e status -> admin pessoal
- Resumo diario -> grupo WhatsApp
"""

import logging
from datetime import datetime

from data.models import Sinal
from notifier.whatsapp_client import WhatsAppClient, WAHAConfig
from notifier.message_formatter import MessageFormatter

logger = logging.getLogger("CPES.NotifManager")


class NotificationManager:
    """Gerencia envio de notificacoes via WhatsApp."""

    def __init__(
        self,
        waha_config: WAHAConfig,
        group_id: str,
        admin_number: str,
        updates_number: str = "",
    ):
        self.client = WhatsAppClient(waha_config)
        self.group_id = group_id  # ex: 120363424218619609@g.us
        self.admin_chat_id = (
            WhatsAppClient.format_chat_id(admin_number) if admin_number else ""
        )
        self.updates_chat_id = (
            WhatsAppClient.format_chat_id(updates_number) if updates_number else ""
        )
        self.formatter = MessageFormatter()

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

    # --- Sinais (vao para o GRUPO + UPDATES) ---

    async def send_signal(self, sinal: Sinal) -> bool:
        try:
            message = self.formatter.format_signal(sinal)
            success = await self._send_to_group(message)

            # Enviar tambem para numero de updates
            await self._send_to_updates(message)

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

    async def send_reevaluation(self, sinal_novo: Sinal) -> bool:
        try:
            jogo_id = sinal_novo.jogo.id

            if not self._can_send_reevaluation(jogo_id):
                logger.debug(f"Re-avaliacao bloqueada (intervalo): jogo {jogo_id}")
                return False

            sinal_anterior = self._sinais_enviados.get(jogo_id)
            if not sinal_anterior:
                return False

            message = self.formatter.format_reevaluation(sinal_novo, sinal_anterior)
            success = await self._send_to_group(message)

            # Enviar tambem para numero de updates
            await self._send_to_updates(message)

            if success:
                self._sinais_enviados[jogo_id] = sinal_novo
                self._last_notification_time[jogo_id] = datetime.now()
                logger.info(f"Re-avaliacao enviada ao grupo: {sinal_novo.jogo.descricao}")

            return success

        except Exception as e:
            logger.error(f"Erro ao enviar re-avaliacao: {e}")
            return False

    async def send_daily_summary(self, stats: dict) -> bool:
        try:
            message = self.formatter.format_summary(stats)
            await self._send_to_updates(message)
            return await self._send_to_group(message)
        except Exception as e:
            logger.error(f"Erro ao enviar resumo: {e}")
            return False

    # --- Erros e status (vao para o ADMIN + UPDATES) ---

    async def send_error_alert(self, error_message: str) -> bool:
        try:
            message = self.formatter.format_error(error_message)
            await self._send_to_updates(message)
            return await self._send_to_admin(message)
        except Exception as e:
            logger.error(f"Erro ao enviar alerta de erro: {e}")
            return False

    async def send_status(self, status: dict) -> bool:
        try:
            message = self.formatter.format_status(status)
            await self._send_to_updates(message)
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

    async def _send_to_updates(self, message: str) -> bool:
        """Envia mensagem para o numero de updates."""
        if not self.updates_chat_id:
            return True

        try:
            await self.client.send_text(self.updates_chat_id, message)
            return True
        except Exception as e:
            logger.error(f"Falha ao enviar para updates: {e}")
            return False

    def _can_send_reevaluation(self, jogo_id: int) -> bool:
        if jogo_id not in self._last_notification_time:
            return False
        last = self._last_notification_time[jogo_id]
        elapsed = (datetime.now() - last).total_seconds()
        return elapsed >= self._min_interval_seconds

    def clear_game_cache(self, jogo_id: int):
        self._sinais_enviados.pop(jogo_id, None)
        self._last_notification_time.pop(jogo_id, None)

    def clear_all_cache(self):
        self._sinais_enviados.clear()
        self._last_notification_time.clear()
