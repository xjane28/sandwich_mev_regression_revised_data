import os
import shutil
import sys
import pandas as pd
import numpy as np

def setup_directories():
    os.makedirs("output/tables", exist_ok=True)
    os.makedirs("output/figures", exist_ok=True)
    os.makedirs("output/reports", exist_ok=True)
    os.makedirs("output/logs", exist_ok=True)
    os.makedirs("data", exist_ok=True)

def ensure_data_files():
    expected_files = [
        "query1_mev_volume.csv",
        "query3_full_bot_distribution.csv",
        "query4_top_bots.csv",
        "query_protocol_vulnerability.csv",
        "query5a_break_points.csv",
        "query5b_victim_impact.csv"
    ]
    missing_in_data = [f for f in expected_files if not os.path.exists(os.path.join("data", f))]
    if missing_in_data:
        # Check fetch/ directory
        for f in missing_in_data:
            src = os.path.join("fetch", f)
            dst = os.path.join("data", f)
            if os.path.exists(src):
                shutil.copy(src, dst)
            else:
                raise FileNotFoundError(f"Missing required input CSV file: {f} in both ./data/ and ./fetch/")

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
    
    prot = pd.read_csv("data/query_protocol_vulnerability.csv", dtype={
        "avg_trade_size": float,
        "project": str,
        "sandwich_count": int,
        "total_volume_usd": float,
        "unique_victims": int
    })
    
    q5a = pd.read_csv("data/query5a_break_points.csv", dtype={
        "max_value": float,
        "mean_value": float,
        "min_value": float,
        "p25": float,
        "p50_median": float,
        "p75": float,
        "p90": float,
        "p95": float,
        "total_victims": int
    })
    
    q5b = pd.read_csv("data/query5b_victim_impact.csv", dtype={
        "avg_tx_size": float,
        "max_tx": float,
        "min_tx": float,
        "pct_of_victims": float,
        "pct_of_volume": float,
        "total_volume": float,
        "unique_victims": int,
        "victim_count": int,
        "victim_tier": str
    })
    
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
    
    # Q5a checks
    p50_5a = q5a.loc[0, "p50_median"]
    p90_5a = q5a.loc[0, "p90"]
    p95_5a = q5a.loc[0, "p95"]
    mean_5a = q5a.loc[0, "mean_value"]
    max_5a = q5a.loc[0, "max_value"]
    min_5a = q5a.loc[0, "min_value"]
    tot_vic_5a = q5a.loc[0, "total_victims"]
    
    add_check("Q5A-P50", "q5a p50_median == 1024.4357 (tol 0.01)", "1024.4357", f"{p50_5a:.4f}", abs(p50_5a - 1024.4357) <= 0.01)
    add_check("Q5A-P90", "q5a p90 == 8928.305 (tol 0.01)", "8928.305", f"{p90_5a:.3f}", abs(p90_5a - 8928.305) <= 0.01)
    add_check("Q5A-P95", "q5a p95 == 17351.61 (tol 0.05)", "17351.61", f"{p95_5a:.2f}", abs(p95_5a - 17351.61) <= 0.05)
    add_check("Q5A-MEAN", "q5a mean_value == 7317.81 (tol 0.05)", "7317.81", f"{mean_5a:.2f}", abs(mean_5a - 7317.81) <= 0.05)
    add_check("Q5A-MAX", "q5a max_value == 21005460", "21005460", int(max_5a), int(max_5a) == 21005460)
    add_check("Q5A-MIN", "q5a min_value ≈ 1.239e-23 (<1e-20)", "< 1e-20", f"{min_5a:.4e}", min_5a < 1e-20)
    add_check("Q5A-TOT-VIC", "q5a total_victims == 3753918 (exact)", "3753918", tot_vic_5a, tot_vic_5a == 3753918)
    
    # Q5b checks
    q5b_ret = q5b[q5b["victim_tier"] == "Retail"].iloc[0]
    q5b_sma = q5b[q5b["victim_tier"] == "Small"].iloc[0]
    q5b_inst = q5b[q5b["victim_tier"] == "Institutional"].iloc[0]
    
    add_check("Q5B-CNT-RET", "q5b victim_count Retail == 1905366", "1905366", q5b_ret["victim_count"], q5b_ret["victim_count"] == 1905366)
    add_check("Q5B-CNT-SMA", "q5b victim_count Small == 1521961", "1521961", q5b_sma["victim_count"], q5b_sma["victim_count"] == 1521961)
    add_check("Q5B-CNT-INST", "q5b victim_count Institutional == 326591", "326591", q5b_inst["victim_count"], q5b_inst["victim_count"] == 326591)
    add_check("Q5B-CNT-SUM", "q5b sum(victim_count) == 3753918 (exact)", "3753918", q5b["victim_count"].sum(), q5b["victim_count"].sum() == 3753918)
    
    add_check("Q5B-UNIQ-RET", "q5b unique_victims Retail == 225280", "225280", q5b_ret["unique_victims"], q5b_ret["unique_victims"] == 225280)
    add_check("Q5B-UNIQ-SMA", "q5b unique_victims Small == 149243", "149243", q5b_sma["unique_victims"], q5b_sma["unique_victims"] == 149243)
    add_check("Q5B-UNIQ-INST", "q5b unique_victims Institutional == 38606", "38606", q5b_inst["unique_victims"], q5b_inst["unique_victims"] == 38606)
    add_check("Q5B-UNIQ-SUM", "q5b sum(unique_victims) == 413129", "413129", q5b["unique_victims"].sum(), q5b["unique_victims"].sum() == 413129)
    
    vol_q5b = q5b["total_volume"].sum()
    add_check("Q5B-VOL-SUM", "q5b sum(total_volume) == 27470469483.62 (tol 1.0)", "27470469483.62", f"{vol_q5b:.2f}", abs(vol_q5b - 27470469483.62) <= 1.0)
    
    add_check("Q5B-AVG-RET", "q5b avg_tx_size Retail == 418.830 (tol 0.01)", "418.830", f"{q5b_ret['avg_tx_size']:.3f}", abs(q5b_ret["avg_tx_size"] - 418.830) <= 0.01)
    add_check("Q5B-AVG-SMA", "q5b avg_tx_size Small == 3329.753 (tol 0.01)", "3329.753", f"{q5b_sma['avg_tx_size']:.3f}", abs(q5b_sma["avg_tx_size"] - 3329.753) <= 0.01)
    add_check("Q5B-AVG-INST", "q5b avg_tx_size Institutional == 66152.130 (tol 0.01)", "66152.130", f"{q5b_inst['avg_tx_size']:.3f}", abs(q5b_inst["avg_tx_size"] - 66152.130) <= 0.01)
    
    add_check("Q5B-BOUND-RET", "q5b Retail max_tx == 1024.439 (tol 0.01) ≈ p50", "1024.439", f"{q5b_ret['max_tx']:.3f}", abs(q5b_ret["max_tx"] - 1024.439) <= 0.01)
    add_check("Q5B-BOUND-SMA-MAX", "q5b Small max_tx == 10000.0 (tol 0.01)", "10000.0", f"{q5b_sma['max_tx']:.1f}", abs(q5b_sma["max_tx"] - 10000.0) <= 0.01)
    add_check("Q5B-BOUND-INST-MIN", "q5b Institutional min_tx == 10000.0 (tol 0.01)", "10000.0", f"{q5b_inst['min_tx']:.1f}", abs(q5b_inst["min_tx"] - 10000.0) <= 0.01)
    
    # Protocol checks
    add_check("PROT-ROWS", "protocol row count == 20", "20", len(prot), len(prot) == 20)
    prot_cnt_sum = prot["sandwich_count"].sum()
    add_check("PROT-CNT-SUM", "protocol sum(sandwich_count) == 3753918 (exact)", "3753918", prot_cnt_sum, prot_cnt_sum == 3753918)
    prot_vol_sum = prot["total_volume_usd"].sum()
    add_check("PROT-VOL-SUM", "protocol sum(total_volume_usd) == 27470469483.62 (tol 1.0)", "27470469483.62", f"{prot_vol_sum:.2f}", abs(prot_vol_sum - 27470469483.62) <= 1.0)
    
    uni_row = prot[prot["project"] == "uniswap"].iloc[0]
    uni_share = (uni_row["total_volume_usd"] / prot_vol_sum) * 100
    add_check("PROT-UNI-SHARE", "uniswap volume share == 71.96% (tol 0.05pp)", "71.96%", f"{uni_share:.2f}%", abs(uni_share - 71.96) <= 0.05)
    add_check("PROT-UNI-TRADES", "uniswap sandwich_count == 3562502", "3562502", uni_row["sandwich_count"], uni_row["sandwich_count"] == 3562502)
    add_check("PROT-UNI-VIC", "uniswap unique_victims == 324626", "324626", uni_row["unique_victims"], uni_row["unique_victims"] == 324626)
    
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
    report_lines.append("3. **Dataset README Mislabels Corrected**: (a) Despite its file name and README description, `query4_top_bots.csv` covers all 9,749 bot addresses (identical set to `query3`), not just 'top' bots. (b) In `query5a_break_points.csv`, `total_victims` (3,753,918) represents total sandwiched VICTIM TRADES (attack events), NOT unique victim addresses (which total 413,129 across tiers). (c) In `query5b_victim_impact.csv`, `pct_of_victims` represents the tier share of victim trades, not unique addresses. (d) The upper cutoff for the Small tier / lower cutoff for Institutional in `query5b` is a round $10,000, NOT the $p_{90}$ ($8,928.31) stated in the draft/README. (e) **Correction #6**: The README describes `sandwich_count` in `query_protocol_vulnerability.csv` as sandwich bot trades, but the column sums to 3,753,918 (victim trades) and `total_volume_usd` to the $27.47B victim volume — the protocol file is victim-side and must be labelled as such in all tables and analyses.")
    report_lines.append("4. **Tier Cutoff Discrepancy ($10,000 vs. $p_{90}$)**: Formal audit verifies that the Retail upper bound equals $p_{50}$ ($1,024.44), but the Small upper bound and Institutional lower bound are exactly $10,000.00$. This $10,000 cutoff lies between $p_{90}$ ($8,928.31) and $p_{95}$ ($17,351.61$). Re-tiering at exactly $p_{90}$ cannot be performed without trade-level microdata.")
    report_lines.append("5. **Disjoint Measurement Bases (Bot-side vs. Victim-side)**: The dataset contains two distinct measurement bases that must NEVER be mixed or ratioed without explicit labeling: the **Bot-side base** (`query1`, `query3`, `query4`: 7,205,568 bot trades, $247.32B volume, 9,749 addresses) and the **Victim-side base** (`query_protocol`, `query5a`, `query5b`: 3,753,918 victim trades, $27.47B volume, 413,129 unique addresses). The ~9x volume ratio reflects definitional and measurement differences (counting both front-run and back-run bot legs, multi-hop routing, and DEX detection scopes) and has no economic interpretation.")
    
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
