# Data and Schema Validation Report

## Summary of Assertions

| Check ID | Description | Expected | Computed | Status |
|---|---|---|---|---|
| Q1-ROWS | q1 row count == 731 | 731 | 731 | **PASS** |
| Q1-DATES | q1 date range 2024-01-01 to 2025-12-31 | 2024-01-01 to 2025-12-31 | 2024-01-01 to 2025-12-31 | **PASS** |
| Q1-NOGAPS | q1 zero missing days | 731 | 731 | **PASS** |
| Q1-VOL-SUM | q1 sum(total_sandwich_volume_usd) == 247322343792.92 (tol 1.0) | 247322343792.92 | 247322343792.92 | **PASS** |
| Q1-TRADES-SUM | q1 sum(sandwich_trade_count) == 7205568 (exact) | 7205568 | 7205568 | **PASS** |
| Q1-VOL-MEAN | q1 mean daily volume == 338334259.63 (tol 1.0) | 338334259.63 | 338334259.63 | **PASS** |
| Q1-VOL-MAX | q1 max day == 2025-08-09 at 1610042604.93 (tol 1.0) | 2025-08-09: 1610042604.93 | 2025-08-09: 1610042604.93 | **PASS** |
| Q1-VOL-MIN | q1 min day == 2024-06-23 at 93006121.47 (tol 1.0) | 2024-06-23: 93006121.47 | 2024-06-23: 93006121.47 | **PASS** |
| Q1-VOL-2024 | q1 mean daily volume 2024 == 242.85M (tol 0.1M) | 242.85M | 242.85M | **PASS** |
| Q1-VOL-2025 | q1 mean daily volume 2025 == 434.08M (tol 0.1M) | 434.08M | 434.08M | **PASS** |
| Q1-BOTS-ALL | q1 mean unique bots overall == 172.4 (tol 0.2) | 172.4 | 172.4 | **PASS** |
| Q1-BOTS-2024 | q1 mean unique bots 2024 == 217.7 (tol 0.2) | 217.7 | 217.7 | **PASS** |
| Q1-BOTS-2025 | q1 mean unique bots 2025 == 127.0 (tol 0.2) | 127.0 | 127.0 | **PASS** |
| Q3-ROWS | q3 row count == 9749 | 9749 | 9749 | **PASS** |
| Q3-UNIQUE-ADDR | q3 bot_address unique | 9749 | 9749 | **PASS** |
| Q3-NAN-COUNT | q3 NaN volume count == 117 | 117 | 117 | **PASS** |
| Q3-ZERO-COUNT | q3 zero volume count == 2 | 2 | 2 | **PASS** |
| Q3-VOL-SUM | q3 sum(total_volume_usd) == 247322343792.92 (tol 1.0) | 247322343792.92 | 247322343792.92 | **PASS** |
| Q4-ROWS | q4 row count == 9749 | 9749 | 9749 | **PASS** |
| Q4-ADDR-SET | q4 address set identical to q3 | True | True | **PASS** |
| Q4-VOL-MATCH | q4 per-address volume matches q3 (max abs diff < 0.01) | <0.01 | 0.000961 | **PASS** |
| Q4-TRADES-SUM | q4 sum(total_sandwich_trades) == 7205568 (exact) | 7205568 | 7205568 | **PASS** |
| Q4-DAYS-MEDIAN | q4 median days_active == 3 | 3 | 3.0 | **PASS** |
| Q4-DAYS-MEAN | q4 mean days_active == 12.93 (tol 0.05) | 12.93 | 12.93 | **PASS** |
| Q5A-P50 | q5a p50_median == 1024.4357 (tol 0.01) | 1024.4357 | 1024.4357 | **PASS** |
| Q5A-P90 | q5a p90 == 8928.305 (tol 0.01) | 8928.305 | 8928.305 | **PASS** |
| Q5A-P95 | q5a p95 == 17351.61 (tol 0.05) | 17351.61 | 17351.61 | **PASS** |
| Q5A-MEAN | q5a mean_value == 7317.81 (tol 0.05) | 7317.81 | 7317.81 | **PASS** |
| Q5A-MAX | q5a max_value == 21005460 | 21005460 | 21005460 | **PASS** |
| Q5A-MIN | q5a min_value ≈ 1.239e-23 (<1e-20) | < 1e-20 | 1.2390e-23 | **PASS** |
| Q5A-TOT-VIC | q5a total_victims == 3753918 (exact) | 3753918 | 3753918 | **PASS** |
| Q5B-CNT-RET | q5b victim_count Retail == 1905366 | 1905366 | 1905366 | **PASS** |
| Q5B-CNT-SMA | q5b victim_count Small == 1521961 | 1521961 | 1521961 | **PASS** |
| Q5B-CNT-INST | q5b victim_count Institutional == 326591 | 326591 | 326591 | **PASS** |
| Q5B-CNT-SUM | q5b sum(victim_count) == 3753918 (exact) | 3753918 | 3753918 | **PASS** |
| Q5B-UNIQ-RET | q5b unique_victims Retail == 225280 | 225280 | 225280 | **PASS** |
| Q5B-UNIQ-SMA | q5b unique_victims Small == 149243 | 149243 | 149243 | **PASS** |
| Q5B-UNIQ-INST | q5b unique_victims Institutional == 38606 | 38606 | 38606 | **PASS** |
| Q5B-UNIQ-SUM | q5b sum(unique_victims) == 413129 | 413129 | 413129 | **PASS** |
| Q5B-VOL-SUM | q5b sum(total_volume) == 27470469483.62 (tol 1.0) | 27470469483.62 | 27470469483.62 | **PASS** |
| Q5B-AVG-RET | q5b avg_tx_size Retail == 418.830 (tol 0.01) | 418.830 | 418.830 | **PASS** |
| Q5B-AVG-SMA | q5b avg_tx_size Small == 3329.753 (tol 0.01) | 3329.753 | 3329.753 | **PASS** |
| Q5B-AVG-INST | q5b avg_tx_size Institutional == 66152.130 (tol 0.01) | 66152.130 | 66152.130 | **PASS** |
| Q5B-BOUND-RET | q5b Retail max_tx == 1024.439 (tol 0.01) ≈ p50 | 1024.439 | 1024.439 | **PASS** |
| Q5B-BOUND-SMA-MAX | q5b Small max_tx == 10000.0 (tol 0.01) | 10000.0 | 10000.0 | **PASS** |
| Q5B-BOUND-INST-MIN | q5b Institutional min_tx == 10000.0 (tol 0.01) | 10000.0 | 10000.0 | **PASS** |
| PROT-ROWS | protocol row count == 20 | 20 | 20 | **PASS** |
| PROT-CNT-SUM | protocol sum(sandwich_count) == 3753918 (exact) | 3753918 | 3753918 | **PASS** |
| PROT-VOL-SUM | protocol sum(total_volume_usd) == 27470469483.62 (tol 1.0) | 27470469483.62 | 27470469483.62 | **PASS** |
| PROT-UNI-SHARE | uniswap volume share == 71.96% (tol 0.05pp) | 71.96% | 71.96% | **PASS** |
| PROT-UNI-TRADES | uniswap sandwich_count == 3562502 | 3562502 | 3562502 | **PASS** |
| PROT-UNI-VIC | uniswap unique_victims == 324626 | 324626 | 324626 | **PASS** |
| CROSS-VOL-Q1-Q3 | q1 volume total == q3 volume total (tol 1.0) | True | abs(247322343792.92 - 247322343792.92) | **PASS** |
| CROSS-TRADES-Q1-Q4 | q1 trade total == q4 trade total (exact) | True | 7205568 == 7205568 | **PASS** |
| CROSS-VIC-Q5B-Q5A-PROT | q5b victim_count sum == q5a total_victims == prot sandwich_count sum | True | 3753918 == 3753918 == 3753918 | **PASS** |
| CROSS-VOL-Q5B-PROT | q5b volume sum == protocol volume sum (tol 1.0) | True | abs(27470469483.62 - 27470469483.62) | **PASS** |
| TOTAL-CHECKS | total validation checks >= 40 | >= 40 | 57 | **PASS** |

## Documented Data Quirks

1. **Missing and Zero Volumes in Bot Distribution (`query3`/`query4`)**: Exactly 117 bot addresses have `NaN` total volume (due to missing historical token prices in Dune Analytics), and 2 bot addresses have exactly `0.0` volume. These 119 bots are excluded from volume-based concentration analysis (`B_meas`, N=9,632) and positive-volume analysis (`B_pos`, N=9,630), as documented in sample definitions.
2. **Pricing Artifact in Victim Trade Sizes (`query5a`)**: The minimum victim trade size (`min_value`) is reported as approximately $1.239 \times 10^{-23}$ USD. This is an extreme pricing/precision artifact in raw DEX swap logs and points to the necessity of trade-level winsorization in microdata analyses.
3. **Dataset README Mislabels Corrected**: (a) Despite its file name and README description, `query4_top_bots.csv` covers all 9,749 bot addresses (identical set to `query3`), not just 'top' bots. (b) In `query5a_break_points.csv`, `total_victims` (3,753,918) represents total sandwiched VICTIM TRADES (attack events), NOT unique victim addresses (which total 413,129 across tiers). (c) In `query5b_victim_impact.csv`, `pct_of_victims` represents the tier share of victim trades, not unique addresses. (d) The upper cutoff for the Small tier / lower cutoff for Institutional in `query5b` is a round $10,000, NOT the $p_{90}$ ($8,928.31) stated in the draft/README. (e) **Correction #6**: The README describes `sandwich_count` in `query_protocol_vulnerability.csv` as sandwich bot trades, but the column sums to 3,753,918 (victim trades) and `total_volume_usd` to the $27.47B victim volume — the protocol file is victim-side and must be labelled as such in all tables and analyses.
4. **Tier Cutoff Discrepancy ($10,000 vs. $p_{90}$)**: Formal audit verifies that the Retail upper bound equals $p_{50}$ ($1,024.44), but the Small upper bound and Institutional lower bound are exactly $10,000.00$. This $10,000 cutoff lies between $p_{90}$ ($8,928.31) and $p_{95}$ ($17,351.61$). Re-tiering at exactly $p_{90}$ cannot be performed without trade-level microdata.
5. **Disjoint Measurement Bases (Bot-side vs. Victim-side)**: The dataset contains two distinct measurement bases that must NEVER be mixed or ratioed without explicit labeling: the **Bot-side base** (`query1`, `query3`, `query4`: 7,205,568 bot trades, $247.32B volume, 9,749 addresses) and the **Victim-side base** (`query_protocol`, `query5a`, `query5b`: 3,753,918 victim trades, $27.47B volume, 413,129 unique addresses). The ~9x volume ratio reflects definitional and measurement differences (counting both front-run and back-run bot legs, multi-hop routing, and DEX detection scopes) and has no economic interpretation.

## Analyst Decisions

Where the specification leaves implementation details to econometric discretion, standard conventions were adopted and recorded:
- **Newey-West HAC Standard Errors**: Configured with explicit lag length `maxlags=7` for daily time series regressions to account for weekly seasonality and persistent autocorrelation ($AR(1) \approx 0.78$).
- **Bootstrap Confidence Intervals**: Computed using 10,000 replications with fixed random seed (`numpy.random.default_rng(42)`) via the non-parametric percentile method.
- **Quandt-Andrews Unknown Date Break Scan**: Conducted over the central 70% sample window (15% trimming on each end) using a seeded circular moving-block bootstrap with block length = 14 days (999 replications, `rng=42`).
- **Structural Break Segmentation**: Applied `ruptures` binary segmentation (`Binseg`) with `l2` cost on log daily volume, capped at a maximum of 3 breaks to prevent over-segmentation on trending series.
- **Chow Tests**: Classical known-date Chow tests are explicitly labeled as descriptive due to non-iid daily volume errors ($AR(1) \approx 0.78$), with HAC-robust F-tests on interrupted time series step/slope terms providing formal inference.
