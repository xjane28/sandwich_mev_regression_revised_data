# SQL Provenance and Revision Layer

Recovered 2026-08 from the original 2026-01 analysis transcript. Before this, the
repository contained six CSVs with no SQL at all — which is how a hand-copied tier
cutoff drifted from `p90 = $8,928.31` to a hardcoded `$10,000` without anyone noticing
for eight months. This directory exists so that cannot recur.

## Layout

- `*.sql` (this directory): **provenance records**. Byte-exact SQL that produced the
  identically-named CSV in `fetch/`, verified against the delivered data. Known defects
  are ANNOTATED in each header (`D1…Dn`), never silently repaired — the delivered CSVs
  and the `src/` pipeline anchor on these exact outputs. **Edit the comments if they are
  wrong; never edit an SQL body.**
- `revised/*.sql`: **corrected queries** for the paper revision. Self-contained — no
  query needs a number hand-copied from another. Every remaining literal carries a
  derivation comment. Exports use NEW filenames so nothing in `src/` breaks.

## Re-run sequence (Dune, engine: Trino; session time zone UTC)

| # | query | purpose / acceptance check |
|---|-------|-----------------------------|
| 1 | `revised/query0a_data_quality.sql` | sizes what `amount_usd > 0`, NULL prices, dust and NULL takers exclude, on both bases; yields the **single global unique-victim count** the paper currently lacks. Read off `sandwiched_rows_all` = 3,753,918. Key on the `metric` column, not row order |
| 2 | `revised/query0b_router_check.sql` | top takers by trade count, by volume, and by large-trade count. If these are router/aggregator CONTRACTS, every per-address statistic (step 5) needs reinterpretation. **Gate for step 5** |
| 3 | `revised/query5a_break_points_v2.sql` | exact order statistics. Expect exact p50 slightly **below** the delivered approx `1,024.44` (that approx value sat at the ~50.76th percentile) and exact p90 near the delivered approx `8,928.31` |
| 4 | `revised/query5b_victim_impact_v2.sql` | percentile-spec tiers (trade level). `cutoff_p50`/`cutoff_p90` must **equal** step 3's `p50_median`/`p90` — run back-to-back |
| 5 | `revised/query5c_repeat_victimization_v2.sql` | address-level tiers keyed on the **sending EOA** (`tx_from`), with searcher-linked addresses flagged. Σ`attack_events` must equal step 4's Σ`victim_trades`; cutoffs must match steps 3–4. Σ`unique_eoas` should substantially EXCEED the taker-based 330,521 |
| 6 | `revised/query5d_trade_size_distribution.sql` | 100 equal-mass bins per tier — the real distribution behind the violin figure, which is currently drawn from synthetic lognormal draws. Σ`trades_in_bin` per tier must equal step 4's `victim_trades` |
| 7 | `revised/query_protocol_vulnerability_v2.sql` | expect 20 rows; counts identical to delivered, volumes to float noise |
| 8 | `revised/query1_mev_volume_v2.sql` | expect 731 rows, no missing days; Σcount = 7,205,568 exact; Σvolume = 247,322,343,792.92 ± 0.01 |
| 9 | `revised/query3_full_bot_distribution_v2.sql` | expect 9,749 rows, 9,632 with non-NULL volume; top bot 62,055,408,756.59 ± noise |
| 10 | `revised/query4_top_bots_v2.sql` | expect 9,749 rows; count aggregates exact, volume/avg to float noise |

Steps 7–10 are **regression tests** as much as data pulls: equality with the delivered
CSVs falsifies the residual risk that `AT TIME ZONE 'GMT'` shifted the sample window in
the original runs. Any count inequality is a finding — stop and investigate.

**Robustness variant:** the delivered `$1,024.44 / $10,000` tiers (legacy
`query5b_victim_impact.sql` → `fetch/query5b_victim_impact.csv`) are retained as the
paper's robustness specification against the percentile spec in step 4. No rerun needed.

## Conventions

- **Quantiles** are type-1 (lower empirical): `Q(p)` = value at rank `ceil(p·n)`.
  Identical in every revised file, so cutoffs are comparable across them. Bounds are
  closed below — write tiers as `[p50, p90)` and `[p90, ∞)`, never `>P90`.
- **Reproducibility:** count / min / max / percentile / cutoff columns are exactly
  reproducible. `SUM`/`AVG` over `DOUBLE` are addition-order dependent in a distributed
  engine — compare with a relative tolerance (1e-12 is ample), never byte-for-byte.
- **Window:** `revised/*.sql` currently target the paper's **24-month sample,
  2024-01-01 to 2026-01-01 exclusive (731 days)**. Both windows have been run in full:
  24-month results in `fetch/data/revised-24m/`, 30-month
  (to 2026-07-01, 912 days) in `fetch/data/revised-30m/`. Switching window is a
  two-line edit of the commented literals at the top of each query — the cutoffs
  re-derive themselves, so nothing else needs touching.
- **Export** each revised query as its filename with `.csv`, into the dated folder for
  its window. Do not overwrite anything in `fetch/`.
- **Pulling results:** `curl -H "x-dune-api-key: $DUNE_API_KEY" \
  "https://api.dune.com/api/v1/query/<ID>/results/csv?limit=1000"`.
  Known IDs: query0a = 8439243, query0b = 8439361.

## Known-defect index

Full detail in each SQL header; cross-referenced to `output/reports/validation_report.md`.

| defect | affects | fixed by |
|---|---|---|
| `$10,000` tier cutoff is an ad hoc constant, not `p90` | query5b | `revised/query5b_victim_impact_v2.sql` |
| `APPROX_PERCENTILE` reported to 17 sig figs; its p50 sat at the ~50.76th pct | query5a | `revised/query5a_break_points_v2.sql` |
| per-group `COUNT(DISTINCT taker)` is non-additive (413,129 by tier vs 364,713 by protocol) | query5b, protocol | `revised/query5c_repeat_victimization.sql`, `query0a` |
| `total_victims` / `pct_of_victims` / `sandwich_count` count TRADES, not victims | query5a, query5b, protocol | renamed throughout `revised/` |
| `AT TIME ZONE 'GMT'` on the partition key | all six | dropped throughout `revised/` |
| `COUNT(*)` and `SUM(amount_usd)` on different bases within a row | query1, query3, query4 | `priced_trades` column added in `revised/` |
| violin figure drawn from synthetic lognormal draws, unseeded | `process_trade_size_distribution.py` | `revised/query5d_trade_size_distribution.sql` |
| `taker` is a router contract, not an end user, for 53.9% of victim trades | all victim-side | **CONFIRMED 2026-08-25** by `query0b`; fixed by keying on `tx_from` in `revised/query5c_repeat_victimization_v2.sql` |
| sandwich bots appear as victims (e.g. the #1 bot: 15,287 victim trades, $660M) | all victim-side | flagged via `is_known_bot` in `revised/query5c_repeat_victimization_v2.sql` |

## Measured so far — **24-month window** (`fetch/data/revised-24m/`)

> The queries in `revised/` currently target this window, so these are the live anchors.
> The 30-month equivalents are in `fetch/data/revised-30m/` and are **larger**
> throughout — never compare an output from one window against the other's anchors.

| finding | value |
|---|---|
| true unique **taker** count | **330,521** — vs 413,129 summed by tier and 364,713 by protocol; the paper's figure overstates by 25.0% |
| but `taker` is a router for | **53.9%** of victim trades (30 addresses, ≥1,000 distinct senders each) |
| largest single router | Uniswap Universal Router: 882,844 trades from **186,190** senders = 23.5% of all victim trades |
| `amount_usd > 0` drops | 2,284 of 3,756,141 rows (**0.061%**) — immaterial |
| dust < $1 | 4,021 trades, $1,512.84 total; moves Retail mean $418.83 → $419.72 (**+0.21%**) — immaterial |
| NULL takers | **0** |
| drift vs Jan-2026 | −61 victim trades, −62 bot legs (0.002%) — far too small for a timezone shift, so `AT TIME ZONE 'GMT'` was a no-op and the delivered window was correct |

### Exact percentiles (`query5a_break_points_v2`, Dune 6440810) — supersede the delivered approximations

| stat | **exact** | delivered `APPROX_PERCENTILE` | approx error |
|---|---|---|---|
| p25 | **$354.97** | $370.68 | **+4.43%** |
| p50 | **$1,001.85** | $1,024.44 | **+2.25%** |
| p75 | **$3,121.76** | $3,182.88 | +1.96% |
| p90 | **$8,986.61** | $8,928.31 | −0.65% |
| p95 | **$17,006.16** | $17,351.61 | +2.03% |
| mean | **$7,332.08** | $7,317.81 | — |

`APPROX_PERCENTILE` error is neither small nor uniformly signed — up to 4.43% at p25,
and it flips direction at p90. Every percentile quoted to the cent in the draft is wrong.
`total_victim_trades` = 3,753,857 and `unique_victim_addresses` = 330,521 both reconcile
exactly with `query0a`.

### Tier results under the exact percentile spec (`query5b_victim_impact_v2`, Dune 6440827)

All 13 acceptance checks pass; `cutoff_p50`/`cutoff_p90` match `query5a_v2` bit-for-bit.

| tier | trades | share | delivered share | avg trade | delivered avg |
|---|---|---|---|---|---|
| Retail | 1,876,928 | **50.0000%** | 50.7567% | **$409.84** | $418.83 |
| Small | 1,501,543 | **40.0000%** | 40.5433% | **$3,082.28** | $3,329.75 |
| Institutional | 375,386 | **10.0000%** | 8.7000% | **$58,942.39** | $66,152.13 |

Institutional gains +48,795 trades (the $8,987–$10,000 band) so its share becomes a true
top decile, and its mean trade size *falls* because that band is its cheapest cohort.

**Consequence for the draft: the "157.9× spread" headline becomes 143.8× (−8.9%).**
Quoted in the `fig:trade-size-distribution` caption and twice in `results_summary.md`.

Non-additivity persists under the correct cutoffs: per-tier address counts sum to
391,729 against 330,521 true unique takers, so ≥30,604 takers (9.3%) still span more
than one tier. The defect is structural, not a cutoff artifact — it cannot be fixed by
re-cutting, only by changing the estimand (`query5c_repeat_victimization_v2`).

### Real trade-size distribution (`query5d_trade_size_distribution`, Dune 8440084)

300 rows, all 18 acceptance checks pass; bins reconcile to 5b_v2 tier totals and volumes
exactly, cutoffs bit-exact. Internal cross-check holds: Retail's within-tier median equals
the global p25 ($354.97) and Institutional's equals the global p95 ($17,006.16), as they
must by construction.

**The synthetic violins cannot be salvaged.** `process_trade_size_distribution.py:71` caps
the lognormal shape at `sigma = min(max(0.7, log(max/min)/6), 1.0)`. Real per-tier sigma:

| tier | real σ | script σ | real median/mean | script implies |
|---|---|---|---|---|
| Retail | 0.536 | 1.000 | 0.866 | 0.607 |
| Small | 0.686 | 0.700 | 0.790 | 0.783 |
| Institutional | **1.577** | 1.000 (capped) | **0.289** | 0.607 |

Institutional's true shape lies *outside* the script's hard cap, so the figure understates
skew in precisely the tier the paper cares about — irrespective of the seed. Rebuild the
figure from this query (each bin carries 1% of tier mass over `[lower_edge_usd,
upper_edge_usd]`, so density = 0.01 / width) or cut it.

**New finding this enables:** the top 1% of Institutional trades — 3,754 swaps out of
3,753,857 (0.1%) — carry $6.87B, or **25.0% of all sandwiched victim volume**. Victim-side
exposure is as concentrated as bot-side extraction. No delivered CSV could show this.

### Repeat victimization, corrected (`query5c_repeat_victimization_v2`, Dune 8440229)

All 9 acceptance checks pass; cutoffs bit-exact, `SUM(attack_events)` = 3,753,857.

**`tx_from` unmasks 742,330 EOAs against 330,521 takers (+124.6%).** The taker-based
count understated the victim population by more than half.

Trader EOAs only (`is_known_bot = 0`):

| tier | unique EOAs | attacks | **attacks/EOA** | **median** | max |
|---|---|---|---|---|---|
| Retail | 393,766 | 1,873,714 | **4.7584** | **1** | 9,779 |
| Small | 278,906 | 1,507,105 | **5.4036** | **1** | 13,887 |
| Institutional | 68,732 | 267,152 | **3.8869** | **1** | 2,115 |

**The inverted-U shape survives; the level and the comparisons do not.** Paper reports
8.46 → 10.20 → 8.46. Measured: 4.76 → 5.40 → 3.89. Small is still highest, but every
level is roughly halved, and Institutional is now the *lowest* rather than tied with
Retail. Recomputed Poisson rate ratios:

| ratio | paper | **measured** |
|---|---|---|
| Small / Retail | 1.2057 [1.2032, 1.2083] | **1.1356 [1.1332, 1.1380]** |
| Retail / Institutional | 0.9998 [0.9961, 1.0035] | **1.2242 [1.2193, 1.2292]** |

The Retail/Institutional "statistically indistinguishable" result (CI containing 1.0) is
withdrawn: the CI now excludes 1.0 decisively.

**The repeat-victimisation hypothesis fails.** `hypothesis[Repeat victimisation]` asserts
"a typical victim address is sandwiched many times". The **median trader EOA in every
tier is sandwiched exactly once** — so at least half of all victims are one-time victims.
The 4.8–5.4 means are tail artifacts. This is precisely what taker-based counting
concealed: routers pooled thousands of one-time victims into a few addresses with huge
counts, manufacturing the appearance of repeat victimization.

Searcher-linked EOAs: 926 (0.13% of all) carry 2.82% of attacks and $3.19B = 11.59% of
victim volume — flagged, not filtered, so both specifications remain reportable.

### Bot-side regression checks (`query1_v2` 6440670, `query3_v2` 6562142, `query4_v2` 6440710)

All internal checks pass and the three reconcile to each other and to `query0a` exactly:
731 days, 7,205,506 legs, $247.52B, 9,917 addresses, 117 NULL-volume bots.

Aggregates are stable vs the delivered CSVs — **−62 trades (−0.001%), +$0.20B (+0.082%)**.
Confirms once more that the `AT TIME ZONE 'GMT'` window was never shifted.

**But bot-level attribution is not stable.** That +0.08% net hides **$49.4B of per-address
increases against $49.6B of decreases — ~20% of total sandwich volume re-attributed**
between January and August 2026. The clearest case is a near-exact swap:

| address | volume | trades |
|---|---|---|
| `0x1f2f10d1…` | **+$16.02B** | +99,111 |
| `0xae2fc483…` | **−$16.03B** | −101,225 |

Dune's spellbook now assigns that activity to a different address. Consequences:

| metric | delivered | re-pull | change |
|---|---|---|---|
| Gini | 0.9976 | 0.9974 | −0.0001 |
| top-1% share | 98.51% | 98.49% | −0.03 pp |
| HHI | 1,236.5 | 1,348.2 | +111.7 |
| **CR4** | **65.70%** | **59.50%** | **−6.19 pp** |
| **top-10** | **76.81%** | **73.59%** | **−3.22 pp** |
| top-1 bot | 25.09% | 31.54% | +6.45 pp |

**Gini and top-1% share are attribution-robust; CR4 and top-10 are not.** The paper
quotes CR4 = 65.7% and top-10 = 76.8% in `results_summary.md`. Prefer the robust
statistics for headline claims, and treat CR4/top-N as vintage-dependent.

This is neither a paper error nor a query error — both pulls are internally consistent
and describe the same aggregate market with different address-level attribution seven
months apart. Two implications: the replication package **must pin the data vintage**
("Dune, 2024–2025" is not a reproducible citation), and the Sybil caveat in
`table2_concentration` is understated — the issue is not only that addresses ≠ entities,
it is that **the mapping itself moves over time**.

**The $10,000 cutoff on exact numbers:** exact p90 is $8,986.61, so the shipped cutoff sits
**11.28% above p90** (was 12.00% on the approximation) and still falls between p90 and p95.
The gap narrows; it does not close.

### Protocol exposure (`query_protocol_vulnerability_v2`, Dune 8446953) — **30-month only**

All 5 acceptance checks pass: 21 protocols, `sum(victim_trade_count)` = 4,286,398 and
`sum(total_volume_usd)` = $30.37B, both matching `query0a` / `5a_v2` / `5b_v2` exactly.

Adding `tx_from` alongside `taker` measures the router layer **per venue** — the ratio
of distinct senders to distinct taker addresses:

| protocol | victim trades | takers | EOAs | EOAs/taker |
|---|---|---|---|---|
| uniswap | 4,001,516 | 348,973 | 774,463 | 2.2 |
| dodo | 48,397 | 81 | 26,743 | **330.2** |
| curve | 25,460 | 701 | 11,739 | 16.7 |
| maverick | 13,065 | 449 | 7,056 | 15.7 |
| fluid | 1,302 | 52 | 442 | 8.5 |
| pancakeswap | 51,487 | 3,811 | 29,178 | 7.7 |
| balancer | 17,842 | 10,738 | 10,738 | **1.0** |
| ekubo | 47,481 | 27,367 | 27,367 | **1.0** |

Balancer and Ekubo have *no* router intermediation — every taker is its own sender.
Dodo is the opposite extreme: 81 taker addresses front 26,743 distinct traders. This
means router contamination is **venue-specific**, so any protocol-level victim-count
comparison built on `taker` is not comparing like with like — Ekubo's victim count is
real traders, Dodo's is routers. Protocol-level *volume* is unaffected.

Protocol concentration is stable across vintages and windows: Uniswap 70.9% of victim
volume (delivered 72.0%), HHI 5,230 (5,365), CR2 81.5% (81.7%).

Now run on both windows (24-month: 20 protocols, 3,753,857 trades, $27.52B — all
acceptance checks pass). The senders-per-taker ratio is a **stable structural property
of each venue**, moving little between windows for nine of ten. The exception is `dodo`,
which doubles from **164× to 330×** (takers 58 → 81 while distinct senders go 9,529 →
26,743): its router fronting intensified sharply during H1 2026.

Protocol concentration is among the most stable numbers in the project — Uniswap 72.0% /
72.0% / 70.9% and HHI 5,365 / 5,371 / 5,230 across shipped, 24-month and 30-month. On the
24-month re-pull 19 of 20 taker counts reproduce the delivered file exactly; only
Uniswap's falls (324,626 → 302,247, −6.9%), the same vintage drift seen elsewhere.

## Still open (outside this directory)

- `fetch/README.md` documents the tiers as `p50`/`p90` and `total_victims` as unique
  addresses. Both false; needs a corrections banner.
- `output/reports/results_summary.md` states the inverted-U from the defective
  denominators and mislabels the Retail cutoff as `$418.83` (that is the Retail *mean*).
  It is generated by `src/m7_reports.py` — regenerate after the re-run, do not hand-edit.
