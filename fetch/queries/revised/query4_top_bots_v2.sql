-- ============================================================================
-- query4_top_bots_v2.sql — replacement for query4_top_bots.sql
-- (filename kept for lineage; like the original it covers ALL 9,749 bot addresses)
-- Fixes: AT TIME ZONE dropped everywhere (days_active now COUNT(DISTINCT CAST .. AS DATE);
-- first/last_seen lose the cosmetic ' UTC' suffix); priced_trades added so
-- avg_trade_size_usd's base (priced legs only) is explicit.
-- ACCEPTANCE (24-month window): row count and volume totals must match query3_v2 exactly
-- (9,917 rows, $247.52B measured 2026-08); sum(total_sandwich_trades) must equal
-- query1_v2's sum(sandwich_trade_count) and query0a's sandwiches_rows_all = 7,205,506.
-- days_active tops out at 731.
-- ============================================================================
SELECT
    taker                                      AS bot_address,
    COUNT(*)                                   AS total_sandwich_trades,  -- all attacker legs
    COUNT(amount_usd)                          AS priced_trades,          -- base of SUM and AVG below
    SUM(amount_usd)                            AS total_volume_usd,
    COUNT(DISTINCT CAST(block_time AS DATE))   AS days_active,
    MIN(block_time)                            AS first_seen,
    MAX(block_time)                            AS last_seen,
    AVG(amount_usd)                            AS avg_trade_size_usd      -- priced legs only
FROM dex.sandwiches
WHERE block_time >= TIMESTAMP '2024-01-01 00:00:00'  -- window start: 2024-01-01
  AND block_time <  TIMESTAMP '2026-01-01 00:00:00'  -- exclusive end = 2026-01-01 (24 months, 731 days)
  AND blockchain = 'ethereum'
GROUP BY 1
ORDER BY total_volume_usd DESC NULLS LAST, bot_address  -- tiebreaker: byte-stable export
