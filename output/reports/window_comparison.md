# 24m vs 30m Comparison Framework

This file provides side-by-side metrics with a replication-vs-instability split.  
Primary: 24m. Robustness: 30m when present.

Status: 30m window loaded: 2024-01-01 to 2026-06-30 (912 days).

## Replication vs Instability Panel
| Metric | 24m | 30m | Status |
|---|---:|---:|---|
| Median attacks/trader (Retail) | 1.0000 | 1.0000 | replicates (+0.0%) |
| Median attacks/trader (Small) | 1.0000 | 1.0000 | replicates (+0.0%) |
| Median attacks/trader (Institutional) | 1.0000 | 1.0000 | replicates (+0.0%) |
| Small/Retail RR (non-bot tx_from) | 1.1356 | 1.1619 | replicates (+2.3%) |
| Retail/Institutional RR (non-bot tx_from) | 1.2242 | 1.1458 | replicates (-6.4%) |
| Bot-side Gini | 0.9974 | 0.9971 | replicates (-0.0%) |
| CR4 (vintage-sensitive) | 59.5032 | 56.3441 | replicates (-5.3%) |
| CR10 (vintage-sensitive) | 73.5904 | 68.0697 | replicates (-7.5%) |
| Institutional/Retail mean-size ratio | 143.8180 | 176.0315 | window-sensitive (+22.4%) |
| Bot/Victim volume ratio | 8.9932 | 10.1505 | window-sensitive (+12.9%) |

## Interpretation Rules
- **Replicates**: relative change <= 10%.
- **Window-sensitive**: relative change > 10%.
- Metrics explicitly flagged as vintage-sensitive (e.g., CR4/CR10/top-N) should not be used as sole headline evidence without a pinned data vintage.
