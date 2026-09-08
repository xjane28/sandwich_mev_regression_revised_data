import os
import numpy as np
import pandas as pd
from src import m1_prepare, tex_utils

def run_synthesis():
    q1, q3, q4, prot, q5a, q5b, B_full, B_meas, B_pos = m1_prepare.prepare_all()
    
    # 1. Measurement-Base Reconciliation Table (Table 8)
    bot_vol = q4["total_volume_usd"].sum()
    bot_trades = q4["total_sandwich_trades"].sum()
    bot_addrs = len(q4)
    
    vic_vol = q5b["total_volume"].sum()
    vic_trades = q5b["victim_count"].sum()
    vic_addrs = q5b["unique_victims"].sum()
    
    prot_vol = prot["total_volume_usd"].sum()
    prot_trades = prot["sandwich_count"].sum()
    prot_addrs = prot["unique_victims"].sum()
    
    ratio_vol = bot_vol / vic_vol
    ratio_trades = bot_trades / vic_trades
    
    print(f"Volume Ratio (Bot / Victim) = {ratio_vol:.2f}x | Trade Ratio = {ratio_trades:.2f}x")
    
    t8_rows = [
        {"Measurement Base": "Bot-Side Base (query3 / query4)", "Addresses / Entities ($N$)": f"{bot_addrs:,} bot addresses", "Trade Event Count": f"{int(bot_trades):,} attacker legs", "Notional Volume (USD)": f"${bot_vol/1e9:,.2f}B", "Interpretation & Routing Notes": "Aggregates front-run + back-run legs across all DEX pools involved in routing"},
        {"Measurement Base": "Victim-Side Base (query5a / query5b)", "Addresses / Entities ($N$)": f"{int(vic_addrs):,} unique victims", "Trade Event Count": f"{int(vic_trades):,} attack events", "Notional Volume (USD)": f"${vic_vol/1e9:,.2f}B", "Interpretation & Routing Notes": "Records only the sandwiched swap event itself (single victim leg)"},
        {"Measurement Base": "Protocol File (query_protocol_vulnerability)", "Addresses / Entities ($N$)": f"{int(prot_addrs):,} unique victims", "Trade Event Count": f"{int(prot_trades):,} attack events", "Notional Volume (USD)": f"${prot_vol/1e9:,.2f}B", "Interpretation & Routing Notes": "Victim-side base disaggregated by protocol (mislabeled 'sandwich bot trades' in README)"},
        {"Measurement Base": "Reconciliation Ratio (Bot / Victim)", "Addresses / Entities ($N$)": "---", "Trade Event Count": f"{ratio_trades:.2f}x", "Notional Volume (USD)": f"{ratio_vol:.2f}x", "Interpretation & Routing Notes": "Bot volume exceeds victim volume by 9.00x due to multi-hop routing and multi-leg MEV"}
    ]
    df_t8 = pd.DataFrame(t8_rows)
    notes_t8 = (
        "This table reconciles the two disjoint measurement bases present in the Dune Analytics export. "
        "\\textbf{Do not mix measurement bases:} The bot-side base (Panels A/B of Table 1, Tables 2, 3, 6, 7, 9) captures searcher attacker legs, whereas the victim-side base (Panel C of Table 1, Tables 4, 5, protocol analysis) captures sandwiched victim swap events. "
        f"Bot volume (\\${bot_vol/1e9:.2f}B) exceeds victim volume (\\${vic_vol/1e9:.2f}B) by exactly {ratio_vol:.2f}\\times, and bot trade legs ({int(bot_trades):,}) exceed victim attack events ({int(vic_trades):,}) by {ratio_trades:.2f}\\times. "
        "This divergence occurs because searcher volume aggregates front-run and back-run legs across all DEX pools involved in multi-hop routing, whereas victim volume records only the single sandwiched swap."
    )
    tex_utils.write_table(df_t8, "table8_measurement_bases", "Reconciliation of Disjoint Measurement Bases in Dune Analytics Export", "tab:measurement_bases", notes_t8, col_align="llrrrl", col_headers=["Measurement Base", "Addresses ($N$)", "Trade Count", "Volume (USD)", "Interpretation Notes"])
    
    # 2. H4 (Protocol Vulnerability) Formal Evaluation
    prot_sorted = prot.sort_values(by="total_volume_usd", ascending=False).copy()
    prot_sorted["share_vol"] = prot_sorted["total_volume_usd"] / prot_vol
    prot_sorted["share_pct"] = prot_sorted["share_vol"] * 100
    
    hhi_prot = np.sum(prot_sorted["share_vol"] ** 2) * 10000
    cr2_prot = prot_sorted["share_pct"].iloc[:2].sum()
    cr4_prot = prot_sorted["share_pct"].iloc[:4].sum()
    
    print(f"Protocol HHI = {hhi_prot:.1f} | CR2 (Uniswap v2+v3) = {cr2_prot:.2f}% | CR4 = {cr4_prot:.2f}%")
    
    # Save H4 summary table as an additional clean output or log
    os.makedirs("output/tables", exist_ok=True)
    prot_out = prot_sorted.rename(columns={
        "project": "Protocol", "protocol": "Protocol", "sandwich_count": "Victim Trades (N)", "unique_victims": "Unique Victims",
        "total_volume_usd": "Total Volume (USD)", "share_pct": "Volume Share (%)"
    })[["Protocol", "Victim Trades (N)", "Unique Victims", "Total Volume (USD)", "Volume Share (%)"]]
    prot_out.to_csv("output/tables/protocol_vulnerability_summary.csv", index=False)
    
    print("[PASS] m6_synthesis completed successfully.")
    return ratio_vol, hhi_prot, cr2_prot

if __name__ == "__main__":
    run_synthesis()
