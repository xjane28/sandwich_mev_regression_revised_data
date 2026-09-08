-- ============================================================================
-- PROVENANCE RECORD — do not edit the SQL below; corrections: revised/query5a_break_points_v2.sql
-- Produced : fetch/query5a_break_points.csv (Dune export, run 2026-01-19)
-- Base     : dex.sandwiched = VICTIM-side sandwiched swap events
-- Verified : total_victims = 3,753,918 matches query5b Σvictim_count and protocol Σsandwich_count
-- KNOWN DEFECTS (annotated, not repaired here):
--  D1: APPROX_PERCENTILE is t-digest APPROXIMATE. Demonstrably material: the reported
--      p50 (1024.4357...) actually sits at the ~50.76th percentile of the same population
--      (1,905,366/3,753,918 trades fall below the 1024.44 cutoff in query5b — an overshoot
--      of ~28,400 trades that rounding to cents cannot explain). All five percentiles carry
--      15-17 printed significant figures of which few are meaningful. v2 computes EXACT
--      order statistics.
--  D2: `total_victims` is COUNT(*) = victim TRADES, not victim addresses
--      (validation_report.md correction #3b). No unique-address count exists anywhere in
--      the delivered data; v2 adds one.
--  D3: `AT TIME ZONE 'GMT'` — as query1 D1.
--  D4: `amount_usd > 0` silently drops NULL-priced and zero rows; magnitude quantified by
--      revised/query0a_data_quality.sql.
-- ============================================================================
SELECT
    APPROX_PERCENTILE(amount_usd, 0.25) as p25,
    APPROX_PERCENTILE(amount_usd, 0.50) as p50_median,
    APPROX_PERCENTILE(amount_usd, 0.75) as p75,
    APPROX_PERCENTILE(amount_usd, 0.90) as p90,
    APPROX_PERCENTILE(amount_usd, 0.95) as p95,
    MIN(amount_usd) as min_value,
    MAX(amount_usd) as max_value,
    AVG(amount_usd) as mean_value,
    COUNT(*) as total_victims
FROM dex.sandwiched
WHERE block_time AT TIME ZONE 'GMT' >= TIMESTAMP '2024-01-01 00:00:00'
    AND block_time AT TIME ZONE 'GMT' < TIMESTAMP '2026-01-01 00:00:00'
        AND blockchain = 'ethereum'
        AND amount_usd > 0
