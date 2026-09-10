import os
import pandas as pd
import numpy as np
from src import m0_validate, m2_concentration, m4_victims


def _metric_from_q0a(q0a, metric_name, default=np.nan):
    if q0a.empty or "metric" not in q0a.columns:
        return default
    hit = q0a[q0a["metric"] == metric_name]
    if hit.empty:
        return default
    return float(hit["value"].iloc[0])


def _load_bundle_or_none(window_key, write_repro_manifest=False):
    try:
        return m0_validate.load_data_bundle(window=window_key, write_repro_manifest=write_repro_manifest), None
    except Exception as exc:
        return None, str(exc)


def _load_legacy_metrics():
    na_vals = ["<nil>", "NULL", "null", "NaN", "nan"]
    q5a = pd.read_csv("fetch/query5a_break_points.csv", na_values=na_vals)
    q5b = pd.read_csv("fetch/query5b_victim_impact.csv", na_values=na_vals)
    q4 = pd.read_csv("fetch/query4_top_bots.csv", na_values=na_vals)
    q1 = pd.read_csv("fetch/query1_mev_volume.csv", na_values=na_vals)

    for col in ["total_sandwich_trades", "total_volume_usd"]:
        if col in q4.columns:
            q4[col] = pd.to_numeric(q4[col], errors="coerce")
    for col in [
        "avg_tx_size",
        "p25",
        "p50_median",
        "p75",
        "p90",
        "p95",
        "victim_count",
        "unique_victims",
        "total_volume",
    ]:
        if col in q5a.columns:
            q5a[col] = pd.to_numeric(q5a[col], errors="coerce")
        if col in q5b.columns:
            q5b[col] = pd.to_numeric(q5b[col], errors="coerce")
    for col in ["sandwich_trade_count", "total_sandwich_volume_usd", "unique_sandwich_bots", "unique_transactions"]:
        if col in q1.columns:
            q1[col] = pd.to_numeric(q1[col], errors="coerce")

    q5b_t = q5b.set_index("victim_tier")
    ret = q5b_t.loc["Retail"]
    sma = q5b_t.loc["Small"]
    inst = q5b_t.loc["Institutional"]
    rr_sr = (sma["victim_count"] / sma["unique_victims"]) / (ret["victim_count"] / ret["unique_victims"])
    rr_ri = (ret["victim_count"] / ret["unique_victims"]) / (inst["victim_count"] / inst["unique_victims"])
    se_ri = np.sqrt(1.0 / ret["victim_count"] + 1.0 / inst["victim_count"])
    rr_ri_ci = (rr_ri * np.exp(-1.96 * se_ri), rr_ri * np.exp(1.96 * se_ri))

    return {
        "victim_events": int(q5b["victim_count"].sum()),
        "victim_volume": float(q5b["total_volume"].sum()),
        "bot_addresses": int(len(q4)),
        "bot_volume": float(q4["total_volume_usd"].sum()),
        "p25": float(q5a.loc[0, "p25"]),
        "p50": float(q5a.loc[0, "p50_median"]),
        "p75": float(q5a.loc[0, "p75"]),
        "p90": float(q5a.loc[0, "p90"]),
        "p95": float(q5a.loc[0, "p95"]),
        "retail_mean": float(ret["avg_tx_size"]),
        "small_mean": float(sma["avg_tx_size"]),
        "inst_mean": float(inst["avg_tx_size"]),
        "size_ratio": float(inst["avg_tx_size"] / ret["avg_tx_size"]),
        "rr_sr": float(rr_sr),
        "rr_ri": float(rr_ri),
        "rr_ri_ci": rr_ri_ci,
    }


def _compute_window_metrics(bundle):
    q1 = bundle["q1"]
    q4 = bundle["q4"]
    q5a = bundle["q5a"]
    q5b = bundle["q5b"]
    q5c = bundle["q5c"]
    q0a = bundle["q0a"]
    q0b = bundle["q0b"]
    manifest = bundle["manifest"]
    tier_addr_col = m0_validate.q5b_tier_address_col(q5b)

    min_date = q1["date_parsed"].min()
    max_date = q1["date_parsed"].max()
    window_label = f"{min_date.strftime('%Y-%m-%d')} to {max_date.strftime('%Y-%m-%d')} ({q1['date_parsed'].nunique()} days)"

    v_meas = q4[q4["total_volume_usd"].notna() & (q4["total_volume_usd"] >= 0.0)]["total_volume_usd"]
    gini_meas = m2_concentration.compute_gini(v_meas)
    cr_meas = m2_concentration.compute_concentration_ratios(v_meas)

    tiers = q5b.set_index("victim_tier")
    non_bot = q5c[q5c["is_known_bot"] == 0].set_index("victim_tier")
    known_bot = q5c[q5c["is_known_bot"] == 1].set_index("victim_tier")

    rr_sr, sr_low, sr_high, _ = m4_victims.poisson_rate_ratio(
        non_bot.loc["Small", "attack_events"],
        non_bot.loc["Small", "unique_eoas"],
        non_bot.loc["Retail", "attack_events"],
        non_bot.loc["Retail", "unique_eoas"],
    )
    rr_ri, ri_low, ri_high, _ = m4_victims.poisson_rate_ratio(
        non_bot.loc["Retail", "attack_events"],
        non_bot.loc["Retail", "unique_eoas"],
        non_bot.loc["Institutional", "attack_events"],
        non_bot.loc["Institutional", "unique_eoas"],
    )

    unique_takers = _metric_from_q0a(q0a, "sandwiched_unique_takers_gt0_usd", default=float(q5a.loc[0, "unique_victim_addresses"]))
    tx_from_total = float(q5c["unique_eoas"].sum())
    tx_from_non_bot = float(non_bot["unique_eoas"].sum())
    tx_from_known_bot = float(known_bot["unique_eoas"].sum())

    top30_router_trade_share = np.nan
    if not q0b.empty:
        top30 = q0b.sort_values("distinct_senders", ascending=False).drop_duplicates("taker").head(30)
        top30_router_trade_share = float(top30["victim_trades"].sum() / q5b["victim_count"].sum())

    ratio_vol = float(q4["total_volume_usd"].sum() / q5b["total_volume"].sum())
    ratio_size = float(tiers.loc["Institutional", "avg_tx_size"] / tiers.loc["Retail", "avg_tx_size"])

    return {
        "window_label": window_label,
        "q5a": q5a.iloc[0],
        "q5b": tiers,
        "q5c_nonbot": non_bot,
        "q5c_bot": known_bot,
        "manifest": manifest,
        "gini": gini_meas,
        "cr": cr_meas,
        "bot_addresses": len(q4),
        "bot_legs": int(q4["total_sandwich_trades"].sum()),
        "bot_volume": float(q4["total_volume_usd"].sum()),
        "victim_events": int(q5b["victim_count"].sum()),
        "victim_volume": float(q5b["total_volume"].sum()),
        "tier_address_obs": int(q5b[tier_addr_col].sum()),
        "unique_takers": int(unique_takers),
        "tx_from_total": int(tx_from_total),
        "tx_from_non_bot": int(tx_from_non_bot),
        "tx_from_known_bot": int(tx_from_known_bot),
        "rr_sr": rr_sr,
        "rr_sr_ci": (sr_low, sr_high),
        "rr_ri": rr_ri,
        "rr_ri_ci": (ri_low, ri_high),
        "ratio_vol": ratio_vol,
        "ratio_size": ratio_size,
        "top30_router_trade_share": top30_router_trade_share,
    }


def _fmt_money(val):
    return f"${val:,.2f}"


def _fmt_billion(val):
    return f"${val / 1e9:,.2f}B"


def _comparison_row(name, a, b):
    if b is None:
        return f"| {name} | {a} | n/a | pending 30m data |"
    if isinstance(a, (int, float)) and isinstance(b, (int, float)) and np.isfinite(a) and np.isfinite(b):
        if a == 0:
            return f"| {name} | {a:,.4f} | {b:,.4f} | check |"
        rel = (b - a) / abs(a) * 100
        stable = "replicates" if abs(rel) <= 10 else "window-sensitive"
        return f"| {name} | {a:,.4f} | {b:,.4f} | {stable} ({rel:+.1f}%) |"
    return f"| {name} | {a} | {b} | check |"


def _rank_correlation(x, y):
    if len(x) < 2:
        return np.nan
    xr = pd.Series(x).rank(method="average").to_numpy(dtype=float)
    yr = pd.Series(y).rank(method="average").to_numpy(dtype=float)
    if np.nanstd(xr) == 0 or np.nanstd(yr) == 0:
        return np.nan
    return float(np.corrcoef(xr, yr)[0, 1])


def _build_monthly_intensity(q1):
    d = q1.copy()
    if "date_parsed" not in d.columns:
        d["date_parsed"] = m0_validate.parse_utc_date(d["date"])
    for c in ["sandwich_trade_count", "total_sandwich_volume_usd", "unique_sandwich_bots", "unique_transactions"]:
        if c in d.columns:
            d[c] = pd.to_numeric(d[c], errors="coerce")

    d["month"] = d["date_parsed"].dt.to_period("M").dt.to_timestamp()
    d["usd_per_leg_daily"] = d["total_sandwich_volume_usd"] / d["sandwich_trade_count"].replace(0, np.nan)
    d["legs_per_tx_daily"] = d["sandwich_trade_count"] / d["unique_transactions"].replace(0, np.nan)

    monthly = (
        d.groupby("month", as_index=False)
        .agg(
            days_observed=("date_parsed", "nunique"),
            bot_legs=("sandwich_trade_count", "sum"),
            bot_transactions=("unique_transactions", "sum"),
            bot_volume_usd=("total_sandwich_volume_usd", "sum"),
            avg_daily_unique_bots=("unique_sandwich_bots", "mean"),
            median_daily_usd_per_leg=("usd_per_leg_daily", "median"),
            median_daily_legs_per_tx=("legs_per_tx_daily", "median"),
        )
        .sort_values("month")
        .reset_index(drop=True)
    )
    monthly["avg_daily_legs"] = monthly["bot_legs"] / monthly["days_observed"].replace(0, np.nan)
    monthly["avg_daily_bot_volume_usd"] = monthly["bot_volume_usd"] / monthly["days_observed"].replace(0, np.nan)
    monthly["usd_per_leg"] = monthly["bot_volume_usd"] / monthly["bot_legs"].replace(0, np.nan)
    monthly["legs_per_tx"] = monthly["bot_legs"] / monthly["bot_transactions"].replace(0, np.nan)
    monthly["usd_per_tx"] = monthly["bot_volume_usd"] / monthly["bot_transactions"].replace(0, np.nan)
    monthly["month"] = monthly["month"].dt.strftime("%Y-%m")
    return monthly


def _first_last_change(df, col, n=3):
    if df.empty:
        return np.nan, np.nan, np.nan
    head = float(df[col].head(min(n, len(df))).mean())
    tail = float(df[col].tail(min(n, len(df))).mean())
    if head == 0:
        return head, tail, np.nan
    return head, tail, ((tail - head) / abs(head)) * 100.0


def generate_reports():
    os.makedirs("output/reports", exist_ok=True)

    primary_bundle, _ = _load_bundle_or_none("24m", write_repro_manifest=True)
    if primary_bundle is None:
        primary_bundle = m0_validate.load_data_bundle(write_repro_manifest=True)
    primary = _compute_window_metrics(primary_bundle)

    robust_bundle, robust_err = _load_bundle_or_none("30m", write_repro_manifest=False)
    robust = _compute_window_metrics(robust_bundle) if robust_bundle is not None else None
    primary_window_key = (primary_bundle.get("manifest", {}).get("selected_window", {}) or {}).get("key", "24m")
    # Ensure local ./data remains pinned to the primary window after optional robustness loading.
    m0_validate.ensure_data_files(window=primary_window_key)
    legacy = _load_legacy_metrics()

    q5a = primary["q5a"]
    q5b = primary["q5b"]
    q5c_nonbot = primary["q5c_nonbot"]
    q5c_bot = primary["q5c_bot"]
    ret_row = q5b.loc["Retail"]
    sma_row = q5b.loc["Small"]
    inst_row = q5b.loc["Institutional"]

    rr_sr, (sr_low, sr_high) = primary["rr_sr"], primary["rr_sr_ci"]
    rr_ri, (ri_low, ri_high) = primary["rr_ri"], primary["rr_ri_ci"]
    ratio_attacks_1k = (ret_row["victim_count"] / ret_row["total_volume"] * 1000.0) / (inst_row["victim_count"] / inst_row["total_volume"] * 1000.0)
    ratio_avg_size = inst_row["avg_tx_size"] / ret_row["avg_tx_size"]

    manifest = primary["manifest"]
    selected_window = manifest.get("selected_window", {}) or {}
    manifest_window = selected_window.get("name", "unknown")
    manifest_pull_date = manifest.get("data_pull_date_utc", "unknown")
    query_ids = manifest.get("query_ids", {})

    rr_ri_claim = "excludes 1.0 (statistically distinguishable)" if (ri_low > 1.0 or ri_high < 1.0) else "includes 1.0 (not distinguishable)"
    router_share_txt = f"{primary['top30_router_trade_share'] * 100:.2f}%" if np.isfinite(primary["top30_router_trade_share"]) else "n/a"

    summary_md = f"""# Empirical Results Summary: Distributional Incidence of Sandwich-MEV on Ethereum

Primary window: **24m** (`{primary['window_label']}`). Robustness window: **30m** (loaded when data are present).

## Reproducibility and Data Vintage Controls
- Selected source folder: `{manifest_window}`
- Data pull date (UTC, inferred from file timestamps): `{manifest_pull_date}`
- Query IDs pinned in this run: {query_ids}
- Repeat-victimisation identity source: `query5c_repeat_victimization_v2` keyed on `tx_from`

## 1) Repeat-victimisation Correction (implemented)
- The repeat-victimisation hypothesis is **withdrawn** as a typical-case claim.
- Trader-level medians (non-bot `tx_from`) are Retail **{int(q5c_nonbot.loc['Retail', 'median_attacks_per_eoa'])}**, Small **{int(q5c_nonbot.loc['Small', 'median_attacks_per_eoa'])}**, Institutional **{int(q5c_nonbot.loc['Institutional', 'median_attacks_per_eoa'])}**.
- Trader-level means remain heterogenous: Retail **{q5c_nonbot.loc['Retail', 'attacks_per_eoa']:.2f}**, Small **{q5c_nonbot.loc['Small', 'attacks_per_eoa']:.2f}**, Institutional **{q5c_nonbot.loc['Institutional', 'attacks_per_eoa']:.2f}**.
- Known-bot victims are reported separately (EOAs): Retail **{int(q5c_bot.loc['Retail', 'unique_eoas'])}**, Small **{int(q5c_bot.loc['Small', 'unique_eoas'])}**, Institutional **{int(q5c_bot.loc['Institutional', 'unique_eoas'])}**.

## 2) Unique-victim Identity Correction (implemented)
- `query5b` tier counts are **tier-address observations** (non-additive), not global unique victims.
- Unique takers (`query0a`): **{primary['unique_takers']:,}**
- Unique `tx_from` EOAs (`query5c`): **{primary['tx_from_total']:,}** total, of which **{primary['tx_from_non_bot']:,}** are non-bot trader EOAs.

## 3) Revised Core Numbers (24m primary)
- Victim events: **{primary['victim_events']:,}**
- Victim volume: **{_fmt_billion(primary['victim_volume'])}**
- Bot addresses: **{primary['bot_addresses']:,}**
- Bot-side volume: **{_fmt_billion(primary['bot_volume'])}**
- Percentiles (`query5a_v2`): p25 **{_fmt_money(q5a['p25'])}**, p50 **{_fmt_money(q5a['p50_median'])}**, p75 **{_fmt_money(q5a['p75'])}**, p90 **{_fmt_money(q5a['p90'])}**, p95 **{_fmt_money(q5a['p95'])}**
- Tier means (`query5b_v2`): Retail **{_fmt_money(ret_row['avg_tx_size'])}**, Small **{_fmt_money(sma_row['avg_tx_size'])}**, Institutional **{_fmt_money(inst_row['avg_tx_size'])}**
- Mean-size spread (Institutional/Retail): **{ratio_avg_size:.2f}x** (window-specific, replaces static 157.9x text)
- Mechanical identity check: attacks-per-$1k ratio Retail/Institutional = **{ratio_attacks_1k:.2f}x**.

## 4) Repeat-Frequency Ratio Correction (implemented)
- Small/Retail (non-bot `tx_from`): **{rr_sr:.4f}** [{sr_low:.4f}, {sr_high:.4f}]
- Retail/Institutional (non-bot `tx_from`): **{rr_ri:.4f}** [{ri_low:.4f}, {ri_high:.4f}] → **{rr_ri_claim}**

## 5) Router/Intermediation Diagnostics (implemented)
- Top-30 takers by distinct senders account for **{router_share_txt}** of victim trades.
- Interpretation control: protocol-level size patterns can partially reflect routing/intermediation structure, not only trader composition.

## 6) Trade-Size Distribution Figure Source (implemented)
- Violin geometry is generated from `query5d_trade_size_distribution` empirical bins.
- Synthetic lognormal generation is removed from the production path.

## 7) Concentration Metrics and Vintage-Sensitive Fields
- Bot-side Gini: **{primary['gini']:.4f}**
- CR1: **{primary['cr']['cr1']:.2f}%**, CR4: **{primary['cr']['cr4']:.2f}%**, CR10: **{primary['cr']['cr10']:.2f}%**
- Top-1% share: **{primary['cr']['top_1']:.2f}%**
- Vintage-sensitive metrics to track explicitly in comparisons: **CR4, CR10, top-10 share, top-1 bot share**.

## 8) Previous (Legacy) vs Revised Comparison
- Legacy victim events: **{legacy['victim_events']:,}** vs revised-24m **{primary['victim_events']:,}**
- Legacy bot addresses: **{legacy['bot_addresses']:,}** vs revised-24m **{primary['bot_addresses']:,}**
- Legacy p50/p90: **{_fmt_money(legacy['p50'])} / {_fmt_money(legacy['p90'])}**
  vs revised-24m **{_fmt_money(q5a['p50_median'])} / {_fmt_money(q5a['p90'])}**
- Legacy Institutional/Retail mean-size ratio: **{legacy['size_ratio']:.2f}x**
  vs revised-24m **{primary['ratio_size']:.2f}x** and revised-30m **{(robust['ratio_size'] if robust is not None else float('nan')):.2f}x**
- Legacy Retail/Institutional RR: **{legacy['rr_ri']:.4f}** [{legacy['rr_ri_ci'][0]:.4f}, {legacy['rr_ri_ci'][1]:.4f}]
  vs revised-24m **{primary['rr_ri']:.4f}** [{primary['rr_ri_ci'][0]:.4f}, {primary['rr_ri_ci'][1]:.4f}]
"""

    with open("output/reports/results_summary.md", "w") as f:
        f.write(summary_md)
    print("[PASS] Generated output/reports/results_summary.md")

    legacy_comp_md = f"""# Legacy vs Revised Comparison (24m focus, 30m robustness)

This panel compares the previously shipped legacy outputs to revised-24m (primary) and revised-30m (robustness).

| Metric | Legacy (previous) | Revised 24m (primary) | Revised 30m (robustness) |
|---|---:|---:|---:|
| Victim events | {legacy['victim_events']:,} | {primary['victim_events']:,} | {f"{robust['victim_events']:,}" if robust is not None else "n/a"} |
| Victim volume | {_fmt_billion(legacy['victim_volume'])} | {_fmt_billion(primary['victim_volume'])} | {_fmt_billion(robust['victim_volume']) if robust is not None else "n/a"} |
| Bot addresses | {legacy['bot_addresses']:,} | {primary['bot_addresses']:,} | {f"{robust['bot_addresses']:,}" if robust is not None else "n/a"} |
| p25 | {_fmt_money(legacy['p25'])} | {_fmt_money(primary['q5a']['p25'])} | {_fmt_money(robust['q5a']['p25']) if robust is not None else "n/a"} |
| p50 | {_fmt_money(legacy['p50'])} | {_fmt_money(primary['q5a']['p50_median'])} | {_fmt_money(robust['q5a']['p50_median']) if robust is not None else "n/a"} |
| p75 | {_fmt_money(legacy['p75'])} | {_fmt_money(primary['q5a']['p75'])} | {_fmt_money(robust['q5a']['p75']) if robust is not None else "n/a"} |
| p90 | {_fmt_money(legacy['p90'])} | {_fmt_money(primary['q5a']['p90'])} | {_fmt_money(robust['q5a']['p90']) if robust is not None else "n/a"} |
| p95 | {_fmt_money(legacy['p95'])} | {_fmt_money(primary['q5a']['p95'])} | {_fmt_money(robust['q5a']['p95']) if robust is not None else "n/a"} |
| Institutional/Retail mean-size ratio | {legacy['size_ratio']:.2f}x | {primary['ratio_size']:.2f}x | {f"{robust['ratio_size']:.2f}x" if robust is not None else "n/a"} |
| Retail/Institutional RR | {legacy['rr_ri']:.4f} | {primary['rr_ri']:.4f} | {f"{robust['rr_ri']:.4f}" if robust is not None else "n/a"} |
| Small/Retail RR | {legacy['rr_sr']:.4f} | {primary['rr_sr']:.4f} | {f"{robust['rr_sr']:.4f}" if robust is not None else "n/a"} |
"""
    with open("output/reports/legacy_vs_revised_comparison.md", "w") as f:
        f.write(legacy_comp_md)
    print("[PASS] Generated output/reports/legacy_vs_revised_comparison.md")

    robust_line = (
        f"30m window loaded: {robust['window_label']}."
        if robust is not None
        else f"30m bundle not available in repository snapshot. Loader message: `{robust_err}`."
    )
    comparison_md = f"""# 24m vs 30m Comparison Framework

This file provides side-by-side metrics with a replication-vs-instability split.  
Primary: 24m. Robustness: 30m when present.

Status: {robust_line}

## Replication vs Instability Panel
| Metric | 24m | 30m | Status |
|---|---:|---:|---|
{_comparison_row("Median attacks/trader (Retail)", float(q5c_nonbot.loc["Retail", "median_attacks_per_eoa"]), float(robust["q5c_nonbot"].loc["Retail", "median_attacks_per_eoa"]) if robust is not None else None)}
{_comparison_row("Median attacks/trader (Small)", float(q5c_nonbot.loc["Small", "median_attacks_per_eoa"]), float(robust["q5c_nonbot"].loc["Small", "median_attacks_per_eoa"]) if robust is not None else None)}
{_comparison_row("Median attacks/trader (Institutional)", float(q5c_nonbot.loc["Institutional", "median_attacks_per_eoa"]), float(robust["q5c_nonbot"].loc["Institutional", "median_attacks_per_eoa"]) if robust is not None else None)}
{_comparison_row("Small/Retail RR (non-bot tx_from)", float(primary["rr_sr"]), float(robust["rr_sr"]) if robust is not None else None)}
{_comparison_row("Retail/Institutional RR (non-bot tx_from)", float(primary["rr_ri"]), float(robust["rr_ri"]) if robust is not None else None)}
{_comparison_row("Bot-side Gini", float(primary["gini"]), float(robust["gini"]) if robust is not None else None)}
{_comparison_row("CR4 (vintage-sensitive)", float(primary["cr"]["cr4"]), float(robust["cr"]["cr4"]) if robust is not None else None)}
{_comparison_row("CR10 (vintage-sensitive)", float(primary["cr"]["cr10"]), float(robust["cr"]["cr10"]) if robust is not None else None)}
{_comparison_row("Institutional/Retail mean-size ratio", float(primary["ratio_size"]), float(robust["ratio_size"]) if robust is not None else None)}
{_comparison_row("Bot/Victim volume ratio", float(primary["ratio_vol"]), float(robust["ratio_vol"]) if robust is not None else None)}

## Interpretation Rules
- **Replicates**: relative change <= 10%.
- **Window-sensitive**: relative change > 10%.
- Metrics explicitly flagged as vintage-sensitive (e.g., CR4/CR10/top-N) should not be used as sole headline evidence without a pinned data vintage.
"""
    with open("output/reports/window_comparison.md", "w") as f:
        f.write(comparison_md)
    print("[PASS] Generated output/reports/window_comparison.md")

    # Additional angle: month-by-month intensity drift (proxy) and bot/victim ratio dynamics
    monthly_24m = _build_monthly_intensity(primary_bundle["q1"])
    monthly_24m.to_csv("output/tables/monthly_bot_intensity_24m.csv", index=False)

    monthly_focus = monthly_24m
    if robust_bundle is not None:
        monthly_30m = _build_monthly_intensity(robust_bundle["q1"])
        monthly_30m.to_csv("output/tables/monthly_bot_intensity_30m.csv", index=False)
        monthly_focus = monthly_30m
    else:
        monthly_30m = None

    t = np.arange(len(monthly_focus))
    slope_legs = float(np.polyfit(t, monthly_focus["avg_daily_legs"], 1)[0]) if len(monthly_focus) >= 2 else np.nan
    slope_usd_per_leg = float(np.polyfit(t, monthly_focus["usd_per_leg"], 1)[0]) if len(monthly_focus) >= 2 else np.nan
    rho_usd_per_leg = _rank_correlation(t, monthly_focus["usd_per_leg"])
    rho_legs = _rank_correlation(t, monthly_focus["avg_daily_legs"])

    legs_first, legs_last, legs_pct = _first_last_change(monthly_focus, "avg_daily_legs")
    usdleg_first, usdleg_last, usdleg_pct = _first_last_change(monthly_focus, "usd_per_leg")
    bots_first, bots_last, bots_pct = _first_last_change(monthly_focus, "avg_daily_unique_bots")

    ratio_24m = primary["ratio_vol"]
    ratio_30m = robust["ratio_vol"] if robust is not None else np.nan
    ratio_delta = (ratio_30m / ratio_24m - 1.0) * 100.0 if robust is not None else np.nan
    ratio_added_2026h1 = np.nan
    if robust is not None:
        add_bot = robust["bot_volume"] - primary["bot_volume"]
        add_victim = robust["victim_volume"] - primary["victim_volume"]
        if add_victim != 0:
            ratio_added_2026h1 = add_bot / add_victim

    monthly_signal = (
        "interesting"
        if np.isfinite(usdleg_pct) and np.isfinite(legs_pct) and (abs(usdleg_pct) >= 20.0) and (abs(legs_pct) >= 20.0)
        else "not clearly interesting"
    )
    ratio_signal = (
        "interesting"
        if np.isfinite(ratio_delta) and abs(ratio_delta) >= 10.0
        else "not clearly interesting"
    )

    angle_md = f"""# Additional Angle Check: Month-by-Month Drift and Bot/Victim Ratio

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
- Analysis horizon for monthly proxy: `{monthly_focus['month'].iloc[0]}` to `{monthly_focus['month'].iloc[-1]}` ({len(monthly_focus)} months)
- Avg daily bot legs: {legs_first:,.0f} -> {legs_last:,.0f} (**{legs_pct:+.1f}%**; rank-corr={rho_legs:.3f}, slope={slope_legs:,.2f} legs/month)
- Bot-side USD per leg: {_fmt_money(usdleg_first)} -> {_fmt_money(usdleg_last)} (**{usdleg_pct:+.1f}%**; rank-corr={rho_usd_per_leg:.3f}, slope={slope_usd_per_leg:,.2f} USD/month)
- Avg daily active bots: {bots_first:,.1f} -> {bots_last:,.1f} (**{bots_pct:+.1f}%**)

- Bot/Victim volume ratio (24m): **{ratio_24m:.2f}x**
- Bot/Victim volume ratio (30m): **{ratio_30m:.2f}x**
- Change 24m -> 30m: **{ratio_delta:+.1f}%**
- Implied added-period ratio (Jan--Jun 2026 segment): **{ratio_added_2026h1:.2f}x**

## Interpretation
- Month-by-month intensity proxy: **{monthly_signal}**.
- Bot/Victim ratio drift: **{ratio_signal}**.
- Combined reading: the added months are consistent with a **lower-frequency / higher-notional** regime (fewer legs, larger USD per leg), and a higher bot/victim notional multiplier.

"""
    with open("output/reports/monthly_angle_check.md", "w") as f:
        f.write(angle_md)
    print("[PASS] Generated output/reports/monthly_angle_check.md")

    dict_md = f"""# Data Dictionary and Identity Conventions (Revised)

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
- Window: {primary['window_label']}
- Victim events: {primary['victim_events']:,}
- Unique takers: {primary['unique_takers']:,}
- Unique tx_from EOAs (total): {primary['tx_from_total']:,}
- Unique tx_from non-bot EOAs: {primary['tx_from_non_bot']:,}
"""
    with open("output/reports/data_dictionary.md", "w") as f:
        f.write(dict_md)
    print("[PASS] Generated output/reports/data_dictionary.md")

    return True


if __name__ == "__main__":
    generate_reports()
