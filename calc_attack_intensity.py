#!/usr/bin/env python3
"""Attack-intensity sanity check (attacks per $1,000 traded), by victim tier.

DEPRECATED / NOT USED IN THE PAPER: no .tex file in this repository
references this script's output, and it is not called from run_all.py.
The methodologically correct, currently-maintained version of this exact
metric ("Attacks / $1k Traded") is computed in src/m4_victims.py and
published in output/tables/table4_victim_tiers.csv, which is what the
actual paper figure (fig_victim_impact_metrics.tex, Panel C) uses.

This script previously also fabricated box-plot quartile/whisker bounds
as fixed percentages of the point estimate (median * 0.8/0.9/1.1/1.2)
rather than computing them from real per-observation data -- there is no
real distribution to summarize this way from a single tier-level ratio.
That fabricated part has been removed entirely rather than fixed, since
no real quartile/whisker data exists to compute it from in this export.
It also previously read the legacy fetch/query5b_victim_impact.csv, whose
"victim_count"/"unique_victims" columns were part of the router-
contamination issue documented in fetch/queries/README.md; it now reads
the current revised export instead (fetch/data/revised-24m/), whose
schema renamed victim_count to victim_trades.
Kept only as a standalone sanity check against table4_victim_tiers.csv;
prefer that table for anything going into the paper.
"""

import csv

if __name__ == "__main__":
    with open('fetch/data/revised-24m/query5b_victim_impact_v2.csv', 'r') as f:
        reader = csv.DictReader(f)
        data = list(reader)

    # Attacks per $1,000 traded: a real ratio of two real columns, kept as a
    # sanity check only. No box-plot quartiles/whiskers are computed here --
    # a single tier-level ratio has no real distribution to summarize that
    # way, and the previous version fabricated fixed-percentage bounds
    # instead of a genuine IQR.
    for row in data:
        victim_trades = float(row['victim_trades'])
        total_volume = float(row['total_volume'])
        attack_intensity = (victim_trades / total_volume) * 1000
        print(f"{row['victim_tier']}: {attack_intensity:.3f} attacks per $1,000 "
              f"(sanity check only -- see output/tables/table4_victim_tiers.csv for the published figure)")
