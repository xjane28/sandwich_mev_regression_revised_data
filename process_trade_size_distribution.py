#!/usr/bin/env python3
"""Build trade-size violin geometry from empirical query5d bins."""

import pandas as pd
import numpy as np
import sys
from src import m0_validate


def _interpolate_quantile(tier_df, q):
    target = q * tier_df["trades_in_bin"].sum()
    cum = tier_df["trades_in_bin"].cumsum()
    idx = int(np.searchsorted(cum.values, target, side="left"))
    idx = min(idx, len(tier_df) - 1)
    row = tier_df.iloc[idx]
    prev_cum = cum.iloc[idx - 1] if idx > 0 else 0.0
    in_bin = max(row["trades_in_bin"], 1.0)
    frac = (target - prev_cum) / in_bin
    frac = min(max(frac, 0.0), 1.0)
    return row["lower_edge_usd"] + frac * (row["upper_edge_usd"] - row["lower_edge_usd"])


def process_trade_size_distribution(output_file):
    """Use query5d equal-mass bins to produce violin outlines and tier stats."""
    bundle = m0_validate.load_data_bundle()
    q5d = bundle["q5d"].copy()
    if q5d.empty:
        raise RuntimeError("query5d_trade_size_distribution data is required.")

    tier_order = ["Retail", "Small", "Institutional"]
    q5d["tier_index"] = q5d["victim_tier"].map({tier: i for i, tier in enumerate(tier_order)})
    q5d = q5d.sort_values(["tier_index", "pctile_in_tier"]).reset_index(drop=True)

    stats_data = []
    ymin_candidates = []
    ymax_candidates = []

    for tier_idx, tier in enumerate(tier_order, start=1):
        tier_df = q5d[q5d["victim_tier"] == tier].copy()
        if tier_df.empty:
            continue

        lower = tier_df["lower_edge_usd"].to_numpy(dtype=float)
        upper = tier_df["upper_edge_usd"].to_numpy(dtype=float)
        mids = tier_df["mean_usd"].to_numpy(dtype=float)
        widths_log = np.log10(np.maximum(upper, 1e-12)) - np.log10(np.maximum(lower, 1e-12))
        widths_log = np.maximum(widths_log, 1e-9)
        density_log = 0.01 / widths_log
        violin_width = 0.3 * density_log / density_log.max()

        left = [(tier_idx - w, y) for w, y in zip(violin_width, mids)]
        right = [(tier_idx + violin_width[i], mids[i]) for i in range(len(mids) - 1, -1, -1)]
        coords = left + right + [left[0]]

        tier_file = output_file.replace(".csv", f"_{tier.lower()}.csv")
        with open(tier_file, "w") as f:
            f.write("x,y\n")
            for x, y in coords:
                f.write(f"{x},{y}\n")

        trades = float(tier_df["trades_in_bin"].sum())
        volume = float(tier_df["volume_usd"].sum())
        mean = volume / trades if trades > 0 else np.nan
        q25 = _interpolate_quantile(tier_df, 0.25)
        med = _interpolate_quantile(tier_df, 0.50)
        q75 = _interpolate_quantile(tier_df, 0.75)

        stats_data.append(
            {
                "tier": tier,
                "tier_index": tier_idx,
                "x_pos": tier_idx,
                "trades": trades,
                "avg_tx_size": mean,
                "min_tx": float(tier_df["lower_edge_usd"].min()),
                "max_tx": float(tier_df["upper_edge_usd"].max()),
                "q25": q25,
                "median": med,
                "q75": q75,
                "max_width": float(violin_width.max()),
                "cutoff_p50": float(tier_df["cutoff_p50"].iloc[0]),
                "cutoff_p90": float(tier_df["cutoff_p90"].iloc[0]),
            }
        )

        ymin_candidates.append(float(tier_df["lower_edge_usd"].replace(0, np.nan).dropna().min()))
        ymax_candidates.append(float(tier_df["upper_edge_usd"].max()))

    stats_df = pd.DataFrame(stats_data)
    stats_file = output_file.replace(".csv", "_stats.csv")
    stats_df.to_csv(stats_file, index=False)

    ymin = max(min(ymin_candidates), 1e-1)
    ymax = max(ymax_candidates) * 1.1

    print(f"Y-axis range: {ymin:.2e} to {ymax:.2e}", file=sys.stderr)
    ratio = stats_df.loc[stats_df["tier"] == "Institutional", "avg_tx_size"].iloc[0] / stats_df.loc[stats_df["tier"] == "Retail", "avg_tx_size"].iloc[0]
    print(f"Ratio (Institutional/Retail): {ratio:.1f}x", file=sys.stderr)
    for _, row in stats_df.iterrows():
        print(
            f"{row['tier']}: mean=${row['avg_tx_size']:.2f}, median=${row['median']:.2f}, trades={int(row['trades']):,}",
            file=sys.stderr,
        )

    return ymin, ymax, stats_df

if __name__ == "__main__":
    output_file = "trade_size_distribution_data.csv"
    ymin, ymax, stats = process_trade_size_distribution(output_file)
    print(f"\nProcessed data written to {output_file}")
    print(f"Y-axis range: {ymin:.2e} to {ymax:.2e}")
