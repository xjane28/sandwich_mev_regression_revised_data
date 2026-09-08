-- ============================================================================
-- PROVENANCE RECORD — do not edit the SQL below; corrections: revised/query3_full_bot_distribution_v2.sql
-- Produced : fetch/query3_full_bot_distribution.csv (Dune export, run 2026-01-19)
-- Base     : dex.sandwiches = BOT-side attacker trade legs; one row per bot address
-- Verified : 9,749 rows; matches query4 totals per address to float-summation noise
-- KNOWN DEFECTS (annotated, not repaired here):
--  D1: `AT TIME ZONE 'GMT'` — same issue as query1 D1.
--  D2: Bots with only NULL-priced trades get SUM(amount_usd) = NULL (117 of 9,749 addresses;
--      the pipeline's B_meas = 9,632). Not wrong, but implicit; v2 makes the bases explicit.
--  D3: ORDER BY ... DESC without NULLS LAST leaves NULL placement engine-defined.
-- ============================================================================
SELECT
    taker as bot_address,
    SUM(amount_usd) as total_volume_usd
FROM dex.sandwiches
WHERE block_time AT TIME ZONE 'GMT' >= TIMESTAMP '2024-01-01 00:00:00'
  AND block_time AT TIME ZONE 'GMT' < TIMESTAMP '2026-01-01 00:00:00'
  AND blockchain = 'ethereum'
GROUP BY 1
ORDER BY total_volume_usd DESC
