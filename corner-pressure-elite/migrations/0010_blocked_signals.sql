-- Fase K — P5 (2026-05-17): telemetria de sinais bloqueados pelo refetch
-- just-before-send.
--
-- Quando o refetch detecta mudança brusca entre captura e momento de envio
-- (linha sumiu, odd drift >15%, refetch stale, etc.), o sinal é ABORTADO
-- mas registramos aqui pra análise:
--   - Quantos sinais bloqueados por dia?
--   - Qual razão mais comum?
--   - Estimativa esperada: 5-15% dos sinais (final de jogo + odds voando)
--
-- Idempotente.

BEGIN;

CREATE TABLE IF NOT EXISTS blocked_signals (
    id BIGSERIAL PRIMARY KEY,
    fixture_id INTEGER NOT NULL,
    market_kind TEXT NOT NULL,  -- 'corners' | 'cards'
    linha NUMERIC(5,2),
    reason TEXT NOT NULL,
    -- 'refetch_none' | 'refetch_stale' | 'line_changed'
    -- | 'odd_drift' | 'refetch_exception'
    orig_odd NUMERIC(6,3),
    fresh_odd NUMERIC(6,3),
    drift_pct NUMERIC(5,2),
    metadata JSONB,
    blocked_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_bs_fixture ON blocked_signals(fixture_id);
CREATE INDEX IF NOT EXISTS idx_bs_reason ON blocked_signals(reason, blocked_at);

COMMIT;
