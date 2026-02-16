"""
Formatador de mensagens WhatsApp para o CPES.
Usa negrito (*texto*) compativel com WhatsApp.
"""

from typing import Dict, List
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
            f"Linha (mercado): {jogo.linha_atual}\n"
            f"Proje\u00e7\u00e3o (CPES): {sinal.projecao}\n"
            f"Edge: +{sinal.edge:.2f}\n"
            f"\n"
            f"\U0001f525 *Pressure Score:* {sinal.pressure_score}/10\n"
            f"\n"
            f"\U0001f4b0 *MERCADO (Odds ao vivo):*\n"
            f"Over: {jogo.odd_atual}x\n"
            f"Linha: {jogo.linha_atual}\n"
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
    def format_upcoming_games(games: List[Dict]) -> str:
        """Formata agenda de jogos do dia para WhatsApp."""
        if not games:
            return (
                "\U0001f4c5 *AGENDA DO DIA - CPES*\n"
                "\n"
                "Nenhum jogo programado para hoje nas ligas monitoradas."
            )

        msg = (
            f"\U0001f4c5 *AGENDA DO DIA - CPES*\n"
            f"\n"
            f"\u26bd *{len(games)} jogos programados:*\n"
            f"\n"
        )

        # Agrupar por liga
        by_liga: Dict[str, list] = {}
        for g in games:
            liga = g.get("liga", "?")
            by_liga.setdefault(liga, []).append(g)

        for liga, liga_games in sorted(by_liga.items()):
            msg += f"\U0001f3c6 *{liga}*\n"
            for g in sorted(liga_games, key=lambda x: x.get("timestamp", 0)):
                hora = g.get("hora_inicio", "?")
                home = g.get("home", "?")
                away = g.get("away", "?")
                msg += f"  \u23f0 {hora} - {home} vs {away}\n"
            msg += "\n"

        msg += "\U0001f50d Sistema monitorando automaticamente."
        return msg

    @staticmethod
    def format_pre_game_alert(games: List[Dict]) -> str:
        """Formata alerta de jogos prestes a comecar."""
        msg = (
            f"\U0001f6a8 *JOGOS COME\u00c7ANDO EM BREVE!*\n"
            f"\n"
        )
        for g in games:
            hora = g.get("hora_inicio", "?")
            home = g.get("home", "?")
            away = g.get("away", "?")
            liga = g.get("liga", "?")
            mins = g.get("minutos_ate", 0)
            msg += f"\u26bd {hora} - {home} vs {away}\n"
            msg += f"   {liga} | Em {mins} min\n"
        msg += f"\n\U0001f50d Sistema entrando em modo de analise."
        return msg

    @staticmethod
    def format_health_response(status: Dict) -> str:
        """Formata resposta de saude do sistema para comando admin."""
        online = "\U0001f7e2 Online" if status.get("online") else "\U0001f534 Offline"
        return (
            f"\U0001f916 *STATUS DO SISTEMA*\n"
            f"\n"
            f"{online}\n"
            f"\U0001f4e1 API Football: {status.get('api_usado', '?')}/{status.get('api_limite', '?')}\n"
            f"\u26bd Jogos ao vivo: {status.get('jogos_ao_vivo', 0)}\n"
            f"\U0001f50d Na janela: {status.get('jogos_na_janela', 0)}\n"
            f"\U0001f4ca Ciclo: #{status.get('ciclo', '?')}\n"
            f"\u23f0 Ultimo update: {status.get('ultimo_update', '?')}"
        )

    @staticmethod
    def format_upcoming_response(games: List[Dict]) -> str:
        """Formata resposta de proximos jogos para comando admin."""
        if not games:
            return "\u26bd *PR\u00d3XIMOS JOGOS*\n\nNenhum jogo programado."

        msg = f"\u26bd *PR\u00d3XIMOS JOGOS ({len(games)})*\n\n"
        for g in games:
            hora = g.get("hora_inicio", "?")
            home = g.get("home", "?")
            away = g.get("away", "?")
            liga = g.get("liga", "?")
            mins = g.get("minutos_ate", 0)
            status = g.get("status", "NS")
            if status != "NS" and mins == 0:
                msg += f"\U0001f534 {hora} - {home} vs {away} ({liga}) - *EM ANDAMENTO*\n"
            else:
                msg += f"\u23f0 {hora} - {home} vs {away} ({liga}) - em {mins}min\n"
        return msg

    @staticmethod
    def format_stats_response(stats: Dict) -> str:
        """Formata resposta de stats para comando admin."""
        return (
            f"\U0001f4ca *PERFORMANCE CPES*\n"
            f"\n"
            f"Total sinais: {stats.get('total', 0)}\n"
            f"\u2705 Greens: {stats.get('greens', 0)}\n"
            f"\u274c Reds: {stats.get('reds', 0)}\n"
            f"\U0001f4ca Winrate: {stats.get('winrate', 0):.1f}%\n"
            f"\U0001f4b0 ROI: {stats.get('roi_total', 0):+.2f}u\n"
            f"\u23f3 Pendentes: {stats.get('pendentes', 0)}"
        )

    @staticmethod
    def format_help_response() -> str:
        """Formata lista de comandos disponiveis."""
        return (
            "\U0001f916 *COMANDOS CPES*\n"
            "\n"
            "/status - Sa\u00fade do sistema\n"
            "/jogos - Pr\u00f3ximos jogos do dia\n"
            "/stats - Performance (greens, reds, ROI)\n"
            "/help - Esta mensagem\n"
            "\n"
            "_Aceita com ou sem / (ex: status ou /status)_"
        )

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
