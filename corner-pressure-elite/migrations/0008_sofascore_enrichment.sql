-- Fase K.1 PARTE B.6 — schema enrichment SofaScore.
--
-- 1. stats_history.enriched_by JSONB — lista de providers que enriqueceram
--    o snapshot (ex: '["sofascore"]'). NULL quando snapshot é puro do primary.
-- 2. lineups_history.missing_players JSONB — lesões/suspensões SofaScore
--    (gap Betano). Lista vazia '[]' quando snapshot é Betano sem enrichment.
--
-- Idempotente (ADD COLUMN IF NOT EXISTS + CREATE INDEX IF NOT EXISTS).

BEGIN;

-- stats_history.enriched_by
ALTER TABLE stats_history
  ADD COLUMN IF NOT EXISTS enriched_by JSONB;

CREATE INDEX IF NOT EXISTS idx_sh_enriched_by
  ON stats_history(fixture_id)
  WHERE enriched_by IS NOT NULL;

-- lineups_history.missing_players
ALTER TABLE lineups_history
  ADD COLUMN IF NOT EXISTS missing_players JSONB DEFAULT '[]'::jsonb;

CREATE INDEX IF NOT EXISTS idx_lh_has_missing
  ON lineups_history(fixture_id)
  WHERE jsonb_array_length(missing_players) > 0;

COMMIT;
