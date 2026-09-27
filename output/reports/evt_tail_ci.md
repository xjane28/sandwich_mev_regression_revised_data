# EVT (Extreme-Value-Theory) Tail-Aware Confidence Intervals

Standalone comparison diagnostic (see src/m14_evt_tail_ci.py). Does not modify or replace m8_h1_test.py's existing bootstrap CI or its subsample (m-out-of-n) stability diagnostic -- both stay in place. This module computes a second, heavy-tail-aware interval for CR1/CR4/HHI/top-1% share, alongside the plain nonparametric bootstrap, using the same real per-bot volume data and the same concentration formulas m8 uses.

**Important labeling note:** the "EVT tail-bootstrap" interval below is a MODEL-BASED, semi-parametric interval -- it assumes the fitted Generalized Pareto Distribution is a reasonable model for the tail above the chosen threshold. It is not an assumption-free or purely nonparametric CI the way that label might suggest. The threshold-sensitivity table and diagnostic plots below exist specifically so that assumption can be checked rather than taken on faith.

| Window | Metric | Point estimate | Naive bootstrap 95% CI | EVT/semi-parametric bootstrap 95% CI (u=90th pct) | EVT/naive CI width ratio | Implied Hill alpha (95% CI across replicates) |
|---|---|---:|---:|---:|---:|---:|
| revised-24m | cr1 | 0.3154 | [0.0788, 0.4188] | [0.2867, 1.0000] | 2.10x | 0.341 [0.318, 0.368] |
| revised-24m | cr4 | 0.5950 | [0.2525, 0.7152] | [0.7394, 1.0000] | 0.56x | 0.341 [0.318, 0.368] |
| revised-24m | hhi | 1348.2 | [308.8, 2085.0] | [1791.4, 9999.6] | 4.62x | 0.341 [0.318, 0.368] |
| revised-24m | top_1pct_share | 0.9849 | [0.9643, 0.9927] | [0.9986, 1.0000] | 0.05x | 0.341 [0.318, 0.368] |
| revised-30m | cr1 | 0.3211 | [0.0646, 0.4180] | [0.2982, 1.0000] | 1.99x | 0.326 [0.305, 0.350] |
| revised-30m | cr4 | 0.5634 | [0.2041, 0.6977] | [0.7257, 1.0000] | 0.56x | 0.326 [0.305, 0.350] |
| revised-30m | hhi | 1302.8 | [232.0, 1935.2] | [1802.6, 9999.6] | 4.81x | 0.326 [0.305, 0.350] |
| revised-30m | top_1pct_share | 0.9811 | [0.9580, 0.9908] | [0.9993, 1.0000] | 0.02x | 0.326 [0.305, 0.350] |

GPD tail fit (revised-24m, primary, u=90th pct): threshold u = $101168.30, k = 980 exceedances out of n bots, shape xi = 2.929, implied tail index alpha = 1/xi = 0.341 (refit across 2000 bootstrap replicates; 0 refits fell back to the primary fit). For comparison, m2_concentration.py's Hill estimator on the same data reports alpha in roughly [0.34-0.41] (see Table 3, read directly via load_hill_alpha_range() rather than hardcoded); these two independent tail-index estimates should be in the same rough range as an internal consistency check -- they are not forced to match by construction.

Interpretation: a wider EVT/semi-parametric interval than the naive bootstrap for a given metric means the naive bootstrap was UNDERSTATING uncertainty for that metric, because it cannot simulate a bot more extreme than the largest one already observed -- exactly the failure mode this module targets. A ratio close to 1x means the two methods agree, i.e. the naive interval was not materially miscalibrated for that metric. This diagnostic does not itself choose which interval the paper should quote; that is a reporting decision informed by this comparison, not a decision this script makes.

## Threshold sensitivity

The table above uses a single primary threshold (u = 90th percentile, tail_fraction=0.10), matching m2_concentration.py's Hill-threshold convention. The table below sweeps the threshold across tail_fraction in {5%, 10%, 15%, 20%} for each metric and window, so threshold sensitivity is shown rather than assumed away. A metric/window whose EVT interval and implied alpha stay roughly stable across this range is on firmer footing than one that swings sharply with threshold choice.

| Window | Metric | Tail fraction | Threshold u | k | Point estimate | EVT 95% CI | Implied alpha | Alpha 95% CI |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| revised-24m | cr1 | 0.05 | $414309 | 490 | 0.3154 | [0.3039, 1.0000] | 0.316 | [0.290, 0.349] |
| revised-24m | cr4 | 0.05 | $414309 | 490 | 0.5950 | [0.7705, 1.0000] | 0.316 | [0.290, 0.349] |
| revised-24m | hhi | 0.05 | $414309 | 490 | 1348.2 | [2008.3, 9999.7] | 0.316 | [0.290, 0.349] |
| revised-24m | top_1pct_share | 0.05 | $414309 | 490 | 0.9849 | [0.9990, 1.0000] | 0.316 | [0.290, 0.349] |
| revised-24m | cr1 | 0.10 | $101168 | 980 | 0.3154 | [0.3136, 1.0000] | 0.341 | [0.319, 0.370] |
| revised-24m | cr4 | 0.10 | $101168 | 980 | 0.5950 | [0.7418, 1.0000] | 0.341 | [0.319, 0.370] |
| revised-24m | hhi | 0.10 | $101168 | 980 | 1348.2 | [1929.6, 9999.5] | 0.341 | [0.319, 0.370] |
| revised-24m | top_1pct_share | 0.10 | $101168 | 980 | 0.9849 | [0.9987, 1.0000] | 0.341 | [0.319, 0.370] |
| revised-24m | cr1 | 0.15 | $45161 | 1470 | 0.3154 | [0.2678, 0.9997] | 0.389 | [0.365, 0.418] |
| revised-24m | cr4 | 0.15 | $45161 | 1470 | 0.5950 | [0.6656, 1.0000] | 0.389 | [0.365, 0.418] |
| revised-24m | hhi | 0.15 | $45161 | 1470 | 1348.2 | [1470.4, 9994.1] | 0.389 | [0.365, 0.418] |
| revised-24m | top_1pct_share | 0.15 | $45161 | 1470 | 0.9849 | [0.9962, 1.0000] | 0.389 | [0.365, 0.418] |
| revised-24m | cr1 | 0.20 | $23970 | 1960 | 0.3154 | [0.2359, 0.9999] | 0.413 | [0.389, 0.442] |
| revised-24m | cr4 | 0.20 | $23970 | 1960 | 0.5950 | [0.6429, 1.0000] | 0.413 | [0.389, 0.442] |
| revised-24m | hhi | 0.20 | $23970 | 1960 | 1348.2 | [1292.4, 9998.7] | 0.413 | [0.389, 0.442] |
| revised-24m | top_1pct_share | 0.20 | $23970 | 1960 | 0.9849 | [0.9923, 1.0000] | 0.413 | [0.389, 0.442] |
| revised-30m | cr1 | 0.05 | $433275 | 537 | 0.3211 | [0.3048, 1.0000] | 0.303 | [0.279, 0.332] |
| revised-30m | cr4 | 0.05 | $433275 | 537 | 0.5634 | [0.7554, 1.0000] | 0.303 | [0.279, 0.332] |
| revised-30m | hhi | 0.05 | $433275 | 537 | 1302.8 | [1881.7, 9999.8] | 0.303 | [0.279, 0.332] |
| revised-30m | top_1pct_share | 0.05 | $433275 | 537 | 0.9811 | [0.9996, 1.0000] | 0.303 | [0.279, 0.332] |
| revised-30m | cr1 | 0.10 | $96139 | 1074 | 0.3211 | [0.3094, 1.0000] | 0.326 | [0.305, 0.351] |
| revised-30m | cr4 | 0.10 | $96139 | 1074 | 0.5634 | [0.7551, 1.0000] | 0.326 | [0.305, 0.351] |
| revised-30m | hhi | 0.10 | $96139 | 1074 | 1302.8 | [1866.7, 9999.6] | 0.326 | [0.305, 0.351] |
| revised-30m | top_1pct_share | 0.10 | $96139 | 1074 | 0.9811 | [0.9994, 1.0000] | 0.326 | [0.305, 0.351] |
| revised-30m | cr1 | 0.15 | $41956 | 1610 | 0.3211 | [0.2712, 0.9998] | 0.369 | [0.349, 0.394] |
| revised-30m | cr4 | 0.15 | $41956 | 1610 | 0.5634 | [0.6702, 1.0000] | 0.369 | [0.349, 0.394] |
| revised-30m | hhi | 0.15 | $41956 | 1610 | 1302.8 | [1520.6, 9995.5] | 0.369 | [0.349, 0.394] |
| revised-30m | top_1pct_share | 0.15 | $41956 | 1610 | 0.9811 | [0.9974, 1.0000] | 0.369 | [0.349, 0.394] |
| revised-30m | cr1 | 0.20 | $21981 | 2147 | 0.3211 | [0.2822, 0.9999] | 0.392 | [0.368, 0.415] |
| revised-30m | cr4 | 0.20 | $21981 | 2147 | 0.5634 | [0.6895, 1.0000] | 0.392 | [0.368, 0.415] |
| revised-30m | hhi | 0.20 | $21981 | 2147 | 1302.8 | [1652.9, 9997.9] | 0.392 | [0.368, 0.415] |
| revised-30m | top_1pct_share | 0.20 | $21981 | 2147 | 0.9811 | [0.9944, 1.0000] | 0.392 | [0.368, 0.415] |

Full detail (including per-threshold refit-failure counts) is in h1_evt_threshold_sensitivity.csv.

## Tail-fit parameter uncertainty

Unlike a version of this bootstrap that fits the GPD once and reuses that single (xi, sigma) pair for every replicate, this module refits (xi, sigma) by MLE on a bootstrap resample of the observed exceedances inside every replicate, so uncertainty in the tail-shape estimate itself is propagated into the reported interval and into the "implied Hill alpha (95% CI)" column above -- not just resampling variability in which observations appear. A refit that fails on a degenerate resample falls back to the primary fit rather than crashing the run; how often this happens is reported per row (n_tail_refit_failures / n_refit_failures in the CSVs) so it is visible, not silently absorbed.

## Calibration / backtest diagnostics

For each window, output/figures/evt_diagnostics_<window>.png contains three panels checking the threshold and GPD assumption empirically rather than by assertion: (1) a mean-excess plot across a grid of candidate thresholds -- a roughly linear/flat region around the chosen threshold supports the GPD approximation there; (2) a Hill-style tail-index stability plot tracing alpha_hat(k) over a wide range of top-k counts -- a reader can check directly whether "alpha ~= X" is a stable estimate or an artifact of one particular k; (3) a GPD QQ plot of the observed exceedances against the fitted GPD's theoretical quantiles at the primary threshold -- points close to the 45-degree line support the fit, systematic curvature would not.
- revised-24m: `output/figures/evt_diagnostics_revised-24m.png`
- revised-30m: `output/figures/evt_diagnostics_revised-30m.png`

