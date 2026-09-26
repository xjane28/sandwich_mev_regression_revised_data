# H3 Hypothesis Testing

## Hypothesis

H3: "Extraction persists throughout 2024–2025 — occurring daily and continuing after major protocol upgrades — rather than being a transitory market failure."

## Primary persistence result

- Primary window: 2024-01-01 through 2025-12-31 (731 consecutive calendar days).
- Positive sandwich volume occurred on 731/731 days (100.00%).
- Positive sandwich trade count occurred on 731/731 days (100.00%).
- At least one observed sandwich bot was present on 731/731 days (100.00%).
- Minimum observed daily sandwich volume was $93,006,121.47; median was $276,314,339.63.
- Minimum daily sandwich trade count was 2,782; median was 8,284.

Persistence is a directly observed property of the complete daily series. No p-value or arbitrary minimum-volume cutoff is required to establish whether activity occurred every calendar day.

## Persistence after protocol upgrades

- Dencun (2024-03-13): positive volume on 659/659 observed days through 2025-12-31 (100.00%).
- Pectra (2025-05-07): positive volume on 239/239 observed days through 2025-12-31 (100.00%).

## Temporal evolution (primary 24m sample)

- log daily USD volume, Dencun primary step+slope joint HAC(14) Wald test: F(2,719)=2.235, raw p=0.1078, Holm-adjusted p=0.2156.
- log daily USD volume, Pectra primary step+slope joint HAC(14) Wald test: F(2,719)=9.950, raw p=5.465e-05, Holm-adjusted p=0.0001639.
- log daily trade count, Dencun primary step+slope joint HAC(14) Wald test: F(2,719)=14.030, raw p=1.053e-06, Holm-adjusted p=4.214e-06.
- log daily trade count, Pectra primary step+slope joint HAC(14) Wald test: F(2,719)=15.235, raw p=3.311e-07, Holm-adjusted p=1.655e-06.
- log daily unique bots, Dencun primary step+slope joint HAC(14) Wald test: F(2,719)=37.530, raw p=3.139e-16, Holm-adjusted p=1.883e-15.
- log daily unique bots, Pectra primary step+slope joint HAC(14) Wald test: F(2,719)=0.880, raw p=0.4151, Holm-adjusted p=0.4151.

## Additional formal temporal tests

- log daily USD volume, post_Dencun_pre_Pectra: resulting HAC(14) slope=0.000211; F(1,719)=0.474, raw p=0.4916, Holm-adjusted p=0.4916. This tests whether the resulting post-upgrade temporal slope equals zero.
- log daily USD volume, post_Pectra: resulting HAC(14) slope=-0.001606; F(1,719)=2.317, raw p=0.1284, Holm-adjusted p=0.2569. This tests whether the resulting post-upgrade temporal slope equals zero.
- log daily USD volume, overall secondary temporal evolution: HAC(14) omnibus F(5,719)=12.260, raw p=2.006e-11, Holm-adjusted p=1.003e-10. This jointly tests whether all five temporal terms are zero; rejection means at least one temporal component differs from zero, not that every component differs from zero.
- log daily trade count, post_Dencun_pre_Pectra: resulting HAC(14) slope=-0.003128; F(1,719)=69.028, raw p=4.825e-16, Holm-adjusted p=2.895e-15. This tests whether the resulting post-upgrade temporal slope equals zero.
- log daily trade count, post_Pectra: resulting HAC(14) slope=-0.003052; F(1,719)=36.094, raw p=2.987e-09, Holm-adjusted p=8.96e-09. This tests whether the resulting post-upgrade temporal slope equals zero.
- log daily trade count, overall secondary temporal evolution: HAC(14) omnibus F(5,719)=43.152, raw p=6.17e-39, Holm-adjusted p=4.936e-38. This jointly tests whether all five temporal terms are zero; rejection means at least one temporal component differs from zero, not that every component differs from zero.
- log daily unique bots, post_Dencun_pre_Pectra: resulting HAC(14) slope=-0.001699; F(1,719)=88.666, raw p=6.202e-20, Holm-adjusted p=4.341e-19. This tests whether the resulting post-upgrade temporal slope equals zero.
- log daily unique bots, post_Pectra: resulting HAC(14) slope=-0.001543; F(1,719)=37.663, raw p=1.389e-09, Holm-adjusted p=5.556e-09. This tests whether the resulting post-upgrade temporal slope equals zero.
- log daily unique bots, overall secondary temporal evolution: HAC(14) omnibus F(5,719)=187.202, raw p=1.505e-127, Holm-adjusted p=1.354e-126. This jointly tests whether all five temporal terms are zero; rejection means at least one temporal component differs from zero, not that every component differs from zero.

These additional tests are secondary formal HAC(14) tests derived from the same ITS model. They provide secondary temporal-association inference only, not causal upgrade effects. Holm adjustment is applied across this separate family of nine secondary formal tests.

These regressions establish temporal association/evolution in the observed series. Upgrade-date coefficients and joint tests are not interpreted causally because the design does not isolate upgrades from other contemporaneous market changes.

## Financial time-series diagnostics and robustness

- Residual ACF and Ljung-Box diagnostics are reported at 1, 7, 14, and 28 days for each primary HAC(14) ITS outcome. They are descriptive residual-dependence diagnostics; their p-values are not used as formal model-selection tests and do not determine the primary HAC bandwidth.
- A calendar-month-seasonality ITS is reported as a robustness specification to assess sensitivity to broader recurring calendar patterns.
- Poisson PPML with HAC(14) covariance is reported for sandwich trade counts and unique bot counts as count-data robustness. The primary specification remains log-OLS/HAC for comparability across outcomes.
- Log-model coefficient tables include exact percentage translations, 100*(exp(beta)-1), and transformed confidence intervals. Step terms are reported as level percentage changes; time and slope-change terms are reported as changes in the one-day multiplicative growth factor (percentage per day).

## Inferential assumptions and model validation

- HAC inference allows heteroskedasticity and serial correlation, but remains a large-sample approximation requiring sufficiently weak temporal dependence. It does not repair misspecification of the conditional mean or remove structural confounding.
- The segmented ITS is interpreted as a model for temporal association around the upgrade dates. Without a counterfactual/control series, its step and slope changes are not causal estimates of Dencun or Pectra.
- Persistence additionally relies on the underlying query/export representing every calendar day, including true zero-activity days, rather than omitting days without detected activity.
- Residual ACF and Ljung-Box results are summarized in h3_model_validation_summary.csv. Transparent descriptive flags identify large remaining dependence signals, but they do not change the HAC bandwidth, model, significance threshold, or test family.
- Model-validation diagnostic, log daily USD volume: status=strong_residual_dependence_signal; max |residual ACF| across lags 1/7/14/28=0.687; minimum Ljung-Box p across those reported lags=0. This is a diagnostic signal, not a formal validity verdict.
- Model-validation diagnostic, log daily trade count: status=strong_residual_dependence_signal; max |residual ACF| across lags 1/7/14/28=0.830; minimum Ljung-Box p across those reported lags=0. This is a diagnostic signal, not a formal validity verdict.
- Model-validation diagnostic, log daily unique bots: status=strong_residual_dependence_signal; max |residual ACF| across lags 1/7/14/28=0.526; minimum Ljung-Box p across those reported lags=4.121e-192. This is a diagnostic signal, not a formal validity verdict.

## 30m descriptive persistence extension

- The descriptive extension is identical to the primary data for 2024–2025 and continues through 2026-06-30.
- The interrupted-time-series regressions remain restricted to the primary 24m sample; the 30m file extends only the descriptive persistence assessment.
- Positive sandwich volume occurs on 912/912 days (100.00%) through 2026-06-30.
- Minimum daily volume in the 30m series is $66,699,541.16; minimum daily trade count is 2,027.
- This is a descriptive persistence extension of the 2024–2025 result.

## Evidentiary conclusion

- H3's persistence implication is evaluated directly from complete calendar coverage and daily positive activity.
- Primary upgrade-date interrupted-time-series models provide formal evidence about temporal evolution while allowing serial correlation in inference. HAC(14) is primary and HAC(7)/HAC(28) are lag-bandwidth robustness checks. The next-day upgrade boundary and quadratic-background-trend ITS specification are robustness diagnostics only. Holm adjustment controls multiplicity across the six primary HAC(14) upgrade joint tests.
- Inferential conclusions from the ITS are conditional on the stated mean-model and weak-dependence assumptions. Material residual-dependence flags should therefore be reported alongside, rather than used to silently replace, the primary specification.
- Continued activity after Dencun and Pectra establishes post-upgrade persistence in the observed data, but does not identify a causal upgrade effect or prove that upgrades could not have changed the level or trend of extraction.
- If the validated complete daily series has positive activity on every calendar day, the observed data establish daily persistence over the stated sample. The analysis does not by itself establish the broader welfare interpretation implied by the phrase 'market failure'.