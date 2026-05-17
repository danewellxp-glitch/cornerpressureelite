-- Fase F (Caminho A soft) — histórico granular de eventos individuais por
-- fixture (gols, cartões, escanteios, substituições, etc) capturados via
-- bridge Betano (`event.incidents[]`) com fallback API-Football.
--
-- Escopo "dataset puro" (PASSO 0 confirmou zero consumidores externos):
-- worker persiste em paralelo, decision_engine NÃO consome. Alimenta
-- Quant H1-H4 (modelo de pricing/projeção sobre timeline real).
--
-- Idempotente: CREATE IF NOT EXISTS em tabela + índices. Zero impacto em
-- tabelas existentes.

BEGIN;

CREATE TABLE IF NOT EXISTS events_history (
  id              BIGSERIAL PRIMARY KEY,
  fixture_id      BIGINT NOT NULL,
  source          TEXT NOT NULL,           -- 'bridge_betano' | 'apifootball'

  event_type      TEXT NOT NULL,           -- 'CRNR'|'YELL'|'GOAL'|'OFFS'|'SUBS'|
                                           -- 'RCRD'|'PEND'|'PBEG'|'EBEG'|'PENL'|
                                           -- 'StoppageTime'|'Aggregated'|...
  event_minute    INTEGER NOT NULL,        -- minuto do incidente (0..120+)
  event_second    INTEGER,                 -- segundo opcional (Betano clock granular)

  team_side       TEXT,                    -- 'home'|'away'|NULL (eventos sem lado)
  player_name     TEXT,                    -- opcional (nem todo provider expõe)

  props           JSONB,                   -- campos específicos (scoreHome/Away,
                                           -- description, overtimeMinute, etc)
  raw             JSONB,                   -- incident original (preservado p/ debug)

  captured_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),

  CONSTRAINT events_history_team_side_check
    CHECK (team_side IN ('home', 'away') OR team_side IS NULL),

  -- Dedup: mesmo incidente capturado em polls subsequentes não duplica.
  -- (fixture, source, type, minute, side, player) é chave natural de incidente.
  -- player_name e team_side podem ser NULL — UNIQUE em Postgres trata NULL
  -- como "valor distinto", então 2 eventos sem player+side viriam dup. Para
  -- evitar isso, usamos COALESCE via expression index (mais robusto que UNIQUE
  -- direto em colunas nullable).
  CONSTRAINT events_history_dedup_uq
    UNIQUE (fixture_id, source, event_type, event_minute, team_side, player_name)
);

CREATE INDEX IF NOT EXISTS idx_eh_fixture_captured
  ON events_history(fixture_id, captured_at DESC);

CREATE INDEX IF NOT EXISTS idx_eh_type_minute
  ON events_history(event_type, event_minute);

CREATE INDEX IF NOT EXISTS idx_eh_source
  ON events_history(source);

COMMIT;
