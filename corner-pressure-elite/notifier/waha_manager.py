"""
Gerenciador persistente de cliente WhatsApp.
Mantém conexão ativa e reutiliza cliente para evitar STOPPED status.
"""

import logging
import asyncio
from typing import Optional, Dict
from datetime import datetime
from notifier.whatsapp_client import WhatsAppClient, WAHAConfig
from config import WAHA_URL, WAHA_SESSION_NAME, WAHA_API_KEY

logger = logging.getLogger("CPES.WAHAManager")


class WAHASessionManager:
    """Gerencia sessão WhatsApp compartilhada e reutilizável."""

    _instance: Optional['WAHASessionManager'] = None
    _client: Optional[WhatsAppClient] = None
    _lock = asyncio.Lock()
    _last_health_status: Optional[Dict] = None
    _last_health_check: Optional[datetime] = None
    _consecutive_failures: int = 0
    _alert_cooldown_seconds: int = 600  # 10 min entre alertas repetidos
    _last_alert_time: Optional[datetime] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    async def get_client(self) -> WhatsAppClient:
        """Retorna cliente WhatsApp existente ou cria novo."""
        async with self._lock:
            if self._client is None or (self._client._session and self._client._session.closed):
                logger.info("Criando novo cliente WhatsApp...")
                config = WAHAConfig(
                    base_url=WAHA_URL,
                    session_name=WAHA_SESSION_NAME,
                    api_key=WAHA_API_KEY or None,
                )
                self._client = WhatsAppClient(config)
                try:
                    await self._client.start()
                    logger.info("✓ Cliente WhatsApp inicializado")
                except Exception as e:
                    logger.warning(f"⚠️  Erro ao iniciar cliente: {e}")
                    # Continuar mesmo com erro - sessão pode estar em background

            return self._client

    async def send_message(self, chat_id: str, text: str) -> dict:
        """Envia mensagem via cliente persistente."""
        try:
            client = await self.get_client()
            result = await client.send_text(chat_id, text)
            logger.info(f"✓ Mensagem enviada para {chat_id[:25]}")
            return result
        except Exception as e:
            logger.error(f"✗ Erro ao enviar: {e}")
            # Fechar cliente para força reconexão na próxima vez
            if self._client:
                try:
                    await self._client.close()
                except:
                    pass
                self._client = None
            raise

    async def close(self):
        """Fecha cliente (apenas para shutdown gracioso)."""
        if self._client:
            try:
                await self._client.close()
            except:
                pass
            self._client = None

    async def check_session_health(self) -> Dict:
        """Verifica saúde da sessão WAHA e tenta recuperação automática.

        Returns:
            Dict com keys: status (str), healthy (bool), action_taken (str), details (dict)
        """
        now = datetime.now()
        result = {
            "status": "UNKNOWN",
            "healthy": False,
            "action_taken": "none",
            "details": {},
            "timestamp": now.isoformat(),
        }

        try:
            client = await self.get_client()
            status_data = await client.check_status()
            session_status = status_data.get("status", "UNKNOWN")
            result["status"] = session_status
            result["details"] = status_data

            if session_status == "WORKING":
                result["healthy"] = True
                self._consecutive_failures = 0
                logger.debug(f"WAHA healthcheck: session WORKING")
            else:
                self._consecutive_failures += 1
                logger.warning(
                    f"WAHA healthcheck: session {session_status} "
                    f"(falhas consecutivas: {self._consecutive_failures})"
                )
                recovery = await self._attempt_recovery(session_status)
                result["action_taken"] = recovery["action"]
                result["healthy"] = recovery["success"]
                result["details"]["recovery"] = recovery

            self._last_health_status = result
            self._last_health_check = now
            return result

        except Exception as e:
            self._consecutive_failures += 1
            error_msg = str(e)[:200]
            logger.error(f"WAHA healthcheck falhou: {error_msg}")
            result["status"] = "ERROR"
            result["details"]["error"] = error_msg
            self._last_health_status = result
            self._last_health_check = now
            return result

    async def _attempt_recovery(self, current_status: str) -> Dict:
        """Tenta recuperar sessão com status não-WORKING.

        Estratégia:
        1. Se STOPPED → tentar start_session
        2. Se falhar → recriar cliente do zero
        """
        result = {"action": "none", "success": False}

        try:
            client = await self.get_client()

            if current_status == "STOPPED":
                logger.info("WAHA recovery: tentando restart da sessão...")
                try:
                    await client.start_session()
                    # Verificar se ficou WORKING
                    check = await client.check_status()
                    if check.get("status") == "WORKING":
                        result = {"action": "session_restart", "success": True}
                        self._consecutive_failures = 0
                        logger.info("WAHA recovery: sessão restaurada com sucesso")
                        return result
                except Exception as restart_err:
                    logger.warning(f"WAHA recovery: start_session falhou: {restart_err}")

            # Fallback: recriar cliente do zero
            logger.info("WAHA recovery: recriando cliente do zero...")
            async with self._lock:
                if self._client:
                    try:
                        await self._client.close()
                    except:
                        pass
                    self._client = None

                config = WAHAConfig(
                    base_url=WAHA_URL,
                    session_name=WAHA_SESSION_NAME,
                    api_key=WAHA_API_KEY or None,
                )
                self._client = WhatsAppClient(config)
                await self._client.start()

                # Verificar se ficou WORKING
                check = await self._client.check_status()
                if check.get("status") == "WORKING":
                    result = {"action": "client_recreated", "success": True}
                    self._consecutive_failures = 0
                    logger.info("WAHA recovery: cliente recriado com sucesso")
                else:
                    result = {"action": "client_recreated", "success": False}
                    logger.warning(
                        f"WAHA recovery: cliente recriado mas status={check.get('status')}"
                    )

        except Exception as e:
            logger.error(f"WAHA recovery falhou: {e}")
            result = {"action": "recovery_failed", "success": False, "error": str(e)[:200]}

        return result

    def get_last_health(self) -> Optional[Dict]:
        """Retorna último resultado de healthcheck (síncrono, para API)."""
        return self._last_health_status

    def should_send_alert(self) -> bool:
        """Verifica se deve enviar alerta admin baseado no cooldown."""
        if self._last_alert_time is None:
            return True
        elapsed = (datetime.now() - self._last_alert_time).total_seconds()
        return elapsed >= self._alert_cooldown_seconds

    def mark_alert_sent(self):
        """Registra que alerta foi enviado (reseta cooldown)."""
        self._last_alert_time = datetime.now()


# Singleton global
_manager = WAHASessionManager()


async def send_whatsapp_message(chat_id: str, text: str) -> dict:
    """Função helper para enviar mensagem WhatsApp."""
    return await _manager.send_message(chat_id, text)


async def get_whatsapp_client() -> WhatsAppClient:
    """Função helper para obter cliente WhatsApp."""
    return await _manager.get_client()


async def check_waha_health() -> Dict:
    """Função helper para healthcheck WAHA."""
    return await _manager.check_session_health()


def get_waha_last_health() -> Optional[Dict]:
    """Função helper para último healthcheck (síncrono)."""
    return _manager.get_last_health()
