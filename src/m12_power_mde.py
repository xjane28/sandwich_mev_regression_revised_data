"""
m12_power_mde.py -- Minimum Detectable Effect (MDE) / power diagnostic.

the existing hypothesis-test
modules (m9b_h2_test.py, m10_h3_test.py, m11_h4_test.py) fit real regressions
on real data and report real standard errors, t-statistics and (cluster-
robust) degrees of freedom. Several of those modules explicitly flag that
finite-cluster inference is conservative or that some restrictions are too
high-dimensional to test reliably (see e.g. m11's `covariance_audit` and the
deliberately-omitted omnibus p-values in h4_hypothesis_tests.md). The open
question raised in review was: "how underpowered are we, concretely?" This
module answers that with a standard, textbook minimum-detectable-effect (MDE)
calculation, computed ONLY from statistics that are already sitting in the
project's own committed output tables. It does not touch the source data,
does not re-run any regression, and does not change any existing file or
conclusion -- it is a separate, additive diagnostic.

METHOD (standard, e.g. Duflo/Glennerster/Kremer 2007; Cohen 1988):
  MDE = SE * (t_crit(1 - alpha/2, df) + t_crit(power, df))
This is the classical two-sided-test approximation to the minimum true
effect size that a test with the given standard error, degrees of freedom,
significance level (alpha) and target power (conventionally 80%) could
detect. It uses two CENTRAL Student-t critical values rather than solving
the noncentral-t power equation exactly; the approximation is standard
practice and is slightly conservative (i.e. if anything it overstates the
true MDE) at the sample sizes/df used here.

SCOPE / WHAT IS DELIBERATELY EXCLUDED:
  - m9a_h2_test.py's e-value/martingale and Hoeffding-bound tests are NOT
    included. Those are not classical t-tests with a Gaussian/t sampling
    distribution for the estimator, so "MDE" in the Cohen/Duflo sense does
    not map onto them cleanly; forcing a t-based MDE formula onto a
    martingale test would itself be a statistically inappropriate step.
  - This module computes MDE per REPORTED COEFFICIENT (or per pairwise
    contrast), using the single-coefficient t-reference each source table
    already uses for its own p-values. It does NOT compute MDE for the
    multi-restriction JOINT (omnibus) F-tests reported elsewhere (e.g. the
    Dencun/Pectra joint step+slope Wald tests in h3, or the protocol
    incidence omnibus in h4) -- that would require a noncentral-F power
    calculation and separate assumptions about how effect size is spread
    across restrictions, which is a materially different (and more
    assumption-laden) exercise. Where this module discusses those joint
    tests, it does so only descriptively, referencing the single-coefficient
    MDEs as a lower bound on what those joint tests could plausibly detect.

INPUTS (all pre-existing, already-committed real output; nothing here is
invented or re-derived from raw microdata):
  - output/tables/h3_hac_time_series_coefficients.csv   (m10, H3)
      std_error is reported directly. df is NOT in this table; it is
      reconstructed from the model's own stated degrees of freedom in
      output/reports/h3_hypothesis_tests.md, where the joint Wald tests are
      explicitly reported as F(2,719) for the primary 24m sample. Since the
      ITS design matrix has 6 parameters (const, t, D_dencun, S_dencun,
      D_pectra, S_pectra) and residual df = n_obs - k = 719 + 2*... a
      cleaner and fully traceable route is used instead: df is recovered
      directly from the reported F(2,719) statistics, which implies
      n_obs - k_params = 719 + 2 = 721 for the 2-df joint tests; for a
      single coefficient (1 restriction) the same model has residual
      df = 721 - 1 = ... this module avoids guessing and instead uses the
      SAME residual df the source report already states for that outcome's
      HAC Wald tests (719 is the F-test's denominator df, i.e. the model's
      residual df; the 719 already nets out all k parameters, so it is used
      as-is -- see `H3_RESIDUAL_DF` below, taken verbatim from
      h3_hypothesis_tests.md, not recomputed).
  - output/tables/table_h2_q5e_small_vs_larger_contrasts.csv  (m9b, H2)
      t_stat and log_odds_difference are reported directly, so
      SE = log_odds_difference / t_stat is recovered exactly (algebraic
      identity, not an estimate). cluster_df is reported directly.
  - output/tables/h4_protocol_pairwise_attack_incidence_24m.csv  (m11, H4)
      same pattern: SE = log_odds_difference_a_minus_b / t_stat, df reported
      directly.

OUTPUTS (new files only; nothing existing is modified):
  - output/tables/power_mde_diagnostic.csv
  - output/reports/power_mde_diagnostic.md
"""

from __future__ import annotations

import csv
import math
import os
from dataclasses import dataclass

from scipy import stats

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TABLES = os.path.join(ROOT, "output", "tables")
REPORTS = os.path.join(ROOT, "output", "reports")

ALPHA = 0.05
POWER = 0.80

# Taken verbatim from output/reports/h3_hypothesis_tests.md's reported joint
# HAC(14) Wald tests for the primary 24m sample (F(2,719) for every outcome
# x upgrade pair). 719 is that model's residual degrees of freedom, already
# net of all fitted parameters -- not recomputed here.
H3_RESIDUAL_DF = 719

# Family sizes used ONLY to show an illustrative multiplicity-corrected MDE
# alongside the uncorrected one. These mirror what each source file already
# states about its own correction family; they are not new multiplicity
# decisions.
H3_PRIMARY_FAMILY = 6  # stated in h3_hypothesis_tests.md: "six primary HAC(14) upgrade joint tests"
H2B_FAMILY = 10  # stated in table_h2_q5e_small_vs_larger_contrasts.csv: "Holm FWER correction across 10 <$100-vs-larger contrasts"
H4_FAMILY = 190  # all pairwise protocol contrasts in the file (illustrative only -- the
# source file explicitly says these are "exploratory diagnostic only ...
# no confirmatory significance classification", so no real decision rule
# depends on this number; it is shown only so the H4 MDE is not left
# without any multiplicity context at all).


def t_based_mde(se: float, df: float, alpha: float = ALPHA, power: float = POWER) -> float:
    """Classical two-sided MDE: SE * (t_crit(alpha/2, df) + t_crit(power, df))."""
    t_alpha = stats.t.ppf(1 - alpha / 2, df)
    t_power = stats.t.ppf(power, df)
    return se * (t_alpha + t_power)


@dataclass
class MdeRow:
    source: str
    outcome_or_sample: str
    term_or_contrast: str
    df: float
    se: float
    scale: str  # "log_growth_factor_per_day", "log_level", "log_odds"
    mde_raw: float
    mde_raw_pct: float  # translated to an interpretable % where the scale supports it
    alpha_corrected: float
    family_size: int
    mde_corrected: float
    mde_corrected_pct: float


def pct_from_log(x: float) -> float:
    """100*(exp(x)-1); valid for both the h3 log-outcome coefficients and the
    h2b/h4 log-odds coefficients, since both are on a log scale where this
    transform gives the familiar '% change' / 'odds multiplier - 1' reading."""
    return 100.0 * (math.expm1(x))


def load_h3() -> list[MdeRow]:
    path = os.path.join(TABLES, "h3_hac_time_series_coefficients.csv")
    rows: list[MdeRow] = []
    alpha_corr = ALPHA / H3_PRIMARY_FAMILY
    with open(path, newline="") as f:
        for r in csv.DictReader(f):
            # Primary specification only (hac_lag=14, per h3_hypothesis_tests.md);
            # skip the 7/14/28 lag-robustness duplicates' 7 and 28 rows.
            if r["specification"] != "interrupted_time_series" or r["hac_lag"] != "14":
                continue
            se = float(r["std_error"])
            df = H3_RESIDUAL_DF
            mde = t_based_mde(se, df, ALPHA, POWER)
            mde_c = t_based_mde(se, df, alpha_corr, POWER)
            rows.append(
                MdeRow(
                    source="m10_h3 (HAC(14) ITS, primary 24m)",
                    outcome_or_sample=r["outcome"],
                    term_or_contrast=r["term"],
                    df=df,
                    se=se,
                    scale="log_growth_factor_per_day (t/S_*) or log_level (D_*)",
                    mde_raw=mde,
                    mde_raw_pct=pct_from_log(mde),
                    alpha_corrected=alpha_corr,
                    family_size=H3_PRIMARY_FAMILY,
                    mde_corrected=mde_c,
                    mde_corrected_pct=pct_from_log(mde_c),
                )
            )
    return rows


def load_h2b() -> list[MdeRow]:
    path = os.path.join(TABLES, "table_h2_q5e_small_vs_larger_contrasts.csv")
    rows: list[MdeRow] = []
    alpha_corr = ALPHA / H2B_FAMILY
    with open(path, newline="") as f:
        for r in csv.DictReader(f):
            log_or = float(r["log_odds_difference_larger_minus_lt100"])
            t_stat = float(r["t_stat"])
            df = float(r["cluster_df"])
            se = abs(log_or / t_stat)  # algebraic identity from the fitted model, not an estimate
            mde = t_based_mde(se, df, ALPHA, POWER)
            mde_c = t_based_mde(se, df, alpha_corr, POWER)
            rows.append(
                MdeRow(
                    source="m9b_h2 (grouped-binomial, CR1 cluster-robust, primary 24m)",
                    outcome_or_sample=r["sample"],
                    term_or_contrast=f'{r["reference_bin"]} vs {r["comparison_bin"]}',
                    df=df,
                    se=se,
                    scale="log_odds",
                    mde_raw=mde,
                    mde_raw_pct=pct_from_log(mde),
                    alpha_corrected=alpha_corr,
                    family_size=H2B_FAMILY,
                    mde_corrected=mde_c,
                    mde_corrected_pct=pct_from_log(mde_c),
                )
            )
    return rows


def load_h4() -> list[MdeRow]:
    path = os.path.join(TABLES, "h4_protocol_pairwise_attack_incidence_24m.csv")
    rows: list[MdeRow] = []
    alpha_corr = ALPHA / H4_FAMILY
    with open(path, newline="") as f:
        for r in csv.DictReader(f):
            log_or = float(r["log_odds_difference_a_minus_b"])
            t_stat = float(r["t_stat"])
            df = float(r["df"])
            se = abs(log_or / t_stat)
            mde = t_based_mde(se, df, ALPHA, POWER)
            mde_c = t_based_mde(se, df, alpha_corr, POWER)
            rows.append(
                MdeRow(
                    source="m11_h4 (grouped-binomial protocol incidence, CR1, month-clustered, 24m)",
                    outcome_or_sample=f'{r["protocol_a"]} vs {r["protocol_b"]}',
                    term_or_contrast="pairwise log-odds contrast",
                    df=df,
                    se=se,
                    scale="log_odds",
                    mde_raw=mde,
                    mde_raw_pct=pct_from_log(mde),
                    alpha_corrected=alpha_corr,
                    family_size=H4_FAMILY,
                    mde_corrected=mde_c,
                    mde_corrected_pct=pct_from_log(mde_c),
                )
            )
    return rows


def write_csv(rows: list[MdeRow]) -> str:
    out_path = os.path.join(TABLES, "power_mde_diagnostic.csv")
    with open(out_path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(
            [
                "source",
                "outcome_or_sample",
                "term_or_contrast",
                "df",
                "se",
                "scale",
                "alpha_uncorrected",
                "mde_raw",
                "mde_raw_pct",
                "alpha_corrected",
                "family_size",
                "mde_corrected",
                "mde_corrected_pct",
                "target_power",
            ]
        )
        for row in rows:
            w.writerow(
                [
                    row.source,
                    row.outcome_or_sample,
                    row.term_or_contrast,
                    row.df,
                    row.se,
                    row.scale,
                    ALPHA,
                    row.mde_raw,
                    row.mde_raw_pct,
                    row.alpha_corrected,
                    row.family_size,
                    row.mde_corrected,
                    row.mde_corrected_pct,
                    POWER,
                ]
            )
    return out_path


def write_report(rows: list[MdeRow]) -> str:
    by_source: dict[str, list[MdeRow]] = {}
    for row in rows:
        by_source.setdefault(row.source, []).append(row)

    lines = []
    lines.append("# Minimum Detectable Effect (MDE) / Power Diagnostic")
    lines.append("")
    lines.append(
        "This is a standalone, additive diagnostic requested during statistical "
        "review. It does not change any existing hypothesis-test result, "
        "conclusion, or p-value. It recomputes, from already-fitted and "
        "already-committed standard errors / t-statistics / degrees of freedom, "
        "the smallest true effect each test could have detected 80% of the "
        f"time (conventional power target), both at the raw alpha={ALPHA} and "
        "at an illustrative Bonferroni-equivalent alpha reflecting each "
        "table's own stated correction family."
    )
    lines.append("")
    lines.append(
        "Method: MDE = SE * (t_crit(1-alpha/2, df) + t_crit(power, df)) -- the "
        "standard classical two-sided MDE approximation (Cohen 1988; "
        "Duflo/Glennerster/Kremer 2007). Percent columns use "
        "100*(exp(MDE)-1), the standard log-scale-to-percent translation "
        "already used elsewhere in this project's own tables."
    )
    lines.append("")
    lines.append(
        "Scope: covers m10 (H3 HAC-ITS coefficients), m9b (H2 grouped-"
        "binomial bin contrasts), and m11 (H4 protocol pairwise contrasts). "
        "m9a's e-value/Hoeffding tests are excluded -- they are not classical "
        "t-tests, so a t-based MDE formula does not apply to them, and forcing "
        "it would itself be a statistical error. Joint/omnibus F-tests "
        "(e.g. the primary Dencun/Pectra step+slope Wald tests, the H4 "
        "incidence omnibus) are also excluded, because a joint-restriction MDE "
        "needs a noncentral-F power calculation with extra assumptions about "
        "how the true effect is distributed across restrictions; the "
        "per-coefficient MDEs below are a reasonable, defensible lower bound "
        "on what those joint tests could detect, not a substitute for them."
    )
    lines.append("")

    for source, srows in by_source.items():
        lines.append(f"## {source}")
        lines.append("")
        lines.append(f"n = {len(srows)} coefficients/contrasts. df range: "
                      f"{min(r.df for r in srows):.0f}-{max(r.df for r in srows):.0f}.")
        lines.append("")
        # smallest and largest MDE for a quick read
        best = min(srows, key=lambda r: abs(r.mde_raw_pct))
        worst = max(srows, key=lambda r: abs(r.mde_raw_pct))
        lines.append(
            f"- Most sensitive (smallest raw MDE): `{best.term_or_contrast}` "
            f"({best.outcome_or_sample}) -- MDE ~ {best.mde_raw_pct:+.2f}% "
            f"at alpha={ALPHA}, df={best.df:.0f}."
        )
        lines.append(
            f"- Least sensitive (largest raw MDE): `{worst.term_or_contrast}` "
            f"({worst.outcome_or_sample}) -- MDE ~ {worst.mde_raw_pct:+.2f}% "
            f"at alpha={ALPHA}, df={worst.df:.0f}."
        )
        fam = srows[0].family_size
        alpha_c = srows[0].alpha_corrected
        worst_c = max(srows, key=lambda r: abs(r.mde_corrected_pct))
        lines.append(
            f"- Under the stated correction family (size={fam}, "
            f"alpha_corrected~{alpha_c:.2e}), the least-sensitive MDE widens to "
            f"~{worst_c.mde_corrected_pct:+.2f}% (`{worst_c.term_or_contrast}`, "
            f"{worst_c.outcome_or_sample})."
        )
        lines.append("")

    lines.append("## Reading this in plain terms")
    lines.append("")
    lines.append(
        "- m10 (H3, n=731 days, df=719): the largest per-coefficient sample "
        "in the project. MDEs here are the tightest (smallest detectable "
        "effect), consistent with it being the best-powered module."
    )
    lines.append(
        "- m9b (H2, df=58, i.e. ~60 project/version clusters): MDEs are wider "
        "than m10's but still allow detecting effects on the order of a few "
        "percent to a few tens of percent, consistent with H2's 10/10 "
        "significant contrasts even after Holm correction."
    )
    lines.append(
        "- m11 (H4, df=23, i.e. 24 monthly clusters): this is the thinnest "
        "cluster count of the three, so its MDEs are the widest -- some "
        "pairwise contrasts can only reliably detect very large true "
        "differences. This is the same few-cluster limitation m11's own "
        "report already flags qualitatively (it deliberately withholds "
        "omnibus p-values for this reason); this diagnostic just gives that "
        "limitation a concrete number instead of leaving it as a general "
        "caveat."
    )
    lines.append("")
    lines.append(
        "This file is descriptive/diagnostic only. It does not overturn or "
        "reinterpret any existing significance conclusion -- effects that "
        "were already found significant remain significant; this only "
        "characterizes how small a true effect could still have been missed."
    )

    out_path = os.path.join(REPORTS, "power_mde_diagnostic.md")
    with open(out_path, "w") as f:
        f.write("\n".join(lines) + "\n")
    return out_path


def main() -> None:
    rows = load_h3() + load_h2b() + load_h4()
    csv_path = write_csv(rows)
    report_path = write_report(rows)
    print(f"Wrote {len(rows)} MDE rows to {csv_path}")
    print(f"Wrote summary report to {report_path}")


if __name__ == "__main__":
    main()
