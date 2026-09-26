# H4 Protocol Heterogeneity Analysis

## Hypothesis

H4: "Sandwich activity differs systematically across DEX protocols: a small set of protocols hosts victim trades that are orders of magnitude larger than the market average ('whale pools'), concentrating the highest-stakes extraction."

## H4a — victim-trade scale and concentration (direct H4 evidence)

- Primary 24m sample contains 20 protocol families and 3,753,857 victim trades.
- The pooled victim-trade average is $7,332.08.
- The largest protocol-level average is fluid at $755,006.09, or 103.0x the pooled market average.
- 3 protocols have average victim trade size >=10x the pooled market average: fluid, maverick, curve.
- Protocol victim-volume concentration: CR1=72.01%, CR2=81.76%, CR4=93.47%, HHI=5370.5.

## 30m temporal robustness extension

- The 30m files are cross-reconciled against each other, but no independent hard-coded 30m victim-count acceptance total is enforced until equivalent upstream provenance is documented.
- The 30m extension contains 21 protocol families and 4,286,398 victim trades.
- The largest protocol-level average remains fluid at 93.5x the 30m pooled market average.
- 3 protocols remain at >=10x the pooled 30m average: fluid, maverick, curve.
- 30m concentration remains high descriptively: CR1=70.89%, CR2=81.54%, CR4=93.32%, HHI=5230.4.
- Across 20 protocols present in both files, 24m-vs-30m average-trade-size rank correlation is 0.980; this is descriptive because the windows overlap.

## H4b — detected sandwich-incidence heterogeneity (complementary evidence)

- Primary 24m model uses 8,391 genuine month × project × version × trade-size-bin cells and 24 calendar-month clusters.
- Q5e defines the denominator as all positive-USD Ethereum dex.trades events in the window. Therefore this model estimates detected sandwich incidence among candidate trades, not proven equal-coverage latent sandwich risk across Dune project labels.
- The grouped-binomial protocol model controls for month and trade-size bin. Its 24m month-clustered CR1 omnibus sensitivity statistic is F(19,23)=280.304. The corresponding approximate reference p-value is retained in the machine-readable diagnostics for transparency, but it is deliberately not printed here or used to decide whether H4 is statistically supported because only 24 independent monthly clusters support a high-dimensional protocol restriction block.
- The 30m model is a nested temporal robustness extension, not an independent replication.
- Candidate-only protocols with zero attacks are excluded from the unpenalized fixed-effect logit because of complete separation. Therefore the incidence model is explicitly outcome-conditioned: it estimates heterogeneity only among protocols with >=1 observed attacked event and is not a test across the full candidate-trade protocol universe. Full-universe zero-attack protocols remain visible in the descriptive prevalence tables.
- Pairwise protocol contrasts are exploratory effect-size comparisons with approximate month-clustered CR1 uncertainty and Holm multiplicity adjustment.
- The protocol × linear-calendar-time omnibus p-value is deliberately omitted because the interaction restriction block is too large relative to the number of independent monthly clusters.

## Where detected sandwich events occur most often and observable associated factors

- Most observed attacked events (24m): uniswap with 3,562,438 attacked events.
- Highest raw protocol detected sandwich rate (24m): solidly at 2.941% of observed positive-USD candidate DEX trades.
- Highest detected-attack concentration relative to candidate-trade exposure (24m): solidly with attack-share/candidate-share ratio 1.714; this is descriptive exposure normalization, not a significance or causal estimate.
- Highest descriptive model-adjusted protocol detected-sandwich probability point estimate (24m, among protocols with >=1 observed attack): dodo at 2.492%, standardized to the observed pooled month x trade-size-bin candidate distribution. This is a model-standardized prediction and may partly extrapolate to month x size cells not observed for that protocol; protocol-specific observed/extrapolated target-mass diagnostics are written to the adjusted-probability table.
- Highest raw trade-size-bin detected sandwich rate (24m): 06_2500_5000 at 2.725%.
- Highest raw monthly detected sandwich rate (24m): 2024-05 at 3.614%.
- These tables identify observable associations with protocol, protocol version, trade-size bin, and calendar month. They do not identify causal mechanisms such as liquidity design, routing, slippage settings, or bot strategy because Q5e does not contain those mechanism variables.

## Evidentiary hierarchy

- Primary H4 evidence: continuous protocol average victim-trade-size ratios to the pooled transaction-weighted market average, plus victim-volume CR1/CR2/CR4 and HHI.
- Complementary evidence: raw detected sandwich incidence, detected-attack concentration relative to candidate-trade exposure, and model-adjusted protocol attack probabilities controlling for month and trade-size bin.
- Robustness and diagnostics: 30m extension, covariance audit, pairwise contrasts, yearly/rank diagnostics, and within-protocol diagnostics.

## Evidentiary strength and limitations

- The aggregated files show large descriptive differences across protocol/project labels in average victim trade size and concentration of victim-side sandwich-associated trade volume; they do not identify individual liquidity pools.
- The continuous ratio to the pooled transaction-weighted market average is the main magnitude measure. The >=10x indicator is retained only because 10x corresponds to one order of magnitude in H4's wording; it carries no special inferential significance.
- The 30m extension tests whether the descriptive pattern remains over a longer window; it is not an independent replication because it contains the 24m period.
- A formal transaction-level protocol-effect test is unavailable from this aggregated file because within-protocol transaction-level variation has been discarded.
- Therefore this module deliberately does not report ANOVA/Kruskal-Wallis/regression p-values from protocol averages as though they were transaction-level evidence.
- Protocol-level victim trade volume is not the same quantity as attacker profit or victim loss, so 'highest-stakes extraction' should be interpreted as high victim-side sandwich-associated trade volume unless extraction/profit microdata are added.
- The data are aggregated by Dune project label; they do not identify heterogeneity among individual pools or protocol versions.

## Conclusion

The direct H4 evidence concerns victim-trade scale and concentration across protocol/project labels. The Q5e incidence analysis addresses the related but distinct estimand of detected sandwich incidence among positive-USD candidate DEX trades after conditioning on month and trade-size bin; it does not identify latent true sandwich risk if detection coverage differs across protocols/versions. The observed protocol/project aggregates show substantial descriptive heterogeneity in victim trade size and concentration of victim-side sandwich-associated trade volume; this is not evidence about individual liquidity pools. Because only 24 independent monthly clusters are available, the high-dimensional CR1 incidence omnibus p-value is retained only as an approximate sensitivity diagnostic and is not used as the decision rule for H4. The 30m results are nested robustness evidence, not an independent replication. Transaction-level inference about continuous victim-trade-size distributions, causal protocol mechanisms, and attacker extraction/profit is not available from these aggregated data.