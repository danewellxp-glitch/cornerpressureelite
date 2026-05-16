-- Fase D.2 §B.1 — mapping team_id (Betano) ↔ team_id (API-Football).
-- Populado pelo BetanoFixtureDiscovery worker (catálogo + matches on-demand).
-- Idempotente: IF NOT EXISTS + DROP/CREATE INDEX guarded.

BEGIN;

CREATE EXTENSION IF NOT EXISTS pg_trgm;

CREATE TABLE IF NOT EXISTS betano_team_map (
  betano_team_id          BIGINT PRIMARY KEY,
  betano_team_name        TEXT NOT NULL,
  api_football_team_id    INTEGER,
  api_football_team_name  TEXT,
  match_method            TEXT,                 -- 'static_catalog' | 'fuzzy' | 'manual'
  match_confidence        NUMERIC(3,2),          -- 0.00 a 1.00
  resolved_at             TIMESTAMPTZ DEFAULT NOW(),
  updated_at              TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_btm_af_id
  ON betano_team_map(api_football_team_id)
  WHERE api_football_team_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS ix_btm_name_trgm
  ON betano_team_map USING gin (betano_team_name gin_trgm_ops);

COMMIT;
