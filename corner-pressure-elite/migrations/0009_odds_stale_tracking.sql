-- Fase K — P4-B (2026-05-17): cache stale tracking pra odds.
--
-- 1. odds_history.is_stale BOOL — true quando captura veio do cache local
--    com idade > TTL adaptativo do market (bridge falhou, fallback cache).
-- 2. odds_history.source_age_seconds INT — idade da captura original em segundos
--    (0 quando fresh do bridge).
--
-- Sinais com is_stale=true são BLOQUEADOS (não enviados via WhatsApp), mas
-- gravados em odds_history pra telemetria.
--
-- AF removido do path runtime de odds (continua em discovery + cold checks).
-- Sistema fica silente em outage extremo (melhor silêncio que sinal errado).
--
-- Idempotente.

BEGIN;

ALTER TABLE odds_history
  ADD COLUMN IF NOT EXISTS is_stale BOOLEAN NOT NULL DEFAULT false,
  ADD COLUMN IF NOT EXISTS source_age_seconds INTEGER NOT NULL DEFAULT 0;

CREATE INDEX IF NOT EXISTS idx_oh_stale
  ON odds_history(fixture_id, captured_at)
  WHERE is_stale = true;

COMMENT ON COLUMN odds_history.is_stale IS
  'true = cache stale (bridge falhou, idade > TTL); false = captura fresh Betano';
COMMENT ON COLUMN odds_history.source_age_seconds IS
  'Segundos desde captura original (0 = fresh; >0 = cache stale)';

COMMIT;
