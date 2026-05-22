-- 0017 (2026-05-20) — Apostas manuais em "Minhas Apostas" (single/multi).
--
-- Reusa user_signal_decisions (+ user_decision_legs) em vez de tabela nova:
-- toda a infra de banca/legs/bonus/unidades/settle da Sprint M.2 vale igual.
-- Aposta manual = decision SEM signal_id (signal_id agora nullable).
--
-- Modelo UNIFORME por legs (single = 1 leg, multi = N legs). Cada leg aponta
-- pra um jogo ao vivo (jogo_id) + mercado (escanteios|cartoes) + linha + side.
-- Auto-settle: quando o jogo finaliza, resolve cada leg (placar final cru vs
-- linha/side); quando TODAS as legs de uma decision resolvem, fecha a decision
-- (GREEN sse todas GREEN, RED se qualquer RED) + credita banca. Legs de mercado
-- nao-rastreavel (gols/1X2/...) ou jogo nao-monitorado caem em manual confirm.
--
-- Idempotente. Sem DROP de dados de producao (so colunas novas vazias).

BEGIN;

-- signal_id nullable (apostas manuais nao tem sinal). UNIQUE(user_id, signal_id)
-- continua valido: Postgres trata NULLs como distintos.
ALTER TABLE user_signal_decisions ALTER COLUMN signal_id DROP NOT NULL;

ALTER TABLE user_signal_decisions
    ADD COLUMN IF NOT EXISTS is_manual BOOLEAN DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS jogo_id INTEGER,        -- jogo principal (display/filtro)
    ADD COLUMN IF NOT EXISTS descricao TEXT;         -- "Santos vs San Lorenzo" (ou "Multipla 3 jogos")

-- Dados de auto-settle vivem na LEG (uniforme single+multi).
ALTER TABLE user_decision_legs
    ADD COLUMN IF NOT EXISTS jogo_id INTEGER,        -- fixture monitorado da leg
    ADD COLUMN IF NOT EXISTS side TEXT;              -- 'over' | 'under'

ALTER TABLE user_decision_legs DROP CONSTRAINT IF EXISTS udl_side_check;
ALTER TABLE user_decision_legs
    ADD CONSTRAINT udl_side_check CHECK (side IS NULL OR side IN ('over', 'under'));

-- Limpa colunas da 1a versao desta migration (auto-settle migrou pra legs).
ALTER TABLE user_signal_decisions DROP CONSTRAINT IF EXISTS usd_side_check;
ALTER TABLE user_signal_decisions DROP CONSTRAINT IF EXISTS usd_tipo_analise_check;
ALTER TABLE user_signal_decisions DROP COLUMN IF EXISTS tipo_analise;
ALTER TABLE user_signal_decisions DROP COLUMN IF EXISTS linha;
ALTER TABLE user_signal_decisions DROP COLUMN IF EXISTS side;

-- Auto-settle varre legs nao-resolvidas por jogo+mercado.
CREATE INDEX IF NOT EXISTS idx_udl_unsettled
    ON user_decision_legs(jogo_id, mercado)
    WHERE resultado IS NULL AND jogo_id IS NOT NULL;

COMMIT;
