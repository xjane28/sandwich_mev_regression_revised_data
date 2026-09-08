-- ============================================================================
-- PROVENANCE RECORD — do not edit the SQL below; corrections: revised/query4_top_bots_v2.sql
-- Produced : fetch/query4_top_bots.csv (Dune export, run 2026-01-19, "untruncated" re-export)
-- Base     : dex.sandwiches = BOT-side attacker trade legs
-- Verified : 9,749 rows — the filename is a MISNOMER: this covers ALL bot addresses, not
--            a "top" subset (validation_report.md correction #3a). Name retained for lineage.
-- KNOWN DEFECTS (annotated, not repaired here):
--  D1: `AT TIME ZONE 'GMT'` — as query1 D1; additionally cosmetic here: it is why
--      first_seen/last_seen export with a ' UTC' suffix.
--  D2: AVG(amount_usd) averages priced trades only, while COUNT(*) counts all trades —
--      mixed bases within a row (as query1 D2).
-- ============================================================================
SELECT
    taker as bot_address,
    COUNT(*) as total_sandwich_trades,
    SUM(amount_usd) as total_volume_usd,
    COUNT(DISTINCT DATE_TRUNC('day', block_time AT TIME ZONE 'GMT')) as days_active,
    MIN(block_time AT TIME ZONE 'GMT') as first_seen,
    MAX(block_time AT TIME ZONE 'GMT') as last_seen,
    AVG(amount_usd) as avg_trade_size_usd
FROM dex.sandwiches
WHERE block_time AT TIME ZONE 'GMT' >= TIMESTAMP '2024-01-01 00:00:00'
    AND block_time AT TIME ZONE 'GMT' < TIMESTAMP '2026-01-01 00:00:00'
        AND blockchain = 'ethereum'
GROUP BY 1
ORDER BY total_volume_usd DESC
