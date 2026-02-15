"""
Cliente assincrono para WAHA (WhatsApp HTTP API).
Documentacao: https://github.com/devlikeapro/waha
"""

import json
import aiohttp
import logging
from typing import Optional, Dict
from dataclasses import dataclass

logger = logging.getLogger("CPES.WhatsApp")


@dataclass
class WAHAConfig:
    """Configuracao do cliente WAHA."""
    base_url: str = "http://localhost:3000"
    session_name: str = "cpes-alerts"
    api_key: Optional[str] = None
    timeout: int = 30


class WhatsAppClient:
    """Cliente para envio de mensagens via WAHA API."""

    def __init__(self, config: WAHAConfig):
        self.config = config
        self._session: Optional[aiohttp.ClientSession] = None
        self._headers: Dict[str, str] = {}
        if config.api_key:
            self._headers["X-Api-Key"] = config.api_key

    async def __aenter__(self):
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()

    async def start(self):
        if self._session is None or self._session.closed:
            timeout = aiohttp.ClientTimeout(total=self.config.timeout)
            self._session = aiohttp.ClientSession(
                headers=self._headers, timeout=timeout
            )
            logger.info("WhatsApp client iniciado")

    async def close(self):
        if self._session and not self._session.closed:
            await self._session.close()
            self._session = None
            logger.info("WhatsApp client encerrado")

    async def _request(
        self, method: str, endpoint: str, data: Optional[Dict] = None
    ) -> Dict:
        if not self._session or self._session.closed:
            await self.start()

        url = f"{self.config.base_url}/api/{endpoint}"

        try:
            async with self._session.request(method, url, json=data) as response:
                body = await response.text()
                ct = response.headers.get("Content-Type", "")

                # Se receber HTML (404 do Next.js, etc.) em vez de JSON
                if "application/json" not in ct:
                    logger.error(
                        "WAHA retornou HTML em vez de JSON (status %s). "
                        "Verifique se WAHA_URL aponta para o WAHA correto. "
                        "Conflito de porta? Dashboard Next.js usa 3000, WAHA precisa de outra porta (ex: 8080). "
                        "URL: %s | Content-Type: %s",
                        response.status,
                        url,
                        ct,
                    )
                    raise aiohttp.ClientError(
                        f"WAHA indisponivel: recebeu HTML em vez de JSON (porta errada?). "
                        f"Verifique WAHA_URL no .env. URL: {url}"
                    )

                result = json.loads(body)
                logger.debug(f"WAHA {method} {endpoint} -> {response.status}")

                if response.status >= 400:
                    logger.error(f"WAHA erro {response.status}: {result}")

                return result

        except aiohttp.ClientError as e:
            logger.error(f"WAHA conexao erro: {endpoint} - {e}")
            raise
        except Exception as e:
            logger.error(f"WAHA erro inesperado: {e}")
            raise

    # --- Sessao ---

    async def start_session(self, config: Optional[Dict] = None) -> Dict:
        data = {"name": self.config.session_name}
        if config:
            data["config"] = config
        return await self._request("POST", "sessions/start", data)

    async def stop_session(self) -> Dict:
        return await self._request(
            "POST", f"sessions/{self.config.session_name}/stop"
        )

    async def check_status(self) -> Dict:
        return await self._request(
            "GET", f"sessions/{self.config.session_name}"
        )

    async def get_qr_code(self) -> Dict:
        return await self._request(
            "GET", f"sessions/{self.config.session_name}/auth/qr"
        )

    async def logout_session(self) -> Dict:
        return await self._request(
            "POST", f"sessions/{self.config.session_name}/logout"
        )

    # --- Mensagens ---

    async def send_text(self, chat_id: str, text: str) -> Dict:
        data = {
            "session": self.config.session_name,
            "chatId": chat_id,
            "text": text,
        }
        result = await self._request("POST", "sendText", data)
        logger.info(f"Mensagem enviada para {chat_id[:15]}...")
        return result

    async def send_image(
        self, chat_id: str, image_url: str, caption: Optional[str] = None
    ) -> Dict:
        data = {
            "session": self.config.session_name,
            "chatId": chat_id,
            "url": image_url,
        }
        if caption:
            data["caption"] = caption
        return await self._request("POST", "sendImage", data)

    async def send_file(
        self, chat_id: str, file_url: str, filename: Optional[str] = None
    ) -> Dict:
        data = {
            "session": self.config.session_name,
            "chatId": chat_id,
            "url": file_url,
        }
        if filename:
            data["filename"] = filename
        return await self._request("POST", "sendFile", data)

    # --- Utilidades ---

    async def check_number_status(self, phone: str) -> Dict:
        data = {"session": self.config.session_name, "phone": phone}
        return await self._request("POST", "checkNumberStatus", data)

    @staticmethod
    def format_chat_id(phone: str) -> str:
        """Formata telefone para chat_id WAHA (ex: 5511999999999@c.us).

        Aceita formatos: +5541..., 5541..., 41..., +6140508..., 6140508...
        Numero com codigo internacional (61=AU, 44=UK, 1=US, etc.): usa direto.
        Se tiver 10-11 digitos sem codigo internacional, assume Brasil (55).
        """
        clean = "".join(filter(str.isdigit, phone))
        # Ja tem codigo internacional - usar direto (61=Australia, 44=UK, 1=US, etc.)
        if clean.startswith("61") or clean.startswith("44") or clean.startswith("1"):
            pass
        elif len(clean) <= 11 and not clean.startswith("55"):
            clean = "55" + clean  # Brasil sem codigo
        return f"{clean}@c.us"
