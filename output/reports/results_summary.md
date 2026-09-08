# Empirical Results Summary: Distributional Incidence of Sandwich-MEV on Ethereum

Primary window: **24m** (`2024-01-01 to 2025-12-31 (731 days)`). Robustness window: **30m** (loaded when data are present).

## Reproducibility and Data Vintage Controls
- Selected source folder: `revised-24m`
- Data pull date (UTC, inferred from file timestamps): `2026-08-29`
- Query IDs pinned in this run: {'query0a_data_quality': 8439243, 'query0b_router_check': 8439361, 'query1_mev_volume_v2': 6440670, 'query3_full_bot_distribution_v2': 6562142, 'query4_top_bots_v2': 6440710, 'query5a_break_points_v2': 6440810, 'query5b_victim_impact_v2': 6440827, 'query5c_repeat_victimization_v2': 8440229, 'query5d_trade_size_distribution': 8440084, 'query_protocol_vulnerability_v2': 8446953}
- Repeat-victimisation identity source: `query5c_repeat_victimization_v2` keyed on `tx_from`

## 1) Repeat-victimisation Correction (implemented)
- The repeat-victimisation hypothesis is **withdrawn** as a typical-case claim.
- Trader-level medians (non-bot `tx_from`) are Retail **1**, Small **1**, Institutional **1**.
- Trader-level means remain heterogenous: Retail **4.76**, Small **5.40**, Institutional **3.89**.
- Known-bot victims are reported separately (EOAs): Retail **684**, Small **205**, Institutional **37**.

## 2) Unique-victim Identity Correction (implemented)
- `query5b` tier counts are **tier-address observations** (non-additive), not global unique victims.
- Unique takers (`query0a`): **330,521**
- Unique `tx_from` EOAs (`query5c`): **742,330** total, of which **741,404** are non-bot trader EOAs.

## 3) Revised Core Numbers (24m primary)
- Victim events: **3,753,857**
- Victim volume: **$27.52B**
- Bot addresses: **9,917**
- Bot-side volume: **$247.52B**
- Percentiles (`query5a_v2`): p25 **$354.97**, p50 **$1,001.85**, p75 **$3,121.76**, p90 **$8,986.61**, p95 **$17,006.16**
- Tier means (`query5b_v2`): Retail **$409.84**, Small **$3,082.28**, Institutional **$58,942.39**
- Mean-size spread (Institutional/Retail): **143.82x** (window-specific, replaces static 157.9x text)
- Mechanical identity check: attacks-per-$1k ratio Retail/Institutional = **143.82x**.

## 4) Repeat-Frequency Ratio Correction (implemented)
- Small/Retail (non-bot `tx_from`): **1.1356** [1.1332, 1.1380]
- Retail/Institutional (non-bot `tx_from`): **1.2242** [1.2193, 1.2292] → **excludes 1.0 (statistically distinguishable)**

## 5) Router/Intermediation Diagnostics (implemented)
- Top-30 takers by distinct senders account for **53.85%** of victim trades.
- Interpretation control: protocol-level size patterns can partially reflect routing/intermediation structure, not only trader composition.

## 6) Trade-Size Distribution Figure Source (implemented)
- Violin geometry is generated from `query5d_trade_size_distribution` empirical bins.
- Synthetic lognormal generation is removed from the production path.

## 7) Concentration Metrics and Vintage-Sensitive Fields
- Bot-side Gini: **0.9974**
- CR1: **31.54%**, CR4: **59.50%**, CR10: **73.59%**
- Top-1% share: **98.49%**
- Vintage-sensitive metrics to track explicitly in comparisons: **CR4, CR10, top-10 share, top-1 bot share**.

## 8) Previous (Legacy) vs Revised Comparison
- Legacy victim events: **3,753,918** vs revised-24m **3,753,857**
- Legacy bot addresses: **9,749** vs revised-24m **9,917**
- Legacy p50/p90: **$1,024.44 / $8,928.31**
  vs revised-24m **$1,001.85 / $8,986.61**
- Legacy Institutional/Retail mean-size ratio: **157.95x**
  vs revised-24m **143.82x** and revised-30m **176.03x**
- Legacy Retail/Institutional RR: **0.9998** [0.9961, 1.0035]
  vs revised-24m **1.2242** [1.2193, 1.2292]
