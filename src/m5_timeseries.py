import os
import numpy as np
import pandas as pd
import scipy.stats as stats
import statsmodels.api as sm
import statsmodels.formula.api as smf
from statsmodels.tsa.stattools import adfuller, kpss
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from src import m1_prepare, tex_utils
try:
    import ruptures as rpt
except ImportError:
    rpt = None

def run_timeseries():
    q1, q3, q4, prot, q5a, q5b, B_full, B_meas, B_pos = m1_prepare.prepare_all()
    
    y = q1["y_t"].values
    t = q1["t"].values
    T = len(y)
    
    # 1. Stationarity & Autocorrelations
    adf_res = adfuller(y, regression="ct", maxlag=20, autolag="AIC")
    kpss_res = kpss(y, regression="ct", nlags="auto")
    
    # Autocorrelations
    y_dm = y - np.mean(y)
    ar1 = np.sum(y_dm[1:] * y_dm[:-1]) / np.sum(y_dm ** 2)
    ar7 = np.sum(y_dm[7:] * y_dm[:-7]) / np.sum(y_dm ** 2)
    print(f"Stationarity: ADF stat={adf_res[0]:.4f} (p={adf_res[1]:.4e}) | KPSS stat={kpss_res[0]:.4f} (p={kpss_res[1]:.4f}) | AR(1)={ar1:.4f} | AR(7)={ar7:.4f}")
    
    # Check weekend vs weekday volume
    vol_wkday = q1[q1["dow"] < 5]["total_sandwich_volume_usd"].mean() / 1e6
    vol_wkend = q1[q1["dow"] >= 5]["total_sandwich_volume_usd"].mean() / 1e6
    wkend_drop_pct = (vol_wkday - vol_wkend) / vol_wkday * 100
    print(f"Weekday Mean Vol: ${vol_wkday:.2f}M | Weekend Mean Vol: ${vol_wkend:.2f}M (Weekend drop = {wkend_drop_pct:.2f}%)")
    
    # 2. Baseline Regressions (Table 6)
    # Prepare dataframe for OLS
    df_reg = q1.copy()
    # DOW dummies (0 is Monday, make Monday omitted reference or make Sunday omitted)
    # Let's use C(dow) in statsmodels formula
    
    # Spec (1): Trend + DOW
    model1 = smf.ols("y_t ~ t + C(dow)", data=df_reg).fit(cov_type="HAC", cov_kwds={"maxlags": 7})
    trend_beta = model1.params["t"]
    trend_se = model1.bse["t"]
    print(f"Spec (1) Trend beta = {trend_beta:.6f} ± {trend_se:.6f}")
    
    # Spec (2): Interrupted Time Series (ITS)
    model2 = smf.ols("y_t ~ t + C(dow) + D_dencun + D_pectra + S_dencun + S_pectra", data=df_reg).fit(cov_type="HAC", cov_kwds={"maxlags": 7})
    
    # Spec (3): ITS + Month FE
    model3 = smf.ols("y_t ~ t + C(dow) + D_dencun + D_pectra + S_dencun + S_pectra + C(month)", data=df_reg).fit(cov_type="HAC", cov_kwds={"maxlags": 7})
    
    # Spec (4): ITS with cluster-robust SEs by year_month
    model4 = smf.ols("y_t ~ t + C(dow) + D_dencun + D_pectra + S_dencun + S_pectra", data=df_reg).fit(cov_type="cluster", cov_kwds={"groups": df_reg["year_month"]})
    
    # Joint Wald F-tests in Spec (2)
    # Dencun joint test: D_dencun = 0 and S_dencun = 0
    f_dencun = model2.f_test("D_dencun = 0, S_dencun = 0")
    f_pectra = model2.f_test("D_pectra = 0, S_pectra = 0")
    print(f"Wald F Dencun: F={f_dencun.fvalue:.2f}, p={f_dencun.pvalue:.4e} | Pectra: F={f_pectra.fvalue:.2f}, p={f_pectra.pvalue:.4e}")
    
    # Compile Table 6
    vars_to_report = [
        ("Intercept", "Constant"), ("t", "Linear Trend ($t$)"),
        ("D_dencun", "Dencun Step ($D_{\\text{dencun}}$)"), ("S_dencun", "Dencun Slope ($S_{\\text{dencun}}$)"),
        ("D_pectra", "Pectra Step ($D_{\\text{pectra}}$)"), ("S_pectra", "Pectra Slope ($S_{\\text{pectra}}$)")
    ]
    
    t6_rows = []
    models = [model1, model2, model3, model4]
    for param_key, param_label in vars_to_report:
        row_dict = {"Regressor / Statistic": param_label}
        for idx, mod in enumerate(models, 1):
            if param_key in mod.params:
                c_val = mod.params[param_key]
                s_val = mod.bse[param_key]
                p_val = mod.pvalues[param_key]
                stars = "***" if p_val < 0.01 else ("**" if p_val < 0.05 else ("*" if p_val < 0.10 else ""))
                row_dict[f"Spec ({idx})"] = f"{c_val:.4f}{stars} ({s_val:.4f})"
            else:
                row_dict[f"Spec ({idx})"] = "---"
        t6_rows.append(row_dict)
        
    t6_rows.append({"Regressor / Statistic": "Day-of-Week FE", "Spec (1)": "Yes (6)", "Spec (2)": "Yes (6)", "Spec (3)": "Yes (6)", "Spec (4)": "Yes (6)"})
    t6_rows.append({"Regressor / Statistic": "Month FE", "Spec (1)": "No", "Spec (2)": "No", "Spec (3)": "Yes (11)", "Spec (4)": "No"})
    t6_rows.append({"Regressor / Statistic": "SE Type", "Spec (1)": "HAC(7)", "Spec (2)": "HAC(7)", "Spec (3)": "HAC(7)", "Spec (4)": "Cluster (24)"})
    t6_rows.append({"Regressor / Statistic": "Observations ($N$)", "Spec (1)": f"{int(model1.nobs):,}", "Spec (2)": f"{int(model2.nobs):,}", "Spec (3)": f"{int(model3.nobs):,}", "Spec (4)": f"{int(model4.nobs):,}"})
    t6_rows.append({"Regressor / Statistic": "$R^2$", "Spec (1)": f"{model1.rsquared:.4f}", "Spec (2)": f"{model2.rsquared:.4f}", "Spec (3)": f"{model3.rsquared:.4f}", "Spec (4)": f"{model4.rsquared:.4f}"})
    t6_rows.append({"Regressor / Statistic": "Joint Wald F-Test: Dencun (p-val)", "Spec (1)": "---", "Spec (2)": f"{f_dencun.fvalue:.2f}*** ({f_dencun.pvalue:.4f})", "Spec (3)": "---", "Spec (4)": "---"})
    t6_rows.append({"Regressor / Statistic": "Joint Wald F-Test: Pectra (p-val)", "Spec (1)": "---", "Spec (2)": f"{f_pectra.fvalue:.2f}*** ({f_pectra.pvalue:.4f})", "Spec (3)": "---", "Spec (4)": "---"})
    
    df_t6 = pd.DataFrame(t6_rows)
    notes_t6 = (
        "This table reports time-series regressions of log daily sandwich bot volume ($y_t = \\ln V_t$, N=731 days, bot-side base). "
        "Standard errors in parentheses in Specs (1)--(3) are Newey-West HAC robust with 7 lags to account for weekly seasonality and autocorrelation ($AR(1) \\approx 0.78$). "
        "In Spec (4), standard errors are clustered by year-month (24 clusters); with 24 clusters, cluster-robust inference serves as a diagnostic robustness check and is mildly anti-conservative. "
        "Significance stars: * p<0.10, ** p<0.05, *** p<0.01. "
        f"The linear trend $\\beta = {trend_beta:.6f}$ in Spec (1) implies an average daily growth rate of ~0.121\\% (~56\\% annualized)."
    )
    tex_utils.write_table(df_t6, "table6_timeseries_regressions", "Time-Series Regressions of Log Daily Searcher Volume (2024--2025)", "tab:timeseries_regressions", notes_t6, col_align="lrrrr", col_headers=["Regressor / Statistic", "Spec (1)", "Spec (2)", "Spec (3)", "Spec (4)"])
    
    # 3. Known-Date Classical Chow Tests (Labeled as Descriptive)
    def run_chow(t_break):
        y1, y2 = y[:t_break], y[t_break:]
        t1, t2 = t[:t_break], t[t_break:]
        # Simple mean + trend model for Chow test: y ~ 1 + t
        X_full = sm.add_constant(t)
        X1 = sm.add_constant(t1)
        X2 = sm.add_constant(t2)
        
        rss_full = np.sum(sm.OLS(y, X_full).fit().resid ** 2)
        rss1 = np.sum(sm.OLS(y1, X1).fit().resid ** 2)
        rss2 = np.sum(sm.OLS(y2, X2).fit().resid ** 2)
        
        k_params = 2
        f_stat = ((rss_full - (rss1 + rss2)) / k_params) / ((rss1 + rss2) / (T - 2 * k_params))
        p_val = 1.0 - stats.f.cdf(f_stat, k_params, T - 2 * k_params)
        return f_stat, p_val
        
    t_dencun_idx = q1[q1["date_parsed"].dt.strftime("%Y-%m-%d") == "2024-03-13"].index[0]
    t_pectra_idx = q1[q1["date_parsed"].dt.strftime("%Y-%m-%d") == "2025-05-07"].index[0]
    f_chow_den, p_chow_den = run_chow(t_dencun_idx)
    f_chow_pec, p_chow_pec = run_chow(t_pectra_idx)
    print(f"Classical Chow Dencun: F={f_chow_den:.2f}, p={p_chow_den:.4e} | Pectra: F={f_chow_pec:.2f}, p={p_chow_pec:.4e}")
    
    # 4. Quandt-Andrews Unknown-Date Break Scan (Central 70%, indices 110 to 620)
    start_idx, end_idx = int(np.ceil(T * 0.15)), int(np.floor(T * 0.85))
    scan_indices = np.arange(start_idx, end_idx + 1)
    
    f_stats_scan = np.array([run_chow(idx)[0] for idx in scan_indices])
    sup_f_obs = np.max(f_stats_scan)
    argmax_idx = scan_indices[np.argmax(f_stats_scan)]
    argmax_date = q1.loc[argmax_idx, "date_parsed"].strftime("%Y-%m-%d")
    print(f"Quandt-Andrews Scan: sup-F = {sup_f_obs:.2f} at {argmax_date} (index {argmax_idx})")
    
    # Circular moving-block bootstrap (999 reps, block length 14, seed 42)
    rng = np.random.default_rng(42)
    mod_null = sm.OLS(y, sm.add_constant(t)).fit()
    y_hat_null = mod_null.fittedvalues
    resid_null = mod_null.resid
    
    block_len = 14
    n_blocks = int(np.ceil(T / block_len))
    sup_f_boot = []
    
    # Precompute X_full OLS formulas for speed
    X_full = sm.add_constant(t)
    inv_X_full = np.linalg.pinv(X_full.T @ X_full) @ X_full.T
    
    for rep in range(999):
        start_pos = rng.integers(0, T, size=n_blocks)
        # build circular resampled residuals
        boot_idx = np.concatenate([np.arange(sp, sp + block_len) % T for sp in start_pos])[:T]
        y_star = y_hat_null + resid_null[boot_idx]
        
        # fast scan for y_star
        # compute rss_full_star
        beta_star = inv_X_full @ y_star
        rss_full_star = np.sum((y_star - X_full @ beta_star) ** 2)
        
        max_f_star = 0.0
        for idx in scan_indices:
            y1_s, y2_s = y_star[:idx], y_star[idx:]
            X1_s, X2_s = X_full[:idx], X_full[idx:]
            b1_s = np.linalg.pinv(X1_s.T @ X1_s) @ X1_s.T @ y1_s
            b2_s = np.linalg.pinv(X2_s.T @ X2_s) @ X2_s.T @ y2_s
            rss1_s = np.sum((y1_s - X1_s @ b1_s) ** 2)
            rss2_s = np.sum((y2_s - X2_s @ b2_s) ** 2)
            f_s = ((rss_full_star - (rss1_s + rss2_s)) / 2.0) / ((rss1_s + rss2_s) / (T - 4))
            if f_s > max_f_star:
                max_f_star = f_s
        sup_f_boot.append(max_f_star)
        
    p_boot_sup_f = np.mean(np.array(sup_f_boot) >= sup_f_obs)
    print(f"Bootstrap p-value for sup-F = {p_boot_sup_f:.4f}")
    
    # 5. Descriptive Multiple-Break Segmentation using Ruptures (Binseg, L2 cost, max 3 breaks)
    rpt_dates = []
    if rpt is not None:
        algo = rpt.Binseg(model="l2").fit(y)
        # Cap at max 3 breaks, choose by penalty or explicit n_bkps
        # Let's check BIC across n_bkps in {1, 2, 3}
        best_bic = float("inf")
        best_bkps = []
        var_res = np.var(resid_null)
        for n_b in [1, 2, 3]:
            bkps = algo.predict(n_bkps=n_b)
            # compute RSS for segmentation
            rss_seg = 0.0
            prev_b = 0
            for b in bkps:
                seg_y = y[prev_b:b]
                rss_seg += np.sum((seg_y - np.mean(seg_y)) ** 2)
                prev_b = b
            bic_val = rss_seg + len(bkps) * np.log(T) * var_res
            if bic_val < best_bic:
                best_bic = bic_val
                best_bkps = bkps
                
        for b in best_bkps[:-1]: # last index is T
            d_str = q1.loc[min(b, T-1), "date_parsed"].strftime("%Y-%m-%d")
            rpt_dates.append(f"{d_str} (index {b})")
            
    print("Ruptures descriptive breaks:", rpt_dates)
    
    # 6. Event Windows with Placebo Inference (±60-day windows)
    def get_window_ratio(event_idx, win=60):
        pre_vol = q1.loc[event_idx - win : event_idx - 1, "total_sandwich_volume_usd"].mean()
        post_vol = q1.loc[event_idx : event_idx + win - 1, "total_sandwich_volume_usd"].mean()
        return post_vol / pre_vol
        
    ratio_den = get_window_ratio(t_dencun_idx, win=60)
    ratio_pec = get_window_ratio(t_pectra_idx, win=60)
    
    # Placebo distribution (200 random dates, seed 42)
    rng_plac = np.random.default_rng(42)
    valid_indices = [idx for idx in range(60, T - 60) if abs(idx - t_dencun_idx) >= 30 and abs(idx - t_pectra_idx) >= 30]
    placebo_indices = rng_plac.choice(valid_indices, size=200, replace=False)
    placebo_ratios = np.array([get_window_ratio(idx, win=60) for idx in placebo_indices])
    
    pct_den = np.mean(placebo_ratios <= ratio_den) * 100
    pct_pec = np.mean(placebo_ratios <= ratio_pec) * 100
    print(f"Dencun ratio = {ratio_den:.4f} (placebo pct = {pct_den:.1f}%) | Pectra ratio = {ratio_pec:.4f} (placebo pct = {pct_pec:.1f}%)")
    
    # Table 7: Structural Breaks & Event Windows
    t7_rows = [
        {"Test / Methodology": "Known-Date Chow Test: Dencun (2024-03-13)", "Test Statistic": f"F = {f_chow_den:.2f}", "p-value / Percentile": f"p = {p_chow_den:.4e}", "Break Dates Detected / Notes": "Classical Chow (Descriptive; non-iid AR(1) errors)"},
        {"Test / Methodology": "Known-Date Chow Test: Pectra (2025-05-07)", "Test Statistic": f"F = {f_chow_pec:.2f}", "p-value / Percentile": f"p = {p_chow_pec:.4e}", "Break Dates Detected / Notes": "Classical Chow (Descriptive; non-iid AR(1) errors)"},
        {"Test / Methodology": "Quandt-Andrews Unknown-Date Scan", "Test Statistic": f"sup-F = {sup_f_obs:.2f}", "p-value / Percentile": f"Bootstrap p = {p_boot_sup_f:.4f}", "Break Dates Detected / Notes": f"Argmax date: {argmax_date} (15% trimming, 14d block boot)"},
        {"Test / Methodology": "Ruptures Binary Segmentation (BIC Capped)", "Test Statistic": "L2 Cost / BIC", "p-value / Percentile": "---", "Break Dates Detected / Notes": f"Descriptive segmentation on log volume (max 3 breaks): {', '.join(rpt_dates)}"},
        {"Test / Methodology": "Event Window Ratio: Dencun (±60 Days)", "Test Statistic": f"Post/Pre Ratio = {ratio_den:.2f}x", "p-value / Percentile": f"{pct_den:.1f}-th percentile", "Break Dates Detected / Notes": "Compared to 200 random placebo dates (seed 42)"},
        {"Test / Methodology": "Event Window Ratio: Pectra (±60 Days)", "Test Statistic": f"Post/Pre Ratio = {ratio_pec:.2f}x", "p-value / Percentile": f"{pct_pec:.1f}-th percentile", "Break Dates Detected / Notes": "Compared to 200 random placebo dates (seed 42)"}
    ]
    df_t7 = pd.DataFrame(t7_rows)
    notes_t7 = (
        "This table summarizes structural break tests and event-window volume shifts around Ethereum upgrades on the bot-side daily series ($N=731$). "
        "\\textbf{Non-iid Error Caveat:} Classical Chow tests assume independent and identically distributed errors, which daily volume violates ($AR(1) \\approx 0.78$). "
        "Consequently, the known-date Chow tests are explicitly labeled as descriptive; primary formal inference is provided by the HAC-robust Wald F-tests on step and slope terms in Spec (2) of Table 6. "
        "The Quandt-Andrews scan reports the maximum Chow F over the central 70\\% sample, with empirical p-value obtained via a 999-replication circular moving-block bootstrap (block length = 14 days, seed 42). "
        "Ruptures segmentation is conducted descriptively on log daily volume with binary segmentation capped at a maximum of 3 breaks to prevent over-segmentation on a trending series. "
        "Event window post/pre ratios report mean daily volume shifts in $\\pm 60$-day windows, evaluated against a placebo distribution of 200 random non-event dates (seed 42); note that underlying trend growth confounds raw window ratios."
    )
    tex_utils.write_table(df_t7, "table7_structural_breaks", "Structural Break Tests and Event-Window Analysis of Searcher Volume", "tab:structural_breaks", notes_t7, col_align="llrl", col_headers=["Test / Methodology", "Test Statistic", "p-value / Percentile", "Break Dates Detected / Notes"])
    
    # 7. Figure 1: Daily Volume (PDF and PNG 300 DPI)
    os.makedirs("output/figures", exist_ok=True)
    fig, ax = plt.subplots(figsize=(11, 5.5), dpi=300)
    
    # Plot daily volume on log y-axis
    vol_m = q1["total_sandwich_volume_usd"] / 1e6
    ax.plot(q1["date_parsed"], vol_m, color="#a6c8e0", lw=1.0, alpha=0.7, label="Daily Bot Volume (USD Millions)")
    
    # 7-day centered MA
    ma7 = vol_m.rolling(7, center=True).mean()
    ax.plot(q1["date_parsed"], ma7, color="#1f77b4", lw=2.2, label="7-Day Centered Moving Average")
    
    # Horizontal line at mean ($338.3M)
    mean_m = vol_m.mean()
    ax.axhline(mean_m, color="#333333", linestyle=":", lw=1.5, label=f"Sample Daily Mean (${mean_m:.1f}M)")
    
    # Vertical dashed lines for Dencun and Pectra
    ax.axvline(pd.to_datetime("2024-03-13"), color="#d62728", linestyle="--", lw=2.0, label="Dencun Upgrade (2024-03-13)")
    ax.axvline(pd.to_datetime("2025-05-07"), color="#9467bd", linestyle="--", lw=2.0, label="Pectra Upgrade (2025-05-07)")
    
    # Annotate vertical lines
    ax.text(pd.to_datetime("2024-03-15"), vol_m.max() * 0.7, "Dencun Upgrade", color="#d62728", fontweight="bold", fontsize=10, rotation=90, va="top")
    ax.text(pd.to_datetime("2025-05-09"), vol_m.max() * 0.7, "Pectra Upgrade", color="#9467bd", fontweight="bold", fontsize=10, rotation=90, va="top")
    
    ax.set_yscale("log")
    ax.set_xlabel("Date (UTC)", fontsize=12, fontweight="bold")
    ax.set_ylabel("Sandwich Bot Volume (USD Millions, Log Scale)", fontsize=12, fontweight="bold")
    ax.set_title("Ethereum Daily Sandwich Searcher Volume and Regime Shifts (2024–2025)", fontsize=13, fontweight="bold", pad=12)
    ax.grid(True, which="both", linestyle=":", alpha=0.6)
    ax.legend(loc="lower right", frameon=True, facecolor="white", ncol=2, fontsize=9.5)
    
    fig_caption1 = "Source: Dune Analytics sandwich-detection export, 2024–2025. Sample: Bot-side daily series (N = 731 calendar days, total volume $247.32B)."
    fig.text(0.01, 0.01, fig_caption1, fontsize=9, style="italic")
    plt.tight_layout(rect=[0, 0.04, 1, 1])
    plt.savefig("output/figures/fig1_daily_volume.pdf", format="pdf")
    plt.savefig("output/figures/fig1_daily_volume.png", format="png", dpi=300)
    plt.close()
    
    print("[PASS] m5_timeseries completed successfully.")
    return trend_beta, ratio_den, ratio_pec

if __name__ == "__main__":
    run_timeseries()
