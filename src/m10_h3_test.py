"""
H3 persistence and temporal-evolution analysis.

H3:
    "Extraction persists throughout 2024–2025 — occurring daily and continuing
    after major protocol upgrades — rather than being a transitory market failure."

Design
------
The primary sample is revised-24m (2024-01-01 through 2025-12-31).  The
revised-30m sample is an out-of-window descriptive persistence extension through
2026-06-30.

H3 has two empirically separable parts:
  1. Persistence: calendar coverage and positive observed sandwich activity on
     every day, including every observed day after Dencun and Pectra.
  2. Temporal evolution: HAC-robust time-series models assess trend and
     step/slope changes around the two upgrades.

Persistence is established descriptively from complete daily coverage; it does
not require a p-value.  Upgrade regressions are observational interrupted-time-
series evidence.  They test changes around upgrade dates, not causal effects of
those upgrades.  
"""
from __future__ import annotations

import argparse
import math
from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels.api as sm
import statsmodels.formula.api as smf
from statsmodels.stats.diagnostic import acorr_ljungbox
from statsmodels.stats.multitest import multipletests

DENCUN = pd.Timestamp("2024-03-13")
PECTRA = pd.Timestamp("2025-05-07")
PRIMARY_START = pd.Timestamp("2024-01-01")
PRIMARY_END = pd.Timestamp("2025-12-31")
ROBUST_END = pd.Timestamp("2026-06-30")


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--data-root", default="fetch/data")
    p.add_argument("--output-dir", default="output")
    return p.parse_args()


def load_q1(path: Path, expected_start: pd.Timestamp, expected_end: pd.Timestamp) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(path)
    df = pd.read_csv(path)
    required = {
        "date", "sandwich_trade_count", "priced_trade_count",
        "total_sandwich_volume_usd", "unique_sandwich_bots", "unique_transactions",
    }
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"{path} missing required columns: {sorted(missing)}")

    df = df.copy()
    df["date"] = pd.to_datetime(df["date"], errors="raise")
    if df["date"].duplicated().any():
        dup = df.loc[df["date"].duplicated(), "date"].dt.strftime("%Y-%m-%d").tolist()
        raise ValueError(f"Duplicate daily rows in {path}: {dup[:10]}")
    df = df.sort_values("date").reset_index(drop=True)

    expected = pd.date_range(expected_start, expected_end, freq="D")
    actual = pd.DatetimeIndex(df["date"])
    if not actual.equals(expected):
        missing_dates = expected.difference(actual)
        extra_dates = actual.difference(expected)
        raise ValueError(
            f"Calendar coverage mismatch in {path}; missing={len(missing_dates)}, extra={len(extra_dates)}, "
            f"first_missing={missing_dates[:3].tolist()}, first_extra={extra_dates[:3].tolist()}"
        )

    numeric = [c for c in required if c != "date"]
    for c in numeric:
        df[c] = pd.to_numeric(df[c], errors="raise")
        if not np.isfinite(df[c]).all():
            raise ValueError(f"Non-finite values in {path}: {c}")
        if (df[c] < 0).any():
            raise ValueError(f"Negative values in {path}: {c}")

    if (df["priced_trade_count"] > df["sandwich_trade_count"]).any():
        raise ValueError(f"priced_trade_count exceeds sandwich_trade_count in {path}")
    if (df["unique_transactions"] > df["sandwich_trade_count"]).any():
        raise ValueError(f"unique_transactions exceeds sandwich_trade_count in {path}")

    return df


def persistence_summary(df: pd.DataFrame, window: str, role: str) -> dict:
    vol = df["total_sandwich_volume_usd"]
    trades = df["sandwich_trade_count"]
    bots = df["unique_sandwich_bots"]
    return {
        "window": window,
        "analysis_role": role,
        "start_date": df["date"].min().date().isoformat(),
        "end_date": df["date"].max().date().isoformat(),
        "calendar_days": len(df),
        "days_positive_volume": int((vol > 0).sum()),
        "share_days_positive_volume": float((vol > 0).mean()),
        "days_positive_trades": int((trades > 0).sum()),
        "share_days_positive_trades": float((trades > 0).mean()),
        "days_positive_bots": int((bots > 0).sum()),
        "share_days_positive_bots": float((bots > 0).mean()),
        "min_daily_volume_usd": float(vol.min()),
        "median_daily_volume_usd": float(vol.median()),
        "mean_daily_volume_usd": float(vol.mean()),
        "p10_daily_volume_usd": float(vol.quantile(.10)),
        "p90_daily_volume_usd": float(vol.quantile(.90)),
        "min_daily_trade_count": int(trades.min()),
        "median_daily_trade_count": float(trades.median()),
        "min_daily_unique_bots": int(bots.min()),
        "median_daily_unique_bots": float(bots.median()),
    }


def post_event_summary(df: pd.DataFrame, event: str, event_date: pd.Timestamp, sample_end: pd.Timestamp) -> dict:
    z = df[(df["date"] >= event_date) & (df["date"] <= sample_end)].copy()
    if z.empty:
        raise ValueError(f"No observations after {event}")
    return {
        "event": event,
        "event_date": event_date.date().isoformat(),
        "through_date": sample_end.date().isoformat(),
        "post_event_calendar_days": len(z),
        "positive_volume_days": int((z["total_sandwich_volume_usd"] > 0).sum()),
        "share_positive_volume_days": float((z["total_sandwich_volume_usd"] > 0).mean()),
        "positive_trade_days": int((z["sandwich_trade_count"] > 0).sum()),
        "share_positive_trade_days": float((z["sandwich_trade_count"] > 0).mean()),
        "min_daily_volume_usd": float(z["total_sandwich_volume_usd"].min()),
        "median_daily_volume_usd": float(z["total_sandwich_volume_usd"].median()),
        "min_daily_trade_count": int(z["sandwich_trade_count"].min()),
    }


def prepare_reg(df: pd.DataFrame, event_offset_days: int = 0) -> pd.DataFrame:
    z = df.copy()
    # Logs are valid only if the observed series is strictly positive.  H3's
    # persistence check above establishes this before regression is called.
    for c in ["total_sandwich_volume_usd", "sandwich_trade_count", "unique_sandwich_bots"]:
        if (z[c] <= 0).any():
            raise ValueError(f"Cannot log-transform non-positive {c}")
    z["log_volume"] = np.log(z["total_sandwich_volume_usd"])
    z["log_trades"] = np.log(z["sandwich_trade_count"])
    z["log_bots"] = np.log(z["unique_sandwich_bots"])
    z["t"] = np.arange(len(z), dtype=float)
    z["dow"] = z["date"].dt.dayofweek.astype(int)
    for name, d in [("dencun", DENCUN), ("pectra", PECTRA)]:
        effective_date = d + pd.Timedelta(days=event_offset_days)
        idx = int(np.flatnonzero(z["date"].to_numpy() == np.datetime64(effective_date))[0])
        z[f"D_{name}"] = (z["t"] >= idx).astype(int)
        z[f"S_{name}"] = z[f"D_{name}"] * (z["t"] - idx)
    return z


def coef_row(model, outcome, specification, lag, term):
    b = float(model.params[term]); se = float(model.bse[term]); p = float(model.pvalues[term])
    lo = b - 1.959963984540054 * se
    hi = b + 1.959963984540054 * se
    # Step terms are multiplicative level changes. Time and slope-change terms
    # are multiplicative changes in the one-day growth factor, so their exact
    # percentage translation is interpreted per day rather than as a level shift.
    effect_type = "level_percent_change" if term.startswith("D_") else "daily_growth_factor_percent_change"
    return {
        "outcome": outcome, "specification": specification, "hac_lag": lag,
        "term": term, "estimate": b, "std_error": se,
        "ci_low": lo, "ci_high": hi, "p_value": p,
        "percent_translation_type": effect_type,
        "percent_translation": pct_effect(b),
        "percent_translation_ci_low": pct_effect(lo),
        "percent_translation_ci_high": pct_effect(hi),
    }


def residual_diagnostics(model, outcome: str) -> list[dict]:
    """Residual dependence diagnostics for the primary HAC(14) ITS model."""
    resid = pd.Series(np.asarray(model.resid, dtype=float))
    rows = []
    for lag in (1, 7, 14, 28):
        acf = float(resid.autocorr(lag=lag)) if len(resid) > lag else math.nan
        lb = acorr_ljungbox(resid, lags=[lag], return_df=True)
        rows.append({
            "outcome": outcome, "lag": lag, "residual_acf": acf,
            "ljung_box_stat": float(lb["lb_stat"].iloc[0]),
            "ljung_box_p_value": float(lb["lb_pvalue"].iloc[0]),
            "role": "diagnostic only; does not select the HAC bandwidth",
        })
    return rows


def pct_effect(beta: float) -> float:
    """Exact percentage change corresponding to a coefficient in a log outcome model."""
    return 100.0 * math.expm1(beta)


def fit_models(df: pd.DataFrame):
    """Fit the primary trend and upgrade-date ITS models.

    HAC(14) is the primary inference. HAC(7)/HAC(28) are lag sensitivities.
    A next-calendar-day intervention boundary is retained only as a robustness
    diagnostic because daily aggregation makes the upgrade day itself potentially mixed.
    Holm adjustment is applied across the six primary HAC(14) upgrade joint tests
    (3 outcomes x 2 upgrades).
    """
    outcomes = {"log_volume": "log daily USD volume", "log_trades": "log daily trade count", "log_bots": "log daily unique bots"}
    coef_rows, joint_rows = [], []
    diagnostic_rows, qmle_rows, calendar_rows = [], [], []

    z = prepare_reg(df, event_offset_days=0)
    for y, label in outcomes.items():
        for lag in (7, 14, 28):
            its = smf.ols(
                f"{y} ~ t + C(dow) + D_dencun + S_dencun + D_pectra + S_pectra", data=z
            ).fit(cov_type="HAC", cov_kwds={"maxlags": lag})
            for term in ("t", "D_dencun", "S_dencun", "D_pectra", "S_pectra"):
                coef_rows.append(coef_row(its, label, "interrupted_time_series", lag, term))
            for event in ("dencun", "pectra"):
                wt = its.wald_test(f"D_{event} = 0, S_{event} = 0", use_f=True, scalar=True)
                joint_rows.append({
                    "outcome": label, "hac_lag": lag, "event": event,
                    "event_boundary": "upgrade_date",
                    "test": f"D_{event}=0 and S_{event}=0",
                    "f_stat": float(wt.statistic), "p_value": float(wt.pvalue),
                    "df_num": float(wt.df_num), "df_denom": float(wt.df_denom),
                    "holm_p_value_primary_family": math.nan,
                    "interpretation_scope": "primary upgrade-date temporal change; observational, not causal",
                })

    # Residual dependence diagnostics for the primary HAC(14) models.
    # These describe remaining serial dependence and are not used to choose a
    # bandwidth according to statistical significance.
    for y, label in outcomes.items():
        primary = smf.ols(
            f"{y} ~ t + C(dow) + D_dencun + S_dencun + D_pectra + S_pectra", data=z
        ).fit(cov_type="HAC", cov_kwds={"maxlags": 14})
        diagnostic_rows.extend(residual_diagnostics(primary, label))

    # Calendar-seasonality robustness: add calendar-month indicators while
    # retaining the intervention structure. This is a sensitivity specification,
    # not a replacement for the primary linear-background-trend model.
    z["month_of_year"] = z["date"].dt.month.astype(int)
    for y, label in outcomes.items():
        mcal = smf.ols(
            f"{y} ~ t + C(dow) + C(month_of_year) + D_dencun + S_dencun + D_pectra + S_pectra",
            data=z,
        ).fit(cov_type="HAC", cov_kwds={"maxlags": 14})
        for event in ("dencun", "pectra"):
            wt = mcal.wald_test(f"D_{event} = 0, S_{event} = 0", use_f=True, scalar=True)
            calendar_rows.append({
                "outcome": label, "event": event, "hac_lag": 14,
                "specification": "calendar_month_seasonality_ITS",
                "f_stat": float(wt.statistic), "p_value": float(wt.pvalue),
                "df_num": float(wt.df_num), "df_denom": float(wt.df_denom),
                "role": "calendar-seasonality robustness only; raw robustness p-values are sensitivity diagnostics, not additional hypothesis-test discoveries; observational, not causal",
            })

    # Count-data robustness. Poisson pseudo-maximum-likelihood (PPML) targets the conditional mean of the
    # positive count outcomes and remains useful under overdispersion when
    # inference is based on HAC covariance. Log-OLS/HAC remains primary.
    for raw_y, label in [("sandwich_trade_count", "daily trade count"),
                         ("unique_sandwich_bots", "daily unique bots")]:
        pq = smf.glm(
            f"{raw_y} ~ t + C(dow) + D_dencun + S_dencun + D_pectra + S_pectra",
            data=z, family=sm.families.Poisson(),
        ).fit(cov_type="HAC", cov_kwds={"maxlags": 14})
        for event in ("dencun", "pectra"):
            wt = pq.wald_test(f"D_{event} = 0, S_{event} = 0", use_f=False, scalar=True)
            qmle_rows.append({
                "outcome": label, "event": event, "specification": "Poisson_PPML_HAC14",
                "wald_stat": float(wt.statistic), "p_value": float(wt.pvalue),
                "step_log_rate_ratio": float(pq.params[f"D_{event}"]),
                "step_percent_effect": pct_effect(float(pq.params[f"D_{event}"])),
                "slope_change": float(pq.params[f"S_{event}"]),
                "role": "count-data mean-model robustness only; raw robustness p-values are not additional hypothesis-test discoveries; primary inference remains log-OLS/HAC",
            })

    # Additional secondary formal tests from the same primary ITS model.
    # These do not change the model; they test linear combinations of coefficients
    # that directly answer whether the resulting post-upgrade trend is non-zero,
    # plus an omnibus test of all primary temporal terms.
    additional_rows = []
    for y, label in outcomes.items():
        its14 = smf.ols(
            f"{y} ~ t + C(dow) + D_dencun + S_dencun + D_pectra + S_pectra", data=z
        ).fit(cov_type="HAC", cov_kwds={"maxlags": 14})

        # Resulting slope after Dencun and before Pectra.
        wt_d_slope = its14.wald_test("t + S_dencun = 0", use_f=True, scalar=True)
        additional_rows.append({
            "outcome": label, "hac_lag": 14,
            "test_family": "post_upgrade_slope", "period": "post_Dencun_pre_Pectra",
            "test": "t + S_dencun = 0",
            "slope_estimate": float(its14.params["t"] + its14.params["S_dencun"]),
            "f_stat": float(wt_d_slope.statistic), "p_value": float(wt_d_slope.pvalue),
            "holm_p_value_secondary_family": math.nan,
            "df_num": float(wt_d_slope.df_num), "df_denom": float(wt_d_slope.df_denom),
            "interpretation_scope": "formal test of the resulting post-Dencun temporal slope; observational, not causal",
        })

        # Resulting slope after Pectra.
        wt_p_slope = its14.wald_test("t + S_dencun + S_pectra = 0", use_f=True, scalar=True)
        additional_rows.append({
            "outcome": label, "hac_lag": 14,
            "test_family": "post_upgrade_slope", "period": "post_Pectra",
            "test": "t + S_dencun + S_pectra = 0",
            "slope_estimate": float(its14.params["t"] + its14.params["S_dencun"] + its14.params["S_pectra"]),
            "f_stat": float(wt_p_slope.statistic), "p_value": float(wt_p_slope.pvalue),
            "holm_p_value_secondary_family": math.nan,
            "df_num": float(wt_p_slope.df_num), "df_denom": float(wt_p_slope.df_denom),
            "interpretation_scope": "formal test of the resulting post-Pectra temporal slope; observational, not causal",
        })

        # Omnibus temporal-evolution test: no linear trend, upgrade steps, or slope changes.
        wt_all = its14.wald_test(
            "t = 0, D_dencun = 0, S_dencun = 0, D_pectra = 0, S_pectra = 0",
            use_f=True, scalar=True,
        )
        additional_rows.append({
            "outcome": label, "hac_lag": 14,
            "test_family": "overall_temporal_evolution", "period": "primary_24m",
            "test": "t=D_dencun=S_dencun=D_pectra=S_pectra=0",
            "slope_estimate": math.nan,
            "f_stat": float(wt_all.statistic), "p_value": float(wt_all.pvalue),
            "holm_p_value_secondary_family": math.nan,
            "df_num": float(wt_all.df_num), "df_denom": float(wt_all.df_denom),
            "interpretation_scope": "secondary formal omnibus test of temporal evolution; observational, not causal",
        })

    # Multiplicity control for the separate family of nine secondary HAC(14)
    # formal tests (6 post-upgrade slopes + 3 overall temporal-evolution tests).
    # This family is kept separate from the six original primary upgrade tests.
    secondary_adjusted = multipletests(
        [r["p_value"] for r in additional_rows], method="holm"
    )[1]
    for r, padj in zip(additional_rows, secondary_adjusted):
        r["holm_p_value_secondary_family"] = float(padj)

    # Multiplicity control for the six primary HAC(14) upgrade-date joint tests.
    primary_idx = [i for i, r in enumerate(joint_rows) if r["hac_lag"] == 14 and r["event_boundary"] == "upgrade_date"]
    adjusted = multipletests([joint_rows[i]["p_value"] for i in primary_idx], method="holm")[1]
    for i, padj in zip(primary_idx, adjusted):
        joint_rows[i]["holm_p_value_primary_family"] = float(padj)

    # Boundary sensitivity: treat the first full post-upgrade calendar day as post.
    z_next = prepare_reg(df, event_offset_days=1)
    boundary_rows = []
    for y, label in outcomes.items():
        its = smf.ols(
            f"{y} ~ t + C(dow) + D_dencun + S_dencun + D_pectra + S_pectra", data=z_next
        ).fit(cov_type="HAC", cov_kwds={"maxlags": 14})
        for event in ("dencun", "pectra"):
            wt = its.wald_test(f"D_{event} = 0, S_{event} = 0", use_f=True, scalar=True)
            boundary_rows.append({
                "outcome": label, "hac_lag": 14, "event": event,
                "event_boundary": "next_calendar_day",
                "f_stat": float(wt.statistic), "p_value": float(wt.pvalue),
                "df_num": float(wt.df_num), "df_denom": float(wt.df_denom),
                "role": "robustness diagnostic only; raw p-values are sensitivity diagnostics, not additional hypothesis-test discoveries; not an independent H3 test; not causal",
            })

    # Functional-form robustness of the ITS: allow a quadratic background time trend
    # while retaining the same Dencun/Pectra step and slope terms. This directly checks
    # whether upgrade-date joint inferences are sensitive to the linear-background-trend assumption.
    zq = z.copy()
    zq["t2"] = zq["t"] ** 2
    nonlinear_rows = []
    for y, label in outcomes.items():
        m = smf.ols(
            f"{y} ~ t + t2 + C(dow) + D_dencun + S_dencun + D_pectra + S_pectra",
            data=zq,
        ).fit(cov_type="HAC", cov_kwds={"maxlags": 14})
        for event in ("dencun", "pectra"):
            wt = m.wald_test(f"D_{event} = 0, S_{event} = 0", use_f=True, scalar=True)
            nonlinear_rows.append({
                "outcome": label,
                "specification": "quadratic_background_trend_ITS",
                "hac_lag": 14,
                "event": event,
                "test": f"D_{event}=0 and S_{event}=0",
                "linear_time_term": float(m.params["t"]),
                "quadratic_time_term": float(m.params["t2"]),
                "f_stat": float(wt.statistic),
                "p_value": float(wt.pvalue),
                "df_num": float(wt.df_num),
                "df_denom": float(wt.df_denom),
                "role": "functional-form robustness diagnostic for upgrade-date ITS inference only; raw p-values are sensitivity diagnostics, not additional hypothesis-test discoveries; not an independent H3 test",
            })
    return coef_rows, joint_rows, boundary_rows, nonlinear_rows, additional_rows, diagnostic_rows, qmle_rows, calendar_rows


def write_csv(path: Path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(path, index=False)


def run_h3_tests(data_root="fetch/data", output_dir="output"):
    root, out = Path(data_root), Path(output_dir)
    p24 = root / "revised-24m" / "query1_mev_volume_v2.csv"
    p30 = root / "revised-30m" / "query1_mev_volume_v2.csv"
    d24 = load_q1(p24, PRIMARY_START, PRIMARY_END)
    d30 = load_q1(p30, PRIMARY_START, ROBUST_END)

    # The overlapping portion must be identical; otherwise the temporal
    # extension is not a clean extension of the primary data vintage.
    common_cols = ["date", "sandwich_trade_count", "priced_trade_count", "total_sandwich_volume_usd", "unique_sandwich_bots", "unique_transactions"]
    left = d24[common_cols].reset_index(drop=True)
    right = d30.loc[d30["date"] <= PRIMARY_END, common_cols].reset_index(drop=True)
    if not left["date"].equals(right["date"]):
        raise ValueError("24m and 30m files do not have identical dates over 2024-2025")
    for c in common_cols[1:]:
        # CSV floating-point serialization can differ by a few machine-precision
        # units, so compare numeric content with tight tolerance rather than
        # byte/string identity.
        if not np.allclose(left[c].to_numpy(dtype=float), right[c].to_numpy(dtype=float), rtol=1e-12, atol=1e-6):
            raise ValueError(f"24m and 30m files differ materially over 2024-2025 in {c}")

    persistence = [
        persistence_summary(d24, "revised-24m", "primary"),
        persistence_summary(d30, "revised-30m", "descriptive persistence extension"),
    ]
    post = [
        post_event_summary(d24, "Dencun", DENCUN, PRIMARY_END),
        post_event_summary(d24, "Pectra", PECTRA, PRIMARY_END),
        post_event_summary(d30, "Pectra (30m extension)", PECTRA, ROBUST_END),
    ]
    coefs, joint, boundary, nonlinear, additional, diagnostics, qmle, calendar = fit_models(d24)

    td = out / "tables"; rd = out / "reports"
    write_csv(td / "h3_persistence_summary.csv", persistence)
    write_csv(td / "h3_post_upgrade_persistence.csv", post)
    write_csv(td / "h3_hac_time_series_coefficients.csv", coefs)
    write_csv(td / "h3_upgrade_joint_wald_tests.csv", joint)
    write_csv(td / "h3_upgrade_boundary_sensitivity.csv", boundary)
    write_csv(td / "h3_nonlinear_trend_sensitivity.csv", nonlinear)
    write_csv(td / "h3_additional_formal_tests.csv", additional)
    write_csv(td / "h3_residual_dependence_diagnostics.csv", diagnostics)
    write_csv(td / "h3_poisson_ppml_count_robustness.csv", qmle)
    write_csv(td / "h3_calendar_seasonality_robustness.csv", calendar)

    p = persistence[0]; ext = persistence[1]
    joint14 = [r for r in joint if r["hac_lag"] == 14 and r["event_boundary"] == "upgrade_date"]

    lines = [
        "# H3 Hypothesis Testing",
        "",
        "## Hypothesis",
        "",
        'H3: "Extraction persists throughout 2024–2025 — occurring daily and continuing after major protocol upgrades — rather than being a transitory market failure."',
        "",
        "## Primary persistence result",
        "",
        f"- Primary window: {p['start_date']} through {p['end_date']} ({p['calendar_days']} consecutive calendar days).",
        f"- Positive sandwich volume occurred on {p['days_positive_volume']}/{p['calendar_days']} days ({100*p['share_days_positive_volume']:.2f}%).",
        f"- Positive sandwich trade count occurred on {p['days_positive_trades']}/{p['calendar_days']} days ({100*p['share_days_positive_trades']:.2f}%).",
        f"- At least one observed sandwich bot was present on {p['days_positive_bots']}/{p['calendar_days']} days ({100*p['share_days_positive_bots']:.2f}%).",
        f"- Minimum observed daily sandwich volume was ${p['min_daily_volume_usd']:,.2f}; median was ${p['median_daily_volume_usd']:,.2f}.",
        f"- Minimum daily sandwich trade count was {p['min_daily_trade_count']:,}; median was {p['median_daily_trade_count']:,.0f}.",
        "",
        "Persistence is a directly observed property of the complete daily series. No p-value or arbitrary minimum-volume cutoff is required to establish whether activity occurred every calendar day.",
        "",
        "## Persistence after protocol upgrades",
        "",
    ]
    for r in post[:2]:
        lines.append(
            f"- {r['event']} ({r['event_date']}): positive volume on {r['positive_volume_days']}/{r['post_event_calendar_days']} observed days through {r['through_date']} ({100*r['share_positive_volume_days']:.2f}%)."
        )
    lines += ["", "## Temporal evolution (primary 24m sample)", ""]
    for r in joint14:
        lines.append(f"- {r['outcome']}, {r['event'].title()} primary step+slope joint HAC(14) Wald test: F({r['df_num']:.0f},{r['df_denom']:.0f})={r['f_stat']:.3f}, raw p={r['p_value']:.4g}, Holm-adjusted p={r['holm_p_value_primary_family']:.4g}.")
    lines += [
        "",
        "## Additional formal temporal tests",
        "",
    ]
    for r in additional:
        if r["test_family"] == "post_upgrade_slope":
            lines.append(f"- {r['outcome']}, {r['period']}: resulting HAC(14) slope={r['slope_estimate']:.6f}; F({r['df_num']:.0f},{r['df_denom']:.0f})={r['f_stat']:.3f}, raw p={r['p_value']:.4g}, Holm-adjusted p={r['holm_p_value_secondary_family']:.4g}. This tests whether the resulting post-upgrade temporal slope equals zero.")
        else:
            lines.append(f"- {r['outcome']}, overall secondary temporal evolution: HAC(14) omnibus F({r['df_num']:.0f},{r['df_denom']:.0f})={r['f_stat']:.3f}, raw p={r['p_value']:.4g}, Holm-adjusted p={r['holm_p_value_secondary_family']:.4g}. This jointly tests whether all five temporal terms are zero; rejection means at least one temporal component differs from zero, not that every component differs from zero.")
    lines += [
        "",
        "These additional tests are secondary formal HAC(14) tests derived from the same ITS model. They are not independent replications or additional confirmations of H3. They provide secondary temporal-association inference only, not causal upgrade effects. Holm adjustment is applied across this separate family of nine secondary formal tests.",
        "",
        "These regressions establish temporal association/evolution in the observed series. Upgrade-date coefficients and joint tests are not interpreted causally because the design does not isolate upgrades from other contemporaneous market changes.",
        "",
        "## Financial time-series diagnostics and robustness",
        "",
        "- Residual ACF and Ljung-Box diagnostics are reported at 1, 7, 14, and 28 days for each primary HAC(14) ITS outcome. They are descriptive residual-dependence diagnostics; their p-values are not used as formal model-selection tests and do not determine the primary HAC bandwidth.",
        "- A calendar-month-seasonality ITS is reported as a robustness specification to assess sensitivity to broader recurring calendar patterns.",
        "- Poisson PPML with HAC(14) covariance is reported for sandwich trade counts and unique bot counts as count-data robustness. The primary specification remains log-OLS/HAC for comparability across outcomes.",
        "- Log-model coefficient tables include exact percentage translations, 100*(exp(beta)-1), and transformed confidence intervals. Step terms are reported as level percentage changes; time and slope-change terms are reported as changes in the one-day multiplicative growth factor (percentage per day).",
        "",
        "## 30m descriptive persistence extension",
        "",
        f"- The descriptive extension is identical to the primary data for 2024–2025 and continues through {ext['end_date']}.",
        "- The interrupted-time-series regressions remain restricted to the primary 24m sample; the 30m file extends only the descriptive persistence assessment.",
        f"- Positive sandwich volume occurs on {ext['days_positive_volume']}/{ext['calendar_days']} days ({100*ext['share_days_positive_volume']:.2f}%) through 2026-06-30.",
        f"- Minimum daily volume in the 30m series is ${ext['min_daily_volume_usd']:,.2f}; minimum daily trade count is {ext['min_daily_trade_count']:,}.",
        "- This is a descriptive persistence extension, not an independent replication of the 2024–2025 result.",
        "",
        "## Evidentiary conclusion",
        "",
        "- H3's persistence implication is evaluated directly from complete calendar coverage and daily positive activity.",
        "- Primary upgrade-date interrupted-time-series models provide formal evidence about temporal evolution while allowing serial correlation in inference. HAC(14) is primary and HAC(7)/HAC(28) are lag-bandwidth robustness checks. The next-day upgrade boundary and quadratic-background-trend ITS specification are robustness diagnostics only and are not counted as independent H3 tests or additional confirmation. Holm adjustment controls multiplicity across the six primary HAC(14) upgrade joint tests.",
        "- Continued activity after Dencun and Pectra establishes post-upgrade persistence in the observed data, but does not identify a causal upgrade effect or prove that upgrades could not have changed the level or trend of extraction.",
        "- If the validated complete daily series has positive activity on every calendar day, the observed data establish daily persistence over the stated sample. The analysis does not by itself establish the broader welfare interpretation implied by the phrase 'market failure'.",
    ]
    rd.mkdir(parents=True, exist_ok=True)
    (rd / "h3_hypothesis_tests.md").write_text("\n".join(lines), encoding="utf-8")

    print("[PASS] m10_h3_test completed")
    print(f"Primary daily persistence: {p['days_positive_volume']}/{p['calendar_days']} positive-volume days")
    print(f"30m extension: {ext['days_positive_volume']}/{ext['calendar_days']} positive-volume days through {ext['end_date']}")
    for r in joint14:
        print(f"HAC14 joint {r['outcome']} {r['event']}: F={r['f_stat']:.3f}, raw p={r['p_value']:.6g}, Holm p={r['holm_p_value_primary_family']:.6g}")


def main():
    a = parse_args()
    run_h3_tests(a.data_root, a.output_dir)


if __name__ == "__main__":
    main()
