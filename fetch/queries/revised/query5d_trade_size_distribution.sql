-- ============================================================================
-- query5d_trade_size_distribution.sql (NEW) — real per-tier trade-size distribution.
--
-- WHY THIS EXISTS: main.tex fig:trade-size-distribution currently shows violins whose
-- caption claims "kernel density estimate of transaction sizes". They are not. See
-- process_trade_size_distribution.py: it reads ONLY avg/min/max per tier from
-- query5b_victim_impact.csv, back-fits a lognormal (sigma = min(max(0.7,
-- log(max/min)/6), 1.0)), draws np.random.lognormal(size=10000), clips to [min,max]
-- and KDEs those SYNTHETIC draws — with no random seed, so the shape changes every run,
-- and the "non-overlapping distributions" the caption calls evidence are an artifact of
-- the clip to the tier boundaries. No delivered CSV can support that figure.
-- This query exports the actual empirical distribution so the figure can be rebuilt
-- (or the figure must be cut). It answers the todo at main.tex subsec:trader-classification.
--
-- OUTPUT: 100 equal-MASS bins per tier (300 rows). Bin k of a tier holds that tier's
-- trades ranked in the k-th within-tier percentile. This is the exact empirical
-- quantile function, so:
--   * violin / density  : each bin carries 1% of the tier's mass over
--                         [lower_edge_usd, upper_edge_usd] => density = 0.01 / width
--   * box plot          : read bins 25 / 50 / 75 directly
--   * log-scale plots   : bins are already quantile-spaced, so no binning artifacts
-- Cheap: one partitioned sort, 300 output rows. Tiers use the SAME in-query cutoffs as
-- query5b_v2 / query5c, so the three files are mutually consistent by construction.
-- ============================================================================
WITH v AS (
    SELECT amount_usd
    FROM dex.sandwiched
    WHERE block_time >= TIMESTAMP '2024-01-01 00:00:00'  -- window start: 2024-01-01
      AND block_time <  TIMESTAMP '2026-01-01 00:00:00'  -- exclusive end = 2026-01-01 (24 months, 731 days)
      AND blockchain = 'ethereum'
      AND amount_usd > 0   -- same restriction as 5a_v2 / 5b_v2 / 5c
),
r AS (
    SELECT amount_usd,
           ROW_NUMBER() OVER (ORDER BY amount_usd) AS rn,
           COUNT(*)     OVER ()                    AS n
    FROM v
),
breaks AS (
    SELECT
        -- same 0.50/0.90 type-1 quantiles as 5b_v2 / 5c
        MIN(CASE WHEN rn >= CAST(CEILING(0.50 * n) AS BIGINT) THEN amount_usd END) AS q50,
        MIN(CASE WHEN rn >= CAST(CEILING(0.90 * n) AS BIGINT) THEN amount_usd END) AS q90
    FROM r
),
classified AS (
    SELECT v.amount_usd, b.q50, b.q90,
           CASE WHEN v.amount_usd < b.q50 THEN 'Retail'
                WHEN v.amount_usd < b.q90 THEN 'Small'
                ELSE 'Institutional' END AS victim_tier
    FROM v CROSS JOIN breaks b   -- single row; evaluated once
),
binned AS (
    SELECT victim_tier, amount_usd, q50, q90,
           -- 100 = number of equal-mass bins per tier (percentile granularity).
           -- ceil(rank * 100 / n_tier) puts each trade in its within-tier percentile.
           CAST(CEILING(
                 ROW_NUMBER() OVER (PARTITION BY victim_tier ORDER BY amount_usd)
                 * 100.0
                 / COUNT(*)  OVER (PARTITION BY victim_tier)
           ) AS INTEGER) AS pctile_in_tier
    FROM classified
)
SELECT
    victim_tier,
    pctile_in_tier,
    COUNT(*)        AS trades_in_bin,
    MIN(amount_usd) AS lower_edge_usd,   -- exact order statistic at the bin's lower rank
    MAX(amount_usd) AS upper_edge_usd,   -- exact order statistic at the bin's upper rank
    AVG(amount_usd) AS mean_usd,
    SUM(amount_usd) AS volume_usd,
    MIN(q50)        AS cutoff_p50,       -- constant per row; must match 5b_v2 / 5c
    MIN(q90)        AS cutoff_p90
    -- ACCEPTANCE: SUM(trades_in_bin) over all 300 rows must equal 5b_v2's total
    -- victim_trades; per tier it must equal that tier's victim_trades.
FROM binned
GROUP BY 1, 2
ORDER BY CASE victim_tier WHEN 'Retail' THEN 1 WHEN 'Small' THEN 2 ELSE 3 END, pctile_in_tier
