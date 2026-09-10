import os
import numpy as np
import pandas as pd
import scipy.stats as stats
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from src import m0_validate, m1_prepare, tex_utils

def poisson_rate_ratio(count_a, exp_a, count_b, exp_b):
    rate_a = count_a / exp_a
    rate_b = count_b / exp_b
    rr = rate_a / rate_b
    se_ln_rr = np.sqrt(1.0 / count_a + 1.0 / count_b)
    ci_low = rr * np.exp(-1.96 * se_ln_rr)
    ci_high = rr * np.exp(1.96 * se_ln_rr)
    return rr, ci_low, ci_high, se_ln_rr

def run_victims():
    bundle = m0_validate.load_data_bundle()
    q1 = bundle["q1"]
    q5a = bundle["q5a"]
    q5b = bundle["q5b"]
    q5c = bundle["q5c"]

    # Preserve preparation side-effects (Table 1, run log) used elsewhere in the project.
    m1_prepare.prepare_all()

    if q5c.empty:
        raise RuntimeError("query5c_repeat_victimization_v2 data is required for victim identity analysis.")

    min_date = q1["date_parsed"].min()
    max_date = q1["date_parsed"].max()
    date_window_label = f"{min_date.year}--{max_date.year}"

    q5b = q5b.copy()
    tier_addr_col = m0_validate.q5b_tier_address_col(q5b)
    q5b["share_of_events"] = q5b["victim_count"] / q5b["victim_count"].sum()
    q5b["share_of_volume"] = q5b["total_volume"] / q5b["total_volume"].sum()
    q5b["attacks_per_1000usd"] = (q5b["victim_count"] / q5b["total_volume"]) * 1000

    non_bot = q5c[q5c["is_known_bot"] == 0].copy()
    known_bot = q5c[q5c["is_known_bot"] == 1].copy()
    non_bot_rows = {row["victim_tier"]: row for _, row in non_bot.iterrows()}
    bot_rows = {row["victim_tier"]: row for _, row in known_bot.iterrows()}

    # 1. Table 4: tx_from identity-corrected observed attack composition and repeat metrics
    rows = []
    tier_order = ["Retail", "Small", "Institutional"]
    for tier in tier_order:
        qb = q5b[q5b["victim_tier"] == tier].iloc[0]
        nb = non_bot_rows[tier]
        kb = bot_rows[tier]
        rows.append(
            {
                "Tier": tier,
                "Victim Trades (N)": int(qb["victim_count"]),
                "Tier Address Obs (q5b)": int(qb[tier_addr_col]),
                "Trader EOAs (tx_from, non-bot)": int(nb["unique_eoas"]),
                "Trader Attacks (N)": int(nb["attack_events"]),
                "Attacks / Trader": float(nb["attacks_per_eoa"]),
                "Median Attacks / Trader": int(nb["median_attacks_per_eoa"]),
                "Known-Bot EOAs": int(kb["unique_eoas"]),
                "Known-Bot Attacks / EOA": float(kb["attacks_per_eoa"]),
                "Attacks / $1k Traded": float(qb["attacks_per_1000usd"]),
            }
        )
    df_t4_out = pd.DataFrame(rows)

    ret_row = q5b[q5b["victim_tier"] == "Retail"].iloc[0]
    sma_row = q5b[q5b["victim_tier"] == "Small"].iloc[0]
    inst_row = q5b[q5b["victim_tier"] == "Institutional"].iloc[0]
    ret_nb = non_bot_rows["Retail"]
    sma_nb = non_bot_rows["Small"]
    inst_nb = non_bot_rows["Institutional"]

    total_events = int(q5b["victim_count"].sum())
    total_tier_addresses = int(q5b[tier_addr_col].sum())
    total_trader_eoas = int(non_bot["unique_eoas"].sum())
    total_known_bot_eoas = int(known_bot["unique_eoas"].sum())
    ratio_attacks_1k_note = ret_row["attacks_per_1000usd"] / inst_row["attacks_per_1000usd"]
    ratio_avg_size_note = inst_row["avg_tx_size"] / ret_row["avg_tx_size"]
    notes_t4 = (
        f"This table reports observed attacked-trade composition by trade-size tier (query5b_victim_impact_v2) and tx_from identity-corrected repeat metrics (query5c_repeat_victimization_v2) across {total_events:,} attack events. "
        f"Tier-level address counts in q5b ({total_tier_addresses:,}) are non-additive tier-address observations and must not be interpreted as globally unique victims. "
        f"Primary identity counts are tx_from trader EOAs excluding known bots ({total_trader_eoas:,}); known-bot victim EOAs ({total_known_bot_eoas:,}) are reported separately. "
        "\\textbf{Median finding:} the median attacks per trader EOA equals 1 in every tier (Retail, Small, Institutional), so the repeat-victimisation hypothesis is withdrawn as a typical-case claim. "
        "\\textbf{Mechanical identity caveat:} Attacks per $1,000 traded equals 1,000 divided by average trade size by construction. "
        f"Accordingly, the Retail/Institutional attacks-per-$1k ratio ({ratio_attacks_1k_note:.2f}x) is algebraically identical to the Institutional/Retail mean-size ratio ({ratio_avg_size_note:.2f}x)."
    )
    tex_utils.write_table(
        df_t4_out,
        "table4_victim_tiers",
        "Observed Attack Composition and Repeat Metrics by Trade-Size Tier",
        "tab:victim_tiers",
        notes_t4,
    )

    # 2. Conditional repeat-event frequency ratios among observed victim EOAs
    rr_sr, sr_low, sr_high, _ = poisson_rate_ratio(sma_nb["attack_events"], sma_nb["unique_eoas"], ret_nb["attack_events"], ret_nb["unique_eoas"])
    rr_si, si_low, si_high, _ = poisson_rate_ratio(sma_nb["attack_events"], sma_nb["unique_eoas"], inst_nb["attack_events"], inst_nb["unique_eoas"])
    rr_ri, ri_low, ri_high, _ = poisson_rate_ratio(ret_nb["attack_events"], ret_nb["unique_eoas"], inst_nb["attack_events"], inst_nb["unique_eoas"])
    print(
        f"Conditional repeat-frequency ratios among observed non-bot tx_from EOAs: Small/Retail = {rr_sr:.4f} [{sr_low:.4f}, {sr_high:.4f}] "
        f"| Small/Inst = {rr_si:.4f} [{si_low:.4f}, {si_high:.4f}] | Retail/Inst = {rr_ri:.4f} [{ri_low:.4f}, {ri_high:.4f}]"
    )

    # 3. Share-vs-share composition diagnostic (non-inferential due percentile-defined tiers)
    obs_counts = q5b["victim_count"].values
    exp_counts = q5b["share_of_volume"].values * np.sum(obs_counts)
    chi2_stat, p_chi2 = stats.chisquare(f_obs=obs_counts, f_exp=exp_counts)
    print(
        f"Composition diagnostic (non-inferential): X2 = {chi2_stat:.1f}, df=2, p = {p_chi2:.4e}. "
        "Interpretation is descriptive because tiers are defined from attacked-trade percentiles."
    )

    # 4. Mechanical-Identity Audit
    ratio_attacks_1k = ret_row["attacks_per_1000usd"] / inst_row["attacks_per_1000usd"]
    ratio_avg_tx = inst_row["avg_tx_size"] / ret_row["avg_tx_size"]
    assert abs(ratio_attacks_1k - ratio_avg_tx) < 1e-4, f"Mechanical identity failed: {ratio_attacks_1k} != {ratio_avg_tx}"

    # 5. Loss-Model Sensitivity Table (Table 5), calibrated on non-bot tx_from attack frequencies
    tot_vol = q5b["total_volume"].sum()
    tot_loss_target = 0.01 * tot_vol
    tot_attacks = non_bot["attack_events"].sum()
    const_loss_per_attack = tot_loss_target / tot_attacks
    sum_sqrt_term = np.sum(non_bot["attack_events"].values * np.sqrt(q5b.set_index("victim_tier").loc[non_bot["victim_tier"], "avg_tx_size"].values))
    c_sqrt = tot_loss_target / sum_sqrt_term

    t5_rows = []
    for _, r in non_bot.iterrows():
        tier = r["victim_tier"]
        avg_tx = q5b[q5b["victim_tier"] == tier]["avg_tx_size"].iloc[0]
        att_vic = r["attacks_per_eoa"]
        loss_att_prop = 0.01 * avg_tx
        loss_vic_prop = loss_att_prop * att_vic
        bps_prop = 100.0
        t5_rows.append({"Tier": tier, "Loss Model": "Proportional (1% Flat)", "Loss / Attack ($)": f"{loss_att_prop:,.2f}", "Loss / Victim ($)": f"{loss_vic_prop:,.2f}", "Loss / $1,000 Traded (bps)": f"{bps_prop:.1f}"})

        loss_att_const = const_loss_per_attack
        loss_vic_const = loss_att_const * att_vic
        bps_const = (loss_att_const / avg_tx) * 10000.0
        t5_rows.append({"Tier": tier, "Loss Model": f"Constant per Attack (${loss_att_const:.2f})", "Loss / Attack ($)": f"{loss_att_const:,.2f}", "Loss / Victim ($)": f"{loss_vic_const:,.2f}", "Loss / $1,000 Traded (bps)": f"{bps_const:,.1f}"})

        loss_att_sqrt = c_sqrt * np.sqrt(avg_tx)
        loss_vic_sqrt = loss_att_sqrt * att_vic
        bps_sqrt = (loss_att_sqrt / avg_tx) * 10000.0
        t5_rows.append({"Tier": tier, "Loss Model": f"Square-Root Impact (c={c_sqrt:.2f})", "Loss / Attack ($)": f"{loss_att_sqrt:,.2f}", "Loss / Victim ($)": f"{loss_vic_sqrt:,.2f}", "Loss / $1,000 Traded (bps)": f"{bps_sqrt:,.1f}"})

    df_t5 = pd.DataFrame(t5_rows)
    notes_t5 = (
        f"This table reports implied loss incidence under three scaling models calibrated to an assumed normalization of 1% of total victim-side volume (${tot_loss_target/1e6:.2f}M). "
        f"Attack-frequency inputs use non-bot tx_from identity from query5c_repeat_victimization_v2 (total non-bot attacks = {int(tot_attacks):,}). "
        "Under Model (a), losses are proportional (100 bps in all tiers). Under Model (b), losses per attack are constant and therefore strongly regressive in basis points. "
        "Under Model (c), losses scale with the square root of trade size and imply milder regressivity. "
        "Because realized slippage is not observed in the aggregate exports, these are identification-bound sensitivity exercises, not direct welfare-loss estimates or an estimated MEV loss rate."
    )
    tex_utils.write_table(df_t5, "table5_loss_model_sensitivity", "Victim Loss Incidence Under Alternative Calibrated Loss Models", "tab:loss_sensitivity", notes_t5, col_align="llrrr", col_headers=["Tier", "Loss Model", "Loss / Attack (\\$)", "Loss / Victim (\\$)", "Loss / \\$1,000 Traded (bps)"])

    # 6. Tier-Cutoff Audit
    p50_val = q5a.loc[0, "p50_median"]
    p90_val = q5a.loc[0, "p90"]
    assert abs(ret_row["max_tx"] - p50_val) < 0.1, f"Retail max_tx {ret_row['max_tx']} != p50 {p50_val}"
    if "cutoff_p90" in q5b.columns and "cutoff_p50" in q5b.columns:
        cutoff_p50 = q5b["cutoff_p50"].iloc[0]
        cutoff_p90 = q5b["cutoff_p90"].iloc[0]
        assert abs(cutoff_p50 - p50_val) < 0.1, f"q5b cutoff_p50 {cutoff_p50} != q5a p50 {p50_val}"
        assert abs(cutoff_p90 - p90_val) < 0.1, f"q5b cutoff_p90 {cutoff_p90} != q5a p90 {p90_val}"
    assert sma_row["max_tx"] <= p90_val + 1e-6 and inst_row["min_tx"] >= p90_val - 1e-6, "Tier boundary around p90 failed"

    # 7. H5 Withdrawal Diagnostics
    global_att_vic = tot_attacks / non_bot["unique_eoas"].sum()
    medians = non_bot[["victim_tier", "median_attacks_per_eoa"]].set_index("victim_tier").to_dict()["median_attacks_per_eoa"]
    print(f"Global attacks per non-bot tx_from EOA = {global_att_vic:.4f}; medians by tier: {medians}")

    # 8. Figure 4: Victim Tier Metrics (2 panels)
    os.makedirs("output/figures", exist_ok=True)
    tiers = ["Retail", "Small", "Institutional"]
    att_vic_vals = [ret_nb["attacks_per_eoa"], sma_nb["attacks_per_eoa"], inst_nb["attacks_per_eoa"]]
    att_1k_vals = [ret_row["attacks_per_1000usd"], sma_row["attacks_per_1000usd"], inst_row["attacks_per_1000usd"]]

    # Poisson 95% CI error bars for Panel A based on non-bot tx_from counts
    err_low_a = []
    err_high_a = []
    for r in [ret_nb, sma_nb, inst_nb]:
        rate = r["attacks_per_eoa"]
        se_rate = rate / np.sqrt(r["attack_events"])
        err_low_a.append(1.96 * se_rate)
        err_high_a.append(1.96 * se_rate)

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5.5), dpi=300)

    # Panel A: Attacks per Trader EOA (tx_from, non-bot)
    bars1 = ax1.bar(tiers, att_vic_vals, color=["#1f77b4", "#ff7f0e", "#2ca02c"], width=0.55, alpha=0.85, edgecolor="#333333", yerr=[err_low_a, err_high_a], capsize=5)
    ax1.set_ylabel("Attacks per Trader EOA (tx_from, non-bot)", fontsize=11, fontweight="bold")
    ax1.set_title("Panel A: Mean Attack Frequency by Tier\n(Median = 1 in all tiers)", fontsize=12, fontweight="bold", pad=10)
    ax1.grid(True, axis="y", linestyle=":", alpha=0.6)
    ax1.set_ylim(0, 12)

    for idx, b in enumerate(bars1):
        ax1.text(b.get_x() + b.get_width()/2, b.get_height() + 0.3, f"{att_vic_vals[idx]:.2f}", ha="center", va="bottom", fontweight="bold", fontsize=10)

    # Panel B: Attacks per $1,000 Traded (Log scale)
    bars2 = ax2.bar(tiers, att_1k_vals, color=["#1f77b4", "#ff7f0e", "#2ca02c"], width=0.55, alpha=0.85, edgecolor="#333333")
    ax2.set_yscale("log")
    ax2.set_ylabel("Attacks per $1,000 Traded (Log Scale)", fontsize=11, fontweight="bold")
    ax2.set_title("Panel B: Attack Density per USD Volume\n(Reciprocal of Avg Trade Size)", fontsize=12, fontweight="bold", pad=10)
    ax2.grid(True, axis="y", which="both", linestyle=":", alpha=0.6)
    
    for idx, b in enumerate(bars2):
        val = att_1k_vals[idx]
        fmt_val = f"{val:.2f}" if val >= 0.1 else f"{val:.4f}"
        ax2.text(b.get_x() + b.get_width()/2, val * 1.15, fmt_val, ha="center", va="bottom", fontweight="bold", fontsize=10)

    # Footnote on figure and caption
    fig_caption = (
        f"Source: Dune Analytics sandwich-detection export, {date_window_label}. Sample: victim-side base ({total_events:,} attack events) and tx_from repeat-victimisation base ({total_trader_eoas:,} non-bot trader EOAs). "
        "Notes: Panel A uses query5c_repeat_victimization_v2 and reports mean attacks per non-bot trader EOA with 95% Poisson confidence intervals; median attacks per trader EOA equals 1 in every tier. "
        "Panel B displays attack density per $1,000 traded on a logarithmic vertical axis. "
        f"By mechanical identity, Panel B equals 1,000 divided by average trade size by construction, reflecting the {ratio_avg_size_note:.1f}x Institutional-to-Retail trade size spread."
    )
    fig.text(0.01, 0.01, fig_caption, fontsize=8.5, style="italic", wrap=True)
    plt.tight_layout(rect=[0, 0.08, 1, 1])
    plt.savefig("output/figures/fig4_victim_tier_metrics.pdf", format="pdf")
    plt.savefig("output/figures/fig4_victim_tier_metrics.png", format="png", dpi=300)
    plt.close()

    print("[PASS] m4_victims completed successfully.")
    return rr_sr, rr_ri, chi2_stat, p_chi2

if __name__ == "__main__":
    run_victims()
