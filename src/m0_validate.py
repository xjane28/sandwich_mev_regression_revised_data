import json
import os
import shutil
from datetime import datetime, timezone

import numpy as np
import pandas as pd


REVISED_FILE_MAP = {
    "query0a_data_quality.csv": "query0a_data_quality.csv",
    "query0b_router_check.csv": "query0b_router_check.csv",
    "query1_mev_volume.csv": "query1_mev_volume_v2.csv",
    "query3_full_bot_distribution.csv": "query3_full_bot_distribution_v2.csv",
    "query4_top_bots.csv": "query4_top_bots_v2.csv",
    "query5a_break_points.csv": "query5a_break_points_v2.csv",
    "query5b_victim_impact.csv": "query5b_victim_impact_v2.csv",
    "query5c_repeat_victimization.csv": "query5c_repeat_victimization_v2.csv",
    "query5d_trade_size_distribution.csv": "query5d_trade_size_distribution.csv",
    "query_protocol_vulnerability.csv": "query_protocol_vulnerability_v2.csv",
}

LEGACY_FILE_MAP = {
    "query1_mev_volume.csv": "query1_mev_volume.csv",
    "query3_full_bot_distribution.csv": "query3_full_bot_distribution.csv",
    "query4_top_bots.csv": "query4_top_bots.csv",
    "query5a_break_points.csv": "query5a_break_points.csv",
    "query5b_victim_impact.csv": "query5b_victim_impact.csv",
    "query_protocol_vulnerability.csv": "query_protocol_vulnerability.csv",
}

QUERY_IDS = {
    "query0a_data_quality": 8439243,
    "query0b_router_check": 8439361,
    "query1_mev_volume_v2": 6440670,
    "query3_full_bot_distribution_v2": 6562142,
    "query4_top_bots_v2": 6440710,
    "query5a_break_points_v2": 6440810,
    "query5b_victim_impact_v2": 6440827,
    "query5c_repeat_victimization_v2": 8440229,
    "query5d_trade_size_distribution": 8440084,
    "query_protocol_vulnerability_v2": 8446953,
}


def setup_directories():
    os.makedirs("output/tables", exist_ok=True)
    os.makedirs("output/figures", exist_ok=True)
    os.makedirs("output/reports", exist_ok=True)
    os.makedirs("output/logs", exist_ok=True)
    os.makedirs("data", exist_ok=True)


def parse_utc_date(series):
    return pd.to_datetime(series.astype(str).str.replace(" UTC", "", regex=False))


def _normalize_numeric(df, cols):
    for c in cols:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    return df


def q5b_tier_address_col(q5b):
    if "addresses_with_trade_in_tier" in q5b.columns:
        return "addresses_with_trade_in_tier"
    if "unique_victims" in q5b.columns:
        return "unique_victims"
    raise KeyError("q5b must include `addresses_with_trade_in_tier` (preferred) or legacy `unique_victims`.")


def _revised_data_dirs():
    root = os.path.join("fetch", "data")
    if not os.path.isdir(root):
        return []
    dirs = []
    for name in os.listdir(root):
        full = os.path.join(root, name)
        if os.path.isdir(full) and name.startswith("revised"):
            dirs.append(full)
    return sorted(dirs)


def _infer_window_key_from_q1(path):
    if not os.path.exists(path):
        return "unknown"
    q1 = pd.read_csv(path, usecols=["date"])
    dates = parse_utc_date(q1["date"])
    day_count = int(dates.nunique())
    if day_count == 731:
        return "24m"
    if day_count == 912:
        return "30m"
    return f"{day_count}d"


def list_available_windows():
    windows = []
    for full in _revised_data_dirs():
        name = os.path.basename(full)
        q1_path = os.path.join(full, "query1_mev_volume_v2.csv")
        key = _infer_window_key_from_q1(q1_path)
        min_date = None
        max_date = None
        day_count = None
        if os.path.exists(q1_path):
            q1 = pd.read_csv(q1_path, usecols=["date"])
            dates = parse_utc_date(q1["date"])
            min_date = dates.min()
            max_date = dates.max()
            day_count = int(dates.nunique())
        windows.append(
            {
                "key": key,
                "name": name,
                "path": full,
                "day_count": day_count,
                "min_date": min_date,
                "max_date": max_date,
            }
        )
    windows.sort(key=lambda w: (w["max_date"] if w["max_date"] is not None else pd.Timestamp.min, w["name"]))
    return windows


def _select_window(window=None):
    windows = list_available_windows()
    if not windows:
        return None

    desired = window or os.environ.get("SMEV_WINDOW")
    if not desired:
        preferred = [w for w in windows if w["key"] == "24m"]
        if preferred:
            return preferred[-1]
        return windows[-1]

    desired_l = desired.lower()
    matching = [
        w
        for w in windows
        if w["key"] == desired_l
        or w["name"].lower() == desired_l
        or desired_l in w["name"].lower()
    ]
    if not matching:
        available = ", ".join(sorted({w["key"] for w in windows}))
        raise ValueError(f"Requested window '{desired}' not found. Available: {available}")
    return matching[-1]


def _copy_required_files(src_dir, file_map):
    for legacy_name, revised_name in file_map.items():
        src = os.path.join(src_dir, revised_name)
        dst = os.path.join("data", legacy_name)
        if not os.path.exists(src):
            raise FileNotFoundError(f"Missing required revised input CSV: {src}")
        shutil.copy(src, dst)


def ensure_data_files(window=None):
    revised_dirs = _revised_data_dirs()
    if revised_dirs:
        selected = _select_window(window=window)
        _copy_required_files(selected["path"], REVISED_FILE_MAP)
        return selected

    for dst_name, src_name in LEGACY_FILE_MAP.items():
        src = os.path.join("fetch", src_name)
        dst = os.path.join("data", dst_name)
        if os.path.exists(src):
            shutil.copy(src, dst)
        elif not os.path.exists(dst):
            raise FileNotFoundError(f"Missing required input CSV file: {src_name} in ./data/ and ./fetch/")

    return None


def _build_manifest(selected_window):
    copied_files = sorted(REVISED_FILE_MAP.keys())
    latest_mtime = None
    for name in copied_files:
        p = os.path.join("data", name)
        if os.path.exists(p):
            mt = os.path.getmtime(p)
            latest_mtime = mt if latest_mtime is None else max(latest_mtime, mt)

    pull_date = None
    if latest_mtime is not None:
        pull_date = datetime.fromtimestamp(latest_mtime, tz=timezone.utc).strftime("%Y-%m-%d")

    all_windows = []
    for w in list_available_windows():
        all_windows.append(
            {
                "key": w["key"],
                "name": w["name"],
                "day_count": w["day_count"],
                "min_date": w["min_date"].strftime("%Y-%m-%d") if w["min_date"] is not None else None,
                "max_date": w["max_date"].strftime("%Y-%m-%d") if w["max_date"] is not None else None,
            }
        )

    selected_payload = None
    if selected_window is not None:
        selected_payload = {
            "key": selected_window["key"],
            "name": selected_window["name"],
            "day_count": selected_window["day_count"],
            "min_date": selected_window["min_date"].strftime("%Y-%m-%d") if selected_window["min_date"] is not None else None,
            "max_date": selected_window["max_date"].strftime("%Y-%m-%d") if selected_window["max_date"] is not None else None,
            "source_dir": selected_window["path"],
        }

    manifest = {
        "generated_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "selected_window": selected_payload,
        "available_windows": all_windows,
        "query_ids": QUERY_IDS,
        "copied_data_files": copied_files,
        "data_pull_date_utc": pull_date,
    }
    return manifest


def write_manifest(manifest, output_path="output/reports/reproducibility_manifest.json"):
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(manifest, f, indent=2)


def load_data_bundle(window=None, write_repro_manifest=True):
    setup_directories()
    selected = ensure_data_files(window=window)
    manifest = _build_manifest(selected)
    if write_repro_manifest:
        write_manifest(manifest)

    na_vals = ["<nil>", "NULL", "null", "NaN", "nan"]

    q1 = pd.read_csv("data/query1_mev_volume.csv", na_values=na_vals)
    q1 = _normalize_numeric(
        q1,
        ["sandwich_trade_count", "total_sandwich_volume_usd", "unique_sandwich_bots", "unique_transactions", "priced_trade_count"],
    )
    q1["date_parsed"] = parse_utc_date(q1["date"])

    q3 = pd.read_csv("data/query3_full_bot_distribution.csv", na_values=na_vals)
    q3 = _normalize_numeric(q3, ["total_volume_usd", "total_trades", "priced_trades"])

    q4 = pd.read_csv("data/query4_top_bots.csv", na_values=na_vals)
    q4 = _normalize_numeric(q4, ["avg_trade_size_usd", "days_active", "total_sandwich_trades", "total_volume_usd", "priced_trades"])
    q4["first_seen_parsed"] = parse_utc_date(q4["first_seen"])
    q4["last_seen_parsed"] = parse_utc_date(q4["last_seen"])

    prot = pd.read_csv("data/query_protocol_vulnerability.csv", na_values=na_vals)
    if "sandwich_count" not in prot.columns and "victim_trade_count" in prot.columns:
        prot = prot.rename(columns={"victim_trade_count": "sandwich_count"})
    if "unique_victims" not in prot.columns:
        if "unique_eoas_in_protocol" in prot.columns:
            prot["unique_victims"] = prot["unique_eoas_in_protocol"]
        elif "unique_takers_in_protocol" in prot.columns:
            prot["unique_victims"] = prot["unique_takers_in_protocol"]
    prot = _normalize_numeric(prot, ["avg_trade_size", "sandwich_count", "total_volume_usd", "unique_victims", "unique_takers_in_protocol", "unique_eoas_in_protocol"])

    q5a = pd.read_csv("data/query5a_break_points.csv", na_values=na_vals)
    if "total_victims" not in q5a.columns:
        if "total_victim_trades" in q5a.columns:
            q5a["total_victims"] = q5a["total_victim_trades"]
        elif "unique_victim_addresses" in q5a.columns:
            q5a["total_victims"] = q5a["unique_victim_addresses"]
    q5a = _normalize_numeric(
        q5a,
        ["max_value", "mean_value", "min_value", "p25", "p50_median", "p75", "p90", "p95", "total_victims", "total_victim_trades", "unique_victim_addresses"],
    )

    q5b = pd.read_csv("data/query5b_victim_impact.csv", na_values=na_vals)
    rename_map = {}
    if "victim_count" not in q5b.columns and "victim_trades" in q5b.columns:
        rename_map["victim_trades"] = "victim_count"
    if "addresses_with_trade_in_tier" not in q5b.columns and "unique_victims" in q5b.columns:
        rename_map["unique_victims"] = "addresses_with_trade_in_tier"
    if "pct_of_victims" not in q5b.columns and "pct_of_trades" in q5b.columns:
        rename_map["pct_of_trades"] = "pct_of_victims"
    if rename_map:
        q5b = q5b.rename(columns=rename_map)
    if "unique_victims" in q5b.columns and "addresses_with_trade_in_tier" in q5b.columns:
        q5b = q5b.drop(columns=["unique_victims"])
    q5b = _normalize_numeric(
        q5b,
        [
            "avg_tx_size",
            "max_tx",
            "min_tx",
            "pct_of_victims",
            "pct_of_volume",
            "total_volume",
            "addresses_with_trade_in_tier",
            "unique_victims",
            "victim_count",
            "cutoff_p50",
            "cutoff_p90",
        ],
    )

    q0a = pd.read_csv("data/query0a_data_quality.csv", na_values=na_vals) if os.path.exists("data/query0a_data_quality.csv") else pd.DataFrame()
    q0b = pd.read_csv("data/query0b_router_check.csv", na_values=na_vals) if os.path.exists("data/query0b_router_check.csv") else pd.DataFrame()
    q5c = pd.read_csv("data/query5c_repeat_victimization.csv", na_values=na_vals) if os.path.exists("data/query5c_repeat_victimization.csv") else pd.DataFrame()
    q5d = pd.read_csv("data/query5d_trade_size_distribution.csv", na_values=na_vals) if os.path.exists("data/query5d_trade_size_distribution.csv") else pd.DataFrame()

    if not q0b.empty:
        q0b = _normalize_numeric(
            q0b,
            ["victim_trades", "total_volume_usd", "avg_trade_usd", "max_trade_usd", "trades_ge_10k", "protocols_touched", "distinct_senders"],
        )
        if "first_seen" in q0b.columns:
            q0b["first_seen_parsed"] = parse_utc_date(q0b["first_seen"])
        if "last_seen" in q0b.columns:
            q0b["last_seen_parsed"] = parse_utc_date(q0b["last_seen"])

    if not q5c.empty:
        q5c = _normalize_numeric(
            q5c,
            ["is_known_bot", "unique_eoas", "attack_events", "attacks_per_eoa", "max_attacks_single_eoa", "median_attacks_per_eoa", "tier_volume_usd", "avg_median_trade_usd", "cutoff_p50", "cutoff_p90"],
        )

    if not q5d.empty:
        q5d = _normalize_numeric(
            q5d,
            ["pctile_in_tier", "trades_in_bin", "lower_edge_usd", "upper_edge_usd", "mean_usd", "volume_usd", "cutoff_p50", "cutoff_p90"],
        )

    return {
        "q1": q1,
        "q3": q3,
        "q4": q4,
        "prot": prot,
        "q5a": q5a,
        "q5b": q5b,
        "q0a": q0a,
        "q0b": q0b,
        "q5c": q5c,
        "q5d": q5d,
        "manifest": manifest,
    }


def load_data(window=None):
    bundle = load_data_bundle(window=window, write_repro_manifest=True)
    return bundle["q1"], bundle["q3"], bundle["q4"], bundle["prot"], bundle["q5a"], bundle["q5b"]


def run_validation():
    q1, q3, q4, prot, q5a, q5b = load_data()
    checks = []

    def add_check(cid, desc, expected, computed, passed):
        checks.append(
            {
                "check_id": cid,
                "description": desc,
                "expected": expected,
                "computed": str(computed),
                "status": "PASS" if passed else "FAIL",
            }
        )

    min_date = q1["date_parsed"].min()
    max_date = q1["date_parsed"].max()
    expected_days = (max_date - min_date).days + 1
    actual_days = q1["date_parsed"].nunique()
    add_check("Q1-ROWS", "Daily series non-empty", "> 0", len(q1), len(q1) > 0)
    add_check("Q1-DATES-UNIQUE", "Date uniqueness", "nunique == rows", f"{actual_days} vs {len(q1)}", actual_days == len(q1))
    add_check("Q1-DATES-CONTIG", "Date continuity", f"{expected_days}", actual_days, actual_days == expected_days)
    add_check("Q1-VOL-POS", "Total daily volume positive", "> 0", f"{q1['total_sandwich_volume_usd'].sum():.2f}", q1["total_sandwich_volume_usd"].sum() > 0)
    add_check("Q1-TRADES-POS", "Total daily trades positive", "> 0", int(q1["sandwich_trade_count"].sum()), q1["sandwich_trade_count"].sum() > 0)
    add_check("Q1-BOTS-POS", "Mean active bots positive", "> 0", f"{q1['unique_sandwich_bots'].mean():.2f}", q1["unique_sandwich_bots"].mean() > 0)

    add_check("Q3-ROWS", "Bot distribution non-empty", "> 0", len(q3), len(q3) > 0)
    add_check("Q3-UNIQ-ADDR", "Bot addresses unique", "unique == rows", f"{q3['bot_address'].nunique()} vs {len(q3)}", q3["bot_address"].nunique() == len(q3))
    add_check("Q3-HAS-VOLUME", "Has measurable bot volumes", "> 0 non-null rows", q3["total_volume_usd"].notna().sum(), q3["total_volume_usd"].notna().sum() > 0)

    add_check("Q4-ROWS", "Bot profile non-empty", "> 0", len(q4), len(q4) > 0)
    add_check("Q4-ADDR-SET", "q4 address set identical to q3", "True", set(q3["bot_address"]) == set(q4["bot_address"]), set(q3["bot_address"]) == set(q4["bot_address"]))
    add_check("Q4-DAYS-POS", "days_active positive", "all >= 1", int((q4["days_active"] >= 1).all()), (q4["days_active"] >= 1).all())

    q3_merged = q3.merge(q4[["bot_address", "total_volume_usd"]], on="bot_address", suffixes=("_q3", "_q4"))
    vol_diff = (q3_merged["total_volume_usd_q3"] - q3_merged["total_volume_usd_q4"]).abs()
    max_abs_diff_vol = vol_diff.max(skipna=True)
    add_check("Q4-VOL-MATCH", "Per-address volume alignment q3 vs q4", "< 0.01 max abs diff", f"{max_abs_diff_vol:.6f}", max_abs_diff_vol < 0.01)

    p_cols = ["p25", "p50_median", "p75", "p90", "p95"]
    add_check("Q5A-ONE-ROW", "q5a single summary row", "1", len(q5a), len(q5a) == 1)
    add_check("Q5A-PERCENTILES", "q5a percentile columns present", "all present", all(c in q5a.columns for c in p_cols), all(c in q5a.columns for c in p_cols))
    if len(q5a) == 1 and all(c in q5a.columns for c in p_cols):
        row = q5a.iloc[0]
        p_ordered = row["p25"] <= row["p50_median"] <= row["p75"] <= row["p90"] <= row["p95"]
        add_check("Q5A-P-ORDER", "Percentiles non-decreasing", "True", p_ordered, p_ordered)
        add_check("Q5A-MINMAX", "min <= p25 and p95 <= max", "True", row["min_value"] <= row["p25"] and row["p95"] <= row["max_value"], row["min_value"] <= row["p25"] and row["p95"] <= row["max_value"])

    add_check("Q5B-ROWS", "q5b has tier rows", ">= 3", len(q5b), len(q5b) >= 3)
    tier_set = set(q5b["victim_tier"].dropna().unique())
    expected_tiers = {"Retail", "Small", "Institutional"}
    add_check("Q5B-TIERS", "Retail/Small/Institutional present", str(expected_tiers), tier_set, expected_tiers.issubset(tier_set))
    add_check("Q5B-TRADES-POS", "Tier trade counts positive", "all > 0", int((q5b["victim_count"] > 0).all()), (q5b["victim_count"] > 0).all())
    add_check("Q5B-VOLUME-POS", "Tier volumes positive", "all > 0", int((q5b["total_volume"] > 0).all()), (q5b["total_volume"] > 0).all())
    if "pct_of_victims" in q5b.columns:
        pct_trade_sum = q5b["pct_of_victims"].sum()
        add_check("Q5B-PCT-TRADES", "Tier trade shares sum to 100", "100 ± 0.05", f"{pct_trade_sum:.6f}", abs(pct_trade_sum - 100.0) <= 0.05)
    if "pct_of_volume" in q5b.columns:
        pct_vol_sum = q5b["pct_of_volume"].sum()
        add_check("Q5B-PCT-VOL", "Tier volume shares sum to 100", "100 ± 0.05", f"{pct_vol_sum:.6f}", abs(pct_vol_sum - 100.0) <= 0.05)
    if {"cutoff_p50", "cutoff_p90"}.issubset(q5b.columns):
        add_check("Q5B-CUTOFF-P50-CONS", "cutoff_p50 constant across tiers", "nunique == 1", q5b["cutoff_p50"].nunique(), q5b["cutoff_p50"].nunique() == 1)
        add_check("Q5B-CUTOFF-P90-CONS", "cutoff_p90 constant across tiers", "nunique == 1", q5b["cutoff_p90"].nunique(), q5b["cutoff_p90"].nunique() == 1)

    add_check("PROT-ROWS", "Protocol summary non-empty", "> 0", len(prot), len(prot) > 0)
    add_check("PROT-HAS-UNISWAP", "Contains uniswap row", "True", "uniswap" in set(prot["project"].str.lower()), "uniswap" in set(prot["project"].str.lower()))
    add_check("PROT-VOL-POS", "Protocol volume sum positive", "> 0", f"{prot['total_volume_usd'].sum():.2f}", prot["total_volume_usd"].sum() > 0)

    vol_q1 = q1["total_sandwich_volume_usd"].sum()
    vol_q3 = q3["total_volume_usd"].sum(skipna=True)
    trades_q1 = q1["sandwich_trade_count"].sum()
    trades_q4 = q4["total_sandwich_trades"].sum()
    vol_q5b = q5b["total_volume"].sum()
    prot_vol_sum = prot["total_volume_usd"].sum()
    prot_cnt_sum = prot["sandwich_count"].sum()
    total_victim_events_q5b = q5b["victim_count"].sum()
    total_victim_events_q5a = q5a.loc[0, "total_victims"]

    add_check("CROSS-VOL-Q1-Q3", "q1 volume equals q3 volume", "abs diff <= 1", f"{abs(vol_q1-vol_q3):.6f}", abs(vol_q1 - vol_q3) <= 1.0)
    add_check("CROSS-TRADES-Q1-Q4", "q1 trades equals q4 trades", "exact", f"{int(trades_q1)} vs {int(trades_q4)}", int(trades_q1) == int(trades_q4))
    add_check("CROSS-VIC-Q5A-Q5B", "q5a events equals q5b events", "exact", f"{int(total_victim_events_q5a)} vs {int(total_victim_events_q5b)}", int(total_victim_events_q5a) == int(total_victim_events_q5b))
    add_check("CROSS-VIC-Q5B-PROT", "q5b events equals protocol events", "exact", f"{int(total_victim_events_q5b)} vs {int(prot_cnt_sum)}", int(total_victim_events_q5b) == int(prot_cnt_sum))
    add_check("CROSS-VOL-Q5B-PROT", "q5b volume equals protocol volume", "abs diff <= 1", f"{abs(vol_q5b-prot_vol_sum):.6f}", abs(vol_q5b - prot_vol_sum) <= 1.0)

    report_lines = [
        "# Data and Schema Validation Report\n",
        "## Summary of Assertions\n",
        "| Check ID | Description | Expected | Computed | Status |",
        "|---|---|---|---|---|",
    ]
    for c in checks:
        report_lines.append(f"| {c['check_id']} | {c['description']} | {c['expected']} | {c['computed']} | **{c['status']}** |")

    report_lines.append("\n## Data Snapshot\n")
    report_lines.append(f"- Daily window: {min_date.strftime('%Y-%m-%d')} to {max_date.strftime('%Y-%m-%d')} ({actual_days} days).")
    report_lines.append(f"- Bot-side totals: {int(trades_q1):,} trades, ${vol_q1/1e9:,.2f}B volume, {len(q4):,} addresses.")
    report_lines.append(f"- Victim-side totals: {int(total_victim_events_q5b):,} events, ${vol_q5b/1e9:,.2f}B volume.")
    report_lines.append(f"- Protocol rows: {len(prot)}, uniswap share: {(prot[prot['project'].str.lower() == 'uniswap']['total_volume_usd'].sum() / prot_vol_sum) * 100:.2f}% of victim-side volume.")
    report_lines.append(f"- Missing bot volumes in q3: {int(q3['total_volume_usd'].isna().sum())}.")

    report_path = "output/reports/validation_report.md"
    with open(report_path, "w") as f:
        f.write("\n".join(report_lines) + "\n")

    failures = [c for c in checks if c["status"] == "FAIL"]
    if failures:
        err_msg = "Validation failed for checks:\n" + "\n".join(
            [f"{c['check_id']}: expected {c['expected']}, computed {c['computed']}" for c in failures]
        )
        raise RuntimeError(err_msg)

    print(f"[PASS] m0_validate: All {len(checks)} checks passed successfully. Report written to {report_path}")
    return True


if __name__ == "__main__":
    run_validation()
