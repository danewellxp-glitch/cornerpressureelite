"""Repository de banca (Sprint M, 2026-05-17).

Sistema per-user de bankroll + movements imutaveis. Cada user tem 1 banca
(unique by user_id) e N movements (deposit/withdraw/correction/bet_win/loss).

Series temporal e reconstruida snapshotando saldo_apos_cents por dia.
"""
from __future__ import annotations

import logging
from datetime import date, datetime, timedelta, timezone
from typing import Any, Optional

log = logging.getLogger("cpes.repo.banca")


class BancaRepo:
    def __init__(self, pool):
        self._pool = pool

    async def get_summary(self, user_id: int) -> Optional[dict]:
        """Estado atual da banca + config + stats. None se nao configurada."""
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT banca_inicial_cents, banca_atual_cents, currency,
                       unit_pct, max_loss_per_day_cents, max_bets_per_day,
                       started_at, updated_at
                FROM banca WHERE user_id = $1
                """,
                user_id,
            )
        if not row:
            return None
        inicial = int(row["banca_inicial_cents"])
        atual = int(row["banca_atual_cents"])
        delta = atual - inicial
        delta_pct = (delta / inicial * 100.0) if inicial > 0 else 0.0
        return {
            "configured": True,
            "banca_inicial_cents": inicial,
            "banca_atual_cents": atual,
            "delta_cents": delta,
            "delta_pct": round(delta_pct, 2),
            "currency": row["currency"],
            "unit_pct": float(row["unit_pct"]) if row["unit_pct"] is not None else None,
            "max_loss_per_day_cents": row["max_loss_per_day_cents"],
            "max_bets_per_day": row["max_bets_per_day"],
            "stats": await self._compute_stats(user_id),
        }

    async def _compute_stats(self, user_id: int) -> dict:
        """Stats da banca: vem dos movements + (no futuro) decisions."""
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT
                  COUNT(*) FILTER (WHERE tipo = 'bet_win') AS wins,
                  COUNT(*) FILTER (WHERE tipo = 'bet_loss') AS losses,
                  COALESCE(SUM(valor_cents) FILTER (WHERE tipo IN ('bet_win', 'bet_loss')), 0) AS pnl,
                  COALESCE(SUM(-valor_cents) FILTER (WHERE tipo = 'bet_loss'), 0) AS staked_losses,
                  COALESCE(SUM(valor_cents) FILTER (WHERE tipo = 'bet_win'), 0) AS payout_wins
                FROM banca_movements WHERE user_id = $1
                """,
                user_id,
            )
        wins = int(row["wins"] or 0)
        losses = int(row["losses"] or 0)
        decided = wins + losses
        win_rate = (wins / decided) if decided > 0 else 0.0
        pnl_cents = int(row["pnl"] or 0)
        # staked total = sum of bet_loss valor absoluto + (payout - profit) das wins.
        # Sem `valor_apostado` separado isso fica aproximado. Refinaremos com decisions.
        return {
            "win_rate": round(win_rate, 4),
            "avg_odd": 0.0,  # TODO: vira de user_signal_decisions
            "total_staked_cents": int(row["staked_losses"] or 0),
            "total_payout_cents": int(row["payout_wins"] or 0),
            "pnl_cents": pnl_cents,
            "roi_pct": 0.0,  # TODO: idem
            "max_drawdown_cents": 0,  # TODO: rolar series
        }

    async def setup(
        self,
        user_id: int,
        *,
        initial_cents: int,
        unit_pct: Optional[float] = None,
        max_loss_per_day_cents: Optional[int] = None,
        max_bets_per_day: Optional[int] = None,
    ) -> dict:
        """Cria ou re-configura a banca. Re-setup PRESERVA saldo atual."""
        async with self._pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO banca (
                    user_id, banca_inicial_cents, banca_atual_cents,
                    unit_pct, max_loss_per_day_cents, max_bets_per_day
                )
                VALUES ($1, $2, $2, $3, $4, $5)
                ON CONFLICT (user_id) DO UPDATE SET
                    banca_inicial_cents = EXCLUDED.banca_inicial_cents,
                    unit_pct = EXCLUDED.unit_pct,
                    max_loss_per_day_cents = EXCLUDED.max_loss_per_day_cents,
                    max_bets_per_day = EXCLUDED.max_bets_per_day,
                    updated_at = NOW()
                """,
                user_id, initial_cents, unit_pct, max_loss_per_day_cents, max_bets_per_day,
            )
        return await self.get_summary(user_id)  # type: ignore[return-value]

    async def add_movement(
        self,
        user_id: int,
        *,
        tipo: str,
        valor_cents: int,
        descricao: Optional[str] = None,
        motivo: Optional[str] = None,
        bet_id: Optional[int] = None,
    ) -> dict:
        """Adiciona movement + atualiza banca_atual atomically."""
        if tipo not in {"deposit", "withdraw", "correction", "bet_win", "bet_loss", "bet_void"}:
            raise ValueError(f"tipo invalido: {tipo}")
        # Normaliza sinal por convencao.
        if tipo == "withdraw" and valor_cents > 0:
            valor_cents = -valor_cents
        if tipo == "deposit" and valor_cents < 0:
            valor_cents = -valor_cents
        if tipo == "bet_loss" and valor_cents > 0:
            valor_cents = -valor_cents
        if tipo == "bet_win" and valor_cents < 0:
            valor_cents = -valor_cents

        async with self._pool.acquire() as conn, conn.transaction():
            row = await conn.fetchrow(
                "SELECT banca_atual_cents FROM banca WHERE user_id = $1 FOR UPDATE",
                user_id,
            )
            if not row:
                raise LookupError("banca nao configurada")
            saldo_atual = int(row["banca_atual_cents"])
            saldo_novo = saldo_atual + int(valor_cents)
            if saldo_novo < 0:
                raise ValueError(f"saldo insuficiente (atual={saldo_atual} mov={valor_cents})")

            mov_id = await conn.fetchval(
                """
                INSERT INTO banca_movements (
                    user_id, tipo, valor_cents, bet_id, descricao, motivo, saldo_apos_cents
                )
                VALUES ($1, $2, $3, $4, $5, $6, $7)
                RETURNING id
                """,
                user_id, tipo, valor_cents, bet_id, descricao, motivo, saldo_novo,
            )
            await conn.execute(
                "UPDATE banca SET banca_atual_cents = $2, updated_at = NOW() WHERE user_id = $1",
                user_id, saldo_novo,
            )
        return {"movement_id": int(mov_id), "saldo_apos_cents": saldo_novo}

    async def list_movements(
        self,
        user_id: int,
        *,
        tipo: Optional[str] = None,
        page: int = 1,
        page_size: int = 100,
    ) -> dict:
        offset = max(0, (page - 1) * page_size)
        async with self._pool.acquire() as conn:
            if tipo:
                total = await conn.fetchval(
                    "SELECT COUNT(*) FROM banca_movements WHERE user_id = $1 AND tipo = $2",
                    user_id, tipo,
                )
                rows = await conn.fetch(
                    """
                    SELECT id, tipo, valor_cents, saldo_apos_cents, bet_id,
                           descricao, motivo, created_at
                    FROM banca_movements
                    WHERE user_id = $1 AND tipo = $2
                    ORDER BY created_at DESC
                    LIMIT $3 OFFSET $4
                    """,
                    user_id, tipo, page_size, offset,
                )
            else:
                total = await conn.fetchval(
                    "SELECT COUNT(*) FROM banca_movements WHERE user_id = $1",
                    user_id,
                )
                rows = await conn.fetch(
                    """
                    SELECT id, tipo, valor_cents, saldo_apos_cents, bet_id,
                           descricao, motivo, created_at
                    FROM banca_movements
                    WHERE user_id = $1
                    ORDER BY created_at DESC
                    LIMIT $2 OFFSET $3
                    """,
                    user_id, page_size, offset,
                )
        return {
            "total": int(total or 0),
            "page": page,
            "page_size": page_size,
            "items": [
                {
                    "id": int(r["id"]),
                    "tipo": r["tipo"],
                    "valor_cents": int(r["valor_cents"]),
                    "saldo_apos_cents": int(r["saldo_apos_cents"]),
                    "bet_id": int(r["bet_id"]) if r["bet_id"] is not None else None,
                    "descricao": r["descricao"],
                    "motivo": r["motivo"],
                    "created_at": r["created_at"].isoformat() if r["created_at"] else None,
                }
                for r in rows
            ],
        }

    async def series(self, user_id: int, *, days: int = 30) -> list[dict]:
        """Serie diaria do saldo (1 ponto/dia, ultimo saldo conhecido)."""
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT DATE(created_at AT TIME ZONE 'UTC') AS dia,
                       LAST_VALUE(saldo_apos_cents) OVER (
                           PARTITION BY DATE(created_at AT TIME ZONE 'UTC')
                           ORDER BY created_at
                           ROWS BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING
                       ) AS saldo
                FROM banca_movements
                WHERE user_id = $1 AND created_at >= $2
                """,
                user_id, cutoff,
            )
        # dedup por dia (window LAST_VALUE replica em todas as rows do dia)
        per_day: dict[date, int] = {}
        for r in rows:
            per_day[r["dia"]] = int(r["saldo"])
        return [
            {"dia": d.isoformat(), "saldo_cents": s}
            for d, s in sorted(per_day.items())
        ]

    async def reset(self, user_id: int, motivo: Optional[str] = None) -> dict:
        """Zera saldo p/ banca_inicial_cents e registra movement de reset."""
        async with self._pool.acquire() as conn, conn.transaction():
            row = await conn.fetchrow(
                "SELECT banca_inicial_cents, banca_atual_cents FROM banca WHERE user_id = $1 FOR UPDATE",
                user_id,
            )
            if not row:
                raise LookupError("banca nao configurada")
            inicial = int(row["banca_inicial_cents"])
            atual = int(row["banca_atual_cents"])
            delta = inicial - atual
            if delta != 0:
                await conn.execute(
                    """
                    INSERT INTO banca_movements (
                        user_id, tipo, valor_cents, descricao, motivo, saldo_apos_cents
                    )
                    VALUES ($1, 'reset', $2, $3, $4, $5)
                    """,
                    user_id, delta, "reset banca", motivo, inicial,
                )
            await conn.execute(
                "UPDATE banca SET banca_atual_cents = banca_inicial_cents, updated_at = NOW() WHERE user_id = $1",
                user_id,
            )
        return await self.get_summary(user_id)  # type: ignore[return-value]
