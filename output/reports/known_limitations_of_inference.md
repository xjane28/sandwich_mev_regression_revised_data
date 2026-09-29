# Known Limitations of Inference

Standalone summary document. Consolidates, in one place, every area of statistically fragile or bounded inference identified across the H1–H4 analysis pipeline. This document exists so the limitations don't have to be reconstructed by re-reading six different files. Where a mechanism already mitigates a limitation, that is stated; where it does not (and cannot), that is stated too.

---

## 1. H1 concentration metrics (CR1, CR4, HHI, top-1% share) are fragile under a heavy, possibly infinite-mean tail

The Hill tail-index estimate for per-bot volume is **alpha ≈ 0.34–0.41** (see `output/tables/table3_tail_estimates.csv`, read programmatically by `load_hill_tail_estimates()` in `src/m8_h1_test.py` and by `load_hill_alpha_range()` in `src/m14_evt_tail_ci.py`). Alpha < 1 implies the underlying distribution's mean is theoretically undefined (infinite-mean regime), and order-statistic-dominated summary metrics — CR1, CR4, HHI, top-1% share — are the metrics most sensitive to this, because their value is driven by the single largest (or few largest) bots rather than the bulk of the distribution.

Two independent diagnostics quantify this rather than paper over it:

- `src/m8_h1_test.py`'s `subsample_stability()` (m-out-of-n subsample bootstrap), which shows these metrics do not stabilize the way a light-tailed statistic would under resampling.
- `src/m14_evt_tail_ci.py`'s EVT/GPD-based semi-parametric bootstrap (`output/reports/evt_tail_ci.md`, `output/tables/h1_evt_tail_ci.csv`), which simulates tail draws beyond the observed maximum and produces a materially wider interval than the naive bootstrap for cr1, hhi, and (in the opposite direction) an interval that excludes the point estimate entirely for cr4 and top_1pct_share (e.g. revised-24m cr4: point 0.5950 vs. EVT CI [0.7394, 1.0000]). This is documented in that report as an expected model consequence, not a computational error, and is explicitly labeled a "heavy-tail stress test / model-based sensitivity check," not a drop-in replacement CI.

**Status: transparently diagnosed and quantified, not eliminated.** This is a real property of the data under alpha < 1. The two diagnostics above (kept side by side deliberately, per the module docstring cross-reference in `m8_h1_test.py`) let a reader see exactly how fragile these four metrics are and by how much.

**Already available in the same pipeline:** Gini, CR10, and CR20 (also in `output/tables/table2_concentration.csv` / `table3_tail_estimates.csv`) are far less sensitive to the single largest observations and are the more defensible headline concentration statistics when the tail is this heavy. CR1/CR4/HHI/top-1% share remain useful for describing extreme dominance but should be read alongside their wide intervals, not in isolation.

---

## 2. H2b grouped-binomial regression (`m9b_h2_test.py`): quasi-complete separation risk in some contrasts

Grouped-binomial fixed-effect logistic regression on sparse or highly imbalanced clusters can produce quasi-complete or complete separation, which inflates coefficient magnitude and standard errors and can produce spuriously "significant" contrasts. This is now gated by `apply_model_stability_gate()` (confirmed present in `src/m9b_h2_test.py`, called at its `retail24 = apply_model_stability_gate(...)` call site), which adds three columns to the H2b output:

- `model_stability_status` — overall fit-level stability flag,
- `contrast_stability_status` — per-contrast flag comparing the primary fit against a refit excluding degenerate clusters, bounded by a stated ±25% odds-ratio drift threshold,
- `inferential_status` — the resulting confirmatory/non-confirmatory classification.

Unstable contrasts have `significant_holm_0_05` set to a pandas nullable NA (via nullable "boolean" dtype) rather than the affected rows being silently dropped from the output.

**Status: gated, not eliminated.** Separation risk is a structural feature of grouped-binomial models on sparse contingency tables; the gate prevents an unstable contrast from being reported as confirmatory-grade evidence, but does not make the underlying sparse-cluster problem go away. Any contrast surviving the gate should still be read as a fit on real, standard data; any contrast failing it is explicitly excluded from the paper's confirmatory claims by construction.

---

## 3. H2a conservative/assumption-light analysis (`m9a_h2_test.py`): methods explicitly withheld

m9a_h2_test.py contains a self-documented inference_review() table listing methods that were considered and deliberately not applied, with the stated reason for each — for example, Firth penalized-logistic significance testing is listed as withheld, with the documented rationale that treating each observation as an independent penalized-logistic trial does not justify working-independence assumptions for what are actually dependent market events.

Status: self-documented design choice, not a gap. This is the conservative/assumption-light arm of H2 by design — it exists specifically to avoid the assumptions those withheld methods would require.
---

## 4. H4 protocol-level analysis (`m11_h4_test.py`): small cluster count for cluster-robust inference

H4's cluster-robust (CR1) standard errors are computed over roughly 24 monthly clusters. Asymptotic cluster-robust theory generally wants a substantially larger number of clusters for its guarantees to be reliable; ~24 is on the low end, which can understate true standard errors. This module already self-labels its results "exploratory" rather than confirmatory for this reason.

**Status: acknowledged design limitation, not independently re-derived in this audit.** No small-cluster wild-bootstrap or other small-cluster-count correction was implemented or verified in this session; the existing "exploratory" label is the honest current position.

---

## 5. H3 persistence/temporal-evolution tests (`m10_h3_test.py`): single time series, HAC(14)

H3 uses HAC (Newey-West style, lag 14) standard errors on what is a single aggregate time series. This is a standard and reasonable choice for serial correlation, but it was not independently stress-tested in this audit (e.g. no bandwidth-sensitivity sweep or alternative HAC lag was run against it, unlike the threshold-sensitivity sweep performed for H1's EVT interval).

**Status: general caveat carried over from the existing codebase, not independently audited in this session.** No defect was found, but no additional robustness check beyond reading the existing HAC(14) implementation was performed here either.

---

## 6. Cross-window (24m vs. 30m) comparisons: nested, overlapping samples

The "revised-24m" and "revised-30m" windows are not independent samples — the 24-month window is nested inside (a subset of) the 30-month window. Any comparison of a statistic across the two windows (e.g. Hill alpha 0.341 for 24m vs. 0.326 for 30m) is a comparison of overlapping-sample estimates, not two independent draws, so there is no formal permutation-test or independent-samples p-value for "did this change between windows."

**Status: acknowledged overlap, not resolved with a formal test.** Differences across the two windows are legitimately reportable as descriptive robustness checks (does the qualitative conclusion hold under a different window length) but should not be presented as if a hypothesis test of "did the estimate change" was performed, because the standard machinery for such a test assumes independent samples that do not exist here.

---

## Summary table

| # | Area | Metric(s) / module | Mechanism in place | Status |
|---|---|---|---|---|
| 1 | Heavy-tail concentration | CR1, CR4, HHI, top-1% share (`m8_h1_test.py`, `m14_evt_tail_ci.py`) | Subsample stability diagnostic + EVT/GPD semi-parametric interval, threshold-sensitivity sweep, calibration plots | Transparently quantified; structurally fragile by nature of alpha≈0.34–0.41, not fixable in code |
| 2 | Quasi-separation | Grouped-binomial contrasts (`m9b_h2_test.py`) | `apply_model_stability_gate()`: model/contrast/inferential status columns, NA-gated significance | Gated; unstable contrasts excluded from confirmatory claims |
| 3 | Withheld methods | H2a conservative analysis (`m9a_h2_test.py`) | Self-documented `inference_review()` table with reasons | By design; not a gap |
| 4 | Small cluster count | H4 protocol analysis (`m11_h4_test.py`), ~24 monthly clusters | Self-labeled "exploratory" | Acknowledged; not independently re-derived here |
| 5 | Single time series, HAC(14) | H3 persistence tests (`m10_h3_test.py`) | Standard HAC(14) SEs | General caveat; not independently stress-tested here |
| 6 | Nested window overlap | 24m vs. 30m comparisons | None (descriptive only) | Acknowledged; no formal test exists for overlapping samples |

---

*This document consolidates existing, already-verified findings from the project's code and reports (`table3_tail_estimates.csv`, `evt_tail_ci.md`, `m9b_h2_test.py`, `m9a_h2_test.py`, `m10_h3_test.py`, `m11_h4_test.py`). It introduces no new data, estimates, or claims beyond what is already computed and reported elsewhere in this repository.*
