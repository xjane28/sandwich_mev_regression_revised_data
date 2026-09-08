-- ############################################################################
-- SUPERSEDED 2026-08-25 by query5c_repeat_victimization_v2.sql — DO NOT RUN.
-- query0b measured that `taker` is a router CONTRACT for most of the sample:
-- 30 addresses with >=1,000 distinct tx_from senders carry 53.9% of victim trades,
-- the largest (Uniswap Universal Router) collapsing 186,190 distinct senders into a
-- single 'victim address'. Classifying `taker` therefore classifies contracts, and
-- attacks_per_address counts router throughput, not repeat victimization.
-- Kept only to document the estimand that was considered and rejected.
-- ############################################################################
-- ============================================================================
-- query5c_repeat_victimization.sql (NEW) — ADDRESS-level tiers; the corrected
-- repeat-victimization estimand.
--
-- WHY: legacy query5b divides tier trade counts by per-tier COUNT(DISTINCT address),
-- but tiers partition TRADES, not addresses — the sets overlap (provably: 413,129
-- summed by tier vs 364,713 summed by protocol over the SAME population, so >= 24,208
-- addresses are counted more than once). The paper's "attacks per victim" inverted-U
-- is built on those overlapping denominators.
--
-- HERE: each ADDRESS is classified exactly once, by the exact type-1 median of its own
-- trade sizes, against the SAME trade-level Q(0.50)/Q(0.90) cutoffs as query5b_v2
-- (derived in-query below, so the two estimands stay tier-comparable). Tier address
-- counts are therefore DISJOINT and attacks_per_address is a true mean.
--
-- CAVEATS (state these in the paper, do not bury them):
--  * Q50/Q90 are quantiles of the TRADE distribution, not of the address-median
--    distribution. Address tier shares are an empirical outcome, NOT 50/40/10, and the
--    tier labels are not address-population percentiles.
--  * attacks_per_address is a mean over a very skewed count distribution. max_attacks_
--    single_address and median_attacks_per_address are emitted so mean domination by a
--    single super-address is visible rather than hidden.
--  * If query0b shows the top takers are router CONTRACTS, "address" under-counts
--    persons for those rows under ANY estimand. Resolve query0b before quoting this.
--  * NULL takers are dropped in `addr` (they would pool into one pseudo-address);
--    quantiles are computed BEFORE the drop, so cutoffs still match 5b_v2 exactly.
--    Row count dropped = query0a metric `sandwiched_rows_null_taker`.
-- Per-address median is EXACT: array_sort of the address's trades, element at rank
-- ceil(n_addr/2). Volume is ~3.75M values across <= 365k groups (365k is the by-protocol
-- distinct sum, itself an overcount; exact U comes from query0a).
-- ============================================================================
WITH v AS (
    SELECT amount_usd, taker AS victim_address
    FROM dex.sandwiched
    WHERE block_time >= TIMESTAMP '2024-01-01 00:00:00'  -- sample start
      AND block_time <  TIMESTAMP '2026-01-01 00:00:00'  -- exclusive end of 2025
      AND blockchain = 'ethereum'
      AND amount_usd > 0   -- same restriction as 5a_v2 / 5b_v2
),
r AS (
    SELECT amount_usd,
           ROW_NUMBER() OVER (ORDER BY amount_usd) AS rn,
           COUNT(*)     OVER ()                    AS n
    FROM v
),
breaks AS (
    SELECT
        -- same 0.50/0.90 type-1 quantiles as 5b_v2 (keeps the two estimands comparable)
        MIN(CASE WHEN rn >= CAST(CEILING(0.50 * n) AS BIGINT) THEN amount_usd END) AS q50,
        MIN(CASE WHEN rn >= CAST(CEILING(0.90 * n) AS BIGINT) THEN amount_usd END) AS q90
    FROM r
),
addr AS (
    SELECT
        victim_address,
        COUNT(*)        AS attack_count,
        SUM(amount_usd) AS victim_volume_usd,
        MIN(amount_usd) AS min_trade_usd,
        MAX(amount_usd) AS max_trade_usd,
        -- exact type-1 median of this address's own trade sizes (rank ceil(n_addr/2))
        element_at(array_sort(array_agg(amount_usd)),
                   CAST(CEILING(COUNT(*) * 0.5) AS BIGINT)) AS median_trade_usd
    FROM v
    WHERE victim_address IS NOT NULL   -- see header; sized by query0a sandwiched_rows_null_taker
    GROUP BY 1
),
addr_class AS (
    SELECT a.*, b.q50 AS cutoff_p50, b.q90 AS cutoff_p90,
           CASE WHEN a.median_trade_usd < b.q50 THEN 'Retail'
                WHEN a.median_trade_usd < b.q90 THEN 'Small'
                ELSE 'Institutional' END AS victim_tier,
           -- does this address's trade RANGE cross a tier boundary? tier index of its
           -- largest trade minus tier index of its smallest; 0 = confined to one tier
           (CASE WHEN a.max_trade_usd >= b.q90 THEN 3 WHEN a.max_trade_usd >= b.q50 THEN 2 ELSE 1 END)
         - (CASE WHEN a.min_trade_usd >= b.q90 THEN 3 WHEN a.min_trade_usd >= b.q50 THEN 2 ELSE 1 END)
           AS trade_tier_span
    FROM addr a CROSS JOIN breaks b   -- single row; evaluated once (see 5b_v2 header)
)
SELECT
    victim_tier,
    COUNT(*)                                     AS unique_addresses,    -- DISJOINT: each address once
    SUM(attack_count)                            AS attack_events,
    CAST(SUM(attack_count) AS DOUBLE) / COUNT(*) AS attacks_per_address, -- the corrected inverted-U statistic
    -- skew guards: if max dwarfs the median, the mean above is one address's artifact
    MAX(attack_count)                            AS max_attacks_single_address,
    element_at(array_sort(array_agg(attack_count)),
               CAST(CEILING(COUNT(*) * 0.5) AS BIGINT)) AS median_attacks_per_address,
    SUM(victim_volume_usd)                       AS tier_volume_usd,
    AVG(median_trade_usd)                        AS avg_median_trade_usd,
    -- addresses whose trade range crosses a tier boundary UNDER THE CORRECTED CUTOFFS.
    -- Same phenomenon legacy 5b hid, but NOT numerically comparable to the 413,129-vs-
    -- 364,713 excess, whose boundaries were the approx-p50 and the ad hoc $10,000.
    COUNT_IF(trade_tier_span > 0)                AS addresses_spanning_trade_tiers,
    MIN(cutoff_p50)                              AS cutoff_p50,
    MIN(cutoff_p90)                              AS cutoff_p90
    -- ACCEPTANCE: (a) cutoff_p50/cutoff_p90 must equal 5b_v2's and 5a_v2's, run back-to-back;
    --             (b) SUM(unique_addresses) across the 3 tiers must equal query0a's
    --                 sandwiched_unique_takers_gt0_usd minus any NULL-taker pseudo-address
    --                 — this is the additivity that legacy 5b could not satisfy;
    --             (c) SUM(attack_events) must equal 5b_v2's SUM(victim_trades).
FROM addr_class
GROUP BY 1
ORDER BY CASE victim_tier WHEN 'Retail' THEN 1 WHEN 'Small' THEN 2 ELSE 3 END
