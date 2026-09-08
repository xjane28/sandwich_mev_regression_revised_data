-- ============================================================================
-- query5b_victim_impact_v2.sql — percentile-specification tiers (TRADE level)
-- Fixes vs legacy query5b: cutoffs are DERIVED IN-QUERY from the same population
-- (no hand-copied constants — the root cause of the $10,000-vs-p90 discrepancy);
-- honest column names; AT TIME ZONE dropped.
-- The delivered $1,024.44/$10,000 specification stays reproducible from the legacy
-- file and becomes the paper's ROBUSTNESS variant — no rerun needed for it.
--
-- Tier rule (type-1 / lower empirical quantile, identical convention in 5a_v2 and 5c):
--   Retail        : amount_usd <  Q(0.50)
--   Small         : Q(0.50) <= amount_usd < Q(0.90)
--   Institutional : amount_usd >= Q(0.90)
-- Classification is on VALUE vs the quantile, so ties at a cutoff land deterministically
-- in one tier; shares are 50/40/10 up to the tie mass at the cutoffs. Note the closed
-- LOWER bounds: write tiers as [p50, p90) and [p90, inf) in the paper, not ">P90".
--
-- SINGLE-EVALUATION STRUCTURE: `breaks` is referenced exactly once (the CROSS JOIN),
-- and q50/q90 ride along on every row, so the cutoffs REPORTED below are provably the
-- same values that were APPLIED in the CASE. Trino inlines WITH clauses per reference
-- with no common-subexpression reuse, so extra references would mean extra 3.75M-row
-- sorts AND cutoffs computed by a different evaluation than the one used to classify.
-- Denominators use window-over-aggregate rather than a `totals` CTE for the same reason.
--
-- NOTE: addresses_with_trade_in_tier is intentionally NON-additive (one address can
-- trade in several tiers). The additive, address-level estimand is query5c.
-- ============================================================================
WITH v AS (
    SELECT amount_usd, taker AS victim_address
    FROM dex.sandwiched
    WHERE block_time >= TIMESTAMP '2024-01-01 00:00:00'  -- window start: 2024-01-01
      AND block_time <  TIMESTAMP '2026-01-01 00:00:00'  -- exclusive end = 2026-01-01 (24 months, 731 days)
      AND blockchain = 'ethereum'
      AND amount_usd > 0   -- same restriction as 5a_v2; magnitude: query0a_data_quality
),
r AS (
    SELECT amount_usd,
           ROW_NUMBER() OVER (ORDER BY amount_usd) AS rn,  -- global ascending rank
           COUNT(*)     OVER ()                    AS n    -- population size
    FROM v
),
breaks AS (
    SELECT
        -- 0.50 / 0.90: the tier definition (median; 90th pct), main.tex subsec:trader-classification
        MIN(CASE WHEN rn >= CAST(CEILING(0.50 * n) AS BIGINT) THEN amount_usd END) AS q50,
        MIN(CASE WHEN rn >= CAST(CEILING(0.90 * n) AS BIGINT) THEN amount_usd END) AS q90
    FROM r
),
classified AS (
    SELECT v.amount_usd, v.victim_address, b.q50, b.q90,
           CASE WHEN v.amount_usd < b.q50 THEN 'Retail'
                WHEN v.amount_usd < b.q90 THEN 'Small'
                ELSE 'Institutional' END AS victim_tier
    FROM v CROSS JOIN breaks b   -- breaks is a single row; evaluated once
)
SELECT
    victim_tier,
    COUNT(*)                        AS victim_trades,
    COUNT(DISTINCT victim_address)  AS addresses_with_trade_in_tier,  -- NON-additive; see header
    SUM(amount_usd)                 AS total_volume,
    AVG(amount_usd)                 AS avg_tx_size,
    MIN(amount_usd)                 AS min_tx,
    MAX(amount_usd)                 AS max_tx,
    CAST(COUNT(*) AS DOUBLE) / SUM(COUNT(*)) OVER () * 100          AS pct_of_trades,
    SUM(amount_usd) / SUM(SUM(amount_usd)) OVER () * 100            AS pct_of_volume,
    -- constant per row, so MIN is exact: these are the cutoffs actually applied above
    MIN(q50) AS cutoff_p50,
    MIN(q90) AS cutoff_p90
    -- ACCEPTANCE: cutoff_p50/cutoff_p90 must equal 5a_v2's p50_median/p90 from the SAME
    -- window, when both are
    -- run against the SAME dex.sandwiched version (run them back-to-back). A mismatch
    -- after a spellbook re-deploy is data drift, not a defect in either query.
FROM classified
GROUP BY 1
ORDER BY CASE victim_tier WHEN 'Retail' THEN 1 WHEN 'Small' THEN 2 ELSE 3 END
