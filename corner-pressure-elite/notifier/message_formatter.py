"""
Formatador de mensagens WhatsApp para o CPES.
Usa negrito (*texto*) compativel com WhatsApp.
"""

from typing import Dict
from data.models import Sinal


class MessageFormatter:
    """Formata sinais e alertas para mensagens WhatsApp."""

    @staticmethod
    def format_signal(sinal: Sinal) -> str:
        jogo = sinal.jogo
        emoji = "\U0001f525" if sinal.tipo == "PREMIUM" else "\U0001f7e1"
        tipo = sinal.tipo
        tipo_footer = (
            "ENTRADA PREMIUM \U0001f680"
            if sinal.tipo == "PREMIUM"
            else "ENTRADA NORMAL"
        )

        msg = (
            f"{emoji} *OVER ESCANTEIOS \u2013 {tipo}*\n"
            f"\n"
            f"\U0001f3c6 *Liga:* {jogo.liga_nome}\n"
            f"\u26bd *Jogo:* {jogo.time_casa} vs {jogo.time_fora}\n"
            f"\u23f1\ufe0f *Minuto:* {jogo.minuto}'\n"
            f"\U0001f4ca *Placar:* {jogo.placar_casa}-{jogo.placar_fora}\n"
            f"\n"
            f"\U0001f4c8 *AN\u00c1LISE:*\n"
            f"Escanteios atuais: {jogo.escanteios_total}\n"
            f"Linha: {jogo.linha_atual}\n"
            f"Proje\u00e7\u00e3o: {sinal.projecao}\n"
            f"Edge: +{sinal.edge:.2f}\n"
            f"\n"
            f"\U0001f525 *Pressure Score:* {sinal.pressure_score}/10\n"
            f"\n"
            f"\U0001f4b0 *MERCADO:*\n"
            f"Odd: {jogo.odd_atual}\n"
            f"Stake sugerida: 1u\n"
            f"\n"
            f"\u26a0\ufe0f *Tipo:* {tipo_footer}\n"
            f"\u23f0 {sinal.timestamp.strftime('%H:%M:%S')}"
        )
        return msg

    @staticmethod
    def format_reevaluation(sinal_novo: Sinal, sinal_anterior: Sinal) -> str:
        jogo = sinal_novo.jogo
        jogo_ant = sinal_anterior.jogo

        msg = (
            f"\U0001f504 *RE-EVALUATION \u2013 SCENARIO IMPROVED*\n"
            f"\n"
            f"\U0001f3c6 *Liga:* {jogo.liga_nome}\n"
            f"\u26bd *Jogo:* {jogo.time_casa} vs {jogo.time_fora}\n"
            f"\u23f1\ufe0f *Minuto:* {jogo.minuto}' (Alerta inicial: {jogo_ant.minuto}')\n"
            f"\n"
            f"\U0001f4c8 *MUDAN\u00c7AS:*\n"
            f"Escanteios: {jogo_ant.escanteios_total} \u2192 {jogo.escanteios_total}\n"
        )

        if jogo_ant.linha_atual != jogo.linha_atual:
            msg += f"Linha: {jogo_ant.linha_atual} \u2192 {jogo.linha_atual}\n"

        msg += (
            f"Proje\u00e7\u00e3o: {sinal_anterior.projecao} \u2192 {sinal_novo.projecao}\n"
            f"Edge: +{sinal_anterior.edge:.2f} \u2192 +{sinal_novo.edge:.2f}\n"
            f"Score: {sinal_anterior.pressure_score} \u2192 {sinal_novo.pressure_score}\n"
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
            f"\U0001f4ca *RESUMO DI\u00c1RIO - CPES*\n"
            f"\n"
            f"\U0001f4c8 *PERFORMANCE:*\n"
            f"Total de sinais: {stats.get('total', 0)}\n"
            f"\u2705 Greens: {stats.get('greens', 0)}\n"
            f"\u274c Reds: {stats.get('reds', 0)}\n"
            f"\U0001f4ca Winrate: {stats.get('winrate', 0):.1f}%\n"
            f"\U0001f4b0 ROI: {stats.get('roi_total', 0):.2f}u\n"
        )
        return msg

    @staticmethod
    def format_error(error_message: str) -> str:
        return (
            f"\u26a0\ufe0f *ERRO NO SISTEMA*\n"
            f"\n"
            f"\u274c {error_message}\n"
            f"\n"
            f"O sistema est\u00e1 tentando se recuperar..."
        )

    @staticmethod
    def format_status(status: Dict) -> str:
        online = "\U0001f7e2 Online" if status.get("online") else "\U0001f534 Offline"
        return (
            f"\U0001f916 *STATUS DO SISTEMA*\n"
            f"\n"
            f"{online}\n"
            f"\U0001f4e1 API Football: {status.get('api_requests', 0)}/{status.get('api_limit', 0)}\n"
            f"\U0001f441\ufe0f Jogos monitorados: {status.get('jogos_ativos', 0)}\n"
            f"\U0001f4ca Sinais hoje: {status.get('sinais_hoje', 0)}\n"
            f"\u23f0 \u00daltima atualiza\u00e7\u00e3o: {status.get('ultima_atualizacao', '?')}"
        )
