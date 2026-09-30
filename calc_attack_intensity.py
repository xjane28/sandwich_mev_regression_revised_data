#!/usr/bin/env python3
"""Attack-intensity sanity check (attacks per $1,000 traded), by victim tier.

This script is not used by run_all.py or by the paper figures. The canonical
pipeline output for this metric is produced by src/m4_victims.py and written to
output/tables/table4_victim_tiers.csv.

It reads the revised 24m victim-impact export and prints a direct ratio check
for each tier.
"""

import csv

if __name__ == "__main__":
    with open('fetch/data/revised-24m/query5b_victim_impact_v2.csv', 'r') as f:
        reader = csv.DictReader(f)
        data = list(reader)

    # Direct ratio sanity check from observed tier-level aggregates.
    for row in data:
        victim_trades = float(row['victim_trades'])
        total_volume = float(row['total_volume'])
        attack_intensity = (victim_trades / total_volume) * 1000
        print(f"{row['victim_tier']}: {attack_intensity:.3f} attacks per $1,000 "
              f"(sanity check only -- see output/tables/table4_victim_tiers.csv for the published figure)")
