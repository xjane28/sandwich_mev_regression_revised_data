#!/usr/bin/env python3
"""Derive fig_victim_impact_metrics.tex's plot data directly from the
real, pipeline-generated output/tables/table4_victim_tiers.csv, instead of
the figure hardcoding manually-transcribed numbers. Uses plain ASCII
column names (no spaces/slashes) so pgfplots can read them directly.

Run this after src/m4_victims.py (or run_all.py) has produced
output/tables/table4_victim_tiers.csv, and before compiling the paper.
"""

import csv

INPUT = "output/tables/table4_victim_tiers.csv"
OUTPUT = "victim_impact_metrics_data.csv"
TIER_ORDER = ["Retail", "Small", "Institutional"]


def main():
    with open(INPUT, "r") as f:
        rows = {row["Tier"]: row for row in csv.DictReader(f)}

    missing = [t for t in TIER_ORDER if t not in rows]
    if missing:
        raise RuntimeError(f"{INPUT} is missing expected tier(s): {missing}")

    with open(OUTPUT, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["x_pos", "tier", "attacks_per_trader", "attacks_per_1k_traded"])
        for i, tier in enumerate(TIER_ORDER, start=1):
            r = rows[tier]
            writer.writerow([
                i,
                tier,
                float(r["Attacks / Trader"]),
                float(r["Attacks / $1k Traded"]),
            ])

    print(f"Wrote {OUTPUT} from {INPUT}:")
    with open(OUTPUT) as f:
        print(f.read())


if __name__ == "__main__":
    main()
