#!/usr/bin/env python3
"""Victim-impact sanity check (attacks per address with trade), by tier.

This script is not used by run_all.py or by the paper figures. The canonical
pipeline output for tier-level victim metrics is produced by src/m4_victims.py
and written to output/tables/table4_victim_tiers.csv.

It reads the revised 24m victim-impact export and prints a direct ratio check
for each tier.
"""

import csv

if __name__ == "__main__":
    with open('fetch/data/revised-24m/query5b_victim_impact_v2.csv', 'r') as f:
        reader = csv.DictReader(f)
        data = list(reader)

    # Attacks per victim-address-with-a-trade-in-tier: a real ratio of two
    # real columns, kept as a sanity check only. No loss/dollar figure is
    # computed here -- this export does not contain the trade-level
    # slippage data that would be required to compute a real one.
    for row in data:
        victim_trades = float(row['victim_trades'])
        addresses = float(row['addresses_with_trade_in_tier'])
        attacks_per_address = victim_trades / addresses
        print(f"{row['victim_tier']}: attacks_per_address={attacks_per_address:.4f} "
              f"(sanity check only -- see output/tables/table4_victim_tiers.csv for the published figure)")
