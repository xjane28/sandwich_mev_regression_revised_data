"""
H3 persistence and temporal-evolution analysis.

H3:
    "Extraction persists throughout 2024–2025 — occurring daily and continuing
    after major protocol upgrades — rather than being a transitory market failure."

Design
------
The primary sample is revised-24m (2024-01-01 through 2025-12-31).  The
revised-30m sample is an out-of-window temporal robustness extension through
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
import statsmodels.formula.api as smf
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


def late_sample_summary(df: pd.DataFrame, window: str, days: int) -> dict:
    z = df.tail(days)
    return {
        "window": window,
        "last_n_days": days,
        "start_date": z["date"].min().date().isoformat(),
        "end_date": z["date"].max().date().isoformat(),
        "positive_volume_days": int((z["total_sandwich_volume_usd"] > 0).sum()),
        "positive_trade_days": int((z["sandwich_trade_count"] > 0).sum()),
        "median_daily_volume_usd": float(z["total_sandwich_volume_usd"].median()),
        "mean_daily_volume_usd": float(z["total_sandwich_volume_usd"].mean()),
        "median_daily_trade_count": float(z["sandwich_trade_count"].median()),
        "median_daily_unique_bots": float(z["unique_sandwich_bots"].median()),
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
    return {
        "outcome": outcome, "specification": specification, "hac_lag": lag,
        "term": term, "estimate": b, "std_error": se,
        "ci_low": b - 1.959963984540054 * se,
        "ci_high": b + 1.959963984540054 * se,
        "p_value": p,
    }


def fit_models(df: pd.DataFrame):
    """Fit prespecified trend and upgrade-date ITS models.

    HAC(14) is the primary inference. HAC(7)/HAC(28) are lag sensitivities.
    A next-calendar-day intervention boundary is an additional timing sensitivity
    because daily aggregation makes the upgrade day itself potentially mixed.
    Holm adjustment is applied across the six primary HAC(14) upgrade joint tests
    (3 outcomes x 2 upgrades).
    """
    outcomes = {"log_volume": "log daily USD volume", "log_trades": "log daily trade count", "log_bots": "log daily unique bots"}
    coef_rows, joint_rows = [], []

    z = prepare_reg(df, event_offset_days=0)
    for y, label in outcomes.items():
        for lag in (7, 14, 28):
            trend = smf.ols(f"{y} ~ t + C(dow)", data=z).fit(cov_type="HAC", cov_kwds={"maxlags": lag})
            coef_rows.append(coef_row(trend, label, "linear_trend_plus_dow", lag, "t"))

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
                    "interpretation_scope": "prespecified upgrade-date temporal change; observational, not causal",
                })

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
                "role": "timing sensitivity; not causal",
            })

    # Functional-form sensitivity for overall evolution: add a quadratic time term.
    zq = z.copy(); zq["t2"] = zq["t"] ** 2
    nonlinear_rows = []
    for y, label in outcomes.items():
        m = smf.ols(f"{y} ~ t + t2 + C(dow)", data=zq).fit(cov_type="HAC", cov_kwds={"maxlags": 14})
        wt = m.wald_test("t = 0, t2 = 0", use_f=True, scalar=True)
        nonlinear_rows.append({
            "outcome": label, "specification": "quadratic_time_plus_dow", "hac_lag": 14,
            "linear_term": float(m.params["t"]), "quadratic_term": float(m.params["t2"]),
            "joint_f_stat": float(wt.statistic), "joint_p_value": float(wt.pvalue),
            "df_num": float(wt.df_num), "df_denom": float(wt.df_denom),
            "role": "functional-form sensitivity for temporal evolution",
        })
    return coef_rows, joint_rows, boundary_rows, nonlinear_rows


def first_last_summary(df: pd.DataFrame, n=90):
    a, b = df.head(n), df.tail(n)
    rows = []
    for col, label in [
        ("total_sandwich_volume_usd", "daily_volume_usd"),
        ("sandwich_trade_count", "daily_trade_count"),
        ("unique_sandwich_bots", "daily_unique_bots"),
    ]:
        am, bm = float(a[col].mean()), float(b[col].mean())
        rows.append({
            "metric": label, "days_per_period": n,
            "first_period_start": a["date"].min().date().isoformat(),
            "first_period_end": a["date"].max().date().isoformat(),
            "first_period_mean": am,
            "last_period_start": b["date"].min().date().isoformat(),
            "last_period_end": b["date"].max().date().isoformat(),
            "last_period_mean": bm,
            "last_over_first_ratio": bm / am if am else math.nan,
            "role": "descriptive magnitude comparison; not an independent causal test",
        })
    return rows


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
        persistence_summary(d30, "revised-30m", "temporal robustness extension"),
    ]
    post = [
        post_event_summary(d24, "Dencun", DENCUN, PRIMARY_END),
        post_event_summary(d24, "Pectra", PECTRA, PRIMARY_END),
        post_event_summary(d30, "Pectra (30m extension)", PECTRA, ROBUST_END),
    ]
    late = []
    for name, df in [("revised-24m", d24), ("revised-30m", d30)]:
        for n in (30, 60, 90):
            late.append(late_sample_summary(df, name, n))

    coefs, joint, boundary, nonlinear = fit_models(d24)
    first_last = first_last_summary(d24, 90)

    td = out / "tables"; rd = out / "reports"
    write_csv(td / "h3_persistence_summary.csv", persistence)
    write_csv(td / "h3_post_upgrade_persistence.csv", post)
    write_csv(td / "h3_late_sample_persistence.csv", late)
    write_csv(td / "h3_hac_time_series_coefficients.csv", coefs)
    write_csv(td / "h3_upgrade_joint_wald_tests.csv", joint)
    write_csv(td / "h3_upgrade_boundary_sensitivity.csv", boundary)
    write_csv(td / "h3_nonlinear_trend_sensitivity.csv", nonlinear)
    write_csv(td / "h3_first_vs_last_90d.csv", first_last)

    p = persistence[0]; ext = persistence[1]
    primary_coefs = [r for r in coefs if r["hac_lag"] == 14]
    trend = {r["outcome"]: r for r in primary_coefs if r["specification"] == "linear_trend_plus_dow" and r["term"] == "t"}
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
    for outcome, r in trend.items():
        lines.append(f"- {outcome}: HAC(14) linear-trend coefficient={r['estimate']:.6f}, 95% CI [{r['ci_low']:.6f}, {r['ci_high']:.6f}], p={r['p_value']:.4g}.")
    lines.append("")
    for r in joint14:
        lines.append(f"- {r['outcome']}, {r['event'].title()} prespecified step+slope joint HAC(14) Wald test: F({r['df_num']:.0f},{r['df_denom']:.0f})={r['f_stat']:.3f}, raw p={r['p_value']:.4g}, Holm-adjusted p={r['holm_p_value_primary_family']:.4g}.")
    lines += [
        "",
        "These regressions establish temporal association/evolution in the observed series. Upgrade-date coefficients and joint tests are not interpreted causally because the design does not isolate upgrades from other contemporaneous market changes.",
        "",
        "## 30m temporal extension",
        "",
        f"- The extension is identical to the primary data for 2024–2025 and continues through {ext['end_date']}.",
        f"- Positive sandwich volume occurs on {ext['days_positive_volume']}/{ext['calendar_days']} days ({100*ext['share_days_positive_volume']:.2f}%) through 2026-06-30.",
        f"- Minimum daily volume in the 30m series is ${ext['min_daily_volume_usd']:,.2f}; minimum daily trade count is {ext['min_daily_trade_count']:,}.",
        "- This is a temporal robustness extension, not an independent replication of the 2024–2025 result.",
        "",
        "## Evidentiary conclusion",
        "",
        "- H3's persistence implication is evaluated directly from complete calendar coverage and daily positive activity.",
        "- HAC trend and prespecified upgrade-date interrupted-time-series models provide evidence about temporal evolution while allowing serial correlation in inference. HAC(7)/HAC(28), a next-day upgrade boundary, and a quadratic time specification are sensitivity analyses. Holm adjustment controls multiplicity across the six primary HAC(14) upgrade joint tests.",
        "- Continued activity after Dencun and Pectra establishes post-upgrade persistence in the observed data, but does not identify a causal upgrade effect or prove that upgrades could not have changed the level or trend of extraction.",
        "- The data support persistence of observed sandwich activity; they do not by themselves establish the broader welfare interpretation implied by the phrase 'market failure'.",
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
