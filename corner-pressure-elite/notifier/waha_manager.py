"""
Gerenciador persistente de cliente WhatsApp.
Mantém conexão ativa e reutiliza cliente para evitar STOPPED status.
"""

import logging
import asyncio
from typing import Optional
from notifier.whatsapp_client import WhatsAppClient, WAHAConfig
from config import WAHA_URL, WAHA_SESSION_NAME, WAHA_API_KEY

logger = logging.getLogger("CPES.WAHAManager")


class WAHASessionManager:
    """Gerencia sessão WhatsApp compartilhada e reutilizável."""
    
    _instance: Optional['WAHASessionManager'] = None
    _client: Optional[WhatsAppClient] = None
    _lock = asyncio.Lock()
    
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


# Singleton global
_manager = WAHASessionManager()


async def send_whatsapp_message(chat_id: str, text: str) -> dict:
    """Função helper para enviar mensagem WhatsApp."""
    return await _manager.send_message(chat_id, text)


async def get_whatsapp_client() -> WhatsAppClient:
    """Função helper para obter cliente WhatsApp."""
    return await _manager.get_client()
