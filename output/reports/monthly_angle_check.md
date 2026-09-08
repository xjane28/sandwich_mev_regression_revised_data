# Additional Angle Check: Month-by-Month Drift and Bot/Victim Ratio

## What was tested now
1. **Month-by-month intensity proxy** from revised `query1_mev_volume_v2` (daily data aggregated to month):
   - average daily bot legs,
   - bot-side USD per leg,
   - legs per transaction,
   - average daily active bots.
2. **Bot/Victim volume ratio** using revised windows:
   - 24m ratio,
   - 30m ratio,
   - implied ratio in the added Jan--Jun 2026 segment (difference between 30m and 24m totals).

## Important data caveat
- The current revised exports do **not** include month-level victim trade-size bins.
- So this is a **monthly proxy** for trade-size drift on the bot side, not the final month-level victim trade-size distribution test.

## Results
- Analysis horizon for monthly proxy: `2024-01` to `2026-06` (30 months)
- Avg daily bot legs: 11,751 -> 5,782 (**-50.8%**; rank-corr=-0.810, slope=-393.66 legs/month)
- Bot-side USD per leg: $21,415.28 -> $47,716.06 (**+122.8%**; rank-corr=0.782, slope=2,450.41 USD/month)
- Avg daily active bots: 207.7 -> 87.1 (**-58.1%**)

- Bot/Victim volume ratio (24m): **8.99x**
- Bot/Victim volume ratio (30m): **10.15x**
- Change 24m -> 30m: **+12.9%**
- Implied added-period ratio (Jan--Jun 2026 segment): **21.34x**

## Interpretation
- Month-by-month intensity proxy: **interesting**.
- Bot/Victim ratio drift: **interesting**.
- Combined reading: the added months are consistent with a **lower-frequency / higher-notional** regime (fewer legs, larger USD per leg), and a higher bot/victim notional multiplier.

## Recommended next check (new query idea)
- Add a monthly version of `query5d_trade_size_distribution` (group by calendar month and tier).
- Then repeat this same panel on **victim-side** monthly bins (p25/p50/p90 and tail mass per month) to validate the proxy directly.
