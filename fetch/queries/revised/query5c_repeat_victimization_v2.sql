-- ============================================================================
-- query5c_repeat_victimization_v2.sql — ADDRESS-level tiers on the SENDING EOA.
-- Supersedes query5c_repeat_victimization_TAKER_SUPERSEDED.sql.
--
-- WHY THE IDENTITY CHANGED: `taker` in dex.sandwiched is a router CONTRACT for most
-- of the sample. Measured by query0b (2026-08-25): 30 taker addresses each have
-- >=1,000 distinct tx_from senders and together carry 53.9% of all victim trades and
-- 50.6% of victim volume; the largest, 0x3fc91a3a... (Uniswap Universal Router), has
-- 882,844 trades from 186,190 distinct senders — 23.5% of all victim trades collapsed
-- into ONE "victim address". 1inch v4, Paraswap v5 and Uniswap v4 are also present.
-- Any "per unique victim address" statistic built on `taker` measures router
-- throughput. `tx_from` is the externally-owned account that actually sent the
-- transaction, i.e. the trader.
--
-- WHY BOTS ARE EXCLUDED: query0b also found sandwich BOTS appearing as victims — e.g.
-- 0x1f2f10d1... (the #1 bot at $62.06B bot-side volume) shows 15,287 victim trades and
-- $660M victim volume with 1 distinct sender. Bot-on-bot sandwiching is real but it is
-- not household victimization, and because these rows are large they land in the
-- Institutional tier and directly distort the tier comparison.
--
-- The exclusion is a JUDGMENT CALL — report tier results both ways (the flag column
-- below makes that a filter, not a re-run) and state the choice in the paper.
--
-- Tiers: each EOA classified ONCE by the exact type-1 median of its own trade sizes,
-- against the same trade-level Q(0.50)/Q(0.90) cutoffs as query5b_v2, so address
-- counts are DISJOINT and attacks_per_address is a true mean.
-- CAVEAT (unchanged): Q50/Q90 are TRADE-level quantiles, so address tier shares are an
-- empirical outcome, not 50/40/10, and tier labels are not address-population percentiles.
-- ============================================================================
WITH v AS (
    SELECT amount_usd,
           tx_from AS victim_eoa   -- the sending EOA, NOT taker (see header)
    FROM dex.sandwiched
    WHERE block_time >= TIMESTAMP '2024-01-01 00:00:00'  -- window start: 2024-01-01
      AND block_time <  TIMESTAMP '2026-01-01 00:00:00'  -- exclusive end = 2026-01-01 (24 months, 731 days)
      AND blockchain = 'ethereum'
      AND amount_usd > 0   -- same restriction as 5a_v2 / 5b_v2
),
bot_addrs AS (
    -- every address that acted on the ATTACKER side in the same window, by either
    -- identity, so a searcher is caught whether it self-sends or routes
    SELECT taker AS addr FROM dex.sandwiches
    WHERE block_time >= TIMESTAMP '2024-01-01 00:00:00'
      AND block_time <  TIMESTAMP '2026-01-01 00:00:00' AND blockchain = 'ethereum'
    UNION
    SELECT tx_from FROM dex.sandwiches
    WHERE block_time >= TIMESTAMP '2024-01-01 00:00:00'
      AND block_time <  TIMESTAMP '2026-01-01 00:00:00' AND blockchain = 'ethereum'
),
r AS (
    SELECT amount_usd,
           ROW_NUMBER() OVER (ORDER BY amount_usd) AS rn,
           COUNT(*)     OVER ()                    AS n
    FROM v
),
breaks AS (
    -- 0.50 / 0.90: same type-1 quantiles as 5b_v2 / 5d (keeps estimands comparable).
    -- Computed over ALL trades, before any bot exclusion, so cutoffs match exactly.
    SELECT MIN(CASE WHEN rn >= CAST(CEILING(0.50 * n) AS BIGINT) THEN amount_usd END) AS q50,
           MIN(CASE WHEN rn >= CAST(CEILING(0.90 * n) AS BIGINT) THEN amount_usd END) AS q90
    FROM r
),
addr AS (
    SELECT v.victim_eoa,
           COUNT(*)        AS attack_count,
           SUM(v.amount_usd) AS victim_volume_usd,
           element_at(array_sort(array_agg(v.amount_usd)),
                      CAST(CEILING(COUNT(*) * 0.5) AS BIGINT)) AS median_trade_usd,
           -- flag rather than filter: lets the paper report both specifications
           MAX(CASE WHEN b.addr IS NULL THEN 0 ELSE 1 END) AS is_known_bot
    FROM v LEFT JOIN bot_addrs b ON b.addr = v.victim_eoa
    WHERE v.victim_eoa IS NOT NULL
    GROUP BY 1
),
addr_class AS (
    SELECT a.*, bk.q50 AS cutoff_p50, bk.q90 AS cutoff_p90,
           CASE WHEN a.median_trade_usd < bk.q50 THEN 'Retail'
                WHEN a.median_trade_usd < bk.q90 THEN 'Small'
                ELSE 'Institutional' END AS victim_tier
    FROM addr a CROSS JOIN breaks bk   -- single row; evaluated once
)
SELECT
    victim_tier,
    is_known_bot,                                     -- 0 = trader EOA, 1 = searcher-linked
    COUNT(*)                                     AS unique_eoas,        -- DISJOINT within (tier, flag)
    SUM(attack_count)                            AS attack_events,
    CAST(SUM(attack_count) AS DOUBLE) / COUNT(*) AS attacks_per_eoa,    -- corrected inverted-U statistic
    MAX(attack_count)                            AS max_attacks_single_eoa,
    element_at(array_sort(array_agg(attack_count)),
               CAST(CEILING(COUNT(*) * 0.5) AS BIGINT)) AS median_attacks_per_eoa,
    SUM(victim_volume_usd)                       AS tier_volume_usd,
    AVG(median_trade_usd)                        AS avg_median_trade_usd,
    MIN(cutoff_p50)                              AS cutoff_p50,
    MIN(cutoff_p90)                              AS cutoff_p90
    -- ACCEPTANCE: (a) cutoffs must equal 5a_v2 / 5b_v2 / 5d, run back-to-back;
    --   (b) SUM(attack_events) over ALL rows must equal 5b_v2's SUM(victim_trades);
    --   (c) SUM(unique_eoas) is the true victim-EOA count — expect it to EXCEED the
    --       taker-based count from the SAME window, since routers unmask into many
    --       senders (on the 24-month window: 742,330 EOAs vs 330,521 takers, +124.6%).
FROM addr_class
GROUP BY 1, 2
ORDER BY CASE victim_tier WHEN 'Retail' THEN 1 WHEN 'Small' THEN 2 ELSE 3 END, is_known_bot
