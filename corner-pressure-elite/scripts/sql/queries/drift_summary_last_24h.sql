-- Comparação Betano vs API-Football nas últimas 24h.
-- Útil quando rodando com DRIFT_CHECK_PROVIDERS=true em staging.
SELECT
    market_kind,
    COUNT(*) FILTER (WHERE source = 'betano')      AS n_betano,
    COUNT(*) FILTER (WHERE source = 'apifootball') AS n_af,
    ROUND(AVG(linha)   FILTER (WHERE source = 'betano')::numeric,    2) AS avg_linha_betano,
    ROUND(AVG(linha)   FILTER (WHERE source = 'apifootball')::numeric, 2) AS avg_linha_af,
    ROUND(AVG(odd_over) FILTER (WHERE source = 'betano')::numeric,    3) AS avg_over_betano,
    ROUND(AVG(odd_over) FILTER (WHERE source = 'apifootball')::numeric, 3) AS avg_over_af,
    ROUND(AVG(odd_under) FILTER (WHERE source = 'betano')::numeric,   3) AS avg_under_betano,
    ROUND(AVG(odd_under) FILTER (WHERE source = 'apifootball')::numeric, 3) AS avg_under_af
FROM odds_history
WHERE captured_at >= NOW() - INTERVAL '24 hours'
GROUP BY market_kind
ORDER BY market_kind;
