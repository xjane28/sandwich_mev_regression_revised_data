# Minimum Detectable Effect (MDE) / Power Diagnostic

This is a standalone, additive diagnostic requested during statistical review. It does not change any existing hypothesis-test result, conclusion, or p-value. It recomputes, from already-fitted and already-committed standard errors / t-statistics / degrees of freedom, the smallest true effect each test could have detected 80% of the time (conventional power target), both at the raw alpha=0.05 and at an illustrative Bonferroni-equivalent alpha reflecting each table's own stated correction family.

Method: MDE = SE * (t_crit(1-alpha/2, df) + t_crit(power, df)) -- the standard classical two-sided MDE approximation (Cohen 1988; Duflo/Glennerster/Kremer 2007). Percent columns use 100*(exp(MDE)-1), the standard log-scale-to-percent translation already used elsewhere in this project's own tables.

Scope: covers m10 (H3 HAC-ITS coefficients), m9b (H2 grouped-binomial bin contrasts), and m11 (H4 protocol pairwise contrasts). m9a's e-value/Hoeffding tests are excluded -- they are not classical t-tests, so a t-based MDE formula does not apply to them, and forcing it would itself be a statistical error. Joint/omnibus F-tests (e.g. the primary Dencun/Pectra step+slope Wald tests, the H4 incidence omnibus) are also excluded, because a joint-restriction MDE needs a noncentral-F power calculation with extra assumptions about how the true effect is distributed across restrictions; the per-coefficient MDEs below are a reasonable, defensible lower bound on what those joint tests could detect, not a substitute for them.

## m10_h3 (HAC(14) ITS, primary 24m)

n = 15 coefficients/contrasts. df range: 719-719.

- Most sensitive (smallest raw MDE): `S_pectra` (log daily unique bots) -- MDE ~ +0.09% at alpha=0.05, df=719.
- Least sensitive (largest raw MDE): `D_pectra` (log daily USD volume) -- MDE ~ +74.71% at alpha=0.05, df=719.
- Under the stated correction family (size=6, alpha_corrected~8.33e-03), the least-sensitive MDE widens to ~+100.10% (`D_pectra`, log daily USD volume).

## m9b_h2 (grouped-binomial, CR1 cluster-robust, primary 24m)

n = 10 coefficients/contrasts. df range: 58-58.

- Most sensitive (smallest raw MDE): `<$100 vs $100–250` (24m_primary_all_project_versions) -- MDE ~ +23.51% at alpha=0.05, df=58.
- Least sensitive (largest raw MDE): `<$100 vs $50k–100k` (24m_primary_all_project_versions) -- MDE ~ +117.92% at alpha=0.05, df=58.
- Under the stated correction family (size=10, alpha_corrected~5.00e-03), the least-sensitive MDE widens to ~+179.98% (`<$100 vs $50k–100k`, 24m_primary_all_project_versions).

## m11_h4 (grouped-binomial protocol incidence, CR1, month-clustered, 24m)

n = 190 coefficients/contrasts. df range: 23-23.

- Most sensitive (smallest raw MDE): `pairwise log-odds contrast` (balancer vs pancakeswap) -- MDE ~ +17.00% at alpha=0.05, df=23.
- Least sensitive (largest raw MDE): `pairwise log-odds contrast` (apeswap vs kyberswap) -- MDE ~ +4275.81% at alpha=0.05, df=23.
- Under the stated correction family (size=190, alpha_corrected~2.63e-04), the least-sensitive MDE widens to ~+78484.58% (`pairwise log-odds contrast`, apeswap vs kyberswap).

## Reading this in plain terms

- m10 (H3, n=731 days, df=719): the largest per-coefficient sample in the project. MDEs here are the tightest (smallest detectable effect), consistent with it being the best-powered module.
- m9b (H2, df=58, i.e. ~60 project/version clusters): MDEs are wider than m10's but still allow detecting effects on the order of a few percent to a few tens of percent, consistent with H2's 10/10 significant contrasts even after Holm correction.
- m11 (H4, df=23, i.e. 24 monthly clusters): this is the thinnest cluster count of the three, so its MDEs are the widest -- some pairwise contrasts can only reliably detect very large true differences. This is the same few-cluster limitation m11's own report already flags qualitatively (it deliberately withholds omnibus p-values for this reason); this diagnostic just gives that limitation a concrete number instead of leaving it as a general caveat.

This file is descriptive/diagnostic only. It does not overturn or reinterpret any existing significance conclusion -- effects that were already found significant remain significant; this only characterizes how small a true effect could still have been missed.
