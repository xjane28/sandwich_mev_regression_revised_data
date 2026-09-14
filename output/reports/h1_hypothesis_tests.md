# H1 Hypothesis Testing

## Scope

- H1a: concentration exists in sandwich-MEV volume captured by bot addresses.
- H1b: concentration is caused by scale/infrastructure advantages.
- This script tests H1a directly and reports H1b as non-identified in the available files.

## Methods implemented

- Bootstrap resamples (main): 10000
- Bootstrap resamples (monthly/quarterly): 2000
- Metrics: Gini, Top 1% share, CR1, CR4, CR10, CR20, HHI
- One-sided benchmark tests: Gini > 0.90; Top 1% share > 90%
- Sensitivity: largest-bot exclusion; top-k exclusions; positive-volume-only; clustering scenarios
- Time checks: monthly/quarterly concentration and stability when period-level files are available
- Window robustness: 24m vs 30m
- Rank persistence: Spearman, top-k retention, transition matrix

## Window: revised-24m

- Source file: `fetch/data/revised-24m/query3_full_bot_distribution_v2.csv`; rows=9917, measurable volumes=9800, positive volumes=9799
- Gini: 0.9974 (95% CI 0.9950 to 0.9983)
- Top 1% share: 98.49% (95% CI 96.40% to 99.25%)
- CR1=31.54%, CR4=59.50%, CR10=73.59%, CR20=83.44%
- HHI=1348.2
- Benchmark test Gini>0.90: p=0.000100, reject_h0=True
- Benchmark test Top1%>90%: p=0.000100, reject_h0=True
- Positive-volume-only sensitivity: Gini=0.9974, Top 1% share=98.49%, CR4=59.50%, HHI=1348.2

### Top-k exclusion sensitivity

| Scenario | Gini | Top 1% | CR4 | CR10 | HHI | Remaining N |
|---|---:|---:|---:|---:|---:|---:|
| exclude_top_1 | 0.9965 | 97.84% | 45.17% | 63.58% | 753.7 | 9799 |
| exclude_top_5 | 0.9947 | 96.44% | 24.17% | 45.51% | 283.5 | 9795 |
| exclude_top_10 | 0.9937 | 95.53% | 18.99% | 37.31% | 216.6 | 9790 |

### Address-clustering sensitivity

| Scenario | Gini | Top 1% | CR4 | CR10 | HHI | Result N |
|---|---:|---:|---:|---:|---:|---:|
| merge_top_5_into_1 | 0.9979 | 98.63% | 69.45% | 78.61% | 3941.9 | 9796 |
| merge_top_10_into_2 | 0.9981 | 98.76% | 76.34% | 81.98% | 3039.5 | 9792 |
| merge_top_20_into_4 | 0.9984 | 98.97% | 83.44% | 86.70% | 2220.0 | 9784 |

### Time stability

- Period-level concentration test unavailable: period_file_not_found

## Window: revised-30m

- Source file: `fetch/data/revised-30m/query3_full_bot_distribution_v2.csv`; rows=10874, measurable volumes=10734, positive volumes=10733
- Gini: 0.9971 (95% CI 0.9944 to 0.9981)
- Top 1% share: 98.11% (95% CI 95.75% to 99.07%)
- CR1=32.11%, CR4=56.34%, CR10=68.07%, CR20=78.39%
- HHI=1302.8
- Benchmark test Gini>0.90: p=0.000100, reject_h0=True
- Benchmark test Top1%>90%: p=0.000100, reject_h0=True
- Positive-volume-only sensitivity: Gini=0.9971, Top 1% share=98.11%, CR4=56.34%, HHI=1302.8

### Top-k exclusion sensitivity

| Scenario | Gini | Top 1% | CR4 | CR10 | HHI | Remaining N |
|---|---:|---:|---:|---:|---:|---:|
| exclude_top_1 | 0.9959 | 97.28% | 39.81% | 55.25% | 589.4 | 10733 |
| exclude_top_5 | 0.9941 | 95.90% | 17.83% | 37.26% | 206.6 | 10729 |
| exclude_top_10 | 0.9936 | 95.38% | 16.50% | 32.32% | 181.4 | 10724 |

### Address-clustering sensitivity

| Scenario | Gini | Top 1% | CR4 | CR10 | HHI | Result N |
|---|---:|---:|---:|---:|---:|---:|
| merge_top_5_into_1 | 0.9975 | 98.28% | 64.75% | 73.34% | 3531.7 | 10730 |
| merge_top_10_into_2 | 0.9977 | 98.45% | 71.10% | 76.94% | 2761.0 | 10726 |
| merge_top_20_into_4 | 0.9981 | 98.71% | 78.39% | 82.07% | 2058.8 | 10718 |

### Time stability

- Period-level concentration test unavailable: period_file_not_found

## 24m vs 30m robustness

| Metric | 24m | 30m | Abs Change (30m-24m) | Relative Change |
|---|---:|---:|---:|---:|
| gini | 99.74% | 99.71% | -0.04% | -0.04% |
| top_1pct_share | 98.49% | 98.11% | -0.37% | -0.38% |
| cr1 | 31.54% | 32.11% | 0.57% | 1.80% |
| cr4 | 59.50% | 56.34% | -3.16% | -5.31% |
| cr10 | 73.59% | 68.07% | -5.52% | -7.50% |
| cr20 | 83.44% | 78.39% | -5.06% | -6.06% |
| hhi | 1348.2 | 1302.8 | -45.4 | -3.37% |

## Rank persistence and top-bot retention

- Common positive-volume addresses: 9799; Spearman rank correlation=0.9868

| k | Retention | Intersection Count |
|---:|---:|---:|
| 1 | 100.00% | 1 |
| 4 | 100.00% | 4 |
| 10 | 100.00% | 10 |
| 20 | 75.00% | 15 |
| 98 | 79.59% | 78 |

## Conclusions from data

- H1a: In revised-24m, concentration is high: Gini=0.9974, Top 1% share=98.49%, CR4=59.50%, CR10=73.59%, CR20=83.44%, HHI=1348.2.
- H1a benchmark tests: Gini CI [0.9950, 0.9983] against 0.90 (p=0.000100), Top 1% CI [96.40%, 99.25%] against 90% (p=0.000100).
- After excluding the largest bot, concentration remains high: Gini=0.9965, Top 1% share=97.84%, CR4=45.17%, HHI=753.7.
- 24m vs 30m robustness: Gini change=-0.0004, Top 1% share change=-0.37%.
- Rank persistence across windows: Spearman rank correlation=0.9868 on 9799 common addresses.
- H1b: causal attribution to infrastructure/scale advantages is not identified by these tests.
