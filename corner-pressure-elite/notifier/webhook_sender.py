import logging
import requests as req
from typing import Optional

from data.models import Sinal
from config import WEBHOOK_URL

logger = logging.getLogger("CPES.Notifier")


class WebhookSender:
    """Envia alertas formatados via webhook (WhatsApp/Telegram)."""

    def __init__(self, webhook_url: Optional[str] = None):
        self.webhook_url = webhook_url or WEBHOOK_URL

    def enviar_sinal(self, sinal: Sinal) -> bool:
        mensagem = self._formatar_sinal(sinal)
        return self._enviar(mensagem)

    def enviar_reavaliacao(self, sinal: Sinal) -> bool:
        mensagem = self._formatar_reavaliacao(sinal)
        return self._enviar(mensagem)

    def _enviar(self, mensagem: str) -> bool:
        # Sempre logar no console
        print("\n" + "=" * 50)
        print(mensagem)
        print("=" * 50 + "\n")

        if not self.webhook_url:
            logger.info("Webhook URL nao configurada - alerta apenas no console")
            return True

        try:
            response = req.post(
                self.webhook_url,
                json={"message": mensagem},
                headers={"Content-Type": "application/json"},
                timeout=10,
            )
            if response.status_code == 200:
                logger.info("Alerta enviado via webhook com sucesso")
                return True
            else:
                logger.error(f"Webhook retornou status {response.status_code}")
                return False

        except Exception as e:
            logger.error(f"Erro ao enviar webhook: {e}")
            return False

    @staticmethod
    def _formatar_sinal(sinal: Sinal) -> str:
        jogo = sinal.jogo
        emoji = "🔥" if sinal.tipo == "PREMIUM" else "🟡"
        tipo_label = "PREMIUM" if sinal.tipo == "PREMIUM" else "NORMAL"
        tipo_footer = "ENTRADA PREMIUM 🚀" if sinal.tipo == "PREMIUM" else "ENTRADA NORMAL"

        return (
            f"{emoji} OVER ESCANTEIOS – {tipo_label}\n"
            f"\n"
            f"🏆 Liga: {jogo.liga_nome}\n"
            f"⚽ Jogo: {jogo.descricao}\n"
            f"⏱️ Minuto: {jogo.minuto}\n"
            f"📊 Placar: {jogo.placar}\n"
            f"\n"
            f"📈 ANÁLISE:\n"
            f"Escanteios atuais: {jogo.escanteios_total}\n"
            f"Linha: {jogo.linha_atual}\n"
            f"Projeção: {sinal.projecao}\n"
            f"Edge: +{sinal.edge}\n"
            f"\n"
            f"🔥 Pressure Score: {sinal.pressure_score}/10\n"
            f"\n"
            f"💰 MERCADO:\n"
            f"Odd: {jogo.odd_atual}\n"
            f"Stake sugerida: 1u\n"
            f"\n"
            f"⚠️ Tipo: {tipo_footer}"
        )

    @staticmethod
    def _formatar_reavaliacao(sinal: Sinal) -> str:
        jogo = sinal.jogo

        return (
            f"🔄 RE-EVALUATION – SCENARIO IMPROVED\n"
            f"\n"
            f"🏆 Liga: {jogo.liga_nome}\n"
            f"⚽ Jogo: {jogo.descricao}\n"
            f"⏱️ Minuto: {jogo.minuto} (Alerta inicial: {sinal.primeiro_minuto})\n"
            f"\n"
            f"📈 MUDANÇAS:\n"
            f"Escanteios: {sinal.primeiro_escanteios} → {jogo.escanteios_total}\n"
            f"Linha: {sinal.primeiro_linha} → {jogo.linha_atual}\n"
            f"Projeção: {sinal.primeiro_projecao} → {sinal.projecao}\n"
            f"Edge: +{sinal.primeiro_edge} → +{sinal.edge}\n"
            f"Score: {sinal.primeiro_score} → {sinal.pressure_score}\n"
            f"\n"
            f"💡 Cenário melhorou significativamente\n"
            f"⚠️ Re-avaliação informativa apenas\n"
            f"   (Sem sugestão de stake adicional)"
        )
