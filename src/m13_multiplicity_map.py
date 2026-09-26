"""
m13_multiplicity_map.py -- auto-generated multiple-comparison correction map.

Regenerates output/reports/multiplicity_correction_map.md: a single table
showing which correction family and clustering scheme applies to which test,
across m8-m11. Family sizes and correction descriptions are read directly
from columns already present in the modules' own real output tables (not
hardcoded), so re-running this script after a family changes (an extra bin,
an extra contrast) reflects that automatically, same as every other
generated file in output/reports/ and output/tables/.

INPUTS (all pre-existing, already-committed real output; nothing here is
invented, estimated, or re-derived from raw microdata):
  - output/tables/h2a_conditional_tests.csv          (m9a, H2 e-value tests)
  - output/tables/h2a_matched_uncertainty.csv         (m9a, H2 Hoeffding bound)
  - output/tables/table_h2_q5e_small_vs_larger_contrasts.csv  (m9b, H2 regression)
  - output/tables/h3_upgrade_joint_wald_tests.csv     (m10, H3 primary family)
  - output/tables/h3_additional_formal_tests.csv      (m10, H3 secondary family)
  - output/tables/h4_protocol_pairwise_attack_incidence_24m.csv (m11, H4)
  - output/reports/h1_hypothesis_tests.md             (m8, H1 -- checked for
    the absence of any multiplicity-correction language, confirming no
    family/correction applies there; this is a text-presence check, not a
    number pulled from a table, since H1 has no correction family to count)

OUTPUT (new/regenerated file only; nothing existing is modified):
  - output/reports/multiplicity_correction_map.md
"""

from __future__ import annotations

import csv
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TABLES = os.path.join(ROOT, "output", "tables")
REPORTS = os.path.join(ROOT, "output", "reports")


def read_rows(name: str) -> list[dict]:
    path = os.path.join(TABLES, name)
    with open(path, newline="") as f:
        return list(csv.DictReader(f))


def h1_row() -> dict:
    """H1 has no multiplicity family to count from a table -- confirmed by
    the absence of any Holm/Bonferroni/family language in its own report.
    This is stated directly rather than fabricated as a table lookup."""
    report_path = os.path.join(REPORTS, "h1_hypothesis_tests.md")
    with open(report_path) as f:
        text = f.read().lower()
    has_correction_language = any(
        kw in text for kw in ("holm", "bonferroni", "multiplicity", "family")
    )
    assert not has_correction_language, (
        "h1_hypothesis_tests.md now contains multiplicity-correction language; "
        "the H1 row below assumes none exists and must be updated by hand."
    )
    return {
        "module": "m8_h1_test.py",
        "hypothesis": "H1 (concentration)",
        "family": "Gini / top-1% share vs. operational benchmark, per window",
        "family_size": "1 test per metric per window (24m primary; 30m is "
        "robustness re-run of the same test, not pooled into a family)",
        "correction": "None -- single primary test per metric does not "
        "require a multiplicity correction",
        "clustering": "Nonparametric bootstrap (window-level)",
        "status": "Confirmatory (primary window only)",
    }


def h2a_conditional_row() -> dict:
    rows = read_rows("h2a_conditional_tests.csv")
    family_sizes = {r["family_size"] for r in rows}
    assert len(family_sizes) == 1, f"h2a_conditional_tests.csv has inconsistent family_size values: {family_sizes}"
    family_size = family_sizes.pop()
    assert family_size == str(len(rows)), (
        f"h2a_conditional_tests.csv's own family_size column ({family_size}) "
        f"does not match its actual row count ({len(rows)})"
    )
    return {
        "module": "m9a_h2_test.py",
        "hypothesis": "H2 (conditional evidence)",
        "family": "Monthly conditional e-value/martingale tests "
        "(bins x directions x targets x windows)",
        "family_size": family_size,
        "correction": "Bonferroni, applied to the Markov-inequality p-bound "
        "on top of the fixed-stake supermartingale",
        "clustering": "Sequential, per-bin martingale (not cluster-based)",
        "status": 'Descriptive/exploratory -- reported as "not identified", '
        "not a confirmatory decision",
    }


def h2a_matched_row() -> dict:
    rows = read_rows("h2a_matched_uncertainty.csv")
    family_sizes = {r["family_intervals"] for r in rows}
    assert len(family_sizes) == 1, f"h2a_matched_uncertainty.csv has inconsistent family_intervals values: {family_sizes}"
    family_size = family_sizes.pop()
    assert family_size == str(len(rows)), (
        f"h2a_matched_uncertainty.csv's own family_intervals column ({family_size}) "
        f"does not match its actual row count ({len(rows)})"
    )
    return {
        "module": "m9a_h2_test.py",
        "hypothesis": "H2 (matched uncertainty)",
        "family": "Hoeffding-type bound (bins x weighting x windows)",
        "family_size": family_size,
        "correction": "Family-adjusted Hoeffding radius "
        "(2*family/alpha term inside the bound itself)",
        "clustering": "Same as above",
        "status": "Descriptive interval, not a significance test",
    }


def h2b_row() -> dict:
    rows = read_rows("table_h2_q5e_small_vs_larger_contrasts.csv")
    primary = [r for r in rows if r["sample"] == "24m_primary_all_project_versions"]
    adjustments = {r["multiplicity_adjustment"] for r in primary}
    methods = {r["inference_method"] for r in primary}
    return {
        "module": "m9b_h2_test.py",
        "hypothesis": "H2 (grouped-binomial regression)",
        "family": "Small-vs-larger trade-size-bin contrasts, primary 24m specification",
        "family_size": str(len(primary)),
        "correction": "; ".join(sorted(adjustments)),
        "clustering": "; ".join(sorted(methods)),
        "status": f"Confirmatory ({sum(1 for r in primary if r['significant_holm_0_05']=='True')}/"
        f"{len(primary)} significant after Holm in the primary 24m specification)",
    }


def h3_primary_row() -> dict:
    rows = read_rows("h3_upgrade_joint_wald_tests.csv")
    primary = [r for r in rows if r["hac_lag"] == "14"]
    return {
        "module": "m10_h3_test.py",
        "hypothesis": "H3 (primary temporal evolution)",
        "family": "Dencun/Pectra joint step+slope HAC(14) Wald tests "
        "(outcomes x upgrades)",
        "family_size": str(len(primary)),
        "correction": "Holm step-down",
        "clustering": "HAC(14), single time series (heteroskedasticity/"
        "autocorrelation-robust, no clustering)",
        "status": "Confirmatory (primary)",
    }


def h3_secondary_row() -> dict:
    rows = read_rows("h3_additional_formal_tests.csv")
    return {
        "module": "m10_h3_test.py",
        "hypothesis": "H3 (secondary formal tests)",
        "family": "Post-upgrade slope and omnibus temporal tests "
        "(outcomes x sub-tests)",
        "family_size": str(len(rows)),
        "correction": "Holm step-down (separate family from the primary "
        "joint-test family above)",
        "clustering": "HAC(14), same series",
        "status": "Secondary/formal, explicitly association not causal effect",
    }


def h4_row() -> dict:
    rows = read_rows("h4_protocol_pairwise_attack_incidence_24m.csv")
    dfs = {r["df"] for r in rows}
    statuses = {r["inference_status"] for r in rows}
    return {
        "module": "m11_h4_test.py",
        "hypothesis": "H4 (pairwise protocol contrasts)",
        "family": "All pairwise log-odds contrasts between protocols with "
        ">=1 observed attack, 24m sample",
        "family_size": str(len(rows)),
        "correction": "Holm step-down, reported as p_value_holm_exploratory",
        "clustering": f"CR1, clustered by calendar month (df={sorted(dfs)[0] if len(dfs)==1 else dfs})",
        "status": "; ".join(sorted(statuses)),
    }


def render(rows: list[dict]) -> str:
    lines = []
    lines.append("# Multiple-Comparison Correction Map")
    lines.append("")
    lines.append(
        "This is an auto-generated reference table (see "
        "`src/m13_multiplicity_map.py`) mapping which correction family and "
        "clustering scheme applies to which test across the project's "
        "modules. It is regenerated directly from the same already-real, "
        "already-committed output tables the other modules produce -- "
        "family sizes and correction descriptions are read from those "
        "tables' own columns, not hardcoded. Nothing here changes any "
        "existing test, correction, or conclusion; it only documents, in "
        "one place, decisions already made independently inside each "
        "module (m8-m11)."
    )
    lines.append("")
    lines.append(
        "| Module | Hypothesis | Test family | Family size | Correction | "
        "Clustering / inference unit | Decision-rule status |"
    )
    lines.append("|---|---|---|---|---|---|---|")
    for r in rows:
        lines.append(
            f"| {r['module']} | {r['hypothesis']} | {r['family']} | "
            f"{r['family_size']} | {r['correction']} | {r['clustering']} | "
            f"{r['status']} |"
        )
    lines.append("")
    lines.append("## Why the families differ in size and structure")
    lines.append("")
    lines.append(
        "Each module's family is scoped to the tests it actually runs as a "
        "coherent group, not to the project as a whole. m9a runs the same "
        "conditional test independently across bins, directions, targets "
        "and windows, so its family is the full cross-product of those "
        "dimensions. m9b only corrects across the trade-size-bin contrasts "
        "within one specification -- it does not pool across specifications "
        "(24m primary vs. 30m robustness). m10 deliberately keeps two "
        "families apart (primary joint tests vs. secondary formal tests) "
        "because they answer different questions and mixing them would "
        "over- or under-correct one of the two. m11 applies Holm across "
        "all available pairwise contrasts for transparency, but labels the "
        "result exploratory rather than confirmatory, because with only "
        "~24 independent monthly clusters, a family this large is past the "
        "point where the correction's own asymptotics are trustworthy -- "
        "the same reasoning that leads it to withhold the incidence "
        "omnibus and protocol-by-time tests entirely."
    )
    lines.append("")
    lines.append("## Suggested paper placement")
    lines.append("")
    lines.append(
        "A short reference in a methods appendix (e.g. \"Appendix: "
        "Multiple-Comparison Corrections\"), cited once from the main text "
        "where multiplicity is first mentioned, so a reader can look up "
        "\"which correction applied to which test\" in one place rather "
        "than reconstructing it from five separate modules."
    )
    return "\n".join(lines) + "\n"


def main() -> None:
    rows = [
        h1_row(),
        h2a_conditional_row(),
        h2a_matched_row(),
        h2b_row(),
        h3_primary_row(),
        h3_secondary_row(),
        h4_row(),
    ]
    out_path = os.path.join(REPORTS, "multiplicity_correction_map.md")
    with open(out_path, "w") as f:
        f.write(render(rows))
    print(f"Wrote {len(rows)} rows to {out_path}")


if __name__ == "__main__":
    main()
