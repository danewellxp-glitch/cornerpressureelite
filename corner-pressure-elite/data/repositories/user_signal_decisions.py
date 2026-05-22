"""Repository de user_signal_decisions (Sprint M + Sprint M.2 multi-leg/bonus).

Cada user PAGO tem 1 decision por signal (UNIQUE user_id, signal_id):
- pending  -> default ao nascer o signal
- entered  -> user apostou. Pode ser:
              * single (1 leg, mercado bate com sinal CPES) -> settle automatico
              * multi (N legs, varios mercados) -> exige confirmacao manual
- skipped  -> user pulou explicitamente

Stats per-user (winrate/ROI) vem so dos decisions WHERE decision='entered'
AND resultado IS NOT NULL.

Sprint M.2 (2026-05-19): adicionado multi-leg via tabela user_decision_legs,
bonus_pct (turbinada), requires_manual_confirmation para multi.
"""
from __future__ import annotations

import logging
from typing import Any, Optional

log = logging.getLogger("cpes.repo.user_signal_decisions")


class UserSignalDecisionsRepo:
    def __init__(self, pool):
        self._pool = pool

    async def get_or_create_pending(self, user_id: int, signal_id: int) -> dict:
        """Garante row pending para o par. Usado quando user abre o sinal."""
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO user_signal_decisions (user_id, signal_id, decision)
                VALUES ($1, $2, 'pending')
                ON CONFLICT (user_id, signal_id) DO UPDATE SET decision = user_signal_decisions.decision
                RETURNING id, decision, odd_entrada, valor_apostado_cents, resultado,
                          payout_cents, bonus_pct, bonus_cents, is_multi,
                          requires_manual_confirmation, decided_at, settled_at
                """,
                user_id, signal_id,
            )
        return self._row_to_dict(row)

    async def decide(
        self,
        user_id: int,
        signal_id: int,
        *,
        decision: str,
        odd_entrada: Optional[float] = None,
        valor_apostado_cents: Optional[int] = None,
        bonus_pct: Optional[float] = None,
        legs: Optional[list[dict]] = None,
    ) -> dict:
        """Marca decision=entered|skipped. UPSERT idempotente.

        Para entered:
        - legs opcional. Se None ou len<=1: single bet (auto-settle pelo CPES).
        - legs com 2+ itens: multi bet (exige manual confirm).
        - odd_entrada e usado direto como odd efetiva (single = leg unico,
          multi = produto das odds das legs ja calculado pelo cliente).
        - bonus_pct opcional (0.0 a 9.999). Aplicado sobre lucro liquido em GREEN.

        Cada leg: {mercado, descricao, linha?, odd_leg}
        Mercados conhecidos pra auto-settle: 'escanteios', 'cartoes'.
        """
        if decision not in {"entered", "skipped"}:
            raise ValueError(f"decision invalida: {decision}")
        if decision == "entered":
            if not odd_entrada or odd_entrada <= 1.0:
                raise ValueError("odd_entrada > 1.0 obrigatorio para 'entered'")
            if not valor_apostado_cents or valor_apostado_cents <= 0:
                raise ValueError("valor_apostado_cents > 0 obrigatorio para 'entered'")
            if bonus_pct is not None and (bonus_pct < 0 or bonus_pct > 5):
                raise ValueError("bonus_pct deve estar entre 0 e 5 (500%)")
            if legs:
                for leg in legs:
                    if not leg.get("mercado") or not leg.get("descricao"):
                        raise ValueError("cada leg precisa de mercado + descricao")
                    if not leg.get("odd_leg") or float(leg["odd_leg"]) <= 1.0:
                        raise ValueError("cada leg precisa de odd_leg > 1.0")

        is_multi = bool(legs and len(legs) > 1)
        requires_manual = is_multi  # multi sempre exige confirm manual

        async with self._pool.acquire() as conn, conn.transaction():
            row = await conn.fetchrow(
                """
                INSERT INTO user_signal_decisions (
                    user_id, signal_id, decision, odd_entrada,
                    valor_apostado_cents, bonus_pct, is_multi,
                    requires_manual_confirmation, decided_at
                )
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, NOW())
                ON CONFLICT (user_id, signal_id) DO UPDATE SET
                    decision = EXCLUDED.decision,
                    odd_entrada = EXCLUDED.odd_entrada,
                    valor_apostado_cents = EXCLUDED.valor_apostado_cents,
                    bonus_pct = EXCLUDED.bonus_pct,
                    is_multi = EXCLUDED.is_multi,
                    requires_manual_confirmation = EXCLUDED.requires_manual_confirmation,
                    decided_at = NOW()
                RETURNING id, decision, odd_entrada, valor_apostado_cents, resultado,
                          payout_cents, bonus_pct, bonus_cents, is_multi,
                          requires_manual_confirmation, decided_at, settled_at
                """,
                user_id, signal_id, decision, odd_entrada, valor_apostado_cents,
                bonus_pct or 0, is_multi, requires_manual,
            )
            decision_id = int(row["id"])

            if decision == "entered" and legs:
                # Replace legs idempotente: deleta antigas + reinsere
                await conn.execute(
                    "DELETE FROM user_decision_legs WHERE decision_id = $1",
                    decision_id,
                )
                for i, leg in enumerate(legs):
                    await conn.execute(
                        """
                        INSERT INTO user_decision_legs (
                            decision_id, ordem, mercado, descricao, linha, odd_leg
                        )
                        VALUES ($1, $2, $3, $4, $5, $6)
                        """,
                        decision_id, i,
                        leg["mercado"], leg["descricao"],
                        leg.get("linha"), float(leg["odd_leg"]),
                    )

        return self._row_to_dict(row)

    async def create_manual_bet(
        self,
        user_id: int,
        *,
        descricao: str,
        odd_entrada: float,
        valor_apostado_cents: int,
        legs: list[dict],
        bonus_pct: Optional[float] = None,
    ) -> dict:
        """Cria aposta MANUAL (sem signal). 0017.

        legs: [{mercado, descricao, jogo_id?, linha?, side?, odd_leg}]. Single = 1
        leg, multi = N legs. `odd_entrada` = odd efetiva (single = odd da leg;
        multi = produto, calculado pelo cliente).

        Auto-settle quando TODAS as legs sao escanteios/cartoes com jogo_id +
        linha + side (rastreaveis). Senao `requires_manual_confirmation=TRUE`.
        """
        if not odd_entrada or odd_entrada <= 1.0:
            raise ValueError("odd_entrada > 1.0 obrigatorio")
        if not valor_apostado_cents or valor_apostado_cents <= 0:
            raise ValueError("valor_apostado_cents > 0 obrigatorio")
        if not legs:
            raise ValueError("pelo menos 1 leg obrigatoria")
        if bonus_pct is not None and (bonus_pct < 0 or bonus_pct > 5):
            raise ValueError("bonus_pct deve estar entre 0 e 5 (500%)")
        for leg in legs:
            if not leg.get("mercado") or not leg.get("descricao"):
                raise ValueError("cada leg precisa de mercado + descricao")
            if not leg.get("odd_leg") or float(leg["odd_leg"]) <= 1.0:
                raise ValueError("cada leg precisa de odd_leg > 1.0")

        is_multi = len(legs) > 1
        _AUTO = {"escanteios", "cartoes"}
        auto_trackable = all(
            leg.get("mercado") in _AUTO
            and leg.get("jogo_id")
            and leg.get("side") in ("over", "under")
            and leg.get("linha") is not None
            for leg in legs
        )
        requires_manual = not auto_trackable
        primary_jogo = legs[0].get("jogo_id")

        async with self._pool.acquire() as conn, conn.transaction():
            row = await conn.fetchrow(
                """
                INSERT INTO user_signal_decisions (
                    user_id, signal_id, decision, odd_entrada,
                    valor_apostado_cents, bonus_pct, is_multi,
                    requires_manual_confirmation, is_manual, jogo_id,
                    descricao, decided_at
                )
                VALUES ($1, NULL, 'entered', $2, $3, $4, $5, $6, TRUE, $7, $8, NOW())
                RETURNING id
                """,
                user_id, odd_entrada, valor_apostado_cents, bonus_pct or 0,
                is_multi, requires_manual, primary_jogo, descricao,
            )
            decision_id = int(row["id"])
            for i, leg in enumerate(legs):
                await conn.execute(
                    """
                    INSERT INTO user_decision_legs (
                        decision_id, ordem, mercado, descricao, linha,
                        odd_leg, jogo_id, side
                    )
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                    """,
                    decision_id, i, leg["mercado"], leg["descricao"],
                    leg.get("linha"), float(leg["odd_leg"]),
                    leg.get("jogo_id"), leg.get("side"),
                )
        return {
            "id": decision_id,
            "is_multi": is_multi,
            "requires_manual_confirmation": requires_manual,
            "auto_trackable": auto_trackable,
        }

    async def settle_legs_for_game(
        self, jogo_id: int, mercado: str, final_count: int
    ) -> list[int]:
        """Resolve legs (jogo_id+mercado) abertas comparando `final_count` vs
        linha/side. Retorna decision_ids afetados (pra tentar fechar a decision).
        Linhas .5 nao dao PUSH; over: final>linha=GREEN, under: final<linha=GREEN.
        """
        affected: set[int] = set()
        async with self._pool.acquire() as conn:
            legs = await conn.fetch(
                """
                SELECT id, decision_id, linha, side FROM user_decision_legs
                WHERE jogo_id = $1 AND mercado = $2 AND resultado IS NULL
                """,
                jogo_id, mercado,
            )
            for leg in legs:
                if leg["linha"] is None:
                    continue
                linha = float(leg["linha"])
                side = leg["side"] or "over"
                if side == "over":
                    res = "GREEN" if final_count > linha else "RED"
                else:
                    res = "GREEN" if final_count < linha else "RED"
                await conn.execute(
                    "UPDATE user_decision_legs SET resultado = $2 WHERE id = $1",
                    int(leg["id"]), res,
                )
                affected.add(int(leg["decision_id"]))
        return list(affected)

    async def try_settle_decision(self, decision_id: int) -> Optional[dict]:
        """Fecha a decision auto se TODAS as legs resolveram (any RED->RED,
        all GREEN->GREEN). No-op se manual-confirm, ja resolvida, ou legs abertas.
        Retorna o dict resolvido (pra creditar banca) ou None.
        """
        async with self._pool.acquire() as conn:
            d = await conn.fetchrow(
                """
                SELECT id, user_id, odd_entrada, valor_apostado_cents, bonus_pct,
                       resultado, requires_manual_confirmation
                FROM user_signal_decisions WHERE id = $1
                """,
                decision_id,
            )
            if (d is None or d["resultado"] is not None
                    or d["requires_manual_confirmation"]):
                return None
            legs = await conn.fetch(
                "SELECT resultado FROM user_decision_legs WHERE decision_id = $1",
                decision_id,
            )
            if not legs or any(leg["resultado"] is None for leg in legs):
                return None  # ainda tem leg aberta
            results = [leg["resultado"] for leg in legs]
            if "RED" in results:
                final = "RED"
            elif all(r == "GREEN" for r in results):
                final = "GREEN"
            else:
                final = "VOID"  # so PUSH/VOID (raro em .5)
            stake = int(d["valor_apostado_cents"] or 0)
            odd = float(d["odd_entrada"] or 1.0)
            bonus_pct = float(d["bonus_pct"] or 0)
            payout, bonus_cents = self._calc_payout(stake, odd, bonus_pct, final)
            updated = await conn.fetchrow(
                """
                UPDATE user_signal_decisions
                SET resultado = $2, payout_cents = $3, bonus_cents = $4,
                    settled_at = NOW()
                WHERE id = $1
                RETURNING id, user_id, signal_id, resultado, valor_apostado_cents,
                          payout_cents, bonus_cents
                """,
                decision_id, final, payout, bonus_cents,
            )
        return dict(updated)

    async def get_with_legs(self, decision_id: int) -> Optional[dict]:
        """Decision + lista de legs."""
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT id, user_id, signal_id, decision, odd_entrada,
                       valor_apostado_cents, resultado, payout_cents,
                       bonus_pct, bonus_cents, is_multi,
                       requires_manual_confirmation, decided_at, settled_at,
                       manually_confirmed_at
                FROM user_signal_decisions WHERE id = $1
                """,
                decision_id,
            )
            if not row:
                return None
            legs = await conn.fetch(
                """
                SELECT id, ordem, mercado, descricao, linha, odd_leg, resultado
                FROM user_decision_legs WHERE decision_id = $1 ORDER BY ordem
                """,
                decision_id,
            )
        d = self._row_to_dict(row)
        d["legs"] = [
            {
                "id": int(leg["id"]),
                "ordem": int(leg["ordem"]),
                "mercado": leg["mercado"],
                "descricao": leg["descricao"],
                "linha": float(leg["linha"]) if leg["linha"] is not None else None,
                "odd_leg": float(leg["odd_leg"]),
                "resultado": leg["resultado"],
            }
            for leg in legs
        ]
        return d

    async def confirm_manual_result(
        self,
        decision_id: int,
        *,
        resultado: str,
    ) -> dict:
        """User confirma manualmente resultado da multi. Calcula payout + bonus_cents.

        Pode tambem ser usado pra corrigir resultado de single bet (override).
        """
        if resultado not in {"GREEN", "RED", "PUSH", "VOID"}:
            raise ValueError(f"resultado invalido: {resultado}")

        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT odd_entrada, valor_apostado_cents, bonus_pct
                FROM user_signal_decisions WHERE id = $1
                """,
                decision_id,
            )
            if not row:
                raise LookupError(f"decision {decision_id} nao existe")

            stake = int(row["valor_apostado_cents"] or 0)
            odd = float(row["odd_entrada"] or 1.0)
            bonus_pct = float(row["bonus_pct"] or 0)

            payout_cents, bonus_cents = self._calc_payout(stake, odd, bonus_pct, resultado)

            updated = await conn.fetchrow(
                """
                UPDATE user_signal_decisions
                SET resultado = $2,
                    payout_cents = $3,
                    bonus_cents = $4,
                    settled_at = NOW(),
                    manually_confirmed_at = NOW()
                WHERE id = $1
                RETURNING id, decision, odd_entrada, valor_apostado_cents,
                          resultado, payout_cents, bonus_pct, bonus_cents,
                          is_multi, requires_manual_confirmation,
                          decided_at, settled_at
                """,
                decision_id, resultado, payout_cents, bonus_cents,
            )
        return self._row_to_dict(updated)

    async def update_bonus(self, decision_id: int, *, bonus_pct: float) -> dict:
        """PATCH do bonus. Recalcula bonus_cents se ja resolvido."""
        if bonus_pct < 0 or bonus_pct > 5:
            raise ValueError("bonus_pct deve estar entre 0 e 5")

        async with self._pool.acquire() as conn, conn.transaction():
            row = await conn.fetchrow(
                """
                SELECT odd_entrada, valor_apostado_cents, resultado
                FROM user_signal_decisions WHERE id = $1
                """,
                decision_id,
            )
            if not row:
                raise LookupError(f"decision {decision_id} nao existe")

            new_bonus_cents = 0
            if row["resultado"]:
                stake = int(row["valor_apostado_cents"] or 0)
                odd = float(row["odd_entrada"] or 1.0)
                _, new_bonus_cents = self._calc_payout(stake, odd, bonus_pct, row["resultado"])

            updated = await conn.fetchrow(
                """
                UPDATE user_signal_decisions
                SET bonus_pct = $2, bonus_cents = $3
                WHERE id = $1
                RETURNING id, decision, odd_entrada, valor_apostado_cents, resultado,
                          payout_cents, bonus_pct, bonus_cents, is_multi,
                          requires_manual_confirmation, decided_at, settled_at
                """,
                decision_id, bonus_pct, new_bonus_cents,
            )
        return self._row_to_dict(updated)

    async def settle_auto(
        self,
        signal_id: int,
        *,
        resultado: str,
    ) -> list[dict]:
        """Settle automatico de SINGLE BETS deste signal. Multi nao toca.

        Retorna lista de decisions resolvidos (pra main.py creditar banca).
        """
        if resultado not in {"GREEN", "RED", "PUSH", "VOID"}:
            raise ValueError(f"resultado invalido: {resultado}")

        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT id, user_id, odd_entrada, valor_apostado_cents, bonus_pct
                FROM user_signal_decisions
                WHERE signal_id = $1
                  AND decision = 'entered'
                  AND resultado IS NULL
                  AND requires_manual_confirmation = FALSE
                """,
                signal_id,
            )
            if not rows:
                return []

            settled = []
            for r in rows:
                stake = int(r["valor_apostado_cents"] or 0)
                odd = float(r["odd_entrada"] or 1.0)
                bonus_pct = float(r["bonus_pct"] or 0)
                payout_cents, bonus_cents = self._calc_payout(stake, odd, bonus_pct, resultado)

                updated = await conn.fetchrow(
                    """
                    UPDATE user_signal_decisions
                    SET resultado = $2,
                        payout_cents = $3,
                        bonus_cents = $4,
                        settled_at = NOW()
                    WHERE id = $1
                    RETURNING id, user_id, signal_id, decision, odd_entrada,
                              valor_apostado_cents, resultado, payout_cents,
                              bonus_pct, bonus_cents, is_multi,
                              requires_manual_confirmation
                    """,
                    int(r["id"]), resultado, payout_cents, bonus_cents,
                )
                settled.append(dict(updated))
        return settled

    @staticmethod
    def _calc_payout(stake_cents: int, odd: float, bonus_pct: float, resultado: str) -> tuple[int, int]:
        """Calcula payout liquido (P&L) + bonus em centavos.

        Convencoes:
        - payout_cents e o P&L liquido (positivo em GREEN, negativo em RED).
        - bonus_cents e o snapshot do bonus turbinada (sempre >= 0).
        - GREEN: lucro_liq = stake * (odd - 1); bonus = lucro_liq * bonus_pct
        - RED:   payout = -stake; bonus = 0
        - PUSH/VOID: payout = 0; bonus = 0
        """
        if resultado == "GREEN":
            lucro_liq = stake_cents * (odd - 1.0)
            bonus = lucro_liq * bonus_pct
            return int(round(lucro_liq + bonus)), int(round(bonus))
        if resultado == "RED":
            return -stake_cents, 0
        return 0, 0

    async def compute_user_stats(self, user_id: int) -> dict:
        """Stats user-scoped: vem so de decisions entered+resolved."""
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT
                  COUNT(*) FILTER (WHERE decision = 'entered') AS total_entered,
                  COUNT(*) FILTER (WHERE decision = 'entered' AND resultado = 'GREEN') AS greens,
                  COUNT(*) FILTER (WHERE decision = 'entered' AND resultado = 'RED') AS reds,
                  COUNT(*) FILTER (WHERE decision = 'entered' AND resultado IS NULL) AS pendentes,
                  COUNT(*) FILTER (WHERE decision = 'entered' AND resultado IN ('PUSH','VOID')) AS push_void,
                  COALESCE(SUM(valor_apostado_cents) FILTER (WHERE decision = 'entered'), 0) AS staked,
                  COALESCE(SUM(payout_cents) FILTER (WHERE decision = 'entered' AND resultado IS NOT NULL), 0) AS pnl,
                  COALESCE(SUM(bonus_cents) FILTER (WHERE decision = 'entered' AND resultado IS NOT NULL), 0) AS bonus_total,
                  COALESCE(AVG(odd_entrada) FILTER (WHERE decision = 'entered'), 0) AS avg_odd,
                  COUNT(*) FILTER (WHERE decision = 'pending') AS aguardando_decisao,
                  COUNT(*) FILTER (WHERE decision = 'entered' AND requires_manual_confirmation = TRUE AND resultado IS NULL) AS aguardando_confirmacao
                FROM user_signal_decisions
                WHERE user_id = $1
                """,
                user_id,
            )
        if not row:
            return self._empty_stats()
        total = int(row["total_entered"] or 0)
        greens = int(row["greens"] or 0)
        reds = int(row["reds"] or 0)
        decididos = greens + reds
        winrate = (greens / decididos * 100.0) if decididos > 0 else 0.0
        staked = int(row["staked"] or 0)
        pnl = int(row["pnl"] or 0)
        roi = (pnl / staked * 100.0) if staked > 0 else 0.0
        return {
            "total": total,
            "greens": greens,
            "reds": reds,
            "pendentes": int(row["pendentes"] or 0),
            "push_void": int(row["push_void"] or 0),
            "winrate": round(winrate, 1),
            "staked_cents": staked,
            "pnl_cents": pnl,
            "bonus_total_cents": int(row["bonus_total"] or 0),
            "roi_pct": round(roi, 2),
            "roi_total": round(pnl / 100.0, 2),
            "avg_odd": round(float(row["avg_odd"] or 0), 2),
            "aguardando_decisao": int(row["aguardando_decisao"] or 0),
            "aguardando_confirmacao": int(row["aguardando_confirmacao"] or 0),
        }

    async def list_signals_with_decision(
        self,
        user_id: int,
        *,
        limit: int = 100,
    ) -> list[dict]:
        """Sinais recentes JOIN com o decision do user (cria pending se nao houver).

        Inclui legs de cada decision. Inclui signal_resultado (resultado do sinal
        CPES propriamente dito — usado pelo frontend pra propor confirmacao
        manual quando is_multi=true).
        """
        limit = max(1, min(limit, 500))
        async with self._pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO user_signal_decisions (user_id, signal_id, decision)
                SELECT $1, s.id, 'pending'
                FROM sinais s
                WHERE s.reavaliacao = FALSE
                  AND NOT EXISTS (
                    SELECT 1 FROM user_signal_decisions u
                    WHERE u.user_id = $1 AND u.signal_id = s.id
                  )
                ORDER BY s.id DESC
                LIMIT $2
                """,
                user_id, limit,
            )
            rows = await conn.fetch(
                """
                SELECT s.id AS signal_id, s.timestamp, s.jogo_descricao, s.tipo_sinal,
                       s.pressure_score, s.projecao, s.edge, s.linha, s.odd,
                       s.resultado AS signal_resultado, s.escanteios_final,
                       s.tipo_analise, s.matching_tiers, s.minuto, s.placar,
                       u.id AS decision_id, u.decision, u.odd_entrada,
                       u.valor_apostado_cents, u.resultado AS user_resultado,
                       u.payout_cents, u.bonus_pct, u.bonus_cents,
                       u.is_multi, u.requires_manual_confirmation,
                       u.decided_at, u.settled_at, u.manually_confirmed_at
                FROM sinais s
                JOIN user_signal_decisions u ON u.signal_id = s.id AND u.user_id = $1
                WHERE s.reavaliacao = FALSE
                ORDER BY s.timestamp DESC
                LIMIT $2
                """,
                user_id, limit,
            )
            decision_ids = [int(r["decision_id"]) for r in rows]
            legs_by_decision: dict[int, list[dict]] = {}
            if decision_ids:
                leg_rows = await conn.fetch(
                    """
                    SELECT decision_id, id, ordem, mercado, descricao, linha, odd_leg, resultado
                    FROM user_decision_legs
                    WHERE decision_id = ANY($1::bigint[])
                    ORDER BY decision_id, ordem
                    """,
                    decision_ids,
                )
                for lr in leg_rows:
                    legs_by_decision.setdefault(int(lr["decision_id"]), []).append({
                        "id": int(lr["id"]),
                        "ordem": int(lr["ordem"]),
                        "mercado": lr["mercado"],
                        "descricao": lr["descricao"],
                        "linha": float(lr["linha"]) if lr["linha"] is not None else None,
                        "odd_leg": float(lr["odd_leg"]),
                        "resultado": lr["resultado"],
                    })

        return [
            {
                "signal_id": int(r["signal_id"]),
                "timestamp": r["timestamp"].isoformat() if r["timestamp"] else None,
                "jogo_descricao": r["jogo_descricao"],
                "tipo_sinal": r["tipo_sinal"],
                "pressure_score": r["pressure_score"],
                "projecao": float(r["projecao"]) if r["projecao"] is not None else None,
                "edge": float(r["edge"]) if r["edge"] is not None else None,
                "linha": float(r["linha"]) if r["linha"] is not None else None,
                "odd": float(r["odd"]) if r["odd"] is not None else None,
                "signal_resultado": r["signal_resultado"] or "PENDENTE",
                "escanteios_final": r["escanteios_final"],
                "tipo_analise": r["tipo_analise"] or "ESCANTEIOS",
                "matching_tiers": r["matching_tiers"] or [],
                "minuto": r["minuto"],
                "placar": r["placar"],
                "decision": {
                    "id": int(r["decision_id"]),
                    "decision": r["decision"],
                    "odd_entrada": float(r["odd_entrada"]) if r["odd_entrada"] is not None else None,
                    "valor_apostado_cents": int(r["valor_apostado_cents"]) if r["valor_apostado_cents"] is not None else None,
                    "resultado": r["user_resultado"],
                    "payout_cents": int(r["payout_cents"]) if r["payout_cents"] is not None else None,
                    "bonus_pct": float(r["bonus_pct"]) if r["bonus_pct"] is not None else 0.0,
                    "bonus_cents": int(r["bonus_cents"]) if r["bonus_cents"] is not None else 0,
                    "is_multi": bool(r["is_multi"]),
                    "requires_manual_confirmation": bool(r["requires_manual_confirmation"]),
                    "decided_at": r["decided_at"].isoformat() if r["decided_at"] else None,
                    "settled_at": r["settled_at"].isoformat() if r["settled_at"] else None,
                    "manually_confirmed_at": r["manually_confirmed_at"].isoformat() if r["manually_confirmed_at"] else None,
                    "legs": legs_by_decision.get(int(r["decision_id"]), []),
                },
            }
            for r in rows
        ]

    async def list_manual_bets(self, user_id: int, *, limit: int = 100) -> list[dict]:
        """Apostas MANUAIS (is_manual=TRUE) no MESMO shape de list_signals_with_decision,
        pra renderizarem na mesma lista de Minhas Apostas. `signal_id` negativo
        (=-decision_id) como chave unica; flag `is_manual=True` pro frontend.
        """
        limit = max(1, min(limit, 500))
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT id AS decision_id, descricao, jogo_id, decision, odd_entrada,
                       valor_apostado_cents, resultado AS user_resultado, payout_cents,
                       bonus_pct, bonus_cents, is_multi, requires_manual_confirmation,
                       decided_at, settled_at, manually_confirmed_at
                FROM user_signal_decisions
                WHERE user_id = $1 AND is_manual = TRUE
                ORDER BY decided_at DESC NULLS LAST, id DESC
                LIMIT $2
                """,
                user_id, limit,
            )
            decision_ids = [int(r["decision_id"]) for r in rows]
            legs_by_decision: dict[int, list[dict]] = {}
            if decision_ids:
                leg_rows = await conn.fetch(
                    """
                    SELECT decision_id, id, ordem, mercado, descricao, linha, odd_leg, resultado
                    FROM user_decision_legs
                    WHERE decision_id = ANY($1::bigint[])
                    ORDER BY decision_id, ordem
                    """,
                    decision_ids,
                )
                for lr in leg_rows:
                    legs_by_decision.setdefault(int(lr["decision_id"]), []).append({
                        "id": int(lr["id"]),
                        "ordem": int(lr["ordem"]),
                        "mercado": lr["mercado"],
                        "descricao": lr["descricao"],
                        "linha": float(lr["linha"]) if lr["linha"] is not None else None,
                        "odd_leg": float(lr["odd_leg"]),
                        "resultado": lr["resultado"],
                    })

        out = []
        for r in rows:
            legs = legs_by_decision.get(int(r["decision_id"]), [])
            first = legs[0] if legs else {}
            merc = first.get("mercado") or "escanteios"
            out.append({
                "signal_id": -int(r["decision_id"]),  # chave unica (manual nao tem sinal)
                "is_manual": True,
                "timestamp": r["decided_at"].isoformat() if r["decided_at"] else None,
                "jogo_descricao": r["descricao"],
                "tipo_sinal": "MANUAL",
                "pressure_score": None,
                "projecao": None,
                "edge": None,
                "linha": first.get("linha"),
                "odd": float(r["odd_entrada"]) if r["odd_entrada"] is not None else None,
                "signal_resultado": "MANUAL",
                "escanteios_final": None,
                "tipo_analise": "CARTOES" if merc == "cartoes" else "ESCANTEIOS",
                "matching_tiers": [],
                "minuto": None,
                "placar": None,
                "decision": {
                    "id": int(r["decision_id"]),
                    "decision": r["decision"],
                    "odd_entrada": float(r["odd_entrada"]) if r["odd_entrada"] is not None else None,
                    "valor_apostado_cents": int(r["valor_apostado_cents"]) if r["valor_apostado_cents"] is not None else None,
                    "resultado": r["user_resultado"],
                    "payout_cents": int(r["payout_cents"]) if r["payout_cents"] is not None else None,
                    "bonus_pct": float(r["bonus_pct"]) if r["bonus_pct"] is not None else 0.0,
                    "bonus_cents": int(r["bonus_cents"]) if r["bonus_cents"] is not None else 0,
                    "is_multi": bool(r["is_multi"]),
                    "requires_manual_confirmation": bool(r["requires_manual_confirmation"]),
                    "decided_at": r["decided_at"].isoformat() if r["decided_at"] else None,
                    "settled_at": r["settled_at"].isoformat() if r["settled_at"] else None,
                    "manually_confirmed_at": r["manually_confirmed_at"].isoformat() if r["manually_confirmed_at"] else None,
                    "legs": legs,
                },
            })
        return out

    def _row_to_dict(self, row) -> dict:
        return {
            "id": int(row["id"]),
            "decision": row["decision"],
            "odd_entrada": float(row["odd_entrada"]) if row["odd_entrada"] is not None else None,
            "valor_apostado_cents": int(row["valor_apostado_cents"]) if row["valor_apostado_cents"] is not None else None,
            "resultado": row["resultado"],
            "payout_cents": int(row["payout_cents"]) if row["payout_cents"] is not None else None,
            "bonus_pct": float(row["bonus_pct"]) if "bonus_pct" in row.keys() and row["bonus_pct"] is not None else 0.0,
            "bonus_cents": int(row["bonus_cents"]) if "bonus_cents" in row.keys() and row["bonus_cents"] is not None else 0,
            "is_multi": bool(row["is_multi"]) if "is_multi" in row.keys() else False,
            "requires_manual_confirmation": bool(row["requires_manual_confirmation"]) if "requires_manual_confirmation" in row.keys() else False,
            "decided_at": row["decided_at"].isoformat() if row["decided_at"] else None,
            "settled_at": row["settled_at"].isoformat() if row["settled_at"] else None,
        }

    def _empty_stats(self) -> dict:
        return {
            "total": 0, "greens": 0, "reds": 0, "pendentes": 0, "push_void": 0,
            "winrate": 0.0, "staked_cents": 0, "pnl_cents": 0, "bonus_total_cents": 0,
            "roi_pct": 0.0, "roi_total": 0.0, "avg_odd": 0.0,
            "aguardando_decisao": 0, "aguardando_confirmacao": 0,
        }
