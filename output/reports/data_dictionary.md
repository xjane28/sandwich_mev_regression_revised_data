# Data Dictionary and Identity Conventions (Revised)

## Active Identity Conventions
- **Trade events:** `query5b_victim_impact_v2` (`victim_count`, `total_volume`)
- **Victim identity for repeat-victimisation:** `query5c_repeat_victimization_v2` keyed on `tx_from`
- **Router/intermediation diagnostics:** `query0b_router_check`
- **Global taker count audit:** `query0a_data_quality`

## Key Interpretation Rules
1. `query5b` per-tier address counts are non-additive tier-address observations.
2. Global unique victim identity should be reported from tx_from (`query5c`) and distinguished from taker counts (`query0a`/`query5a`).
3. Repeat-victimisation hypothesis is withdrawn as a typical-case claim; medians by tier are the primary statistic.

## Current 24m Primary Snapshot
- Window: 2024-01-01 to 2025-12-31 (731 days)
- Victim events: 3,753,857
- Unique takers: 330,521
- Unique tx_from EOAs (total): 742,330
- Unique tx_from non-bot EOAs: 741,404
