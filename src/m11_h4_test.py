"""
H4 protocol-heterogeneity analysis.

H4:
    "Sandwich activity differs systematically across DEX protocols: a small set
    of protocols hosts victim trades that are orders of magnitude larger than
    the market average ('whale pools'), concentrating the highest-stakes extraction."

Purpose
-------
This module evaluates exactly how strongly the existing *aggregated protocol file*
can support H4, without pretending that protocol-level aggregates are
transaction-level observations.

What the data CAN establish descriptively:
  1. Protocol-level average victim trade sizes differ greatly.
  2. Which protocols have average victim trade sizes >=10x or >=100x the pooled
     victim-trade average (literal "orders of magnitude" diagnostics).
  3. Victim-side sandwich trade volume is concentrated across protocols (CR1/CR2/CR4, HHI).
  4. Whether these descriptive patterns remain in the 30m temporal extension.
  5. Rank stability across the overlapping 24m/30m protocol sets.

What the data CANNOT establish:
  - a transaction-level hypothesis test of equality across protocols;
  - within-protocol dispersion or transaction-level uncertainty;
  - causal effects of protocol design;
  - "extraction" as attacker profit (the file contains victim trade volume);
  - individual-pool heterogeneity, because versions/pools are aggregated to project.

No p-values are manufactured from the ~20 protocol aggregates. The 24m file is
the primary analysis; 30m is a nested temporal robustness extension, not an
independent replication.
"""

from __future__ import annotations

import argparse
import math
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
import patsy
import statsmodels.api as sm
from statsmodels.tools.sm_exceptions import PerfectSeparationWarning
from scipy import stats
from scipy.stats import spearmanr


PRIMARY_EXPECTED_VICTIM_TRADES = 3_753_857
ROBUST_EXPECTED_VICTIM_TRADES = 4_286_398

REQUIRED = {
    "project",
    "victim_trade_count",
    "total_volume_usd",
    "avg_trade_size",
    "unique_takers_in_protocol",
    "unique_eoas_in_protocol",
}


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--data-root", default="fetch/data")
    p.add_argument("--output-dir", default="output")
    return p.parse_args()


def load_protocol_file(path: Path, expected_total_victims: int) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(path)

    df = pd.read_csv(path)
    missing = REQUIRED - set(df.columns)
    if missing:
        raise ValueError(f"{path} missing required columns: {sorted(missing)}")

    df = df.copy()
    df["project"] = df["project"].astype(str).str.strip()
    if (df["project"] == "").any():
        raise ValueError(f"Blank project label in {path}")
    if df["project"].duplicated().any():
        dup = df.loc[df["project"].duplicated(), "project"].tolist()
        raise ValueError(f"Duplicate project rows in {path}: {dup}")

    numeric = sorted(REQUIRED - {"project"})
    for c in numeric:
        df[c] = pd.to_numeric(df[c], errors="raise")
        if not np.isfinite(df[c]).all():
            raise ValueError(f"Non-finite values in {path}: {c}")
        if (df[c] < 0).any():
            raise ValueError(f"Negative values in {path}: {c}")

    if (df["victim_trade_count"] <= 0).any():
        raise ValueError(f"Every protocol row must contain >=1 victim trade in {path}")
    if (df["total_volume_usd"] <= 0).any():
        raise ValueError(f"Every protocol row must contain positive victim volume in {path}")

    # The query defines avg_trade_size as SUM(amount_usd)/COUNT(*).
    implied_avg = df["total_volume_usd"] / df["victim_trade_count"]
    if not np.allclose(
        implied_avg.to_numpy(float),
        df["avg_trade_size"].to_numpy(float),
        rtol=1e-10,
        atol=1e-8,
    ):
        raise ValueError(f"avg_trade_size does not reconcile to volume/count in {path}")

    total_victims = int(round(df["victim_trade_count"].sum()))
    if total_victims != expected_total_victims:
        raise ValueError(
            f"{path}: victim trades={total_victims:,}, expected={expected_total_victims:,}"
        )

    return df.sort_values("project").reset_index(drop=True)


def gini_nonnegative(x) -> float:
    a = np.asarray(x, dtype=float)
    if len(a) == 0 or np.any(a < 0) or a.sum() <= 0:
        return math.nan
    a = np.sort(a)
    n = len(a)
    return float((2 * np.sum(np.arange(1, n + 1) * a) / (n * a.sum())) - (n + 1) / n)


def window_summary(df: pd.DataFrame, window: str, role: str) -> tuple[dict, pd.DataFrame]:
    total_trades = float(df["victim_trade_count"].sum())
    total_volume = float(df["total_volume_usd"].sum())

    # IMPORTANT: pooled market average is transaction-weighted:
    # total victim volume / total victim trades. It is NOT the unweighted
    # mean of protocol averages.
    pooled_avg = total_volume / total_trades

    z = df.copy()
    z["pooled_market_avg_trade_usd"] = pooled_avg
    z["avg_trade_size_ratio_to_pooled"] = z["avg_trade_size"] / pooled_avg
    z["volume_share"] = z["total_volume_usd"] / total_volume
    z["victim_trade_share"] = z["victim_trade_count"] / total_trades
    z["avg_trade_size_ge_10x_pooled"] = z["avg_trade_size_ratio_to_pooled"] >= 10.0
    z["avg_trade_size_ge_100x_pooled"] = z["avg_trade_size_ratio_to_pooled"] >= 100.0

    by_volume = z.sort_values("total_volume_usd", ascending=False)
    shares = by_volume["volume_share"].to_numpy(float)

    # Descriptive dispersion of protocol-level averages. These are NOT
    # transaction-level distributional statistics.
    avg_sizes = z["avg_trade_size"].to_numpy(float)

    summary = {
        "window": window,
        "analysis_role": role,
        "protocol_count": len(z),
        "victim_trade_count": int(round(total_trades)),
        "total_victim_trade_volume_usd": total_volume,
        "pooled_market_avg_victim_trade_usd": pooled_avg,
        "min_protocol_avg_trade_usd": float(np.min(avg_sizes)),
        "median_protocol_avg_trade_usd_unweighted": float(np.median(avg_sizes)),
        "max_protocol_avg_trade_usd": float(np.max(avg_sizes)),
        "max_protocol_avg_ratio_to_pooled": float(z["avg_trade_size_ratio_to_pooled"].max()),
        "protocols_ge_10x_pooled_avg": int(z["avg_trade_size_ge_10x_pooled"].sum()),
        "protocols_ge_100x_pooled_avg": int(z["avg_trade_size_ge_100x_pooled"].sum()),
        "cr1_volume_share": float(shares[:1].sum()),
        "cr2_volume_share": float(shares[:2].sum()),
        "cr4_volume_share": float(shares[:4].sum()),
        "protocol_volume_hhi_0_10000": float(10000.0 * np.sum(shares**2)),
        "gini_protocol_volume": gini_nonnegative(z["total_volume_usd"]),
        "largest_volume_protocol": str(by_volume.iloc[0]["project"]),
        "largest_avg_trade_protocol": str(z.loc[z["avg_trade_size"].idxmax(), "project"]),
    }

    cols = [
        "project",
        "victim_trade_count",
        "total_volume_usd",
        "avg_trade_size",
        "pooled_market_avg_trade_usd",
        "avg_trade_size_ratio_to_pooled",
        "avg_trade_size_ge_10x_pooled",
        "avg_trade_size_ge_100x_pooled",
        "victim_trade_share",
        "volume_share",
        "unique_eoas_in_protocol",
        "unique_takers_in_protocol",
    ]
    detail = z[cols].sort_values(
        ["avg_trade_size_ratio_to_pooled", "total_volume_usd"],
        ascending=[False, False],
    ).reset_index(drop=True)
    detail.insert(0, "window", window)
    return summary, detail


def cross_window_robustness(d24: pd.DataFrame, d30: pd.DataFrame) -> tuple[dict, pd.DataFrame]:
    common = sorted(set(d24["project"]) & set(d30["project"]))
    if not common:
        raise ValueError("No common protocols between 24m and 30m files")

    a = d24.set_index("project").loc[common]
    b = d30.set_index("project").loc[common]

    # Nested windows -> rank correlation is descriptive only. A conventional
    # independence-based p-value would not be an appropriate confirmatory test.
    rho_avg = float(spearmanr(a["avg_trade_size"], b["avg_trade_size"]).statistic)
    rho_vol = float(spearmanr(a["total_volume_usd"], b["total_volume_usd"]).statistic)

    t24 = float(d24["victim_trade_count"].sum())
    v24 = float(d24["total_volume_usd"].sum())
    t30 = float(d30["victim_trade_count"].sum())
    v30 = float(d30["total_volume_usd"].sum())
    pooled24, pooled30 = v24 / t24, v30 / t30

    x = pd.DataFrame({
        "project": common,
        "avg_trade_size_24m": a["avg_trade_size"].to_numpy(float),
        "avg_trade_size_30m": b["avg_trade_size"].to_numpy(float),
        "ratio_to_pooled_24m": a["avg_trade_size"].to_numpy(float) / pooled24,
        "ratio_to_pooled_30m": b["avg_trade_size"].to_numpy(float) / pooled30,
        "volume_24m_usd": a["total_volume_usd"].to_numpy(float),
        "volume_30m_usd": b["total_volume_usd"].to_numpy(float),
    })
    x["remains_ge_10x_pooled"] = (
        (x["ratio_to_pooled_24m"] >= 10) & (x["ratio_to_pooled_30m"] >= 10)
    )
    x["remains_ge_100x_pooled"] = (
        (x["ratio_to_pooled_24m"] >= 100) & (x["ratio_to_pooled_30m"] >= 100)
    )

    summary = {
        "common_protocols": len(common),
        "protocols_24m": len(d24),
        "protocols_30m": len(d30),
        "new_protocols_in_30m": ";".join(sorted(set(d30["project"]) - set(d24["project"]))),
        "spearman_avg_trade_size_rank_24m_vs_30m_descriptive": rho_avg,
        "spearman_volume_rank_24m_vs_30m_descriptive": rho_vol,
        "common_protocols_ge_10x_in_both_windows": int(x["remains_ge_10x_pooled"].sum()),
        "common_protocols_ge_100x_in_both_windows": int(x["remains_ge_100x_pooled"].sum()),
        "inference_note": "Nested windows: rank correlations are descriptive; no p-value reported.",
    }
    return summary, x.sort_values("ratio_to_pooled_24m", ascending=False).reset_index(drop=True)



Q5E_REQUIRED = {
    "month", "project", "version", "trade_size_bin",
    "candidate_trade_events", "attacked_trade_events", "unattacked_trade_events",
    "candidate_volume_usd", "attacked_volume_usd",
}


def load_q5e(path: Path, expected_attacked: int) -> pd.DataFrame:
    """Load genuine Q5e grouped observations. No transactions are reconstructed."""
    if not path.exists():
        raise FileNotFoundError(path)
    d = pd.read_csv(path).copy()
    missing = Q5E_REQUIRED - set(d.columns)
    if missing:
        raise ValueError(f"{path} missing Q5e columns: {sorted(missing)}")

    d["month"] = pd.to_datetime(d["month"], errors="raise", utc=True).dt.strftime("%Y-%m")
    for c in ["project", "version", "trade_size_bin"]:
        d[c] = d[c].astype(str).str.strip()
        if (d[c] == "").any():
            raise ValueError(f"Blank {c} in {path}")

    count_cols = [
        "candidate_trade_events",
        "attacked_trade_events",
        "unattacked_trade_events",
    ]
    volume_cols = ["candidate_volume_usd", "attacked_volume_usd"]

    for c in count_cols + volume_cols:
        d[c] = pd.to_numeric(d[c], errors="raise")
        if not np.isfinite(d[c]).all() or (d[c] < 0).any():
            raise ValueError(f"Invalid numeric values in {path}: {c}")

    # Grouped-binomial event counts must be integer-valued observations.
    for c in count_cols:
        values = d[c].to_numpy(float)
        if not np.allclose(values, np.round(values), rtol=0, atol=1e-8):
            raise ValueError(f"Non-integer grouped event counts in {path}: {c}")

    # A stored Q5e cell must contain at least one eligible candidate event.
    # This also guarantees that all downstream attack-rate denominators are positive.
    if (d["candidate_trade_events"] <= 0).any():
        raise ValueError(f"Q5e contains cells with zero candidate events in {path}")

    if not np.allclose(
        d["candidate_trade_events"],
        d["attacked_trade_events"] + d["unattacked_trade_events"],
        rtol=0, atol=1e-8,
    ):
        raise ValueError(f"Q5e attacked + unattacked does not reconcile in {path}")

    attacked = int(round(d["attacked_trade_events"].sum()))
    if attacked != expected_attacked:
        raise ValueError(f"{path}: attacked={attacked:,}, expected={expected_attacked:,}")

    key = ["month", "project", "version", "trade_size_bin"]
    if d.duplicated(key).any():
        raise ValueError(f"Duplicate Q5e cells in {path}")

    d["protocol_version"] = d["project"] + "::" + d["version"]
    return d


def validate_q5e_against_protocol(q5e, protocol, label):
    """Observed Q5e attacked counts and USD volume must reproduce H4 aggregates."""
    a = q5e.groupby("project", as_index=False).agg(
        victim_trade_count_q5e=("attacked_trade_events", "sum"),
        total_volume_usd_q5e=("attacked_volume_usd", "sum"),
    )
    b = protocol[["project", "victim_trade_count", "total_volume_usd"]]
    # Q5e also contains candidate-trade protocols with zero observed attacks.
    # The protocol vulnerability file, by construction, contains only protocols
    # with >=1 observed sandwich victim. Extra Q5e projects are therefore valid
    # only when both attacked count and attacked volume are exactly zero.
    extra = a.loc[~a["project"].isin(b["project"])].copy()
    if not extra.empty:
        if (extra["victim_trade_count_q5e"] != 0).any() or (extra["total_volume_usd_q5e"] != 0).any():
            raise ValueError(f"{label}: Q5e has attacked projects absent from protocol file")

    m = a.loc[a["project"].isin(b["project"])].merge(b, on="project", how="outer", indicator=True)
    if not (m["_merge"] == "both").all():
        raise ValueError(f"{label}: attacked-project coverage differs between Q5e and protocol file")
    if not np.allclose(m["victim_trade_count_q5e"], m["victim_trade_count"], rtol=0, atol=1e-8):
        raise ValueError(f"{label}: Q5e attacked counts do not reproduce protocol counts")
    if not np.allclose(m["total_volume_usd_q5e"], m["total_volume_usd"], rtol=1e-12, atol=1e-5):
        raise ValueError(f"{label}: Q5e attacked volume does not reproduce protocol volume")


def fit_protocol_attack_incidence(q5e):
    """
    Aggregate-level H4 attack-incidence model and sensitivity diagnostic.

    attacked_g ~ Binomial(candidate_g, p_g)
    logit(p_g) = protocol FE + trade-size-bin FE + month FE

    H0: all non-reference protocol coefficients are zero.

    Inference uses a calendar-month-clustered CR1 sandwich covariance and an
    F reference with G-1 denominator df. With only 24 monthly clusters in
    the primary window, this omnibus p-value is retained as an approximate
    sensitivity diagnostic rather than treated as definitive confirmatory inference. It evaluates
    protocol heterogeneity in ATTACK INCIDENCE using genuine grouped Q5e observations.
    It is not a transaction-level test of continuous victim trade size.
    """
    d = q5e.copy()

    # Restrict the model comparison to protocols that actually host at least
    # one observed sandwich victim in the window. Candidate-only protocols with
    # zero attacks would create complete separation in an unpenalized logit and
    # are not present in the protocol-vulnerability H4 table.
    attacked_by_project = d.groupby("project")["attacked_trade_events"].transform("sum")
    d = d.loc[attacked_by_project > 0].copy()

    ref = (
        d.groupby("project")["candidate_trade_events"].sum()
        .sort_values(ascending=False).index[0]
    )

    formula = (
        f"C(project, Treatment(reference={ref!r}))"
        " + C(trade_size_bin)"
        " + C(month)"
    )
    X = patsy.dmatrix(formula, d, return_type="dataframe")
    y = np.column_stack([
        d["attacked_trade_events"].to_numpy(float),
        d["unattacked_trade_events"].to_numpy(float),
    ])
    res = sm.GLM(y, X, family=sm.families.Binomial()).fit(maxiter=300)
    if not bool(res.converged):
        raise RuntimeError("H4 grouped-binomial GLM did not converge")

    Xn = np.asarray(X, dtype=float)
    if np.linalg.matrix_rank(Xn) != Xn.shape[1]:
        raise RuntimeError("H4 design matrix is rank deficient")

    beta = np.asarray(res.params, dtype=float)
    n = d["candidate_trade_events"].to_numpy(float)
    yy = d["attacked_trade_events"].to_numpy(float)
    p = np.asarray(res.fittedvalues, dtype=float)
    W = n * p * (1.0 - p)

    bread_inv = np.linalg.pinv(Xn.T @ (W[:, None] * Xn))
    scores = Xn * (yy - n * p)[:, None]

    clusters = d["month"].astype(str).to_numpy()
    unique = np.unique(clusters)
    G = len(unique)
    meat = np.zeros((Xn.shape[1], Xn.shape[1]))
    for cl in unique:
        s = scores[clusters == cl].sum(axis=0)
        meat += np.outer(s, s)

    cov = bread_inv @ meat @ bread_inv
    N, K = len(d), Xn.shape[1]
    if G <= 1:
        raise RuntimeError("H4 CR1 covariance requires at least two month clusters")
    if N <= K:
        raise RuntimeError(
            f"H4 CR1 covariance requires more grouped cells than design columns "
            f"(N={N}, K={K})"
        )
    cov *= (G / (G - 1)) * ((N - 1) / (N - K))
    if not np.isfinite(cov).all():
        raise RuntimeError("Non-finite H4 CR1 covariance")

    names = list(X.columns)
    idx = [i for i, name in enumerate(names)
           if name.startswith("C(project, Treatment(reference=")]
    q = len(idx)
    if q != d["project"].nunique() - 1:
        raise RuntimeError("Unexpected number of protocol coefficients")

    b = beta[idx]
    V = cov[np.ix_(idx, idx)]
    rank_v = int(np.linalg.matrix_rank(V))
    if rank_v != q:
        raise RuntimeError(
            f"Protocol restriction covariance rank deficient ({rank_v} < {q}); "
            "an invalid omnibus test will not be reported."
        )

    wald = float(b.T @ np.linalg.solve(V, b))
    F = wald / q
    pval = float(stats.f.sf(F, q, G - 1))

    return {
        "reference_protocol": ref,
        "protocols": int(d["project"].nunique()),
        "month_clusters": G,
        "cells": len(d),
        "restrictions": q,
        "wald_chi2": wald,
        "F": F,
        "df_num": q,
        "df_den": G - 1,
        "p_value": pval,
        "inference_method": (
            "grouped-binomial logit; month and trade-size-bin FE; "
            "calendar-month-clustered CR1; F reference with G-1 df"
        ),
        "null_hypothesis": "all non-reference protocol attack-incidence coefficients are zero",
        "inferential_role": "approximate sensitivity diagnostic; not confirmatory",
        "scope": "aggregate-level attack-incidence model conditional on protocols having >=1 observed attacked event; zero-attack eligible protocols are outside this model estimand; not continuous transaction-size inference",
        "confirmatory_status": "approximate sensitivity only; numerical p-value retained for transparency but must not be used as an H4 support/rejection decision rule because monthly clusters are limited relative to the high-dimensional protocol block",
    }


def holm_adjust(p_values):
    """Holm family-wise-error adjustment, implemented directly."""
    p = np.asarray(p_values, dtype=float)
    m = len(p)
    order = np.argsort(p)
    out = np.empty(m, dtype=float)
    running = 0.0
    for rank, i in enumerate(order):
        val = (m - rank) * p[i]
        running = max(running, val)
        out[i] = min(1.0, running)
    return out


def fit_protocol_pairwise_contrasts(q5e):
    """
    Exploratory pairwise protocol contrasts from the same grouped-binomial model.

    These compare adjusted protocol log-odds/odds ratios conditional on month
    and trade-size bin. Holm adjustment is supplied only as an exploratory
    multiplicity diagnostic; the underlying month-clustered CR1 uncertainty
    remains approximate with the limited cluster count. No transaction-level
    observations are created.
    """
    d = q5e.copy()
    attacked_by_project = d.groupby("project")["attacked_trade_events"].transform("sum")
    d = d.loc[attacked_by_project > 0].copy()
    projects = sorted(d["project"].unique())

    ref = (
        d.groupby("project")["candidate_trade_events"].sum()
        .sort_values(ascending=False).index[0]
    )
    formula = (
        f"C(project, Treatment(reference={ref!r}))"
        " + C(trade_size_bin) + C(month)"
    )
    X = patsy.dmatrix(formula, d, return_type="dataframe")
    y = np.column_stack([
        d["attacked_trade_events"].to_numpy(float),
        d["unattacked_trade_events"].to_numpy(float),
    ])
    res = sm.GLM(y, X, family=sm.families.Binomial()).fit(maxiter=300)
    if not bool(res.converged):
        raise RuntimeError("Pairwise grouped-binomial GLM did not converge")

    Xn = np.asarray(X, float)
    if np.linalg.matrix_rank(Xn) != Xn.shape[1]:
        raise RuntimeError("Pairwise H4 design matrix is rank deficient")
    beta = np.asarray(res.params, float)
    if not np.isfinite(beta).all():
        raise RuntimeError("Pairwise H4 model produced non-finite coefficients")
    n = d["candidate_trade_events"].to_numpy(float)
    yy = d["attacked_trade_events"].to_numpy(float)
    prob = np.asarray(res.fittedvalues, float)
    W = n * prob * (1 - prob)
    bread_inv = np.linalg.pinv(Xn.T @ (W[:, None] * Xn))
    scores = Xn * (yy - n * prob)[:, None]

    clusters = d["month"].astype(str).to_numpy()
    unique = np.unique(clusters)
    G = len(unique)
    meat = np.zeros((Xn.shape[1], Xn.shape[1]))
    for cl in unique:
        s = scores[clusters == cl].sum(axis=0)
        meat += np.outer(s, s)
    cov = bread_inv @ meat @ bread_inv
    N, K = len(d), Xn.shape[1]
    if G <= 1:
        raise RuntimeError("Pairwise H4 CR1 covariance requires at least two month clusters")
    if N <= K:
        raise RuntimeError(
            f"Pairwise H4 CR1 covariance requires more grouped cells than design columns "
            f"(N={N}, K={K})"
        )
    cov *= (G / (G - 1)) * ((N - 1) / (N - K))
    if not np.isfinite(cov).all():
        raise RuntimeError("Pairwise H4 CR1 covariance is non-finite")

    names = list(X.columns)
    coef_index = {}
    for project in projects:
        if project == ref:
            coef_index[project] = None
        else:
            matches = [
                i for i, nm in enumerate(names)
                if nm.startswith("C(project, Treatment(reference=")
                and nm.endswith(f"[T.{project}]")
            ]
            if len(matches) != 1:
                raise RuntimeError(f"Cannot identify coefficient for {project}")
            coef_index[project] = matches[0]

    rows = []
    for ia in range(len(projects)):
        for ib in range(ia + 1, len(projects)):
            a, b = projects[ia], projects[ib]
            c = np.zeros(len(beta))
            if coef_index[a] is not None:
                c[coef_index[a]] += 1
            if coef_index[b] is not None:
                c[coef_index[b]] -= 1
            est = float(c @ beta)
            var = float(c @ cov @ c)
            if not np.isfinite(var) or var <= 0:
                raise RuntimeError(f"Invalid contrast variance for {a} vs {b}")
            se = np.sqrt(var)
            t = est / se
            pv = float(2 * stats.t.sf(abs(t), G - 1))
            crit = float(stats.t.ppf(0.975, G - 1))
            rows.append({
                "protocol_a": a, "protocol_b": b,
                "log_odds_difference_a_minus_b": est,
                "odds_ratio_a_vs_b": float(np.exp(est)),
                "ci95_low_or": float(np.exp(est - crit * se)),
                "ci95_high_or": float(np.exp(est + crit * se)),
                "t_stat": t, "df": G - 1, "p_value_raw": pv,
            })

    adj = holm_adjust([r["p_value_raw"] for r in rows])
    for r, ap in zip(rows, adj):
        r["p_value_holm_exploratory"] = float(ap)
        r["inference_status"] = (
            "exploratory diagnostic only: month-clustered CR1 with a limited "
            "number of clusters; no confirmatory significance classification"
        )
    return rows


def fit_protocol_linear_time_heterogeneity(q5e):
    """
    Protocol x linear-time heterogeneity is intentionally NOT assigned an
    omnibus p-value here.

    Reason: the primary window has only 24 independent calendar-month clusters,
    while the interaction block contains approximately one restriction per
    non-reference protocol. A numerically full-rank CR1 covariance is not enough
    to make that high-dimensional finite-cluster Wald test reliable.

    The analysis is omitted rather than presenting fragile significance.
    """
    d = q5e.copy()
    attacked_by_project = d.groupby("project")["attacked_trade_events"].transform("sum")
    d = d.loc[attacked_by_project > 0].copy()
    G = int(d["month"].nunique())
    q = int(d["project"].nunique() - 1)
    return {
        "protocols": int(d["project"].nunique()),
        "month_clusters": G,
        "restrictions": q,
        "F": np.nan,
        "df_num": q,
        "df_den": G - 1,
        "p_value": np.nan,
        "reportable": False,
        "null_hypothesis": "all protocol-specific linear calendar-time interactions are zero",
        "scope": "not formally tested",
        "reason": (
            "omitted: too many protocol-by-time restrictions relative to the "
            "number of independent monthly clusters for reliable finite-cluster inference"
        ),
    }

def covariance_audit(q5e):
    """
    Audit the grouped-binomial protocol model using only observed Q5e data.

    Reports:
      * cluster structure by project/version and month;
      * number of protocols represented by only one project/version cluster;
      * design-matrix rank and condition number;
      * Pearson and deviance dispersion diagnostics;
      * omnibus protocol test under:
          (a) month-clustered CR1,
          (b) HC0 cell-robust covariance,
          (c) Pearson-scaled quasi-binomial/model covariance.
    These are numerical/model diagnostics and sensitivity calculations, not
    interchangeable confirmatory tests. HC0 and quasi-binomial covariance do
    not solve the limited-independent-month-cluster problem.
    Project/version-clustered protocol-effect inference is deliberately NOT
    reported as a valid sensitivity because for single-version protocols the
    cluster aligns with the protocol fixed effect and can mechanically collapse
    the relevant score variation.
    """
    d = q5e.copy()
    attacked_by_project = d.groupby("project")["attacked_trade_events"].transform("sum")
    d = d.loc[attacked_by_project > 0].copy()
    ref = d.groupby("project")["candidate_trade_events"].sum().idxmax()

    formula = f"C(project, Treatment(reference={ref!r})) + C(trade_size_bin) + C(month)"
    X = patsy.dmatrix(formula, d, return_type="dataframe")
    y = np.column_stack([
        d["attacked_trade_events"].to_numpy(float),
        d["unattacked_trade_events"].to_numpy(float),
    ])
    res = sm.GLM(y, X, family=sm.families.Binomial()).fit(maxiter=300)
    if not bool(res.converged):
        raise RuntimeError("Covariance-audit grouped-binomial GLM did not converge")

    Xn = np.asarray(X, float)
    if np.linalg.matrix_rank(Xn) != Xn.shape[1]:
        raise RuntimeError("Covariance-audit H4 design matrix is rank deficient")
    if not np.isfinite(np.asarray(res.params, float)).all():
        raise RuntimeError("Covariance-audit H4 model produced non-finite coefficients")

    names = list(X.columns)
    idx = [i for i, nm in enumerate(names)
           if nm.startswith("C(project, Treatment(reference=")]
    b = np.asarray(res.params, float)[idx]
    q = len(idx)

    def omnibus_from_cov(cov, label, df_den=None):
        V = np.asarray(cov, float)[np.ix_(idx, idx)]
        rank = int(np.linalg.matrix_rank(V))
        mineig = float(np.linalg.eigvalsh((V + V.T) / 2).min())
        if rank != q or mineig <= 0:
            return {
                "covariance": label, "numerically_usable": False,
                 "inferential_role": "diagnostic only",
                "restrictions": q, "cov_rank": rank, "min_eigenvalue": mineig,
                "F": np.nan, "df_num": q, "df_den": df_den, "p_value": np.nan,
            }
        w = float(b.T @ np.linalg.solve(V, b))
        F = w / q
        if df_den is None:
            pv = float(stats.chi2.sf(w, q))
        else:
            pv = float(stats.f.sf(F, q, df_den))
        return {
            "covariance": label, "numerically_usable": True,
             "inferential_role": "diagnostic only",
            "restrictions": q, "cov_rank": rank, "min_eigenvalue": mineig,
            "F": F, "df_num": q, "df_den": df_den, "p_value": pv,
        }

    # Month-clustered CR1.
    month_fit = sm.GLM(y, X, family=sm.families.Binomial()).fit(
        cov_type="cluster",
        cov_kwds={"groups": d["month"].astype(str), "use_correction": True},
        maxiter=300,
    )
    if not bool(month_fit.converged):
        raise RuntimeError("Month-clustered covariance-audit GLM did not converge")
    month_cov = np.asarray(month_fit.cov_params(), float)
    if not np.isfinite(month_cov).all():
        raise RuntimeError("Month-clustered covariance-audit covariance is non-finite")

    rows = [omnibus_from_cov(
        month_cov, "calendar-month clustered CR1",
        d["month"].nunique() - 1
    )]

    # Cell-robust sandwich sensitivity.
    hc0_fit = sm.GLM(y, X, family=sm.families.Binomial()).fit(
        cov_type="HC0", maxiter=300
    )
    if not bool(hc0_fit.converged):
        raise RuntimeError("HC0 covariance-audit GLM did not converge")
    hc0_cov = np.asarray(hc0_fit.cov_params(), float)
    if not np.isfinite(hc0_cov).all():
        raise RuntimeError("HC0 covariance-audit covariance is non-finite")

    rows.append(omnibus_from_cov(hc0_cov, "HC0 cell-robust", None))

    # Pearson-scaled quasi-binomial/model covariance sensitivity.
    if res.df_resid <= 0:
        raise RuntimeError("Pearson-scaled covariance requires positive residual degrees of freedom")
    pearson_scale = float(res.pearson_chi2 / res.df_resid)
    quasi_cov = np.asarray(res.normalized_cov_params, float) * pearson_scale
    if not np.isfinite(pearson_scale) or pearson_scale < 0:
        raise RuntimeError("Invalid Pearson dispersion estimate in covariance audit")
    if not np.isfinite(quasi_cov).all():
        raise RuntimeError("Pearson-scaled covariance-audit covariance is non-finite")
    rows.append(omnibus_from_cov(
        quasi_cov, "Pearson-scaled quasi-binomial", int(res.df_resid)
    ))

    pv_per_project = d.groupby("project")["protocol_version"].nunique()
    diagnostics = {
        "cells": len(d),
        "protocols": int(d["project"].nunique()),
        "project_version_clusters": int(d["protocol_version"].nunique()),
        "month_clusters": int(d["month"].nunique()),
        "protocols_with_one_project_version": int((pv_per_project == 1).sum()),
        "protocols_with_multiple_project_versions": int((pv_per_project > 1).sum()),
        "design_columns": int(X.shape[1]),
        "design_rank": int(np.linalg.matrix_rank(np.asarray(X, float))),
        "design_condition_number": float(np.linalg.cond(np.asarray(X, float))),
        "converged": bool(res.converged),
        "pearson_dispersion": pearson_scale,
        "deviance_dispersion": float(res.deviance / res.df_resid),
        "note": (
            "Dispersion and covariance comparisons are diagnostics. Naive model-based "
            "binomial uncertainty can be misleading under overdispersion/dependence; "
            "HC0 or Pearson scaling does not replace missing independent cluster information."
        ),
    }
    return diagnostics, rows


def attack_prevalence_analysis(q5e, window):
    """Observed attack prevalence by protocol/version/size/month; no synthetic rows."""
    def agg(cols):
        z = q5e.groupby(cols, as_index=False).agg(
            candidate_trade_events=("candidate_trade_events", "sum"),
            attacked_trade_events=("attacked_trade_events", "sum"),
            unattacked_trade_events=("unattacked_trade_events", "sum"),
            candidate_volume_usd=("candidate_volume_usd", "sum"),
            attacked_volume_usd=("attacked_volume_usd", "sum"),
        )
        z["attack_rate"] = z["attacked_trade_events"] / z["candidate_trade_events"]
        z["share_of_all_attacks"] = z["attacked_trade_events"] / q5e["attacked_trade_events"].sum()
        z.insert(0, "window", window)
        return z
    return {
        "protocol": agg(["project"]).sort_values(["attack_rate","attacked_trade_events"], ascending=False),
        "protocol_version": agg(["project","version"]).sort_values(["attack_rate","attacked_trade_events"], ascending=False),
        "trade_size": agg(["trade_size_bin"]).sort_values("attack_rate", ascending=False),
        "month": agg(["month"]).sort_values("attack_rate", ascending=False),
    }


def adjusted_protocol_probabilities(q5e, window):
    """
    Descriptive model-adjusted protocol attack-probability point estimates.

    Standardization holds the observed pooled month x trade-size-bin candidate
    composition fixed and changes only the protocol indicator. These are
    descriptive standardized point estimates, not confirmatory rankings. The pooled target can include month x size cells outside a given protocol's observed support, so protocol-specific observed/extrapolated target-mass diagnostics are reported.
    """
    d = q5e.copy()
    attacked_by_project = d.groupby("project")["attacked_trade_events"].transform("sum")
    d = d.loc[
        (attacked_by_project > 0) & (d["candidate_trade_events"] > 0)
    ].copy()

    if d.empty or d["project"].nunique() < 2:
        raise RuntimeError(
            "Adjusted-probability model requires at least two protocols with observed attacks"
        )

    ref = (
        d.groupby("project")["candidate_trade_events"]
        .sum()
        .sort_values(ascending=False)
        .index[0]
    )
    formula = (
        f"C(project, Treatment(reference={ref!r}))"
        " + C(trade_size_bin) + C(month)"
    )
    X = patsy.dmatrix(formula, d, return_type="dataframe")
    y = np.column_stack([
        d["attacked_trade_events"].to_numpy(float),
        d["unattacked_trade_events"].to_numpy(float),
    ])

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        res = sm.GLM(y, X, family=sm.families.Binomial()).fit(maxiter=300)

    separation = any(
        issubclass(w.category, PerfectSeparationWarning) for w in caught
    )
    if separation:
        raise RuntimeError(
            "Adjusted-probability grouped-binomial GLM raised a perfect-separation warning"
        )
    if not bool(res.converged):
        raise RuntimeError("Adjusted-probability grouped-binomial GLM did not converge")

    Xn = np.asarray(X, float)
    if np.linalg.matrix_rank(Xn) != Xn.shape[1]:
        raise RuntimeError("Adjusted-probability H4 design matrix is rank deficient")
    if not np.isfinite(np.asarray(res.params, float)).all():
        raise RuntimeError("Adjusted-probability H4 model produced non-finite coefficients")

    std = (
        d.groupby(
            ["month", "trade_size_bin"],
            observed=True,
            as_index=False,
        )["candidate_trade_events"]
        .sum()
    )
    total_weight = float(std["candidate_trade_events"].sum())
    if total_weight <= 0:
        raise RuntimeError("Adjusted-probability standardization has zero candidate weight")
    weights = std["candidate_trade_events"].to_numpy(float) / total_weight

    rows = []
    for project in sorted(d["project"].unique()):
        nd = std[["month", "trade_size_bin"]].copy()
        nd["project"] = project
        XX = patsy.build_design_matrices(
            [X.design_info], nd, return_type="dataframe"
        )[0]
        pr = np.asarray(res.predict(XX), float)
        if not np.isfinite(pr).all():
            raise RuntimeError(
                f"Non-finite adjusted protocol probabilities for {project}"
            )
        if ((pr < 0) | (pr > 1)).any():
            raise RuntimeError(
                f"Adjusted protocol probabilities outside [0,1] for {project}"
            )

        adjusted = float(np.sum(weights * pr))

        # Diagnose empirical support for the pooled standardization target.
        # This does NOT alter the estimand: it reports how much of the pooled
        # candidate-event standardization mass lies on month x size cells that
        # were actually observed for this protocol.
        observed_cells = set(
            map(tuple, d.loc[d["project"] == project, ["month", "trade_size_bin"]]
                .astype(str).to_numpy())
        )
        support_mask = np.array([
            (str(m), str(b)) in observed_cells
            for m, b in zip(std["month"], std["trade_size_bin"])
        ], dtype=bool)
        observed_support_weight = float(weights[support_mask].sum())
        extrapolated_weight = float(1.0 - observed_support_weight)

        rows.append({
            "window": window,
            "project": project,
            "adjusted_attack_probability": adjusted,
            "adjusted_attack_rate_pct": 100.0 * adjusted,
            "pooled_standardization_weight_on_observed_protocol_support": observed_support_weight,
            "pooled_standardization_weight_extrapolated": extrapolated_weight,
            "standardization": (
                "observed pooled candidate-trade month x trade-size-bin distribution"
            ),
            "support_note": (
                "model-standardized prediction; pooled target may include month x "
                "trade-size cells not empirically observed for this protocol. "
                "Support weights quantify observed versus extrapolated target mass; "
                "the estimand itself is unchanged."
            ),
            "scope": "conditional on protocols with >=1 observed attacked event; zero-attack eligible protocols are outside this model estimand",
            "inferential_role": (
                "descriptive standardized point estimate; "
                "no CI or ranking significance claimed"
            ),
        })

    return pd.DataFrame(rows).sort_values(
        "adjusted_attack_probability", ascending=False
    )


def write_csv(path: Path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(obj, pd.DataFrame):
        obj.to_csv(path, index=False)
    elif isinstance(obj, dict):
        pd.DataFrame([obj]).to_csv(path, index=False)
    else:
        pd.DataFrame(obj).to_csv(path, index=False)


def run_h4_tests(data_root="fetch/data", output_dir="output"):
    root, out = Path(data_root), Path(output_dir)
    p24 = root / "revised-24m" / "query_protocol_vulnerability_v2.csv"
    p30 = root / "revised-30m" / "query_protocol_vulnerability_v2.csv"

    d24 = load_protocol_file(p24, PRIMARY_EXPECTED_VICTIM_TRADES)
    d30 = load_protocol_file(p30, ROBUST_EXPECTED_VICTIM_TRADES)

    q24 = load_q5e(root / "revised-24m" / "query5e_eligible_trade_attack_rates_v2.csv",
                   PRIMARY_EXPECTED_VICTIM_TRADES)
    q30 = load_q5e(root / "revised-30m" / "query5e_eligible_trade_attack_rates_v2.csv",
                   ROBUST_EXPECTED_VICTIM_TRADES)
    validate_q5e_against_protocol(q24, d24, "24m")
    validate_q5e_against_protocol(q30, d30, "30m")

    incidence_diag24 = fit_protocol_attack_incidence(q24)
    incidence_diag30 = fit_protocol_attack_incidence(q30)
    audit24, audit_tests24 = covariance_audit(q24)
    audit30, audit_tests30 = covariance_audit(q30)
    pairwise24 = fit_protocol_pairwise_contrasts(q24)
    pairwise30 = fit_protocol_pairwise_contrasts(q30)
    timehet24 = fit_protocol_linear_time_heterogeneity(q24)
    timehet30 = fit_protocol_linear_time_heterogeneity(q30)

    prevalence24 = attack_prevalence_analysis(q24, "revised-24m")
    prevalence30 = attack_prevalence_analysis(q30, "revised-30m")
    adjusted24 = adjusted_protocol_probabilities(q24, "revised-24m")
    adjusted30 = adjusted_protocol_probabilities(q30, "revised-30m")
    exposure24 = exposure_concentration_note(q24, "revised-24m")
    exposure30 = exposure_concentration_note(q30, "revised-30m")

    s24, detail24 = window_summary(d24, "revised-24m", "primary")
    s30, detail30 = window_summary(d30, "revised-30m", "temporal robustness extension")
    robustness, cross = cross_window_robustness(d24, d30)

    td = out / "tables"
    rd = out / "reports"

    write_csv(td / "h4_protocol_summary.csv", [s24, s30])
    write_csv(td / "h4_protocol_detail_24m.csv", detail24)
    write_csv(td / "h4_protocol_detail_30m.csv", detail30)
    write_csv(td / "h4_cross_window_robustness.csv", robustness)
    write_csv(td / "h4_cross_window_protocol_detail.csv", cross)
    write_csv(td / "h4_protocol_attack_incidence_diagnostics.csv", [
        {"window": "revised-24m", "analysis_role": "primary", **incidence_diag24},
        {"window": "revised-30m", "analysis_role": "temporal robustness extension", **incidence_diag30},
    ])
    write_csv(td / "h4_protocol_pairwise_attack_incidence_24m.csv", pairwise24)
    write_csv(td / "h4_protocol_pairwise_attack_incidence_30m.csv", pairwise30)
    write_csv(td / "h4_protocol_linear_time_heterogeneity.csv", [
        {"window": "revised-24m", "analysis_role": "primary", **timehet24},
        {"window": "revised-30m", "analysis_role": "temporal robustness extension", **timehet30},
    ])
    write_csv(td / "h4_covariance_audit_diagnostics.csv", [
        {"window": "revised-24m", **audit24},
        {"window": "revised-30m", **audit30},
    ])
    write_csv(td / "h4_attack_prevalence_by_protocol_24m.csv", prevalence24["protocol"])
    write_csv(td / "h4_attack_prevalence_by_protocol_30m.csv", prevalence30["protocol"])
    write_csv(td / "h4_attack_prevalence_by_protocol_version_24m.csv", prevalence24["protocol_version"])
    write_csv(td / "h4_attack_prevalence_by_trade_size_24m.csv", prevalence24["trade_size"])
    write_csv(td / "h4_attack_prevalence_by_month_24m.csv", prevalence24["month"])
    write_csv(td / "h4_adjusted_protocol_attack_probabilities_24m.csv", adjusted24)
    write_csv(td / "h4_adjusted_protocol_attack_probabilities_30m.csv", adjusted30)
    write_csv(td / "h4_attack_share_vs_candidate_exposure.csv", pd.concat([exposure24, exposure30], ignore_index=True))
    write_csv(td / "h4_covariance_sensitivity_tests.csv",
              [{"window": "revised-24m", **r} for r in audit_tests24] +
              [{"window": "revised-30m", **r} for r in audit_tests30])

    ten24 = detail24.loc[detail24["avg_trade_size_ge_10x_pooled"], "project"].tolist()
    ten30 = detail30.loc[detail30["avg_trade_size_ge_10x_pooled"], "project"].tolist()

    lines = [
        "# H4 Protocol Heterogeneity Analysis",
        "",
        "## Hypothesis",
        "",
        'H4: "Sandwich activity differs systematically across DEX protocols: a small set of protocols hosts victim trades that are orders of magnitude larger than the market average (\'whale pools\'), concentrating the highest-stakes extraction."',
        "",
        "## H4a — victim-trade scale and concentration (direct H4 evidence)",
        "",
        f"- Primary 24m sample contains {s24['protocol_count']} protocol families and {s24['victim_trade_count']:,} victim trades.",
        f"- The pooled victim-trade average is ${s24['pooled_market_avg_victim_trade_usd']:,.2f}.",
        f"- The largest protocol-level average is {s24['largest_avg_trade_protocol']} at ${s24['max_protocol_avg_trade_usd']:,.2f}, or {s24['max_protocol_avg_ratio_to_pooled']:.1f}x the pooled market average.",
        f"- {s24['protocols_ge_10x_pooled_avg']} protocols have average victim trade size >=10x the pooled market average: {', '.join(ten24) if ten24 else 'none'}.",
        f"- {s24['protocols_ge_100x_pooled_avg']} protocols have average victim trade size >=100x the pooled market average (descriptive magnitude marker only).",
        f"- Protocol victim-volume concentration: CR1={100*s24['cr1_volume_share']:.2f}%, CR2={100*s24['cr2_volume_share']:.2f}%, CR4={100*s24['cr4_volume_share']:.2f}%, HHI={s24['protocol_volume_hhi_0_10000']:.1f}.",
        "",
        "## 30m temporal robustness extension",
        "",
        f"- The 30m extension contains {s30['protocol_count']} protocol families and {s30['victim_trade_count']:,} victim trades.",
        f"- The largest protocol-level average remains {s30['largest_avg_trade_protocol']} at {s30['max_protocol_avg_ratio_to_pooled']:.1f}x the 30m pooled market average.",
        f"- {s30['protocols_ge_10x_pooled_avg']} protocols remain at >=10x the pooled 30m average: {', '.join(ten30) if ten30 else 'none'}.",
        f"- 30m concentration remains high descriptively: CR1={100*s30['cr1_volume_share']:.2f}%, CR2={100*s30['cr2_volume_share']:.2f}%, CR4={100*s30['cr4_volume_share']:.2f}%, HHI={s30['protocol_volume_hhi_0_10000']:.1f}.",
        f"- Across {robustness['common_protocols']} protocols present in both files, 24m-vs-30m average-trade-size rank correlation is {robustness['spearman_avg_trade_size_rank_24m_vs_30m_descriptive']:.3f}; this is descriptive because the windows overlap.",
        "",
        "## H4b — protocol attack-incidence heterogeneity (complementary evidence)",
        "",
        f"- Primary 24m model uses {incidence_diag24['cells']:,} genuine month × project × version × trade-size-bin cells and {incidence_diag24['month_clusters']} calendar-month clusters.",
        f"- The grouped-binomial protocol model controls for month and trade-size bin. Its 24m month-clustered CR1 omnibus sensitivity statistic is F({incidence_diag24['df_num']},{incidence_diag24['df_den']})={incidence_diag24['F']:.3f}. The corresponding approximate reference p-value is retained in the machine-readable diagnostics for transparency, but it is deliberately not printed here or used to decide whether H4 is statistically supported because only {incidence_diag24['month_clusters']} independent monthly clusters support a high-dimensional protocol restriction block.",
        "- The 30m model is a nested temporal robustness extension, not an independent replication.",
        "- Candidate-only protocols with zero attacks are excluded from the unpenalized fixed-effect logit because of complete separation. Therefore the incidence model is explicitly outcome-conditioned: it estimates heterogeneity only among protocols with >=1 observed attacked event and is not a test across the full eligible-protocol universe. Full-universe zero-attack protocols remain visible in the descriptive prevalence tables.",
        "- Pairwise protocol contrasts are exploratory effect-size comparisons with approximate month-clustered CR1 uncertainty and Holm multiplicity adjustment.",
        "- The protocol × linear-calendar-time omnibus p-value is deliberately omitted because the interaction restriction block is too large relative to the number of independent monthly clusters.",
        "",
        "## Where attacks occur most often and observable associated factors",
        "",
        f"- Most observed attacked events (24m): {prevalence24['protocol'].sort_values('attacked_trade_events', ascending=False).iloc[0]['project']} with {int(prevalence24['protocol'].sort_values('attacked_trade_events', ascending=False).iloc[0]['attacked_trade_events']):,} attacked events.",
        f"- Highest raw protocol attack rate (24m): {prevalence24['protocol'].iloc[0]['project']} at {100*prevalence24['protocol'].iloc[0]['attack_rate']:.3f}% of observed eligible candidate trades.",
        f"- Highest attack concentration relative to eligible-trade exposure (24m): {exposure24.iloc[0]['project']} with attack-share/candidate-share ratio {exposure24.iloc[0]['relative_attack_concentration_ratio']:.3f}; this is descriptive exposure normalization, not a significance or causal estimate.",
        f"- Highest descriptive model-adjusted protocol attack-probability point estimate (24m, among protocols with >=1 observed attack): {adjusted24.iloc[0]['project']} at {adjusted24.iloc[0]['adjusted_attack_rate_pct']:.3f}%, standardized to the observed pooled month x trade-size-bin candidate distribution. This is a model-standardized prediction and may partly extrapolate to month x size cells not observed for that protocol; protocol-specific observed/extrapolated target-mass diagnostics are written to the adjusted-probability table.",
        f"- Highest raw trade-size-bin attack rate (24m): {prevalence24['trade_size'].iloc[0]['trade_size_bin']} at {100*prevalence24['trade_size'].iloc[0]['attack_rate']:.3f}%.",
        f"- Highest raw monthly attack rate (24m): {prevalence24['month'].iloc[0]['month']} at {100*prevalence24['month'].iloc[0]['attack_rate']:.3f}%.",
        "- These tables identify observable associations with protocol, protocol version, trade-size bin, and calendar month. They do not identify causal mechanisms such as liquidity design, routing, slippage settings, or bot strategy because Q5e does not contain those mechanism variables.",
        "",
        "## Evidentiary hierarchy",
        "",
        "- Primary H4 evidence: continuous protocol average victim-trade-size ratios to the pooled transaction-weighted market average, plus victim-volume CR1/CR2/CR4 and HHI.",
        "- Complementary evidence: raw attack incidence, attack concentration relative to eligible candidate-trade exposure, and model-adjusted protocol attack probabilities controlling for month and trade-size bin.",
        "- Robustness and diagnostics: 30m extension, covariance audit, pairwise contrasts, yearly/rank diagnostics, and within-protocol diagnostics.",
        "",
        "## Evidentiary strength and limitations",
        "",
        "- The aggregated files show large descriptive differences across protocol/project labels in average victim trade size and concentration of victim-side sandwich volume; they do not identify individual liquidity pools.",
        "- The continuous ratio to the pooled transaction-weighted market average is the main magnitude measure. The >=10x and >=100x indicators are descriptive markers only and carry no special inferential significance.",
        "- The 30m extension tests whether the descriptive pattern remains over a longer window; it is not an independent replication because it contains the 24m period.",
        "- A formal transaction-level protocol-effect test is unavailable from this aggregated file because within-protocol transaction-level variation has been discarded.",
        "- Therefore this module deliberately does not report ANOVA/Kruskal-Wallis/regression p-values from protocol averages as though they were transaction-level evidence.",
        "- Protocol-level victim trade volume is not the same quantity as attacker profit or victim loss, so 'highest-stakes extraction' should be interpreted as high victim-side sandwich volume unless extraction/profit microdata are added.",
        "- The data are aggregated by Dune project label; they do not identify heterogeneity among individual pools or protocol versions.",
        "",
        "## Conclusion",
        "",
        "The direct H4 evidence concerns victim-trade scale and concentration across protocol/project labels. The Q5e incidence analysis addresses the related but distinct estimand of attack probability among eligible trades after conditioning on month and trade-size bin. The observed protocol/project aggregates show substantial descriptive heterogeneity in victim trade size and concentration of victim-side sandwich volume; this is not evidence about individual liquidity pools. Because only 24 independent monthly clusters are available, the high-dimensional CR1 incidence omnibus p-value is retained only as an approximate sensitivity diagnostic and is not used as the decision rule for H4. The 30m results are nested robustness evidence, not an independent replication. Transaction-level inference about continuous victim-trade-size distributions, causal protocol mechanisms, and attacker extraction/profit is not available from these aggregated data.",
    ]

    rd.mkdir(parents=True, exist_ok=True)
    (rd / "h4_hypothesis_tests.md").write_text("\n".join(lines), encoding="utf-8")

    print("[PASS] H4 protocol-heterogeneity analysis completed")
    print(
        f"24m: {s24['protocol_count']} protocols; pooled avg=${s24['pooled_market_avg_victim_trade_usd']:,.2f}; "
        f"max protocol avg={s24['max_protocol_avg_ratio_to_pooled']:.1f}x pooled; "
        f"CR4={100*s24['cr4_volume_share']:.2f}%"
    )
    print(
        f"30m: {s30['protocol_count']} protocols; max protocol avg={s30['max_protocol_avg_ratio_to_pooled']:.1f}x pooled; "
        f"CR4={100*s30['cr4_volume_share']:.2f}%"
    )
    print("No transaction-level p-value is reported from aggregated protocol means.")


# ===========================================================================
# COMPLEMENTARY H4 ANALYSES AND ROBUSTNESS DIAGNOSTICS
# ===========================================================================

def fit_grouped(formula, d):
    y,X=patsy.dmatrices(formula,d,return_type='dataframe')
    n=d.candidate_trade_events.to_numpy(float); a=d.attacked_trade_events.to_numpy(float)
    # patsy response is attack proportion constructed in caller
    res=sm.GLM(y.iloc[:,0],X,family=sm.families.Binomial(),freq_weights=n).fit(maxiter=200)
    return res,X,n,a


def within_protocol_size_tests(q, window):
    """
    Within-protocol trade-size heterogeneity diagnostics.

    No within-protocol confirmatory p-values are reported. Each protocol has at
    most the observed monthly clusters in the window, while a categorical
    trade-size effect can require many simultaneous restrictions. Rather than
    impose an arbitrary minimum-month threshold or promote fragile finite-cluster
    Wald tests, this function records only observable support and model
    identification/convergence diagnostics.
    """
    rows = []
    for project, d in q.groupby("project"):
        d = d.loc[d["candidate_trade_events"] > 0].copy()
        months = int(d["month"].astype(str).nunique())
        bins = int(d["trade_size_bin"].nunique())
        attacks = float(d["attacked_trade_events"].sum())

        row = {
            "window": window,
            "project": project,
            "reportable": False,
            "months": months,
            "size_bins": bins,
            "attacked_trade_events": attacks,
            "inferential_role": "diagnostic only; no within-protocol confirmatory p-value",
        }

        if bins < 2:
            row["reason"] = "fewer than two observed trade-size bins"
            rows.append(row)
            continue
        if attacks <= 0:
            row["reason"] = "zero observed attacked events"
            rows.append(row)
            continue

        d["attack_prop"] = d["attacked_trade_events"] / d["candidate_trade_events"]
        try:
            with warnings.catch_warnings(record=True) as caught:
                warnings.simplefilter("always")
                res, X, n, a = fit_grouped(
                    "attack_prop ~ C(trade_size_bin) + C(month)", d
                )
            sep = any(
                issubclass(w.category, PerfectSeparationWarning) for w in caught
            )
            row.update({
                "model_converged": bool(res.converged),
                "perfect_separation_warning": bool(sep),
                "design_columns": int(X.shape[1]),
                "design_rank": int(np.linalg.matrix_rank(X.to_numpy(float))),
                "reason": (
                    "descriptive/model diagnostic only; finite monthly cluster "
                    "structure is not used for confirmatory multi-df inference"
                ),
            })
        except Exception as e:
            row.update({
                "model_converged": False,
                "reason": f"model diagnostic failed: {type(e).__name__}",
            })
        rows.append(row)
    return rows

def yearly_protocol_tests(q, window):
    """
    Year-specific protocol omnibus inference is omitted.

    Each year contributes only 12 independent calendar-month clusters, which is
    insufficient for a large protocol fixed-effect restriction block. HC0 or
    quasi-binomial covariance does not restore the missing independent cluster
    information, so those p-values are not used as substitutes.
    """
    q = q.copy()
    q["year"] = pd.to_datetime(q.month).dt.year
    rows = []
    for year, d in q.groupby("year"):
        attacked_projects = d.groupby("project")["attacked_trade_events"].sum()
        projects = attacked_projects[attacked_projects > 0].index
        dd = d[d.project.isin(projects)].copy()
        rows.append({
            "window": window,
            "year": int(year),
            "protocols_with_attacks": int(len(projects)),
            "month_clusters": int(dd["month"].nunique()),
            "reportable": False,
            "reason": (
                "omitted: only 12 independent monthly clusters are available "
                "for a high-dimensional protocol omnibus test"
            ),
        })
    return rows

def adjusted_year_probabilities(q):
    """
    Descriptive standardized protocol attack-probability point estimates by year.

    These estimates are used only for descriptive rank/direction stability.
    A year is omitted if the grouped-binomial model is not identifiable,
    does not converge, or raises a perfect-separation warning.
    """
    rows = []
    q = q.copy()
    q["year"] = pd.to_datetime(q["month"]).dt.year

    for year, d in q.groupby("year"):
        attacked = d.groupby("project")["attacked_trade_events"].sum()
        keep = attacked[attacked > 0].index
        d = d.loc[
            d["project"].isin(keep) & (d["candidate_trade_events"] > 0)
        ].copy()

        if d.empty or d["project"].nunique() < 2:
            continue

        d["attack_prop"] = (
            d["attacked_trade_events"] / d["candidate_trade_events"]
        )

        # Use candidate-event exposure, consistent with the main incidence model,
        # only to choose a numerically convenient reference category.
        ref = (
            d.groupby("project")["candidate_trade_events"]
            .sum()
            .sort_values(ascending=False)
            .index[0]
        )
        projects = sorted(d["project"].unique())
        categories = [ref] + [x for x in projects if x != ref]
        d["project"] = pd.Categorical(d["project"], categories=categories)

        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            res, X, n, a = fit_grouped(
                "attack_prop ~ C(project) + C(trade_size_bin) + C(month)", d
            )

        separation = any(
            issubclass(w.category, PerfectSeparationWarning) for w in caught
        )
        Xn = X.to_numpy(float)

        if separation:
            continue
        if not bool(res.converged):
            continue
        if np.linalg.matrix_rank(Xn) != Xn.shape[1]:
            continue
        if not np.isfinite(np.asarray(res.params, float)).all():
            continue

        # Standardize to the pooled observed month x size-bin candidate
        # distribution among protocols included in that year's fitted model.
        template = (
            d.groupby(
                ["month", "trade_size_bin"],
                observed=True,
                as_index=False,
            )["candidate_trade_events"]
            .sum()
        )
        total_weight = float(template["candidate_trade_events"].sum())
        if total_weight <= 0:
            continue
        weights = template["candidate_trade_events"].to_numpy(float) / total_weight

        for project in projects:
            t = template[["month", "trade_size_bin"]].copy()
            t["project"] = pd.Categorical(
                [project] * len(t), categories=categories
            )
            xp = patsy.build_design_matrices(
                [X.design_info], t, return_type="dataframe"
            )[0]
            pr = np.asarray(res.predict(xp), float)
            if not np.isfinite(pr).all():
                raise RuntimeError(
                    f"Non-finite adjusted yearly probabilities for {project}, {year}"
                )
            rows.append({
                "year": int(year),
                "project": project,
                "adjusted_probability": float(np.sum(weights * pr)),
                "inferential_role": (
                    "descriptive standardized point estimate; no CI or "
                    "significance claim"
                ),
            })

    return pd.DataFrame(rows)


def stability_test(q, window):
    """
    Descriptive year-to-year rank stability of adjusted protocol probabilities.

    No p-value is reported. If either yearly model is unusable, or fewer than
    two protocols are common to both usable years, the statistic is omitted.
    """
    ap = adjusted_year_probabilities(q)
    if ap.empty or "year" not in ap.columns:
        return {
            "window": window,
            "descriptive_available": False,
            "reason": "no usable yearly adjusted-probability models",
        }, ap

    years = sorted(ap["year"].unique())
    if len(years) != 2:
        return {
            "window": window,
            "descriptive_available": False,
            "reason": "requires exactly two usable yearly models",
        }, ap

    a = (
        ap.loc[ap["year"] == years[0], ["project", "adjusted_probability"]]
        .rename(columns={"adjusted_probability": "p1"})
    )
    b = (
        ap.loc[ap["year"] == years[1], ["project", "adjusted_probability"]]
        .rename(columns={"adjusted_probability": "p2"})
    )
    z = a.merge(b, on="project")

    if len(z) < 2:
        return {
            "window": window,
            "descriptive_available": False,
            "year1": int(years[0]),
            "year2": int(years[1]),
            "common_protocols": int(len(z)),
            "reason": "fewer than two protocols common to both usable yearly models",
        }, z

    p1 = z["p1"].to_numpy(float)
    p2 = z["p2"].to_numpy(float)
    if not np.isfinite(p1).all() or not np.isfinite(p2).all():
        return {
            "window": window,
            "descriptive_available": False,
            "year1": int(years[0]),
            "year2": int(years[1]),
            "common_protocols": int(len(z)),
            "reason": "non-finite yearly adjusted probabilities",
        }, z

    # Kendall tau is undefined if either ranking variable is constant. Ties are
    # otherwise handled by scipy's tau-b calculation and remain descriptive.
    if np.unique(p1).size < 2 or np.unique(p2).size < 2:
        return {
            "window": window,
            "descriptive_available": False,
            "year1": int(years[0]),
            "year2": int(years[1]),
            "common_protocols": int(len(z)),
            "reason": "yearly adjusted probabilities are constant, so rank stability is undefined",
        }, z

    tau = float(stats.kendalltau(p1, p2, variant="b").statistic)
    if not np.isfinite(tau):
        return {
            "window": window,
            "descriptive_available": False,
            "year1": int(years[0]),
            "year2": int(years[1]),
            "common_protocols": int(len(z)),
            "reason": "Kendall tau is non-finite and is therefore omitted",
        }, z

    return {
        "window": window,
        "descriptive_available": True,
        "year1": int(years[0]),
        "year2": int(years[1]),
        "common_protocols": int(len(z)),
        "kendall_tau_descriptive": tau,
        "p_value": np.nan,
        "inferential_role": "descriptive only",
        "interpretation": (
            "descriptive rank stability only; no conventional p-value because "
            "the ranks are estimated quantities and a naive Kendall test would "
            "ignore their estimation uncertainty; tau-b handles ordinary ties, "
            "while constant/non-finite rankings are omitted"
        ),
    }, z


def exposure_concentration_note(q, window):
    """Describe attack concentration relative to eligible-trade exposure.

    A ratio above 1 means a protocol hosts a larger share of observed attacks than
    its share of eligible candidate trades; below 1 means the opposite. This is a
    descriptive market-exposure normalization, not a causal or significance test.
    """
    g = q.groupby("project", as_index=False).agg(
        candidate_trade_events=("candidate_trade_events", "sum"),
        attacked_trade_events=("attacked_trade_events", "sum"),
    )
    total_candidate = float(g["candidate_trade_events"].sum())
    total_attacked = float(g["attacked_trade_events"].sum())
    if total_candidate <= 0 or total_attacked <= 0:
        raise RuntimeError(f"{window}: exposure concentration requires positive candidate and attacked totals")

    g["candidate_trade_share"] = g["candidate_trade_events"] / total_candidate
    g["attack_share"] = g["attacked_trade_events"] / total_attacked
    g["relative_attack_concentration_ratio"] = (
        g["attack_share"] / g["candidate_trade_share"]
    )
    g["attack_share_minus_candidate_share_pp"] = (
        100.0 * (g["attack_share"] - g["candidate_trade_share"])
    )
    g["window"] = window
    g["interpretation"] = (
        "descriptive exposure normalization: ratio >1 indicates attack share exceeds "
        "eligible-candidate-trade share; no causal or significance interpretation"
    )
    return g.sort_values(
        ["relative_attack_concentration_ratio", "attacked_trade_events"],
        ascending=[False, False],
    ).reset_index(drop=True)


def run_complementary_h4_analyses(data_root='fetch/data', output_dir='output'):
    root=Path(data_root); out=Path(output_dir)/'tables'; out.mkdir(parents=True,exist_ok=True)
    q24=load_q5e(root/'revised-24m'/'query5e_eligible_trade_attack_rates_v2.csv',PRIMARY_EXPECTED_VICTIM_TRADES)
    q30=load_q5e(root/'revised-30m'/'query5e_eligible_trade_attack_rates_v2.csv',ROBUST_EXPECTED_VICTIM_TRADES)
    within24=within_protocol_size_tests(q24,'revised-24m'); within30=within_protocol_size_tests(q30,'revised-30m')
    yr24=yearly_protocol_tests(q24,'revised-24m')
    stab24,stabdetail=stability_test(q24,'revised-24m')
    pd.DataFrame(within24+within30).to_csv(out/'h4_within_protocol_size_tests.csv',index=False)
    pd.DataFrame(yr24).to_csv(out/'h4_protocol_heterogeneity_by_year.csv',index=False)
    pd.DataFrame([stab24]).to_csv(out/'h4_protocol_rank_stability_2024_2025.csv',index=False)
    stabdetail.to_csv(out/'h4_protocol_adjusted_probability_by_year.csv',index=False)
    # Objective machine-readable summary.
    summary=pd.DataFrame([
      {'claim':'Attack concentration relative to eligible candidate-trade exposure','status':'descriptive plus approximate adjusted model','result':'attack-share/candidate-share ratios are reported; the grouped-binomial protocol model adjusts for month and trade-size composition','caution':'do not treat the 24-cluster high-dimensional omnibus CR1 p-value as definitive confirmatory inference'},
      {'claim':'Within-protocol trade-size heterogeneity','status':'diagnostic only','result':'observed support and model identification/convergence diagnostics are retained; no Wald p-values are produced','caution':'finite monthly cluster counts are too limited for reliable protocol-by-protocol multi-df confirmation'},
      {'claim':'Protocol heterogeneity separately in 2024 and 2025','status':'not formally tested','result':'omitted','caution':'only 12 independent monthly clusters per year; HC0/quasi covariance is not a substitute for independent cluster information'},
      {'claim':'Protocol rank stability across 2024 and 2025','status':'descriptive if both yearly models pass diagnostics','result':(f"Kendall tau={stab24['kendall_tau_descriptive']:.4g}, common protocols={stab24.get('common_protocols',0)}" if stab24.get('descriptive_available',False) else f"omitted: {stab24.get('reason','yearly model diagnostics failed')}"),'caution':'no conventional p-value; adjusted probabilities are estimated quantities'},
      {'claim':'Large-trade protocol/project concentration relative to exposure','status':'not separately formalized','result':'descriptive large-trade and victim-volume concentration remains available','caution':'avoids circular post-selection inference from defining whale protocols using attacked outcomes and testing the same outcome'},
    ])
    summary.to_csv(out/'h4_remaining_claim_test_map.csv',index=False)
    print(summary.to_string(index=False)); print('\nConservative inference mode: fragile finite-cluster tests are omitted rather than promoted to conclusions.')
    return summary



def run_all_h4_tests(data_root='fetch/data', output_dir='output'):
    """Run the complete H4 module: core analysis plus complementary diagnostics."""
    run_h4_tests(data_root, output_dir)
    return run_complementary_h4_analyses(data_root, output_dir)


if __name__ == '__main__':
    a = parse_args()
    run_all_h4_tests(a.data_root, a.output_dir)
