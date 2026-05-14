-- Fase D §5.2 — histórico granular de odds capturadas (Betano + API-Football).
-- Idempotente: IF NOT EXISTS em tabela e índices.

BEGIN;

CREATE TABLE IF NOT EXISTS odds_history (
  id                BIGSERIAL PRIMARY KEY,
  fixture_id        INT NOT NULL,
  source            TEXT NOT NULL,         -- 'betano' | 'apifootball'
  market_kind       TEXT NOT NULL,         -- 'corners' | 'cards'
  market_code       TEXT,                  -- 'CNOU', 'TCOU', etc
  linha             NUMERIC(5,2),
  odd_over          NUMERIC(6,2),
  odd_under         NUMERIC(6,2),
  minute            INT,
  score_home        INT,
  score_away        INT,
  pressure_score    NUMERIC(5,2),          -- CPES próprio (main.py)
  tension_score     NUMERIC(5,2),
  provider_pressure NUMERIC(5,2),          -- Opta/Betano momentum
  captured_at       TIMESTAMPTZ DEFAULT NOW(),
  raw               JSONB
);

CREATE INDEX IF NOT EXISTS ix_oh_fixture_market_time
  ON odds_history(fixture_id, market_kind, captured_at DESC);

CREATE INDEX IF NOT EXISTS ix_oh_captured_at
  ON odds_history(captured_at);

COMMIT;
