-- Conta `is_dangerous_attack=TRUE` nos 60 segundos anteriores a cada
-- incidente do tipo X.
--
-- Substituir `:event_type_corner` por o event_type real de "corner" (a
-- mapear conforme inspeção pós-deploy, ver §11 do harness Fase D — alvo
-- futuro `data/static/opta_event_types.json`).
WITH targets AS (
    SELECT
        opta_match_id,
        team_id,
        minute,
        seconds,
        (minute * 60 + seconds) AS t_sec
    FROM incidents_history
    WHERE event_type = :event_type_corner
)
SELECT
    t.opta_match_id,
    t.team_id,
    t.minute,
    (
        SELECT COUNT(*)
          FROM incidents_history i
         WHERE i.opta_match_id = t.opta_match_id
           AND i.team_id       = t.team_id
           AND i.is_dangerous_attack
           AND (i.minute * 60 + i.seconds) BETWEEN t.t_sec - 60 AND t.t_sec
    ) AS dangerous_attacks_60s_before
FROM targets t
ORDER BY t.opta_match_id, t.minute;
