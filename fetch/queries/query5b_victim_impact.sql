-- ============================================================================
-- PROVENANCE RECORD — do not edit the SQL below; corrections: revised/query5b_victim_impact_v2.sql
--                    and revised/query5c_repeat_victimization.sql
-- Produced : fetch/query5b_victim_impact.csv (Dune export, run 2026-01-19)
-- Base     : dex.sandwiched = VICTIM-side sandwiched swap events
-- Verified : reproduces the delivered CSV exactly — all internal identities hold to float
--            precision (avg=SUM/COUNT, pct columns, tier boundaries = observed min/max).
-- NOTE     : this file briefly contained an unrun percent_rank draft (2026-08-25); restored
--            to the original SQL because this filename is the provenance record of the
--            delivered CSV. The corrected specification lives in revised/.
-- MAGIC NUMBERS (the reason this record exists):
--  * 1024.44 = the APPROX_PERCENTILE p50 from query5a (1024.4357425137512), hand-rounded
--    to cents and pasted in. Because the un-rounded APPROX_PERCENTILE value is BELOW 1024.44, trades at the
--    "median" land in Retail.
--  * 10000  = NOT a percentile. An ad hoc round-number Small/Institutional cutoff, kept
--    from a template ("literature-based" per the analysis transcript; no citation exists).
--    The same data's p90 is 8,928.31; the delivered Institutional tier is therefore the
--    top 8.70% of trades, not the top 10% (validation_report.md correction #4).
-- KNOWN DEFECTS (annotated, not repaired here):
--  D1: The magic-number cutoffs above; no percentile is computed in-query, so the tiers
--      cannot be checked against the data that allegedly defines them.
--  D2: COUNT(DISTINCT victim_address) per tier is NOT additive: tiers partition trades,
--      not addresses. Σ unique_victims = 413,129 is a sum of overlapping sets (proof: the
--      same population grouped by protocol yields 364,713). ≥24,208 addresses appear in
--      more than one tier. Attacks-per-victim ratios built on these denominators are
--      biased; corrected estimand in revised/query5c_repeat_victimization.sql.
--  D3: `pct_of_victims` is percent of victim TRADES (validation_report.md correction #3c).
--  D4: `AT TIME ZONE 'GMT'` — as query1 D1.
--  D5: block_time and project are selected in the CTE and never used.
-- ============================================================================
WITH victim_classification AS (
    SELECT 
        amount_usd,
        CASE 
            WHEN amount_usd < 1024.44 THEN 'Retail'
            WHEN amount_usd < 10000 THEN 'Small'
            ELSE 'Institutional'
        END as victim_tier,
        taker as victim_address,
        block_time,
        project
    FROM dex.sandwiched
    WHERE block_time AT TIME ZONE 'GMT' >= TIMESTAMP '2024-01-01 00:00:00'
      AND block_time AT TIME ZONE 'GMT' < TIMESTAMP '2026-01-01 00:00:00'
      AND blockchain = 'ethereum'
      AND amount_usd > 0
),
totals AS (
    SELECT 
        COUNT(*) as total_count,
        SUM(amount_usd) as total_volume
    FROM victim_classification
)

SELECT 
    victim_tier,
    COUNT(*) as victim_count,
    COUNT(DISTINCT victim_address) as unique_victims,
    SUM(amount_usd) as total_volume,
    AVG(amount_usd) as avg_tx_size,
    MIN(amount_usd) as min_tx,
    MAX(amount_usd) as max_tx,
    CAST(COUNT(*) AS DOUBLE) / (SELECT total_count FROM totals) * 100 as pct_of_victims,
    SUM(amount_usd) / (SELECT total_volume FROM totals) * 100 as pct_of_volume
FROM victim_classification
GROUP BY 1
ORDER BY 
    CASE victim_tier
        WHEN 'Retail' THEN 1
        WHEN 'Small' THEN 2
        WHEN 'Institutional' THEN 3
    END
