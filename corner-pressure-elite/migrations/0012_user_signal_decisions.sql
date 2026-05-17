-- 2026-05-17 — Sistema de decisão por sinal (Sprint M)
--
-- Cada signal gerado pelo sistema entra em estado PENDING para cada usuário
-- pago. O usuário decide: ENTERED (apostei nessa odd) ou SKIPPED (deixei
-- passar). Estatísticas/ROI/winrate per-user vêm SÓ dos decisions com
-- entered + signal.resultado conhecido.
--
-- Decisão de produto (2026-05-17): default opt-in. Signal nasce PENDING
-- (não conta), user precisa clicar ENTERED com odd_entrada + valor pra
-- contar. Trigger backend pode auto-marcar SKIPPED se passar X tempo sem
-- decisão (TODO futuro, não nesta migration).
--
-- Idempotente.

BEGIN;

CREATE TABLE IF NOT EXISTS user_signal_decisions (
    id BIGSERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    signal_id INTEGER NOT NULL REFERENCES sinais(id) ON DELETE CASCADE,
    decision TEXT NOT NULL DEFAULT 'pending'
        CHECK (decision IN ('pending', 'entered', 'skipped')),
    odd_entrada NUMERIC(6,3),               -- odd que o user efetivamente pegou
    valor_apostado_cents BIGINT,             -- stake em cents
    resultado TEXT
        CHECK (resultado IS NULL OR resultado IN ('GREEN', 'RED', 'PUSH', 'VOID')),
    payout_cents BIGINT,                     -- resultado liquido (positivo = lucro, negativo = perda do stake)
    decided_at TIMESTAMPTZ,                  -- quando o user decidiu
    settled_at TIMESTAMPTZ,                  -- quando o resultado foi assentado
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (user_id, signal_id)
);

CREATE INDEX IF NOT EXISTS idx_usd_user_decision ON user_signal_decisions(user_id, decision);
CREATE INDEX IF NOT EXISTS idx_usd_user_decided_at ON user_signal_decisions(user_id, decided_at DESC) WHERE decided_at IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_usd_signal ON user_signal_decisions(signal_id);

COMMIT;
