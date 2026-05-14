"""End-to-end smoke test: NotificationManager -> WAHA -> WhatsApp.

Roda dentro do container cpes-main (tem .env, deps e network access ao WAHA).
Constroi um JogoAoVivo + Sinal sinteticos e dispara send_signal pelo
NotificationManager (mesmo caminho que main.py usa em producao).
"""
import asyncio
import logging
import sys
import os

sys.path.insert(0, "/app")

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(name)s | %(levelname)s | %(message)s")

from config import (
    WAHA_URL, WAHA_SESSION_NAME, WAHA_API_KEY,
    WHATSAPP_GROUP_ID, WHATSAPP_ADMIN, WHATSAPP_UPDATES,
)
from data.models import JogoAoVivo, Sinal
from notifier.whatsapp_client import WAHAConfig
from notifier.notification_manager import NotificationManager


async def main():
    jogo = JogoAoVivo(
        id=999999999,
        liga_id=39,
        liga_nome="[E2E TEST] Premier League",
        time_casa="Manchester City",
        time_fora="Arsenal",
        placar_casa=1,
        placar_fora=1,
        minuto=72,
        escanteios_total=9,
        escanteios_casa=5,
        escanteios_fora=4,
        linha_atual=11.5,
        odd_atual=1.85,
        odd_betano=1.85,
        odd_bet365=1.83,
        escanteios_ultimos_10min=3,
        escanteios_ultimos_5min=2,
        ataques_perigosos_ultimos_10min=7,
        posse_ultimos_10min=58.0,
        finalizacoes_recentes=4,
        media_historica_combinada=10.8,
    )
    sinal = Sinal(
        tipo="PREMIUM",
        jogo=jogo,
        pressure_score=9,
        projecao=12.4,
        edge=1.6,
    )

    cfg = WAHAConfig(
        base_url=WAHA_URL,
        session_name=WAHA_SESSION_NAME,
        api_key=WAHA_API_KEY or None,
    )
    notifier = NotificationManager(
        cfg,
        group_id=WHATSAPP_GROUP_ID,
        admin_number=WHATSAPP_ADMIN,
        updates_number=WHATSAPP_UPDATES,
    )
    await notifier.start()
    print(f"[E2E] WAHA_URL={WAHA_URL} session={WAHA_SESSION_NAME} group={WHATSAPP_GROUP_ID[:20]}...")
    print(f"[E2E] admin={WHATSAPP_ADMIN[:6]}*** updates={WHATSAPP_UPDATES[:6]}***")
    print("[E2E] Disparando send_signal (PREMIUM ManCity vs Arsenal 1-1 min72, 9 esc, edge 1.6)...")
    await notifier.send_signal(sinal)
    print("[E2E] send_signal retornou sem excecao. Verifique o WhatsApp.")
    await notifier.close()


if __name__ == "__main__":
    asyncio.run(main())
