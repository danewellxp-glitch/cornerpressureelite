-- Fase H A1.1 (2026-05-17) — Dual-key (sofa_event_id) sem mudança comportamental
--
-- Adiciona coluna `sofa_event_id` em 6 tabelas + nova `af_sofa_fixture_map`.
-- Sistema continua usando `fixture_id` (AF) como source-of-truth interno.
-- A1.2 fará backfill assíncrono via SofaScoreEventResolver.
-- A2 fará cutover (sofa_event_id vira primary).
-- A3 deprecará fixture_id.
--
-- AJUSTES DO PLANO:
-- - `fixture_state` skipped (tabela não existe no schema atual)
-- - Estratégia órfãos: PRESERVAR (sofa_event_id NULL aceito)
-- - `betano_fixture_map` não recebe `sofa_event_id` aqui — usar
--   `af_sofa_fixture_map` separada por separação de concerns
--   (nem todo fixture tem betano_event_id; ligas não-cobertas pela Betano)
--
-- Idempotente. Sem DROP de nada.

BEGIN;

-- ─── 6 tabelas de dados (shadow column) ──────────────────────────

ALTER TABLE odds_history ADD COLUMN IF NOT EXISTS sofa_event_id INTEGER;
CREATE INDEX IF NOT EXISTS idx_odds_sofa ON odds_history(sofa_event_id) WHERE sofa_event_id IS NOT NULL;
COMMENT ON COLUMN odds_history.sofa_event_id IS
    'Dual-key Fase H A1. NULL = orfão (sem mapping SofaScore via event_resolver). '
    'Histórico preservado. Queries que precisam de cobertura completa devem filtrar WHERE sofa_event_id IS NOT NULL.';

ALTER TABLE stats_history ADD COLUMN IF NOT EXISTS sofa_event_id INTEGER;
CREATE INDEX IF NOT EXISTS idx_stats_sofa ON stats_history(sofa_event_id) WHERE sofa_event_id IS NOT NULL;
COMMENT ON COLUMN stats_history.sofa_event_id IS
    'Dual-key Fase H A1. NULL = orfão. Ver odds_history.sofa_event_id.';

ALTER TABLE events_history ADD COLUMN IF NOT EXISTS sofa_event_id INTEGER;
CREATE INDEX IF NOT EXISTS idx_events_sofa ON events_history(sofa_event_id) WHERE sofa_event_id IS NOT NULL;
COMMENT ON COLUMN events_history.sofa_event_id IS
    'Dual-key Fase H A1. NULL = orfão. Ver odds_history.sofa_event_id.';

ALTER TABLE lineups_history ADD COLUMN IF NOT EXISTS sofa_event_id INTEGER;
CREATE INDEX IF NOT EXISTS idx_lineups_sofa ON lineups_history(sofa_event_id) WHERE sofa_event_id IS NOT NULL;
COMMENT ON COLUMN lineups_history.sofa_event_id IS
    'Dual-key Fase H A1. NULL = orfão. Ver odds_history.sofa_event_id.';

ALTER TABLE blocked_signals ADD COLUMN IF NOT EXISTS sofa_event_id INTEGER;
CREATE INDEX IF NOT EXISTS idx_blocked_sofa ON blocked_signals(sofa_event_id) WHERE sofa_event_id IS NOT NULL;
COMMENT ON COLUMN blocked_signals.sofa_event_id IS
    'Dual-key Fase H A1. NULL = orfão. Ver odds_history.sofa_event_id.';

ALTER TABLE sinais ADD COLUMN IF NOT EXISTS sofa_event_id INTEGER;
CREATE INDEX IF NOT EXISTS idx_sinais_sofa ON sinais(sofa_event_id) WHERE sofa_event_id IS NOT NULL;
COMMENT ON COLUMN sinais.sofa_event_id IS
    'Dual-key Fase H A1. NULL = orfão. Ver odds_history.sofa_event_id. '
    'detalhes_jogo herda via FK sinal_id JOIN.';

-- ─── Mapping table AF ↔ Sofa ─────────────────────────────────────

CREATE TABLE IF NOT EXISTS af_sofa_fixture_map (
    fixture_id INTEGER PRIMARY KEY,                     -- AF fixture_id
    sofa_event_id INTEGER NOT NULL,
    confidence NUMERIC(3,2) NOT NULL DEFAULT 1.0 CHECK (confidence BETWEEN 0 AND 1),
    mapped_via TEXT NOT NULL,                            -- 'event_resolver_backfill' | 'event_resolver_live' | 'manual' | 'betano_pivot'
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_validated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_afsofa_sofa ON af_sofa_fixture_map(sofa_event_id);
CREATE INDEX IF NOT EXISTS idx_afsofa_via ON af_sofa_fixture_map(mapped_via);

COMMENT ON TABLE af_sofa_fixture_map IS
    'Fase H A1: mapping 1:1 AF fixture_id <-> SofaScore event_id. '
    'Populado por A1.2 backfill + dual-write em workers (A1.3). '
    'Separado de betano_fixture_map porque nem todo fixture cai na Betano.';

COMMIT;
