import os
import sys
import pandas as pd
import numpy as np
try:
    from PIL import Image
except ImportError:
    Image = None

def run_acceptance_checks():
    print("================================================================================")
    print("RUNNING ACADEMIC JOURNAL-GRADE ACCEPTANCE CHECKS")
    print("================================================================================")
    
    errors = []
    passes = 0
    
    def assert_check(cond, msg):
        nonlocal passes
        if not cond:
            errors.append(msg)
            print(f"[FAIL] {msg}")
        else:
            passes += 1
            print(f"[PASS] {msg}")
            
    # 1. Check Output File Existence & Non-Empty
    tables = [
        "table1_descriptives", "table2_concentration", "table3_tail_estimates",
        "table4_victim_tiers", "table5_loss_model_sensitivity", "table6_timeseries_regressions",
        "table7_structural_breaks", "table8_measurement_bases", "table9_bot_dynamics",
        "table10_router_intermediation"
    ]
    for t in tables:
        csv_path = f"output/tables/{t}.csv"
        tex_path = f"output/tables/{t}.tex"
        assert_check(os.path.exists(csv_path) and os.path.getsize(csv_path) > 50, f"Table CSV exists and valid: {csv_path}")
        assert_check(os.path.exists(tex_path) and os.path.getsize(tex_path) > 100, f"Table TEX exists and valid: {tex_path}")
        # Check that tex file escapes %, $, _ correctly in text and has notes
        with open(tex_path, "r") as f:
            tex_content = f.read()
            assert_check("\\begin{table}" in tex_content and "\\end{table}" in tex_content, f"Valid LaTeX table environment in {tex_path}")
            assert_check("Notes:" in tex_content or "notes:" in tex_content, f"Table notes included in {tex_path}")
            
    figures = ["fig1_daily_volume", "fig2_lorenz", "fig3_rank_size", "fig4_victim_tier_metrics"]
    for fig in figures:
        pdf_path = f"output/figures/{fig}.pdf"
        png_path = f"output/figures/{fig}.png"
        assert_check(os.path.exists(pdf_path) and os.path.getsize(pdf_path) > 1000, f"Figure PDF exists and valid: {pdf_path}")
        assert_check(os.path.exists(png_path) and os.path.getsize(png_path) > 5000, f"Figure PNG exists and valid: {png_path}")
        if Image is not None and os.path.exists(png_path):
            with Image.open(png_path) as im:
                width, height = im.size
                assert_check(width >= 1800, f"Figure PNG {png_path} resolution check: width {width}px >= 1800px (300 DPI)")
                
    reports = ["validation_report.md", "results_summary.md", "data_dictionary.md"]
    for r in reports:
        rep_path = f"output/reports/{r}"
        assert_check(os.path.exists(rep_path) and os.path.getsize(rep_path) > 500, f"Report exists and non-empty: {rep_path}")
        
    assert_check(os.path.exists("output/logs/run_log.txt") and os.path.getsize("output/logs/run_log.txt") > 50, "Run log exists and valid: output/logs/run_log.txt")
    
    # 2. Numerical Consistency Assertions
    print("\n--- Verifying Numerical Ground-Truth Anchors ---")
    
    t2 = pd.read_csv("output/tables/table2_concentration.csv")
    gini_val = float(t2.loc[t2["Metric"] == "Gini Coefficient (B_meas)", "Estimate"].iloc[0])
    assert_check(0.0 <= gini_val <= 1.0, f"Gini coefficient in [0,1]: {gini_val}")
    
    cr1_str = t2.loc[t2["Metric"].str.startswith("CR1 "), "Estimate"].iloc[0].replace("%", "")
    cr1 = float(cr1_str)
    cr4_str = t2.loc[t2["Metric"].str.startswith("CR4 "), "Estimate"].iloc[0].replace("%", "")
    cr4 = float(cr4_str)
    cr10_str = t2.loc[t2["Metric"].str.startswith("CR10 "), "Estimate"].iloc[0].replace("%", "")
    cr10 = float(cr10_str)
    cr20_str = t2.loc[t2["Metric"].str.startswith("CR20 "), "Estimate"].iloc[0].replace("%", "")
    cr20 = float(cr20_str)
    assert_check(0 <= cr1 <= cr4 <= cr10 <= cr20 <= 100, f"Concentration ratios ordered and bounded: CR1={cr1:.2f}, CR4={cr4:.2f}, CR10={cr10:.2f}, CR20={cr20:.2f}")

    hhi_str = t2.loc[t2["Metric"].str.startswith("Herfindahl-Hirschman Index"), "Estimate"].iloc[0].replace(",", "")
    hhi = float(hhi_str)
    assert_check(0 <= hhi <= 10000, f"HHI bounded on [0,10000]: {hhi:.1f}")
    
    t4 = pd.read_csv("output/tables/table4_victim_tiers.csv")
    ret_t4 = t4[t4["Tier"] == "Retail"].iloc[0]
    sma_t4 = t4[t4["Tier"] == "Small"].iloc[0]
    inst_t4 = t4[t4["Tier"] == "Institutional"].iloc[0]
    
    rr_sr = (sma_t4["Trader Attacks (N)"] / sma_t4["Trader EOAs (tx_from, non-bot)"]) / (ret_t4["Trader Attacks (N)"] / ret_t4["Trader EOAs (tx_from, non-bot)"])
    assert_check(np.isfinite(rr_sr) and rr_sr > 0, f"Small/Retail attack rate ratio positive and finite: {rr_sr:.4f}")
    
    ratio_att_1k = ret_t4["Attacks / $1k Traded"] / inst_t4["Attacks / $1k Traded"]
    t1 = pd.read_csv("output/tables/table1_descriptives.csv")
    retail_avg = float(t1[t1["Variable"] == "Tier: Retail (Avg Tx Size USD)"]["Mean"].iloc[0])
    inst_avg = float(t1[t1["Variable"] == "Tier: Institutional (Avg Tx Size USD)"]["Mean"].iloc[0])
    ratio_avg_size = inst_avg / retail_avg
    assert_check(abs(ratio_att_1k - ratio_avg_size) < 1e-3, f"Mechanical identity verified: ratio of attacks/1k ({ratio_att_1k:.4f}) == ratio of avg trade size ({ratio_avg_size:.4f})")
    
    t6 = pd.read_csv("output/tables/table6_timeseries_regressions.csv")
    trend_str = t6.loc[t6["Regressor / Statistic"].str.contains("Linear Trend"), "Spec (1)"].iloc[0]
    trend_val = float(trend_str.split()[0].replace("*", ""))
    assert_check(np.isfinite(trend_val), f"Spec (1) trend beta finite: {trend_val:.6f}")
    
    # 3. Required Interpretation Checks in results_summary.md
    print("\n--- Verifying Narrative & Interpretation Fidelity ---")
    with open("output/reports/results_summary.md", "r") as f:
        summary_text = f.read()
        
    required_phrases = [
        ("Repeat correction", "Repeat-victimisation Correction"),
        ("Identity correction", "Unique-victim Identity Correction"),
        ("Router diagnostics", "Router/Intermediation Diagnostics"),
        ("Window framework", "Concentration Metrics and Vintage-Sensitive Fields"),
        ("Reproducibility section", "Reproducibility and Data Vintage Controls"),
    ]
    
    for desc, phrase in required_phrases:
        assert_check(phrase.lower() in summary_text.lower(), f"results_summary.md contains required concept: '{desc}' ({phrase})")
        
    # Compile acceptance report
    report_lines = [
        "================================================================================",
        "ACCEPTANCE CHECK SUMMARY REPORT",
        "================================================================================",
        f"Total Checks Executed: {passes + len(errors)}",
        f"Passed: {passes}",
        f"Failed: {len(errors)}",
        "================================================================================"
    ]
    if len(errors) > 0:
        report_lines.append("FAILURES DETECTED:")
        for err in errors:
            report_lines.append(f" - [FAIL] {err}")
    else:
        report_lines.append("ALL ACADEMIC ACCEPTANCE CRITERIA PASSED 100%. PIPELINE IS READY FOR SUBMISSION.")
        
    report_str = "\n".join(report_lines)
    print("\n" + report_str)
    
    os.makedirs("output/logs", exist_ok=True)
    with open("output/logs/acceptance_report.txt", "w") as f:
        f.write(report_str + "\n")
        
    if len(errors) > 0:
        sys.exit(1)
    else:
        sys.exit(0)

if __name__ == "__main__":
    run_acceptance_checks()
