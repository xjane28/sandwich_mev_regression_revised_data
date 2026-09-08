# README: Sandwich MEV Dataset (Ethereum 2024–2025)

This repository contains a small, self‑contained dataset used to study **sandwich attacks** in decentralized finance (DeFi) on the Ethereum blockchain over the period **2024–2025**.[file:43][file:47][file:48]

It is designed so that a researcher with **no prior knowledge of blockchains or MEV** can explore:

- How large this form of market abuse is over time.
- How concentrated extraction is across bots.
- How different DeFi protocols and victim groups are affected.

All data were generated from SQL queries on **Dune Analytics**, using their curated tables of decentralized‑exchange (DEX) trades and sandwich detections, joined with token prices and basic wallet statistics.[file:43][file:45][file:47][file:48]

---

## 1. Background: What Is in This Data?

### 1.1 Sandwich Attacks (High‑Level)

In a **sandwich attack**, an automated trading bot detects a user’s pending swap on a DEX (for example, swapping token A for token B) and inserts **two trades around it** in the same block:

1. A **front‑run trade** that moves the price against the victim.
2. The victim’s original trade.
3. A **back‑run trade** that closes the bot’s position at a profit.

The bot profits from the artificial price movement; the victim receives a worse execution price than if the bot had not intervened.[file:43][file:47][file:48]

In this dataset:

- A **“sandwich trade”** is a trade executed by the attacking bot as part of such a sequence.
- A **“victim”** is a user address whose trade has been sandwiched.
- All monetary values are reported in **US dollars at the time of the trade**, based on on‑chain price feeds.[file:43][file:45][file:47][file:48]

---

## 2. Files Overview

The dataset consists of six CSV files:

1. `query1_mev_volume.csv` – **Daily time series** of sandwich activity on Ethereum.[file:43]
2. `query3_full_bot_distribution.csv` – **Per‑bot totals** of sandwich volume, used for Lorenz curves and Gini concentration analysis.[file:47]
3. `query4_top_bots.csv` – **Enriched profile** of the largest bots (activity span, average trade size, etc.).[file:44]
4. `query_protocol_vulnerability.csv` – Protocol‑level summary: how much volume is sandwiched on each DEX (Uniswap, Curve, etc.).[file:45]
5. `query5a_break_points.csv` – Global distribution of victim trade sizes and **percentile breakpoints** used to define retail/small/institutional tiers.[file:46]
6. `query5b_victim_impact.csv` – Tier‑level victim statistics (trade sizes, counts, volumes, and attack frequency).[file:48]

The naming reflects the original query numbering in the analysis workflow.

---

## 3. Data Sources and Generation

### 3.1 Upstream Data (Dune Analytics)

All CSVs are exported from **Dune Analytics** queries on Ethereum’s DeFi data.[file:43][file:45][file:47][file:48]

At a high level:

- Sandwich detections rely on Dune’s curated tables of sandwich attacks built from DEX swap data and mempool/transaction ordering, e.g. **DEX trade tables plus a “sandwiches” view**.[file:43][file:45][file:47][file:48]
- USD values (`*_usd` columns) are obtained by joining trades with Dune’s token price feeds at the appropriate block timestamp.[file:43][file:45][file:47][file:48]
- Victim and bot identifiers are **Ethereum addresses** (hex strings starting with `0x`).[file:47][file:44][file:48]

No manual data entry was performed; all files are direct exports from these SQL queries, with light aggregation or grouping in SQL only (no further processing in Excel/R/Python).

---

## 4. File‑by‑File Documentation

### 4.1 `query1_mev_volume.csv`: Daily Sandwich MEV Time Series

**Purpose**

Provides a **daily time series** of sandwich activity on Ethereum, used to measure the total scale of MEV extraction and its evolution over time.[file:43]

**Granularity**

- One row per **calendar day**.
- Coverage: continuous days from `2024‑01‑01` through the end of 2025 (the snippet shows January–February 2024).[file:43]

**Columns**

1. `date` (string, UTC timestamp)
    - Start of the day (`YYYY‑MM‑DD hh:mm:ss.sss UTC`).[file:43]
    - Example: `"2024-01-01 00:00:00.000 UTC"`.[file:43]

2. `sandwich_trade_count` (integer)
    - Number of **bot trades** identified as part of sandwich attacks that day.[file:43]
    - Counts the bot’s trades, not victim trades.

3. `total_sandwich_volume_usd` (float)
    - **USD notional volume** of all sandwich bot trades that day.[file:43]
    - Computed as trade size in tokens × token USD price at execution.[file:43]

4. `unique_sandwich_bots` (integer)
    - Number of **distinct bot addresses** that executed at least one sandwich trade on that day.[file:43]

5. `unique_transactions` (integer)
    - Number of unique **transactions** (Tx hashes) associated with sandwich trades that day.[file:43]

**How it was generated**

- Query selects from Dune’s sandwich‑detection tables, groups by `date_trunc('day', block_time)` and aggregates counts and USD volume.[file:43]
- USD values come from Dune’s price tables at the minute or block level.[file:43]

**Typical uses**

- Plotting time‑series of MEV extraction.
- Computing annualized extraction, daily averages, volatility, and regime shifts.

---

### 4.2 `query3_full_bot_distribution.csv`: Per‑Bot Volume Distribution

**Purpose**

Provides a **full distribution of sandwich volume by bot address**, used for concentration analysis (Lorenz curve, Gini coefficient, CR4, top‑N shares).[file:47]

**Granularity**

- One row per **bot address** that executed at least one sandwich trade during 2024–2025.[file:47]

**Columns**

1. `bot_address` (string)
    - Ethereum address of the **searcher/bot** executing sandwich trades.[file:47]
    - Hex string like `0x1f2f10d1c40777ae1da742455c65828ff36df387`.[file:47]

2. `total_volume_usd` (float)
    - Total USD volume of all sandwich trades executed by this bot over the sample period.[file:47]
    - Sum over all trades attributed to this bot, using execution‑time USD prices.[file:47]

**How it was generated**

- Dune query: group sandwich‑detection table by `bot_address`, summing trade‑level USD volume over the full period.[file:47]
- No additional filtering: this file includes both very large and tiny bots.[file:47]

**Typical uses**

- Sorting bots by `total_volume_usd` to obtain cumulative shares.
- Computing **Gini coefficient** and preparing Lorenz curve data.
- Identifying top‑N bots for deeper profiling (see `query4_top_bots.csv`).[file:47][file:44]

---

### 4.3 `query4_top_bots.csv`: Detailed Profiles of Top Bots

**Purpose**

Contains **enriched metadata** for the largest sandwich bots by volume, including their activity span and average trade size.[file:44]

**Granularity**

- One row per **top bot** (e.g. top 100 or top X% by total volume; exact cutoff depends on the original query).[file:44]

**Columns**

1. `avg_trade_size_usd` (float)
    - Average USD size of the bot’s sandwich trades over the sample period.[file:44]

2. `bot_address` (string)
    - Ethereum address of the bot, consistent with `query3_full_bot_distribution.csv`.[file:44][file:47]

3. `days_active` (integer)
    - Number of **distinct days** on which this bot executed at least one sandwich trade.[file:44]

4. `first_seen` (string, UTC timestamp)
    - Block timestamp of the **first observed sandwich trade** by this bot.[file:44]

5. `last_seen` (string, UTC timestamp)
    - Block timestamp of the **last observed sandwich trade** by this bot within the sample window.[file:44]

6. `total_sandwich_trades` (integer)
    - Number of individual sandwich bot trades attributed to this address.[file:44]

7. `total_volume_usd` (float)
    - Total USD sandwich volume executed by this bot (should match the value from `query3_full_bot_distribution.csv` for the same address).[file:44][file:47]

**How it was generated**

- Starts from the same per‑trade sandwich table as `query3_full_bot_distribution.csv` but:
    - Restricts to the **largest bots** (e.g. by ranking on total volume).[file:44][file:47]
    - Aggregates additional statistics: count of trades, distinct active days, and first/last timestamps.[file:44]

**Typical uses**

- Characterizing the “elite” MEV bots (activity duration, intensity, trade size).
- Investigating whether top bots are long‑lived, bursty, or appear in specific sub‑periods.

---

### 4.4 `query_protocol_vulnerability.csv`: Protocol‑Level Exposure

**Purpose**

Summarizes sandwich activity **by DeFi protocol / DEX**, allowing comparison of how vulnerable each trading venue is to sandwich attacks.[file:45]

**Granularity**

- One row per **DEX protocol** (e.g. Uniswap, Curve, Balancer). Each name in `project` corresponds to a protocol identifier used in Dune’s DEX tables.[file:45]

**Columns**

1. `avg_trade_size` (float)
    - Mean USD size of sandwich trades on this protocol.[file:45]

2. `project` (string)
    - Protocol or DEX name (e.g. `uniswap`, `curve`, `balancer`).[file:45]

3. `sandwich_count` (integer)
    - Total number of sandwich bot trades executed on this protocol.[file:45]

4. `total_volume_usd` (float)
    - Total USD sandwich volume on this protocol.[file:45]

5. `unique_victims` (integer)
    - Number of distinct **victim addresses** that were sandwiched on this protocol.[file:45]

**How it was generated**

- Joins sandwich‑detection data with DEX metadata to assign each trade to a `project` (protocol).[file:45]
- Groups by `project` and aggregates:
    - Count of sandwich trades.
    - Distinct victim addresses.
    - Total and average USD volume.[file:45]

**Typical uses**

- Ranking DEXs by total sandwich volume or victim count.
- Normalizing by each protocol’s overall trading volume (from external data) to compute a “sandwich risk rate”.

---

### 4.5 `query5a_break_points.csv`: Trade‑Size Distribution and Tier Cutoffs

**Purpose**

Provides global **distribution statistics for victim trade sizes**, including the percentile cutoffs used to define **retail**, **small**, and **institutional** tiers.[file:46][file:48]

**Granularity**

- Single summary row describing the distribution of **trade sizes for sandwiched victim trades**, in USD.[file:46]

**Columns**

1. `max_value` (float)
    - Maximum observed victim trade size (USD).[file:46]

2. `mean_value` (float)
    - Mean victim trade size across all sandwiched trades.[file:46]

3. `min_value` (float)
    - Minimum observed victim trade size (USD); can be very close to zero.[file:46]

4. `p25` (float)
    - 25th percentile of victim trade size (USD).[file:46]

5. `p50_median` (float)
    - 50th percentile / median victim trade size (USD).[file:46]

6. `p75` (float)
    - 75th percentile of victim trade size (USD).[file:46]

7. `p90` (float)
    - 90th percentile victim trade size (USD).[file:46]

8. `p95` (float)
    - 95th percentile victim trade size (USD).[file:46]

9. `total_victims` (integer)
    - Total number of **unique victim addresses** observed in the dataset.[file:46]

**Tier definitions used elsewhere**

These percentiles are used to define victim classes in `query5b_victim_impact.csv`:

- **Retail:** victims with typical trade size **below the median** (`< p50_median`).[file:46][file:48]
- **Small:** between the median and the 90th percentile (`p50_median ≤ trade size < p90`).[file:46][file:48]
- **Institutional:** at or above the 90th percentile (`≥ p90`).[file:46][file:48]

(Exact classification implementation may vary, but this is the conceptual mapping.)

**How it was generated**

- Dune query over all sandwiched victim trades:
    - Converts trade size to USD.
    - Computes distribution statistics using percentile functions.[file:46]
- Unique victims are counted at the address level.[file:46]

**Typical uses**

- Describing the overall victim universe.
- Justifying the choice of tier cutoffs in an academic paper.
- Building violin plots / histograms of trade sizes.

---

### 4.6 `query5b_victim_impact.csv`: Tier‑Level Victim Statistics

**Purpose**

Aggregates victim statistics by **trade‑size tier** (Retail / Small / Institutional), showing how losses and attack frequency differ across groups.[file:48]

**Granularity**

- One row per **victim tier**, as defined by `query5a_break_points.csv` (see above).[file:46][file:48]

**Columns**

1. `avg_tx_size` (float)
    - Average USD size of sandwiched trades for victims in this tier.[file:48]

2. `max_tx` (float)
    - Maximum sandwiched trade size (USD) observed in this tier.[file:48]

3. `min_tx` (float)
    - Minimum sandwiched trade size (USD) observed in this tier.[file:48]

4. `pct_of_victims` (float, percentage)
    - Share of **all unique victims** belonging to this tier (0–100).[file:48]

5. `pct_of_volume` (float, percentage)
    - Share of **total victim trading volume** (USD) associated with this tier.[file:48]

6. `total_volume` (float)
    - Total USD volume of sandwiched trades executed by victims in this tier.[file:48]

7. `unique_victims` (integer)
    - Number of distinct victim addresses in this tier.[file:48]

8. `victim_count` (integer)
    - Total number of **sandwich events** (victim trades that were sandwiched) affecting this tier.[file:48]
    - Used together with `unique_victims` to compute attacks per victim.

9. `victim_tier` (string)
    - Tier label: `"Retail"`, `"Small"`, or `"Institutional"`.[file:48]

**How it was generated**

- Starts from trade‑level victim data with trade size in USD and victim address.[file:48]
- Uses the percentile thresholds in `query5a_break_points.csv` to assign each victim (or trade) to a tier.[file:46][file:48]
- For each tier, aggregates:
    - Average, min, max trade size.
    - Total volume.
    - Count of unique victims and victim trades.
    - Shares of overall victims and volume.[file:48]

**Derived metrics (not stored but commonly used)**

From this file you can easily compute:

- **Attacks per victim** = `victim_count / unique_victims` (frequency).[file:48]
- **Estimated loss per attack** assuming 1% slippage = `avg_tx_size × 0.01`.[file:48]
- **Total estimated loss per victim** = `(total_volume / unique_victims) × 0.01`.[file:48]
- **Attack intensity per $1,000 traded** = `(victim_count / total_volume) × 1000`.[file:48]

These derived metrics are used for the multi‑panel figures and “middle‑class squeeze” analysis.

**Typical uses**

- Comparing how often different victim groups are sandwiched.
- Measuring how much volume and wealth transfer each group accounts for.
- Constructing Lorenz‑style or bar‑chart visualizations across tiers.

---

## 5. Common Conventions and Units

- **Currency:** All monetary figures are in **USD**, evaluated at trade time using Dune’s price feeds.[file:43][file:45][file:47][file:48]
- **Time zone:** All timestamps are in **UTC**.[file:43][file:44]
- **Addresses:** Ethereum addresses are **pseudonymous IDs** and are not linked to real‑world identities in this dataset.[file:44][file:47][file:48]
- **Period:** Data span 2024–2025 (inclusive), though some files show only partial snippets above; the underlying CSVs cover the full analysis window.[file:43][file:44][file:47][file:48]

---

## 6. How to Start Using the Dataset

### 6.1 Minimal Examples

- **Plot daily MEV volume**  
  Load `query1_mev_volume.csv` and plot `total_sandwich_volume_usd` over `date` to see time variation in aggregate extraction.[file:43]

- **Reproduce concentration metrics**  
  Load `query3_full_bot_distribution.csv`, sort by `total_volume_usd`, and compute cumulative sums to create a Lorenz curve and Gini coefficient.[file:47]

- **Study protocol vulnerability**  
  Load `query_protocol_vulnerability.csv`, sort by `total_volume_usd` or `unique_victims` to see which DEXs attract the most sandwiching.[file:45]

- **Analyze distributional impact**  
  Use `query5b_victim_impact.csv` to compare attacks per victim and volume shares across Retail/Small/Institutional tiers.[file:48]

### 6.2 Suggested Load Pattern (Pseudocode)

In R / Python / Stata or similar, treat each CSV as a separate table and join on keys when needed:

- Join **bots** (`query3_full_bot_distribution.csv`) with **top bot profiles** (`query4_top_bots.csv`) via `bot_address`.[file:47][file:44]
- Use **tier cutoffs** from `query5a_break_points.csv` only as parameters; `query5b_victim_impact.csv` is already tiered.[file:46][file:48]
- Keep `query1_mev_volume.csv` and `query_protocol_vulnerability.csv` as separate time‑series and cross‑sectional summaries, respectively.[file:43][file:45]

---

## 7. Limitations and Caveats

- **Detection coverage:** The dataset relies on Dune’s sandwich‑detection heuristics. Sophisticated or multi‑block sandwiches may be **missed**, making all volume figures lower bounds.[file:43][file:47]
- **Price accuracy:** USD valuations depend on price feed quality and may be noisy around illiquid tokens or during high volatility.[file:43][file:45]
- **Address aggregation:** A single economic actor can control multiple addresses. Bot and victim counts therefore measure **addresses**, not legal entities.[file:44][file:47][file:48]
- **Tier definition:** Retail/Small/Institutional tiers are based purely on **observed trade sizes**, not on identity or wealth; a single address can change behaviour over time.[file:46][file:48]
- **No non‑victim trades:** These files focus on trades **that were sandwiched**; they do not contain the broader universe of all trades on Ethereum.

---

## 8. Citation Suggestion

If you use this dataset in academic work, you might cite it along the lines of:

> “We use a custom dataset of Ethereum sandwich attacks constructed from Dune Analytics, summarizing 3.75 million sandwiched victim trades and 7.2 million sandwich bot trades between 2024 and 2025. The dataset includes daily aggregate series, per‑bot volumes, protocol‑level exposure, and victim tier statistics (see README for details).”[file:43][file:47][file:45][file:48]
