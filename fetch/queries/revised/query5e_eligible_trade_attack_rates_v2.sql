-- ============================================================================
-- query5e_eligible_trade_attack_rates_v2.sql
--
-- NEW ADDITIVE DATA PULL ONLY.
--
-- PURPOSE:
-- Supply the denominator currently missing from H2 by comparing positive-USD
-- Ethereum DEX trade events with the existing dex.sandwiched victim population.
--
-- OBSERVATIONAL UNIT:
-- One dex.trades event identified by (tx_hash, evt_index).
--
-- MATCHING VALIDATION:
-- Prior diagnostic established:
--   * (tx_hash, evt_index) unique in dex.trades on diagnostic day
--   * all positive-USD dex.sandwiched events matched dex.trades on that key
--
-- PRIMARY WINDOW:
-- 2024-01-01 <= block_time < 2026-01-01
-- 24 months / 731 days
--
-- FILTER:
-- amount_usd > 0, matching query5a/query5b and victim-side analysis.
--
-- IMPORTANT INTERPRETATION:
-- `candidate_trade_events` is the broader positive-USD dex.trades denominator.
-- Do not relabel it "eligible trades" in the paper until the effective coverage
-- of sandwich detection across DEX projects/versions has been established.
--
-- ACCEPTANCE:
-- Sum(attacked_trade_events) should reproduce the existing primary victim-side
-- positive-USD count. At the validated run this was 3,753,857.
--
-- For every output row:
-- candidate_trade_events =
--     attacked_trade_events + unattacked_trade_events
-- ============================================================================

WITH victims AS (
    SELECT DISTINCT
        tx_hash,
        evt_index
    FROM dex.sandwiched
    WHERE block_time >= TIMESTAMP '2024-01-01 00:00:00'
      AND block_time <  TIMESTAMP '2026-01-01 00:00:00'
      AND blockchain = 'ethereum'
      AND amount_usd > 0
),

trades AS (
    SELECT
        DATE_TRUNC('month', block_time) AS month,
        project,
        version,
        tx_hash,
        evt_index,
        amount_usd
    FROM dex.trades
    WHERE block_time >= TIMESTAMP '2024-01-01 00:00:00'
      AND block_time <  TIMESTAMP '2026-01-01 00:00:00'
      AND blockchain = 'ethereum'
      AND amount_usd > 0
),

classified AS (
    SELECT
        t.month,
        t.project,
        t.version,
        t.amount_usd,

        CASE
            WHEN t.amount_usd < 100       THEN '01_<100'
            WHEN t.amount_usd < 250       THEN '02_100_250'
            WHEN t.amount_usd < 500       THEN '03_250_500'
            WHEN t.amount_usd < 1000      THEN '04_500_1000'
            WHEN t.amount_usd < 2500      THEN '05_1000_2500'
            WHEN t.amount_usd < 5000      THEN '06_2500_5000'
            WHEN t.amount_usd < 10000     THEN '07_5000_10000'
            WHEN t.amount_usd < 25000     THEN '08_10000_25000'
            WHEN t.amount_usd < 50000     THEN '09_25000_50000'
            WHEN t.amount_usd < 100000    THEN '10_50000_100000'
            ELSE                               '11_100000_plus'
        END AS trade_size_bin,

        CASE
            WHEN v.tx_hash IS NOT NULL THEN 1
            ELSE 0
        END AS is_sandwiched

    FROM trades t
    LEFT JOIN victims v
        ON t.tx_hash = v.tx_hash
       AND t.evt_index = v.evt_index
)

SELECT
    month,
    project,
    version,
    trade_size_bin,

    COUNT(*) AS candidate_trade_events,

    SUM(is_sandwiched) AS attacked_trade_events,

    COUNT(*) - SUM(is_sandwiched) AS unattacked_trade_events,

    SUM(amount_usd) AS candidate_volume_usd,

    SUM(
        CASE
            WHEN is_sandwiched = 1 THEN amount_usd
            ELSE 0
        END
    ) AS attacked_volume_usd,

    AVG(amount_usd) AS avg_trade_size_usd,

    MIN(amount_usd) AS min_trade_size_usd,

    MAX(amount_usd) AS max_trade_size_usd,

    CAST(SUM(is_sandwiched) AS DOUBLE)
        / COUNT(*) * 100 AS attack_rate_pct

FROM classified

GROUP BY
    month,
    project,
    version,
    trade_size_bin

ORDER BY
    month,
    project,
    version,
    trade_size_bin

