"""
Email Worker — PressureIQ
Sistema de eventos assíncrono baseado em asyncio.Queue.
Separação de responsabilidades:
  - API → publica evento (não bloqueia o request)
  - Worker → consome fila, renderiza template, envia email, registra log
"""
import asyncio
import logging
import secrets
from datetime import datetime, timedelta
from typing import Any

from services.email_service import render_template, send_email

logger = logging.getLogger("CPES.EmailWorker")

# Fila global de eventos (substitui Redis para este stack)
_event_queue: asyncio.Queue = asyncio.Queue()

# Tipos de evento suportados
EVENT_USER_REGISTERED = "USER_REGISTERED"
EVENT_PAYMENT_CONFIRMED = "PAYMENT_CONFIRMED"
EVENT_SUBSCRIPTION_CANCELLED = "SUBSCRIPTION_CANCELLED"
EVENT_SUBSCRIPTION_RENEWED = "SUBSCRIPTION_RENEWED"
EVENT_CHECKOUT_ABANDONED = "CHECKOUT_ABANDONED"


def publish_event(event_type: str, payload: dict) -> None:
    """
    Publica evento na fila de forma não-bloqueante.
    Chamar de qualquer endpoint sem await — não bloqueia o request.
    """
    try:
        _event_queue.put_nowait({"type": event_type, "payload": payload})
        logger.debug(f"[EmailWorker] Evento publicado: {event_type}")
    except asyncio.QueueFull:
        logger.error(f"[EmailWorker] Fila cheia! Evento {event_type} descartado.")


async def _handle_user_registered(payload: dict) -> None:
    """Envia email de boas-vindas com código de verificação."""
    from storage.database import Database
    db = Database()

    email = payload.get("email")
    name = payload.get("full_name", "").split()[0] or "Apostador"
    user_id = payload.get("user_id")

    # Gerar código seguro de 6 dígitos
    code = str(secrets.randbelow(900000) + 100000)  # 100000–999999
    expires_at = datetime.now() + timedelta(minutes=15)

    # Salvar código no banco
    await db.update_user_verification(email, code, expires_at)

    # Renderizar template externo
    html = render_template("welcome.html", {
        "name": name,
        "code": code,
        "expires_minutes": 15,
        "email": email,
    })

    ok, response = await send_email(
        to=email,
        subject="🔐 Verifique seu email — PressureIQ",
        html=html,
    )

    await db.log_email(
        user_id=user_id,
        email_type="welcome",
        status="sent" if ok else "failed",
        response=response[:500],
    )


async def _handle_payment_confirmed(payload: dict) -> None:
    """Envia confirmação de pagamento."""
    from storage.database import Database
    db = Database()

    email = payload.get("email")
    name = payload.get("full_name", "").split()[0] or "Apostador"
    user_id = payload.get("user_id")
    plan = payload.get("plan", "Pro")
    value = payload.get("value", "0,00")
    next_due = payload.get("next_due_date", "")

    html = render_template("payment.html", {
        "name": name,
        "plan": plan.capitalize(),
        "value": value,
        "date": datetime.now().strftime("%d/%m/%Y"),
        "next_due_date": next_due,
        "status": "Confirmado",
    })

    ok, response = await send_email(
        to=email,
        subject=f"✅ Pagamento confirmado — Plano {plan.capitalize()}",
        html=html,
    )

    await db.log_email(user_id=user_id, email_type="payment", status="sent" if ok else "failed", response=response[:500])


async def _handle_subscription_cancelled(payload: dict) -> None:
    """Envia confirmação de cancelamento."""
    from storage.database import Database
    db = Database()

    email = payload.get("email")
    name = payload.get("full_name", "").split()[0] or "Apostador"
    user_id = payload.get("user_id")
    access_until = payload.get("access_until", "")

    html = render_template("cancellation.html", {
        "name": name,
        "access_until": access_until,
        "reactivate_url": f"{payload.get('app_url', '')}/login",
    })

    ok, response = await send_email(
        to=email,
        subject="😔 Assinatura cancelada — PressureIQ",
        html=html,
    )

    await db.log_email(user_id=user_id, email_type="cancellation", status="sent" if ok else "failed", response=response[:500])


async def _handle_subscription_renewed(payload: dict) -> None:
    """Envia confirmação de renovação."""
    from storage.database import Database
    db = Database()

    email = payload.get("email")
    name = payload.get("full_name", "").split()[0] or "Apostador"
    user_id = payload.get("user_id")
    plan = payload.get("plan", "Pro")
    next_due = payload.get("next_due_date", "")

    html = render_template("renewal.html", {
        "name": name,
        "plan": plan.capitalize(),
        "next_due_date": next_due,
        "date": datetime.now().strftime("%d/%m/%Y"),
    })

    ok, response = await send_email(
        to=email,
        subject=f"🔄 Assinatura renovada — Plano {plan.capitalize()}",
        html=html,
    )

    await db.log_email(user_id=user_id, email_type="renewal", status="sent" if ok else "failed", response=response[:500])


async def _handle_checkout_abandoned(payload: dict) -> None:
    """E-mail de recuperação: user criou checkout pending e não pagou em 1h."""
    from storage.database import Database
    db = Database()

    email = payload.get("email")
    name = payload.get("full_name", "").split()[0] or "Apostador"
    user_id = payload.get("user_id")
    plan = (payload.get("plan") or "pro").lower()
    invoice_url = payload.get("invoice_url", "")
    plan_value = "R$ 39,90" if plan == "pro" else "R$ 89,90"

    html = render_template("checkout-abandoned.html", {
        "name": name,
        "plan": plan.capitalize(),
        "plan_value": plan_value,
        "invoice_url": invoice_url,
        "email": email,
    })

    ok, response = await send_email(
        to=email,
        subject=f"📍 Sua assinatura PressureIQ está esperando — finalize em 1 clique",
        html=html,
    )

    await db.log_email(
        user_id=user_id,
        email_type="checkout_abandoned",
        status="sent" if ok else "failed",
        response=response[:500],
    )


# Mapa de handlers por tipo de evento
_HANDLERS = {
    EVENT_USER_REGISTERED: _handle_user_registered,
    EVENT_PAYMENT_CONFIRMED: _handle_payment_confirmed,
    EVENT_SUBSCRIPTION_CANCELLED: _handle_subscription_cancelled,
    EVENT_SUBSCRIPTION_RENEWED: _handle_subscription_renewed,
    EVENT_CHECKOUT_ABANDONED: _handle_checkout_abandoned,
}


async def process_events() -> None:
    """
    Loop principal do worker. Roda em background via asyncio.create_task().
    Consome eventos da fila e despacha para o handler correto.
    """
    logger.info("[EmailWorker] Worker iniciado — aguardando eventos...")
    while True:
        try:
            event = await _event_queue.get()
            event_type = event.get("type")
            payload = event.get("payload", {})

            handler = _HANDLERS.get(event_type)
            if handler:
                try:
                    await handler(payload)
                except Exception as e:
                    logger.error(
                        f"[EmailWorker] Erro ao processar evento {event_type}: {e}",
                        exc_info=True,
                    )
            else:
                logger.warning(f"[EmailWorker] Evento desconhecido ignorado: {event_type}")

            _event_queue.task_done()
        except asyncio.CancelledError:
            logger.info("[EmailWorker] Worker encerrado.")
            break
        except Exception as e:
            logger.error(f"[EmailWorker] Erro inesperado no loop: {e}", exc_info=True)
            await asyncio.sleep(1)
