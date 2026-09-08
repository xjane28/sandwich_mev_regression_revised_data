-- ============================================================================
-- query3_full_bot_distribution_v2.sql — replacement for query3_full_bot_distribution.sql
-- Fixes: AT TIME ZONE dropped; trade counts added so NULL-volume bots (117 of 9,749:
-- all their trades lack USD prices, SUM = NULL) are explicit rather than implicit;
-- deterministic NULLS LAST.
-- ACCEPTANCE (24-month window): 9,917 rows measured 2026-08 (delivered CSV had 9,749 --
-- bot-level attribution is NOT stable across Dune vintages, so treat a row-count or
-- top-bot mismatch as drift, not a defect). total_trades and total_volume_usd must equal
-- query4_v2's and query1_v2's totals exactly: 7,205,506 legs, $247.52B, 117 all-NULL bots.
-- ============================================================================
SELECT
    taker                AS bot_address,
    COUNT(*)             AS total_trades,        -- all attacker legs
    COUNT(amount_usd)    AS priced_trades,       -- legs with USD value; base of the SUM
    SUM(amount_usd)      AS total_volume_usd     -- NULL iff priced_trades = 0
FROM dex.sandwiches
WHERE block_time >= TIMESTAMP '2024-01-01 00:00:00'  -- window start: 2024-01-01
  AND block_time <  TIMESTAMP '2026-01-01 00:00:00'  -- exclusive end = 2026-01-01 (24 months, 731 days)
  AND blockchain = 'ethereum'
GROUP BY 1
ORDER BY total_volume_usd DESC NULLS LAST, bot_address  -- tiebreaker: byte-stable export
