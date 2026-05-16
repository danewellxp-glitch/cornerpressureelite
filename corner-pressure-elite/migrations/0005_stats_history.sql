-- Fase E.1 §5 — histórico granular de stats capturadas (BridgeStatsAdapter
-- Betano + APIFootballStatsProvider). Espelha odds_history (Fase D).
--
-- Idempotente: CREATE IF NOT EXISTS em tabela + índices. Zero impacto em
-- tabelas existentes — sem ALTER, sem DROP, sem FK criada agora.
--
-- Usado por:
--   - BetanoStatsWorker (PARTE E') — INSERT a cada poll bem-sucedido
--   - StatsWindowCalculator (PARTE E') — SELECT pro cálculo das janelas
--                                        corners_last_5min/_10min etc.

BEGIN;

CREATE TABLE IF NOT EXISTS stats_history (
  id                      BIGSERIAL PRIMARY KEY,
  fixture_id              INT NOT NULL,
  source                  TEXT NOT NULL,         -- 'bridge_betano' | 'apifootball'

  -- Snapshot canônico (espelha CanonicalStats)
  minute                  INT,
  second_since_start      INT,                   -- Betano clock granular; AF deixa NULL
  score_home              INT,
  score_away              INT,
  corners_home            INT,
  corners_away            INT,
  yellow_cards_home       INT,
  yellow_cards_away       INT,
  red_cards_home          INT      DEFAULT 0,
  red_cards_away          INT      DEFAULT 0,
  shots_on_target_home    INT      DEFAULT 0,
  shots_on_target_away    INT      DEFAULT 0,
  dangerous_attacks_home  INT      DEFAULT 0,
  dangerous_attacks_away  INT      DEFAULT 0,
  possession_home         INT      DEFAULT 0,
  possession_away         INT      DEFAULT 0,
  x_goals_home            NUMERIC(5,2) DEFAULT 0.0,
  x_goals_away            NUMERIC(5,2) DEFAULT 0.0,

  -- Fase E.1 — específicos do bridge Betano
  version                 INT,                   -- versão do snapshot /latest
  provider_pressure       NUMERIC(5,2),          -- Opta momentum (Fase A; bridge ainda não)

  -- Janelas — preenchidas se o worker já passou pelo StatsWindowCalculator
  -- antes do INSERT. NULL se snapshot recém-saído do adapter sem cálculo.
  corners_last_5min       INT,
  corners_last_10min      INT,
  yellow_last_5min        INT,
  yellow_last_10min       INT,

  captured_at             TIMESTAMPTZ DEFAULT NOW(),
  raw                     JSONB
);

-- Índice principal: queries do calculator (snapshots recentes por fixture).
CREATE INDEX IF NOT EXISTS ix_sh_fixture_time
  ON stats_history(fixture_id, captured_at DESC);

-- Índice secundário: scans temporais (retention, dashboards).
CREATE INDEX IF NOT EXISTS ix_sh_captured_at
  ON stats_history(captured_at);

-- Defesa contra duplicar quando bridge devolve mesma version em race
-- (paranoia: bridge cache TTL=3s + worker poll adaptive pode chamar 2x
-- antes do version update). Partial: só onde version IS NOT NULL pra
-- AF passar livre.
CREATE UNIQUE INDEX IF NOT EXISTS uq_sh_fixture_source_version
  ON stats_history(fixture_id, source, version)
  WHERE version IS NOT NULL;

COMMIT;
