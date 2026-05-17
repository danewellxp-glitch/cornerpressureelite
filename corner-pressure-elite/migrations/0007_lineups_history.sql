-- Fase G.1 (Caminho A soft) — histórico granular de lineups por fixture/team
-- (formation, starting XI, bench, squad) capturadas via bridge Betano
-- (`event.roster` no /event/<id>/state, mesmo payload da E.1) com fallback
-- API-Football.
--
-- Escopo "dataset puro" (CASO α confirmado em G.0): worker persiste em
-- paralelo, decision_engine NÃO consome. Alimenta Quant H2-H4 (modelo
-- pricing/projeção sobre formation + qualidade XI titular + profundidade bench).
--
-- Strategy de captura: 1 snapshot por fixture/team_side via UNIQUE constraint
-- (lineup é estável pós-confirmação; worker chama no PRIMEIRO tick com
-- minute < 5 e desiste após gravar).
--
-- Idempotente: CREATE IF NOT EXISTS. Zero impacto em tabelas existentes.

BEGIN;

CREATE TABLE IF NOT EXISTS lineups_history (
  id              BIGSERIAL PRIMARY KEY,
  fixture_id      BIGINT NOT NULL,
  source          TEXT NOT NULL,            -- 'bridge_betano' | 'apifootball'
  team_side       TEXT NOT NULL,            -- 'home' | 'away'

  formation       TEXT,                     -- "4-3-3", "5-4-1" (None se cobertura zero)
  coach_name      TEXT,                     -- gap Betano (sempre NULL pra bridge_betano)

  -- list[{player_id, name, position, position_display, shirt_number, is_substitute}]
  starting_eleven JSONB,
  substitutes     JSONB,
  -- Betano lineup[][] (linhas táticas): list[list[player_id]] preserva forma
  tactical_grid   JSONB,

  version         INTEGER,                  -- snapshot version (do payload /event/state)
  captured_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  raw             JSONB,

  CONSTRAINT lineups_history_team_side_check
    CHECK (team_side IN ('home', 'away')),

  -- Dedup: 1 lineup por (fixture, source, team_side). Worker chama no
  -- primeiro tick early-game e UNIQUE bloqueia re-inserts. Cache local do
  -- worker é otimização — UNIQUE é a verdade de longo prazo.
  CONSTRAINT lineups_history_dedup_uq
    UNIQUE (fixture_id, source, team_side)
);

CREATE INDEX IF NOT EXISTS idx_lh_fixture
  ON lineups_history(fixture_id);

CREATE INDEX IF NOT EXISTS idx_lh_source
  ON lineups_history(source);

COMMIT;
