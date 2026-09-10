# Data Dictionary & Variable Specifications: Sandwich-MEV Analysis Pipeline

This data dictionary documents every derived variable, metric, and sample definition created across the quantitative analysis modules (`m1_prepare.py` through `m6_synthesis.py`), along with an inventory of all empirical data quirks identified during validation (`m0_validate.py`).

---

## 1. Primary Data Samples & Restrictions

| Sample Name | Base / Source | Sample Size ($N$) | Definition & Sample Restriction |
| :--- | :--- | :---: | :--- |
| **$B_{\text{full}}$** | Bot-Side (`query4`) | 9,749 addresses | All sandwich bot addresses present in `query4_bot_summary.csv`. |
| **$B_{\text{meas}}$** | Bot-Side (`query4`) | 9,632 addresses | Bot addresses with non-missing volume (`total_volume_usd.notna() & >= 0.0`). Includes 2 zero-volume bots. Primary sample for concentration ($H_1$). |
| **$B_{\text{pos}}$** | Bot-Side (`query4`) | 9,630 addresses | Bot addresses with strictly positive volume (`total_volume_usd > 0.0`). Primary sample for log transforms, longevity, and tail estimation. |
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
| `Gini` | `m2_concentration` | `sum((2i - n - 1)*x_i) / (n * sum(x_i))` | Index (0 to 1) | Non-parametric inequality measure of bot volume distribution on $B_{\text{meas}}$. |
| `CR1, CR4, CR10, CR20` | `m2_concentration` | Sum of top $k$ bot volumes / total volume | Percentage (%) | Concentration ratios measuring volume share held by top 1, 4, 10, and 20 bot addresses. |
| `top_01, top_1, top_5, top_10` | `m2_concentration` | Share of top $k = \lceil n \cdot p \rceil$ bots | Percentage (%) | Top percentile volume shares (e.g., Top 1% = top 97 bots in $B_{\text{meas}}$). |
| `HHI` | `m2_concentration` | `sum((share_i)^2) * 10000` | Index (0 to 10,000) | Herfindahl-Hirschman Index of market concentration across searcher addresses. |
| `Hill_alpha` ($\hat{\alpha}$) | `m2_concentration` | `[ (1/k) sum(ln(x_{(i)} / x_{(k+1)})) ]^{-1}` | Tail exponent | Hill estimator on top 5% and 10% bots in $B_{\text{pos}}$. $\hat{\alpha} < 1$ indicates infinite-mean heavy tail. |
| `GI_zeta` ($\hat{\zeta}$) | `m2_concentration` | `-slope` from OLS of `ln(rank - 0.5)` on `ln(vol)` | Power-law slope | Gabaix-Ibragimov rank-size tail exponent on top 500 bots in $B_{\text{pos}}$. |

---

## 4. Derived Victim-Tier & Loss-Model Variables (`m1_prepare.py`, `m4_victims.py`)

| Variable Name | Module | Formula / Definition | Unit | Interpretation / Usage |
| :--- | :--- | :--- | :--- | :--- |
| `attacks_per_victim` | `m1_prepare` | `victim_count / unique_victims` | Attacks per address | Mean number of repeat sandwich attacks suffered per unique victim address in a tier. |
| `attacks_per_1000usd` | `m1_prepare` | `(victim_count / total_volume) * 1000` | Attacks per \$1k | Attack density per dollar traded. **Algebraically identical to `1000 / avg_tx_size`.** |
| `share_of_events` | `m1_prepare` | `victim_count / 3753918` | Percentage (%) | Share of total sandwiched victim trade events accounted for by a tier. |
| `share_of_volume` | `m1_prepare` | `total_volume / sum(total_volume)` | Percentage (%) | Share of total victim notional volume accounted for by a tier. |
| `avg_volume_per_unique_victim` | `m1_prepare` | `total_volume / unique_victims` | USD per address | Average total dollar volume traded per unique victim address within a tier. |
| `loss_att_prop` | `m4_victims` | `0.01 * avg_tx_size` | USD | Implied per-attack loss under Model (a) [Proportional 1% flat loss]. |
| `loss_att_const` | `m4_victims` | `L_tot / N_tot` = \$73.1781 | USD | Implied per-attack loss under Model (b) [Constant per attack]. Calibrated to \$274.7M total loss. |
| `loss_att_sqrt` | `m4_victims` | `c_sqrt * sqrt(avg_tx_size)` | USD | Implied per-attack loss under Model (c) [Square-root impact]. Calibrated to \$274.7M total loss. |
| `bps_prop, bps_const, bps_sqrt` | `m4_victims` | `(loss_att / avg_tx_size) * 10000` | Basis points (bps) | Implied victim loss rate per dollar traded under each calibrated loss model (100 bps = 1%). |

---

## 5. Inventory of Documented Empirical Data Quirks (`m0_validate.py`)

During initial data loading and validation in Step 0, five specific data quirks were identified, verified, and handled in the analysis pipeline:

1. **Missing and Zero Volume in `query4_bot_summary.csv`:**
   - *Description:* Exactly 117 bot addresses have `NaN` for `total_volume_usd`, and exactly 2 bot addresses have `total_volume_usd == 0.0`.
   - *Handling:* The full sample $B_{\text{full}}$ ($N=9,749$) is restricted to $B_{\text{meas}}$ ($N=9,632$) by requiring non-missing volume (`notna() & >= 0.0`). For log transforms and tail estimation, the sample is restricted to strictly positive volume $B_{\text{pos}}$ ($N=9,630$). Both zero-volume addresses (`0x00000000003b3cc22af3ae1eac0440bcee416b40`, `0x4200000000000000000000000000000000000006`) represent specialized MEV settlement or builder contracts.

2. **Divergence of Measurement Bases (Bot vs. Victim Volume):**
   - *Description:* Total bot-side volume (\$247.32B) exceeds total victim-side volume (\$27.47B) by 9.00x, and bot trade legs (7,205,568) exceed victim trade events (3,753,918) by 1.92x.
   - *Handling:* Both bases are validated independently. Table 8 explicitly reconciles this divergence, explaining that searcher volume aggregates multi-hop front-run and back-run routing legs across all DEX pools involved, whereas victim volume records only the single sandwiched swap.

3. **Mislabeled Column in `query_protocol_vulnerability.csv`:**
   - *Description:* The README file defines the column `sandwich_count` in `query_protocol_vulnerability.csv` as "sandwich bot trades". However, the column sums to exactly 3,753,918, which aligns 100% with the total victim trade events in `query5b`.
   - *Handling:* Per User Correction #6, this file is formally classified as victim-side data ("vulnerability by protocol") and its column is correctly reported as victim trade events ($N=3,753,918$) in Table 8 and Section 4 reports.

4. **Extreme Minimum Trade Size Artifact in `query5a`:**
   - *Description:* The minimum victim trade size reported in `query5a` is $1.24 \times 10^{-23}$ USD.
   - *Handling:* This value represents an extreme precision/pricing artifact in raw DEX swap logs (e.g., dust swaps of wei-level quantities in illiquid pools). It is reported transparently in Panel C of Table 1 with an explicit explanatory footnote.

5. **Tier Cutoff Straddling and Non-Equality with $p_{90}$:**
   - *Description:* In `query5b`, the Small tier maximum trade size (\$10,000.00) and Institutional tier minimum trade size (\$10,000.00) straddle exactly \$10,000. In `query5a`, the 90th percentile of victim trade size is $p_{90} = \$8,928.31$, confirming that the Institutional cutoff of \$10,000 does not equal $p_{90}$.
   - *Handling:* Verified via automated assertions in `m4_victims.py` and documented in `validation_report.md` and Table 4 notes.
