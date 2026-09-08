-- ============================================================================
-- query0b_router_check.sql (NEW, diagnostic) — run SECOND
-- In dex.* tables `taker` can be a router/aggregator CONTRACT rather than the end user.
-- If such addresses are material, "unique victim" counts understate victims and every
-- per-address statistic (attacks per address, the inverted-U) is inflated — and inflated
-- DIFFERENTIALLY BY TRADE SIZE, since aggregator usage correlates with size.
-- Ranking by trade count ALONE cannot see the routers that matter most here: a
-- low-frequency, high-value router sitting in the Institutional tier never reaches a
-- global top-25-by-count list. Hence three ranking bases below.
-- Verify the surfaced addresses manually (Etherscan: contract vs EOA) before quoting
-- ANY per-address statistic from query5c.
-- ============================================================================
WITH by_taker AS (
    SELECT
        taker,
        COUNT(*)                AS victim_trades,
        SUM(amount_usd)         AS total_volume_usd,
        AVG(amount_usd)         AS avg_trade_usd,
        MAX(amount_usd)         AS max_trade_usd,
        -- 10000 = the LEGACY Institutional cutoff (fetch/queries/query5b_victim_impact.sql).
        -- Used here only as a fixed size probe, so a router concentrated in large trades
        -- is visible regardless of which tier specification the paper finally adopts.
        COUNT_IF(amount_usd >= 10000) AS trades_ge_10k,
        COUNT(DISTINCT project) AS protocols_touched,  -- routers typically span many venues
        -- A taker with thousands of DISTINCT sending EOAs is a router by construction —
        -- the sharpest available signal. Delete this line if your dex.sandwiched
        -- version does not expose tx_from (it is inherited from the dex.trades schema).
        COUNT(DISTINCT tx_from) AS distinct_senders,
        MIN(block_time)         AS first_seen,
        MAX(block_time)         AS last_seen
    FROM dex.sandwiched
    WHERE block_time >= TIMESTAMP '2024-01-01 00:00:00'  -- 24-month window (paper sample)
      AND block_time <  TIMESTAMP '2026-01-01 00:00:00'  -- exclusive end = 2026-01-01 (731 days)
      AND blockchain = 'ethereum'
      AND amount_usd > 0   -- same restriction as the victim-side analysis queries
    GROUP BY 1
)
-- 25 per basis = manual-review budget; raise if the last row of a basis still looks like a router
SELECT 'by_trade_count' AS rank_basis, t.* FROM (SELECT * FROM by_taker ORDER BY victim_trades DESC LIMIT 25) t
UNION ALL
SELECT 'by_volume',      t.* FROM (SELECT * FROM by_taker ORDER BY total_volume_usd DESC LIMIT 25) t
UNION ALL
SELECT 'by_large_trades', t.* FROM (SELECT * FROM by_taker ORDER BY trades_ge_10k DESC LIMIT 25) t
ORDER BY rank_basis, victim_trades DESC
