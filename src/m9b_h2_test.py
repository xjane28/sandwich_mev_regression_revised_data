"""
m9_h2_test.py

H2:
    "Uninformed order flow (retail) will subsidize informed order flow
     (bots), creating a 'Lemons' problem."

WHAT THE AVAILABLE DATA CAN TEST
--------------------------------
1. Whether Dune-detected sandwich victimization varies with trade size.
2. Whether smaller-trade proxies are disproportionately represented among
   detected victims.
3. Whether the size/victimization relationship persists after controlling
   for month and DEX project/version.
4. Robustness/sensitivity:
      a. a longer 30-month window, including the overall joint size test; and
      b. an outcome-selected coverage-conservative subset excluding
         project/version groups with no detected sandwich victim, used only
         for descriptive/effect-size sensitivity and not formal inference.

PLANNED Q5F EXTENSION — DATASET NOT YET LOCALLY AVAILABLE
--------------------------------------------------------
Q5f (query5f_matched_sandwich_extraction_v1) has been completed on Dune, but
the full CSV is not yet locally available. This script therefore does not load,
analyse, or report Q5f results yet.

Once the CSV becomes available, Q5f can be added as a separate additive H2
extension using matched bot front-run/victim/back-run observations and
bot-side gross extraction. Gross extraction is not counterfactual victim loss
and does not by itself identify the literal subsidy or the Lemons mechanism.

WHAT THE CURRENTLY AVAILABLE LOCAL DATA CANNOT DIRECTLY TEST
--------------------------------------------
The exports do not contain estimated counterfactual victim loss matched to
bot profit at the victim-event level. Therefore this analysis cannot identify
the literal dollar transfer ("subsidy") from retail traders to bots.

The script uses grouped-binomial logistic regression because Q5e contains
counts of attacked and unattacked eligible trades rather than individual
Bernoulli rows.

Inference:
    - month fixed effects;
    - project/version fixed effects;
    - trade-size-bin categorical effects;
    - project/version-clustered sandwich covariance calculated directly
      from the grouped-binomial score;
    - finite-cluster CR1 correction;
    - t/F reference distributions with G-1 cluster degrees of freedom,
      treated as conventional CR1 finite-cluster approximations rather than
      exact finite-sample inference.

DEX/MEV dependence robustness:
    - the project/version-clustered CR1 specification remains primary;
    - two-way project/version + month clustered covariance is reported as a
      robustness specification for the primary 24-month model;
    - because the primary window has only 24 month clusters, two-way-cluster
      inference is explicitly treated as approximate robustness evidence;
    - cluster-size/concentration diagnostics and leave-one-project-out
      sensitivity are reported without creating additional formal
      hypothesis-test families.

STATISTICAL APPROACH
--------------------
Q5e is analyzed using grouped-binomial logistic regression of attacked versus
unattacked eligible trades, with trade-size-bin, month, and project/version
fixed effects. Inference uses project/version-clustered CR1 standard errors.

The primary formal test is the 24-month joint test of trade-size-bin effects.
Secondary formal inference is limited to the same primary 24-month specification:
<$100 is compared with each larger trade-size category using 10 pairwise tests with
Holm family-wise-error correction. The size-victimization shape diagnostic is descriptive only; no formal inverted-U
hypothesis is tested. The 30-month window, two-way clustering, leave-one-project-out
refits, and the coverage-conservative subset are robustness/sensitivity analyses and
are not additional confirmations of H2.

Trade size is treated as a proxy for participant scale. Q5e tests sandwich
attack susceptibility by trade size; it does not directly estimate victim
loss, bot profit, or causal retail-to-bot transfers.
"""

from pathlib import Path
import warnings

import numpy as np
import pandas as pd
import patsy
import statsmodels.api as sm
from scipy import stats


ROOT = Path(__file__).resolve().parents[1]

DATA_24 = ROOT / "fetch" / "data" / "revised-24m"
DATA_30 = ROOT / "fetch" / "data" / "revised-30m"

OUT = ROOT / "output" / "tables"
OUT.mkdir(parents=True, exist_ok=True)

Q5E_NAME = "query5e_eligible_trade_attack_rates_v2.csv"
Q5B_NAME = "query5b_victim_impact_v2.csv"

BIN_ORDER = [
    "01_<100",
    "02_100_250",
    "03_250_500",
    "04_500_1000",
    "05_1000_2500",
    "06_2500_5000",
    "07_5000_10000",
    "08_10000_25000",
    "09_25000_50000",
    "10_50000_100000",
    "11_100000_plus",
]

BIN_LABEL = {
    "01_<100": "<$100",
    "02_100_250": "$100–250",
    "03_250_500": "$250–500",
    "04_500_1000": "$500–1k",
    "05_1000_2500": "$1k–2.5k",
    "06_2500_5000": "$2.5k–5k",
    "07_5000_10000": "$5k–10k",
    "08_10000_25000": "$10k–25k",
    "09_25000_50000": "$25k–50k",
    "10_50000_100000": "$50k–100k",
    "11_100000_plus": "≥$100k",
}


def load_q5e(folder):
    path = folder / Q5E_NAME
    if not path.exists():
        raise FileNotFoundError(path)

    df = pd.read_csv(path)

    required = {
        "month", "project", "version", "trade_size_bin",
        "candidate_trade_events", "attacked_trade_events",
        "unattacked_trade_events", "candidate_volume_usd",
        "attacked_volume_usd", "attack_rate_pct",
    }

    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"{path}: missing columns {sorted(missing)}")

    df["month"] = pd.to_datetime(df["month"], utc=True)
    # Patsy cannot treat timezone-aware datetime64 directly as a categorical.
    # Month FE only require a stable categorical label.
    df["month"] = df["month"].dt.strftime("%Y-%m")

    for c in [
        "candidate_trade_events",
        "attacked_trade_events",
        "unattacked_trade_events",
    ]:
        df[c] = pd.to_numeric(df[c], errors="raise").astype(np.int64)

    if (df["candidate_trade_events"] <= 0).any():
        raise ValueError("Q5e contains non-positive candidate counts.")

    if not np.array_equal(
        df["candidate_trade_events"].to_numpy(),
        (df["attacked_trade_events"] + df["unattacked_trade_events"]).to_numpy(),
    ):
        raise ValueError(
            "Q5e reconciliation failed: candidate != attacked + unattacked."
        )

    key = ["month", "project", "version", "trade_size_bin"]
    if df.duplicated(key).any():
        raise ValueError("Duplicate Q5e month/project/version/bin cells found.")

    unknown = set(df["trade_size_bin"]) - set(BIN_ORDER)
    if unknown:
        raise ValueError(f"Unexpected trade-size bins: {sorted(unknown)}")

    df["trade_size_bin"] = pd.Categorical(
        df["trade_size_bin"], categories=BIN_ORDER, ordered=True
    )

    df["protocol_version"] = (
        df["project"].astype(str) + "::" + df["version"].astype(str)
    )

    return df


def descriptive_rates(df, sample_name):
    g = (
        df.groupby("trade_size_bin", observed=False)
        .agg(
            candidate_trades=("candidate_trade_events", "sum"),
            attacked_trades=("attacked_trade_events", "sum"),
            unattacked_trades=("unattacked_trade_events", "sum"),
            candidate_volume_usd=("candidate_volume_usd", "sum"),
            attacked_volume_usd=("attacked_volume_usd", "sum"),
        )
        .reset_index()
    )

    g["attack_rate"] = g["attacked_trades"] / g["candidate_trades"]
    g["attack_rate_pct"] = 100 * g["attack_rate"]

    z = stats.norm.ppf(0.975)
    n = g["candidate_trades"].to_numpy(dtype=float)
    p = g["attack_rate"].to_numpy(dtype=float)

    denom = 1 + z**2 / n
    center = (p + z**2 / (2*n)) / denom
    half = z * np.sqrt(p*(1-p)/n + z**2/(4*n**2)) / denom

    # These Wilson intervals describe binomial sampling uncertainty only.
    # Candidate trades may be dependent within protocols, pools, blocks, and
    # time periods, so these intervals are descriptive and are NOT used for
    # the regression inference below.
    g["ci95_low_pct"] = 100 * (center - half)
    g["ci95_high_pct"] = 100 * (center + half)
    g["sample"] = sample_name
    g["trade_size"] = g["trade_size_bin"].map(BIN_LABEL)

    return g


def fit_grouped_binomial_fe(df):
    """
    Primary grouped-binomial logit:
        attacked_g ~ Binomial(candidate_g, p_g)

        logit(p_g) =
            trade-size-bin FE + month FE + project/version FE

    The common grouped-binomial/CR1 fitting implementation is delegated to
    _fit_grouped_binomial_from_design() so the primary and secondary models
    cannot silently diverge in their covariance calculations.
    """
    d = df.copy()
    formula = (
        "C(trade_size_bin, Treatment(reference='01_<100'))"
        " + C(month)"
        " + C(protocol_version)"
    )
    X = patsy.dmatrix(formula, d, return_type="dataframe")
    fit = _fit_grouped_binomial_from_design(d, X)

    # Retain the SE field expected by the existing downstream code.
    diag_cov = np.diag(fit["cov"])
    fit["se"] = np.sqrt(np.maximum(diag_cov, 0))
    return fit


def _fit_grouped_binomial_from_design(d, X, allow_invalid_covariance=False):
    """
    Shared grouped-binomial GLM + project/version-clustered CR1 implementation.

    All formal grouped-binomial specifications in this script use this function,
    preventing differences in fitting or covariance construction across models.
    """
    y = np.column_stack([
        d["attacked_trade_events"].to_numpy(dtype=float),
        d["unattacked_trade_events"].to_numpy(dtype=float),
    ])

    model = sm.GLM(y, X, family=sm.families.Binomial())
    res = model.fit(maxiter=200)
    if not bool(res.converged):
        raise RuntimeError("Grouped-binomial GLM did not converge.")

    Xn = np.asarray(X, dtype=float)
    rank = np.linalg.matrix_rank(Xn)
    if rank != Xn.shape[1]:
        raise RuntimeError(
            f"Design matrix is rank deficient: rank={rank}, columns={Xn.shape[1]}."
        )

    beta = np.asarray(res.params, dtype=float)
    if not np.isfinite(beta).all():
        raise RuntimeError("Non-finite GLM coefficient(s) detected.")

    n = d["candidate_trade_events"].to_numpy(dtype=float)
    y_success = d["attacked_trade_events"].to_numpy(dtype=float)
    eta = Xn @ beta
    p = 1 / (1 + np.exp(-np.clip(eta, -35, 35)))
    W = n * p * (1 - p)

    bread_inv = np.linalg.pinv(Xn.T @ (W[:, None] * Xn))
    individual_score = Xn * (y_success - n*p)[:, None]

    clusters = d["protocol_version"].astype(str).to_numpy()
    unique_clusters = np.unique(clusters)
    G = len(unique_clusters)
    if G < 20:
        warnings.warn(
            f"Only {G} project/version clusters. Conventional CR1 cluster-robust "
            "inference can be unreliable with few clusters; p-values and confidence "
            "intervals should be interpreted cautiously. Effect estimates are unchanged."
        )

    meat = np.zeros((Xn.shape[1], Xn.shape[1]))
    for cl in unique_clusters:
        s = individual_score[clusters == cl].sum(axis=0)
        meat += np.outer(s, s)

    cov = bread_inv @ meat @ bread_inv
    N_cells = len(d)
    K = Xn.shape[1]
    if G > 1 and N_cells > K:
        cov *= (G / (G - 1)) * ((N_cells - 1) / (N_cells - K))

    if not np.isfinite(cov).all():
        raise RuntimeError("Non-finite cluster-robust covariance detected.")

    diag_cov = np.diag(cov)
    tol = 1e-12 * max(1.0, float(np.max(np.abs(diag_cov))))
    materially_negative_variance = bool(np.any(diag_cov < -tol))
    if materially_negative_variance and not allow_invalid_covariance:
        raise RuntimeError("Materially negative variance estimate(s) detected.")

    # Model-stability diagnostics. These do not change estimates; they make
    # separation/boundary/numerical problems visible before inference is interpreted.
    singular_values = np.linalg.svd(Xn, compute_uv=False)
    condition_number = (
        float(singular_values[0] / singular_values[-1])
        if singular_values[-1] > 0 else np.inf
    )
    abs_beta_max = float(np.max(np.abs(beta)))
    se_diag = np.sqrt(np.maximum(np.diag(cov), 0.0))
    max_se = float(np.max(se_diag))
    min_prob = float(np.min(p))
    max_prob = float(np.max(p))
    near_boundary_count = int(np.sum((p < 1e-6) | (p > 1 - 1e-6)))
    cluster_outcomes = d.assign(_success=y_success, _n=n).groupby(
        "protocol_version", observed=True
    ).agg(success=("_success", "sum"), total=("_n", "sum"))
    all_zero_clusters = int((cluster_outcomes["success"] == 0).sum())
    all_one_clusters = int((cluster_outcomes["success"] == cluster_outcomes["total"]).sum())
    pattern_outcomes = d.assign(_success=y_success, _n=n).groupby(
        ["protocol_version", "trade_size_bin"], observed=True
    ).agg(success=("_success", "sum"), total=("_n", "sum"))
    all_zero_protocol_size_patterns = int((pattern_outcomes["success"] == 0).sum())
    all_one_protocol_size_patterns = int(
        (pattern_outcomes["success"] == pattern_outcomes["total"]).sum()
    )
    stability_flags = []
    if abs_beta_max > 15:
        stability_flags.append("very_large_coefficient")
    if max_se > 10:
        stability_flags.append("very_large_standard_error")
    if near_boundary_count > 0:
        stability_flags.append("near_boundary_fitted_probabilities")
    if all_zero_clusters > 0:
        stability_flags.append("all_zero_outcome_protocol_clusters_present")
    if all_one_clusters > 0:
        stability_flags.append("all_one_outcome_protocol_clusters_present")
    if all_zero_protocol_size_patterns > 0:
        stability_flags.append("all_zero_protocol_size_patterns_present")
    if all_one_protocol_size_patterns > 0:
        stability_flags.append("all_one_protocol_size_patterns_present")
    # Screening diagnostic only: dummy-variable coding and scale can inflate the raw
    # condition number, so this flag is not by itself evidence that the model is invalid.
    if condition_number > 1e10:
        stability_flags.append("high_raw_design_condition_number_screen")

    return {
        "result": res, "X": X, "data": d, "beta": beta, "cov": cov,
        "clusters": G, "cluster_df": G - 1,
        "diagnostics": {
            "design_rank": rank, "design_columns": Xn.shape[1],
            "condition_number": condition_number,
            "max_abs_coefficient": abs_beta_max, "max_cluster_robust_se": max_se,
            "min_fitted_probability": min_prob, "max_fitted_probability": max_prob,
            "near_boundary_fitted_cells": near_boundary_count,
            "all_zero_outcome_clusters": all_zero_clusters,
            "all_one_outcome_clusters": all_one_clusters,
            "all_zero_protocol_size_patterns": all_zero_protocol_size_patterns,
            "all_one_protocol_size_patterns": all_one_protocol_size_patterns,
            "condition_number_interpretation": "screening_only_dummy_coding_and_scale_sensitive",
            "materially_negative_variance": materially_negative_variance,
            "stability_flags": ";".join(stability_flags) if stability_flags else "none",
        },
    }



def coefficient_stability_diagnostics(fit, threshold=15.0):
    """Show whether extreme coefficients are size effects or nuisance fixed effects."""
    rows = []
    for name, value in zip(list(fit["X"].columns), np.asarray(fit["beta"], dtype=float)):
        if name.startswith("C(trade_size_bin"):
            kind = "trade_size"
        elif name.startswith("C(protocol_version)"):
            kind = "protocol_version_FE"
        elif name.startswith("C(month)"):
            kind = "month_FE"
        else:
            kind = "intercept_or_other"
        rows.append({"coefficient": name, "coefficient_type": kind,
                     "estimate": float(value), "abs_estimate": float(abs(value)),
                     "exceeds_abs_threshold": bool(abs(value) > threshold)})
    return pd.DataFrame(rows).sort_values("abs_estimate", ascending=False)


def zero_outcome_diagnostics(df):
    """Locate zero-attack protocol/version and protocol/version-by-size groups."""
    p = df.groupby("protocol_version", observed=True).agg(
        candidate_trades=("candidate_trade_events", "sum"),
        attacked_trades=("attacked_trade_events", "sum")).reset_index()
    p = p[p["attacked_trades"] == 0].copy()

    s = df.groupby(["protocol_version", "trade_size_bin"], observed=True).agg(
        candidate_trades=("candidate_trade_events", "sum"),
        attacked_trades=("attacked_trade_events", "sum")).reset_index()
    s = s[s["attacked_trades"] == 0].copy()
    s["trade_size"] = s["trade_size_bin"].map(BIN_LABEL)
    return p, s


def fit_grouped_binomial_coefficients_only(df):
    """Diagnostic only: preserve coefficients even if CR1 covariance is invalid."""
    d = df.copy()
    formula = (
        "C(trade_size_bin, Treatment(reference='01_<100'))"
        " + C(month)"
        " + C(protocol_version)"
    )
    X = patsy.dmatrix(formula, d, return_type="dataframe")
    return _fit_grouped_binomial_from_design(d, X, allow_invalid_covariance=True)

def _score_bread_components(fit):
    """Return fitted-model bread inverse and grouped-binomial score rows."""
    d = fit["data"]
    Xn = np.asarray(fit["X"], dtype=float)
    beta = np.asarray(fit["beta"], dtype=float)
    n = d["candidate_trade_events"].to_numpy(dtype=float)
    y_success = d["attacked_trade_events"].to_numpy(dtype=float)
    eta = Xn @ beta
    prob = 1 / (1 + np.exp(-np.clip(eta, -35, 35)))
    W = n * prob * (1 - prob)
    bread_inv = np.linalg.pinv(Xn.T @ (W[:, None] * Xn))
    score = Xn * (y_success - n * prob)[:, None]
    return bread_inv, score


def _cluster_meat(score, labels):
    labels = np.asarray(labels).astype(str)
    unique = np.unique(labels)
    meat = np.zeros((score.shape[1], score.shape[1]))
    for cl in unique:
        s = score[labels == cl].sum(axis=0)
        meat += np.outer(s, s)
    return meat, len(unique)


def _cr1_factor(G, N_cells, K):
    if G <= 1 or N_cells <= K:
        return 1.0
    return (G / (G - 1)) * ((N_cells - 1) / (N_cells - K))


def two_way_cluster_covariance(fit):
    """
    Two-way project/version + month cluster covariance via inclusion-exclusion.

    V = V_project/version + V_month - V_project/version-by-month. Each meat
    component receives the same CR1 scaling convention as the primary model.
    This is robustness inference, not a replacement for the primary CR1 result.
    """
    d = fit["data"]
    bread_inv, score = _score_bread_components(fit)
    N_cells, K = len(d), fit["X"].shape[1]
    protocol = d["protocol_version"].astype(str).to_numpy()
    month = d["month"].astype(str).to_numpy()
    intersection = np.array([f"{a}||{b}" for a, b in zip(protocol, month)])
    meat_p, Gp = _cluster_meat(score, protocol)
    meat_m, Gm = _cluster_meat(score, month)
    meat_pm, Gpm = _cluster_meat(score, intersection)
    meat_p *= _cr1_factor(Gp, N_cells, K)
    meat_m *= _cr1_factor(Gm, N_cells, K)
    meat_pm *= _cr1_factor(Gpm, N_cells, K)
    cov = bread_inv @ (meat_p + meat_m - meat_pm) @ bread_inv
    cov = 0.5 * (cov + cov.T)
    if not np.isfinite(cov).all():
        raise RuntimeError("Non-finite two-way cluster covariance.")
    if float(np.min(np.linalg.eigvalsh(cov))) < -1e-8:
        warnings.warn(
            "Two-way cluster covariance is not positive semidefinite; finite-cluster "
            "two-way results should be treated as robustness evidence only."
        )
    return {
        "cov": cov, "protocol_clusters": Gp, "month_clusters": Gm,
        "intersection_clusters": Gpm,
    }


def joint_trade_size_wald_with_cov(fit, cov):
    """Joint trade-size test under a supplied covariance matrix."""
    names = list(fit["X"].columns)
    idx = [i for i, name in enumerate(names) if name.startswith(
        "C(trade_size_bin, Treatment(reference='01_<100'))"
    )]
    b = fit["beta"][idx]
    V = np.asarray(cov)[np.ix_(idx, idx)]
    stat = float(b.T @ np.linalg.pinv(V) @ b)
    q = len(idx)
    F = stat / q
    # Two-way clustering is a covariance robustness diagnostic. With only 24 month
    # clusters, a single denominator-df rule would give false precision. We therefore
    # report the Wald/F statistic and covariance-based uncertainty, but deliberately
    # do not use a formal p-value or significance decision from this robustness fit.
    return {
        "wald_chi2": stat, "restrictions": q, "F_statistic_descriptive": F,
        "p_value": np.nan, "formal_inference": False,
    }


def cluster_structure_diagnostics(df, sample_name):
    """Descriptive diagnostics for cluster imbalance/concentration."""
    by_protocol = df.groupby("protocol_version", observed=True).agg(
        cells=("candidate_trade_events", "size"),
        candidate_trades=("candidate_trade_events", "sum"),
        attacked_trades=("attacked_trade_events", "sum"),
    ).reset_index()
    by_month = df.groupby("month", observed=True).agg(
        cells=("candidate_trade_events", "size"),
        candidate_trades=("candidate_trade_events", "sum"),
        attacked_trades=("attacked_trade_events", "sum"),
    ).reset_index()
    total = float(by_protocol["candidate_trades"].sum())
    shares = by_protocol["candidate_trades"].to_numpy(dtype=float) / total
    summary = pd.DataFrame([{
        "sample": sample_name,
        "protocol_version_clusters": len(by_protocol),
        "month_clusters": len(by_month),
        "candidate_trades": int(total),
        "largest_protocol_version_candidate_share": float(np.max(shares)),
        "protocol_version_candidate_share_hhi": float(np.sum(shares**2)),
        "median_candidate_trades_per_protocol_version": float(by_protocol["candidate_trades"].median()),
        "max_candidate_trades_per_protocol_version": int(by_protocol["candidate_trades"].max()),
        "min_candidate_trades_per_protocol_version": int(by_protocol["candidate_trades"].min()),
    }])
    by_protocol.insert(0, "sample", sample_name)
    by_month.insert(0, "sample", sample_name)
    return summary, by_protocol, by_month


def leave_one_project_out_sensitivity(df, sample_name, full_fit):
    """LOO coefficient sensitivity; invalid covariance refits are diagnostic-only."""
    names_full = list(full_fit["X"].columns)
    targets = []
    for b in BIN_ORDER[1:]:
        name = "C(trade_size_bin, Treatment(reference='01_<100'))" + f"[T.{b}]"
        targets.append((b, name, float(full_fit["beta"][names_full.index(name)])))

    rows, details = [], []
    total_candidate = float(df["candidate_trade_events"].sum())
    for project in sorted(df["project"].astype(str).unique()):
        project_mask = df["project"].astype(str) == project
        project_candidate_share_pct = (
            100.0 * float(df.loc[project_mask, "candidate_trade_events"].sum()) / total_candidate
            if total_candidate > 0 else float("nan")
        )
        d = df[~project_mask].copy()
        covariance_valid, status = True, "ok"
        try:
            fit = fit_grouped_binomial_fe(d)
        except RuntimeError as exc:
            if "Materially negative variance estimate" not in str(exc):
                rows.append({"sample": sample_name, "excluded_project": project,
                    "excluded_project_candidate_share_pct": project_candidate_share_pct,
                    "remaining_cells": len(d), "remaining_protocol_version_clusters": np.nan,
                    "max_abs_log_odds_change_vs_full": np.nan,
                    "median_abs_log_odds_change_vs_full": np.nan,
                    "min_OR_ratio_loo_vs_full_across_bins": np.nan,
                    "max_OR_ratio_loo_vs_full_across_bins": np.nan,
                    "covariance_valid": False,
                    "status": f"not_estimable: {type(exc).__name__}: {exc}"})
                continue
            covariance_valid = False
            status = "coefficients_only_invalid_CR1_covariance"
            try:
                fit = fit_grouped_binomial_coefficients_only(d)
            except Exception as exc2:
                rows.append({"sample": sample_name, "excluded_project": project,
                    "excluded_project_candidate_share_pct": project_candidate_share_pct,
                    "remaining_cells": len(d), "remaining_protocol_version_clusters": np.nan,
                    "max_abs_log_odds_change_vs_full": np.nan,
                    "median_abs_log_odds_change_vs_full": np.nan,
                    "min_OR_ratio_loo_vs_full_across_bins": np.nan,
                    "max_OR_ratio_loo_vs_full_across_bins": np.nan,
                    "covariance_valid": False,
                    "status": f"not_estimable: {type(exc2).__name__}: {exc2}"})
                continue

        names = list(fit["X"].columns)
        deltas, ratios = [], []
        for b, name, beta_full in targets:
            beta_loo = float(fit["beta"][names.index(name)])
            delta = beta_loo - beta_full
            ratio = float(np.exp(delta))
            deltas.append(abs(delta)); ratios.append(ratio)
            details.append({"sample": sample_name, "excluded_project": project,
                "trade_size_bin": b, "trade_size": BIN_LABEL[b],
                "full_log_odds": beta_full, "loo_log_odds": beta_loo,
                "log_odds_change_loo_minus_full": delta,
                "full_odds_ratio_vs_under_100": float(np.exp(beta_full)),
                "loo_odds_ratio_vs_under_100": float(np.exp(beta_loo)),
                "OR_ratio_loo_vs_full": ratio, "covariance_valid": covariance_valid,
                "status": status})

        rows.append({"sample": sample_name, "excluded_project": project,
            "excluded_project_candidate_share_pct": project_candidate_share_pct,
            "remaining_cells": len(d), "remaining_protocol_version_clusters": fit["clusters"],
            "max_abs_log_odds_change_vs_full": float(np.max(deltas)),
            "median_abs_log_odds_change_vs_full": float(np.median(deltas)),
            "min_OR_ratio_loo_vs_full_across_bins": float(np.min(ratios)),
            "max_OR_ratio_loo_vs_full_across_bins": float(np.max(ratios)),
            "covariance_valid": covariance_valid, "status": status})
    return pd.DataFrame(rows), pd.DataFrame(details)


def bin_effect_table(fit, sample_name):
    beta = fit["beta"]
    cov = fit["cov"]
    X = fit["X"]
    df_t = fit["cluster_df"]
    names = list(X.columns)

    rows = [{
        "sample": sample_name,
        "trade_size_bin": BIN_ORDER[0],
        "trade_size": BIN_LABEL[BIN_ORDER[0]],
        "odds_ratio_vs_under_100": 1.0,
        "ci95_low": 1.0,
        "ci95_high": 1.0,
        "reference": True,
    }]

    crit = stats.t.ppf(0.975, df=df_t)

    for b in BIN_ORDER[1:]:
        target = (
            "C(trade_size_bin, Treatment(reference='01_<100'))"
            f"[T.{b}]"
        )
        if target not in names:
            raise RuntimeError(f"Coefficient not found: {target}")

        j = names.index(target)
        est = beta[j]
        se = np.sqrt(max(cov[j, j], 0))
        rows.append({
            "sample": sample_name,
            "trade_size_bin": b,
            "trade_size": BIN_LABEL[b],
            "odds_ratio_vs_under_100": np.exp(est),
            "ci95_low": np.exp(est - crit*se),
            "ci95_high": np.exp(est + crit*se),
            "reference": False,
        })

    return pd.DataFrame(rows)


def joint_trade_size_wald(fit):
    """
    Joint test that all non-reference trade-size-bin coefficients are zero.

    The covariance is the project/version-clustered CR1 covariance constructed
    in fit_grouped_binomial_fe(). The F reference with G-1 denominator degrees
    of freedom is a finite-cluster approximation, not an exact few-cluster
    procedure. Accordingly, the returned p-value is labelled as CR1-based.
    """
    names = list(fit["X"].columns)

    idx = [
        i for i, name in enumerate(names)
        if name.startswith(
            "C(trade_size_bin, Treatment(reference='01_<100'))"
        )
    ]

    b = fit["beta"][idx]
    V = fit["cov"][np.ix_(idx, idx)]

    stat = float(b.T @ np.linalg.pinv(V) @ b)
    q = len(idx)

    F = stat / q
    p = stats.f.sf(F, q, fit["cluster_df"])

    return {
        "wald_chi2": stat,
        "restrictions": q,
        "F": F,
        "df_num": q,
        "df_den": fit["cluster_df"],
        "p_value": p,
        "inference_method": "CR1 cluster-robust; F reference with G-1 df",
    }




def small_vs_larger_trade_contrasts(fit, sample_name):
    """
    Secondary economic contrasts using the existing categorical
    grouped-binomial model.

    The <$100 bin is treated as the pre-specified smallest trade-size reference category.
    Each larger bin is compared directly with <$100 on the model's log-odds
    scale using the same project/version-clustered CR1 covariance and G-1
    cluster degrees of freedom.

    These are secondary contrasts of observed trade-size categories. They do not
    establish trader identity. Interpreting trade size as a retail/uninformed-flow
    proxy requires an explicit auxiliary assumption. They also do not establish subsidy, counterfactual victim loss, or
    the Lemons mechanism.

    H0 for each contrast:
        susceptibility in the larger bin = susceptibility in the <$100 bin

    Two-sided p-values are reported so the data may show either higher or lower
    susceptibility in the larger bin. Odds ratios >1 mean the larger bin has
    higher estimated odds of detected sandwich victimization than <$100.
    """
    names = list(fit["X"].columns)
    beta = np.asarray(fit["beta"], dtype=float)
    cov = np.asarray(fit["cov"], dtype=float)
    df_t = fit["cluster_df"]

    rows = []
    for b in BIN_ORDER[1:]:
        target = (
            "C(trade_size_bin, Treatment(reference='01_<100'))"
            f"[T.{b}]"
        )
        if target not in names:
            raise RuntimeError(f"Coefficient not found for contrast: {target}")

        idx = names.index(target)
        est = float(beta[idx])
        var = float(cov[idx, idx])
        tol = 1e-12 * max(1.0, float(np.max(np.abs(np.diag(cov)))))
        if var < -tol:
            raise RuntimeError(f"Negative variance for {b}: {var}")
        se = float(np.sqrt(max(var, 0.0)))
        if se == 0:
            raise RuntimeError(f"Zero SE for {b}.")

        t_stat = est / se
        p_two = float(2.0 * stats.t.sf(abs(t_stat), df=df_t))
        crit = float(stats.t.ppf(0.975, df=df_t))
        lo = est - crit * se
        hi = est + crit * se

        rows.append({
            "sample": sample_name,
            "reference_bin": BIN_LABEL[BIN_ORDER[0]],
            "comparison_bin": BIN_LABEL[b],
            "log_odds_difference_larger_minus_lt100": est,
            "odds_ratio_larger_vs_lt100": float(np.exp(est)),
            "or_ci95_low": float(np.exp(lo)),
            "or_ci95_high": float(np.exp(hi)),
            "t_stat": t_stat,
            "p_value_two_sided": p_two,
            "cluster_df": df_t,
            "inference_method": (
                "CR1 project/version-clustered secondary contrast; "
                "two-sided t reference"
            ),
        })

    out = pd.DataFrame(rows)

    # Holm step-down adjustment controls the family-wise error rate across
    # the 10 simultaneous <$100-vs-larger comparisons in this specification.
    # Raw two-sided p-values are retained alongside the adjusted values.
    raw_p = out["p_value_two_sided"].to_numpy(dtype=float)
    m = len(raw_p)
    order = np.argsort(raw_p)
    holm_sorted = np.empty(m, dtype=float)
    running_max = 0.0
    for rank, original_idx in enumerate(order):
        adjusted = (m - rank) * raw_p[original_idx]
        running_max = max(running_max, adjusted)
        holm_sorted[rank] = min(1.0, running_max)

    holm = np.empty(m, dtype=float)
    for rank, original_idx in enumerate(order):
        holm[original_idx] = holm_sorted[rank]

    out["p_value_holm"] = holm
    out["significant_holm_0_05"] = out["p_value_holm"] < 0.05
    out["multiplicity_adjustment"] = (
        "Holm FWER correction across 10 <$100-vs-larger contrasts "
        "within specification"
    )

    return out


def shape_diagnostics(desc):
    """
    Descriptive shape diagnostic only

    'Broad inverted-U' means:
      - the maximum raw attack rate occurs in an interior bin;
      - at least 75% of adjacent changes before the peak are positive; and
      - at least 75% of adjacent changes after the peak are negative.

    This is descriptive only. Formal inference about trade-size heterogeneity
    comes from the categorical grouped-binomial model and its joint coefficient
    test, not this diagnostic. No formal inverted-U hypothesis is tested because
    H2 does not pre-specify an inverted-U shape or peak.
    """
    d = desc.sort_values("trade_size_bin").copy()
    rates = d["attack_rate"].to_numpy()

    peak = int(np.argmax(rates))
    interior_peak = 0 < peak < len(rates) - 1

    pre = np.diff(rates[:peak+1]) if peak > 0 else np.array([])
    post = np.diff(rates[peak:]) if peak < len(rates)-1 else np.array([])

    pre_rising = np.mean(pre > 0) >= 0.75 if len(pre) else False
    post_falling = np.mean(post < 0) >= 0.75 if len(post) else False

    return {
        "lowest_bin": d.iloc[np.argmin(rates)]["trade_size"],
        "lowest_rate_pct": 100*np.min(rates),
        "peak_bin": d.iloc[peak]["trade_size"],
        "peak_rate_pct": 100*rates[peak],
        "largest_bin_rate_pct": 100*rates[-1],
        "broad_inverted_u": (
            interior_peak and pre_rising and post_falling
        ),
    }


def load_victim_composition(folder):
    q5b = pd.read_csv(folder / Q5B_NAME)

    needed = {
        "victim_tier", "victim_trades", "total_volume",
        "avg_tx_size", "pct_of_trades", "pct_of_volume",
    }

    missing = needed - set(q5b.columns)
    if missing:
        raise ValueError(f"Q5b missing {sorted(missing)}")

    return q5b


def attacked_coverage_subset(df):
    """
    Coverage-conservative robustness only.

    Restricts to project/version combinations with at least one detected
    sandwich victim.  This is not the primary specification because protocols
    with zero detected victims are excluded based on the outcome being studied.
    """
    totals = (
        df.groupby("protocol_version", observed=True)["attacked_trade_events"]
        .sum()
    )
    observed_attack_protocols = totals[totals > 0].index
    return df[df["protocol_version"].isin(observed_attack_protocols)].copy()


def evidence_assessment(
    desc24, fit24, joint24, shape24,
    desc30, fit30, joint30, shape30,
    q5b,
):
    total_candidate = int(desc24["candidate_trades"].sum())
    total_attacked = int(desc24["attacked_trades"].sum())

    victim_trade_share = q5b.set_index("victim_tier")["pct_of_trades"]
    victim_volume_share = q5b.set_index("victim_tier")["pct_of_volume"]

    print("\n" + "="*78)
    print("H2 EVIDENCE-STRENGTH ASSESSMENT")
    print("="*78)

    print(
        "\nH2: Uninformed order flow (retail) will subsidize informed "
        "order flow (bots), creating a 'Lemons' problem."
    )

    print("\nA. DATA SCALE")
    print(f"24m eligible/candidate trades: {total_candidate:,}")
    print(f"24m detected sandwich victims: {total_attacked:,}")
    print(f"Project/version clusters: {fit24['clusters']}")

    print("\nB. DOES DETECTED ATTACK SUSCEPTIBILITY VARY WITH TRADE SIZE?")
    print(
        f"Joint trade-size test (CR1 clustered by project/version): "
        f"F({joint24['df_num']}, {joint24['df_den']}) "
        f"= {joint24['F']:.3f}, p={joint24['p_value']:.4g}"
    )
    if fit24["clusters"] < 20:
        print(
            "CAUTION: fewer than 20 project/version clusters; conventional "
            "CR1 small-cluster inference is approximate and should not be "
            "treated as definitive."
        )
    print(
        f"Raw 24m peak detected attack rate: "
        f"{shape24['peak_bin']} = {shape24['peak_rate_pct']:.3f}%"
    )
    print(
        f"Raw 24m >=$100k rate: "
        f"{shape24['largest_bin_rate_pct']:.3f}%"
    )
    print(
        f"Broad inverted-U diagnostic, 24m: "
        f"{shape24['broad_inverted_u']}"
    )
    print(
        f"Broad inverted-U diagnostic, 30m: "
        f"{shape30['broad_inverted_u']}"
    )

    print("\nC. ATTACKED-VICTIM COMPOSITION")
    for tier in ["Retail", "Small", "Institutional"]:
        if tier in victim_trade_share.index:
            print(
                f"{tier}: "
                f"{victim_trade_share[tier]:.2f}% of attacked trades, "
                f"{victim_volume_share[tier]:.2f}% of attacked volume"
            )

    print("\nD. WHAT CAN BE CONCLUDED?")
    print(
        "1. Q5e permits formal testing of the association between trade size "
        "and Dune-detected sandwich victimization because it contains both "
        "attacked and unattacked candidate trades. The strength and direction "
        "of evidence must be determined from the executed estimates and "
        "cluster-robust inference."
    )

    if shape24["broad_inverted_u"] and shape30["broad_inverted_u"]:
        print(
            "2. Descriptively, the raw size relationship is nonlinear in "
            "both the 24m and 30m windows and satisfies the defined "
            "broad hump-shape (inverted-U) diagnostic. This diagnostic is "
            "descriptive, not a formal statistical test of an inverted-U "
            "functional form. The categorical model separately tests whether "
            "attack susceptibility differs across size bins."
        )
    else:
        print(
            "2. The relationship should be described from the estimated "
            "bin effects rather than assumed to be monotonic."
        )

    print(
        "3. Q5b provides descriptive information about the composition of "
        "already-detected victims, but this is conditional on attack and is "
        "not itself a susceptibility test."
    )
    print(
        "4. The available exports provide no direct identification of the "
        "dollar subsidy/wealth transfer from retail victims to bots because "
        "estimated counterfactual victim loss is not observed, and Q5f matched "
        "bot-side gross extraction is not yet available for local analysis."
    )
    print(
        "5. Trade size is a proxy for participant scale, not verified "
        "retail/institutional identity. Conclusions must therefore refer "
        "to smaller trade-size categories; any retail/uninformed-flow interpretation requires an explicit auxiliary proxy assumption."
    )

    print(
        "\nOVERALL: the data permit formal testing of an important observable "
        "implication of H2 (who is exposed/susceptible to detected sandwich "
        "attacks), but can provide only indirect evidence for the full H2 "
        "claim that retail order flow subsidizes bots. Q5f has been completed on "
        "Dune but is not analysed here because the full CSV is not yet "
        "available locally. Once available, it will add matched bot-side "
        "gross-extraction evidence; it will not by itself identify "
        "counterfactual victim loss or the full Lemons mechanism."
    )


def run_spec(df, label):
    """
    Fit one specification for descriptive rates, adjusted effect sizes, and
    the overall joint trade-size test.

    Pairwise <$100-vs-larger formal contrasts are intentionally not generated
    here because they are secondary inference reserved for the primary 24m
    specification only.
    """
    desc = descriptive_rates(df, label)
    fit = fit_grouped_binomial_fe(df)
    effects = bin_effect_table(fit, label)
    joint = joint_trade_size_wald(fit)
    shape = shape_diagnostics(desc)
    return desc, fit, effects, joint, shape


def main():
    print("="*78)
    print("H2: TRADE-SIZE / SANDWICH SUSCEPTIBILITY ANALYSIS")
    print("="*78)

    q24 = load_q5e(DATA_24)
    q30 = load_q5e(DATA_30)
    q5b24 = load_victim_composition(DATA_24)

    desc24, fit24, eff24, joint24, shape24 = run_spec(
        q24, "24m_primary_all_project_versions"
    )

    desc30, fit30, eff30, joint30, shape30 = run_spec(
        q30, "30m_robustness_all_project_versions"
    )

    # Secondary pairwise inference is limited to the primary 24m specification.
    # The 30m specification is a robustness analysis for the overall relationship.
    # The outcome-selected coverage-conservative subset is effect-size/descriptive
    # sensitivity only and receives no formal hypothesis test.
    retail24 = small_vs_larger_trade_contrasts(
        fit24, "24m_primary_all_project_versions"
    )
    # DEX/MEV dependence robustness. Primary coefficients/inference are unchanged.
    twoway24 = two_way_cluster_covariance(fit24)
    twoway_joint24 = joint_trade_size_wald_with_cov(
        fit24, twoway24["cov"]
    )
    twoway_joint24.update({
        "sample": "24m_primary_all_project_versions",
        "protocol_version_clusters": twoway24["protocol_clusters"],
        "month_clusters": twoway24["month_clusters"],
        "intersection_clusters": twoway24["intersection_clusters"],
        "inference_method": (
            "two-way project/version + month clustered sandwich covariance; "
            "inclusion-exclusion with componentwise CR1; covariance robustness only; "
            "no formal two-way p-value/significance decision"
        ),
    })
    cluster_summary24, cluster_protocol24, cluster_month24 = cluster_structure_diagnostics(
        q24, "24m_primary_all_project_versions"
    )
    loo24, loo24_detail = leave_one_project_out_sensitivity(
        q24, "24m_primary_all_project_versions", fit24
    )
    coef_diag24 = coefficient_stability_diagnostics(fit24)
    zero_protocols24, zero_patterns24 = zero_outcome_diagnostics(q24)

    q24_cov = attacked_coverage_subset(q24)
    # Outcome-selected sensitivity analysis only. Because inclusion requires at
    # least one detected victim, this subset is not used for formal hypothesis
    # testing of a selected population. We retain descriptive rates and
    # adjusted effect-size estimates.
    desc24_cov = descriptive_rates(q24_cov, "24m_coverage_conservative")
    fit24_cov = fit_grouped_binomial_fe(q24_cov)
    eff24_cov = bin_effect_table(fit24_cov, "24m_coverage_conservative")

    # Separate diagnostic purpose from the coverage-conservative subset above:
    # ~1 in 3 project/version clusters in the primary fit have zero attacked
    # trades in every cell they appear in, so their fixed-effect coefficients
    # are quasi-separated (see coefficient_stability_diagnostics /
    # all_zero_outcome_clusters). Those degenerate coefficients share the same
    # Fisher information matrix as the trade-size coefficients of interest, so
    # their precision could be distorted even though their point estimates
    # look stable. This re-fits on the same zero-attack-excluded subset purely
    # to check whether the primary joint test's magnitude survives dropping
    # the degenerate clusters. It is a numerical-stability check on the
    # PRIMARY specification's inference, not a new formal H2 test of a
    # selected population -- that question (and why it is not tested) is
    # answered separately above.
    joint24_zero_outcome_excluded = joint_trade_size_wald(fit24_cov)

    desc_all = pd.concat(
        [desc24, desc30, desc24_cov], ignore_index=True
    )
    effects_all = pd.concat(
        [eff24, eff30, eff24_cov], ignore_index=True
    )

    desc_all.to_csv(
        OUT / "table_h2_q5e_descriptive_rates.csv", index=False
    )
    effects_all.to_csv(
        OUT / "table_h2_q5e_adjusted_odds_ratios.csv", index=False
    )

    joint_df = pd.DataFrame([
        {"sample": "24m_primary_all_project_versions", **joint24},
        {"sample": "30m_robustness_all_project_versions", **joint30},
    ])

    joint_df.to_csv(
        OUT / "table_h2_q5e_joint_tests.csv", index=False
    )
    numerical_stability_df = pd.DataFrame([
        {
            "sample": "24m_primary_all_project_versions",
            "role": "primary_estimation_includes_degenerate_clusters",
            "all_zero_outcome_clusters_included": len(zero_protocols24),
            "near_boundary_fitted_cells": fit24["diagnostics"]["near_boundary_fitted_cells"],
            "max_abs_coefficient": fit24["diagnostics"]["max_abs_coefficient"],
            **joint24,
        },
        {
            "sample": "24m_zero_outcome_clusters_excluded",
            "role": "numerical_stability_diagnostic_not_a_formal_test_of_selected_population",
            "all_zero_outcome_clusters_included": 0,
            "near_boundary_fitted_cells": fit24_cov["diagnostics"]["near_boundary_fitted_cells"],
            "max_abs_coefficient": fit24_cov["diagnostics"]["max_abs_coefficient"],
            **joint24_zero_outcome_excluded,
        },
    ])
    numerical_stability_df.to_csv(
        OUT / "table_h2_q5e_zero_outcome_excluded_numerical_sensitivity.csv", index=False
    )
    retail24.to_csv(
        OUT / "table_h2_q5e_small_vs_larger_contrasts.csv", index=False
    )
    pd.DataFrame([twoway_joint24]).to_csv(
        OUT / "table_h2_q5e_two_way_cluster_robustness.csv", index=False
    )
    cluster_summary24.to_csv(
        OUT / "table_h2_q5e_cluster_structure_summary.csv", index=False
    )
    cluster_protocol24.to_csv(
        OUT / "table_h2_q5e_cluster_structure_by_protocol_version.csv", index=False
    )
    cluster_month24.to_csv(
        OUT / "table_h2_q5e_cluster_structure_by_month.csv", index=False
    )
    loo24.to_csv(OUT / "table_h2_q5e_leave_one_project_out.csv", index=False)
    loo24_detail.to_csv(OUT / "table_h2_q5e_leave_one_project_out_bin_details.csv", index=False)
    coef_diag24.to_csv(OUT / "table_h2_q5e_coefficient_stability_diagnostics.csv", index=False)
    zero_protocols24.to_csv(OUT / "table_h2_q5e_zero_attack_protocol_versions.csv", index=False)
    zero_patterns24.to_csv(OUT / "table_h2_q5e_zero_attack_protocol_size_patterns.csv", index=False)

    print("\nRAW 24-MONTH DETECTED ATTACK RATES")
    print(
        desc24[[
            "trade_size", "candidate_trades", "attacked_trades",
            "attack_rate_pct", "ci95_low_pct", "ci95_high_pct",
        ]].to_string(index=False)
    )

    print("\nADJUSTED 24-MONTH ODDS RATIOS")
    print(
        eff24[[
            "trade_size", "odds_ratio_vs_under_100",
            "ci95_low", "ci95_high",
        ]].to_string(index=False)
    )

    print("\nPRIMARY JOINT TEST")
    print(joint24)
    print("\nPRIMARY MODEL STABILITY DIAGNOSTICS")
    print(fit24["diagnostics"])
    if fit24["diagnostics"]["stability_flags"] != "none":
        print(
            "CAUTION: model-stability flags are present. Interpret inferential results "
            "only after investigating the flagged numerical/separation diagnostics."
        )
        print(
            f"\nNUMERICAL STABILITY CHECK: re-fitting with the "
            f"{len(zero_protocols24)} all-zero-outcome-cluster project/versions excluded "
            f"(same {len(q24_cov):,}-row subset as the coverage-conservative descriptive "
            f"table above, reused here only to check estimation stability, not as a formal "
            f"test of that selected population):\n"
            f"  Primary (clusters included):  F({joint24['restrictions']}, {joint24['df_den']}) = "
            f"{joint24['F']:.3f}, p={joint24['p_value']:.3e}, "
            f"max|coef|={fit24['diagnostics']['max_abs_coefficient']:.2f}, "
            f"near-boundary cells={fit24['diagnostics']['near_boundary_fitted_cells']}\n"
            f"  Zero-outcome clusters excluded: F({joint24_zero_outcome_excluded['restrictions']}, "
            f"{joint24_zero_outcome_excluded['df_den']}) = {joint24_zero_outcome_excluded['F']:.3f}, "
            f"p={joint24_zero_outcome_excluded['p_value']:.3e}, "
            f"max|coef|={fit24_cov['diagnostics']['max_abs_coefficient']:.2f}, "
            f"near-boundary cells={fit24_cov['diagnostics']['near_boundary_fitted_cells']}\n"
            f"  If the trade-size effect and its significance survive this exclusion at "
            f"comparable magnitude, the degenerate clusters were not materially distorting "
            f"the primary result; if it changes sharply, the primary joint test should not "
            f"be reported without this caveat. See "
            f"table_h2_q5e_zero_outcome_excluded_numerical_sensitivity.csv."
        )

    print("\nFOCUSED COEFFICIENT STABILITY DIAGNOSTICS")
    print(coef_diag24.head(20).to_string(index=False))
    extreme = coef_diag24[coef_diag24["exceeds_abs_threshold"]]
    if not extreme.empty:
        print("\nCoefficients with |beta| > 15:")
        print(extreme.to_string(index=False))
    print(f"\nZero-attack protocol/version clusters: {len(zero_protocols24)}; "
          f"zero-attack protocol/version x size patterns: {len(zero_patterns24)}")

    print("\nSECONDARY H2 CONTRASTS — <$100 VS EACH LARGER BIN")
    print(
        retail24[[
            "comparison_bin", "odds_ratio_larger_vs_lt100",
            "or_ci95_low", "or_ci95_high", "p_value_two_sided",
            "p_value_holm", "significant_holm_0_05",
        ]].to_string(index=False)
    )
    print(
        "NOTE: <$100 is a trade-size proxy, not verified retail identity. "
        "These are secondary contrasts. Holm-adjusted p-values "
        "control family-wise error across the 10 comparisons within this "
        "specification. These contrasts test susceptibility differences only."
    )

    print("\nDESCRIPTIVE SIZE-SHAPE DIAGNOSTIC — NO FORMAL INVERTED-U TEST")
    print(
        f"24m broad hump diagnostic: {shape24['broad_inverted_u']}; "
        f"raw peak: {shape24['peak_bin']} "
        f"({shape24['peak_rate_pct']:.3f}%)."
    )
    print(
        "NOTE: The broad hump/inverted-U label is descriptive only. H2 did not "
        "pre-specify an inverted-U shape or peak, so no formal inverted-U "
        "hypothesis test is performed or interpreted."
    )


    print("\n30-MONTH ROBUSTNESS JOINT TEST")
    print(joint30)

    print("\nDEX/MEV DEPENDENCE ROBUSTNESS — TWO-WAY PROJECT/VERSION + MONTH CLUSTERING")
    print(twoway_joint24)
    print(
        "NOTE: The original project/version-clustered CR1 specification remains "
        "primary. Two-way clustering is robustness analysis for dependence along "
        "both DEX protocol/version and calendar-month dimensions. With only 24 "
        "months in the primary window, the month dimension is small. No formal two-way p-value is used. "
        "Any difference from the primary CR1 result should be reported as a robustness "
        "difference in uncertainty, not reduced to a competing significant/non-significant label."
    )

    print("\nCLUSTER STRUCTURE DIAGNOSTICS — DESCRIPTIVE")
    print(cluster_summary24.to_string(index=False))

    print("\nLEAVE-ONE-PROJECT-OUT SENSITIVITY — ROBUSTNESS ONLY")
    print(loo24[[
        "excluded_project", "excluded_project_candidate_share_pct",
        "remaining_protocol_version_clusters",
        "max_abs_log_odds_change_vs_full",
        "median_abs_log_odds_change_vs_full",
        "min_OR_ratio_loo_vs_full_across_bins",
        "max_OR_ratio_loo_vs_full_across_bins", "covariance_valid", "status"
    ]].to_string(index=False))
    print(
        "NOTE: Leave-one-project-out refits assess influence through changes in the "
        "estimated trade-size effects relative to the full-sample model. No leave-one-out "
        "p-values or significance decisions are used, so this does not create an "
        "additional formal hypothesis-test family."
    )
    dominant_and_fragile = loo24[
        (loo24["excluded_project_candidate_share_pct"] >= 20.0)
        & ((~loo24["covariance_valid"])
           | (loo24["max_OR_ratio_loo_vs_full_across_bins"] / loo24["min_OR_ratio_loo_vs_full_across_bins"] >= 1.2))
    ]
    if not dominant_and_fragile.empty:
        for _, r in dominant_and_fragile.iterrows():
            print(
                f"CAUTION: excluding '{r['excluded_project']}' "
                f"({r['excluded_project_candidate_share_pct']:.1f}% of all candidate trades) "
                f"materially shifts effect sizes and/or invalidates CR1 covariance "
                f"(covariance_valid={r['covariance_valid']}, "
                f"OR ratio range=[{r['min_OR_ratio_loo_vs_full_across_bins']:.3f}, "
                f"{r['max_OR_ratio_loo_vs_full_across_bins']:.3f}]). "
                f"The primary result should be described as this project's relationship, "
                f"robustness-checked against smaller venues, rather than as a broad "
                f"cross-venue finding of equal weight."
            )

    print("\nCOVERAGE-CONSERVATIVE SENSITIVITY — NO FORMAL HYPOTHESIS TEST")
    print(
        "Protocols with zero detected victims are excluded based on the outcome. "
        "Accordingly, this subset is used only to inspect descriptive rates and "
        "adjusted effect-size sensitivity; no joint p-value is calculated or "
        "interpreted for this subset."
    )

    evidence_assessment(
        desc24, fit24, joint24, shape24,
        desc30, fit30, joint30, shape30,
        q5b24,
    )

    print("\nSaved additive outputs:")
    print("  output/tables/table_h2_q5e_descriptive_rates.csv")
    print("  output/tables/table_h2_q5e_adjusted_odds_ratios.csv  [descriptive/model effect-size table: ORs + clustered CIs; no individual p-values]")
    print("  output/tables/table_h2_q5e_joint_tests.csv  [24m primary + 30m robustness only; excludes outcome-selected coverage subset]")
    print("  output/tables/table_h2_q5e_small_vs_larger_contrasts.csv  [formal secondary contrast table: raw + Holm-adjusted p-values; primary 24m only]")
    print("  output/tables/table_h2_q5e_two_way_cluster_robustness.csv  [24m approximate robustness only]")
    print("  output/tables/table_h2_q5e_cluster_structure_summary.csv  [descriptive]")
    print("  output/tables/table_h2_q5e_cluster_structure_by_protocol_version.csv")
    print("  output/tables/table_h2_q5e_cluster_structure_by_month.csv")
    print("  output/tables/table_h2_q5e_leave_one_project_out.csv  [effect/influence robustness only; no leave-one-out p-values]")
    print("  output/tables/table_h2_q5e_leave_one_project_out_bin_details.csv")
    print("  output/tables/table_h2_q5e_coefficient_stability_diagnostics.csv")
    print("  output/tables/table_h2_q5e_zero_attack_protocol_versions.csv")
    print("  output/tables/table_h2_q5e_zero_attack_protocol_size_patterns.csv")


if __name__ == "__main__":
    main()
