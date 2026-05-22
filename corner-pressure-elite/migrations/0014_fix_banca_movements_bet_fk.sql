-- 0014_fix_banca_movements_bet_fk.sql
-- 2026-05-19: corrige FK errada em banca_movements.bet_id.
--
-- Bug: 0011_banca.sql declarou bet_id BIGINT sem FK, mas uma versao anterior
-- (legado) criou a constraint banca_movements_bet_id_fkey apontando pra
-- bets(id). Em Sprint M (0012), o endpoint /api/signals/{id}/decision passa
-- result["id"] (user_signal_decisions.id) como bet_id, causando FK violation
-- ja que esse id nao existe na tabela bets.
--
-- Fix: drop a FK errada e recria apontando pra user_signal_decisions(id),
-- que e o que o codigo Sprint M usa de fato. ON DELETE SET NULL preserva
-- historico de movimentacoes mesmo se a decision for deletada.

BEGIN;

ALTER TABLE banca_movements
    DROP CONSTRAINT IF EXISTS banca_movements_bet_id_fkey;

-- Limpa bet_ids orfaos (que apontariam pra bets.id que nao existe em
-- user_signal_decisions) antes de adicionar a nova FK.
UPDATE banca_movements
SET bet_id = NULL
WHERE bet_id IS NOT NULL
  AND bet_id NOT IN (SELECT id FROM user_signal_decisions);

ALTER TABLE banca_movements
    ADD CONSTRAINT banca_movements_bet_id_fkey
    FOREIGN KEY (bet_id) REFERENCES user_signal_decisions(id) ON DELETE SET NULL;

COMMIT;
