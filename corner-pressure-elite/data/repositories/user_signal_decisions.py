"""Repository de user_signal_decisions (Sprint M, 2026-05-17).

Cada user PAGO tem 1 decision por signal (UNIQUE user_id, signal_id):
- pending  → default ao nascer o signal (nao conta em stats)
- entered  → user apostou nessa odd com tal stake
- skipped  → user pulou explicitamente

Stats per-user (winrate/ROI) vem SO dos decisions WHERE decision='entered'
AND resultado IS NOT NULL (GREEN/RED resolvidos).
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
                RETURNING id, decision, odd_entrada, valor_apostado_cents, resultado, payout_cents, decided_at, settled_at
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
    ) -> dict:
        """Marca decision=entered|skipped. UPSERT idempotente."""
        if decision not in {"entered", "skipped"}:
            raise ValueError(f"decision invalida: {decision}")
        if decision == "entered":
            if not odd_entrada or odd_entrada <= 1.0:
                raise ValueError("odd_entrada > 1.0 obrigatorio para 'entered'")
            if not valor_apostado_cents or valor_apostado_cents <= 0:
                raise ValueError("valor_apostado_cents > 0 obrigatorio para 'entered'")

        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO user_signal_decisions (
                    user_id, signal_id, decision, odd_entrada,
                    valor_apostado_cents, decided_at
                )
                VALUES ($1, $2, $3, $4, $5, NOW())
                ON CONFLICT (user_id, signal_id) DO UPDATE SET
                    decision = EXCLUDED.decision,
                    odd_entrada = EXCLUDED.odd_entrada,
                    valor_apostado_cents = EXCLUDED.valor_apostado_cents,
                    decided_at = NOW()
                RETURNING id, decision, odd_entrada, valor_apostado_cents, resultado, payout_cents, decided_at, settled_at
                """,
                user_id, signal_id, decision, odd_entrada, valor_apostado_cents,
            )
        return self._row_to_dict(row)

    async def settle(
        self,
        signal_id: int,
        *,
        resultado: str,
    ) -> int:
        """Atualiza resultado + payout em TODOS os decisions 'entered' deste signal.

        Chamado quando o signal resolve (GREEN/RED). Calcula payout liquido:
        - GREEN: stake * (odd - 1)
        - RED:   -stake
        - PUSH/VOID: 0
        """
        if resultado not in {"GREEN", "RED", "PUSH", "VOID"}:
            raise ValueError(f"resultado invalido: {resultado}")
        async with self._pool.acquire() as conn:
            if resultado == "GREEN":
                # payout = round(stake * (odd - 1))
                count = await conn.fetchval(
                    """
                    UPDATE user_signal_decisions
                    SET resultado = $2,
                        payout_cents = ROUND(valor_apostado_cents * (odd_entrada - 1)),
                        settled_at = NOW()
                    WHERE signal_id = $1
                      AND decision = 'entered'
                      AND resultado IS NULL
                    RETURNING 1
                    """,
                    signal_id, resultado,
                )
                # fetchval com RETURNING multiline retorna o 1o. Reconto:
                count = await conn.fetchval(
                    "SELECT COUNT(*) FROM user_signal_decisions WHERE signal_id = $1 AND resultado = $2",
                    signal_id, resultado,
                )
            elif resultado == "RED":
                await conn.execute(
                    """
                    UPDATE user_signal_decisions
                    SET resultado = $2,
                        payout_cents = -valor_apostado_cents,
                        settled_at = NOW()
                    WHERE signal_id = $1 AND decision = 'entered' AND resultado IS NULL
                    """,
                    signal_id, resultado,
                )
                count = await conn.fetchval(
                    "SELECT COUNT(*) FROM user_signal_decisions WHERE signal_id = $1 AND resultado = $2",
                    signal_id, resultado,
                )
            else:  # PUSH/VOID
                await conn.execute(
                    """
                    UPDATE user_signal_decisions
                    SET resultado = $2, payout_cents = 0, settled_at = NOW()
                    WHERE signal_id = $1 AND decision = 'entered' AND resultado IS NULL
                    """,
                    signal_id, resultado,
                )
                count = await conn.fetchval(
                    "SELECT COUNT(*) FROM user_signal_decisions WHERE signal_id = $1 AND resultado = $2",
                    signal_id, resultado,
                )
        return int(count or 0)

    async def compute_user_stats(self, user_id: int) -> dict:
        """Stats user-scoped: vem SO de decisions entered+resolved."""
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
                  COALESCE(AVG(odd_entrada) FILTER (WHERE decision = 'entered'), 0) AS avg_odd,
                  COUNT(*) FILTER (WHERE decision = 'pending') AS aguardando_decisao
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
            "roi_pct": round(roi, 2),
            "roi_total": round(pnl / 100.0, 2),  # em reais p/ retro-compat com payload SSE
            "avg_odd": round(float(row["avg_odd"] or 0), 2),
            "aguardando_decisao": int(row["aguardando_decisao"] or 0),
        }

    async def list_signals_with_decision(
        self,
        user_id: int,
        *,
        limit: int = 100,
    ) -> list[dict]:
        """Sinais recentes JOIN com o decision do user (cria pending se nao houver)."""
        limit = max(1, min(limit, 500))
        async with self._pool.acquire() as conn:
            # Garante row pending pra signals sem decision deste user.
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
                       u.payout_cents, u.decided_at
                FROM sinais s
                JOIN user_signal_decisions u ON u.signal_id = s.id AND u.user_id = $1
                WHERE s.reavaliacao = FALSE
                ORDER BY s.timestamp DESC
                LIMIT $2
                """,
                user_id, limit,
            )
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
                    "decision": r["decision"],
                    "odd_entrada": float(r["odd_entrada"]) if r["odd_entrada"] is not None else None,
                    "valor_apostado_cents": int(r["valor_apostado_cents"]) if r["valor_apostado_cents"] is not None else None,
                    "resultado": r["user_resultado"],
                    "payout_cents": int(r["payout_cents"]) if r["payout_cents"] is not None else None,
                    "decided_at": r["decided_at"].isoformat() if r["decided_at"] else None,
                },
            }
            for r in rows
        ]

    def _row_to_dict(self, row) -> dict:
        return {
            "id": int(row["id"]),
            "decision": row["decision"],
            "odd_entrada": float(row["odd_entrada"]) if row["odd_entrada"] is not None else None,
            "valor_apostado_cents": int(row["valor_apostado_cents"]) if row["valor_apostado_cents"] is not None else None,
            "resultado": row["resultado"],
            "payout_cents": int(row["payout_cents"]) if row["payout_cents"] is not None else None,
            "decided_at": row["decided_at"].isoformat() if row["decided_at"] else None,
            "settled_at": row["settled_at"].isoformat() if row["settled_at"] else None,
        }

    def _empty_stats(self) -> dict:
        return {
            "total": 0, "greens": 0, "reds": 0, "pendentes": 0, "push_void": 0,
            "winrate": 0.0, "staked_cents": 0, "pnl_cents": 0, "roi_pct": 0.0,
            "roi_total": 0.0, "avg_odd": 0.0, "aguardando_decisao": 0,
        }
