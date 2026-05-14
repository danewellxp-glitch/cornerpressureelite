-- Quantos fixtures viraram `betano_event_id` por dia e tempo médio entre
-- kickoff e resolução (útil para entender se a Catalog está pegando jogos
-- antes do apito inicial).
SELECT
    DATE(resolved_at) AS dia,
    COUNT(*)          AS resolvidos,
    ROUND(AVG(EXTRACT(EPOCH FROM (resolved_at - kickoff_utc)) / 60)::numeric, 1) AS avg_resolve_min,
    COUNT(*) FILTER (WHERE resolved_via = 'fuzzy_match')  AS via_fuzzy,
    COUNT(*) FILTER (WHERE resolved_via = 'manual')        AS via_manual,
    COUNT(*) FILTER (WHERE resolved_via = 'statsplayer')   AS via_statsplayer
FROM betano_fixture_map
WHERE kickoff_utc IS NOT NULL
GROUP BY 1
ORDER BY 1 DESC
LIMIT 30;
