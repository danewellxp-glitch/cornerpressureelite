-- 0015_user_signal_decisions_multi_bonus.sql
-- 2026-05-19: estende Sprint M com multi-leg + bonus turbinada.
--
-- User pode compor multi (escanteios + cartoes + gols + 1X2 etc) usando o
-- sinal CPES como UMA das legs. Sistema settle automatico SO em single bets
-- (1 leg, mercado bate com sinal); multi exige confirmacao manual do user
-- ja que CPES nao conhece todos os mercados.
--
-- Bonus turbinada: snapshot em bonus_pct (ex: 0.250 = 25%); aplica sobre
-- lucro liquido em GREEN. bonus_cents e snapshot do bonus calculado no settle.

BEGIN;

ALTER TABLE user_signal_decisions
    ADD COLUMN IF NOT EXISTS bonus_pct DECIMAL(4,3) DEFAULT 0,
    ADD COLUMN IF NOT EXISTS bonus_cents BIGINT DEFAULT 0,
    ADD COLUMN IF NOT EXISTS is_multi BOOLEAN DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS requires_manual_confirmation BOOLEAN DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS manually_confirmed_at TIMESTAMPTZ;

CREATE TABLE IF NOT EXISTS user_decision_legs (
    id BIGSERIAL PRIMARY KEY,
    decision_id BIGINT NOT NULL REFERENCES user_signal_decisions(id) ON DELETE CASCADE,
    ordem INT NOT NULL DEFAULT 0,
    mercado TEXT NOT NULL,
    descricao TEXT NOT NULL,
    linha DECIMAL(5,2),
    odd_leg DECIMAL(8,3) NOT NULL,
    resultado TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    CONSTRAINT user_decision_legs_resultado_check
        CHECK (resultado IS NULL OR resultado IN ('GREEN','RED','PUSH','VOID')),
    CONSTRAINT user_decision_legs_odd_check CHECK (odd_leg > 1.0)
);

CREATE INDEX IF NOT EXISTS idx_user_decision_legs_decision
    ON user_decision_legs(decision_id);

COMMIT;
