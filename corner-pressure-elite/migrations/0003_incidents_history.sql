-- Fase D §5.3 — histórico granular de eventos Opta (X/Y, possession, attack).
-- Idempotente: IF NOT EXISTS em tabela e índices; UNIQUE (opta_match_id, event_uid)
-- garante dedupe quando WS reconecta.

BEGIN;

CREATE TABLE IF NOT EXISTS incidents_history (
  id                  BIGSERIAL PRIMARY KEY,
  fixture_id          INT,
  opta_match_id       TEXT NOT NULL,
  event_uid           TEXT NOT NULL,            -- sha1 dos campos discriminantes (24 chars)
  event_type          INT NOT NULL,
  period_id           INT,
  minute              INT,
  seconds             INT,
  team_id             TEXT,
  player_id           TEXT,
  x                   REAL,
  y                   REAL,
  x_end               REAL,
  y_end               REAL,
  is_attack           BOOLEAN,
  is_dangerous_attack BOOLEAN,
  is_possession       BOOLEAN,
  is_dangerous        BOOLEAN,
  captured_at         TIMESTAMPTZ DEFAULT NOW(),
  raw                 JSONB,
  UNIQUE (opta_match_id, event_uid)
);

CREATE INDEX IF NOT EXISTS ix_ih_fixture_minute
  ON incidents_history(fixture_id, minute);

CREATE INDEX IF NOT EXISTS ix_ih_opta_match
  ON incidents_history(opta_match_id);

COMMIT;
