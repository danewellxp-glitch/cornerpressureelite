"""
Email Service — PressureIQ
Responsabilidade única: renderizar templates e enviar emails via Resend API.
Nunca chame este módulo diretamente de endpoints — use o email_worker.
"""
import logging
import asyncio
import aiohttp
from pathlib import Path
from typing import Optional
from jinja2 import Environment, FileSystemLoader, select_autoescape

from config import RESEND_API_KEY, EMAIL_FROM, APP_URL

logger = logging.getLogger("CPES.EmailService")

# Diretório de templates (relativo a este arquivo → ../templates)
TEMPLATES_DIR = Path(__file__).parent.parent / "templates"

# Jinja2 — carrega apenas arquivos .html, escapa HTML por padrão
_jinja_env = Environment(
    loader=FileSystemLoader(str(TEMPLATES_DIR)),
    autoescape=select_autoescape(["html"]),
)


def render_template(template_name: str, context: dict) -> str:
    """
    Renderiza um template HTML externo com Jinja2.
    Nunca monta HTML inline — todo HTML fica em /templates/*.html.
    """
    try:
        template = _jinja_env.get_template(template_name)
        return template.render(**context, app_url=APP_URL)
    except Exception as e:
        logger.error(f"[EmailService] Erro ao renderizar template '{template_name}': {e}")
        raise


async def send_email(
    to: str,
    subject: str,
    html: str,
    max_retries: int = 3,
) -> tuple[bool, str]:
    """
    Envia email via Resend API com retry automático (backoff exponencial).
    Retorna (sucesso, resposta_provider).
    """
    if not RESEND_API_KEY:
        logger.error("[EmailService] RESEND_API_KEY não configurada. Email não enviado.")
        return False, "RESEND_API_KEY ausente"

    payload = {
        "from": EMAIL_FROM,
        "to": [to],
        "subject": subject,
        "html": html,
    }

    for attempt in range(1, max_retries + 1):
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    "https://api.resend.com/emails",
                    headers={
                        "Authorization": f"Bearer {RESEND_API_KEY}",
                        "Content-Type": "application/json",
                    },
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=10),
                ) as resp:
                    body = await resp.text()
                    if resp.status in (200, 201):
                        logger.info(f"[EmailService] Email enviado para {to} (tentativa {attempt})")
                        return True, body
                    else:
                        logger.warning(
                            f"[EmailService] Resend retornou {resp.status} para {to} "
                            f"(tentativa {attempt}/{max_retries}): {body}"
                        )
        except Exception as e:
            logger.warning(
                f"[EmailService] Erro na tentativa {attempt}/{max_retries} para {to}: {e}"
            )

        if attempt < max_retries:
            await asyncio.sleep(2 ** attempt)  # backoff: 2s, 4s

    logger.error(f"[EmailService] Falha ao enviar email para {to} após {max_retries} tentativas.")
    return False, "Falha após retries"
