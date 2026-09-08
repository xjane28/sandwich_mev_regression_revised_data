-- ============================================================================
-- query0a_data_quality.sql (NEW, diagnostic) — run FIRST
-- Quantifies everything the analysis queries silently exclude or conflate, on BOTH
-- measurement bases. Long format: (metric, value). Consumers MUST key on `metric`,
-- never on row position.
-- Window: 2024-01-01 to 2025-12-31 inclusive = the paper's 731-day sample
--         (defined in main.tex subsec:ledger-reconstruction, currently Sec. 3).
-- TYPE NOTE: metrics are DECIMAL(38,6), not DOUBLE. Casting counts to DOUBLE made Dune
--      render them in scientific notation (3.756141e+06) — exact at 7 significant
--      figures only by luck; an 8-digit count would have silently lost precision.
-- NOTE on "priced": on the VICTIM side the analysis population is `amount_usd > 0`,
--      on the BOT side query1/3/4 apply no USD filter at all and "priced" means
--      `amount_usd IS NOT NULL`. Metric names below spell out which is meant.
-- ============================================================================
WITH vic AS (
    SELECT amount_usd, taker
    FROM dex.sandwiched
    WHERE block_time >= TIMESTAMP '2024-01-01 00:00:00'  -- window start: 2024-01-01
      AND block_time <  TIMESTAMP '2026-01-01 00:00:00'  -- exclusive end = 2026-01-01 (24 months, 731 days)
      AND blockchain = 'ethereum'
),
bot AS (
    SELECT amount_usd, taker
    FROM dex.sandwiches
    WHERE block_time >= TIMESTAMP '2024-01-01 00:00:00'  -- same 24-month window as vic above
      AND block_time <  TIMESTAMP '2026-01-01 00:00:00'
      AND blockchain = 'ethereum'
)
SELECT * FROM (
    SELECT 'sandwiched_rows_all' AS metric, CAST(COUNT(*) AS DECIMAL(38,6)) AS value FROM vic
    -- read-off anchor: should equal 3,753,918 (the delivered victim-side population)
    UNION ALL SELECT 'sandwiched_rows_gt0_usd',      CAST(COUNT(*) AS DECIMAL(38,6)) FROM vic WHERE amount_usd > 0
    UNION ALL SELECT 'sandwiched_rows_null_usd',     CAST(COUNT(*) AS DECIMAL(38,6)) FROM vic WHERE amount_usd IS NULL
    UNION ALL SELECT 'sandwiched_rows_zero_usd',     CAST(COUNT(*) AS DECIMAL(38,6)) FROM vic WHERE amount_usd = 0
    -- NULL takers would be pooled into one pseudo-address by every GROUP BY taker
    -- (query5c drops them; this sizes the drop)
    UNION ALL SELECT 'sandwiched_rows_null_taker',   CAST(COUNT(*) AS DECIMAL(38,6)) FROM vic WHERE taker IS NULL
    -- dust screen at $1: arbitrary DIAGNOSTIC threshold, used ONLY to size the price-feed
    -- artifact problem (delivered Retail min_tx = 1.239e-23); not a filter in any analysis query
    UNION ALL SELECT 'sandwiched_rows_dust_lt_1usd', CAST(COUNT(*) AS DECIMAL(38,6)) FROM vic WHERE amount_usd > 0 AND amount_usd < 1
    UNION ALL SELECT 'sandwiched_dust_volume_usd',   CAST(COALESCE(SUM(amount_usd),0) AS DECIMAL(38,6)) FROM vic WHERE amount_usd > 0 AND amount_usd < 1
    -- THE number the paper currently lacks: one global U, resolving the delivered
    -- ambiguity between 413,129 (summed by tier) and 364,713 (summed by protocol)
    UNION ALL SELECT 'sandwiched_unique_takers_gt0_usd', CAST(COUNT(DISTINCT taker) AS DECIMAL(38,6)) FROM vic WHERE amount_usd > 0
    UNION ALL SELECT 'sandwiched_unique_takers_all',     CAST(COUNT(DISTINCT taker) AS DECIMAL(38,6)) FROM vic
    -- bot side: sizes the COUNT(*)-vs-SUM base mismatch in query1_v2/query3_v2/query4_v2
    UNION ALL SELECT 'sandwiches_rows_all',          CAST(COUNT(*) AS DECIMAL(38,6)) FROM bot
    UNION ALL SELECT 'sandwiches_rows_null_usd',     CAST(COUNT(*) AS DECIMAL(38,6)) FROM bot WHERE amount_usd IS NULL
    UNION ALL SELECT 'sandwiches_rows_zero_usd',     CAST(COUNT(*) AS DECIMAL(38,6)) FROM bot WHERE amount_usd = 0
    UNION ALL SELECT 'sandwiches_rows_dust_lt_1usd', CAST(COUNT(*) AS DECIMAL(38,6)) FROM bot WHERE amount_usd > 0 AND amount_usd < 1
    UNION ALL SELECT 'sandwiches_unique_takers',     CAST(COUNT(DISTINCT taker) AS DECIMAL(38,6)) FROM bot
) ORDER BY metric
