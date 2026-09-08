-- ============================================================================
-- query5a_break_points_v2.sql — EXACT replacement for query5a_break_points.sql
-- Fixes: D1 exact order statistics instead of APPROX_PERCENTILE (whose p50 sat at the
--        ~50.76th percentile of this very population); D2 adds the unique-address count;
--        D3 drops the AT TIME ZONE wrapper (block_time is already UTC; wrapper defeated
--        partition pruning); renames total_victims -> total_victim_trades.
-- Quantile convention: type-1 (lower)aa empirical quantile — Q(p) = the value at
-- rank ceil(p*n) of the ascending sort = the smallest x with at least p*n observations <= x.
-- Deterministic, tie-safe, and identical to the convention in query5b_victim_impact_v2.sql,
-- query5c_repeat_victimization.sql and query5d_trade_size_distribution.sql.
-- REPRODUCIBILITY: count/min/max/percentile columns are exactly reproducible; mean_value
-- is a DOUBLE SUM/AVG and so is addition-order dependent in a distributed engine —
-- compare it with a relative tolerance (1e-12 is ample), not byte-for-byte.
-- ============================================================================
WITH v AS (
    SELECT amount_usd, taker AS victim_address
    FROM dex.sandwiched
    WHERE block_time >= TIMESTAMP '2024-01-01 00:00:00'  -- window start: 2024-01-01
      AND block_time <  TIMESTAMP '2026-01-01 00:00:00'  -- exclusive end = 2026-01-01 (24 months, 731 days)
      AND blockchain = 'ethereum'
      AND amount_usd > 0   -- drops NULL-priced/zero rows; magnitude: query0a_data_quality
),
r AS (
    SELECT amount_usd, victim_address,
           ROW_NUMBER() OVER (ORDER BY amount_usd) AS rn,   -- global ascending rank
           COUNT(*)     OVER ()                    AS n     -- population size
    FROM v
)
SELECT
    -- MIN over {rows with rn >= ceil(p*n)} returns exactly the order statistic at rank ceil(p*n)
    MIN(CASE WHEN rn >= CAST(CEILING(0.25 * n) AS BIGINT) THEN amount_usd END) AS p25,
    MIN(CASE WHEN rn >= CAST(CEILING(0.50 * n) AS BIGINT) THEN amount_usd END) AS p50_median,
    MIN(CASE WHEN rn >= CAST(CEILING(0.75 * n) AS BIGINT) THEN amount_usd END) AS p75,
    MIN(CASE WHEN rn >= CAST(CEILING(0.90 * n) AS BIGINT) THEN amount_usd END) AS p90,
    MIN(CASE WHEN rn >= CAST(CEILING(0.95 * n) AS BIGINT) THEN amount_usd END) AS p95,
    MIN(amount_usd)                 AS min_value,
    MAX(amount_usd)                 AS max_value,
    AVG(amount_usd)                 AS mean_value,
    COUNT(*)                        AS total_victim_trades,     -- honest name: trades, not victims
    COUNT(DISTINCT victim_address)  AS unique_victim_addresses  -- the number the paper currently lacks
FROM r
