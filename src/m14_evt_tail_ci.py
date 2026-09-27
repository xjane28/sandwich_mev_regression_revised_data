"""
m14_evt_tail_ci.py -- extreme-value-theory (EVT) confidence intervals for
CR1/CR4/HHI, as a heavy-tail-aware complement to the plain n-out-of-n
bootstrap used in m8_h1_test.py.

WHY THIS EXISTS: m8_h1_test.py's own subsample-stability diagnostic already
shows, on the real data, that CR1's and HHI's plain nonparametric bootstrap
CIs are not trustworthy here -- both metrics swing sharply as the subsample
size shrinks (CR1 more than doubles; HHI moves nearly 5x), which is exactly
the failure mode m8 itself warns is possible given the Hill tail index
(alpha ~= 0.34-0.41, an infinite-mean regime -- read from
table3_tail_estimates.csv by load_hill_alpha_range() below, not hardcoded;
see that function's docstring for a note on an earlier hardcoded "0.6-0.8"
figure that was wrong). The reason the plain bootstrap breaks for CR1/HHI
specifically: resampling observed values WITH REPLACEMENT can never produce
a value larger than the observed maximum. Under a heavy tail this
understates real uncertainty, because a bot even more extreme than the
biggest one already observed is entirely plausible -- the data just hasn't
shown it yet. CR1 and HHI are both dominated by the single largest
value(s), so this omission distorts them badly; Gini and CR4/CR10/CR20
average over more of the distribution and are far less affected (m8 already
excludes Gini from the subsample diagnostic for exactly this reason).

METHOD (peaks-over-threshold semi-parametric tail bootstrap -- a standard,
textbook EVT technique for exactly this failure mode, e.g. used in
insurance/operational-risk loss modeling; not a new or invented method):
  1. Fit a Generalized Pareto Distribution (GPD) by MLE to the exceedances
     over a high threshold u.
  2. Each bootstrap replicate resamples the BULK (values at or below u) with
     replacement as usual, but resamples the TAIL (values above u) by
     drawing fresh values from a GPD instead of resampling the same
     observed extreme values. This lets a replicate's simulated maximum
     exceed the real observed maximum, which is exactly the behavior the
     plain bootstrap cannot produce and exactly why it understates CR1/HHI
     uncertainty.
  3. The number of tail values in each replicate is itself resampled from
     Binomial(n, k/n) (k = observed exceedance count, n = total bots),
     rather than held fixed, so replicate-to-replicate variation in how
     many bots are "extreme" is also reflected, not just their sizes.
  4. CR1/CR4/HHI/top_1pct_share are recomputed on each simulated population
     using the exact same formulas m8_h1_test.py uses (see concentration()
     there), and the 2.5th/97.5th percentiles across replicates give the
     interval.

INPUT: fetch/data/revised-24m/query3_full_bot_distribution_v2.csv and the
revised-30m equivalent -- the same real, already-committed per-bot volume
data m8_h1_test.py itself loads (see its load_window()). Nothing here is
invented, estimated from a different source, or re-derived from raw
microdata beyond what m8 already uses.

OUTPUT (new files only; does not modify m8_h1_test.py's own output):
  - output/tables/h1_evt_tail_ci.csv                 (primary, u = 90th pct)
  - output/tables/h1_evt_threshold_sensitivity.csv    (v2, see below)
  - output/reports/evt_tail_ci.md
  - output/figures/evt_diagnostics_<window>.png       (v2, see below)

SCOPE: this is an additive, comparison diagnostic -- it does not replace or
overrule m8's existing bootstrap CIs or its subsample (m-out-of-n)
stability diagnostic, and does not decide which interval the paper should
quote. It exists so that decision can be made by comparing real, computed
diagnostics side by side, rather than by the plain bootstrap alone. (A
cross-reference comment pointing here has been added next to
subsample_stability() in m8_h1_test.py, so a reader of either module finds
the other.)

-------------------------------------------------------------------------
v2 CHANGES (kept as history rather than silently dropped -- reviewer
feedback on the first version of this module; see each function's own
docstring for the full detail of each point):

  1. THRESHOLD SENSITIVITY. v1 hardcoded a single threshold (the 90th
     percentile, tail_fraction=0.10, matching m2_concentration.py's
     hill_estimator(v_pos, 0.10) convention) and reported one CI from it.
     v2 additionally sweeps TAIL_FRACTIONS = (0.05, 0.10, 0.15, 0.20) and
     reports point estimate / CI / implied alpha at each threshold in
     output/tables/h1_evt_threshold_sensitivity.csv, so threshold choice is
     visibly checked, not silently assumed. The 0.10 fraction is kept as
     the single "primary" headline number (for continuity with the rest of
     the project's Hill-threshold convention), but it is no longer the
     only threshold examined. See run_threshold_sensitivity().

  2. LABELING. v1's report called the output an "EVT tail-bootstrap 95%
     CI" without flagging that it is a MODEL-based interval (it assumes the
     fitted GPD is a reasonable tail model), not an assumption-free /
     nonparametric CI the way the plain bootstrap is often (mis)understood
     to be. v2's report explicitly labels it "EVT/semi-parametric bootstrap
     interval (model-based -- assumes the fitted GPD tail model, not
     assumption-free)" wherever it is presented. See write_report().

  3. TAIL-FIT PARAMETER UNCERTAINTY. v1 fit the GPD's (xi, sigma) ONCE on
     the full sample and reused that single fixed pair to generate every
     bootstrap replicate's simulated tail values -- so the reported
     interval only reflected resampling variability, not uncertainty in
     the tail-shape estimate itself. v2's evt_tail_bootstrap() now refits
     (xi, sigma) by MLE on a bootstrap resample of the exceedances INSIDE
     every replicate (refit_tail_params=True, the default), so parameter
     uncertainty is propagated into the interval, not just observation
     resampling. A refit that fails on a degenerate resample falls back to
     the primary fit and is counted (n_refit_failures), never silently
     dropped.

  4. BACKTEST / CALIBRATION CHECKS. v1 had no visual diagnostic for
     whether the GPD/threshold choice was reasonable -- it asserted the
     tail-index comparison in text only. v2 adds
     write_diagnostic_plots(), which saves, per window, a 3-panel figure:
     a mean-excess (threshold-choice) plot, a Hill-style tail-index
     stability plot across a range of k, and a GPD QQ plot of the
     exceedances at the primary threshold. These let a reader check the
     GPD/threshold assumption empirically instead of taking it on faith.

  5. m8 DIAGNOSTIC STAYS. This module has never modified or replaced
     m8_h1_test.py's own bootstrap CI or its subsample (m-out-of-n)
     stability diagnostic, and still doesn't -- v2 just makes that
     relationship explicit in both places (this docstring, and a new
     comment next to subsample_stability() in m8_h1_test.py) rather than
     leaving it implicit.
-------------------------------------------------------------------------
"""

from __future__ import annotations

import csv
import os

import numpy as np
from scipy import stats

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_24 = os.path.join(ROOT, "fetch", "data", "revised-24m")
DATA_30 = os.path.join(ROOT, "fetch", "data", "revised-30m")
TABLES = os.path.join(ROOT, "output", "tables")
REPORTS = os.path.join(ROOT, "output", "reports")
FIGURES = os.path.join(ROOT, "output", "figures")

# Primary threshold: matches m2_concentration.py's hill_estimator(v_pos, 0.10)
# convention, kept as the single headline number for continuity with the
# rest of the project. See v2 CHANGES #1 above for the full sensitivity
# sweep this no longer stands alone next to.
PRIMARY_TAIL_FRACTION = 0.10
TAIL_FRACTIONS = (0.05, 0.10, 0.15, 0.20)

# N_BOOT was 5000 in v1, when every replicate reused one fixed GPD fit.
# v2's per-replicate GPD refit (v2 CHANGES #3) costs roughly 7ms/refit in
# this sandbox, so 5000 replicates x 2 windows would take several minutes;
# 2000 keeps the primary run under a minute while still giving stable
# 95th/2.5th percentiles for a diagnostic (not a primary confirmatory CI).
N_BOOT = 2000
# The threshold-sensitivity sweep runs 4 thresholds x 2 windows on top of
# the primary run, so it uses a smaller replicate count -- it is a
# supplementary check of threshold stability, not the headline interval,
# and does not need the same precision.
N_BOOT_SENSITIVITY = 500
SEED = 20260927  # fixed for reproducibility; arbitrary otherwise
CI_LOW, CI_HIGH = 2.5, 97.5


def load_bot_volumes(window_dir: str) -> np.ndarray:
    """Same missing-value convention as m8_h1_test.py's field parsing
    (<nil>/null/none/nan/blank treated as missing, not as zero or an error),
    so this uses the identical set of bots m8 itself uses."""
    path = os.path.join(window_dir, "query3_full_bot_distribution_v2.csv")
    vols = []
    with open(path, newline="") as f:
        for row in csv.DictReader(f):
            s = (row["total_volume_usd"] or "").strip()
            if s == "" or s.lower() in {"<nil>", "null", "none", "nan"}:
                continue
            v = float(s.replace(",", ""))
            if v >= 0:
                vols.append(v)
    return np.asarray(vols, dtype=float)


def load_hill_alpha_range() -> str:
    """Read the real Hill tail-index estimate for bot volume from
    table3_tail_estimates.csv, the same file src.m8_h1_test's
    load_hill_tail_estimates() reads, rather than hardcode a comparison
    figure here.

    HISTORY (kept per project convention, nothing silently erased): this
    module's docstring and the GPD-fit line in write_report() below used to
    state, hardcoded, "alpha in roughly [0.6, 0.8]" as the value to compare
    this script's independently-fitted GPD-implied alpha against. That
    figure was copied from src/m8_h1_test.py's own comments at the time,
    which were themselves wrong (see load_hill_tail_estimates() in that
    module for the full story) -- a hardcoded number copied from another
    hardcoded number, neither ever actually read from Table 3. The real
    value is alpha ~= 0.34 (top 5%) to 0.41 (top 10%), which in fact closely
    matches this script's own GPD-implied alpha (~0.34) -- i.e. once both
    numbers are read correctly, the two independent tail-index estimates
    agree, which is exactly the internal-consistency check this comparison
    is meant to provide.
    """
    path = os.path.join(TABLES, "table3_tail_estimates.csv")
    with open(path, newline="") as fh:
        by_estimator = {
            str(r.get("Model / Estimator", "")).strip(): r for r in csv.DictReader(fh)
        }
    required = ["Hill Estimator (Top 5% Bots)", "Hill Estimator (Top 10% Bots)"]
    missing = [m for m in required if m not in by_estimator]
    if missing:
        raise ValueError(
            f"{path} is missing required Hill-estimator row(s): " + ", ".join(missing)
        )

    def _alpha(label):
        raw = str(by_estimator[label]["Tail Parameter (SE)"])
        return float(raw.split("(")[0].strip())

    lo, hi = sorted([_alpha(required[0]), _alpha(required[1])])
    return f"{lo:.2f}-{hi:.2f}"


def concentration(vals: np.ndarray) -> dict:
    """Identical formulas to m8_h1_test.py's concentration(), so the two
    modules' point estimates and CIs are directly comparable."""
    x = vals[vals >= 0]
    total = x.sum()
    s = np.sort(x)[::-1]
    n = len(s)

    def top_share(k):
        k = min(max(1, k), n)
        return s[:k].sum() / total

    top1k = max(1, int(np.ceil(0.01 * n)))
    return {
        "top_1pct_share": top_share(top1k),
        "cr1": top_share(1),
        "cr4": top_share(4),
        "hhi": 10000.0 * float(np.sum((s / total) ** 2)),
    }


def fit_gpd_tail(vals: np.ndarray, tail_fraction: float):
    u = float(np.quantile(vals, 1 - tail_fraction))
    excesses = vals[vals > u] - u
    k = len(excesses)
    # floc=0: excesses over a threshold are non-negative by construction, so
    # the GPD location is fixed at 0 rather than estimated freely.
    xi_hat, _, sigma_hat = stats.genpareto.fit(excesses, floc=0)
    return u, k, xi_hat, sigma_hat


def evt_tail_bootstrap(
    vals: np.ndarray,
    tail_fraction: float,
    n_boot: int,
    seed: int,
    refit_tail_params: bool = True,
):
    """Semi-parametric tail bootstrap (see module docstring for the method).

    refit_tail_params=True (the default, v2 CHANGES #3): on every
    replicate, (xi, sigma) are re-estimated by MLE on a bootstrap resample
    of the observed exceedances, rather than reusing one fixed
    (xi_hat, sigma_hat) fit on the full sample for all replicates. This
    propagates uncertainty in the tail-shape estimate itself into the
    reported interval, not just resampling variability in which
    observations appear. Set False only to reproduce the v1 fixed-parameter
    behavior for comparison; there is no other reason to disable it.

    A refit that fails or returns a non-finite/non-positive parameter (can
    happen on a small or degenerate resample) falls back to the primary
    fit rather than crashing the whole bootstrap; how often this happens
    is counted (n_refit_failures) and reported, not silently absorbed.
    """
    rng = np.random.default_rng(seed)
    n = len(vals)
    u, k, xi_hat, sigma_hat = fit_gpd_tail(vals, tail_fraction)
    excesses = vals[vals > u] - u
    bulk = vals[vals <= u]
    p_tail = k / n

    reps = {"cr1": [], "cr4": [], "hhi": [], "top_1pct_share": []}
    xi_reps = []
    n_refit_failures = 0

    for _ in range(n_boot):
        k_rep = int(rng.binomial(n, p_tail))
        k_rep = max(1, min(k_rep, n - 1))  # keep at least one bulk and one tail draw
        n_bulk_rep = n - k_rep
        bulk_sample = rng.choice(bulk, size=n_bulk_rep, replace=True) if len(bulk) else np.array([])

        if refit_tail_params and k >= 2:
            exc_resample = rng.choice(excesses, size=k, replace=True)
            try:
                xi_rep, _, sigma_rep = stats.genpareto.fit(exc_resample, floc=0)
                if not (np.isfinite(xi_rep) and np.isfinite(sigma_rep) and sigma_rep > 0):
                    raise ValueError("non-finite or non-positive GPD refit")
            except Exception:
                xi_rep, sigma_rep = xi_hat, sigma_hat
                n_refit_failures += 1
        else:
            xi_rep, sigma_rep = xi_hat, sigma_hat

        xi_reps.append(xi_rep)
        tail_sample = u + stats.genpareto.rvs(xi_rep, loc=0, scale=sigma_rep, size=k_rep, random_state=rng)
        pop = np.concatenate([bulk_sample, tail_sample])
        c = concentration(pop)
        for key in reps:
            reps[key].append(c[key])

    out = {}
    for key, values in reps.items():
        arr = np.asarray(values)
        out[key] = {
            "mean": float(arr.mean()),
            "ci_low": float(np.percentile(arr, CI_LOW)),
            "ci_high": float(np.percentile(arr, CI_HIGH)),
        }

    # Uncertainty in the implied tail index itself, propagated the same way
    # (v2 CHANGES #3) -- reported alongside the concentration-metric CIs so
    # the tail-fit uncertainty is visible, not just its downstream effect.
    xi_arr = np.asarray(xi_reps)
    alpha_arr = np.where(xi_arr > 0, 1.0 / xi_arr, np.nan)
    implied_alpha_ci = {
        "mean": float(np.nanmean(alpha_arr)),
        "ci_low": float(np.nanpercentile(alpha_arr, CI_LOW)),
        "ci_high": float(np.nanpercentile(alpha_arr, CI_HIGH)),
    }

    tail_info = {
        "threshold_u": u,
        "tail_count_k": k,
        "n": n,
        "xi_hat": xi_hat,
        "sigma_hat": sigma_hat,
        "n_refit_failures": n_refit_failures,
        "n_boot": n_boot,
        "implied_alpha_ci": implied_alpha_ci,
    }
    return out, tail_info


def naive_bootstrap(vals: np.ndarray, n_boot: int, seed: int):
    """Plain n-out-of-n resampling, for direct side-by-side comparison with
    the EVT interval above. Same metrics, same replicate count, same seed
    family -- the only methodological difference is whether tail values can
    exceed the observed maximum (EVT: yes, via the fitted GPD; naive: no,
    since resampling with replacement is bounded by observed values)."""
    rng = np.random.default_rng(seed + 1)
    n = len(vals)
    reps = {"cr1": [], "cr4": [], "hhi": [], "top_1pct_share": []}
    for _ in range(n_boot):
        pop = rng.choice(vals, size=n, replace=True)
        c = concentration(pop)
        for key in reps:
            reps[key].append(c[key])
    out = {}
    for key, values in reps.items():
        arr = np.asarray(values)
        out[key] = {
            "mean": float(arr.mean()),
            "ci_low": float(np.percentile(arr, CI_LOW)),
            "ci_high": float(np.percentile(arr, CI_HIGH)),
        }
    return out


def run_threshold_sensitivity(vals: np.ndarray, label: str, fractions, n_boot: int, seed: int) -> list[dict]:
    """v2 CHANGES #1: sweep the POT threshold across `fractions` instead of
    reporting only the single hardcoded PRIMARY_TAIL_FRACTION, so a reader
    can see whether the EVT interval and implied tail index are stable
    across threshold choice or sensitive to it."""
    point = concentration(vals)
    rows = []
    for i, frac in enumerate(fractions):
        evt, tail_info = evt_tail_bootstrap(vals, frac, n_boot, seed + 7919 * i)
        alpha_hat = 1.0 / tail_info["xi_hat"] if tail_info["xi_hat"] > 0 else float("nan")
        for metric in ["cr1", "cr4", "hhi", "top_1pct_share"]:
            rows.append({
                "window": label,
                "tail_fraction": frac,
                "metric": metric,
                "point_estimate": point[metric],
                "evt_ci_low": evt[metric]["ci_low"],
                "evt_ci_high": evt[metric]["ci_high"],
                "threshold_u": tail_info["threshold_u"],
                "tail_count_k": tail_info["tail_count_k"],
                "gpd_shape_xi": tail_info["xi_hat"],
                "implied_hill_alpha": alpha_hat,
                "implied_alpha_ci_low": tail_info["implied_alpha_ci"]["ci_low"],
                "implied_alpha_ci_high": tail_info["implied_alpha_ci"]["ci_high"],
                "n_refit_failures": tail_info["n_refit_failures"],
                "n_boot": tail_info["n_boot"],
            })
    return rows


def hill_stability(x_pos: np.ndarray, ks) -> list[tuple]:
    """Hill alpha_hat(k) traced across a range of top-k order-statistic
    counts, for the tail-index stability plot (v2 CHANGES #4). This is a
    standard-formula Hill trace implemented locally for the plot only --
    it is not a substitute for, and is not claimed to be numerically
    identical to, m2_concentration.py's own hill_estimator() (which is the
    project's one canonical Hill estimate, read via load_hill_alpha_range()
    rather than recomputed here)."""
    x = np.sort(x_pos[x_pos > 0])[::-1]
    n = len(x)
    out = []
    for k in ks:
        k = int(k)
        if k < 2 or k >= n:
            continue
        top = x[: k + 1]
        if top[-1] <= 0:
            continue
        logs = np.log(top[:-1] / top[-1])
        m = float(np.mean(logs))
        if m > 0:
            out.append((k, 1.0 / m))
    return out


def write_diagnostic_plots(vals: np.ndarray, tail_fraction: float, label: str) -> str:
    """v2 CHANGES #4: backtest/calibration diagnostics for the primary GPD
    tail fit, so the threshold and distributional choice can be checked
    visually rather than assumed. Three panels, saved as one PNG:

      (a) Mean excess plot: mean(X-u | X>u) vs u over a grid of candidate
          thresholds. A roughly linear/flat region supports the GPD
          approximation there; a sharp bend or trend near the primary
          threshold is a warning sign worth noting in the paper.
      (b) Hill-style tail-index stability plot: alpha_hat(k) traced over a
          range of top-k counts. If alpha is not roughly stable over a
          wide range of k, the single-number "alpha~=X" framing used
          elsewhere in this module and in m8_h1_test.py should be read
          with more caution.
      (c) GPD QQ plot: empirical exceedance quantiles vs the fitted GPD's
          theoretical quantiles at the primary threshold. Points close to
          the 45-degree reference line support the GPD fit; systematic
          curvature would not.
    """
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    x_pos = vals[vals > 0]
    n = len(x_pos)

    u_grid = np.quantile(x_pos, np.linspace(0.70, 0.99, 60))
    mean_excess = []
    for u in u_grid:
        exc = x_pos[x_pos > u] - u
        mean_excess.append(float(exc.mean()) if len(exc) > 5 else float("nan"))

    ks = np.unique(np.linspace(20, min(2000, n - 2), 80).astype(int))
    hill_pts = hill_stability(x_pos, ks)

    u_primary, k_primary, xi_hat, sigma_hat = fit_gpd_tail(x_pos, tail_fraction)
    excesses = np.sort(x_pos[x_pos > u_primary] - u_primary)
    kk = len(excesses)
    plotting_pos = (np.arange(1, kk + 1) - 0.5) / kk
    theoretical_q = stats.genpareto.ppf(plotting_pos, xi_hat, loc=0, scale=sigma_hat)

    fig, axes = plt.subplots(1, 3, figsize=(15, 4.5))

    # Log-log axes: with a tail this heavy, one or two bots are orders of
    # magnitude larger than the rest, and a linear-scale mean-excess/QQ plot
    # is visually dominated by that single point -- everything else
    # collapses near the origin and the plot conveys nothing. Log scale is
    # standard practice for exactly this situation in EVT diagnostics
    # (spreads out the bulk of the threshold/quantile range instead of
    # letting the single largest bot set the axis range).
    axes[0].plot(u_grid, mean_excess, marker="o", ms=3, lw=1)
    axes[0].axvline(u_primary, color="red", ls="--", lw=1, label=f"primary threshold (u={u_primary:.0f})")
    axes[0].set_xscale("log")
    axes[0].set_yscale("log")
    axes[0].set_xlabel("Threshold u (log scale)")
    axes[0].set_ylabel("Mean excess (X-u | X>u) (log scale)")
    axes[0].set_title(f"{label}: mean excess plot")
    axes[0].legend(fontsize=8)

    if hill_pts:
        ks_arr, alphas_arr = zip(*hill_pts)
        axes[1].plot(ks_arr, alphas_arr, lw=1)
        axes[1].axhline(1.0, color="gray", ls=":", lw=1, label="alpha=1 (finite/infinite mean boundary)")
        axes[1].axvline(k_primary, color="red", ls="--", lw=1, label=f"primary k={k_primary}")
        axes[1].set_xlabel("k (top order statistics)")
        axes[1].set_ylabel("Hill alpha_hat(k)")
        axes[1].set_title(f"{label}: tail-index stability")
        axes[1].legend(fontsize=8)

    axes[2].scatter(theoretical_q, excesses, s=8)
    lower = max(min(float(theoretical_q.min()), float(excesses.min())), 1.0) if kk else 1.0
    upper = max(float(theoretical_q.max()) if kk else 1.0, float(excesses.max()) if kk else 1.0) * 1.05
    axes[2].plot([lower, upper], [lower, upper], color="red", ls="--", lw=1)
    axes[2].set_xscale("log")
    axes[2].set_yscale("log")
    axes[2].set_xlabel("Theoretical GPD quantile (log scale)")
    axes[2].set_ylabel("Empirical exceedance quantile (log scale)")
    axes[2].set_title(f"{label}: GPD QQ plot (u={u_primary:.0f}, xi={xi_hat:.2f})")

    fig.tight_layout()
    os.makedirs(FIGURES, exist_ok=True)
    out_path = os.path.join(FIGURES, f"evt_diagnostics_{label}.png")
    fig.savefig(out_path, dpi=130)
    plt.close(fig)
    return out_path


def run_window(label: str, window_dir: str) -> tuple[list[dict], list[dict], str]:
    vals = load_bot_volumes(window_dir)
    point = concentration(vals)
    evt, tail_info = evt_tail_bootstrap(vals, PRIMARY_TAIL_FRACTION, N_BOOT, SEED)
    naive = naive_bootstrap(vals, N_BOOT, SEED)

    implied_alpha = 1.0 / tail_info["xi_hat"] if tail_info["xi_hat"] > 0 else float("nan")

    rows = []
    for metric in ["cr1", "cr4", "hhi", "top_1pct_share"]:
        rows.append({
            "window": label,
            "metric": metric,
            "point_estimate": point[metric],
            "naive_bootstrap_ci_low": naive[metric]["ci_low"],
            "naive_bootstrap_ci_high": naive[metric]["ci_high"],
            "evt_tail_bootstrap_ci_low": evt[metric]["ci_low"],
            "evt_tail_bootstrap_ci_high": evt[metric]["ci_high"],
            "evt_ci_width_over_naive_ci_width": (
                (evt[metric]["ci_high"] - evt[metric]["ci_low"])
                / (naive[metric]["ci_high"] - naive[metric]["ci_low"])
                if (naive[metric]["ci_high"] - naive[metric]["ci_low"]) > 0 else float("nan")
            ),
            "gpd_threshold_u": tail_info["threshold_u"],
            "gpd_tail_count_k": tail_info["tail_count_k"],
            "gpd_shape_xi": tail_info["xi_hat"],
            "gpd_scale_sigma": tail_info["sigma_hat"],
            "gpd_implied_hill_alpha": implied_alpha,
            "gpd_implied_hill_alpha_ci_low": tail_info["implied_alpha_ci"]["ci_low"],
            "gpd_implied_hill_alpha_ci_high": tail_info["implied_alpha_ci"]["ci_high"],
            "n_tail_refit_failures": tail_info["n_refit_failures"],
            "n_boot": tail_info["n_boot"],
        })

    sensitivity_rows = run_threshold_sensitivity(vals, label, TAIL_FRACTIONS, N_BOOT_SENSITIVITY, SEED + 1)
    figure_path = write_diagnostic_plots(vals, PRIMARY_TAIL_FRACTION, label)
    return rows, sensitivity_rows, figure_path


def write_csv(rows: list[dict], filename: str) -> str:
    out_path = os.path.join(TABLES, filename)
    with open(out_path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    return out_path


def write_report(rows: list[dict], sensitivity_rows: list[dict], figure_paths: dict) -> str:
    lines = []
    lines.append("# EVT (Extreme-Value-Theory) Tail-Aware Confidence Intervals")
    lines.append("")
    lines.append(
        "Standalone comparison diagnostic (see src/m14_evt_tail_ci.py). Does "
        "not modify or replace m8_h1_test.py's existing bootstrap CI or its "
        "subsample (m-out-of-n) stability diagnostic -- both stay in place. "
        "This module computes a second, heavy-tail-aware interval for "
        "CR1/CR4/HHI/top-1% share, alongside the plain nonparametric "
        "bootstrap, using the same real per-bot volume data and the same "
        "concentration formulas m8 uses."
    )
    lines.append("")
    lines.append(
        "**Important labeling note:** the \"EVT tail-bootstrap\" interval "
        "below is a MODEL-BASED, semi-parametric interval -- it assumes the "
        "fitted Generalized Pareto Distribution is a reasonable model for "
        "the tail above the chosen threshold. It is not an assumption-free "
        "or purely nonparametric CI the way that label might suggest. The "
        "threshold-sensitivity table and diagnostic plots below exist "
        "specifically so that assumption can be checked rather than taken "
        "on faith."
    )
    lines.append("")
    lines.append(
        "| Window | Metric | Point estimate | Naive bootstrap 95% CI | "
        "EVT/semi-parametric bootstrap 95% CI (u=90th pct) | EVT/naive CI "
        "width ratio | Implied Hill alpha (95% CI across replicates) |"
    )
    lines.append("|---|---|---:|---:|---:|---:|---:|")
    for r in rows:
        fmt = (lambda v: f"{v:.4f}") if r["metric"] != "hhi" else (lambda v: f"{v:.1f}")
        lines.append(
            f"| {r['window']} | {r['metric']} | {fmt(r['point_estimate'])} | "
            f"[{fmt(r['naive_bootstrap_ci_low'])}, {fmt(r['naive_bootstrap_ci_high'])}] | "
            f"[{fmt(r['evt_tail_bootstrap_ci_low'])}, {fmt(r['evt_tail_bootstrap_ci_high'])}] | "
            f"{r['evt_ci_width_over_naive_ci_width']:.2f}x | "
            f"{r['gpd_implied_hill_alpha']:.3f} "
            f"[{r['gpd_implied_hill_alpha_ci_low']:.3f}, {r['gpd_implied_hill_alpha_ci_high']:.3f}] |"
        )
    lines.append("")
    primary = [r for r in rows if r["window"] == "revised-24m"]
    if primary:
        xi = primary[0]["gpd_shape_xi"]
        alpha_implied = primary[0]["gpd_implied_hill_alpha"]
        # [Corrected: this used to hardcode "roughly [0.6, 0.8]" here, copied
        # from a wrong figure in src/m8_h1_test.py at the time. Now read
        # dynamically via load_hill_alpha_range() -- see its docstring.]
        hill_range = load_hill_alpha_range()
        lines.append(
            f"GPD tail fit (revised-24m, primary, u=90th pct): threshold u = "
            f"${primary[0]['gpd_threshold_u']:.2f}, k = "
            f"{primary[0]['gpd_tail_count_k']} exceedances out of n bots, "
            f"shape xi = {xi:.3f}, implied tail index alpha = 1/xi = "
            f"{alpha_implied:.3f} (refit across {primary[0]['n_boot']} "
            f"bootstrap replicates; {primary[0]['n_tail_refit_failures']} "
            f"refits fell back to the primary fit). For comparison, "
            f"m2_concentration.py's Hill estimator on the same data reports "
            f"alpha in roughly [{hill_range}] (see Table 3, read directly "
            f"via load_hill_alpha_range() rather than hardcoded); these two "
            f"independent tail-index estimates should be in the same rough "
            f"range as an internal consistency check -- they are not forced "
            f"to match by construction."
        )
    lines.append("")
    lines.append(
        "Interpretation: a wider EVT/semi-parametric interval than the "
        "naive bootstrap for a given metric means the naive bootstrap was "
        "UNDERSTATING uncertainty for that metric, because it cannot "
        "simulate a bot more extreme than the largest one already observed "
        "-- exactly the failure mode this module targets. A ratio close to "
        "1x means the two methods agree, i.e. the naive interval was not "
        "materially miscalibrated for that metric. This diagnostic does "
        "not itself choose which interval the paper should quote; that is "
        "a reporting decision informed by this comparison, not a decision "
        "this script makes."
    )
    lines.append("")

    lines.append("## Threshold sensitivity")
    lines.append("")
    lines.append(
        "The table above uses a single primary threshold (u = 90th "
        "percentile, tail_fraction=0.10), matching m2_concentration.py's "
        "Hill-threshold convention. The table below sweeps the threshold "
        "across tail_fraction in {5%, 10%, 15%, 20%} for each metric and "
        "window, so threshold sensitivity is shown rather than assumed "
        "away. A metric/window whose EVT interval and implied alpha stay "
        "roughly stable across this range is on firmer footing than one "
        "that swings sharply with threshold choice."
    )
    lines.append("")
    lines.append(
        "| Window | Metric | Tail fraction | Threshold u | k | Point "
        "estimate | EVT 95% CI | Implied alpha | Alpha 95% CI |"
    )
    lines.append("|---|---|---:|---:|---:|---:|---:|---:|---:|")
    for r in sensitivity_rows:
        fmt = (lambda v: f"{v:.4f}") if r["metric"] != "hhi" else (lambda v: f"{v:.1f}")
        lines.append(
            f"| {r['window']} | {r['metric']} | {r['tail_fraction']:.2f} | "
            f"${r['threshold_u']:.0f} | {r['tail_count_k']} | "
            f"{fmt(r['point_estimate'])} | "
            f"[{fmt(r['evt_ci_low'])}, {fmt(r['evt_ci_high'])}] | "
            f"{r['implied_hill_alpha']:.3f} | "
            f"[{r['implied_alpha_ci_low']:.3f}, {r['implied_alpha_ci_high']:.3f}] |"
        )
    lines.append("")
    lines.append(
        "Full detail (including per-threshold refit-failure counts) is in "
        "h1_evt_threshold_sensitivity.csv."
    )
    lines.append("")

    lines.append("## Tail-fit parameter uncertainty")
    lines.append("")
    lines.append(
        "Unlike a version of this bootstrap that fits the GPD once and "
        "reuses that single (xi, sigma) pair for every replicate, this "
        "module refits (xi, sigma) by MLE on a bootstrap resample of the "
        "observed exceedances inside every replicate, so uncertainty in "
        "the tail-shape estimate itself is propagated into the reported "
        "interval and into the \"implied Hill alpha (95% CI)\" column above "
        "-- not just resampling variability in which observations appear. "
        "A refit that fails on a degenerate resample falls back to the "
        "primary fit rather than crashing the run; how often this happens "
        "is reported per row (n_tail_refit_failures / n_refit_failures in "
        "the CSVs) so it is visible, not silently absorbed."
    )
    lines.append("")

    lines.append("## Calibration / backtest diagnostics")
    lines.append("")
    lines.append(
        "For each window, output/figures/evt_diagnostics_<window>.png "
        "contains three panels checking the threshold and GPD assumption "
        "empirically rather than by assertion: (1) a mean-excess plot "
        "across a grid of candidate thresholds -- a roughly linear/flat "
        "region around the chosen threshold supports the GPD "
        "approximation there; (2) a Hill-style tail-index stability plot "
        "tracing alpha_hat(k) over a wide range of top-k counts -- a "
        "reader can check directly whether \"alpha ~= X\" is a stable "
        "estimate or an artifact of one particular k; (3) a GPD QQ plot of "
        "the observed exceedances against the fitted GPD's theoretical "
        "quantiles at the primary threshold -- points close to the "
        "45-degree line support the fit, systematic curvature would not."
    )
    for label, path in figure_paths.items():
        rel = os.path.relpath(path, ROOT)
        lines.append(f"- {label}: `{rel}`")
    lines.append("")

    out_path = os.path.join(REPORTS, "evt_tail_ci.md")
    with open(out_path, "w") as f:
        f.write("\n".join(lines) + "\n")
    return out_path


def main() -> None:
    rows = []
    sensitivity_rows = []
    figure_paths = {}
    for label, data_dir in (("revised-24m", DATA_24), ("revised-30m", DATA_30)):
        r, sr, fig_path = run_window(label, data_dir)
        rows += r
        sensitivity_rows += sr
        figure_paths[label] = fig_path

    csv_path = write_csv(rows, "h1_evt_tail_ci.csv")
    sensitivity_csv_path = write_csv(sensitivity_rows, "h1_evt_threshold_sensitivity.csv")
    report_path = write_report(rows, sensitivity_rows, figure_paths)
    print(f"Wrote {len(rows)} rows to {csv_path}")
    print(f"Wrote {len(sensitivity_rows)} rows to {sensitivity_csv_path}")
    print(f"Wrote report to {report_path}")
    for label, path in figure_paths.items():
        print(f"Wrote diagnostic figure for {label} to {path}")


if __name__ == "__main__":
    main()
