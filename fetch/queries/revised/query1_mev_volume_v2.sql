-- ============================================================================
-- query1_mev_volume_v2.sql — replacement for query1_mev_volume.sql (bot-side daily series)
-- Fixes: AT TIME ZONE dropped (block_time is already UTC; wrapper risked a silent window
-- shift under a non-UTC session and defeated partition pruning); date exported as DATE;
-- priced_trade_count added so the COUNT(*)-vs-SUM base mismatch is visible per day.
-- ACCEPTANCE (24-month window = the paper's sample): 912 -> 731 rows, no missing days.
-- Measured 2026-08: sum(sandwich_trade_count) = 7,205,506 (exact) and
-- sum(total_sandwich_volume_usd) = $247.52B. The originally DELIVERED CSV had 7,205,568
-- and $247.32B -- the difference is Dune spellbook drift, not a defect.
-- DOUBLE summation order is nondeterministic -- never demand cent-exact SUM equality.
-- ============================================================================
SELECT
    CAST(block_time AS DATE)   AS date,
    COUNT(*)                   AS sandwich_trade_count,      -- ALL attacker legs, incl. NULL-priced
    COUNT(amount_usd)          AS priced_trade_count,        -- legs with a USD value; base of the SUM below
    SUM(amount_usd)            AS total_sandwich_volume_usd,
    COUNT(DISTINCT taker)      AS unique_sandwich_bots,
    COUNT(DISTINCT tx_hash)    AS unique_transactions
FROM dex.sandwiches
WHERE block_time >= TIMESTAMP '2024-01-01 00:00:00'  -- window start: 2024-01-01
  AND block_time <  TIMESTAMP '2026-01-01 00:00:00'  -- exclusive end = 2026-01-01 (24 months, 731 days)
  AND blockchain = 'ethereum'
GROUP BY CAST(block_time AS DATE)   -- explicit, not positional: edit-safe
ORDER BY 1
