-- ============================================================================
-- PROVENANCE RECORD — do not edit the SQL below; corrections: revised/query1_mev_volume_v2.sql
-- Produced : fetch/query1_mev_volume.csv (Dune export, run 2026-01-19)
-- Base     : dex.sandwiches = BOT-side attacker trade legs (front-run + back-run)
-- Verified : 731 rows, Σ sandwich_trade_count = 7,205,568, Σ volume = $247,322,343,792.92
--            (anchors in src/m0_validate.py, all PASS)
-- KNOWN DEFECTS (annotated, not repaired here):
--  D1: `AT TIME ZONE 'GMT'` mis-fixes a non-problem: block_time is already UTC. It coerces
--      to timestamp-with-tz using the SESSION zone (UTC on Dune, hence a no-op in effect)
--      and wrapping the partition key can defeat partition pruning (slower scans).
--  D2: No amount_usd filter: COUNT(*) includes NULL-priced trades that SUM/AVG silently
--      exclude, so count and volume columns have different bases within each row.
--      Magnitude quantified by revised/query0a_data_quality.sql.
--  D3: `date` exports as 'YYYY-MM-DD 00:00:00.000 UTC' rather than a plain DATE.
-- ============================================================================
SELECT
    DATE_TRUNC('day', block_time) as date,
    COUNT(*) as sandwich_trade_count,
    SUM(amount_usd) as total_sandwich_volume_usd,
    COUNT(DISTINCT taker) as unique_sandwich_bots,
    COUNT(DISTINCT tx_hash) as unique_transactions
FROM dex.sandwiches
WHERE block_time AT TIME ZONE 'GMT' >= TIMESTAMP '2024-01-01 00:00:00'
  AND block_time AT TIME ZONE 'GMT' < TIMESTAMP '2026-01-01 00:00:00'
  AND blockchain = 'ethereum'
GROUP BY 1
ORDER BY 1
