import logging
from typing import Optional, Dict, List, Any
from datetime import datetime
from collections import defaultdict

from data.models import JogoAoVivo, Sinal
from engine.score_engine import PressureScoreEngine
from engine.projection_engine import ProjectionEngine
from config import (
    JANELA_ANTECIPADA_INICIO,
    MAX_DIFERENCA_GOLS,
    MAX_DIFERENCA_GOLS_1T,
    MIN_ESCANTEIOS_TOTAL,
    MIN_ESCANTEIOS_5MIN,
    MIN_ESCANTEIOS_JOGO_MORNO,
    ESCANTEIOS_EARLY_WINDOW,
    MIN_SCORE_NORMAL,
    MIN_SCORE_PREMIUM,
    MIN_EDGE_NORMAL,
    MIN_EDGE_PREMIUM,
)

logger = logging.getLogger("CPES.DecisionEngine")


class DecisionEngine:
    """Motor de decisao - Avalia se deve emitir sinal."""

    def __init__(self):
        self.score_engine = PressureScoreEngine()
        self.projection_engine = ProjectionEngine()
        # Contadores de auditoria por ciclo
        self._ciclo_stats: Dict[str, int] = defaultdict(int)
        self._ciclo_filtros: Dict[str, int] = defaultdict(int)
        self._ciclo_jogos: List[Dict[str, Any]] = []

    def reset_ciclo_stats(self):
        """Reseta contadores ao início de cada ciclo."""
        self._ciclo_stats = defaultdict(int)
        self._ciclo_filtros = defaultdict(int)
        self._ciclo_jogos = []

    def get_ciclo_report(self) -> str:
        """Gera relatório resumido do ciclo de análise."""
        s = self._ciclo_stats
        f = self._ciclo_filtros
        total = s.get("total", 0)
        if total == 0:
            return ""

        lines = [
            f"[AUDIT] === RELATÓRIO DO CICLO ===",
            f"[AUDIT] Total analisados: {total}",
            f"[AUDIT] Passaram filtros:  {s.get('passou_filtros', 0)}",
            f"[AUDIT] Score suficiente:  {s.get('score_ok', 0)}",
            f"[AUDIT] Edge suficiente:   {s.get('edge_ok', 0)}",
            f"[AUDIT] SINAIS emitidos:   {s.get('sinais', 0)} ({s.get('premium', 0)}P + {s.get('normal', 0)}N)",
            f"[AUDIT] --- Motivos de exclusão ---",
        ]
        for motivo, count in sorted(f.items(), key=lambda x: -x[1]):
            lines.append(f"[AUDIT]   {motivo}: {count}")
        lines.append(f"[AUDIT] === FIM DO RELATÓRIO ===")
        return "\n".join(lines)

    def get_audit_data(self) -> Dict[str, Any]:
        """Retorna dados completos de auditoria do ciclo para o dashboard."""
        s = self._ciclo_stats
        total = s.get("total", 0)
        passou = s.get("passou_filtros", 0)
        score_ok = s.get("score_ok", 0)
        edge_ok = s.get("edge_ok", 0)
        sinais = s.get("sinais", 0)

        return {
            "funil": {
                "total_analisados": total,
                "passou_filtros": passou,
                "score_ok": score_ok,
                "edge_ok": edge_ok,
                "sinais_emitidos": sinais,
                "premium": s.get("premium", 0),
                "normal": s.get("normal", 0),
            },
            "filtros_breakdown": dict(sorted(
                self._ciclo_filtros.items(), key=lambda x: -x[1]
            )),
            "jogos": self._ciclo_jogos,
            "taxas": {
                "elegibilidade": round(passou / total * 100, 1) if total > 0 else 0,
                "conversao_score": round(score_ok / passou * 100, 1) if passou > 0 else 0,
                "conversao_edge": round(edge_ok / score_ok * 100, 1) if score_ok > 0 else 0,
                "hit_rate": round(sinais / total * 100, 1) if total > 0 else 0,
            },
        }

    def pre_avaliar(self, jogo: JogoAoVivo) -> Optional[int]:
        """Pre-avaliacao leve: filtros + score apenas. Sem auditoria.
        Retorna pressure score se o jogo passa, None se bloqueado.
        Usar para decidir se vale buscar odds (requisicao cara)."""
        motivo = self._verificar_filtros(jogo)
        if motivo:
            return None
        score = self.score_engine.calcular(jogo, log=False)
        if score < MIN_SCORE_NORMAL:
            return None
        return score

    def avaliar(self, jogo: JogoAoVivo) -> Optional[Sinal]:
        self._ciclo_stats["total"] += 1
        corner_rate = jogo.escanteios_total / max(1, jogo.minuto)

        # Base audit detail for this game
        game_audit = {
            "descricao": jogo.descricao,
            "liga": jogo.liga_nome,
            "minuto": jogo.minuto,
            "placar": jogo.placar,
            "escanteios_total": jogo.escanteios_total,
            "escanteios_casa": jogo.escanteios_casa,
            "escanteios_fora": jogo.escanteios_fora,
            "corner_rate": round(corner_rate, 3),
            "est_5min": jogo.escanteios_ultimos_5min,
            "est_10min": jogo.escanteios_ultimos_10min,
            "ataques": jogo.ataques_perigosos_ultimos_10min,
            "posse": jogo.posse_ultimos_10min,
            "finalizacoes": jogo.finalizacoes_recentes,
            "linha": jogo.linha_atual,
            "odd": jogo.odd_atual,
            "pressure_score": None,
            "projecao": None,
            "edge": None,
            "status": "BLOQUEADO",
            "motivo": None,
        }

        # Log detalhado de cada jogo analisado
        logger.info(
            f"[ANALISE] {jogo.liga_nome} | {jogo.descricao} | "
            f"Min {jogo.minuto} | Placar {jogo.placar} | "
            f"Escanteios: {jogo.escanteios_total} (H:{jogo.escanteios_casa} A:{jogo.escanteios_fora}) | "
            f"Rate: {corner_rate:.3f}/min | "
            f"Est5min: {jogo.escanteios_ultimos_5min} Est10min: {jogo.escanteios_ultimos_10min} | "
            f"Ataques: {jogo.ataques_perigosos_ultimos_10min} Posse: {jogo.posse_ultimos_10min}% "
            f"Finalizacoes: {jogo.finalizacoes_recentes} | "
            f"Linha: {jogo.linha_atual} Odd: {jogo.odd_atual}"
        )

        # 1. Filtros estruturais
        motivo_bloqueio = self._verificar_filtros(jogo)
        if motivo_bloqueio:
            self._ciclo_filtros[motivo_bloqueio.split("(")[0].strip()] += 1
            logger.info(f"[ANALISE] ✗ BLOQUEADO: {jogo.descricao} | {motivo_bloqueio}")
            game_audit["motivo"] = motivo_bloqueio
            self._ciclo_jogos.append(game_audit)
            return None

        self._ciclo_stats["passou_filtros"] += 1

        # 2. Pressure Score
        score = self.score_engine.calcular(jogo)
        game_audit["pressure_score"] = score

        if score < MIN_SCORE_NORMAL:
            self._ciclo_filtros["Score insuficiente"] += 1
            logger.info(
                f"[ANALISE] ✗ Score insuficiente: {jogo.descricao} | "
                f"Score={score} < {MIN_SCORE_NORMAL}"
            )
            game_audit["status"] = "SCORE_INSUFICIENTE"
            game_audit["motivo"] = f"Score {score} < {MIN_SCORE_NORMAL}"
            self._ciclo_jogos.append(game_audit)
            return None

        self._ciclo_stats["score_ok"] += 1

        # 3. Verificar se temos dados de odds (sem linha = sem edge confiavel)
        if jogo.linha_atual <= 0:
            self._ciclo_filtros["Sem odds/linha disponivel"] += 1
            logger.info(
                f"[ANALISE] ✗ Sem linha de mercado: {jogo.descricao} | "
                f"linha={jogo.linha_atual} (odds nao disponiveis)"
            )
            game_audit["status"] = "SEM_ODDS"
            game_audit["motivo"] = "Linha de mercado indisponivel"
            self._ciclo_jogos.append(game_audit)
            return None

        # 4. Projecao hibrida
        projecao = self.projection_engine.calcular_projecao(jogo, score)
        game_audit["projecao"] = round(projecao, 2)

        # 5. Edge
        edge = round(projecao - jogo.linha_atual, 2)
        game_audit["edge"] = edge

        # 6. Decisao
        if score >= MIN_SCORE_PREMIUM and edge >= MIN_EDGE_PREMIUM:
            self._ciclo_stats["sinais"] += 1
            self._ciclo_stats["premium"] += 1
            self._ciclo_stats["edge_ok"] += 1
            sinal = Sinal(
                tipo="PREMIUM",
                jogo=jogo,
                pressure_score=score,
                projecao=projecao,
                edge=edge,
                timestamp=datetime.now(),
            )
            logger.info(
                f"[ANALISE] ★ SINAL PREMIUM: {jogo.descricao} | "
                f"Score={score} Edge={edge:+.2f} Proj={projecao:.1f} Linha={jogo.linha_atual}"
            )
            game_audit["status"] = "SINAL_PREMIUM"
            self._ciclo_jogos.append(game_audit)
            return sinal

        elif score >= MIN_SCORE_NORMAL and edge >= MIN_EDGE_NORMAL:
            self._ciclo_stats["sinais"] += 1
            self._ciclo_stats["normal"] += 1
            self._ciclo_stats["edge_ok"] += 1
            sinal = Sinal(
                tipo="NORMAL",
                jogo=jogo,
                pressure_score=score,
                projecao=projecao,
                edge=edge,
                timestamp=datetime.now(),
            )
            logger.info(
                f"[ANALISE] ● SINAL NORMAL: {jogo.descricao} | "
                f"Score={score} Edge={edge:+.2f} Proj={projecao:.1f} Linha={jogo.linha_atual}"
            )
            game_audit["status"] = "SINAL_NORMAL"
            self._ciclo_jogos.append(game_audit)
            return sinal

        self._ciclo_filtros["Edge insuficiente"] += 1
        logger.info(
            f"[ANALISE] ✗ Edge insuficiente: {jogo.descricao} | "
            f"Score={score} Edge={edge:+.2f} (min={MIN_EDGE_NORMAL}) "
            f"Proj={projecao:.1f} Linha={jogo.linha_atual}"
        )
        game_audit["status"] = "EDGE_INSUFICIENTE"
        game_audit["motivo"] = f"Edge {edge:+.2f} < {MIN_EDGE_NORMAL}"
        self._ciclo_jogos.append(game_audit)
        return None

    @staticmethod
    def _verificar_filtros(jogo: JogoAoVivo) -> Optional[str]:
        """Retorna motivo do bloqueio ou None se passou."""

        # Janela de monitoramento: min 50+ OU early window (7+ escanteios em qualquer minuto)
        early_window = jogo.escanteios_total >= ESCANTEIOS_EARLY_WINDOW
        if jogo.minuto < JANELA_ANTECIPADA_INICIO and not early_window:
            return f"Fora da janela (min {jogo.minuto} < {JANELA_ANTECIPADA_INICIO})"

        # Goleada: 3+ gols de diferenca no 1T -> jogo morto
        if jogo.minuto <= 45 and jogo.diferenca_gols >= MAX_DIFERENCA_GOLS_1T:
            return f"Goleada no 1T ({jogo.diferenca_gols} gols >= {MAX_DIFERENCA_GOLS_1T})"

        # Diferenca de gols muito alta (4+) em qualquer momento
        if jogo.diferenca_gols > MAX_DIFERENCA_GOLS:
            return f"Diferenca de gols alta ({jogo.diferenca_gols} > {MAX_DIFERENCA_GOLS})"

        # Minimo de escanteios
        if jogo.escanteios_total < MIN_ESCANTEIOS_TOTAL:
            return f"Poucos escanteios ({jogo.escanteios_total} < {MIN_ESCANTEIOS_TOTAL})"

        # Escanteio recente (estimado via corner rate)
        if jogo.escanteios_ultimos_5min < MIN_ESCANTEIOS_5MIN:
            return f"Sem escanteio recente (est_5min={jogo.escanteios_ultimos_5min} < {MIN_ESCANTEIOS_5MIN})"

        # Jogo morno (0x0 depois do min 60)
        if (
            jogo.placar_casa == 0
            and jogo.placar_fora == 0
            and jogo.minuto >= 60
            and jogo.escanteios_total < MIN_ESCANTEIOS_JOGO_MORNO
        ):
            return f"Jogo morno 0x0 min {jogo.minuto} ({jogo.escanteios_total} < {MIN_ESCANTEIOS_JOGO_MORNO})"

        # Bloqueio jogo morto (time sem escanteio apos 1o tempo)
        if jogo.minuto > 45 and (jogo.escanteios_casa == 0 or jogo.escanteios_fora == 0):
            return f"Time sem escanteio (casa={jogo.escanteios_casa}, fora={jogo.escanteios_fora})"

        return None
