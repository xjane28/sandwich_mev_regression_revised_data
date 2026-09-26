# H2: observed data and measurement limitations

**H2 unchanged:** Uninformed order flow (retail) will subsidize informed order flow (bots), creating a 'Lemons' problem.

**Run status: completed.** See computation status for failed, missing or partial checks.

All empirical results below are calculated from the existing CSV exports inside project/fetch. There are no simulated observations, resampling or imputed values. The assumption-light track uses analytical conditional tests; the grouped-binomial regression track (estimated separately in m9b_h2_test.py and cross-referenced below) fits models only to observed Q5e query cells.


## Main question and interpretation

Within the same project/version and month, how does the observed attack rate differ between each larger trade-size bin and trades under $100?

For each observed project/version/month pair, attack rate = attacked events / eligible events. Difference (percentage points) = 100 * (larger-bin rate - under-$100 rate). Both rates must be observed in that same cell. Missing cells are not zeros. Projects can enter, leave or have gaps; no full-period activity requirement is imposed.

- A positive difference means higher observed attack incidence for that comparison.
- Persistence across projects, periods and weighting choices strengthens the descriptive finding; it is not independent replication.
- Neither result establishes retail identity, monetary subsidy or causation.
- Missing measurements mean H2 is not directly assessed, rather than H2 is false.

The two summaries answer different averaging questions: **equal project** gives each observed matched project equal weight within a month (equal versions within each project); **overlap exposure** gives more weight to cells with eligible activity in both compared bins. The same weights are applied to both rates. Each available month then has equal weight. Neither summary is the pooled probability for an arbitrary transaction. Both are reported without selecting the more favorable answer.

## Main observed results

| Window | Larger bin | Weighting | Larger rate (%) | Under-$100 rate (%) | Difference (pp) | Months | Matched coverage: larger / reference |
|---|---|---|---:|---:|---:|---:|---:|
| 24m | $100–250 | equal_project | 0.3482 | 0.1235 | +0.2247 | 24 | 100.00% / 99.99% |
| 24m | $100–250 | overlap_exposure | 1.2544 | 0.4926 | +0.7618 | 24 | 100.00% / 99.99% |
| 24m | $250–500 | equal_project | 0.5354 | 0.1176 | +0.4178 | 24 | 100.00% / 99.99% |
| 24m | $250–500 | overlap_exposure | 1.8455 | 0.4891 | +1.3564 | 24 | 100.00% / 99.99% |
| 24m | $500–1k | equal_project | 0.7678 | 0.1148 | +0.6530 | 24 | 100.00% / 99.99% |
| 24m | $500–1k | overlap_exposure | 2.3191 | 0.4805 | +1.8386 | 24 | 100.00% / 99.99% |
| 24m | $1k–2.5k | equal_project | 1.0340 | 0.1527 | +0.8813 | 24 | 100.00% / 99.99% |
| 24m | $1k–2.5k | overlap_exposure | 2.6493 | 0.4684 | +2.1809 | 24 | 100.00% / 99.99% |
| 24m | $2.5k–5k | equal_project | 1.3583 | 0.1148 | +1.2435 | 24 | 100.00% / 99.99% |
| 24m | $2.5k–5k | overlap_exposure | 2.9712 | 0.4373 | +2.5339 | 24 | 100.00% / 99.99% |
| 24m | $5k–10k | equal_project | 1.3999 | 0.1175 | +1.2824 | 24 | 99.99% / 99.90% |
| 24m | $5k–10k | overlap_exposure | 3.0580 | 0.3935 | +2.6645 | 24 | 99.99% / 99.90% |
| 24m | $10k–25k | equal_project | 1.3498 | 0.1164 | +1.2334 | 24 | 99.96% / 99.52% |
| 24m | $10k–25k | overlap_exposure | 2.7653 | 0.3477 | +2.4176 | 24 | 99.96% / 99.52% |
| 24m | $25k–50k | equal_project | 1.2435 | 0.1140 | +1.1295 | 24 | 99.92% / 98.76% |
| 24m | $25k–50k | overlap_exposure | 2.0465 | 0.2932 | +1.7533 | 24 | 99.92% / 98.76% |
| 24m | $50k–100k | equal_project | 1.4356 | 0.1232 | +1.3125 | 24 | 99.88% / 98.14% |
| 24m | $50k–100k | overlap_exposure | 1.3480 | 0.2609 | +1.0871 | 24 | 99.88% / 98.14% |
| 24m | ≥$100k | equal_project | 2.3031 | 0.1273 | +2.1757 | 24 | 99.94% / 98.18% |
| 24m | ≥$100k | overlap_exposure | 1.3623 | 0.2556 | +1.1067 | 24 | 99.94% / 98.18% |
| 30m | $100–250 | equal_project | 0.3781 | 0.1659 | +0.2123 | 30 | 100.00% / 99.99% |
| 30m | $100–250 | overlap_exposure | 1.2047 | 0.5227 | +0.6820 | 30 | 100.00% / 99.99% |
| 30m | $250–500 | equal_project | 0.5321 | 0.1634 | +0.3687 | 30 | 100.00% / 99.99% |
| 30m | $250–500 | overlap_exposure | 1.6620 | 0.5160 | +1.1460 | 30 | 100.00% / 99.99% |
| 30m | $500–1k | equal_project | 0.7544 | 0.1595 | +0.5949 | 30 | 100.00% / 99.98% |
| 30m | $500–1k | overlap_exposure | 2.0398 | 0.5033 | +1.5365 | 30 | 100.00% / 99.98% |
| 30m | $1k–2.5k | equal_project | 0.9395 | 0.1908 | +0.7488 | 30 | 100.00% / 99.98% |
| 30m | $1k–2.5k | overlap_exposure | 2.2737 | 0.4882 | +1.7856 | 30 | 100.00% / 99.98% |
| 30m | $2.5k–5k | equal_project | 1.2236 | 0.1484 | +1.0752 | 30 | 100.00% / 99.93% |
| 30m | $2.5k–5k | overlap_exposure | 2.5174 | 0.4554 | +2.0620 | 30 | 100.00% / 99.93% |
| 30m | $5k–10k | equal_project | 1.4254 | 0.1518 | +1.2735 | 30 | 99.98% / 99.83% |
| 30m | $5k–10k | overlap_exposure | 2.5720 | 0.4154 | +2.1566 | 30 | 99.98% / 99.83% |
| 30m | $10k–25k | equal_project | 1.1713 | 0.1509 | +1.0204 | 30 | 99.96% / 99.29% |
| 30m | $10k–25k | overlap_exposure | 2.3182 | 0.3712 | +1.9471 | 30 | 99.96% / 99.29% |
| 30m | $25k–50k | equal_project | 1.2326 | 0.1527 | +1.0799 | 30 | 99.92% / 98.45% |
| 30m | $25k–50k | overlap_exposure | 1.7628 | 0.3208 | +1.4420 | 30 | 99.92% / 98.45% |
| 30m | $50k–100k | equal_project | 1.2126 | 0.1605 | +1.0521 | 30 | 99.90% / 97.62% |
| 30m | $50k–100k | overlap_exposure | 1.2234 | 0.3122 | +0.9111 | 30 | 99.90% / 97.62% |
| 30m | ≥$100k | equal_project | 1.9176 | 0.1754 | +1.7422 | 30 | 99.95% / 97.83% |
| 30m | ≥$100k | overlap_exposure | 1.2895 | 0.3358 | +0.9537 | 30 | 99.95% / 97.83% |

Rates are averages using the stated common weights; reference rates can differ across comparisons because matched cells and weights differ. Coverage is the share of original eligible events in each bin retained in matched cells, not a confidence level. The 24-month and 30-month results overlap. These tables establish recorded differences, not population significance. See main_matched_results.csv for full precision, monthly sign counts and coverage; composition_matched_cells.csv contains the underlying pairs.

- 24m, equal_project: 10 positive, 0 negative and 0 zero average differences across 10 larger bins.
- 24m, overlap_exposure: 10 positive, 0 negative and 0 zero average differences across 10 larger bins.
- 30m, equal_project: 10 positive, 0 negative and 0 zero average differences across 10 larger bins.
- 30m, overlap_exposure: 10 positive, 0 negative and 0 zero average differences across 10 larger bins.
A positive average does not mean the difference is positive for every project or every month; heterogeneity is reported in the checks below.

## Conservative uncertainty for the main matched comparison

D_t is the observed matched monthly rate difference under one of the two stated weighting rules. The target here is the average of E[D_t | previous monthly information] over the stated window. These conditional expectations may change with market conditions. This is not an unconditional long-run average, a causal effect, or a monetary subsidy. It is a different and less restrictive target than the exploratory every-month conditional nulls.

Because D_t lies in [-1,1], the conditional Hoeffding bound gives P(|mean(D_t) - mean(E[D_t|past])| >= r) <= 2 exp(-T r^2/2). For 40 intervals (10 bins, 2 weighting schemes, 2 windows), r = sqrt(2 log(2*40/0.05)/T). Intervals are clipped to the known [-100,100] percentage-point range. This is a fixed-horizon simultaneous 95% bound for that fixed family. It permits dependence across months and comparisons, changing conditional means and variances, and overlapping windows. It uses neither simulated data nor estimated standard errors.

Only the all-project matched comparisons enter these bounds. Each monthly statistic uses its own observed cells and denominators. No full-window outcome-dependent weights or selections are used. A missing scheduled month makes an interval unavailable, rather than triggering imputation. The bound does not correct measurement error or establish the unmeasured H2 mechanism. The 95% statement covers this fixed interval family and is not a simultaneous error-control statement for other analysis families.

| Window | Intervals | Half-width (percentage points) | Intervals containing zero |
|---|---:|---:|---:|
| 24m | 20 | 78.41 | 20 |
| 30m | 20 | 70.13 | 20 |
All calculated intervals include zero. This method does not establish a positive expected matched difference. It also does not establish equality or absence of a relationship.

The wide intervals reflect the conservative bounded-data guarantee and the short monthly record. This is not a proof that every possible method must be inconclusive. Narrower intervals require a stronger, defensible model or a different justified method. Do not replace the known [-1,1] bound with the observed minimum/maximum: unobserved outcomes need not lie inside the observed range.

Methodological basis: the bounded-observation martingale concentration framework and average conditional-expectation target in [Howard et al., Time-uniform, nonparametric, nonasymptotic confidence sequences](https://arxiv.org/abs/1810.08240). The implementation uses the elementary fixed-time Hoeffding bound derived above, not simulations or the more elaborate confidence sequences in that paper.

## Weighting and dominant-project sensitivity

These are descriptive robustness analyses, not additional hypothesis tests. Both rates are compared inside identical project/version/month cells. Unmatched cells are excluded with denominator coverage explicitly reported; they are not imputed. The matched population can differ by bin and window. Composition coverage must accompany any comparison.

Overlap-exposure standardization applies weights n_reference*n_bin/(n_reference+n_bin) to both rates. It emphasizes strata with exposure in both bins. Equal-project standardization first averages matched versions within a project/month, then averages projects equally. Finally, each available month receives equal weight. These are deliberately different target averages, not repeated independent tests. They remove observed project/version composition differences within the matched cells but do not identify a causal trade-size effect.

The largest project is selected using 24-month eligible-event counts and the same project is excluded in both windows. This deletion is an influence check, not a separate confirming sample. No new p-values are calculated or added to the 80-test family.

Excluded project: **uniswap**, with 86.85% of primary-window eligible events.

| Window | Scope | Weighting | Bins with positive mean difference | Bins compared |
|---|---|---|---:|---:|
| 24m | all_projects | equal_project | 10 | 10 |
| 24m | all_projects | overlap_exposure | 10 | 10 |
| 24m | exclude_primary_dominant_project | equal_project | 10 | 10 |
| 24m | exclude_primary_dominant_project | overlap_exposure | 10 | 10 |
| 30m | all_projects | equal_project | 10 | 10 |
| 30m | all_projects | overlap_exposure | 10 | 10 |
| 30m | exclude_primary_dominant_project | equal_project | 10 | 10 |
| 30m | exclude_primary_dominant_project | overlap_exposure | 10 | 10 |

Full magnitudes in percentage points, monthly signs and observed monthly ranges appear in composition_summary.csv. Ranges are not confidence intervals. composition_monthly.csv separates unrestricted pooled, matched pooled and standardized differences. composition_coverage.csv reports retained denominators; composition_matched_cells.csv and composition_project_month.csv retain the calculation detail.

### Effect-size and confirmation assessment

No economically meaningful attack-rate threshold was supplied or identified in these exports. None is invented or selected from the results. The standardized rate differences measure observed magnitude; they are not estimates of monetary losses. The existing mean-difference e-tests address different, unadjusted conditional hypotheses and cannot supply uncertainty for these standardized contrasts. An economic-effect threshold test is therefore not performed. A direct subsidy test also remains unavailable: the existing windows have already been inspected, and attributable transfer/participant/mechanism measurements are missing.

## Consistency, common support and measurement checks

These checks are descriptive and add no p-values. They do not treat projects, calendar halves, or overlapping windows as independent replications. consistency_by_project.csv reports each project mean, its available months and signs. consistency_project_distribution.csv includes negative and zero project means, spread, and concentration of positive mean differences. That concentration is an equal-project difference diagnostic, not a volume or loss share. Calendar periods are fixed January-June and July-December halves; none is selected for favorable results. Monthly sign reversals and all half-year results are retained.

The primary pairwise analysis includes each project/version/month whenever both compared bins have observed denominators, even if that project enters, exits or has missing months. The optional common_bins comparison requires all 11 bins only within a particular project/version/month. No project must remain active throughout either window, and later activity is not used to decide inclusion in earlier months. Selection does not use attack outcomes, but activity-based selection can still change the target population. Source coverage by bin, unavailable restrictions, and all comparisons are reported. These are sensitivity results, not corrections for unobserved missingness.

| Restriction | Window | Scope | Weighting | Positive mean differences | Bins compared |
|---|---|---|---|---:|---:|
| common_bins | 24m | all_projects | equal_project | 10 | 10 |
| common_bins | 24m | all_projects | overlap_exposure | 10 | 10 |
| common_bins | 24m | exclude_primary_dominant_project | equal_project | 10 | 10 |
| common_bins | 24m | exclude_primary_dominant_project | overlap_exposure | 10 | 10 |
| common_bins | 30m | all_projects | equal_project | 10 | 10 |
| common_bins | 30m | all_projects | overlap_exposure | 10 | 10 |
| common_bins | 30m | exclude_primary_dominant_project | equal_project | 10 | 10 |
| common_bins | 30m | exclude_primary_dominant_project | overlap_exposure | 10 | 10 |

Measurement checks use the actual query0a_data_quality.csv exports: null and zero USD values, small-notional rows, and count reconciliation. They do not estimate attack-detector false positives/negatives, retail classification accuracy, or differential detection by size/time. Aggregate quality metrics cannot resolve those questions. No detection rates or loss estimates are invented.

The existing conditional ordering tests retain their original narrow nulls. Persistent rankings can contradict those conditional nulls without establishing a positive unconditional mean, a causal effect or H2. A common-support pattern, temporal robustness, and dominant-project sensitivity can strengthen a descriptive conclusion, but do not create independent confirmation or supply the missing subsidy and Lemons measurements.

### Project heterogeneity

| Window (all projects) | Positive-project count range across bins | Negative-project count range | Zero-project count range |
|---|---:|---:|---:|
| 24m | 12–17 | 2–5 | 12–14 |
| 30m | 13–18 | 2–5 | 13–14 |
Project means cover different observed months and may include zero detected attacks. Positive aggregate averages do not establish a universal project-level relationship.
Across the reported overlapping windows, scopes, bins and weighting schemes, 4 of 360 half-year comparisons have negative mean differences. These counts are descriptive and dependent.

### Coverage of common-support restrictions

Coverage below is relative to each original window before dominant-project exclusion; it is the minimum retained candidate share across the 11 bins.

| Restriction | Window | Minimum candidate coverage |
|---|---|---:|
| common_bins | 24m | 97.45% |
| common_bins | 30m | 96.88% |
Missing cells are not filled with zero. Both the pairwise and optional all-bin comparisons describe their observed matched populations; they do not recover unobserved activity.

## Recorded sample context

- 24m: 218,761,436 eligible events and 3,753,857 detected attacked events (1.7160%).
- 30m: 288,218,841 eligible events and 4,286,398 detected attacked events (1.4872%).
- 24m: highest observed bin attack rate 2.7251% in $2.5k–5k. Adjacent bin changes: increase,increase,increase,increase,increase,decrease,decrease,decrease,decrease,increase.
- 30m: highest observed bin attack rate 2.4142% in $2.5k–5k. Adjacent bin changes: increase,increase,increase,increase,increase,decrease,decrease,decrease,decrease,increase.
- 24m: 33 projects; largest project accounts for 86.85% of eligible events.
- 30m: 35 projects; largest project accounts for 84.95% of eligible events.

Rates describe detected attacked events per eligible event, not unique traders. These differences and peaks describe the recorded sample; they do not establish a population inverted-U relationship or causation. The 30-month window overlaps the 24-month window and is not an independent replication. The extension table uses only observed additional months; it is not a forecast.

## Victim-tier context

The project defines Retail/Small/Institutional using victim-trade size quantiles. The approximately 50% Retail share follows the median-based definition and is not independent evidence of disproportionate targeting or verified retail identity. Traded notional is not victim loss or bot profit. Q5b quantile tiers and Q5e fixed dollar bins are different classifications.

## Measurement requirements for H2

The following is a requirements assessment, not a statistical test or an empirical finding about unmeasured quantities.

| Component | Assessment | Missing evidence |
|---|---|---|
| Retail/informed participant classification | not_identified | Verified information status and defensible retail identity; a small trade is not a verified retail trader. |
| Retail-to-informed-bot subsidy | not_identified_no_valid_H2_p_value | Matched loss/transfer and bot proceeds with gas, fees, inventory and counterfactual execution accounted for. Notional volume is neither loss nor profit. |
| Lemons mechanism | not_identified | Identified information asymmetry, mechanism-linked outcome and defensible comparison/counterfactual. |
| Related size-susceptibility association | observed_descriptions_and_exploratory_conditional_tests | Direct H2 measurements and causal identification; conditional-null tests do not supply these. |

## Grouped-binomial regression complement

Using the same observed Q5e query cells, a grouped-binomial logit is fitted with trade-size indicators, project/version fixed effects and month fixed effects (the under-$100 bin is the statistical reference category only and is not treated as verified retail). This model is estimated once, in `src/m9b_h2_test.py`, rather than re-estimated here, so there is a single canonical set of coefficients, odds ratios, cluster-robust standard errors and Holm-adjusted contrasts to cite -- not two independently-coded copies that could silently drift apart. Primary model-based uncertainty uses project/version-clustered CR1 covariance with t/F reference distributions and G-1 cluster degrees of freedom; two-way project/version + month clustering is reported there as approximate robustness inference. This is grouped-binomial regression-based association inference. It does not create observations, establish causality, identify retail status, measure monetary subsidy, or directly test H2.

See (all in `output/tables/`): `table_h2_q5e_adjusted_odds_ratios.csv` (odds ratios and CR1 confidence intervals by trade-size bin), `table_h2_q5e_joint_tests.csv` (the omnibus Wald/F test that all nonreference size coefficients are jointly zero), `table_h2_q5e_small_vs_larger_contrasts.csv` (Holm-adjusted pairwise contrasts against the under-$100 reference), `table_h2_q5e_two_way_cluster_robustness.csv` (two-way clustering robustness), and `table_h2_q5e_coefficient_stability_diagnostics.csv` / `table_h2_q5e_leave_one_project_out.csv` (stability diagnostics not duplicated in this track).

## Conclusion

**Multiple-testing scope (read this first):** this report and its cross-referenced companion (m9b_h2_test.py) evaluate H2-related evidence across three separately-controlled test families: (1) 80 bounded monthly e-tests at alpha=0.05 (Holm-adjusted within this family only), (2) 40 Hoeffding-type matched-interval bounds at a separate alpha=0.05 (also controlled within this family only), and (3) the grouped-binomial regression's pairwise and joint contrasts (Holm-adjusted within that family only, see m9b_h2_test.py). There is no combined family-wise error rate across these three families, and none is claimed. A reader should not add up rejections across families (for example, "most of the roughly 130 tests across these procedures rejected their null") and treat that as one coherent significance claim at one alpha -- each family's error-rate control applies only to comparisons within that family.

The output establishes the reported counts, proportions and patterns within the supplied exports, subject to their measurement definitions. It does not establish retail-to-bot monetary transfers, information status, or the Lemons mechanism. H2 is not directly assessed because its required measurements are missing; this does not mean H2 is false. The main conclusion concerns observed matched attack incidence. Exploratory pooled tests are kept in a separate appendix.

## Review of statistical procedures

inference_review.csv records each reviewed procedure, its decision, and observed design facts. Validation checks and descriptive comparisons are retained. A grouped-binomial fixed-effects regression model with project/version-clustered covariance is estimated once, in m9b_h2_test.py, and cross-referenced here as a regression-based complement rather than re-estimated; unclustered and other unsupported variants remain withheld. The bounded monthly e-tests remain separate procedures with different null hypotheses. A withheld test is not a rejected null hypothesis. This is not a claim that all formal inference is impossible, and simulations are neither read nor used to make these decisions. Regression on real data is not artificial data; its inferential assumptions still require justification.

For the methodological distinction between within-cluster dependence, independent clusters, and few-cluster limitations, see [Cameron and Miller, A Practitioner's Guide to Cluster-Robust Inference](https://cameron.econ.ucdavis.edu/research/Cameron_Miller_JHR_2015_February.pdf). This reference provides methodology, not empirical inputs.

## Source traceability

fetch_inventory.csv lists available export schemas and hashes. The designated revised Q5e/Q5b files supply attack-rate and tier analysis values; Q0a supplies measurement-quality summaries. Legacy exports are not pooled. run_manifest.json records the exact input file hashes.

## Computation status

- 24m_input: completed
- 24m_conditional_e_tests: completed
- 30m_input: completed
- 30m_conditional_e_tests: completed
- composition_sensitivity: completed
- composition_sensitivity/composition_status/24m/all_projects/02_100_250: completed
- composition_sensitivity/composition_status/24m/all_projects/03_250_500: completed
- composition_sensitivity/composition_status/24m/all_projects/04_500_1000: completed
- composition_sensitivity/composition_status/24m/all_projects/05_1000_2500: completed
- composition_sensitivity/composition_status/24m/all_projects/06_2500_5000: completed
- composition_sensitivity/composition_status/24m/all_projects/07_5000_10000: completed
- composition_sensitivity/composition_status/24m/all_projects/08_10000_25000: completed
- composition_sensitivity/composition_status/24m/all_projects/09_25000_50000: completed
- composition_sensitivity/composition_status/24m/all_projects/10_50000_100000: completed
- composition_sensitivity/composition_status/24m/all_projects/11_100000_plus: completed
- composition_sensitivity/composition_status/24m/exclude_primary_dominant_project/02_100_250: completed
- composition_sensitivity/composition_status/24m/exclude_primary_dominant_project/03_250_500: completed
- composition_sensitivity/composition_status/24m/exclude_primary_dominant_project/04_500_1000: completed
- composition_sensitivity/composition_status/24m/exclude_primary_dominant_project/05_1000_2500: completed
- composition_sensitivity/composition_status/24m/exclude_primary_dominant_project/06_2500_5000: completed
- composition_sensitivity/composition_status/24m/exclude_primary_dominant_project/07_5000_10000: completed
- composition_sensitivity/composition_status/24m/exclude_primary_dominant_project/08_10000_25000: completed
- composition_sensitivity/composition_status/24m/exclude_primary_dominant_project/09_25000_50000: completed
- composition_sensitivity/composition_status/24m/exclude_primary_dominant_project/10_50000_100000: completed
- composition_sensitivity/composition_status/24m/exclude_primary_dominant_project/11_100000_plus: completed
- composition_sensitivity/composition_status/30m/all_projects/02_100_250: completed
- composition_sensitivity/composition_status/30m/all_projects/03_250_500: completed
- composition_sensitivity/composition_status/30m/all_projects/04_500_1000: completed
- composition_sensitivity/composition_status/30m/all_projects/05_1000_2500: completed
- composition_sensitivity/composition_status/30m/all_projects/06_2500_5000: completed
- composition_sensitivity/composition_status/30m/all_projects/07_5000_10000: completed
- composition_sensitivity/composition_status/30m/all_projects/08_10000_25000: completed
- composition_sensitivity/composition_status/30m/all_projects/09_25000_50000: completed
- composition_sensitivity/composition_status/30m/all_projects/10_50000_100000: completed
- composition_sensitivity/composition_status/30m/all_projects/11_100000_plus: completed
- composition_sensitivity/composition_status/30m/exclude_primary_dominant_project/02_100_250: completed
- composition_sensitivity/composition_status/30m/exclude_primary_dominant_project/03_250_500: completed
- composition_sensitivity/composition_status/30m/exclude_primary_dominant_project/04_500_1000: completed
- composition_sensitivity/composition_status/30m/exclude_primary_dominant_project/05_1000_2500: completed
- composition_sensitivity/composition_status/30m/exclude_primary_dominant_project/06_2500_5000: completed
- composition_sensitivity/composition_status/30m/exclude_primary_dominant_project/07_5000_10000: completed
- composition_sensitivity/composition_status/30m/exclude_primary_dominant_project/08_10000_25000: completed
- composition_sensitivity/composition_status/30m/exclude_primary_dominant_project/09_25000_50000: completed
- composition_sensitivity/composition_status/30m/exclude_primary_dominant_project/10_50000_100000: completed
- composition_sensitivity/composition_status/30m/exclude_primary_dominant_project/11_100000_plus: completed
- main_matched_results: completed
- matched_uncertainty: completed
- matched_uncertainty/matched_uncertainty_status/24m/02_100_250: completed
- matched_uncertainty/matched_uncertainty_status/24m/02_100_250: completed
- matched_uncertainty/matched_uncertainty_status/24m/03_250_500: completed
- matched_uncertainty/matched_uncertainty_status/24m/03_250_500: completed
- matched_uncertainty/matched_uncertainty_status/24m/04_500_1000: completed
- matched_uncertainty/matched_uncertainty_status/24m/04_500_1000: completed
- matched_uncertainty/matched_uncertainty_status/24m/05_1000_2500: completed
- matched_uncertainty/matched_uncertainty_status/24m/05_1000_2500: completed
- matched_uncertainty/matched_uncertainty_status/24m/06_2500_5000: completed
- matched_uncertainty/matched_uncertainty_status/24m/06_2500_5000: completed
- matched_uncertainty/matched_uncertainty_status/24m/07_5000_10000: completed
- matched_uncertainty/matched_uncertainty_status/24m/07_5000_10000: completed
- matched_uncertainty/matched_uncertainty_status/24m/08_10000_25000: completed
- matched_uncertainty/matched_uncertainty_status/24m/08_10000_25000: completed
- matched_uncertainty/matched_uncertainty_status/24m/09_25000_50000: completed
- matched_uncertainty/matched_uncertainty_status/24m/09_25000_50000: completed
- matched_uncertainty/matched_uncertainty_status/24m/10_50000_100000: completed
- matched_uncertainty/matched_uncertainty_status/24m/10_50000_100000: completed
- matched_uncertainty/matched_uncertainty_status/24m/11_100000_plus: completed
- matched_uncertainty/matched_uncertainty_status/24m/11_100000_plus: completed
- matched_uncertainty/matched_uncertainty_status/30m/02_100_250: completed
- matched_uncertainty/matched_uncertainty_status/30m/02_100_250: completed
- matched_uncertainty/matched_uncertainty_status/30m/03_250_500: completed
- matched_uncertainty/matched_uncertainty_status/30m/03_250_500: completed
- matched_uncertainty/matched_uncertainty_status/30m/04_500_1000: completed
- matched_uncertainty/matched_uncertainty_status/30m/04_500_1000: completed
- matched_uncertainty/matched_uncertainty_status/30m/05_1000_2500: completed
- matched_uncertainty/matched_uncertainty_status/30m/05_1000_2500: completed
- matched_uncertainty/matched_uncertainty_status/30m/06_2500_5000: completed
- matched_uncertainty/matched_uncertainty_status/30m/06_2500_5000: completed
- matched_uncertainty/matched_uncertainty_status/30m/07_5000_10000: completed
- matched_uncertainty/matched_uncertainty_status/30m/07_5000_10000: completed
- matched_uncertainty/matched_uncertainty_status/30m/08_10000_25000: completed
- matched_uncertainty/matched_uncertainty_status/30m/08_10000_25000: completed
- matched_uncertainty/matched_uncertainty_status/30m/09_25000_50000: completed
- matched_uncertainty/matched_uncertainty_status/30m/09_25000_50000: completed
- matched_uncertainty/matched_uncertainty_status/30m/10_50000_100000: completed
- matched_uncertainty/matched_uncertainty_status/30m/10_50000_100000: completed
- matched_uncertainty/matched_uncertainty_status/30m/11_100000_plus: completed
- matched_uncertainty/matched_uncertainty_status/30m/11_100000_plus: completed
- consistency_checks: completed
- common_support_checks: completed
- common_support_checks/support_comparison_status/24m/all_projects/02_100_250/common_bins: completed
- common_support_checks/support_comparison_status/24m/all_projects/03_250_500/common_bins: completed
- common_support_checks/support_comparison_status/24m/all_projects/04_500_1000/common_bins: completed
- common_support_checks/support_comparison_status/24m/all_projects/05_1000_2500/common_bins: completed
- common_support_checks/support_comparison_status/24m/all_projects/06_2500_5000/common_bins: completed
- common_support_checks/support_comparison_status/24m/all_projects/07_5000_10000/common_bins: completed
- common_support_checks/support_comparison_status/24m/all_projects/08_10000_25000/common_bins: completed
- common_support_checks/support_comparison_status/24m/all_projects/09_25000_50000/common_bins: completed
- common_support_checks/support_comparison_status/24m/all_projects/10_50000_100000/common_bins: completed
- common_support_checks/support_comparison_status/24m/all_projects/11_100000_plus/common_bins: completed
- common_support_checks/support_comparison_status/24m/exclude_primary_dominant_project/02_100_250/common_bins: completed
- common_support_checks/support_comparison_status/24m/exclude_primary_dominant_project/03_250_500/common_bins: completed
- common_support_checks/support_comparison_status/24m/exclude_primary_dominant_project/04_500_1000/common_bins: completed
- common_support_checks/support_comparison_status/24m/exclude_primary_dominant_project/05_1000_2500/common_bins: completed
- common_support_checks/support_comparison_status/24m/exclude_primary_dominant_project/06_2500_5000/common_bins: completed
- common_support_checks/support_comparison_status/24m/exclude_primary_dominant_project/07_5000_10000/common_bins: completed
- common_support_checks/support_comparison_status/24m/exclude_primary_dominant_project/08_10000_25000/common_bins: completed
- common_support_checks/support_comparison_status/24m/exclude_primary_dominant_project/09_25000_50000/common_bins: completed
- common_support_checks/support_comparison_status/24m/exclude_primary_dominant_project/10_50000_100000/common_bins: completed
- common_support_checks/support_comparison_status/24m/exclude_primary_dominant_project/11_100000_plus/common_bins: completed
- common_support_checks/support_comparison_status/30m/all_projects/02_100_250/common_bins: completed
- common_support_checks/support_comparison_status/30m/all_projects/03_250_500/common_bins: completed
- common_support_checks/support_comparison_status/30m/all_projects/04_500_1000/common_bins: completed
- common_support_checks/support_comparison_status/30m/all_projects/05_1000_2500/common_bins: completed
- common_support_checks/support_comparison_status/30m/all_projects/06_2500_5000/common_bins: completed
- common_support_checks/support_comparison_status/30m/all_projects/07_5000_10000/common_bins: completed
- common_support_checks/support_comparison_status/30m/all_projects/08_10000_25000/common_bins: completed
- common_support_checks/support_comparison_status/30m/all_projects/09_25000_50000/common_bins: completed
- common_support_checks/support_comparison_status/30m/all_projects/10_50000_100000/common_bins: completed
- common_support_checks/support_comparison_status/30m/all_projects/11_100000_plus/common_bins: completed
- common_support_checks/support_comparison_status/30m/exclude_primary_dominant_project/02_100_250/common_bins: completed
- common_support_checks/support_comparison_status/30m/exclude_primary_dominant_project/03_250_500/common_bins: completed
- common_support_checks/support_comparison_status/30m/exclude_primary_dominant_project/04_500_1000/common_bins: completed
- common_support_checks/support_comparison_status/30m/exclude_primary_dominant_project/05_1000_2500/common_bins: completed
- common_support_checks/support_comparison_status/30m/exclude_primary_dominant_project/06_2500_5000/common_bins: completed
- common_support_checks/support_comparison_status/30m/exclude_primary_dominant_project/07_5000_10000/common_bins: completed
- common_support_checks/support_comparison_status/30m/exclude_primary_dominant_project/08_10000_25000/common_bins: completed
- common_support_checks/support_comparison_status/30m/exclude_primary_dominant_project/09_25000_50000/common_bins: completed
- common_support_checks/support_comparison_status/30m/exclude_primary_dominant_project/10_50000_100000/common_bins: completed
- common_support_checks/support_comparison_status/30m/exclude_primary_dominant_project/11_100000_plus/common_bins: completed
- common_support_checks/support_status/24m/common_bins: completed
- common_support_checks/support_status/30m/common_bins: completed
- 24m_measurement_quality: completed
- 24m_measurement_quality/measurement_check_status/24m: completed
- 30m_measurement_quality: completed
- 30m_measurement_quality/measurement_check_status/30m: completed
- victim_tier_context: completed

## Exploratory appendix: pooled conditional monthly tests

These pooled tests do not test the main within-project comparison and do not determine its descriptive conclusion. These conditional tests evaluate related observable implications rather than the full H2 mechanism. The multiplicity adjustment covers the 80 tests in this file, and does not provide multiplicity control for distinct analysis families outside that set.

For every larger fixed dollar bin, aggregate all projects within each calendar month and compare its attacked/eligible rate with the under-$100 bin. This is a marginal market-composition comparison, not a project-adjusted or causal effect. Months receive equal weight; unequal event counts remain in the rate denominators. Missing monthly denominators cause unavailability, not imputation.

Two distinct one-sided nulls are tested in both directions:

1. **Conditional mean difference:** the expected signed monthly rate difference, given previous monthly observations, is nonpositive at every month.
2. **Conditional monthly ordering:** given previous months, a difference in the specified direction is never more probable than a difference in the opposite direction. Exact ties contribute zero.

These are stronger, history-conditional nulls than equality of overall average rates. Serial dependence is allowed under these conditional restrictions; independent months, independent transactions, constant variance, normality and a large number of months are not required. A process with zero long-run mean can violate these conditional nulls. Therefore rejection must not be reported as rejection of equal unconditional means.

Let X_t be the signed rate difference (between -1 and 1) or its sign. The fixed-stake statistic is L_T = product_t(1 + 0.5 X_t). Under the stated null, each factor has conditional expectation at most one, so this nonnegative product has expectation at most one. The Markov inequality gives p_bound = min(1, 1/L_T). The stake is fixed at 0.5; it is not optimized using these data. No maximum over dates is used. The reported adjusted bound is min(1, 80*p_bound), with rejection at 0.05. All 10 bins, two directions, two targets and two windows belong to this one family. The denominator remains 80 if some tests are unavailable. Dependence between tests and overlapping windows does not invalidate this Bonferroni bound.

Rejection provides evidence against the stated every-month conditional null. It does not establish a positive effect in every month, a positive unconditional mean, future persistence, causation, participant information status, subsidy or an inverted U. Failure to reject is inconclusive. The raw-difference test is particularly conservative because its known bound is [-1,1] while observed attack-rate differences can be small. The ordering test discards magnitude and must not substitute for an economic-effect-size claim.

The finite-sample argument above applies to the stated fixed testing rule and the explicitly defined conditional nulls.

Methodological basis: [Waudby-Smith and Ramdas, Estimating means of bounded random variables by betting](https://arxiv.org/abs/2010.09686), especially the capital-process construction and non-iid extensions. The code uses the elementary one-sided supermartingale argument shown above, not the simulation results in the paper.

| Window | Target | Tests computed | Exploratory rejection-threshold crossings |
|---|---|---:|---:|
| 24m | conditional_mean_rate_difference | 20 | 0 |
| 24m | conditional_monthly_ordering | 20 | 10 |
| 30m | conditional_mean_rate_difference | 20 | 0 |
| 30m | conditional_monthly_ordering | 20 | 9 |

All outcomes, including non-rejections and opposite directions, are in conditional_tests.csv. monthly_test_inputs.csv gives the actual counts, denominators and exact rate ordering for each monthly comparison.

| Window | Bin versus under $100 | Target | Direction | Adjusted p-bound |
|---|---|---|---|---:|
| 24m | $100–250 | conditional_monthly_ordering | larger_bin_higher | 0.00475226 |
| 24m | $250–500 | conditional_monthly_ordering | larger_bin_higher | 0.00475226 |
| 24m | $500–1k | conditional_monthly_ordering | larger_bin_higher | 0.00475226 |
| 24m | $1k–2.5k | conditional_monthly_ordering | larger_bin_higher | 0.00475226 |
| 24m | $2.5k–5k | conditional_monthly_ordering | larger_bin_higher | 0.00475226 |
| 24m | $5k–10k | conditional_monthly_ordering | larger_bin_higher | 0.00475226 |
| 24m | $10k–25k | conditional_monthly_ordering | larger_bin_higher | 0.0142568 |
| 24m | $25k–50k | conditional_monthly_ordering | larger_bin_higher | 0.0142568 |
| 24m | $50k–100k | conditional_monthly_ordering | larger_bin_higher | 0.0142568 |
| 24m | ≥$100k | conditional_monthly_ordering | larger_bin_higher | 0.00475226 |
| 30m | $100–250 | conditional_monthly_ordering | larger_bin_higher | 0.000417208 |
| 30m | $250–500 | conditional_monthly_ordering | larger_bin_higher | 0.000417208 |
| 30m | $500–1k | conditional_monthly_ordering | larger_bin_higher | 0.00125162 |
| 30m | $1k–2.5k | conditional_monthly_ordering | larger_bin_higher | 0.00375487 |
| 30m | $2.5k–5k | conditional_monthly_ordering | larger_bin_higher | 0.0112646 |
| 30m | $5k–10k | conditional_monthly_ordering | larger_bin_higher | 0.0337938 |
| 30m | $25k–50k | conditional_monthly_ordering | larger_bin_higher | 0.0337938 |
| 30m | $50k–100k | conditional_monthly_ordering | larger_bin_higher | 0.0337938 |
| 30m | ≥$100k | conditional_monthly_ordering | larger_bin_higher | 0.000417208 |
