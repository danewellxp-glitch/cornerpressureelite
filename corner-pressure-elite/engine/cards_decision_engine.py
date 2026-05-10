import logging
from typing import Optional, Dict, List, Any
from datetime import datetime
from collections import defaultdict

from data.models import JogoAoVivo, SinalCartoes
from engine.cards_score_engine import TensionScoreEngine
from engine.cards_projection_engine import CardsProjectionEngine
from engine.strategy_config import (
    StrategyTier,
    CardStrategy,
    get_card_strategy,
    DEFAULT_CARD_STRATEGY,
    CARD_STRATEGIES,
    compute_matching_tiers,
)
from config import (
    CARTOES_MINUTO_INICIO,
    CARTOES_MAX_DIFERENCA_GOLS,
    CARTOES_MIN_JOGO_MORNO,
)

logger = logging.getLogger("CPES.CardsDecision")


class CardsDecisionEngine:
    """Motor de decisao para cartoes amarelos."""

    def __init__(self, strategy: Optional[StrategyTier] = None):
        self.score_engine = TensionScoreEngine()
        self.projection_engine = CardsProjectionEngine()
        self.strategy: CardStrategy = get_card_strategy(strategy)
        self._ciclo_stats: Dict[str, int] = defaultdict(int)
        self._ciclo_filtros: Dict[str, int] = defaultdict(int)
        self._ciclo_jogos: List[Dict[str, Any]] = []

    def reset_ciclo_stats(self):
        self._ciclo_stats = defaultdict(int)
        self._ciclo_filtros = defaultdict(int)
        self._ciclo_jogos = []

    def get_ciclo_report(self) -> str:
        s = self._ciclo_stats
        f = self._ciclo_filtros
        total = s.get("total", 0)
        if total == 0:
            return ""

        lines = [
            f"[CARDS AUDIT] === RELATORIO DO CICLO ===",
            f"[CARDS AUDIT] Total analisados: {total}",
            f"[CARDS AUDIT] Passaram filtros:  {s.get('passou_filtros', 0)}",
            f"[CARDS AUDIT] Score suficiente:  {s.get('score_ok', 0)}",
            f"[CARDS AUDIT] Edge suficiente:   {s.get('edge_ok', 0)}",
            f"[CARDS AUDIT] SINAIS emitidos:   {s.get('sinais', 0)} ({s.get('premium', 0)}P + {s.get('normal', 0)}N)",
            f"[CARDS AUDIT] --- Motivos de exclusao ---",
        ]
        for motivo, count in sorted(f.items(), key=lambda x: -x[1]):
            lines.append(f"[CARDS AUDIT]   {motivo}: {count}")
        lines.append(f"[CARDS AUDIT] === FIM DO RELATORIO ===")
        return "\n".join(lines)

    def get_audit_data(self) -> Dict[str, Any]:
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
        Retorna tension score se o jogo passa, None se bloqueado.
        Usar para decidir se vale buscar odds de cartoes."""
        motivo = self._verificar_filtros(jogo, self.strategy)
        if motivo:
            return None
        score = self.score_engine.calcular(jogo, log=False)
        if score < self.strategy.min_score:
            return None
        return score

    def avaliar(self, jogo: JogoAoVivo) -> Optional[SinalCartoes]:
        self._ciclo_stats["total"] += 1
        minuto = max(1, jogo.minuto)
        card_rate = jogo.cartoes_amarelos_total / minuto
        foul_rate = jogo.faltas_total / minuto

        game_audit = {
            "descricao": jogo.descricao,
            "liga": jogo.liga_nome,
            "minuto": jogo.minuto,
            "placar": jogo.placar,
            "cartoes_amarelos": jogo.cartoes_amarelos_total,
            "cartoes_vermelhos": jogo.cartoes_vermelhos_total,
            "faltas": jogo.faltas_total,
            "card_rate": round(card_rate, 3),
            "foul_rate": round(foul_rate, 3),
            "est_5min": jogo.cartoes_ultimos_5min,
            "est_10min": jogo.cartoes_ultimos_10min,
            "linha_cartoes": jogo.linha_cartoes,
            "odd_cartoes": jogo.odd_cartoes,
            "tension_score": None,
            "projecao": None,
            "edge": None,
            "status": "BLOQUEADO",
            "motivo": None,
        }

        logger.info(
            f"[CARDS] {jogo.liga_nome} | {jogo.descricao} | "
            f"Min {jogo.minuto} | Placar {jogo.placar} | "
            f"Amarelos: {jogo.cartoes_amarelos_total} (H:{jogo.cartoes_amarelos_casa} A:{jogo.cartoes_amarelos_fora}) | "
            f"Vermelhos: {jogo.cartoes_vermelhos_total} | Faltas: {jogo.faltas_total} | "
            f"CardRate: {card_rate:.3f}/min FoulRate: {foul_rate:.3f}/min | "
            f"Linha: {jogo.linha_cartoes} Odd: {jogo.odd_cartoes}"
        )

        # 1. Filtros estruturais
        motivo_bloqueio = self._verificar_filtros(jogo, self.strategy)
        if motivo_bloqueio:
            self._ciclo_filtros[motivo_bloqueio.split("(")[0].strip()] += 1
            logger.info(f"[CARDS] ✗ BLOQUEADO: {jogo.descricao} | {motivo_bloqueio}")
            game_audit["motivo"] = motivo_bloqueio
            self._ciclo_jogos.append(game_audit)
            return None

        self._ciclo_stats["passou_filtros"] += 1

        # 2. Tension Score
        score = self.score_engine.calcular(jogo)
        game_audit["tension_score"] = score

        if score < self.strategy.min_score:
            self._ciclo_filtros["Score insuficiente"] += 1
            logger.info(
                f"[CARDS] ✗ Score insuficiente: {jogo.descricao} | "
                f"Score={score} < {self.strategy.min_score}"
            )
            game_audit["status"] = "SCORE_INSUFICIENTE"
            game_audit["motivo"] = f"Score {score} < {self.strategy.min_score}"
            self._ciclo_jogos.append(game_audit)
            return None

        self._ciclo_stats["score_ok"] += 1

        # 3. Verificar odds de cartoes
        if jogo.linha_cartoes <= 0:
            self._ciclo_filtros["Sem odds/linha cartoes"] += 1
            logger.info(
                f"[CARDS] ✗ Sem linha de cartoes: {jogo.descricao} | "
                f"linha={jogo.linha_cartoes}"
            )
            game_audit["status"] = "SEM_ODDS"
            game_audit["motivo"] = "Linha de cartoes indisponivel"
            self._ciclo_jogos.append(game_audit)
            return None

        # 4. Projecao de cartoes
        projecao = self.projection_engine.calcular_projecao(jogo, score)
        game_audit["projecao"] = round(projecao, 2)

        # 5. Edge
        edge = round(projecao - jogo.linha_cartoes, 2)
        game_audit["edge"] = edge

        # 6. Decisao
        if score >= self.strategy.premium_score and edge >= self.strategy.premium_edge:
            self._ciclo_stats["sinais"] += 1
            self._ciclo_stats["premium"] += 1
            self._ciclo_stats["edge_ok"] += 1
            matching = compute_matching_tiers(score, edge, CARD_STRATEGIES)
            sinal = SinalCartoes(
                tipo="PREMIUM",
                jogo=jogo,
                tension_score=score,
                projecao_cartoes=projecao,
                edge=edge,
                timestamp=datetime.now(),
                matching_tiers=matching,
            )
            logger.info(
                f"[CARDS] ★ SINAL PREMIUM: {jogo.descricao} | "
                f"TScore={score} Edge={edge:+.2f} Proj={projecao:.1f} Linha={jogo.linha_cartoes}"
            )
            game_audit["status"] = "SINAL_PREMIUM"
            self._ciclo_jogos.append(game_audit)
            return sinal

        elif score >= self.strategy.min_score and edge >= self.strategy.min_edge:
            self._ciclo_stats["sinais"] += 1
            self._ciclo_stats["normal"] += 1
            self._ciclo_stats["edge_ok"] += 1
            matching = compute_matching_tiers(score, edge, CARD_STRATEGIES)
            sinal = SinalCartoes(
                tipo="NORMAL",
                jogo=jogo,
                tension_score=score,
                projecao_cartoes=projecao,
                edge=edge,
                timestamp=datetime.now(),
                matching_tiers=matching,
            )
            logger.info(
                f"[CARDS] ● SINAL NORMAL: {jogo.descricao} | "
                f"TScore={score} Edge={edge:+.2f} Proj={projecao:.1f} Linha={jogo.linha_cartoes}"
            )
            game_audit["status"] = "SINAL_NORMAL"
            self._ciclo_jogos.append(game_audit)
            return sinal

        self._ciclo_filtros["Edge insuficiente"] += 1
        logger.info(
            f"[CARDS] ✗ Edge insuficiente: {jogo.descricao} | "
            f"Score={score} Edge={edge:+.2f} (min={self.strategy.min_edge}) "
            f"Proj={projecao:.1f} Linha={jogo.linha_cartoes}"
        )
        game_audit["status"] = "EDGE_INSUFICIENTE"
        game_audit["motivo"] = f"Edge {edge:+.2f} < {self.strategy.min_edge}"
        self._ciclo_jogos.append(game_audit)
        return None

    @staticmethod
    def _verificar_filtros(jogo: JogoAoVivo, strategy: CardStrategy) -> Optional[str]:
        """Retorna motivo do bloqueio ou None se passou."""

        # Janela: min 40+ OU early window (strategy-dependent)
        early_window = jogo.cartoes_amarelos_total >= strategy.early_window_cartoes
        if jogo.minuto < CARTOES_MINUTO_INICIO and not early_window:
            return f"Fora da janela (min {jogo.minuto} < {CARTOES_MINUTO_INICIO})"

        # Goleada
        if jogo.diferenca_gols > CARTOES_MAX_DIFERENCA_GOLS:
            return f"Diferenca de gols alta ({jogo.diferenca_gols} > {CARTOES_MAX_DIFERENCA_GOLS})"

        # Minimo cartoes (strategy-dependent)
        if jogo.cartoes_amarelos_total < strategy.min_cartoes_total:
            return f"Poucos cartoes ({jogo.cartoes_amarelos_total} < {strategy.min_cartoes_total})"

        # Cartao recente (strategy-dependent)
        if jogo.cartoes_ultimos_5min < strategy.min_cartoes_5min:
            return f"Sem cartao recente (est_5min={jogo.cartoes_ultimos_5min} < {strategy.min_cartoes_5min})"

        # Jogo morno 0x0 apos min 60 com poucos cartoes
        if (
            jogo.placar_casa == 0
            and jogo.placar_fora == 0
            and jogo.minuto >= 60
            and jogo.cartoes_amarelos_total < CARTOES_MIN_JOGO_MORNO
        ):
            return f"Jogo morno 0x0 min {jogo.minuto} ({jogo.cartoes_amarelos_total} < {CARTOES_MIN_JOGO_MORNO})"

        return None
