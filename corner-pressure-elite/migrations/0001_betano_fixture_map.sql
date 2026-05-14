-- Fase D §5.1 — mapping fixture_id (API-Football) ↔ event_id (Betano)
-- Idempotente: IF NOT EXISTS em tabela e índice.

BEGIN;

CREATE TABLE IF NOT EXISTS betano_fixture_map (
  fixture_id        INT PRIMARY KEY,
  betano_event_id   BIGINT UNIQUE NOT NULL,
  sr_match_id       TEXT,
  opta_match_id     TEXT,
  home_team         TEXT,
  away_team         TEXT,
  league_id         INT,
  kickoff_utc       TIMESTAMPTZ,
  resolved_at       TIMESTAMPTZ DEFAULT NOW(),
  resolved_via      TEXT
);

CREATE INDEX IF NOT EXISTS ix_fxm_betano_event
  ON betano_fixture_map(betano_event_id);

COMMIT;
