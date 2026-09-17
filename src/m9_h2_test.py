"""
m4b_h2_test.py

ADDITIVE H2 ANALYSIS — does not modify existing analyses.

H2 in the manuscript:
    "Uninformed order flow (retail) will subsidize informed order flow
     (bots), creating a 'Lemons' problem."

WHAT THE AVAILABLE DATA CAN TEST
--------------------------------
1. Whether Dune-detected sandwich victimization varies with trade size.
2. Whether smaller-trade proxies are disproportionately represented among
   detected victims.
3. Whether the size/victimization relationship persists after controlling
   for month and DEX project/version.
4. Whether the result is robust to:
      a. a longer 30-month window; and
      b. excluding project/version groups in which no sandwich victim is
         ever detected.

WHAT THE AVAILABLE DATA CANNOT DIRECTLY TEST
--------------------------------------------
The exports do not contain realized counterfactual victim loss matched to
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
    - t reference distribution with G-1 cluster degrees of freedom.
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
Q5A_NAME = "query5a_break_points_v2.csv"

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

    g["ci95_low_pct"] = 100 * (center - half)
    g["ci95_high_pct"] = 100 * (center + half)
    g["sample"] = sample_name
    g["trade_size"] = g["trade_size_bin"].map(BIN_LABEL)

    return g


def fit_grouped_binomial_fe(df):
    """
    Grouped-binomial logit:
        attacked_g ~ Binomial(candidate_g, p_g)

        logit(p_g) =
            trade-size-bin FE + month FE + project/version FE

    Cluster-robust covariance is calculated from grouped-binomial score
    contributions:
        score_i = X_i * (y_i - n_i*p_i)
    """

    d = df.copy()

    formula = (
        "C(trade_size_bin, Treatment(reference='01_<100'))"
        " + C(month)"
        " + C(protocol_version)"
    )

    X = patsy.dmatrix(formula, d, return_type="dataframe")

    y = np.column_stack([
        d["attacked_trade_events"].to_numpy(dtype=float),
        d["unattacked_trade_events"].to_numpy(dtype=float),
    ])

    model = sm.GLM(y, X, family=sm.families.Binomial())
    res = model.fit(maxiter=200)

    beta = np.asarray(res.params)
    Xn = np.asarray(X, dtype=float)

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
            f"Only {G} clusters. Cluster-robust inference may be unstable."
        )

    meat = np.zeros((Xn.shape[1], Xn.shape[1]))
    for cl in unique_clusters:
        s = individual_score[clusters == cl].sum(axis=0)
        meat += np.outer(s, s)

    cov = bread_inv @ meat @ bread_inv

    N_cells = len(d)
    K = Xn.shape[1]
    if G > 1 and N_cells > K:
        correction = (G / (G - 1)) * ((N_cells - 1) / (N_cells - K))
        cov *= correction

    se = np.sqrt(np.maximum(np.diag(cov), 0))

    return {
        "result": res,
        "X": X,
        "data": d,
        "beta": beta,
        "cov": cov,
        "se": se,
        "clusters": G,
        "cluster_df": G - 1,
    }


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
        "p_value": np.nan,
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
        t_stat = est / se
        pval = 2 * stats.t.sf(abs(t_stat), df=df_t)

        rows.append({
            "sample": sample_name,
            "trade_size_bin": b,
            "trade_size": BIN_LABEL[b],
            "odds_ratio_vs_under_100": np.exp(est),
            "ci95_low": np.exp(est - crit*se),
            "ci95_high": np.exp(est + crit*se),
            "p_value": pval,
            "reference": False,
        })

    return pd.DataFrame(rows)


def joint_trade_size_wald(fit):
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
    }


def shape_diagnostics(desc):
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
    q5a = pd.read_csv(folder / Q5A_NAME)

    needed = {
        "victim_tier", "victim_trades", "total_volume",
        "avg_tx_size", "pct_of_trades", "pct_of_volume",
    }

    missing = needed - set(q5b.columns)
    if missing:
        raise ValueError(f"Q5b missing {sorted(missing)}")

    return q5b, q5a


def attacked_coverage_subset(df):
    """
    Coverage-conservative robustness only.

    Restricts to project/version combinations with at least one detected
    sandwich victim. This is not the primary specification because excluding
    zero-outcome protocols based on the outcome can induce selection.
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
        f"Joint trade-size Wald test: "
        f"F({joint24['df_num']}, {joint24['df_den']}) "
        f"= {joint24['F']:.3f}, p={joint24['p_value']:.4g}"
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
        "1. Strong evidence can be obtained about the association between "
        "trade size and Dune-detected sandwich victimization because Q5e "
        "contains both attacked and unattacked candidate trades."
    )

    if shape24["broad_inverted_u"] and shape30["broad_inverted_u"]:
        print(
            "2. The size relationship is nonlinear and robust across the "
            "24m and 30m windows: susceptibility is broadly hump-shaped "
            "(inverted-U), rather than monotonically decreasing with size."
        )
    else:
        print(
            "2. The relationship should be described from the estimated "
            "bin effects rather than assumed to be monotonic."
        )

    print(
        "3. Q5b provides strong descriptive evidence about the composition "
        "of already-detected victims, but this is conditional on attack and "
        "is not itself a susceptibility test."
    )
    print(
        "4. The available exports provide no direct identification of the "
        "dollar subsidy/wealth transfer from retail victims to bots because "
        "realized counterfactual victim loss and matched bot profit are not "
        "observed by victim tier."
    )
    print(
        "5. Trade size is a proxy for participant scale, not verified "
        "retail/institutional identity. Conclusions must therefore refer "
        "to smaller-trade or retail-proxy groups, not verified retail users."
    )

    print(
        "\nOVERALL: the data can strongly test an important observable "
        "implication of H2 (who is exposed/susceptible to detected sandwich "
        "attacks), but can provide only indirect evidence for the full H2 "
        "claim that retail order flow subsidizes bots. The full causal "
        "wealth-transfer/Lemons interpretation is not identified by these "
        "aggregate exports."
    )


def run_spec(df, label):
    desc = descriptive_rates(df, label)
    fit = fit_grouped_binomial_fe(df)
    effects = bin_effect_table(fit, label)
    joint = joint_trade_size_wald(fit)
    shape = shape_diagnostics(desc)
    return desc, fit, effects, joint, shape


def main():
    print("="*78)
    print("H2: RETAIL-PROXY / SANDWICH SUSCEPTIBILITY ANALYSIS")
    print("="*78)

    q24 = load_q5e(DATA_24)
    q30 = load_q5e(DATA_30)
    q5b24, q5a24 = load_victim_composition(DATA_24)

    desc24, fit24, eff24, joint24, shape24 = run_spec(
        q24, "24m_primary_all_project_versions"
    )

    desc30, fit30, eff30, joint30, shape30 = run_spec(
        q30, "30m_robustness_all_project_versions"
    )

    q24_cov = attacked_coverage_subset(q24)
    desc24_cov, fit24_cov, eff24_cov, joint24_cov, shape24_cov = run_spec(
        q24_cov, "24m_coverage_conservative"
    )

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
        {"sample": "24m_coverage_conservative", **joint24_cov},
    ])

    joint_df.to_csv(
        OUT / "table_h2_q5e_joint_tests.csv", index=False
    )

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
            "ci95_low", "ci95_high", "p_value",
        ]].to_string(index=False)
    )

    print("\nPRIMARY JOINT TEST")
    print(joint24)

    print("\n30-MONTH ROBUSTNESS JOINT TEST")
    print(joint30)

    print("\nCOVERAGE-CONSERVATIVE JOINT TEST")
    print(joint24_cov)

    evidence_assessment(
        desc24, fit24, joint24, shape24,
        desc30, fit30, joint30, shape30,
        q5b24,
    )

    print("\nSaved additive outputs:")
    print("  output/tables/table_h2_q5e_descriptive_rates.csv")
    print("  output/tables/table_h2_q5e_adjusted_odds_ratios.csv")
    print("  output/tables/table_h2_q5e_joint_tests.csv")


if __name__ == "__main__":
    main()
