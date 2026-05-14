"""
Formatador de mensagens WhatsApp para cartoes amarelos (CPES).
Usa negrito (*texto*) compativel com WhatsApp.
"""

from typing import Dict
from data.models import SinalCartoes


class CardsMessageFormatter:
    """Formata sinais de cartoes para mensagens WhatsApp."""

    @staticmethod
    def format_signal(sinal: SinalCartoes) -> str:
        jogo = sinal.jogo
        emoji = "\U0001f525" if sinal.tipo == "PREMIUM" else "\U0001f7e1"
        tipo = sinal.tipo
        tipo_footer = (
            "ENTRADA PREMIUM \U0001f680"
            if sinal.tipo == "PREMIUM"
            else "ENTRADA NORMAL"
        )

        # Fonte das odds: única (CompositeOddsProvider) ou genérica (legado).
        if jogo.odds_source_cartoes in ("betano_bridge", "apifootball"):
            fonte_cartoes = (
                "Betano"
                if jogo.odds_source_cartoes == "betano_bridge"
                else "API-Football"
            )
        else:
            fonte_cartoes = "mercado"

        msg = (
            f"{emoji} *OVER CART\u00d5ES \u2013 {tipo}*\n"
            f"\n"
            f"\U0001f3c6 *Liga:* {jogo.liga_nome}\n"
            f"\u26bd *Jogo:* {jogo.time_casa} vs {jogo.time_fora}\n"
            f"\u23f1\ufe0f *Minuto:* {jogo.minuto}'\n"
            f"\U0001f4ca *Placar:* {jogo.placar_casa}-{jogo.placar_fora}\n"
            f"\n"
            f"\U0001f4c8 *AN\u00c1LISE:*\n"
            f"Cart\u00f5es amarelos: {jogo.cartoes_amarelos_total}\n"
            f"Cart\u00f5es vermelhos: {jogo.cartoes_vermelhos_total}\n"
            f"Faltas: {jogo.faltas_total}\n"
            f"Linha ({fonte_cartoes}): {jogo.linha_cartoes}\n"
            f"Proje\u00e7\u00e3o (CPES): {sinal.projecao_cartoes}\n"
            f"Edge: +{sinal.edge:.2f}\n"
            f"\n"
            f"\U0001f525 *Tension Score:* {sinal.tension_score}/11\n"
            f"\n"
            f"\U0001f4b0 *MERCADO (Odds ao vivo):*\n"
            f"Over: {jogo.odd_cartoes}x\n"
            f"Linha: {jogo.linha_cartoes}\n"
            f"Stake sugerida: 1u\n"
            f"\n"
            f"\u26a0\ufe0f *Tipo:* {tipo_footer}\n"
            f"\u23f0 {sinal.timestamp.strftime('%H:%M:%S')}"
        )
        return msg

    @staticmethod
    def format_reevaluation(sinal_novo: SinalCartoes, sinal_anterior: SinalCartoes) -> str:
        jogo = sinal_novo.jogo
        jogo_ant = sinal_anterior.jogo

        msg = (
            f"\U0001f504 *RE-EVALUATION CART\u00d5ES \u2013 SCENARIO IMPROVED*\n"
            f"\n"
            f"\U0001f3c6 *Liga:* {jogo.liga_nome}\n"
            f"\u26bd *Jogo:* {jogo.time_casa} vs {jogo.time_fora}\n"
            f"\u23f1\ufe0f *Minuto:* {jogo.minuto}' (Alerta inicial: {jogo_ant.minuto}')\n"
            f"\n"
            f"\U0001f4c8 *MUDAN\u00c7AS:*\n"
            f"Cart\u00f5es: {jogo_ant.cartoes_amarelos_total} \u2192 {jogo.cartoes_amarelos_total}\n"
        )

        if jogo_ant.linha_cartoes != jogo.linha_cartoes:
            msg += f"Linha: {jogo_ant.linha_cartoes} \u2192 {jogo.linha_cartoes}\n"

        msg += (
            f"Proje\u00e7\u00e3o: {sinal_anterior.projecao_cartoes} \u2192 {sinal_novo.projecao_cartoes}\n"
            f"Edge: +{sinal_anterior.edge:.2f} \u2192 +{sinal_novo.edge:.2f}\n"
            f"TScore: {sinal_anterior.tension_score} \u2192 {sinal_novo.tension_score}\n"
            f"\n"
            f"\U0001f4a1 Cen\u00e1rio melhorou significativamente\n"
            f"\u26a0\ufe0f Re-avalia\u00e7\u00e3o informativa apenas\n"
            f"   (Sem sugest\u00e3o de stake adicional)\n"
            f"\u23f0 {sinal_novo.timestamp.strftime('%H:%M:%S')}"
        )
        return msg

    @staticmethod
    def format_summary(stats: Dict) -> str:
        msg = (
            f"\U0001f4ca *RESUMO DI\u00c1RIO - CPES CART\u00d5ES*\n"
            f"\n"
            f"\U0001f4c8 *PERFORMANCE:*\n"
            f"Total de sinais: {stats.get('total', 0)}\n"
            f"\u2705 Greens: {stats.get('greens', 0)}\n"
            f"\u274c Reds: {stats.get('reds', 0)}\n"
            f"\U0001f4ca Winrate: {stats.get('winrate', 0):.1f}%\n"
            f"\U0001f4b0 ROI: {stats.get('roi_total', 0):.2f}u\n"
        )
        return msg
