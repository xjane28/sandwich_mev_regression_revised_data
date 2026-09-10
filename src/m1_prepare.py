import os
import pandas as pd
import numpy as np
from src import m0_validate, tex_utils

def prepare_all():
    q1, q3, q4, prot, q5a, q5b = m0_validate.load_data()
    
    # 1. Samples
    B_full = q4.copy()
    B_meas = q4[q4["total_volume_usd"].notna() & (q4["total_volume_usd"] >= 0.0)].copy()
    B_pos = q4[q4["total_volume_usd"] > 0.0].copy()
    
    # 2. Daily series
    q1["y_t"] = np.log(q1["total_sandwich_volume_usd"])
    q1["dow"] = q1["date_parsed"].dt.dayofweek
    q1["month"] = q1["date_parsed"].dt.month
    q1["year_month"] = q1["date_parsed"].dt.strftime("%Y-%m")
    q1["t"] = np.arange(len(q1))
    
    t_dencun = q1[q1["date_parsed"].dt.strftime("%Y-%m-%d") == "2024-03-13"].index[0]
    t_pectra = q1[q1["date_parsed"].dt.strftime("%Y-%m-%d") == "2025-05-07"].index[0]
    
    q1["D_dencun"] = (q1["t"] >= t_dencun).astype(int)
    q1["D_pectra"] = (q1["t"] >= t_pectra).astype(int)
    q1["S_dencun"] = q1["D_dencun"] * (q1["t"] - t_dencun)
    q1["S_pectra"] = q1["D_pectra"] * (q1["t"] - t_pectra)
    
    # Verify step dummies and slopes on 3 hand-picked dates
    check_dates = ["2024-03-12", "2024-03-13", "2025-05-07"]
    log_lines = ["--- Step 1: Verification of Dummies/Slopes ---"]
    for d_str in check_dates:
        row = q1[q1["date_parsed"].dt.strftime("%Y-%m-%d") == d_str].iloc[0]
        log_lines.append(f"Date: {d_str} | t={row['t']} | D_dencun={row['D_dencun']} | S_dencun={row['S_dencun']} | D_pectra={row['D_pectra']} | S_pectra={row['S_pectra']}")
    
    os.makedirs("output/logs", exist_ok=True)
    with open("output/logs/run_log.txt", "a") as f:
        f.write("\n".join(log_lines) + "\n\n")
    print("\n".join(log_lines))
    
    # 3. Tier-level derived metrics
    q5b["attacks_per_victim"] = q5b["victim_count"] / q5b["unique_victims"]
    q5b["attacks_per_1000usd"] = (q5b["victim_count"] / q5b["total_volume"]) * 1000
    q5b["share_of_events"] = q5b["victim_count"] / 3753918
    q5b["share_of_volume"] = q5b["total_volume"] / q5b["total_volume"].sum()
    q5b["avg_volume_per_unique_victim"] = q5b["total_volume"] / q5b["unique_victims"]
    
    # 4. Bot-level derived metrics
    def assign_cohort(dt):
        if dt.year == 2024:
            return "2024H1" if dt.month <= 6 else "2024H2"
        else:
            return "2025H1" if dt.month <= 6 else "2025H2"
            
    B_pos["lifespan_days"] = (B_pos["last_seen_parsed"] - B_pos["first_seen_parsed"]).dt.days + 1
    B_pos["intensity"] = B_pos["total_sandwich_trades"] / B_pos["days_active"]
    B_pos["first_seen_cohort"] = B_pos["first_seen_parsed"].apply(assign_cohort)
    B_pos["active_at_end"] = (B_pos["last_seen_parsed"] >= pd.to_datetime("2025-12-01")).astype(int)
    
    # Also add to B_meas and B_full for general use
    B_meas["lifespan_days"] = (B_meas["last_seen_parsed"] - B_meas["first_seen_parsed"]).dt.days + 1
    B_meas["intensity"] = B_meas["total_sandwich_trades"] / B_meas["days_active"]
    B_meas["first_seen_cohort"] = B_meas["first_seen_parsed"].apply(assign_cohort)
    B_meas["active_at_end"] = (B_meas["last_seen_parsed"] >= pd.to_datetime("2025-12-01")).astype(int)
    
    # 5. Produce Table 1: Summary Statistics (Panels A, B, C)
    # Let's create a combined CSV and a clean multi-panel LaTeX table
    rows_csv = []
    
    def get_stats(series, name, panel):
        return {
            "Panel": panel,
            "Variable": name,
            "N": len(series.dropna()),
            "Mean": series.mean(),
            "Std": series.std(),
            "Min": series.min(),
            "P25": series.quantile(0.25),
            "Median": series.median(),
            "P75": series.quantile(0.75),
            "Max": series.max()
        }
    
    # Panel A: Daily Series
    rows_csv.append(get_stats(q1["sandwich_trade_count"], "Daily Trade Count", "A. Daily Bot-Side Series"))
    rows_csv.append(get_stats(q1["total_sandwich_volume_usd"] / 1e6, "Daily Volume (USD Millions)", "A. Daily Bot-Side Series"))
    rows_csv.append(get_stats(q1["unique_sandwich_bots"], "Daily Unique Bots", "A. Daily Bot-Side Series"))
    rows_csv.append(get_stats(q1["unique_transactions"], "Daily Unique Transactions", "A. Daily Bot-Side Series"))
    
    # Panel B: Bot Cross-Section
    rows_csv.append(get_stats(B_meas["total_volume_usd"] / 1e6, "Total Volume (USD Millions, B_meas)", "B. Bot Cross-Section"))
    rows_csv.append(get_stats(B_pos["days_active"], "Days Active (B_pos)", "B. Bot Cross-Section"))
    rows_csv.append(get_stats(B_pos["total_sandwich_trades"], "Total Sandwich Trades (B_pos)", "B. Bot Cross-Section"))
    rows_csv.append(get_stats(B_pos["avg_trade_size_usd"], "Avg Trade Size (USD, B_pos)", "B. Bot Cross-Section"))
    
    df_ab = pd.DataFrame(rows_csv)
    
    # For Panel C (Victim Side), let's create a structured representation in the CSV
    # Row from q5a distribution
    row_5a = {
        "Panel": "C. Victim-Side Distribution",
        "Variable": "Victim Trade Size Distribution (USD)",
        "N": int(q5a.loc[0, "total_victims"]),
        "Mean": q5a.loc[0, "mean_value"],
        "Std": np.nan,
        "Min": q5a.loc[0, "min_value"],
        "P25": q5a.loc[0, "p25"],
        "Median": q5a.loc[0, "p50_median"],
        "P75": q5a.loc[0, "p75"],
        "Max": q5a.loc[0, "max_value"]
    }
    rows_csv.append(row_5a)
    
    for _, row in q5b.iterrows():
        rows_csv.append({
            "Panel": "C. Victim-Side Distribution",
            "Variable": f"Tier: {row['victim_tier']} (Avg Tx Size USD)",
            "N": int(row["victim_count"]),
            "Mean": row["avg_tx_size"],
            "Std": np.nan,
            "Min": row["min_tx"],
            "P25": np.nan,
            "Median": np.nan,
            "P75": np.nan,
            "Max": row["max_tx"]
        })
        
    df_csv = pd.DataFrame(rows_csv)
    os.makedirs("output/tables", exist_ok=True)
    df_csv.to_csv("output/tables/table1_descriptives.csv", index=False)
    
    # Generate LaTeX Table 1 with booktabs and multi-panel structure
    tex_lines = [
        "\\begin{table}[htbp]",
        "\\centering",
        "\\caption{Summary Statistics of the Sandwich-MEV Dataset (2024--2025)}",
        "\\label{tab:descriptives}",
        "\\begin{tabular}{lrrrrrrrr}",
        "\\toprule",
        "Variable & N & Mean & Std & Min & P25 & Median & P75 & Max \\\\",
        "\\midrule",
        "\\multicolumn{9}{l}{\\textbf{Panel A: Daily Bot-Side Series (N = 731 days)}} \\\\",
        "\\midrule"
    ]
    
    def fmt(val):
        if pd.isna(val):
            return ""
        if abs(val) >= 1000:
            return f"{val:,.2f}"
        if abs(val) > 0 and abs(val) < 0.0001:
            return f"{val:.4e}"
        return f"{val:.4f}".rstrip("0").rstrip(".") if val == int(val) else f"{val:.4f}"
        
    for _, r in df_ab[df_ab["Panel"] == "A. Daily Bot-Side Series"].iterrows():
        line = f"{r['Variable']} & {int(r['N']):,} & {fmt(r['Mean'])} & {fmt(r['Std'])} & {fmt(r['Min'])} & {fmt(r['P25'])} & {fmt(r['Median'])} & {fmt(r['P75'])} & {fmt(r['Max'])} \\\\"
        tex_lines.append(line)
        
    tex_lines.extend([
        "\\midrule",
        "\\multicolumn{9}{l}{\\textbf{Panel B: Bot Cross-Section}} \\\\",
        "\\midrule"
    ])
    
    for _, r in df_ab[df_ab["Panel"] == "B. Bot Cross-Section"].iterrows():
        line = f"{r['Variable']} & {int(r['N']):,} & {fmt(r['Mean'])} & {fmt(r['Std'])} & {fmt(r['Min'])} & {fmt(r['P25'])} & {fmt(r['Median'])} & {fmt(r['P75'])} & {fmt(r['Max'])} \\\\"
        tex_lines.append(line)
        
    tex_lines.extend([
        "\\midrule",
        "\\multicolumn{9}{l}{\\textbf{Panel C: Victim-Side Distribution}} \\\\",
        "\\midrule"
    ])
    
    # Add Row 5a
    r5a = row_5a
    line_5a = f"Victim Trade Size (USD) & {int(r5a['N']):,} & {fmt(r5a['Mean'])} & --- & {fmt(r5a['Min'])} & {fmt(r5a['P25'])} & {fmt(r5a['Median'])} & {fmt(r5a['P75'])} & {fmt(r5a['Max'])} \\\\"
    tex_lines.append(line_5a)
    
    for _, r in q5b.iterrows():
        line = f"Tier: {r['victim_tier']} (Avg Tx USD) & {int(r['victim_count']):,} & {fmt(r['avg_tx_size'])} & --- & {fmt(r['min_tx'])} & --- & --- & --- & {fmt(r['max_tx'])} \\\\"
        tex_lines.append(line)
        
    notes_str = (
        "This table presents descriptive statistics for the Ethereum Sandwich-MEV dataset (2024--2025). "
        "\\textbf{Measurement bases must not be mixed without adjustment:} Panels A and B report on the \\textbf{bot-side base}, comprising 7,205,568 sandwich attacker trade legs and \\$247.32B in total notional volume across 9,749 bot addresses (9,632 with non-missing volume in $B_{\\text{meas}}$, and 9,630 with strictly positive volume in $B_{\\text{pos}}$). "
        "Panel C reports on the \\textbf{victim-side base}, comprising 3,753,918 sandwiched victim trade events (attack events) and \\$27.47B in total volume across 413,129 unique victim addresses. "
        "In Panel C, N represents the number of sandwiched victim trades (attack events), not unique addresses. "
        "The minimum trade size in Panel C ($1.24 \\times 10^{-23}$ USD) represents an extreme pricing/precision artifact in raw DEX logs."
    )
    
    tex_lines.extend([
        "\\bottomrule",
        "\\end{tabular}",
        "\\vspace{0.2cm}",
        "\\begin{minipage}{\\linewidth}",
        "\\small",
        f"\\textit{{Notes:}} {notes_str}",
        "\\end{minipage}",
        "\\end{table}"
    ])
    
    with open("output/tables/table1_descriptives.tex", "w") as f:
        f.write("\n".join(tex_lines) + "\n")
        
    print("[PASS] m1_prepare completed successfully. Table 1 generated.")
    return q1, q3, q4, prot, q5a, q5b, B_full, B_meas, B_pos

if __name__ == "__main__":
    prepare_all()
