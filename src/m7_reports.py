import os
import pandas as pd
import numpy as np
from src import m0_validate, m1_prepare, m2_concentration, m3_bot_dynamics, m4_victims, m5_timeseries, m6_synthesis

def generate_reports():
    os.makedirs("output/reports", exist_ok=True)
    
    # Run pipeline steps or load existing prepared data
    q1, q3, q4, prot, q5a, q5b, B_full, B_meas, B_pos = m1_prepare.prepare_all()
    
    # Extract exact metrics from tables or recalculate to ensure 100% exact consistency without rounding drift
    gini_meas = m2_concentration.compute_gini(B_meas["total_volume_usd"])
    cr_meas = m2_concentration.compute_concentration_ratios(B_meas["total_volume_usd"])
    alpha_5, se_5, _ = m2_concentration.hill_estimator(B_pos["total_volume_usd"], 0.05)
    zeta_gi, se_gi, _, _ = m2_concentration.gabaix_ibragimov(B_pos["total_volume_usd"], 500)
    
    ret_row = q5b[q5b["victim_tier"] == "Retail"].iloc[0]
    sma_row = q5b[q5b["victim_tier"] == "Small"].iloc[0]
    inst_row = q5b[q5b["victim_tier"] == "Institutional"].iloc[0]
    
    rr_sr, sr_low, sr_high, _ = m4_victims.poisson_rate_ratio(sma_row["victim_count"], sma_row["unique_victims"], ret_row["victim_count"], ret_row["unique_victims"])
    rr_ri, ri_low, ri_high, _ = m4_victims.poisson_rate_ratio(ret_row["victim_count"], ret_row["unique_victims"], inst_row["victim_count"], inst_row["unique_victims"])
    
    bot_vol = q4["total_volume_usd"].sum()
    vic_vol = q5b["total_volume"].sum()
    ratio_vol = bot_vol / vic_vol
    
    # 1. results_summary.md
    summary_md = f"""# Empirical Results Summary: Distributional Incidence of Sandwich-MEV on Ethereum (2024–2025)

This report provides the synthesized empirical findings of the Sandwich-MEV quantitative analysis pipeline, evaluated across five core hypotheses ($H_1$--$H_5$) using daily and cross-sectional data exported from Dune Analytics.

---

## 1. Searcher Concentration and Market Structure ($H_1$)

### Key Empirical Findings
- **Extreme Gini Inequality:** Across the $B_{{\\text{{meas}}}}$ sample ($N = 9,632$ bot addresses with non-missing volume), searcher trading volume exhibits an extreme Gini coefficient of **{gini_meas:.4f}** (95% bootstrap CI: $[0.9974, 0.9978]$).
- **Winner-Take-Most Concentration Ratios:** The single largest searcher bot address account for **{cr_meas['cr1']:.2f}%** of all searcher volume (CR1), while the top 4 bots control **{cr_meas['cr4']:.2f}%** (CR4), the top 10 control **{cr_meas['cr10']:.2f}%** (CR10), and the top 20 control **{cr_meas['cr20']:.2f}%** (CR20). The top 1% of bot addresses ($k = {cr_meas['k_1']}$) capture **{cr_meas['top_1']:.2f}%** of total notional volume, and the top 10% capture **{cr_meas['top_10']:.2f}%**.
- **Herfindahl-Hirschman Index:** The HHI across searcher bot addresses stands at **{cr_meas['hhi']:,.1f}** (on a 0--10,000 scale), indicating a highly concentrated market structure.
- **Heavy-Tailed Pareto Distribution:** On the strictly positive volume sample ($B_{{\\text{{pos}}}}$, $N = 9,630$), tail exponent estimation confirms an infinite-mean regime. The Hill estimator for the top 5% tail yields $\\hat{{\\alpha}} = {alpha_5:.4f}$ (SE: ${se_5:.4f}$), while the Gabaix-Ibragimov rank-size regression on the top 500 bots estimates an OLS power-law slope of $\\hat{{\\zeta}} = {zeta_gi:.4f}$ (SE: ${se_gi:.4f}$). Both $\\hat{{\\alpha}} < 1$ and $\\hat{{\\zeta}} < 1$ demonstrate an extreme Pareto upper tail significantly heavier than Zipf's law ($\\alpha = 1$), confirming winner-take-most dynamics in MEV extraction.

### Methodological Caveat: Address vs. Entity Concentration
*Sybil Caveat:* Ethereum on-chain addresses do not map one-to-one with economic entities. A single searcher operator or algorithmic trading firm may deploy multiple bot addresses (Sybil addresses) for operational security or routing efficiency, or conversely, independent searcher algorithms may route trades through a shared settlement contract. Therefore, economic entity-level concentration is not formally identified by address-level data, and the direction of bias is theoretically ambiguous.

---

## 2. Victim-Side Incidence and Repeat Victimization ($H_2$ & $H_5$)

### Key Empirical Findings
- **Inverted-U Non-Monotonic Victimization:** Repeat victimization per unique victim address does **not** decrease monotonically with trade size. In the **Small** tier (\\$418.83 to \\$10,000.00), traders suffer an average of **{sma_row['attacks_per_victim']:.2f}** attacks per unique address. By contrast, traders in the **Retail** tier (< \\$418.83) suffer **{ret_row['attacks_per_victim']:.2f}** attacks per address, and traders in the **Institutional** tier (>= \\$10,000.00) suffer **{inst_row['attacks_per_victim']:.2f}** attacks per address.
- **Formal Poisson Rate Ratios:** Formal inference under a Poisson exposure model confirms that the Small tier attack frequency is **20.6% above** the Retail tier, with a Rate Ratio of **{rr_sr:.4f}** (95% CI: $[{sr_low:.4f}, {sr_high:.4f}]$). Similarly, the Small tier experiences 20.6% higher attack frequency than the Institutional tier.
- **Indistinguishability of Extreme Tiers:** The Rate Ratio comparing Retail to Institutional attack frequency is **{rr_ri:.4f}** (95% CI: $[{ri_low:.4f}, {ri_high:.4f}]$). Because this confidence interval strictly includes 1.0, attack frequency per unique address between Retail and Institutional traders is statistically indistinguishable.
- **Economic Refinement:** This inverted-U finding refutes a simple "more attacks for the smallest traders" narrative and provides rigorous empirical support for a "middle-tier squeeze", where mid-sized DEX traders experience the highest frequency of repeat extraction.

### Mechanical-Identity Audit: Attacks per \$1,000 Traded
*Mandatory Methodological Caveat:* In any trade-size tier, the metric $\\text{{Attacks per \\$1,000 Traded}}$ is computed as $(\\text{{Victim Trades}} / \\text{{Total Volume}}) \\times 1,000$. Because $\\text{{Total Volume}} = \\text{{Victim Trades}} \\times \\text{{Avg Tx Size}}$, this ratio simplifies algebraically to:
$$\\text{{Attacks per \\$1,000 Traded}} \\equiv \\frac{{1,000}}{{\\text{{Avg Tx Size}}}}$$
Consequently, the apparent 157.94-fold discrepancy between Retail attacks per \\$1,000 traded (2.39) and Institutional attacks per \\$1,000 traded (0.0151) is **algebraically identical** to the Institutional-to-Retail ratio of average trade sizes (\\$66,152.13 / \\$418.83 = 157.94x). This metric contains no empirical information beyond the average trade size spread and must not be interpreted as independent evidence of differential vulnerability.

### Loss-Model Sensitivity & Identification Limitations
*Regressivity Identification Caveat:* Whether MEV extraction constitutes a "regressive tax" per dollar traded is fundamentally unidentified in pre-aggregated DEX data. Calibrating three alternative loss-scaling models to an identical aggregate loss anchor of 1% of total victim volume (\\$274.70M) demonstrates that regressivity depends entirely on unobserved micro-level scaling:
1. **Proportional Model:** If loss scales linearly with trade size (1% flat), extraction is strictly proportional (100 basis points across all tiers).
2. **Constant per Attack Model:** If every attack extracts a constant dollar amount (\\$73.18/attack), extraction is hyper-regressive, imposing ~1,747 bps on Retail versus ~11 bps on Institutional traders (a >= 150x spread).
3. **Square-Root Impact Model:** If loss scales with the square root of trade size, extraction exhibits mild regressivity.
Because realized slippage and per-trade extraction amounts are unobserved in the export, the data pin down attack frequencies and volume distributions, but not welfare loss rates.

---

## 3. Time-Series Persistence, Seasonality, and Structural Shifts ($H_3$)

### Key Empirical Findings
- **High Autocorrelation and Stationarity:** Log daily searcher volume ($y_t = \\ln V_t$, $N = 731$ days) exhibits strong first-order autocorrelation ($AR(1) \\approx 0.782$ and $AR(7) \\approx 0.443$). Augmented Dickey-Fuller (ADF) testing rejects the unit root null in favor of trend-stationarity at $p < 0.001$, while KPSS testing confirms stationarity around a deterministic trend.
- **Secular Trend Growth:** Baseline OLS regression with Newey-West HAC standard errors (7 lags) estimates a statistically significant linear trend of $\\beta = 0.001214$ ($p < 0.001$), corresponding to an average daily volume growth rate of **+0.121% per day** (~56% annualized growth in log volume).
- **Weekly Seasonality:** Searcher activity exhibits pronounced weekly seasonality. Mean daily volume during weekdays (Monday--Friday) averages **\\$377.30M**, falling by **28.48%** during weekends (Saturday--Sunday) to an average of **\\$269.85M**.
- **Dynamic Searcher Consolidation:** Comparing calendar year 2024 to 2025 in `query1`, mean daily active searcher bot addresses fell from **217.7 bots/day** in 2024 to **127.0 bots/day** in 2025 (a **-41.67% decline**). Simultaneously, mean daily searcher volume rose by **+78.69%**. This massive increase in volume per active bot provides powerful time-series confirmation of dynamic concentration under $H_1$.
- **Structural Shifts Around Upgrades:** Interrupted Time Series (ITS) regressions confirm significant joint step and slope shifts around the Dencun (2024-03-13) and Pectra (2025-05-07) network upgrades (Wald F-test $p < 0.001$). However, raw event-window post/pre volume ratios (Dencun: 1.19x, Pectra: 1.35x) are heavily confounded by underlying trend growth when compared against a 200-replication placebo distribution.
- **Methodological Note on Chow Tests:** Because daily volume violates the iid error assumption required by classical Chow tests ($AR(1) \\approx 0.78$), known-date Chow F-statistics are reported descriptively. Primary formal inference relies on HAC-robust ITS Wald tests and Quandt-Andrews unknown-date scans evaluated via a 999-replication circular moving-block bootstrap (block length 14 days).

---

## 4. Protocol Vulnerability and DEX Concentration ($H_4$)

### Key Empirical Findings
- **Protocol Volume Dominance:** Across the 3,753,918 victim trade events in `query_protocol_vulnerability.csv`, sandwich volume is heavily concentrated in automated market makers (AMMs). **Uniswap v2** accounts for **\\$13.43B** (48.87% of victim volume) and **Uniswap v3** accounts for **\\$11.08B** (40.35%), yielding a combined four-firm concentration ratio (CR2) of **89.22%**.
- **Protocol HHI:** The Herfindahl-Hirschman Index across the six monitored routing protocols is **4,057.1**, indicating an extremely concentrated market structure.
- **Identification Caveat on Protocol Security:** While $H_4$ is supported in terms of raw volume concentration in AMMs, this dominance does **not** identify inherent differences in protocol security design or smart contract vulnerability. Uniswap v2 and v3 account for the vast majority of all decentralized exchange trading volume on Ethereum; therefore, their dominance in sandwich volume mechanically reflects their underlying market share. A rigorous test of protocol-specific vulnerability would require normalizing sandwich volume by total DEX routing volume per protocol, which is unobserved in this dataset.

---

## 5. Cross-Base Reconciliation & Synthesis ($H_5$)

### Measurement Base Reconciliation
The Dune Analytics export contains two disjoint measurement bases that must never be mixed without explicit labeling:
1. **Bot-Side Base (`query3` / `query4`):** Measures searcher attacker trade legs ($N = 9,749$ bot addresses, 7,205,568 trade legs, **\\$247.32B** total notional volume).
2. **Victim-Side Base (`query5a` / `query5b` / `protocol`):** Measures sandwiched victim swap events ($N = 413,129$ unique victim addresses, 3,753,918 attack events, **\\$27.47B** total volume).

### Explanation of Divergence (9.00x Volume Ratio)
Searcher bot notional volume exceeds victim notional volume by exactly **9.00x** (\\$247.32B vs \\$27.47B), and searcher trade legs exceed victim attack events by **1.92x** (7.21M vs 3.75M). This divergence is not a data error; it reflects the mechanics of MEV execution on Ethereum:
- A single sandwiched victim trade event (1 leg on the victim side) requires at least two searcher trade legs (a front-run leg and a back-run leg).
- In multi-hop routing or multi-pool arbitrage execution, an MEV bot may execute across several DEX liquidity pools simultaneously to capture price discrepancies created by the victim swap. The bot-side base aggregates the sum of all front-run, back-run, and intermediate routing leg volumes across all pools, whereas the victim base records only the single sandwiched swap.

### Final Distributional Synthesis
The empirical evidence presents a cohesive structure of Ethereum sandwich MEV in 2024--2025:
1. **Extraction Side:** A hyper-concentrated, winner-take-most searcher oligopoly (Gini 0.9976, top-1% share 98.51%, infinite-mean Pareto tail $\\hat{{\\zeta}} = 0.376$) that has consolidated dynamically over time (active bots down 41.7%, volume up 78.7%).
2. **Victim Side:** An inverted-U incidence structure where mid-sized DEX traders (Small tier, \\$418--\\$10k) suffer the highest frequency of repeat victimization (10.20 attacks/address), refuting monotonic regressivity claims in attack frequency.
3. **Welfare Impact:** While attack frequency peaks in the middle tier, whether welfare losses are regressive per dollar traded remains empirically unidentified without micro-level slippage data, highlighting a critical boundary for empirical MEV research.
"""

    with open("output/reports/results_summary.md", "w") as f:
        f.write(summary_md)
    print("[PASS] Generated output/reports/results_summary.md")
    
    # 2. data_dictionary.md
    dict_md = """# Data Dictionary & Variable Specifications: Sandwich-MEV Analysis Pipeline

This data dictionary documents every derived variable, metric, and sample definition created across the quantitative analysis modules (`m1_prepare.py` through `m6_synthesis.py`), along with an inventory of all empirical data quirks identified during validation (`m0_validate.py`).

---

## 1. Primary Data Samples & Restrictions

| Sample Name | Base / Source | Sample Size ($N$) | Definition & Sample Restriction |
| :--- | :--- | :---: | :--- |
| **$B_{\\text{full}}$** | Bot-Side (`query4`) | 9,749 addresses | All sandwich bot addresses present in `query4_bot_summary.csv`. |
| **$B_{\\text{meas}}$** | Bot-Side (`query4`) | 9,632 addresses | Bot addresses with non-missing volume (`total_volume_usd.notna() & >= 0.0`). Includes 2 zero-volume bots. Primary sample for concentration ($H_1$). |
| **$B_{\\text{pos}}$** | Bot-Side (`query4`) | 9,630 addresses | Bot addresses with strictly positive volume (`total_volume_usd > 0.0`). Primary sample for log transforms, longevity, and tail estimation. |
| **Daily Series** | Bot-Side (`query1`) | 731 days | Complete daily time series from 2024-01-01 to 2025-12-31 without gaps. |
| **Victim Base** | Victim-Side (`query5b`) | 3,753,918 events | Sandwiched victim trade events across 413,129 unique victim addresses, disaggregated into Retail, Small, and Institutional tiers. |
| **Protocol Base** | Victim-Side (`protocol`) | 3,753,918 events | Sandwiched victim trade events disaggregated across 6 DEX routing protocols. |

---

## 2. Derived Daily Time-Series Variables (`m1_prepare.py`, `m5_timeseries.py`)

| Variable Name | Module | Formula / Definition | Unit | Interpretation / Usage |
| :--- | :--- | :--- | :--- | :--- |
| `y_t` | `m1_prepare` | `np.log(total_sandwich_volume_usd)` | Log USD | Natural log of daily bot-side volume. Primary dependent variable in time-series regressions ($H_3$). |
| `dow` | `m1_prepare` | `date_parsed.dt.dayofweek` | Categorical (0--6) | Day of week indicator (0 = Monday, ..., 6 = Sunday). Used for weekly seasonality controls. |
| `month` | `m1_prepare` | `date_parsed.dt.month` | Categorical (1--12) | Calendar month indicator. Used for monthly fixed effects in Spec (3). |
| `year_month` | `m1_prepare` | `date_parsed.dt.strftime("%Y-%m")` | Categorical (24 levels) | Year-month string ('2024-01' to '2025-12'). Used for cluster-robust standard errors in Spec (4). |
| `t` | `m1_prepare` | `np.arange(len(q1))` | Integer (0--730) | Linear daily time trend (0 = 2024-01-01, 730 = 2025-12-31). |
| `t_dencun` | `m1_prepare` | Index of date '2024-03-13' | Constant ($t = 72$) | Zero-indexed integer time step of the Dencun network upgrade. |
| `t_pectra` | `m1_prepare` | Index of date '2025-05-07' | Constant ($t = 492$) | Zero-indexed integer time step of the Pectra network upgrade. |
| `D_dencun` | `m1_prepare` | `1(t >= t_dencun)` | Binary indicator (0/1) | Step dummy for Dencun upgrade post-period. |
| `D_pectra` | `m1_prepare` | `1(t >= t_pectra)` | Binary indicator (0/1) | Step dummy for Pectra upgrade post-period. |
| `S_dencun` | `m1_prepare` | `D_dencun * (t - t_dencun)` | Linear slope (0, 1, 2, ...) | Post-Dencun slope interaction term in Interrupted Time Series regressions. |
| `S_pectra` | `m1_prepare` | `D_pectra * (t - t_pectra)` | Linear slope (0, 1, 2, ...) | Post-Pectra slope interaction term in Interrupted Time Series regressions. |
| `ma7` | `m5_timeseries` | `vol_m.rolling(7, center=True).mean()` | USD Millions | 7-day centered moving average of daily bot volume, plotted in Figure 1. |

---

## 3. Derived Bot-Level & Concentration Variables (`m1_prepare.py`, `m2_concentration.py`, `m3_bot_dynamics.py`)

| Variable Name | Module | Formula / Definition | Unit | Interpretation / Usage |
| :--- | :--- | :--- | :--- | :--- |
| `lifespan_days` | `m1_prepare` | `(last_seen - first_seen).dt.days + 1` | Days (integer >= 1) | Total calendar duration between a bot address's first and last observed transaction. |
| `intensity` | `m1_prepare` | `total_sandwich_trades / days_active` | Trades per active day | Average trading frequency on days when the bot was active on-chain. |
| `first_seen_cohort` | `m1_prepare` | Six-month entry window based on `first_seen` | Categorical (4 levels) | Assigns bots to entry cohorts: `2024H1`, `2024H2`, `2025H1`, `2025H2`. |
| `active_at_end` | `m1_prepare` | `1(last_seen >= '2025-12-01')` | Binary indicator (0/1) | Indicates whether a bot address survived into the final month of the sample period. |
| `Gini` | `m2_concentration` | `sum((2i - n - 1)*x_i) / (n * sum(x_i))` | Index (0 to 1) | Non-parametric inequality measure of bot volume distribution on $B_{\\text{meas}}$. |
| `CR1, CR4, CR10, CR20` | `m2_concentration` | Sum of top $k$ bot volumes / total volume | Percentage (%) | Concentration ratios measuring volume share held by top 1, 4, 10, and 20 bot addresses. |
| `top_01, top_1, top_5, top_10` | `m2_concentration` | Share of top $k = \\lceil n \\cdot p \\rceil$ bots | Percentage (%) | Top percentile volume shares (e.g., Top 1% = top 97 bots in $B_{\\text{meas}}$). |
| `HHI` | `m2_concentration` | `sum((share_i)^2) * 10000` | Index (0 to 10,000) | Herfindahl-Hirschman Index of market concentration across searcher addresses. |
| `Hill_alpha` ($\\hat{\\alpha}$) | `m2_concentration` | `[ (1/k) sum(ln(x_{(i)} / x_{(k+1)})) ]^{-1}` | Tail exponent | Hill estimator on top 5% and 10% bots in $B_{\\text{pos}}$. $\\hat{\\alpha} < 1$ indicates infinite-mean heavy tail. |
| `GI_zeta` ($\\hat{\\zeta}$) | `m2_concentration` | `-slope` from OLS of `ln(rank - 0.5)` on `ln(vol)` | Power-law slope | Gabaix-Ibragimov rank-size tail exponent on top 500 bots in $B_{\\text{pos}}$. |

---

## 4. Derived Victim-Tier & Loss-Model Variables (`m1_prepare.py`, `m4_victims.py`)

| Variable Name | Module | Formula / Definition | Unit | Interpretation / Usage |
| :--- | :--- | :--- | :--- | :--- |
| `attacks_per_victim` | `m1_prepare` | `victim_count / unique_victims` | Attacks per address | Mean number of repeat sandwich attacks suffered per unique victim address in a tier. |
| `attacks_per_1000usd` | `m1_prepare` | `(victim_count / total_volume) * 1000` | Attacks per \\$1k | Attack density per dollar traded. **Algebraically identical to `1000 / avg_tx_size`.** |
| `share_of_events` | `m1_prepare` | `victim_count / 3753918` | Percentage (%) | Share of total sandwiched victim trade events accounted for by a tier. |
| `share_of_volume` | `m1_prepare` | `total_volume / sum(total_volume)` | Percentage (%) | Share of total victim notional volume accounted for by a tier. |
| `avg_volume_per_unique_victim` | `m1_prepare` | `total_volume / unique_victims` | USD per address | Average total dollar volume traded per unique victim address within a tier. |
| `loss_att_prop` | `m4_victims` | `0.01 * avg_tx_size` | USD | Implied per-attack loss under Model (a) [Proportional 1% flat loss]. |
| `loss_att_const` | `m4_victims` | `L_tot / N_tot` = \\$73.1781 | USD | Implied per-attack loss under Model (b) [Constant per attack]. Calibrated to \\$274.7M total loss. |
| `loss_att_sqrt` | `m4_victims` | `c_sqrt * sqrt(avg_tx_size)` | USD | Implied per-attack loss under Model (c) [Square-root impact]. Calibrated to \\$274.7M total loss. |
| `bps_prop, bps_const, bps_sqrt` | `m4_victims` | `(loss_att / avg_tx_size) * 10000` | Basis points (bps) | Implied victim loss rate per dollar traded under each calibrated loss model (100 bps = 1%). |

---

## 5. Inventory of Documented Empirical Data Quirks (`m0_validate.py`)

During initial data loading and validation in Step 0, five specific data quirks were identified, verified, and handled in the analysis pipeline:

1. **Missing and Zero Volume in `query4_bot_summary.csv`:**
   - *Description:* Exactly 117 bot addresses have `NaN` for `total_volume_usd`, and exactly 2 bot addresses have `total_volume_usd == 0.0`.
   - *Handling:* The full sample $B_{\\text{full}}$ ($N=9,749$) is restricted to $B_{\\text{meas}}$ ($N=9,632$) by requiring non-missing volume (`notna() & >= 0.0`). For log transforms and tail estimation, the sample is restricted to strictly positive volume $B_{\\text{pos}}$ ($N=9,630$). Both zero-volume addresses (`0x00000000003b3cc22af3ae1eac0440bcee416b40`, `0x4200000000000000000000000000000000000006`) represent specialized MEV settlement or builder contracts.

2. **Divergence of Measurement Bases (Bot vs. Victim Volume):**
   - *Description:* Total bot-side volume (\\$247.32B) exceeds total victim-side volume (\\$27.47B) by 9.00x, and bot trade legs (7,205,568) exceed victim trade events (3,753,918) by 1.92x.
   - *Handling:* Both bases are validated independently. Table 8 explicitly reconciles this divergence, explaining that searcher volume aggregates multi-hop front-run and back-run routing legs across all DEX pools involved, whereas victim volume records only the single sandwiched swap.

3. **Mislabeled Column in `query_protocol_vulnerability.csv`:**
   - *Description:* The README file defines the column `sandwich_count` in `query_protocol_vulnerability.csv` as "sandwich bot trades". However, the column sums to exactly 3,753,918, which aligns 100% with the total victim trade events in `query5b`.
   - *Handling:* Per User Correction #6, this file is formally classified as victim-side data ("vulnerability by protocol") and its column is correctly reported as victim trade events ($N=3,753,918$) in Table 8 and Section 4 reports.

4. **Extreme Minimum Trade Size Artifact in `query5a`:**
   - *Description:* The minimum victim trade size reported in `query5a` is $1.24 \\times 10^{-23}$ USD.
   - *Handling:* This value represents an extreme precision/pricing artifact in raw DEX swap logs (e.g., dust swaps of wei-level quantities in illiquid pools). It is reported transparently in Panel C of Table 1 with an explicit explanatory footnote.

5. **Tier Cutoff Straddling and Non-Equality with $p_{90}$:**
   - *Description:* In `query5b`, the Small tier maximum trade size (\\$10,000.00) and Institutional tier minimum trade size (\\$10,000.00) straddle exactly \\$10,000. In `query5a`, the 90th percentile of victim trade size is $p_{90} = \\$8,928.31$, confirming that the Institutional cutoff of \\$10,000 does not equal $p_{90}$.
   - *Handling:* Verified via automated assertions in `m4_victims.py` and documented in `validation_report.md` and Table 4 notes.
"""

    with open("output/reports/data_dictionary.md", "w") as f:
        f.write(dict_md)
    print("[PASS] Generated output/reports/data_dictionary.md")
    
    return True

if __name__ == "__main__":
    generate_reports()
