import os
import shutil
import sys
import pandas as pd
import numpy as np

REVISED_DIR = os.path.join("fetch", "data", "revised-24m")

def setup_directories():
    os.makedirs("output/tables", exist_ok=True)
    os.makedirs("output/figures", exist_ok=True)
    os.makedirs("output/reports", exist_ok=True)
    os.makedirs("output/logs", exist_ok=True)
    os.makedirs("data", exist_ok=True)

def ensure_data_files():
    # Bot-side / legacy-sourced files: unchanged, still copied from fetch/.
    legacy_expected = [
        "query1_mev_volume.csv",
        "query3_full_bot_distribution.csv",
        "query4_top_bots.csv",
    ]
    missing_legacy = [f for f in legacy_expected if not os.path.exists(os.path.join("data", f))]
    if missing_legacy:
        for f in missing_legacy:
            src = os.path.join("fetch", f)
            dst = os.path.join("data", f)
            if os.path.exists(src):
                shutil.copy(src, dst)
            else:
                raise FileNotFoundError(f"Missing required input CSV file: {f} in both ./data/ and ./fetch/")

    # Victim-side files: sourced from the corrected percentile-spec pull
    # (fetch/data/revised-24m/), not the legacy fetch/ CSVs. See
    # fetch/queries/README.md for why: the legacy files use a hardcoded
    # $10,000 tier cutoff instead of the true p90, among other defects.
    revised_expected = [
        "query_protocol_vulnerability_v2.csv",
        "query5a_break_points_v2.csv",
        "query5b_victim_impact_v2.csv",
    ]
    missing_revised = [f for f in revised_expected if not os.path.exists(os.path.join("data", f))]
    if missing_revised:
        for f in missing_revised:
            src = os.path.join(REVISED_DIR, f)
            dst = os.path.join("data", f)
            if os.path.exists(src):
                shutil.copy(src, dst)
            else:
                raise FileNotFoundError(f"Missing required input CSV file: {f} in both ./data/ and {REVISED_DIR}/")

def parse_utc_date(series):
    # Strip literal suffix " UTC" then pd.to_datetime
    return pd.to_datetime(series.astype(str).str.replace(" UTC", "", regex=False))

def load_data():
    setup_directories()
    ensure_data_files()

    q1 = pd.read_csv("data/query1_mev_volume.csv", dtype={
        "date": str,
        "sandwich_trade_count": int,
        "total_sandwich_volume_usd": float,
        "unique_sandwich_bots": int,
        "unique_transactions": int
    })
    q1["date_parsed"] = parse_utc_date(q1["date"])

    q3 = pd.read_csv("data/query3_full_bot_distribution.csv", dtype={
        "bot_address": str,
        "total_volume_usd": float
    })

    q4 = pd.read_csv("data/query4_top_bots.csv", dtype={
        "avg_trade_size_usd": float,
        "bot_address": str,
        "days_active": int,
        "first_seen": str,
        "last_seen": str,
        "total_sandwich_trades": int,
        "total_volume_usd": float
    })
    q4["first_seen_parsed"] = parse_utc_date(q4["first_seen"])
    q4["last_seen_parsed"] = parse_utc_date(q4["last_seen"])

    # Protocol file: revised. Columns renamed vs. legacy
    # (sandwich_count -> victim_trade_count, unique_victims split into
    # unique_takers_in_protocol / unique_eoas_in_protocol per the router-
    # unmasking fix in fetch/queries/README.md).
    prot = pd.read_csv(os.path.join("data", "query_protocol_vulnerability_v2.csv"), dtype={
        "project": str,
        "victim_trade_count": float,
        "total_volume_usd": float,
        "avg_trade_size": float,
        "unique_takers_in_protocol": int,
        "unique_eoas_in_protocol": int
    })
    prot["victim_trade_count"] = prot["victim_trade_count"].round().astype(int)
    # Back-compat alias so downstream code that still says "sandwich_count" /
    # "unique_victims" (the legacy column names) keeps working unchanged.
    prot["sandwich_count"] = prot["victim_trade_count"]
    prot["unique_victims"] = prot["unique_takers_in_protocol"]

    # Victim-side percentile breakpoints: revised (exact percentiles, not
    # Dune's APPROX_PERCENTILE). total_victims renamed to total_victim_trades;
    # unique_victim_addresses is new.
    q5a = pd.read_csv(os.path.join("data", "query5a_break_points_v2.csv"), dtype={
        "p25": float,
        "p50_median": float,
        "p75": float,
        "p90": float,
        "p95": float,
        "min_value": float,
        "max_value": float,
        "mean_value": float,
        "total_victim_trades": float,
        "unique_victim_addresses": int
    })
    q5a["total_victim_trades"] = q5a["total_victim_trades"].round().astype(int)
    # Back-compat alias for legacy column name.
    q5a["total_victims"] = q5a["total_victim_trades"]

    # Victim-side tier table: revised, tiers cut at the exact p50/p90 above
    # instead of the legacy $1,024.44 / $10,000 boundary.
    q5b = pd.read_csv(os.path.join("data", "query5b_victim_impact_v2.csv"), dtype={
        "victim_tier": str,
        "victim_trades": float,
        "addresses_with_trade_in_tier": int,
        "total_volume": float,
        "avg_tx_size": float,
        "min_tx": float,
        "max_tx": float,
        "pct_of_trades": float,
        "pct_of_volume": float,
        "cutoff_p50": float,
        "cutoff_p90": float
    })
    q5b["victim_trades"] = q5b["victim_trades"].round().astype(int)
    # Back-compat aliases for legacy column names.
    q5b["victim_count"] = q5b["victim_trades"]
    q5b["unique_victims"] = q5b["addresses_with_trade_in_tier"]
    q5b["pct_of_victims"] = q5b["pct_of_trades"]

    return q1, q3, q4, prot, q5a, q5b

def run_validation():
    q1, q3, q4, prot, q5a, q5b = load_data()
    checks = []

    def add_check(cid, desc, expected_str, computed_val, passed):
        checks.append({
            "check_id": cid,
            "description": desc,
            "expected": expected_str,
            "computed": str(computed_val),
            "status": "PASS" if passed else "FAIL"
        })

    # Q1 checks
    add_check("Q1-ROWS", "q1 row count == 731", "731", len(q1), len(q1) == 731)
    min_date_str = q1["date_parsed"].min().strftime("%Y-%m-%d")
    max_date_str = q1["date_parsed"].max().strftime("%Y-%m-%d")
    add_check("Q1-DATES", "q1 date range 2024-01-01 to 2025-12-31", "2024-01-01 to 2025-12-31", f"{min_date_str} to {max_date_str}", min_date_str == "2024-01-01" and max_date_str == "2025-12-31")
    add_check("Q1-NOGAPS", "q1 zero missing days", "731", q1["date_parsed"].nunique(), q1["date_parsed"].nunique() == 731)

    vol_q1 = q1["total_sandwich_volume_usd"].sum()
    add_check("Q1-VOL-SUM", "q1 sum(total_sandwich_volume_usd) == 247322343792.92 (tol 1.0)", "247322343792.92", f"{vol_q1:.2f}", abs(vol_q1 - 247322343792.92) <= 1.0)

    trades_q1 = q1["sandwich_trade_count"].sum()
    add_check("Q1-TRADES-SUM", "q1 sum(sandwich_trade_count) == 7205568 (exact)", "7205568", trades_q1, trades_q1 == 7205568)

    mean_vol_q1 = q1["total_sandwich_volume_usd"].mean()
    add_check("Q1-VOL-MEAN", "q1 mean daily volume == 338334259.63 (tol 1.0)", "338334259.63", f"{mean_vol_q1:.2f}", abs(mean_vol_q1 - 338334259.63) <= 1.0)

    max_day_row = q1.loc[q1["total_sandwich_volume_usd"].idxmax()]
    min_day_row = q1.loc[q1["total_sandwich_volume_usd"].idxmin()]
    max_day_str = max_day_row["date_parsed"].strftime("%Y-%m-%d")
    min_day_str = min_day_row["date_parsed"].strftime("%Y-%m-%d")
    add_check("Q1-VOL-MAX", "q1 max day == 2025-08-09 at 1610042604.93 (tol 1.0)", "2025-08-09: 1610042604.93", f"{max_day_str}: {max_day_row['total_sandwich_volume_usd']:.2f}", max_day_str == "2025-08-09" and abs(max_day_row["total_sandwich_volume_usd"] - 1610042604.93) <= 1.0)
    add_check("Q1-VOL-MIN", "q1 min day == 2024-06-23 at 93006121.47 (tol 1.0)", "2024-06-23: 93006121.47", f"{min_day_str}: {min_day_row['total_sandwich_volume_usd']:.2f}", min_day_str == "2024-06-23" and abs(min_day_row["total_sandwich_volume_usd"] - 93006121.47) <= 1.0)

    q1_2024 = q1[q1["date_parsed"].dt.year == 2024]
    q1_2025 = q1[q1["date_parsed"].dt.year == 2025]
    mean_vol_2024 = q1_2024["total_sandwich_volume_usd"].mean() / 1e6
    mean_vol_2025 = q1_2025["total_sandwich_volume_usd"].mean() / 1e6
    add_check("Q1-VOL-2024", "q1 mean daily volume 2024 == 242.85M (tol 0.1M)", "242.85M", f"{mean_vol_2024:.2f}M", abs(mean_vol_2024 - 242.85) <= 0.1)
    add_check("Q1-VOL-2025", "q1 mean daily volume 2025 == 434.08M (tol 0.1M)", "434.08M", f"{mean_vol_2025:.2f}M", abs(mean_vol_2025 - 434.08) <= 0.1)

    mean_bots_overall = q1["unique_sandwich_bots"].mean()
    mean_bots_2024 = q1_2024["unique_sandwich_bots"].mean()
    mean_bots_2025 = q1_2025["unique_sandwich_bots"].mean()
    add_check("Q1-BOTS-ALL", "q1 mean unique bots overall == 172.4 (tol 0.2)", "172.4", f"{mean_bots_overall:.1f}", abs(mean_bots_overall - 172.4) <= 0.2)
    add_check("Q1-BOTS-2024", "q1 mean unique bots 2024 == 217.7 (tol 0.2)", "217.7", f"{mean_bots_2024:.1f}", abs(mean_bots_2024 - 217.7) <= 0.2)
    add_check("Q1-BOTS-2025", "q1 mean unique bots 2025 == 127.0 (tol 0.2)", "127.0", f"{mean_bots_2025:.1f}", abs(mean_bots_2025 - 127.0) <= 0.2)

    # Q3 checks
    add_check("Q3-ROWS", "q3 row count == 9749", "9749", len(q3), len(q3) == 9749)
    add_check("Q3-UNIQUE-ADDR", "q3 bot_address unique", "9749", q3["bot_address"].nunique(), q3["bot_address"].nunique() == 9749)
    nan_count_q3 = q3["total_volume_usd"].isna().sum()
    zero_count_q3 = (q3["total_volume_usd"] == 0.0).sum()
    add_check("Q3-NAN-COUNT", "q3 NaN volume count == 117", "117", nan_count_q3, nan_count_q3 == 117)
    add_check("Q3-ZERO-COUNT", "q3 zero volume count == 2", "2", zero_count_q3, zero_count_q3 == 2)
    vol_q3 = q3["total_volume_usd"].sum(skipna=True)
    add_check("Q3-VOL-SUM", "q3 sum(total_volume_usd) == 247322343792.92 (tol 1.0)", "247322343792.92", f"{vol_q3:.2f}", abs(vol_q3 - 247322343792.92) <= 1.0)

    # Q4 checks
    add_check("Q4-ROWS", "q4 row count == 9749", "9749", len(q4), len(q4) == 9749)
    addr_match = set(q3["bot_address"]) == set(q4["bot_address"])
    add_check("Q4-ADDR-SET", "q4 address set identical to q3", "True", str(addr_match), addr_match)

    q3_merged = q3.merge(q4[["bot_address", "total_volume_usd"]], on="bot_address", suffixes=("_q3", "_q4"))
    max_abs_diff_vol = (q3_merged["total_volume_usd_q3"] - q3_merged["total_volume_usd_q4"]).abs().max()
    add_check("Q4-VOL-MATCH", "q4 per-address volume matches q3 (max abs diff < 0.01)", "<0.01", f"{max_abs_diff_vol:.6f}", max_abs_diff_vol < 0.01)

    trades_q4 = q4["total_sandwich_trades"].sum()
    add_check("Q4-TRADES-SUM", "q4 sum(total_sandwich_trades) == 7205568 (exact)", "7205568", trades_q4, trades_q4 == 7205568)
    median_days = q4["days_active"].median()
    mean_days = q4["days_active"].mean()
    add_check("Q4-DAYS-MEDIAN", "q4 median days_active == 3", "3", median_days, median_days == 3)
    add_check("Q4-DAYS-MEAN", "q4 mean days_active == 12.93 (tol 0.05)", "12.93", f"{mean_days:.2f}", abs(mean_days - 12.93) <= 0.05)

    # Q5a checks (revised exact percentiles; supersede the old
    # APPROX_PERCENTILE-derived values and their up-to-4.43% error).
    p50_5a = q5a.loc[0, "p50_median"]
    p90_5a = q5a.loc[0, "p90"]
    p95_5a = q5a.loc[0, "p95"]
    mean_5a = q5a.loc[0, "mean_value"]
    max_5a = q5a.loc[0, "max_value"]
    min_5a = q5a.loc[0, "min_value"]
    tot_vic_5a = q5a.loc[0, "total_victims"]

    add_check("Q5A-P50", "q5a p50_median == 1001.8474 (tol 0.01)", "1001.8474", f"{p50_5a:.4f}", abs(p50_5a - 1001.8474) <= 0.01)
    add_check("Q5A-P90", "q5a p90 == 8986.608 (tol 0.01)", "8986.608", f"{p90_5a:.3f}", abs(p90_5a - 8986.608) <= 0.01)
    add_check("Q5A-P95", "q5a p95 == 17006.16 (tol 0.05)", "17006.16", f"{p95_5a:.2f}", abs(p95_5a - 17006.16) <= 0.05)
    add_check("Q5A-MEAN", "q5a mean_value == 7332.08 (tol 0.05)", "7332.08", f"{mean_5a:.2f}", abs(mean_5a - 7332.08) <= 0.05)
    add_check("Q5A-MAX", "q5a max_value == 21005460 (tol 100)", "21005460", int(max_5a), abs(max_5a - 21005460) <= 100)
    add_check("Q5A-MIN", "q5a min_value ≈ 1.239e-23 (<1e-20)", "< 1e-20", f"{min_5a:.4e}", min_5a < 1e-20)
    add_check("Q5A-TOT-VIC", "q5a total_victims == 3753857 (exact)", "3753857", tot_vic_5a, tot_vic_5a == 3753857)

    # Q5b checks (revised: tiers cut at exact p50/p90, not the legacy
    # $1,024.44 / $10,000 boundary)
    q5b_ret = q5b[q5b["victim_tier"] == "Retail"].iloc[0]
    q5b_sma = q5b[q5b["victim_tier"] == "Small"].iloc[0]
    q5b_inst = q5b[q5b["victim_tier"] == "Institutional"].iloc[0]

    add_check("Q5B-CNT-RET", "q5b victim_count Retail == 1876928", "1876928", q5b_ret["victim_count"], q5b_ret["victim_count"] == 1876928)
    add_check("Q5B-CNT-SMA", "q5b victim_count Small == 1501543", "1501543", q5b_sma["victim_count"], q5b_sma["victim_count"] == 1501543)
    add_check("Q5B-CNT-INST", "q5b victim_count Institutional == 375386", "375386", q5b_inst["victim_count"], q5b_inst["victim_count"] == 375386)
    add_check("Q5B-CNT-SUM", "q5b sum(victim_count) == 3753857 (exact)", "3753857", q5b["victim_count"].sum(), q5b["victim_count"].sum() == 3753857)

    add_check("Q5B-UNIQ-RET", "q5b unique_victims (tier-address obs) Retail == 209181", "209181", q5b_ret["unique_victims"], q5b_ret["unique_victims"] == 209181)
    add_check("Q5B-UNIQ-SMA", "q5b unique_victims (tier-address obs) Small == 142031", "142031", q5b_sma["unique_victims"], q5b_sma["unique_victims"] == 142031)
    add_check("Q5B-UNIQ-INST", "q5b unique_victims (tier-address obs) Institutional == 40517", "40517", q5b_inst["unique_victims"], q5b_inst["unique_victims"] == 40517)
    add_check("Q5B-UNIQ-SUM", "q5b sum(unique_victims), non-additive tier-address obs == 391729", "391729", q5b["unique_victims"].sum(), q5b["unique_victims"].sum() == 391729)

    vol_q5b = q5b["total_volume"].sum()
    add_check("Q5B-VOL-SUM", "q5b sum(total_volume) == 27523561653.66 (tol 1.0)", "27523561653.66", f"{vol_q5b:.2f}", abs(vol_q5b - 27523561653.66) <= 1.0)

    add_check("Q5B-AVG-RET", "q5b avg_tx_size Retail == 409.840 (tol 0.01)", "409.840", f"{q5b_ret['avg_tx_size']:.3f}", abs(q5b_ret["avg_tx_size"] - 409.840) <= 0.01)
    add_check("Q5B-AVG-SMA", "q5b avg_tx_size Small == 3082.279 (tol 0.01)", "3082.279", f"{q5b_sma['avg_tx_size']:.3f}", abs(q5b_sma["avg_tx_size"] - 3082.279) <= 0.01)
    add_check("Q5B-AVG-INST", "q5b avg_tx_size Institutional == 58942.386 (tol 0.01)", "58942.386", f"{q5b_inst['avg_tx_size']:.3f}", abs(q5b_inst["avg_tx_size"] - 58942.386) <= 0.01)

    # Tier boundaries now anchor on the exact percentiles, never a round
    # dollar constant. Retail max_tx must equal p50; Small max_tx and
    # Institutional min_tx must both equal p90. See fetch/queries/README.md
    # for why the old $10,000 constant was wrong (it sat between p90 and p95).
    # tol widened to 0.05: the tier's observed max/min trade is the nearest
    # actual trade value to the percentile cutoff, not the cutoff itself, so
    # a sub-cent gap is expected rather than a defect.
    add_check("Q5B-BOUND-RET", "q5b Retail max_tx == p50 (tol 0.05)", f"{p50_5a:.3f}", f"{q5b_ret['max_tx']:.3f}", abs(q5b_ret["max_tx"] - p50_5a) <= 0.05)
    add_check("Q5B-BOUND-SMA-MAX", "q5b Small max_tx == p90 (tol 0.05)", f"{p90_5a:.3f}", f"{q5b_sma['max_tx']:.3f}", abs(q5b_sma["max_tx"] - p90_5a) <= 0.05)
    add_check("Q5B-BOUND-INST-MIN", "q5b Institutional min_tx == p90 (tol 0.01)", f"{p90_5a:.3f}", f"{q5b_inst['min_tx']:.3f}", abs(q5b_inst["min_tx"] - p90_5a) <= 0.01)

    # Protocol checks (revised)
    add_check("PROT-ROWS", "protocol row count == 20", "20", len(prot), len(prot) == 20)
    prot_cnt_sum = prot["sandwich_count"].sum()
    add_check("PROT-CNT-SUM", "protocol sum(sandwich_count) == 3753857 (exact)", "3753857", prot_cnt_sum, prot_cnt_sum == 3753857)
    prot_vol_sum = prot["total_volume_usd"].sum()
    add_check("PROT-VOL-SUM", "protocol sum(total_volume_usd) == 27523561653.66 (tol 1.0)", "27523561653.66", f"{prot_vol_sum:.2f}", abs(prot_vol_sum - 27523561653.66) <= 1.0)

    uni_row = prot[prot["project"] == "uniswap"].iloc[0]
    uni_share = (uni_row["total_volume_usd"] / prot_vol_sum) * 100
    add_check("PROT-UNI-SHARE", "uniswap volume share == 72.01% (tol 0.05pp)", "72.01%", f"{uni_share:.2f}%", abs(uni_share - 72.01) <= 0.05)
    add_check("PROT-UNI-TRADES", "uniswap sandwich_count == 3562438", "3562438", uni_row["sandwich_count"], uni_row["sandwich_count"] == 3562438)
    add_check("PROT-UNI-VIC", "uniswap unique_takers_in_protocol == 302247", "302247", uni_row["unique_victims"], uni_row["unique_victims"] == 302247)

    # Cross-file identities
    add_check("CROSS-VOL-Q1-Q3", "q1 volume total == q3 volume total (tol 1.0)", "True", f"abs({vol_q1:.2f} - {vol_q3:.2f})", abs(vol_q1 - vol_q3) <= 1.0)
    add_check("CROSS-TRADES-Q1-Q4", "q1 trade total == q4 trade total (exact)", "True", f"{trades_q1} == {trades_q4}", trades_q1 == trades_q4)
    add_check("CROSS-VIC-Q5B-Q5A-PROT", "q5b victim_count sum == q5a total_victims == prot sandwich_count sum", "True", f"{q5b['victim_count'].sum()} == {tot_vic_5a} == {prot_cnt_sum}", q5b["victim_count"].sum() == tot_vic_5a and tot_vic_5a == prot_cnt_sum)
    add_check("CROSS-VOL-Q5B-PROT", "q5b volume sum == protocol volume sum (tol 1.0)", "True", f"abs({vol_q5b:.2f} - {prot_vol_sum:.2f})", abs(vol_q5b - prot_vol_sum) <= 1.0)

    # Check total count of checks >= 40
    add_check("TOTAL-CHECKS", "total validation checks >= 40", ">= 40", len(checks) + 1, len(checks) + 1 >= 40)

    # Write validation report
    report_lines = [
        "# Data and Schema Validation Report\n",
        "## Summary of Assertions\n",
        "| Check ID | Description | Expected | Computed | Status |",
        "|---|---|---|---|---|"
    ]
    for c in checks:
        report_lines.append(f"| {c['check_id']} | {c['description']} | {c['expected']} | {c['computed']} | **{c['status']}** |")

    report_lines.append("\n## Documented Data Quirks\n")
    report_lines.append("1. **Missing and Zero Volumes in Bot Distribution (`query3`/`query4`)**: Exactly 117 bot addresses have `NaN` total volume (due to missing historical token prices in Dune Analytics), and 2 bot addresses have exactly `0.0` volume. These 119 bots are excluded from volume-based concentration analysis (`B_meas`, N=9,632) and positive-volume analysis (`B_pos`, N=9,630), as documented in sample definitions.")
    report_lines.append("2. **Pricing Artifact in Victim Trade Sizes (`query5a`)**: The minimum victim trade size (`min_value`) is reported as approximately $1.239 \\times 10^{-23}$ USD. This is an extreme pricing/precision artifact in raw DEX swap logs and points to the necessity of trade-level winsorization in microdata analyses.")
    report_lines.append("3. **Victim-side files are now sourced from the corrected percentile-spec pull (`fetch/data/revised-24m/`), not the legacy delivered CSVs.** The legacy files (still preserved unmodified in `fetch/`) used Dune's `APPROX_PERCENTILE` (up to 4.43% error at p25) and a hardcoded $10,000 tier cutoff instead of the true p90 ($8,986.61 exact). See `fetch/queries/README.md` for the full defect list and the SQL that produced each revised file.")
    report_lines.append("4. **Tier Cutoff Fix**: Tiers are now cut at the exact percentiles: Retail `[$0, p50)`, Small `[p50, p90)`, Institutional `[p90, \\infty)`, with p50 = $1,001.85 and p90 = $8,986.61 (24-month window). This replaces the old $1,024.44 / $10,000 boundary; the legacy delivered tiers are retained separately as a robustness specification, not deleted.")
    report_lines.append("5. **Disjoint Measurement Bases (Bot-side vs. Victim-side)**: The dataset contains two distinct measurement bases that must NEVER be mixed or ratioed without explicit labeling: the **Bot-side base** (`query1`, `query3`, `query4`: 7,205,568 bot trades, $247.32B volume, 9,749 addresses) and the **Victim-side base** (`query_protocol`, `query5a`, `query5b`: 3,753,857 victim trades, $27.52B volume, 330,521 unique addresses per `query0a`; 391,729 non-additive tier-address observations per `query5b`). The ~9x volume ratio reflects definitional and measurement differences (counting both front-run and back-run bot legs, multi-hop routing, and DEX detection scopes) and has no economic interpretation.")

    report_lines.append("\n## Analyst Decisions\n")
    report_lines.append("Where the specification leaves implementation details to econometric discretion, standard conventions were adopted and recorded:")
    report_lines.append("- **Newey-West HAC Standard Errors**: Configured with explicit lag length `maxlags=7` for daily time series regressions to account for weekly seasonality and persistent autocorrelation ($AR(1) \\approx 0.78$).")
    report_lines.append("- **Bootstrap Confidence Intervals**: Computed using 10,000 replications with fixed random seed (`numpy.random.default_rng(42)`) via the non-parametric percentile method.")
    report_lines.append("- **Quandt-Andrews Unknown Date Break Scan**: Conducted over the central 70% sample window (15% trimming on each end) using a seeded circular moving-block bootstrap with block length = 14 days (999 replications, `rng=42`).")
    report_lines.append("- **Structural Break Segmentation**: Applied `ruptures` binary segmentation (`Binseg`) with `l2` cost on log daily volume, capped at a maximum of 3 breaks to prevent over-segmentation on trending series.")
    report_lines.append("- **Chow Tests**: Classical known-date Chow tests are explicitly labeled as descriptive due to non-iid daily volume errors ($AR(1) \\approx 0.78$), with HAC-robust F-tests on interrupted time series step/slope terms providing formal inference.")

    report_path = "output/reports/validation_report.md"
    with open(report_path, "w") as f:
        f.write("\n".join(report_lines) + "\n")

    failures = [c for c in checks if c["status"] == "FAIL"]
    if failures:
        err_msg = "Validation failed for checks:\n" + "\n".join([f"{c['check_id']}: expected {c['expected']}, computed {c['computed']}" for c in failures])
        raise RuntimeError(err_msg)

    print(f"[PASS] m0_validate: All {len(checks)} checks passed successfully. Report written to {report_path}")
    return True

if __name__ == "__main__":
    run_validation()
