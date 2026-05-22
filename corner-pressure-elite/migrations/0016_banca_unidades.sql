-- 0016_banca_unidades.sql
-- 2026-05-19: sistema de unidades na banca.
--
-- User divide banca em N unidades (default 100). 1u = banca_atual / N.
-- Permite raciocinar em "apostar 2u nesse sinal" em vez de pensar em R$.
-- Sinais sugerem unidades baseado no tipo (NORMAL=1u, PREMIUM=2u).
--
-- Difere de unit_pct (que era % por aposta sugerida): aqui e quantidade total
-- de unidades em que a banca esta dividida. unit_pct fica como fallback se
-- total_unidades = NULL (compat).

BEGIN;

ALTER TABLE banca
    ADD COLUMN IF NOT EXISTS total_unidades INTEGER DEFAULT 100
        CHECK (total_unidades IS NULL OR total_unidades > 0);

COMMIT;
