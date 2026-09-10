import os
import numpy as np
import pandas as pd
from src import m0_validate, tex_utils

def run_synthesis():
    bundle = m0_validate.load_data_bundle()
    q4 = bundle["q4"]
    prot = bundle["prot"]
    q5a = bundle["q5a"]
    q5b = bundle["q5b"]
    q0a = bundle["q0a"]
    q0b = bundle["q0b"]
    q5c = bundle["q5c"]
    tier_addr_col = m0_validate.q5b_tier_address_col(q5b)

    # 1. Measurement-Base Reconciliation Table (Table 8)
    bot_vol = q4["total_volume_usd"].sum()
    bot_trades = q4["total_sandwich_trades"].sum()
    bot_addrs = len(q4)

    vic_vol = q5b["total_volume"].sum()
    vic_trades = q5b["victim_count"].sum()
    tier_address_obs = q5b[tier_addr_col].sum()

    unique_takers = np.nan
    if not q0a.empty and "metric" in q0a.columns:
        match = q0a[q0a["metric"] == "sandwiched_unique_takers_gt0_usd"]
        if not match.empty:
            unique_takers = float(match["value"].iloc[0])
    if not np.isfinite(unique_takers):
        unique_takers = float(q5a.loc[0, "unique_victim_addresses"])

    tx_from_unique_total = q5c["unique_eoas"].sum() if not q5c.empty else np.nan
    tx_from_unique_nonbot = q5c[q5c["is_known_bot"] == 0]["unique_eoas"].sum() if not q5c.empty else np.nan
    tx_from_known_bot = q5c[q5c["is_known_bot"] == 1]["unique_eoas"].sum() if not q5c.empty else np.nan

    prot_vol = prot["total_volume_usd"].sum()
    prot_trades = prot["sandwich_count"].sum()

    ratio_vol = bot_vol / vic_vol
    ratio_trades = bot_trades / vic_trades

    print(f"Volume Ratio (Bot / Victim) = {ratio_vol:.2f}x | Trade Ratio = {ratio_trades:.2f}x")

    t8_rows = [
        {"Measurement Base": "Bot-Side Base (query3 / query4)", "Addresses / Entities ($N$)": f"{bot_addrs:,} bot addresses", "Trade Event Count": f"{int(bot_trades):,} attacker legs", "Notional Volume (USD)": f"${bot_vol/1e9:,.2f}B", "Interpretation & Routing Notes": "Aggregates front-run + back-run legs across all DEX pools involved in routing"},
        {"Measurement Base": "Victim-Side Trades (query5b)", "Addresses / Entities ($N$)": f"{int(tier_address_obs):,} tier-address observations", "Trade Event Count": f"{int(vic_trades):,} attack events", "Notional Volume (USD)": f"${vic_vol/1e9:,.2f}B", "Interpretation & Routing Notes": "Trade-level victim events by tier; address counts are non-additive across tiers"},
        {"Measurement Base": "Victim Identity: taker (query0a/q5a)", "Addresses / Entities ($N$)": f"{int(unique_takers):,} unique takers", "Trade Event Count": f"{int(vic_trades):,} attack events", "Notional Volume (USD)": f"${vic_vol/1e9:,.2f}B", "Interpretation & Routing Notes": "taker includes router contracts; not equivalent to end-trader identity"},
        {"Measurement Base": "Victim Identity: tx_from (query5c)", "Addresses / Entities ($N$)": f"{int(tx_from_unique_nonbot):,} non-bot EOAs / {int(tx_from_unique_total):,} total EOAs", "Trade Event Count": f"{int(q5c['attack_events'].sum()):,} attack events", "Notional Volume (USD)": f"${q5c['tier_volume_usd'].sum()/1e9:,.2f}B", "Interpretation & Routing Notes": f"Primary repeat-victimisation identity base; includes {int(tx_from_known_bot):,} known-bot EOAs flagged separately"},
        {"Measurement Base": "Protocol File (query_protocol_vulnerability)", "Addresses / Entities ($N$)": f"{int(prot['unique_victims'].sum()):,} protocol-level address counts", "Trade Event Count": f"{int(prot_trades):,} attack events", "Notional Volume (USD)": f"${prot_vol/1e9:,.2f}B", "Interpretation & Routing Notes": "Victim-side trade base by protocol; shares align with query5b totals"},
        {"Measurement Base": "Reconciliation Ratio (Bot / Victim)", "Addresses / Entities ($N$)": "---", "Trade Event Count": f"{ratio_trades:.2f}x", "Notional Volume (USD)": f"{ratio_vol:.2f}x", "Interpretation & Routing Notes": f"Bot volume exceeds victim volume by {ratio_vol:.2f}x due to multi-hop routing and multi-leg execution"},
    ]
    df_t8 = pd.DataFrame(t8_rows)
    notes_t8 = (
        "This table reconciles disjoint measurement bases and identity conventions in the revised Dune export. "
        "\\textbf{Identity correction:} repeat-victimisation claims use tx_from EOAs (query5c), not taker addresses. "
        "\\textbf{Non-additivity caveat:} summing per-tier address counts in query5b overstates global unique victims because addresses can appear in multiple tiers."
    )
    tex_utils.write_table(df_t8, "table8_measurement_bases", "Reconciliation of Measurement Bases and Identity Layers", "tab:measurement_bases", notes_t8, col_align="lllll", col_headers=["Measurement Base", "Addresses / Entities ($N$)", "Trade Event Count", "Notional Volume (USD)", "Interpretation & Routing Notes"])

    # 2. Router / Intermediation Diagnostics (new table from query0b)
    if not q0b.empty:
        router_unique = q0b.sort_values("distinct_senders", ascending=False).drop_duplicates("taker")
        top30 = router_unique.head(30)
        top30_trade_share = (top30["victim_trades"].sum() / vic_trades) * 100.0
        top30_volume_share = (top30["total_volume_usd"].sum() / vic_vol) * 100.0
        max_router = router_unique.iloc[0]

        table10_rows = [
            {
                "Diagnostic": "Router concentration (top-30 takers by distinct senders)",
                "Value": f"{top30_trade_share:.2f}% of victim trades",
                "Interpretation": "Large share of events routed through a small set of contract takers",
            },
            {
                "Diagnostic": "Router concentration (top-30 by distinct senders, volume)",
                "Value": f"{top30_volume_share:.2f}% of victim volume",
                "Interpretation": "Intermediation intensity is material on both count and dollar bases",
            },
            {
                "Diagnostic": "Top taker by distinct senders",
                "Value": f"{max_router['distinct_senders']:,.0f} senders, {max_router['victim_trades']:,.0f} trades",
                "Interpretation": "A single taker contract can aggregate very large trader populations",
            },
            {
                "Diagnostic": "Top-30 takers with >=1,000 distinct senders",
                "Value": f"{int((top30['distinct_senders'] >= 1000).sum()):,} / 30",
                "Interpretation": "Router-heavy addresses are pervasive among the highest-throughput takers",
            },
            {
                "Diagnostic": "Identity bridge",
                "Value": f"{int(tx_from_unique_total):,} tx_from EOAs vs {int(unique_takers):,} takers",
                "Interpretation": "Confirms taker and trader identities are not interchangeable for victim incidence",
            },
        ]
        df_t10 = pd.DataFrame(table10_rows)
        tex_utils.write_table(
            df_t10,
            "table10_router_intermediation",
            "Router Intermediation Diagnostics (query0b_router_check)",
            "tab:router_intermediation",
            "Diagnostics derived from the revised router check query. They provide the empirical basis for treating router intermediation as an identification issue in protocol-level interpretations.",
            col_align="lll",
        )

        # Also export the router leaderboard by trade count for direct manuscript use.
        top_trade_count = q0b[q0b["rank_basis"] == "by_trade_count"].copy()
        if not top_trade_count.empty:
            top_trade_count = top_trade_count.sort_values("victim_trades", ascending=False)
            top_trade_count["senders_per_100_trades"] = (top_trade_count["distinct_senders"] / top_trade_count["victim_trades"]) * 100.0
            top_trade_count.to_csv("output/tables/router_check_top_takers.csv", index=False)

    # 3. H4 (Protocol Vulnerability) Formal Evaluation
    prot_sorted = prot.sort_values(by="total_volume_usd", ascending=False).copy()
    prot_sorted["share_vol"] = prot_sorted["total_volume_usd"] / prot_vol
    prot_sorted["share_pct"] = prot_sorted["share_vol"] * 100

    hhi_prot = np.sum(prot_sorted["share_vol"] ** 2) * 10000
    cr2_prot = prot_sorted["share_pct"].iloc[:2].sum()
    cr4_prot = prot_sorted["share_pct"].iloc[:4].sum()

    print(f"Protocol HHI = {hhi_prot:.1f} | CR2 (top 2) = {cr2_prot:.2f}% | CR4 = {cr4_prot:.2f}%")

    os.makedirs("output/tables", exist_ok=True)
    prot_out = prot_sorted.rename(columns={
        "project": "Protocol", "protocol": "Protocol", "sandwich_count": "Victim Trades (N)", "unique_victims": "Address Count",
        "total_volume_usd": "Total Volume (USD)", "share_pct": "Volume Share (%)"
    })[["Protocol", "Victim Trades (N)", "Address Count", "Total Volume (USD)", "Volume Share (%)"]]
    prot_out.to_csv("output/tables/protocol_vulnerability_summary.csv", index=False)

    print("[PASS] m6_synthesis completed successfully.")
    return ratio_vol, hhi_prot, cr2_prot

if __name__ == "__main__":
    run_synthesis()
