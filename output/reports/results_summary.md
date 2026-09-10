# Empirical Results Summary: Distributional Incidence of Sandwich-MEV on Ethereum (2024–2025)

This report provides the synthesized empirical findings of the Sandwich-MEV quantitative analysis pipeline, evaluated across five core hypotheses ($H_1$--$H_5$) using daily and cross-sectional data exported from Dune Analytics.

---

## 1. Searcher Concentration and Market Structure ($H_1$)

### Key Empirical Findings
- **Extreme Gini Inequality:** Across the $B_{\text{meas}}$ sample ($N = 9,632$ bot addresses with non-missing volume), searcher trading volume exhibits an extreme Gini coefficient of **0.9976** (95% bootstrap CI: $[0.9974, 0.9978]$).
- **Winner-Take-Most Concentration Ratios:** The single largest searcher bot address account for **25.09%** of all searcher volume (CR1), while the top 4 bots control **65.70%** (CR4), the top 10 control **76.81%** (CR10), and the top 20 control **84.59%** (CR20). The top 1% of bot addresses ($k = 97$) capture **98.51%** of total notional volume, and the top 10% capture **99.97%**.
- **Herfindahl-Hirschman Index:** The HHI across searcher bot addresses stands at **1,236.5** (on a 0--10,000 scale), indicating a highly concentrated market structure.
- **Heavy-Tailed Pareto Distribution:** On the strictly positive volume sample ($B_{\text{pos}}$, $N = 9,630$), tail exponent estimation confirms an infinite-mean regime. The Hill estimator for the top 5% tail yields $\hat{\alpha} = 0.3438$ (SE: $0.0157$), while the Gabaix-Ibragimov rank-size regression on the top 500 bots estimates an OLS power-law slope of $\hat{\zeta} = 0.3758$ (SE: $0.0238$). Both $\hat{\alpha} < 1$ and $\hat{\zeta} < 1$ demonstrate an extreme Pareto upper tail significantly heavier than Zipf's law ($\alpha = 1$), confirming winner-take-most dynamics in MEV extraction.

### Methodological Caveat: Address vs. Entity Concentration
*Sybil Caveat:* Ethereum on-chain addresses do not map one-to-one with economic entities. A single searcher operator or algorithmic trading firm may deploy multiple bot addresses (Sybil addresses) for operational security or routing efficiency, or conversely, independent searcher algorithms may route trades through a shared settlement contract. Therefore, economic entity-level concentration is not formally identified by address-level data, and the direction of bias is theoretically ambiguous.

---

## 2. Victim-Side Incidence and Repeat Victimization ($H_2$ & $H_5$)

### Key Empirical Findings
- **Inverted-U Non-Monotonic Victimization:** Repeat victimization per unique victim address does **not** decrease monotonically with trade size. In the **Small** tier (\$418.83 to \$10,000.00), traders suffer an average of **10.20** attacks per unique address. By contrast, traders in the **Retail** tier (< \$418.83) suffer **8.46** attacks per address, and traders in the **Institutional** tier (>= \$10,000.00) suffer **8.46** attacks per address.
- **Formal Poisson Rate Ratios:** Formal inference under a Poisson exposure model confirms that the Small tier attack frequency is **20.6% above** the Retail tier, with a Rate Ratio of **1.2057** (95% CI: $[1.2032, 1.2083]$). Similarly, the Small tier experiences 20.6% higher attack frequency than the Institutional tier.
- **Indistinguishability of Extreme Tiers:** The Rate Ratio comparing Retail to Institutional attack frequency is **0.9998** (95% CI: $[0.9961, 1.0035]$). Because this confidence interval strictly includes 1.0, attack frequency per unique address between Retail and Institutional traders is statistically indistinguishable.
- **Economic Refinement:** This inverted-U finding refutes a simple "more attacks for the smallest traders" narrative and provides rigorous empirical support for a "middle-tier squeeze", where mid-sized DEX traders experience the highest frequency of repeat extraction.

### Mechanical-Identity Audit: Attacks per \$1,000 Traded
*Mandatory Methodological Caveat:* In any trade-size tier, the metric $\text{Attacks per \$1,000 Traded}$ is computed as $(\text{Victim Trades} / \text{Total Volume}) \times 1,000$. Because $\text{Total Volume} = \text{Victim Trades} \times \text{Avg Tx Size}$, this ratio simplifies algebraically to:
$$\text{Attacks per \$1,000 Traded} \equiv \frac{1,000}{\text{Avg Tx Size}}$$
Consequently, the apparent 157.94-fold discrepancy between Retail attacks per \$1,000 traded (2.39) and Institutional attacks per \$1,000 traded (0.0151) is **algebraically identical** to the Institutional-to-Retail ratio of average trade sizes (\$66,152.13 / \$418.83 = 157.94x). This metric contains no empirical information beyond the average trade size spread and must not be interpreted as independent evidence of differential vulnerability.

### Loss-Model Sensitivity & Identification Limitations
*Regressivity Identification Caveat:* Whether MEV extraction constitutes a "regressive tax" per dollar traded is fundamentally unidentified in pre-aggregated DEX data. Calibrating three alternative loss-scaling models to an identical aggregate loss anchor of 1% of total victim volume (\$274.70M) demonstrates that regressivity depends entirely on unobserved micro-level scaling:
1. **Proportional Model:** If loss scales linearly with trade size (1% flat), extraction is strictly proportional (100 basis points across all tiers).
2. **Constant per Attack Model:** If every attack extracts a constant dollar amount (\$73.18/attack), extraction is hyper-regressive, imposing ~1,747 bps on Retail versus ~11 bps on Institutional traders (a >= 150x spread).
3. **Square-Root Impact Model:** If loss scales with the square root of trade size, extraction exhibits mild regressivity.
Because realized slippage and per-trade extraction amounts are unobserved in the export, the data pin down attack frequencies and volume distributions, but not welfare loss rates.

---

## 3. Time-Series Persistence, Seasonality, and Structural Shifts ($H_3$)

### Key Empirical Findings
- **High Autocorrelation and Stationarity:** Log daily searcher volume ($y_t = \ln V_t$, $N = 731$ days) exhibits strong first-order autocorrelation ($AR(1) \approx 0.782$ and $AR(7) \approx 0.443$). Augmented Dickey-Fuller (ADF) testing rejects the unit root null in favor of trend-stationarity at $p < 0.001$, while KPSS testing confirms stationarity around a deterministic trend.
- **Secular Trend Growth:** Baseline OLS regression with Newey-West HAC standard errors (7 lags) estimates a statistically significant linear trend of $\beta = 0.001214$ ($p < 0.001$), corresponding to an average daily volume growth rate of **+0.121% per day** (~56% annualized growth in log volume).
- **Weekly Seasonality:** Searcher activity exhibits pronounced weekly seasonality. Mean daily volume during weekdays (Monday--Friday) averages **\$377.30M**, falling by **28.48%** during weekends (Saturday--Sunday) to an average of **\$269.85M**.
- **Dynamic Searcher Consolidation:** Comparing calendar year 2024 to 2025 in `query1`, mean daily active searcher bot addresses fell from **217.7 bots/day** in 2024 to **127.0 bots/day** in 2025 (a **-41.67% decline**). Simultaneously, mean daily searcher volume rose by **+78.69%**. This massive increase in volume per active bot provides powerful time-series confirmation of dynamic concentration under $H_1$.
- **Volume Regimes and Volatility:** Complementing the project's existing finding that sandwich-bot volume increased despite declining bot and trade counts, PELT changepoint detection identifies four endogenous structural shifts on 30 March, 10 July, 29 August, and 17 October 2025, partitioning the sample into five distinct volume regimes. The most pronounced high-volume regime occurred from 10 July to 28 August 2025, when average daily volume reached approximately $913.8M, compared with $362.9M in the preceding regime. Rolling volatility measures further indicate that relative and proportional volatility increased during the transition into this high-volume regime but subsequently declined while volume remained exceptionally high, suggesting that the August surge represented a sustained high-activity period rather than merely a sequence of isolated volume spikes.
- **Structural Shifts Around Upgrades:** Interrupted Time Series (ITS) regressions confirm significant joint step and slope shifts around the Dencun (2024-03-13) and Pectra (2025-05-07) network upgrades (Wald F-test $p < 0.001$). However, raw event-window post/pre volume ratios (Dencun: 1.19x, Pectra: 1.35x) are heavily confounded by underlying trend growth when compared against a 200-replication placebo distribution.
- **Methodological Note on Chow Tests:** Because daily volume violates the iid error assumption required by classical Chow tests ($AR(1) \approx 0.78$), known-date Chow F-statistics are reported descriptively. Primary formal inference relies on HAC-robust ITS Wald tests and Quandt-Andrews unknown-date scans evaluated via a 999-replication circular moving-block bootstrap (block length 14 days).
  

---

## 4. Protocol Vulnerability and DEX Concentration ($H_4$)

### Key Empirical Findings
- **Protocol Volume Dominance:** Across the 3,753,918 victim trade events in `query_protocol_vulnerability.csv`, sandwich volume is heavily concentrated in automated market makers (AMMs). **Uniswap v2** accounts for **\$13.43B** (48.87% of victim volume) and **Uniswap v3** accounts for **\$11.08B** (40.35%), yielding a combined four-firm concentration ratio (CR2) of **89.22%**.
- **Protocol HHI:** The Herfindahl-Hirschman Index across the six monitored routing protocols is **4,057.1**, indicating an extremely concentrated market structure.
- **Identification Caveat on Protocol Security:** While $H_4$ is supported in terms of raw volume concentration in AMMs, this dominance does **not** identify inherent differences in protocol security design or smart contract vulnerability. Uniswap v2 and v3 account for the vast majority of all decentralized exchange trading volume on Ethereum; therefore, their dominance in sandwich volume mechanically reflects their underlying market share. A rigorous test of protocol-specific vulnerability would require normalizing sandwich volume by total DEX routing volume per protocol, which is unobserved in this dataset.

---

## 5. Cross-Base Reconciliation & Synthesis ($H_5$)

### Measurement Base Reconciliation
The Dune Analytics export contains two disjoint measurement bases that must never be mixed without explicit labeling:
1. **Bot-Side Base (`query3` / `query4`):** Measures searcher attacker trade legs ($N = 9,749$ bot addresses, 7,205,568 trade legs, **\$247.32B** total notional volume).
2. **Victim-Side Base (`query5a` / `query5b` / `protocol`):** Measures sandwiched victim swap events ($N = 413,129$ unique victim addresses, 3,753,918 attack events, **\$27.47B** total volume).

### Explanation of Divergence (9.00x Volume Ratio)
Searcher bot notional volume exceeds victim notional volume by exactly **9.00x** (\$247.32B vs \$27.47B), and searcher trade legs exceed victim attack events by **1.92x** (7.21M vs 3.75M). This divergence is not a data error; it reflects the mechanics of MEV execution on Ethereum:
- A single sandwiched victim trade event (1 leg on the victim side) requires at least two searcher trade legs (a front-run leg and a back-run leg).
- In multi-hop routing or multi-pool arbitrage execution, an MEV bot may execute across several DEX liquidity pools simultaneously to capture price discrepancies created by the victim swap. The bot-side base aggregates the sum of all front-run, back-run, and intermediate routing leg volumes across all pools, whereas the victim base records only the single sandwiched swap.

### Final Distributional Synthesis
The empirical evidence presents a cohesive structure of Ethereum sandwich MEV in 2024--2025:
1. **Extraction Side:** A hyper-concentrated, winner-take-most searcher oligopoly (Gini 0.9976, top-1% share 98.51%, infinite-mean Pareto tail $\hat{\zeta} = 0.376$) that has consolidated dynamically over time (active bots down 41.7%, volume up 78.7%).
2. **Victim Side:** An inverted-U incidence structure where mid-sized DEX traders (Small tier, \$418--\$10k) suffer the highest frequency of repeat victimization (10.20 attacks/address), refuting monotonic regressivity claims in attack frequency.
3. **Welfare Impact:** While attack frequency peaks in the middle tier, whether welfare losses are regressive per dollar traded remains empirically unidentified without micro-level slippage data, highlighting a critical boundary for empirical MEV research.
