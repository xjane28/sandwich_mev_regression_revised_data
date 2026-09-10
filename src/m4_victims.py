import os
import numpy as np
import pandas as pd
import scipy.stats as stats
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from src import m1_prepare, tex_utils

def poisson_rate_ratio(count_a, exp_a, count_b, exp_b):
    rate_a = count_a / exp_a
    rate_b = count_b / exp_b
    rr = rate_a / rate_b
    se_ln_rr = np.sqrt(1.0 / count_a + 1.0 / count_b)
    ci_low = rr * np.exp(-1.96 * se_ln_rr)
    ci_high = rr * np.exp(1.96 * se_ln_rr)
    return rr, ci_low, ci_high, se_ln_rr

def run_victims():
    q1, q3, q4, prot, q5a, q5b, B_full, B_meas, B_pos = m1_prepare.prepare_all()
    
    # 1. Reproduce Table 4: Victim Tiers
    t4_df = q5b.copy()
    t4_df["share_of_events_pct"] = t4_df["share_of_events"] * 100
    t4_df["share_of_volume_pct"] = t4_df["share_of_volume"] * 100
    
    # Select and rename columns for Table 4 CSV
    cols_csv = [
        "victim_tier", "avg_tx_size", "min_tx", "max_tx", "unique_victims", "victim_count",
        "total_volume", "share_of_events_pct", "share_of_volume_pct", "attacks_per_victim",
        "attacks_per_1000usd", "avg_volume_per_unique_victim"
    ]
    df_t4_out = t4_df[cols_csv].rename(columns={
        "victim_tier": "Tier", "avg_tx_size": "Avg Tx Size (USD)", "min_tx": "Min Tx (USD)",
        "max_tx": "Max Tx (USD)", "unique_victims": "Unique Victims", "victim_count": "Victim Trades (N)",
        "total_volume": "Total Volume (USD)", "share_of_events_pct": "Event Share (%)",
        "share_of_volume_pct": "Volume Share (%)", "attacks_per_victim": "Attacks / Victim",
        "attacks_per_1000usd": "Attacks / $1k Traded", "avg_volume_per_unique_victim": "Avg Vol / Victim (USD)"
    })
    
    notes_t4 = (
        "This table reports victim-side tier incidence and impact metrics across Retail, Small, and Institutional tiers on the victim-side base (3,753,918 total sandwiched trade events across 413,129 unique addresses). "
        "\\textbf{Mechanical Identity Caveat:} Within every tier, $\\text{Attacks per \\$1,000 Traded} = (\\text{Victim Trades} / \\text{Total Volume}) \\times 1,000 \\equiv 1,000 / \\text{Avg Tx Size}$. "
        "Consequently, the Retail-to-Institutional ratio of attacks per \\$1,000 traded (157.94\\times) is algebraically identical to the Institutional-to-Retail ratio of average trade sizes (\\$66,152.13 / \\$418.83 = 157.94\\times), containing no empirical information beyond the average trade size spread."
    )
    tex_utils.write_table(df_t4_out, "table4_victim_tiers", "Victim-Side Incidence and Impact Metrics by Trade-Size Tier", "tab:victim_tiers", notes_t4)
    
    # 2. Formal Inference on Attack Frequency (Poisson Exposure Model)
    ret_row = q5b[q5b["victim_tier"] == "Retail"].iloc[0]
    sma_row = q5b[q5b["victim_tier"] == "Small"].iloc[0]
    inst_row = q5b[q5b["victim_tier"] == "Institutional"].iloc[0]
    
    rr_sr, sr_low, sr_high, _ = poisson_rate_ratio(sma_row["victim_count"], sma_row["unique_victims"], ret_row["victim_count"], ret_row["unique_victims"])
    rr_si, si_low, si_high, _ = poisson_rate_ratio(sma_row["victim_count"], sma_row["unique_victims"], inst_row["victim_count"], inst_row["unique_victims"])
    rr_ri, ri_low, ri_high, _ = poisson_rate_ratio(ret_row["victim_count"], ret_row["unique_victims"], inst_row["victim_count"], inst_row["unique_victims"])
    
    print(f"Rate Ratios: Small/Retail = {rr_sr:.4f} [{sr_low:.4f}, {sr_high:.4f}] | Retail/Inst = {rr_ri:.4f} [{ri_low:.4f}, {ri_high:.4f}]")
    
    # 3. Share-vs-Share Chi-Square Goodness-of-Fit
    obs_counts = q5b["victim_count"].values
    exp_counts = q5b["share_of_volume"].values * np.sum(obs_counts)
    chi2_stat, p_chi2 = stats.chisquare(f_obs=obs_counts, f_exp=exp_counts)
    print(f"Chi-Square Goodness of Fit: X2 = {chi2_stat:.1f}, df=2, p = {p_chi2:.4e}")
    
    # 4. Mechanical-Identity Audit
    ratio_attacks_1k = ret_row["attacks_per_1000usd"] / inst_row["attacks_per_1000usd"]
    ratio_avg_tx = inst_row["avg_tx_size"] / ret_row["avg_tx_size"]
    assert abs(ratio_attacks_1k - ratio_avg_tx) < 1e-4, f"Mechanical identity failed: {ratio_attacks_1k} != {ratio_avg_tx}"
    
    # 5. Loss-Model Sensitivity Table (Table 5)
    tot_vol = q5b["total_volume"].sum()
    tot_loss_target = 0.01 * tot_vol # $274,704,694.84
    tot_attacks = q5b["victim_count"].sum()
    const_loss_per_attack = tot_loss_target / tot_attacks # $73.178121
    
    # Sqrt impact constant c
    sum_sqrt_term = np.sum(q5b["victim_count"] * np.sqrt(q5b["avg_tx_size"]))
    c_sqrt = tot_loss_target / sum_sqrt_term
    
    t5_rows = []
    for _, r in q5b.iterrows():
        tier = r["victim_tier"]
        avg_tx = r["avg_tx_size"]
        att_vic = r["attacks_per_victim"]
        
        # Model (a) Proportional (1% flat)
        loss_att_prop = 0.01 * avg_tx
        loss_vic_prop = loss_att_prop * att_vic
        bps_prop = 100.0 # exactly 100 bps
        t5_rows.append({"Tier": tier, "Loss Model": "Proportional (1% Flat)", "Loss / Attack ($)": f"{loss_att_prop:,.2f}", "Loss / Victim ($)": f"{loss_vic_prop:,.2f}", "Loss / $1,000 Traded (bps)": f"{bps_prop:.1f}"})
        
        # Model (b) Constant per attack ($73.18)
        loss_att_const = const_loss_per_attack
        loss_vic_const = loss_att_const * att_vic
        bps_const = (loss_att_const / avg_tx) * 10000.0
        t5_rows.append({"Tier": tier, "Loss Model": "Constant per Attack ($73.18)", "Loss / Attack ($)": f"{loss_att_const:,.2f}", "Loss / Victim ($)": f"{loss_vic_const:,.2f}", "Loss / $1,000 Traded (bps)": f"{bps_const:,.1f}"})
        
        # Model (c) Square-root impact
        loss_att_sqrt = c_sqrt * np.sqrt(avg_tx)
        loss_vic_sqrt = loss_att_sqrt * att_vic
        bps_sqrt = (loss_att_sqrt / avg_tx) * 10000.0
        t5_rows.append({"Tier": tier, "Loss Model": f"Square-Root Impact (c={c_sqrt:.2f})", "Loss / Attack ($)": f"{loss_att_sqrt:,.2f}", "Loss / Victim ($)": f"{loss_vic_sqrt:,.2f}", "Loss / $1,000 Traded (bps)": f"{bps_sqrt:,.1f}"})
        
    df_t5 = pd.DataFrame(t5_rows)
    notes_t5 = (
        f"This table illustrates implied victim loss incidence under three transparent loss-scaling models, all calibrated to the identical aggregate loss anchor of 1\\% of total victim volume (\\${tot_loss_target/1e6:.2f}M). "
        "Under Model (a) [Proportional], loss is 1\\% of trade size, yielding a flat 100 basis points across all tiers. "
        f"Under Model (b) [Constant per attack], each attack extracts an identical \\${const_loss_per_attack:.2f}, generating severe regressivity where Retail loses ~1,747 bps compared to ~11 bps for Institutional traders (>= 150\\times spread). "
        "Under Model (c) [Square-root impact], loss scales with the square root of trade size, producing mild regressivity. "
        "\\textbf{Illustrative Anchor & Identification Caveat:} The 1\\% aggregate loss anchor is purely illustrative and not an estimate of realized execution losses. Because realized slippage and per-trade losses are unobserved in pre-aggregated DEX data, whether MEV constitutes a 'regressive tax' per dollar traded is fundamentally unidentified; the dataset pins down attack frequencies and volume distributions, but not loss rates. "
        "\\textbf{Jensen's Inequality Note:} For Model (c), evaluating square-root impact at tier mean trade sizes understates within-tier dispersion due to the concavity of the square root function."
    )
    tex_utils.write_table(df_t5, "table5_loss_model_sensitivity", "Victim Loss Incidence Under Alternative Calibrated Loss Models", "tab:loss_sensitivity", notes_t5, col_align="llrrr", col_headers=["Tier", "Loss Model", "Loss / Attack (\\$)", "Loss / Victim (\\$)", "Loss / \\$1,000 Traded (bps)"])
    
    # 6. Tier-Cutoff Audit
    p50_val = q5a.loc[0, "p50_median"]
    p90_val = q5a.loc[0, "p90"]
    assert abs(ret_row["max_tx"] - p50_val) < 0.01, f"Retail max_tx {ret_row['max_tx']} != p50 {p50_val}"
    assert abs(sma_row["max_tx"] - 10000.0) < 0.01 and abs(inst_row["min_tx"] - 10000.0) < 0.01, "Cutoff 10,000 audit failed"
    assert abs(p90_val - 10000.0) > 100.0, f"10,000 equals p90 {p90_val}"
    
    # 7. H5 Assessment
    global_att_vic = tot_attacks / q5b["unique_victims"].sum() # 9.0865
    print(f"Global attacks per unique victim address = {global_att_vic:.4f}")
    
    # 8. Figure 4: Victim Tier Metrics (2 panels)
    os.makedirs("output/figures", exist_ok=True)
    tiers = ["Retail", "Small", "Institutional"]
    att_vic_vals = [ret_row["attacks_per_victim"], sma_row["attacks_per_victim"], inst_row["attacks_per_victim"]]
    att_1k_vals = [ret_row["attacks_per_1000usd"], sma_row["attacks_per_1000usd"], inst_row["attacks_per_1000usd"]]
    
    # Poisson 95% CI error bars for Panel A:
    # SE of rate = sqrt(count) / unique_victims = rate / sqrt(count)
    err_low_a = []
    err_high_a = []
    for r in [ret_row, sma_row, inst_row]:
        rate = r["attacks_per_victim"]
        se_rate = rate / np.sqrt(r["victim_count"])
        err_low_a.append(1.96 * se_rate)
        err_high_a.append(1.96 * se_rate)
        
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5.5), dpi=300)
    
    # Panel A: Attacks per Unique Victim
    bars1 = ax1.bar(tiers, att_vic_vals, color=["#1f77b4", "#ff7f0e", "#2ca02c"], width=0.55, alpha=0.85, edgecolor="#333333", yerr=[err_low_a, err_high_a], capsize=5)
    ax1.set_ylabel("Attacks per Unique Victim Address", fontsize=11, fontweight="bold")
    ax1.set_title("Panel A: Repeat Victimization Frequency\n(Inverted-U Non-Monotonicity)", fontsize=12, fontweight="bold", pad=10)
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
        "Source: Dune Analytics sandwich-detection export, 2024–2025. Sample: Victim-side base (3.75M attack events across 413,129 unique addresses). "
        "Notes: Panel A displays mean attacks per unique victim address with 95% Poisson confidence intervals; because victim sample sizes are in the hundreds of thousands (N >= 38,606), "
        "Poisson standard errors are extremely small (<= 0.043), rendering the 95% CI error bars smaller than the plot markers/bar caps. "
        "Panel B displays attack density per $1,000 traded on a logarithmic vertical axis. "
        "By mechanical identity, Panel B equals 1,000 divided by average trade size by construction, reflecting the 157.9x Institutional-to-Retail trade size spread."
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
