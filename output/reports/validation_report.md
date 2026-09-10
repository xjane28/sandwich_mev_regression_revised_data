# Data and Schema Validation Report

## Summary of Assertions

| Check ID | Description | Expected | Computed | Status |
|---|---|---|---|---|
| Q1-ROWS | Daily series non-empty | > 0 | 731 | **PASS** |
| Q1-DATES-UNIQUE | Date uniqueness | nunique == rows | 731 vs 731 | **PASS** |
| Q1-DATES-CONTIG | Date continuity | 731 | 731 | **PASS** |
| Q1-VOL-POS | Total daily volume positive | > 0 | 247524853969.93 | **PASS** |
| Q1-TRADES-POS | Total daily trades positive | > 0 | 7205506 | **PASS** |
| Q1-BOTS-POS | Mean active bots positive | > 0 | 171.92 | **PASS** |
| Q3-ROWS | Bot distribution non-empty | > 0 | 9917 | **PASS** |
| Q3-UNIQ-ADDR | Bot addresses unique | unique == rows | 9917 vs 9917 | **PASS** |
| Q3-HAS-VOLUME | Has measurable bot volumes | > 0 non-null rows | 9800 | **PASS** |
| Q4-ROWS | Bot profile non-empty | > 0 | 9917 | **PASS** |
| Q4-ADDR-SET | q4 address set identical to q3 | True | True | **PASS** |
| Q4-DAYS-POS | days_active positive | all >= 1 | 1 | **PASS** |
| Q4-VOL-MATCH | Per-address volume alignment q3 vs q4 | < 0.01 max abs diff | 0.000771 | **PASS** |
| Q5A-ONE-ROW | q5a single summary row | 1 | 1 | **PASS** |
| Q5A-PERCENTILES | q5a percentile columns present | all present | True | **PASS** |
| Q5A-P-ORDER | Percentiles non-decreasing | True | True | **PASS** |
| Q5A-MINMAX | min <= p25 and p95 <= max | True | True | **PASS** |
| Q5B-ROWS | q5b has tier rows | >= 3 | 3 | **PASS** |
| Q5B-TIERS | Retail/Small/Institutional present | {'Retail', 'Institutional', 'Small'} | {'Retail', 'Institutional', 'Small'} | **PASS** |
| Q5B-TRADES-POS | Tier trade counts positive | all > 0 | 1 | **PASS** |
| Q5B-VOLUME-POS | Tier volumes positive | all > 0 | 1 | **PASS** |
| Q5B-PCT-TRADES | Tier trade shares sum to 100 | 100 ± 0.05 | 100.000000 | **PASS** |
| Q5B-PCT-VOL | Tier volume shares sum to 100 | 100 ± 0.05 | 100.000000 | **PASS** |
| Q5B-CUTOFF-P50-CONS | cutoff_p50 constant across tiers | nunique == 1 | 1 | **PASS** |
| Q5B-CUTOFF-P90-CONS | cutoff_p90 constant across tiers | nunique == 1 | 1 | **PASS** |
| PROT-ROWS | Protocol summary non-empty | > 0 | 20 | **PASS** |
| PROT-HAS-UNISWAP | Contains uniswap row | True | True | **PASS** |
| PROT-VOL-POS | Protocol volume sum positive | > 0 | 27523561653.66 | **PASS** |
| CROSS-VOL-Q1-Q3 | q1 volume equals q3 volume | abs diff <= 1 | 0.000336 | **PASS** |
| CROSS-TRADES-Q1-Q4 | q1 trades equals q4 trades | exact | 7205506 vs 7205506 | **PASS** |
| CROSS-VIC-Q5A-Q5B | q5a events equals q5b events | exact | 3753857 vs 3753857 | **PASS** |
| CROSS-VIC-Q5B-PROT | q5b events equals protocol events | exact | 3753857 vs 3753857 | **PASS** |
| CROSS-VOL-Q5B-PROT | q5b volume equals protocol volume | abs diff <= 1 | 0.000088 | **PASS** |

## Data Snapshot

- Daily window: 2024-01-01 to 2025-12-31 (731 days).
- Bot-side totals: 7,205,506 trades, $247.52B volume, 9,917 addresses.
- Victim-side totals: 3,753,857 events, $27.52B volume.
- Protocol rows: 20, uniswap share: 72.01% of victim-side volume.
- Missing bot volumes in q3: 117.
