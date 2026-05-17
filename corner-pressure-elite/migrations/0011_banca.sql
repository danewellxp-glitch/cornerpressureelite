-- 2026-05-17 — Sistema de Banca per-user (Sprint M)
--
-- Cada usuário paga tem uma "banca" (bankroll inicial + atual + moeda) e um
-- log imutável de movimentos (deposit/withdraw/correction) que mantém o
-- saldo_apos_cents para reconstrução histórica em séries temporais.
--
-- Frontend chama 5 endpoints: GET /banca, /banca/series, /banca/movements,
-- POST /banca/setup, /banca/movements, /banca/reset. Ate aqui retornava 404
-- (endpoints + tabelas não existiam).
--
-- Decisão: 1:1 user→banca (PK = user_id). Reset apaga movements e recria
-- saldo inicial; histórico fica em banca_resets (audit trail) — não nesta
-- migration, será adicionado se necessário (YAGNI por enquanto).
--
-- Idempotente.

BEGIN;

CREATE TABLE IF NOT EXISTS banca (
    user_id INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    banca_inicial_cents BIGINT NOT NULL CHECK (banca_inicial_cents >= 0),
    banca_atual_cents BIGINT NOT NULL CHECK (banca_atual_cents >= 0),
    currency VARCHAR(3) NOT NULL DEFAULT 'BRL',
    unit_pct NUMERIC(5,2),                     -- % da banca por aposta (ex: 2.00 = 2%)
    max_loss_per_day_cents BIGINT,              -- stop-loss diario (opcional)
    max_bets_per_day INTEGER,                   -- limite numerico diario (opcional)
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS banca_movements (
    id BIGSERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    tipo TEXT NOT NULL CHECK (tipo IN ('deposit', 'withdraw', 'correction', 'bet_win', 'bet_loss', 'bet_void', 'reset')),
    valor_cents BIGINT NOT NULL,        -- positivo (deposit/win) ou negativo (withdraw/loss)
    bet_id BIGINT,                       -- FK opcional p/ user_signal_decisions.id (0012)
    descricao TEXT,
    motivo TEXT,
    saldo_apos_cents BIGINT NOT NULL CHECK (saldo_apos_cents >= 0),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_banca_mov_user_date ON banca_movements(user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_banca_mov_user_tipo ON banca_movements(user_id, tipo);
CREATE INDEX IF NOT EXISTS idx_banca_mov_bet ON banca_movements(bet_id) WHERE bet_id IS NOT NULL;

COMMIT;
