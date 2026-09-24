"""H2-related observed attack incidence: matched project/version/month analysis.

H2 unchanged: Uninformed order flow (retail) will subsidize informed order flow
(bots), creating a 'Lemons' problem.

Run: python h2_analysis.py --root /path/to/project

This file does not generate a direct p-value or acceptance/rejection decision for H2:
the supplied aggregate exports do not identify its transfer/information mechanism.
It explicitly records that identification result instead of substituting a size
heterogeneity test for H2. No data or evidence is manufactured.

Main question: within the same project/version and month, how does each larger
trade-size bin differ in observed attack rate from trades under $100?

Retained: validation of existing exports, observed counts/rates/notional,
calendar-window comparisons, project concentration, and victim-tier context.
Related conditional monthly hypotheses are tested with fixed-stake e-tests.
These are conditional tests of related observable implications, not direct tests of H2.
The assumption-light track uses no fitted model; a separate conventional grouped-binomial
fixed-effects track is estimated in m9b_h2_test.py from the same observed query cells and
cross-referenced here rather than re-estimated. No generated
observations, simulation, resampling or imputation are used.
All empirical inputs must be existing CSV exports inside ROOT/fetch.
Missing evidence is reported rather than filled in or inferred.

Dependencies: Python 3.10+, numpy, pandas. Actual versions are recorded per run.
Standalone; no project Python imports.
"""
from pathlib import Path
from decimal import Decimal, InvalidOperation
from datetime import datetime, timezone
import argparse
import hashlib
import importlib.metadata
import json
import platform
import warnings
import numpy as np
import pandas as pd

Q5E_NAME = "query5e_eligible_trade_attack_rates_v2.csv"
Q5B_NAME = "query5b_victim_impact_v2.csv"
BIN_ORDER = [
    "01_<100", "02_100_250", "03_250_500", "04_500_1000",
    "05_1000_2500", "06_2500_5000", "07_5000_10000",
    "08_10000_25000", "09_25000_50000", "10_50000_100000",
    "11_100000_plus",
]
BIN_LABEL = dict(zip(BIN_ORDER, [
    "<$100", "$100–250", "$250–500", "$500–1k", "$1k–2.5k",
    "$2.5k–5k", "$5k–10k", "$10k–25k", "$25k–50k", "$50k–100k", "≥$100k",
]))
KEY = ["month", "project", "version", "trade_size_bin"]
COUNTS = ["candidate_trade_events", "attacked_trade_events", "unattacked_trade_events"]
VOLUMES = ["candidate_volume_usd", "attacked_volume_usd"]
MAX_EXACT_COUNT = 2**53 - 1
ALPHA = 0.05
BET_STAKE = 0.5
TEST_FAMILY_SIZE = 80  # 10 bins x 2 directions x 2 targets x 2 windows


class DataValidationError(ValueError):
    """Expected input failure; report without hiding programming errors."""

def require(condition, message):
    if not condition:
        raise DataValidationError(message)

def rounding_allowance(decimals):
    if not isinstance(decimals, int) or not 0 <= decimals <= 12:
        raise ValueError("Export decimal places must be an integer from 0 to 12.")
    return 0.5 * 10.0**(-decimals)

def clean_keys(df, columns):
    for c in columns:
        require(df[c].notna().all(), f"Missing {c}.")
        df[c] = df[c].astype(str).str.strip()
        require(df[c].ne("").all(), f"Blank {c}.")

def read_export(path):
    try:
        return pd.read_csv(path, dtype=str)
    except (pd.errors.EmptyDataError, pd.errors.ParserError, UnicodeError) as exc:
        raise DataValidationError(f"{path}: empty, malformed, or undecodable CSV.") from exc

def integer_counts(series, name):
    """Validate original decimal values before integer conversion."""
    values = []
    for raw in series:
        try:
            x = Decimal(str(raw))
        except InvalidOperation as exc:
            raise DataValidationError(f"{name}: invalid count {raw!r}.") from exc
        require(x.is_finite() and x >= 0, f"{name}: counts must be finite/nonnegative.")
        require(x == x.to_integral_value(), f"{name}: fractional count {raw!r}.")
        require(x <= MAX_EXACT_COUNT, f"{name}: count exceeds exact float64 integer range.")
        values.append(int(x))
    # Also prevent overflow/precision loss during aggregation.
    require(sum(values) <= MAX_EXACT_COUNT, f"{name}: total exceeds exact integer range.")
    return pd.Series(values, index=series.index, dtype="int64")

def nonnegative_numeric(series, name):
    try:
        x = pd.to_numeric(series, errors="raise").astype(float)
    except (ValueError, TypeError) as exc:
        raise DataValidationError(f"{name}: invalid numeric value.") from exc
    require(np.isfinite(x).all() and (x >= 0).all(), f"{name}: non-finite/negative value.")
    return x

def validate_bins(df):
    observed = set(df["trade_size_bin"].dropna().astype(str))
    require(observed == set(BIN_ORDER),
            f"Planned bins missing={sorted(set(BIN_ORDER)-observed)}, "
            f"unexpected={sorted(observed-set(BIN_ORDER))}.")

def load_q5e(folder, *, rate_decimals=4, check_volume_subset=False, money_decimals=2):
    path = Path(folder) / Q5E_NAME
    df = read_export(path)
    required = set(KEY + COUNTS + VOLUMES)
    require(required <= set(df), f"{path}: missing columns {sorted(required-set(df))}.")
    require(not df.empty, f"{path}: empty export.")
    clean_keys(df, KEY)
    try:
        dates = pd.to_datetime(df["month"], utc=True, errors="raise")
    except (ValueError, TypeError) as exc:
        raise DataValidationError(f"{path}: invalid month.") from exc
    require(dates.notna().all(), f"{path}: missing month.")
    df["month"] = dates.dt.strftime("%Y-%m")
    for c in COUNTS:
        df[c] = integer_counts(df[c], c)
    for c in VOLUMES:
        df[c] = nonnegative_numeric(df[c], c)
    require((df[COUNTS[0]] > 0).all(), "Q5e candidate counts must be positive.")
    # Subtraction avoids integer overflow on malformed attacked+unattacked values.
    require((df[COUNTS[1]] <= df[COUNTS[0]]).all(), "Attacked count exceeds candidate.")
    require((df[COUNTS[0]] - df[COUNTS[1]] == df[COUNTS[2]]).all(),
            "Q5e candidate != attacked + unattacked.")
    rate = 100.0 * df[COUNTS[1]] / df[COUNTS[0]]
    if "attack_rate_pct" in df:
        exported = nonnegative_numeric(df["attack_rate_pct"], "attack_rate_pct")
        require((exported <= 100).all(), "Q5e percentage exceeds 100.")
        require(np.allclose(exported, rate, rtol=1e-12,
                            atol=rounding_allowance(rate_decimals)),
                "Q5e exported rates disagree with counts at configured export precision.")
    df["attack_rate_pct"] = rate
    if check_volume_subset:
        excess = df[VOLUMES[1]] - df[VOLUMES[0]]
        tol = 2 * rounding_allowance(money_decimals) + 1e-12 * df[VOLUMES[0]]
        require((excess <= tol).all(), "Attacked volume exceeds candidate volume.")
    require(not df.duplicated(KEY).any(), "Duplicate Q5e month/project/version/bin cells.")
    validate_bins(df)
    df["trade_size_bin"] = pd.Categorical(df["trade_size_bin"], BIN_ORDER, ordered=True)
    # JSON tuples avoid delimiter collisions between project and version strings.
    df["protocol_version"] = [
        json.dumps([p, v], ensure_ascii=False) for p, v in zip(df["project"], df["version"])
    ]
    return df

def validate_window(df, *, start=None, end=None, count=None):
    months = pd.PeriodIndex(sorted(df["month"].unique()), freq="M")
    require(len(months) > 0, "Empty month window.")
    try:
        first = pd.Period(start, freq="M") if start is not None else months.min()
        last = pd.Period(end, freq="M") if end is not None else months.max()
    except (ValueError, TypeError) as exc:
        raise DataValidationError(f"Invalid calendar window: {exc}") from exc
    require(first <= last, f"Window start {first} is after window end {last}.")
    expected = pd.period_range(first, last, freq="M")
    require(months.equals(expected), f"Unexpected calendar window; expected "
            f"{expected[0]} through {expected[-1]}, without missing/extra months.")
    if count is not None:
        require(len(months) == count, f"Expected {count} months; got {len(months)}.")
    return months

def validate_overlap(primary, longer, money_decimals=2):
    require(set(primary["month"]) <= set(longer["month"]),
            "Longer window does not contain every primary month.")
    common = longer[longer["month"].isin(primary["month"])]
    a = primary.set_index(KEY).sort_index()
    b = common.set_index(KEY).sort_index()
    require(a.index.equals(b.index), "Common-window cells differ between Q5e exports.")
    require(np.array_equal(a[COUNTS].to_numpy(), b[COUNTS].to_numpy()),
            "Common-window counts differ between Q5e exports.")
    require(np.allclose(a[VOLUMES], b[VOLUMES], rtol=1e-12,
                        atol=2*rounding_allowance(money_decimals)),
            "Common-window volumes differ between Q5e exports.")

def load_victim_composition(folder, *, pct_decimals=2, money_decimals=2,
                            complete=True, check_average=False):
    df = read_export(Path(folder) / Q5B_NAME)
    numeric = ["victim_trades", "total_volume", "avg_tx_size", "pct_of_trades", "pct_of_volume"]
    require(set(["victim_tier"] + numeric) <= set(df), "Q5b missing required columns.")
    require(not df.empty, "Q5b is empty.")
    clean_keys(df, ["victim_tier"])
    require(not df["victim_tier"].duplicated().any(), "Duplicate Q5b victim tiers.")
    df["victim_trades"] = integer_counts(df["victim_trades"], "victim_trades")
    for c in numeric[1:]:
        df[c] = nonnegative_numeric(df[c], c)
    pct_tol = rounding_allowance(pct_decimals)
    for pct, value in [("pct_of_trades", "victim_trades"), ("pct_of_volume", "total_volume")]:
        require((df[pct] <= 100).all(), f"Q5b {pct} exceeds 100.")
        total = float(df[value].sum())
        require(np.isfinite(total) and total > 0, f"Q5b {value} has no positive finite total.")
        if complete:
            require(np.allclose(df[pct], 100*df[value]/total, atol=pct_tol, rtol=1e-12),
                    f"Q5b {pct} disagrees with {value}; check export precision/completeness.")
        else:
            # A subset cannot be reconciled to its own denominator as if exhaustive.
            require(float(df[pct].sum()) <= 100 + len(df)*pct_tol, f"Q5b {pct} exceeds 100 total.")
            warnings.warn(f"Q5b incomplete: {pct} cannot be reconciled without full denominator.")
    zero = df["victim_trades"].eq(0)
    require((df.loc[zero, "total_volume"] == 0).all(), "Q5b zero trades with positive volume.")
    if check_average:
        positive = ~zero
        expected = df.loc[positive, "total_volume"]/df.loc[positive, "victim_trades"]
        tol = rounding_allowance(money_decimals)*(1 + 1/df.loc[positive, "victim_trades"])
        require((abs(df.loc[positive, "avg_tx_size"]-expected) <= tol + 1e-12*expected).all(),
                "Q5b average size disagrees with total volume / victim count.")
        require((df.loc[zero, "avg_tx_size"] == 0).all(), "Q5b nonzero average for zero trades.")
    else:
        # This column is neither used nor reported without verified denominator semantics.
        df = df.drop(columns="avg_tx_size")
    return df

def descriptive_rates(df, sample_name):
    validate_bins(df)
    g = df.groupby("trade_size_bin", observed=False).agg(
        candidate_trades=(COUNTS[0], "sum"), attacked_trades=(COUNTS[1], "sum"),
        unattacked_trades=(COUNTS[2], "sum"),
        candidate_volume_usd=(VOLUMES[0], "sum"), attacked_volume_usd=(VOLUMES[1], "sum"),
    ).reset_index()
    require(np.isfinite(g.iloc[:, 1:].to_numpy(dtype=float)).all(), "Non-finite aggregates.")
    require((g["candidate_trades"] > 0).all(), "Missing positive bin denominator.")
    n = g["candidate_trades"].to_numpy(dtype=float)
    p = g["attacked_trades"].to_numpy(dtype=float)/n
    g["attack_rate"], g["attack_rate_pct"] = p, 100*p
    g["interval_scope"] = "none; observed rates only; independent-trial Wilson intervals omitted"
    g["sample"] = sample_name
    g["trade_size"] = g["trade_size_bin"].map(BIN_LABEL)
    return g

def shape_diagnostics(desc):
    require(not desc["trade_size_bin"].duplicated().any(), "Duplicate shape bins.")
    d = desc.set_index("trade_size_bin").reindex(BIN_ORDER)
    rates = d["attack_rate"].to_numpy(dtype=float)
    require(np.isfinite(rates).all() and ((rates >= 0)&(rates <= 1)).all(),
            "Shape summary requires all eleven valid rates.")
    peaks = np.flatnonzero(rates == rates.max())
    return {
        "lowest_bin": ",".join(d.iloc[np.flatnonzero(rates == rates.min())]["trade_size"]),
        "lowest_rate_pct": 100*rates.min(),
        "peak_bin": ",".join(d.iloc[peaks]["trade_size"]),
        "peak_rate_pct": 100*rates.max(),
        "largest_bin_rate_pct": 100*rates[-1],
        "peak_is_interior": bool(np.all((peaks > 0)&(peaks < len(rates)-1))),
        "peak_tied": len(peaks) > 1,
        "adjacent_change_signs": ",".join(
            "increase" if x > 0 else "decrease" if x < 0 else "flat" for x in np.diff(rates)),
    }

def add_input_options(parser):
    parser.add_argument("--data-24", type=Path, help="Primary folder inside ROOT/fetch; relative paths are relative to ROOT/fetch. Default: data/revised-24m.")
    parser.add_argument("--data-30", type=Path, help="Longer-window folder inside ROOT/fetch; relative paths are relative to ROOT/fetch. Default: data/revised-30m.")
    parser.add_argument("--primary-start", default="2024-01")
    parser.add_argument("--primary-end", default="2025-12")
    parser.add_argument("--robustness-start", help="Optional exact start of the 30-month window.")
    parser.add_argument("--robustness-end", help="Optional exact end of the 30-month window.")
    parser.add_argument("--rate-decimals", type=int, default=4)
    parser.add_argument("--q5b-pct-decimals", type=int, default=2)
    parser.add_argument("--money-decimals", type=int, default=2)
    parser.add_argument("--check-volume-subset", action="store_true",
                        help="Require matching candidate/attacked valuation definitions.")
    parser.add_argument("--check-q5b-average", action="store_true",
                        help="Validate Q5b average against volume/victim count.")
    parser.add_argument("--q5b-incomplete", action="store_true",
                        help="Allow incomplete Q5b tiers; no within-export share reconciliation.")

def validate_options(args):
    for value in [args.rate_decimals, args.q5b_pct_decimals, args.money_decimals]:
        rounding_allowance(value)
    primary = pd.period_range(args.primary_start, args.primary_end, freq="M")
    require(len(primary) == 24, "Primary window must contain exactly 24 consecutive months.")
    if args.robustness_start and args.robustness_end:
        require(len(pd.period_range(args.robustness_start, args.robustness_end, freq="M")) == 30,
                "Robustness window must contain exactly 30 consecutive months.")
    return args



def fetch_path(root, path):
    """Reject traversal and symlinks that route inputs outside project/fetch."""
    fetch = Path(root).resolve() / 'fetch'
    require(fetch.is_dir(), f'Missing project fetch folder: {fetch}')
    require(fetch.resolve() == fetch, 'The fetch folder must not link outside the project fetch path.')
    resolved = Path(path).resolve()
    require(resolved.is_relative_to(fetch), f'Input must be inside {fetch}: {path}')
    return resolved


def export_folder(root, window, options):
    override = options.data_24 if window == "24m" else options.data_30
    folder = Path(override) if override is not None else Path('data') / f'revised-{window}'
    if not folder.is_absolute():
        folder = Path(root) / 'fetch' / folder
    folder = fetch_path(root, folder)
    for name in [Q5E_NAME, Q5B_NAME]:
        fetch_path(root, folder / name)
    return folder

def load_analysis_window(root, window, options):
    d = load_q5e(export_folder(root, window, options), rate_decimals=options.rate_decimals,
                 check_volume_subset=options.check_volume_subset, money_decimals=options.money_decimals)
    start, end = ((options.primary_start, options.primary_end) if window == "24m" else
                  (options.robustness_start, options.robustness_end))
    validate_window(d, start=start, end=end, count=int(window[:-1]))
    return d

HYPOTHESIS = "Uninformed order flow (retail) will subsidize informed order flow (bots), creating a 'Lemons' problem."


def formal_evidence_map():
    """Identification assessment, not an invented test or a p-value."""
    return pd.DataFrame([
        dict(component='Retail/informed participant classification',
             target='Identify information status and retail/bot roles independently of outcomes.',
             formal_requirement='Operational definitions and validated classification are required before a transfer test.',
             available='Trade-size bins; victim quantile tiers; some bot-address labels in other exports.',
             missing='Verified information status and defensible retail identity; a small trade is not a verified retail trader.',
             assessment='not_identified'),
        dict(component='Retail-to-informed-bot subsidy',
             target='Positive attributable monetary transfer from identified retail participants to identified informed bots, under a specified execution counterfactual and cost convention.',
             formal_requirement='Once identified: H0 tau <= 0 versus H1 tau > 0, where tau is the predeclared average attributable transfer per eligible retail event.',
             available='Candidate/attacked counts and traded USD notional; bot traded notional in other exports.',
             missing='Matched loss/transfer and bot proceeds with gas, fees, inventory and counterfactual execution accounted for. Notional volume is neither loss nor profit.',
             assessment='not_identified_no_valid_H2_p_value'),
        dict(component='Lemons mechanism',
             target='Information asymmetry causes adverse selection with a specified participation/composition or market-quality consequence.',
             formal_requirement='Predeclare a measurable adverse-selection outcome and identify its counterfactual change. Positive bot gains alone are insufficient.',
             available='Aggregated attack incidence and trade-size composition.',
             missing='Identified information asymmetry, mechanism-linked outcome and defensible comparison/counterfactual.',
             assessment='not_identified'),
        dict(component='Related size-susceptibility association',
             target='Observed attacked-event counts divided by eligible-event counts in each fixed trade-size bin.',
             formal_requirement='Monthly conditional mean/order nulls have finite-sample e-tests; these differ from an unconditional population association.',
             available='Q5e cell counts, exposures, month and project/version labels.',
             missing='Direct H2 measurements and causal identification; conditional-null tests do not supply these.',
             assessment='observed_descriptions_and_exploratory_conditional_tests'),
    ])


def monthly_conditional_tests(df, window):
    """Finite-sample tests of strong, explicitly conditional monthly nulls.

    For signed bounded X_t in [-1,1], H0 is E[X_t | F_(t-1)] <= 0
    at EVERY t, where F_(t-1) contains previous monthly observations.
    L_t = product(1 + 0.5 X_s) is nonnegative and
    E[L_t | F_(t-1)] <= L_(t-1). Thus E[L_T] <= 1 and
    min(1, 1/L_T) is a valid fixed-terminal p-bound by the Markov inequality.
    Bonferroni over 80 fixed tests allows arbitrary dependence among tests.
    This is not valid for the weaker null of a nonpositive overall mean alone.
    Sign-score tests concern conditional ordering, NOT effect magnitude.
    No asymptotic reference distribution or simulated calibration is used.
    """
    grouped = df.groupby(['month','trade_size_bin'], observed=True)[COUNTS[:2]].sum()
    months = sorted(df.month.unique())
    audit=[]; results=[]
    for b in BIN_ORDER[1:]:
        differences=[]; signs=[]
        for month in months:
            require((month,b) in grouped.index and (month,BIN_ORDER[0]) in grouped.index,
                    f'Missing monthly comparison denominator: {month}, {b}; no imputation.')
            n,a = map(int,grouped.loc[(month,b),COUNTS[:2]])
            n0,a0 = map(int,grouped.loc[(month,BIN_ORDER[0]),COUNTS[:2]])
            require(n>0 and n0>0,'Monthly denominators must be positive.')
            # Python integers prevent overflow and classify exact ties correctly.
            numerator=a*n0-a0*n
            difference=numerator/(n*n0)
            sign=(numerator>0)-(numerator<0)
            differences.append(difference);signs.append(sign)
            audit.append(dict(window=window,month=month,trade_size_bin=b,
                reference_bin=BIN_ORDER[0],candidate_events=n,attacked_events=a,
                reference_candidate_events=n0,reference_attacked_events=a0,
                rate=a/n,reference_rate=a0/n0,difference_pp=100*difference,
                exact_rate_order=sign))
        for target,values in [('conditional_mean_rate_difference',differences),
                              ('conditional_monthly_ordering',signs)]:
            for direction,orientation in [('larger_bin_higher',1),('larger_bin_lower',-1)]:
                x=orientation*np.asarray(values,dtype=float)
                require(np.isfinite(x).all() and (abs(x)<=1).all(),'Invalid bounded test score.')
                log_e=float(np.log1p(BET_STAKE*x).sum())
                p_bound=float(np.exp(-max(0.,log_e)))
                adjusted=min(1.,TEST_FAMILY_SIZE*p_bound)
                null=('E[direction * (rate_bin,t - rate_reference,t) | past monthly data] <= 0 at every month'
                      if target=='conditional_mean_rate_difference' else
                      'P(direction * rate_difference_t > 0 | past) <= P(direction * rate_difference_t < 0 | past) at every month')
                results.append(dict(window=window,trade_size_bin=b,reference_bin=BIN_ORDER[0],
                    target=target,direction=direction,null_hypothesis=null,
                    months=len(months),months_higher=sum(v>0 for v in signs),
                    months_lower=sum(v<0 for v in signs),months_tied=sum(v==0 for v in signs),
                    mean_monthly_difference_pp=100*float(np.mean(differences)),
                    fixed_stake=BET_STAKE,log_e_value=log_e,e_value=float(np.exp(log_e)),
                    p_value_bound=p_bound,bonferroni_p_value_bound=adjusted,
                    family_size=TEST_FAMILY_SIZE,alpha=ALPHA,
                    reject_conditional_null=bool(adjusted<=ALPHA),
                    decision='reject_stated_conditional_null' if adjusted<=ALPHA else 'do_not_reject_not_evidence_of_equality',
                    analysis_role='conditional_observable_implication_analysis',
                    direct_H2_test=False))
    return pd.DataFrame(results),pd.DataFrame(audit)


def composition_sensitivity(primary, datasets):
    """Observed common-cell comparisons; no fitted values or inferential claims.

    Choose the largest project by primary-window eligible count, without attack
    outcomes. Freeze that project for both windows. Two standardizations:
    overlap-exposure weights n0*n1/(n0+n1), applied to BOTH bin rates;
    equal projects, with equal versions within each project-month.
    Summary months receive equal weight. These are different estimands.
    """
    totals=primary.groupby('project',observed=True)[COUNTS[0]].sum()
    largest=sorted(totals[totals==totals.max()].index)[0]
    details=[];monthly=[];coverage=[];summary=[];projects=[];checks=[]
    for window,original in datasets.items():
        for scope in ['all_projects','exclude_primary_dominant_project']:
            d=original if scope=='all_projects' else original[original.project!=largest]
            if d.empty:
                checks.append(dict(window=window,scope=scope,
                    status='unavailable: no observations remain after project exclusion'))
                continue
            keys=['month','project','version']
            ref=d[d.trade_size_bin==BIN_ORDER[0]][keys+COUNTS[:2]].rename(
                columns={COUNTS[0]:'n_reference',COUNTS[1]:'a_reference'})
            for b in BIN_ORDER[1:]:
                other=d[d.trade_size_bin==b][keys+COUNTS[:2]].rename(
                    columns={COUNTS[0]:'n_bin',COUNTS[1]:'a_bin'})
                pair=other.merge(ref,on=keys,how='inner',validate='one_to_one')
                base=dict(window=window,scope=scope,trade_size_bin=b,
                          excluded_project=largest if scope!='all_projects' else '')
                coverage.append(dict(**base,matched_cells=len(pair),
                    bin_candidate_coverage=float(pair.n_bin.sum()/other.n_bin.sum()) if len(other) else np.nan,
                    reference_candidate_coverage=float(pair.n_reference.sum()/ref.n_reference.sum()) if len(ref) else np.nan,
                    interpretation='unmatched_strata_excluded_not_imputed'))
                missing=sorted(set(d.month)-set(pair.month))
                checks.append(dict(**base,status=('unavailable: no matched cells' if pair.empty else
                    'partial: missing matched months '+','.join(missing) if missing else 'completed')))
                if pair.empty:continue
                pair['rate_bin']=pair.a_bin/pair.n_bin
                pair['rate_reference']=pair.a_reference/pair.n_reference
                pair['difference_pp']=100*(pair.rate_bin-pair.rate_reference)
                pair['overlap_weight']=1/(1/pair.n_bin+1/pair.n_reference)
                for k,v in base.items():pair[k]=v
                details.append(pair)
                for (month,project),g in pair.groupby(['month','project'],sort=True):
                    projects.append(dict(**base,month=month,project=project,
                        matched_versions=len(g),difference_pp=float(g.difference_pp.mean()),
                        interpretation='equal_matched_versions_within_project_month'))
                for month,g in pair.groupby('month',sort=True):
                    raw=d[d.month==month]
                    br=raw[raw.trade_size_bin==b];rr=raw[raw.trade_size_bin==BIN_ORDER[0]]
                    pooled=100*(br[COUNTS[1]].sum()/br[COUNTS[0]].sum()-rr[COUNTS[1]].sum()/rr[COUNTS[0]].sum())
                    matched_pooled=100*(g.a_bin.sum()/g.n_bin.sum()-g.a_reference.sum()/g.n_reference.sum())
                    for scheme in ['overlap_exposure','equal_project']:
                        if scheme=='overlap_exposure':
                            r1=float(np.average(g.rate_bin,weights=g.overlap_weight))
                            r0=float(np.average(g.rate_reference,weights=g.overlap_weight))
                        else:
                            equal=g.groupby('project')[['rate_bin','rate_reference']].mean().mean()
                            r1=float(equal.rate_bin);r0=float(equal.rate_reference)
                        monthly.append(dict(**base,month=month,weighting=scheme,
                            matched_projects=int(g.project.nunique()),matched_cells=len(g),
                            standardized_bin_rate_pct=100*r1,standardized_reference_rate_pct=100*r0,
                            standardized_difference_pp=100*(r1-r0),
                            pooled_difference_pp=float(pooled),matched_pooled_difference_pp=float(matched_pooled),
                            interpretation='observed_standardization_no_causal_or_significance_claim'))
    require(bool(monthly),'No matched comparisons available; no summary can be calculated.')
    m=pd.DataFrame(monthly)
    for key,g in m.groupby(['window','scope','trade_size_bin','weighting'],sort=True):
        window,scope,b,scheme=key
        x=g.standardized_difference_pp
        summary.append(dict(window=window,scope=scope,trade_size_bin=b,weighting=scheme,
            excluded_project=largest if scope!='all_projects' else '',months=len(g),
            mean_standardized_bin_rate_pct=float(g.standardized_bin_rate_pct.mean()),
            mean_standardized_reference_rate_pct=float(g.standardized_reference_rate_pct.mean()),
            equal_month_standardized_difference_pp=float(x.mean()),
            equal_month_pooled_difference_pp=float(g.pooled_difference_pp.mean()),
            equal_month_matched_pooled_difference_pp=float(g.matched_pooled_difference_pp.mean()),
            months_positive=int((x>0).sum()),months_negative=int((x<0).sum()),
            months_zero=int((x==0).sum()),observed_month_min_pp=float(x.min()),observed_month_max_pp=float(x.max()),
            inference_status='descriptive_sensitivity_not_a_hypothesis_test'))
    return dict(composition_status=pd.DataFrame(checks),composition_matched_cells=pd.concat(details,ignore_index=True),
        composition_monthly=m,composition_coverage=pd.DataFrame(coverage),
        composition_project_month=pd.DataFrame(projects),composition_summary=pd.DataFrame(summary),
        composition_design=pd.DataFrame([dict(dominant_project=largest,
            selection='largest_24m_candidate_count_not_selected_using_attack_outcomes_fixed_across_windows',
            primary_candidate_share=float(totals.max()/totals.sum()),
            formal_effect_size_test='not_performed',
            reason='No externally justified economically meaningful attack-rate threshold is supplied; observed standardized differences are reported without population confidence claims.',
            additional_validation='requires_additional_independent_observations_not_available_here',
            direct_subsidy_test='requires_missing_participant_transfer_and_mechanism_measurements')]))



def consistency_checks(tables):
    """Predefined calendar halves and project distributions; no independent-replication claim."""
    d=tables['composition_project_month'].copy()
    d['calendar_half']=d.month.str[:4]+'-H'+(((d.month.str[5:7].astype(int)-1)//6)+1).astype(str)
    keys=['window','scope','trade_size_bin']
    by_project=d.groupby(keys+['project'],as_index=False).agg(
        months=('month','nunique'),mean_difference_pp=('difference_pp','mean'),
        months_positive=('difference_pp',lambda x:int((x>0).sum())),
        months_negative=('difference_pp',lambda x:int((x<0).sum())),
        months_zero=('difference_pp',lambda x:int((x==0).sum())))
    rows=[]
    for key,g in by_project.groupby(keys):
        x=g.mean_difference_pp
        positive=x[x>0]
        rows.append(dict(zip(keys,key),projects=len(g),positive_projects=int((x>0).sum()),
            negative_projects=int((x<0).sum()),zero_projects=int((x==0).sum()),
            median_project_difference_pp=float(x.median()),min_project_difference_pp=float(x.min()),
            max_project_difference_pp=float(x.max()),min_observed_months=int(g.months.min()),
            max_observed_months=int(g.months.max()),
            largest_share_of_positive_project_mean_differences=float(positive.max()/positive.sum()) if len(positive) else np.nan,
            interpretation='equal_project_descriptive_distribution_unequal_month_coverage_not_population_inference'))
    m=tables['composition_monthly'].copy()
    m['calendar_half']=m.month.str[:4]+'-H'+(((m.month.str[5:7].astype(int)-1)//6)+1).astype(str)
    half=m.groupby(keys+['weighting','calendar_half'],as_index=False).agg(
        months=('month','nunique'),mean_difference_pp=('standardized_difference_pp','mean'),
        months_positive=('standardized_difference_pp',lambda x:int((x>0).sum())),
        months_negative=('standardized_difference_pp',lambda x:int((x<0).sum())))
    reversals=[]
    for key,g in m.groupby(keys+['weighting']):
        g=g.sort_values('month');sign=np.sign(g.standardized_difference_pp.to_numpy())
        # Consecutive nonzero signs; a zero is not itself a reversal.
        nz=sign[sign!=0]
        reversals.append(dict(zip(keys+['weighting'],key),
            observed_sign_reversals=int(np.sum(nz[1:]!=nz[:-1])),
            months_positive=int((sign>0).sum()),months_negative=int((sign<0).sum()),months_zero=int((sign==0).sum())))
    return dict(consistency_by_project=by_project,consistency_project_distribution=pd.DataFrame(rows),
                consistency_calendar_halves=half,consistency_monthly_reversals=pd.DataFrame(reversals))


def common_support_checks(primary,datasets):
    """Optional within-month all-bin comparison, with no survival requirement.

    Every window is selected separately using only its observed denominators.
    Entry, exit and intermittent activity are permitted. The main pairwise
    analysis retains still more observations and remains the primary comparison.
    """
    keys=['month','project','version'];output={};coverage=[];statuses=[]
    for window,d in datasets.items():
        counts=d.groupby(keys,observed=True).trade_size_bin.nunique()
        keep=counts[counts==len(BIN_ORDER)].reset_index()[keys]
        sub=d.merge(keep,on=keys,how='inner',validate='many_to_one')
        for b in BIN_ORDER:
            whole=d[d.trade_size_bin==b];part=sub[sub.trade_size_bin==b]
            coverage.append(dict(restriction='common_bins',window=window,trade_size_bin=b,
                retained_candidates=int(part[COUNTS[0]].sum()),total_candidates=int(whole[COUNTS[0]].sum()),
                retained_candidate_share=float(part[COUNTS[0]].sum()/whole[COUNTS[0]].sum()) if whole[COUNTS[0]].sum()>0 else np.nan,
                retained_projects=int(part.project.nunique()),retained_months=int(part.month.nunique())))
        if sub.empty:
            statuses.append(dict(window=window,restriction='common_bins',status='unavailable: no within-month all-bin cells'));continue
        try:
            result=composition_sensitivity(primary,{window:sub})
        except DataValidationError as exc:
            statuses.append(dict(window=window,restriction='common_bins',status='failed: '+str(exc)));continue
        for name,frame in result.items():
            if name in ['composition_summary','composition_monthly','composition_coverage','composition_status']:
                frame=frame.copy();frame['restriction']='common_bins'
                dest='support_'+name.removeprefix('composition_')
                if dest=='support_status':dest='support_comparison_status'
                output[dest]=pd.concat([output.get(dest,pd.DataFrame()),frame],ignore_index=True)
        missing=sorted(set(d.month)-set(sub.month))
        statuses.append(dict(window=window,restriction='common_bins',
            status='partial: no comparable cells in '+','.join(missing) if missing else 'completed'))
    output['support_source_coverage']=pd.DataFrame(coverage)
    output['support_status']=pd.DataFrame(statuses)
    return output


def result_status_records(name, result):
    """Propagate nested check outcomes; successful computation is not a passed check."""
    records=[]
    if isinstance(result,dict):
        for key,frame in result.items():
            if key.endswith('_status') and isinstance(frame,pd.DataFrame) and 'status' in frame:
                for index,row in enumerate(frame.to_dict('records')):
                    labels=[str(row[x]) for x in ['window','scope','trade_size_bin','restriction'] if x in row]
                    records.append(dict(analysis=name+'/'+key+'/'+('/'.join(labels) or str(index)),status=str(row['status'])))
    ok=all(r['status']=='completed' for r in records)
    return [dict(analysis=name,status='completed' if ok else 'completed_with_issues')]+records


def overall_status(statuses):
    return 'completed' if statuses and all(r['status']=='completed' for r in statuses) else 'completed_with_issues'


def measurement_quality(folder,window,observed):
    path=folder/'query0a_data_quality.csv'
    d=read_export(path)
    require({'metric','value'}<=set(d),'Quality export missing metric/value.')
    clean_keys(d,['metric'])
    require(not d.metric.duplicated().any(),'Duplicate quality metrics.')
    d['value']=nonnegative_numeric(d.value,'quality metric')
    d['window']=window
    d['interpretation']='exported_coverage_metric_not_detection_accuracy_or_information_status'
    values=d.set_index('metric').value
    rows=[]
    for prefix in ['sandwiched','sandwiches']:
        total=values.get(prefix+'_rows_all')
        if total is None or total<=0:continue
        for suffix in ['null_usd','zero_usd','dust_lt_1usd']:
            key=prefix+'_rows_'+suffix
            if key in values:
                rows.append(dict(window=window,population=prefix,metric=suffix,
                    count=float(values[key]),denominator_rows=float(total),share_pct=100*float(values[key]/total),
                    interpretation='separate_categories_do_not_add_dust_and_zero_shares'))
    metric='sandwiched_rows_gt0_usd'
    check_status=('unavailable: missing '+metric if metric not in values else
                  'completed' if values[metric]==observed[COUNTS[1]].sum() else
                  'failed: Q0a positive-USD row count differs from Q5e attacked count')
    matching=pd.DataFrame([dict(window=window,
        q5e_attacked_events=int(observed[COUNTS[1]].sum()),
        quality_positive_usd_rows=values.get('sandwiched_rows_gt0_usd',np.nan),
        counts_match=bool(values.get('sandwiched_rows_gt0_usd',np.nan)==observed[COUNTS[1]].sum()),
        interpretation='cross_export_reconciliation_not_independent_validation_of_detection')])
    return dict(measurement_check_status=pd.DataFrame([dict(window=window,status=check_status)]),
                measurement_quality_metrics=d,measurement_quality_shares=pd.DataFrame(rows),
                measurement_count_reconciliation=matching)


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def inference_review(df, window):
    """Review applicability using observed design facts, not simulated outcomes.

    This is not a statistical test of assumptions. Unverified assumptions are
    not declared false, and withholding a test is not rejection of its null.
    """
    grouped = df.groupby(['project', 'version'], observed=True)[COUNTS].sum()
    project_counts = df.groupby('project', observed=True)[COUNTS[0]].sum()
    zero_groups = int(grouped[COUNTS[1]].eq(0).sum())
    all_attacked_groups = int(grouped[COUNTS[1]].eq(grouped[COUNTS[0]]).sum())
    facts = dict(window=window, observed_months=int(df.month.nunique()),
                 observed_projects=int(df.project.nunique()),
                 zero_attack_project_version_groups=zero_groups,
                 all_attacked_project_version_groups=all_attacked_groups,
                 largest_project_exposure_share=float(project_counts.max()/project_counts.sum()))
    methods = [
        ('Export consistency checks', 'retained_data_validation',
         'Counts, denominators, dates, keys and overlapping-window records reconcile.',
         'Checks internal consistency only; does not independently verify event detection or SQL.'),
        ('Observed rates and shape', 'retained_descriptive_comparison',
         'Describe rates and adjacent-bin changes in the recorded sample.',
         'No independence assumption is needed for arithmetic summaries; no population or causal inference follows.'),
        ('Independent-trial binomial / contingency-table tests', 'withheld',
         'Equal population attack probabilities across size bins.',
         'Independent or otherwise justified trial sampling is not established by these aggregate exports.'),
        ('Ordinary unclustered fixed-effect logistic Wald tests', 'withheld',
         'Zero size coefficients or zero relative linear-time slopes.',
         ('Boundary-outcome project/version groups prevent a finite full ordinary-logistic MLE. '
          if zero_groups or all_attacked_groups else 'Finite MLE existence has not been established. ')
         + 'This does not establish that every individual contrast is unidentified.'),
        ('Project/version-clustered grouped-binomial fixed-effect Wald tests', 'implemented_model_based_complement',
         'Jointly zero adjusted size coefficients and individual size-bin contrasts.',
         'Implemented as conventional model-based association inference using observed Q5e cells only. Cluster independence/asymptotic adequacy remain assumptions and limitations, not facts established by the exports.'),
        ('Project/version + month two-way clustered tests', 'implemented_robustness_only',
         'Jointly zero adjusted size coefficients.',
         'Implemented by inclusion-exclusion as a robustness specification. With few month clusters it remains approximate and is not treated as exact finite-sample inference.'),
        ('Monthly-score HAC tests', 'withheld',
         'Zero adjusted size coefficients or relative linear-time slopes.',
         'Requires restrictions on temporal dependence and defensible bandwidth/reference calibration. The short monthly panel alone does not establish these.'),
        ('Holm correction', 'not_a_validity_repair',
         'Control familywise error across valid component tests.',
         'Multiplicity adjustment does not repair unjustified component p-values.'),
        ('Firth likelihood-based significance tests', 'withheld',
         'Zero penalized-logistic size association.',
         'Handling separation does not justify working-independent likelihood uncertainty for dependent market events.'),
        ('Population inverted-U test', 'withheld',
         'Increase followed by decrease over a specified size range.',
         'Observed peaks and omnibus size differences do not test both shape restrictions; no justified shape-inference procedure is implemented.'),
        ('Retail-to-bot subsidy / Lemons test', 'not_identified',
         'Positive attributable transfer and the specified adverse-selection mechanism.',
         'Participant information status, attributable loss/profit and the mechanism outcome are not measured in these exports.'),
    ]
    return pd.DataFrame([dict(**facts, procedure=name, decision=decision,
                             question=question, justification=reason,
                             interpretation='method_review_not_a_null_hypothesis_result')
                         for name, decision, question, reason in methods])


def write_csv(path, frame):
    tmp=path.with_suffix('.tmp');frame.to_csv(tmp,index=False);tmp.replace(path)


def fetch_inventory(root):
    """Inspect actual CSV schemas; inventory is not a validation of identification."""
    rows=[]
    for path in sorted((root/'fetch').rglob('*.csv')):
        fetch_path(root, path)
        columns=pd.read_csv(path,nrows=0).columns.tolist()
        revised='revised-24m' in path.parts or 'revised-30m' in path.parts
        role=('analysis_input' if (path.name in [Q5E_NAME,'query0a_data_quality.csv'] or (path.name==Q5B_NAME and 'revised-24m' in path.parts)) else 'context_available_not_automatically_pooled') if revised else 'legacy_not_pooled'
        rows.append(dict(path=str(path.relative_to(root)),columns=json.dumps(columns),role=role,sha256=digest(path)))
    return pd.DataFrame(rows,columns=['path','columns','role','sha256'])


MAIN_QUESTION = ('Within the same project/version and month, how does the observed '
                 'attack rate differ between each larger trade-size bin and trades under $100?')
INTERPRETATION_RULES = [
    'A positive difference means higher observed attack incidence for that comparison.',
    'Persistence across projects, periods and weighting choices strengthens the descriptive finding; it is not independent replication.',
    'Neither result establishes retail identity, monetary subsidy or causation.',
    'Missing measurements mean H2 is not directly assessed, rather than H2 is false.',
]


def main_matched_results(tables):
    summary=tables['composition_summary']
    selected=summary[summary.scope=='all_projects'].copy()
    coverage=tables['composition_coverage']
    coverage=coverage[coverage.scope=='all_projects']
    keys=['window','scope','trade_size_bin']
    out=selected.merge(coverage[keys+['matched_cells','bin_candidate_coverage','reference_candidate_coverage']],
                       on=keys,how='left',validate='many_to_one')
    require(out.matched_cells.notna().all(),'Main results lack denominator-coverage information.')
    out['question']=MAIN_QUESTION
    out['reference_bin']=BIN_ORDER[0]
    out['unit']='percentage_points'
    out['analysis_role']='main_descriptive_matched_comparison'
    out['h2_status']='not_directly_assessed_not_false'
    out['interpretation']='observed_incidence_difference_no_retail_identity_transfer_or_causation_claim'
    return out


def matched_uncertainty(tables):
    """Fixed-horizon conditional Hoeffding bound for the main matched statistic.

    D_t is a within-month standardized rate difference in [-1,1]. Target:
    theta_T = mean_t E[D_t | F_(t-1)], potentially varying by month and random.
    Conditional Hoeffding lemma gives E[exp(lambda*(D_t-mu_t))|past]
    <= exp(lambda**2/2). Iteration and Chernoff yield
    P(abs(mean(D)-theta_T)>=r) <= 2*exp(-T*r*r/2).
    Union bound for M=40 comparisons: r=sqrt(2*log(2*M/alpha)/T).
    No stationarity, independence, asymptotic covariance or simulation needed.
    No claim about unconditional long-run means or causation follows.
    Only all-project, within-month statistics are used: no full-window project
    selection, selected dates, dominant-project exclusions, or shared-cell
    restrictions using future months enter this uncertainty calculation.
    """
    rows=[];checks=[];family=40;alpha=.05
    frame=tables['composition_monthly']
    frame=frame[frame.scope=='all_projects']
    for window in ['24m','30m']:
        months=24 if window=='24m' else 30
        available=frame[frame.window==window]
        expected_months=sorted(available.month.unique())
        for b in BIN_ORDER[1:]:
            for weighting in ['equal_project','overlap_exposure']:
                g=available[(available.trade_size_bin==b)&(available.weighting==weighting)].sort_values('month')
                status='completed'
                if len(g)!=months or g.month.duplicated().any() or sorted(g.month)!=expected_months:
                    status='unavailable: requires every scheduled month; missing comparisons are not imputed'
                checks.append(dict(window=window,trade_size_bin=b,weighting=weighting,status=status))
                if status!='completed':continue
                d=g.standardized_difference_pp.to_numpy(dtype=float)/100
                require(np.isfinite(d).all() and (abs(d)<=1).all(),'Monthly rate difference outside [-1,1].')
                radius=float(np.sqrt(2*np.log(2*family/alpha)/months))
                center=float(d.mean())
                low=max(-1.,center-radius);high=min(1.,center+radius)
                rows.append(dict(window=window,trade_size_bin=b,weighting=weighting,months=months,
                    observed_mean_difference_pp=100*center,half_width_pp=100*radius,
                    lower_bound_pp=100*low,upper_bound_pp=100*high,
                    zero_in_interval=bool(low<=0<=high),family_intervals=family,family_alpha=alpha,
                    target='time_average_conditional_expectation_of_monthly_matched_statistic',
                    dependence='arbitrary_adapted_dependence_bounded_monthly_statistic',
                    confidence_scope='fixed_40_interval_family_only_not_other_analysis_families',
                    interpretation='conservative_uncertainty_for_observable_implication_not_direct_H2'))
    return dict(matched_uncertainty=pd.DataFrame(rows),matched_uncertainty_status=pd.DataFrame(checks))


def matched_uncertainty_report(tables):
    lines=['','## Conservative uncertainty for the main matched comparison','',
        'D_t is the observed matched monthly rate difference under one of the two stated weighting rules. '
        'The target here is the average of E[D_t | previous monthly information] over the stated window. '
        'These conditional expectations may change with market conditions. This is not an unconditional long-run average, '
        'a causal effect, or a monetary subsidy. It is a different and less restrictive target than the exploratory every-month conditional nulls.', '',
        'Because D_t lies in [-1,1], the conditional Hoeffding bound gives '
        'P(|mean(D_t) - mean(E[D_t|past])| >= r) <= 2 exp(-T r^2/2). '
        'For 40 intervals (10 bins, 2 weighting schemes, 2 windows), r = sqrt(2 log(2*40/0.05)/T). '
        'Intervals are clipped to the known [-100,100] percentage-point range. '
        'This is a fixed-horizon simultaneous 95% bound for that fixed family. It permits dependence across months and comparisons, '
        'changing conditional means and variances, and overlapping windows. It uses neither simulated data nor estimated standard errors.', '',
        'Only the all-project matched comparisons enter these bounds. Each monthly statistic uses its own observed cells and denominators. '
        'No full-window outcome-dependent weights or selections are used. A missing scheduled month makes an interval unavailable, rather than triggering imputation. '
        'The bound does not correct measurement error or establish the unmeasured H2 mechanism. '
        'The 95% statement covers this fixed interval family and is not a simultaneous error-control statement for other analysis families.', '',
        '| Window | Intervals | Half-width (percentage points) | Intervals containing zero |',
        '|---|---:|---:|---:|']
    intervals=tables.get('matched_uncertainty',pd.DataFrame())
    if intervals.empty:lines.append('| Unavailable | 0 | — | — |')
    else:
        for window,g in intervals.groupby('window'):
            lines.append(f'| {window} | {len(g)} | {g.half_width_pp.iloc[0]:.2f} | {int(g.zero_in_interval.sum())} |')
        if intervals.zero_in_interval.all():
            lines.append('All calculated intervals include zero. This method does not establish a positive expected matched difference. It also does not establish equality or absence of a relationship.')
    lines+=['','The wide intervals reflect the conservative bounded-data guarantee and the short monthly record. '
        'This is not a proof that every possible method must be inconclusive. Narrower intervals require a stronger, defensible model or a different justified method. '
        'Do not replace the known [-1,1] bound with the observed minimum/maximum: unobserved outcomes need not lie inside the observed range.', '',
        'Methodological basis: the bounded-observation martingale concentration framework and average conditional-expectation target in '
        '[Howard et al., Time-uniform, nonparametric, nonasymptotic confidence sequences](https://arxiv.org/abs/1810.08240). '
        'The implementation uses the elementary fixed-time Hoeffding bound derived above, not simulations or the more elaborate confidence sequences in that paper.']
    return lines


def main_question_report(tables):
    lines=['','## Main question and interpretation','',MAIN_QUESTION,'',
        'For each observed project/version/month pair, attack rate = attacked events / eligible events. '
        'Difference (percentage points) = 100 * (larger-bin rate - under-$100 rate). '
        'Both rates must be observed in that same cell. Missing cells are not zeros. '
        'Projects can enter, leave or have gaps; no full-period activity requirement is imposed.', '']
    lines += ['- '+rule for rule in INTERPRETATION_RULES]
    lines += ['', 'The two summaries answer different averaging questions: **equal project** gives each observed matched project equal weight within a month '
        '(equal versions within each project); **overlap exposure** gives more weight to cells with eligible activity in both compared bins. '
        'The same weights are applied to both rates. Each available month then has equal weight. '
        'Neither summary is the pooled probability for an arbitrary transaction. Both are reported without selecting the more favorable answer.', '',
        '## Main observed results','',
        '| Window | Larger bin | Weighting | Larger rate (%) | Under-$100 rate (%) | Difference (pp) | Months | Matched coverage: larger / reference |',
        '|---|---|---|---:|---:|---:|---:|---:|']
    result=tables.get('main_matched_results',pd.DataFrame())
    if result.empty:return lines+['Main matched results unavailable; consult computation status.']
    for r in result.to_dict('records'):
        lines.append(f'| {r["window"]} | {BIN_LABEL[r["trade_size_bin"]]} | {r["weighting"]} | '
            f'{r["mean_standardized_bin_rate_pct"]:.4f} | {r["mean_standardized_reference_rate_pct"]:.4f} | '
            f'{r["equal_month_standardized_difference_pp"]:+.4f} | {r["months"]} | '
            f'{100*r["bin_candidate_coverage"]:.2f}% / {100*r["reference_candidate_coverage"]:.2f}% |')
    lines+=['','Rates are averages using the stated common weights; reference rates can differ across comparisons because matched cells and weights differ. '
        'Coverage is the share of original eligible events in each bin retained in matched cells, not a confidence level. '
        'The 24-month and 30-month results overlap. These tables establish recorded differences, not population significance. '
        'See main_matched_results.csv for full precision, monthly sign counts and coverage; composition_matched_cells.csv contains the underlying pairs.', '']
    for (window,weighting),g in result.groupby(['window','weighting']):
        x=g.equal_month_standardized_difference_pp
        lines.append(f'- {window}, {weighting}: {int((x>0).sum())} positive, {int((x<0).sum())} negative and {int((x==0).sum())} zero average differences across {len(g)} larger bins.')
    lines.append('A positive average does not mean the difference is positive for every project or every month; heterogeneity is reported in the checks below.')
    return lines


def write_report(out, tables, statuses):
    lines = ['# H2: observed data and measurement limitations', '',
        f'**H2 unchanged:** {HYPOTHESIS}', '',
        f'**Run status: {overall_status(statuses)}.** See computation status for failed, missing or partial checks.', '',
        'All empirical results below are calculated from the existing CSV exports inside project/fetch. '
        'There are no simulated observations, resampling or imputed values. The assumption-light track uses analytical conditional tests; the conventional track fits grouped-binomial models only to observed Q5e query cells.', '',
        ]
    lines += main_question_report(tables)
    lines += matched_uncertainty_report(tables)
    lines += composition_report(tables)
    lines += additional_checks_report(tables)
    lines += ['', '## Recorded sample context', '']
    for r in tables.get('sample_totals', pd.DataFrame()).to_dict('records'):
        lines.append(f'- {r["window"]}: {r["candidate_events"]:,} eligible events and '
                     f'{r["attacked_events"]:,} detected attacked events '
                     f'({r["attack_rate_pct"]:.4f}%).')
    for r in tables.get('shape_summary', pd.DataFrame()).to_dict('records'):
        lines.append(f'- {r["sample"]}: highest observed bin attack rate '
                     f'{r["peak_rate_pct"]:.4f}% in {r["peak_bin"]}. '
                     f'Adjacent bin changes: {r["adjacent_change_signs"]}.')
    for r in tables.get('project_concentration', pd.DataFrame()).to_dict('records'):
        lines.append(f'- {r["window"]}: {r["projects"]} projects; largest project accounts for '
                     f'{100*r["largest_project_share"]:.2f}% of eligible events.')
    lines += ['', 'Rates describe detected attacked events per eligible event, not unique traders. '
        'These differences and peaks describe the recorded sample; they do not establish a population inverted-U relationship or causation. '
        'The 30-month window overlaps the 24-month window and is not an independent replication. '
        'The extension table uses only observed additional months; it is not a forecast.', '',
        '## Victim-tier context', '',
        'The project defines Retail/Small/Institutional using victim-trade size quantiles. '
        'The approximately 50% Retail share follows the median-based definition and is not independent evidence of disproportionate targeting or verified retail identity. '
        'Traded notional is not victim loss or bot profit. Q5b quantile tiers and Q5e fixed dollar bins are different classifications.', '',
        '## Measurement requirements for H2', '',
        'The following is a requirements assessment, not a statistical test or an empirical finding about unmeasured quantities.', '',
        '| Component | Assessment | Missing evidence |', '|---|---|---|']
    for r in tables['formal_h2_evidence_map'].to_dict('records'):
        lines.append(f'| {r["component"]} | {r["assessment"]} | {r["missing"]} |')
    lines += ['', '## Conventional econometric complement', '',
        'Using the same observed Q5e query cells, a grouped-binomial logit is fitted with trade-size indicators, project/version fixed effects and month fixed effects '
        '(the under-$100 bin is the statistical reference category only and is not treated as verified retail). This model is estimated once, in `src/m9b_h2_test.py`, '
        'rather than re-estimated here, so there is a single canonical set of coefficients, odds ratios, cluster-robust standard errors and Holm-adjusted contrasts to cite -- '
        'not two independently-coded copies that could silently drift apart. Primary model-based uncertainty uses project/version-clustered CR1 covariance with t/F reference '
        'distributions and G-1 cluster degrees of freedom; two-way project/version + month clustering is reported there as approximate robustness inference. '
        'This is conventional model-based association inference. It does not create observations, establish causality, identify retail status, measure monetary subsidy, or directly test H2.', '',
        'See (all in `output/tables/`): `table_h2_q5e_adjusted_odds_ratios.csv` (odds ratios and CR1 confidence intervals by trade-size bin), '
        '`table_h2_q5e_joint_tests.csv` (the omnibus Wald/F test that all nonreference size coefficients are jointly zero), '
        '`table_h2_q5e_small_vs_larger_contrasts.csv` (Holm-adjusted pairwise contrasts against the under-$100 reference), '
        '`table_h2_q5e_two_way_cluster_robustness.csv` (two-way clustering robustness), and '
        '`table_h2_q5e_coefficient_stability_diagnostics.csv` / `table_h2_q5e_leave_one_project_out.csv` (stability diagnostics not duplicated in this track).']

    lines += ['', '## Conclusion', '',
        'The output establishes the reported counts, proportions and patterns within the supplied exports, subject to their measurement definitions. '
        'It does not establish retail-to-bot monetary transfers, information status, or the Lemons mechanism. '
        'H2 is not directly assessed because its required measurements are missing; this does not mean H2 is false. '
        'The main conclusion concerns observed matched attack incidence. Exploratory pooled tests are kept in a separate appendix.', '',
        '## Review of statistical procedures', '',
        'inference_review.csv records each reviewed procedure, its decision, and observed design facts. '
        'Validation checks and descriptive comparisons are retained. A conventional grouped-binomial fixed-effects model with project/version-clustered covariance is estimated once, in m9b_h2_test.py, and cross-referenced here as a model-based complement rather than re-estimated; unclustered and other unsupported variants remain withheld. The bounded monthly e-tests remain separate procedures with different null hypotheses. '
        'A withheld test is not a rejected null hypothesis. This is not a claim that all formal inference is impossible, '
        'and simulations are neither read nor used to make these decisions. '
        'Regression on real data is not artificial data; its inferential assumptions still require justification.', '',
        'For the methodological distinction between within-cluster dependence, independent clusters, and few-cluster limitations, see '
        '[Cameron and Miller, A Practitioner\'s Guide to Cluster-Robust Inference]'
        '(https://cameron.econ.ucdavis.edu/research/Cameron_Miller_JHR_2015_February.pdf). '
        'This reference provides methodology, not empirical inputs.', '',
        '## Source traceability', '',
        'fetch_inventory.csv lists available export schemas and hashes. The designated revised Q5e/Q5b files supply attack-rate and tier analysis values; Q0a supplies measurement-quality summaries. '
        'Legacy exports are not pooled. run_manifest.json records the exact input file hashes.', '',
        '## Computation status', '']
    lines += [f'- {r["analysis"]}: {r["status"]}' for r in statuses]
    lines += conditional_test_report(tables)
    (out/'reports'/f'{TABLE_PREFIX}evidence_assessment.md').write_text('\n'.join(lines)+'\n')


def conditional_test_report(tables):
    lines=['', '## Exploratory appendix: pooled conditional monthly tests', '',
        'These pooled tests do not test the main within-project comparison and do not determine its descriptive conclusion. '
        'These conditional tests evaluate related observable implications rather than the full H2 mechanism. '
        'The multiplicity adjustment covers the 80 tests in this file, '
        'and does not provide multiplicity control for distinct analysis families outside that set.', '',
        'For every larger fixed dollar bin, aggregate all projects within each calendar month and compare its attacked/eligible rate with the under-$100 bin. '
        'This is a marginal market-composition comparison, not a project-adjusted or causal effect. '
        'Months receive equal weight; unequal event counts remain in the rate denominators. Missing monthly denominators cause unavailability, not imputation.', '',
        'Two distinct one-sided nulls are tested in both directions:', '',
        '1. **Conditional mean difference:** the expected signed monthly rate difference, given previous monthly observations, is nonpositive at every month.',
        '2. **Conditional monthly ordering:** given previous months, a difference in the specified direction is never more probable than a difference in the opposite direction. Exact ties contribute zero.', '',
        'These are stronger, history-conditional nulls than equality of overall average rates. Serial dependence is allowed under these conditional restrictions; '
        'independent months, independent transactions, constant variance, normality and a large number of months are not required. '
        'A process with zero long-run mean can violate these conditional nulls. Therefore rejection must not be reported as rejection of equal unconditional means.', '',
        'Let X_t be the signed rate difference (between -1 and 1) or its sign. The fixed-stake statistic is '
        'L_T = product_t(1 + 0.5 X_t). Under the stated null, each factor has conditional expectation at most one, '
        'so this nonnegative product has expectation at most one. The Markov inequality gives p_bound = min(1, 1/L_T). '
        'The stake is fixed at 0.5; it is not optimized using these data. No maximum over dates is used. '
        'The reported adjusted bound is min(1, 80*p_bound), with rejection at 0.05. '
        'All 10 bins, two directions, two targets and two windows belong to this one family. The denominator remains 80 if some tests are unavailable. '
        'Dependence between tests and overlapping windows does not invalidate this Bonferroni bound.', '',
        'Rejection provides evidence against the stated every-month conditional null. It does not establish a positive effect in every month, '
        'a positive unconditional mean, future persistence, causation, participant information status, subsidy or an inverted U. '
        'Failure to reject is inconclusive. The raw-difference test is particularly conservative because its known bound is [-1,1] while observed attack-rate differences can be small. '
        'The ordering test discards magnitude and must not substitute for an economic-effect-size claim.', '',
        'The finite-sample argument above applies to the stated fixed testing rule and the explicitly defined conditional nulls.', '',
        'Methodological basis: [Waudby-Smith and Ramdas, Estimating means of bounded random variables by betting]'
        '(https://arxiv.org/abs/2010.09686), especially the capital-process construction and non-iid extensions. '
        'The code uses the elementary one-sided supermartingale argument shown above, not the simulation results in the paper.', '',
        '| Window | Target | Tests computed | Exploratory rejection-threshold crossings |',
        '|---|---|---:|---:|']
    tests=tables.get('conditional_tests',pd.DataFrame())
    if tests.empty:
        lines.append('| unavailable | see computation status | 0 | 0 |')
        return lines
    for (window,target),g in tests.groupby(['window','target'],sort=True):
        lines.append(f'| {window} | {target} | {len(g)} | {int(g.reject_conditional_null.sum())} |')
    lines += ['', 'All outcomes, including non-rejections and opposite directions, are in conditional_tests.csv. '
        'monthly_test_inputs.csv gives the actual counts, denominators and exact rate ordering for each monthly comparison.', '',
        '| Window | Bin versus under $100 | Target | Direction | Adjusted p-bound |',
        '|---|---|---|---|---:|']
    rejected=tests[tests.reject_conditional_null]
    for r in rejected.to_dict('records'):
        lines.append(f'| {r["window"]} | {BIN_LABEL[r["trade_size_bin"]]} | {r["target"]} | {r["direction"]} | {r["bonferroni_p_value_bound"]:.6g} |')
    if rejected.empty:lines.append('| None | — | — | — | — |')
    return lines


def composition_report(tables):
    lines=['','## Weighting and dominant-project sensitivity','',
        'These are descriptive robustness analyses, not additional hypothesis tests. Both rates are compared inside identical project/version/month cells. '
        'Unmatched cells are excluded with denominator coverage explicitly reported; they are not imputed. '
        'The matched population can differ by bin and window. Composition coverage must accompany any comparison.', '',
        'Overlap-exposure standardization applies weights n_reference*n_bin/(n_reference+n_bin) to both rates. '
        'It emphasizes strata with exposure in both bins. Equal-project standardization first averages matched versions within a project/month, '
        'then averages projects equally. Finally, each available month receives equal weight. '
        'These are deliberately different target averages, not repeated independent tests. '
        'They remove observed project/version composition differences within the matched cells but do not identify a causal trade-size effect.', '',
        'The largest project is selected using 24-month eligible-event counts and the same project is excluded in both windows. '
        'This deletion is an influence check, not a separate confirming sample. No new p-values are calculated or added to the 80-test family.', '']
    design=tables.get('composition_design',pd.DataFrame())
    if design.empty:return lines+['Analysis unavailable; see computation status.']
    r=design.iloc[0]
    lines.append(f'Excluded project: **{r.dominant_project}**, with {100*r.primary_candidate_share:.2f}% of primary-window eligible events.')
    lines+=['','| Window | Scope | Weighting | Bins with positive mean difference | Bins compared |',
            '|---|---|---|---:|---:|']
    for (window,scope,scheme),g in tables['composition_summary'].groupby(['window','scope','weighting']):
        lines.append(f'| {window} | {scope} | {scheme} | {int((g.equal_month_standardized_difference_pp>0).sum())} | {len(g)} |')
    lines+=['','Full magnitudes in percentage points, monthly signs and observed monthly ranges appear in composition_summary.csv. '
        'Ranges are not confidence intervals. composition_monthly.csv separates unrestricted pooled, matched pooled and standardized differences. '
        'composition_coverage.csv reports retained denominators; composition_matched_cells.csv and composition_project_month.csv retain the calculation detail.', '',
        '### Effect-size and confirmation assessment','',
        'No economically meaningful attack-rate threshold was supplied or identified in these exports. None is invented or selected from the results. '
        'The standardized rate differences measure observed magnitude; they are not estimates of monetary losses. '
        'The existing mean-difference e-tests address different, unadjusted conditional hypotheses and cannot supply uncertainty for these standardized contrasts. '
        'An economic-effect threshold test is therefore not performed. A direct subsidy test also remains unavailable: '
        'the existing windows have already been inspected, and attributable transfer/participant/mechanism measurements are missing.']
    return lines


def additional_checks_report(tables):
    lines=['','## Consistency, common support and measurement checks','',
        'These checks are descriptive and add no p-values. They do not treat projects, calendar halves, or overlapping windows as independent replications. '
        'consistency_by_project.csv reports each project mean, its available months and signs. '
        'consistency_project_distribution.csv includes negative and zero project means, spread, and concentration of positive mean differences. '
        'That concentration is an equal-project difference diagnostic, not a volume or loss share. '
        'Calendar periods are fixed January-June and July-December halves; none is selected for favorable results. '
        'Monthly sign reversals and all half-year results are retained.', '',
        'The primary pairwise analysis includes each project/version/month whenever both compared bins have observed denominators, even if that project enters, exits or has missing months. '
        'The optional common_bins comparison requires all 11 bins only within a particular project/version/month. '
        'No project must remain active throughout either window, and later activity is not used to decide inclusion in earlier months. '
        'Selection does not use attack outcomes, but activity-based selection can still change the target population. '
        'Source coverage by bin, unavailable restrictions, and all comparisons are reported. These are sensitivity results, not corrections for unobserved missingness.', '',
        '| Restriction | Window | Scope | Weighting | Positive mean differences | Bins compared |',
        '|---|---|---|---|---:|---:|']
    support=tables.get('support_summary',pd.DataFrame())
    if not support.empty:
        for key,g in support.groupby(['restriction','window','scope','weighting']):
            lines.append('| '+' | '.join(key)+f' | {int((g.equal_month_standardized_difference_pp>0).sum())} | {len(g)} |')
    lines+=['','Measurement checks use the actual query0a_data_quality.csv exports: null and zero USD values, small-notional rows, and count reconciliation. '
        'They do not estimate attack-detector false positives/negatives, retail classification accuracy, or differential detection by size/time. '
        'Aggregate quality metrics cannot resolve those questions. No detection rates or loss estimates are invented.', '',
        'The existing conditional ordering tests retain their original narrow nulls. Persistent rankings can contradict those conditional nulls '
        'without establishing a positive unconditional mean, a causal effect or H2. '
        'A common-support pattern, temporal robustness, and dominant-project sensitivity can strengthen a descriptive conclusion, '
        'but do not create independent confirmation or supply the missing subsidy and Lemons measurements.']
    project=tables.get('consistency_project_distribution',pd.DataFrame())
    if not project.empty:
        lines+=['','### Project heterogeneity','',
            '| Window (all projects) | Positive-project count range across bins | Negative-project count range | Zero-project count range |',
            '|---|---:|---:|---:|']
        for window,g in project[project.scope=='all_projects'].groupby('window'):
            lines.append(f'| {window} | {g.positive_projects.min()}–{g.positive_projects.max()} | {g.negative_projects.min()}–{g.negative_projects.max()} | {g.zero_projects.min()}–{g.zero_projects.max()} |')
        lines.append('Project means cover different observed months and may include zero detected attacks. Positive aggregate averages do not establish a universal project-level relationship.')
    halves=tables.get('consistency_calendar_halves',pd.DataFrame())
    if not halves.empty:
        lines.append(f'Across the reported overlapping windows, scopes, bins and weighting schemes, {int((halves.mean_difference_pp<0).sum())} of {len(halves)} half-year comparisons have negative mean differences. These counts are descriptive and dependent.')
    coverage=tables.get('support_source_coverage',pd.DataFrame())
    if not coverage.empty:
        lines+=['','### Coverage of common-support restrictions','',
            'Coverage below is relative to each original window before dominant-project exclusion; it is the minimum retained candidate share across the 11 bins.', '',
            '| Restriction | Window | Minimum candidate coverage |','|---|---|---:|']
        for (restriction,window),g in coverage.groupby(['restriction','window']):
            lines.append(f'| {restriction} | {window} | {100*g.retained_candidate_share.min():.2f}% |')
        lines.append('Missing cells are not filled with zero. Both the pairwise and optional all-bin comparisons describe their observed matched populations; they do not recover unobserved activity.')
    return lines


TABLE_PREFIX = 'h2a_'  # matches the h1_/h3_/h4_ file-naming convention used by the rest of the pipeline


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__,formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--root',type=Path,default=Path.cwd())
    parser.add_argument('--output',type=Path,help='Project output folder; tables/ and reports/ subfolders are written or overwritten in place, matching the rest of the pipeline.')
    add_input_options(parser)
    try:args=validate_options(parser.parse_args(argv))
    except (DataValidationError,ValueError) as exc:parser.error(str(exc))
    args.root=args.root.resolve()
    try:
        fetch_path(args.root, args.root/'fetch')
        for window in ['24m', '30m']:
            export_folder(args.root, window, args)
        out=(args.output or args.root/'output').resolve()
        require(not out.is_relative_to(args.root/'fetch'),
                'Output must be outside fetch to keep source datasets separate from generated results.')
    except (DataValidationError, OSError, RuntimeError) as exc:
        parser.error(str(exc))
    (out/'tables').mkdir(parents=True,exist_ok=True);(out/'reports').mkdir(parents=True,exist_ok=True)
    written_files=[]
    statuses=[];tables={'formal_h2_evidence_map':formal_evidence_map()};datasets={};input_paths=[]
    manifest=dict(status='running',hypothesis=HYPOTHESIS,h2_identification='not_identified_from_supplied_aggregate_exports',
        main_question=MAIN_QUESTION,interpretation_rules=INTERPRETATION_RULES,
        direct_H2_test=False,inference_policy='dual_track_assumption_light_plus_conventional_grouped_binomial_fixed_effects_cross_referenced_from_m9b',
        test_stake=BET_STAKE,test_family_size=TEST_FAMILY_SIZE,alpha=ALPHA,
        matched_interval_family_size=40,matched_interval_family_alpha=.05,
        interval_scope='separate_fixed_family_not_combined_across_distinct_analysis_families',
        input_policy='existing_project_fetch_csv_exports_only',fetch_root=str(args.root/'fetch'),
        artificial_datasets_used=False,simulation_results_used=False,resampling_used=False,
        fitted_models_used=True,imputation_used=False,conclusion_scope='descriptive_conditional_and_model_based_association_analyses_not_direct_H2',
        script_sha256=digest(__file__),python=platform.python_version(),
        packages={x:importlib.metadata.version(x) for x in ['numpy','pandas']},
        settings={k:str(v) if isinstance(v,Path) else v for k,v in vars(args).items()})
    def save():
        for name,frame in tables.items():
            path=out/'tables'/f'{TABLE_PREFIX}{name}.csv'
            write_csv(path,frame);written_files.append(path)
        status_path=out/'tables'/f'{TABLE_PREFIX}computation_status.csv'
        write_csv(status_path,pd.DataFrame(statuses,columns=['analysis','status']));written_files.append(status_path)
        manifest['analyses']=statuses
        manifest_path=out/'reports'/f'{TABLE_PREFIX}run_manifest.json'
        with manifest_path.open('w') as handle:
            json.dump(manifest,handle,indent=2,allow_nan=False);handle.write('\n')
            handle.flush()
            import os
            os.fsync(handle.fileno())
        if manifest_path not in written_files:written_files.append(manifest_path)
    def append(name,frame):
        tables[name]=pd.concat([tables.get(name,pd.DataFrame()),frame],ignore_index=True)
    def attempt(name,function):
        try:
            value=function();statuses.extend(result_status_records(name,value));return value
        except DataValidationError as exc:
            statuses.append(dict(analysis=name,status='failed: '+str(exc)));return None
        except OSError as exc:
            statuses.append(dict(analysis=name,status='unavailable: '+str(exc)));return None
        finally:save()
    try:
        tables['fetch_inventory']=fetch_inventory(args.root)
        save()
        for window in ['24m','30m']:
            folder=export_folder(args.root,window,args);path=folder/Q5E_NAME
            if path.is_file():input_paths.append(path)
            def load():
                d=load_analysis_window(args.root,window,args)
                if window=='30m':
                    require('24m' in datasets,'Primary data unavailable for overlap validation.')
                    validate_overlap(datasets['24m'],d,args.money_decimals)
                return d
            d=attempt(window+'_input',load)
            if d is None:continue
            datasets[window]=d
            append('inference_review',inference_review(d,window))
            tested=attempt(window+'_conditional_e_tests',lambda:monthly_conditional_tests(d,window))
            if tested is not None:
                result,audit=tested
                append('conditional_tests',result)
                append('monthly_test_inputs',audit)
            desc=descriptive_rates(d,window);append('observed_rates',desc)
            append('shape_summary',pd.DataFrame([dict(sample=window,**shape_diagnostics(desc))]))
            shares=d.groupby('project',observed=True)[COUNTS[0]].sum();shares=shares/shares.sum()
            append('project_concentration',pd.DataFrame([dict(window=window,projects=len(shares),largest_project_share=float(shares.max()),exposure_hhi=float((shares**2).sum()))]))
            n=int(d[COUNTS[0]].sum());a=int(d[COUNTS[1]].sum())
            append('sample_totals',pd.DataFrame([dict(window=window,
                candidate_events=n,attacked_events=a,attack_rate_pct=100*a/n)]))
            save()
        if '24m' in datasets and '30m' in datasets:
            extra=datasets['30m'][~datasets['30m'].month.isin(datasets['24m'].month)]
            if len(extra):append('observed_rates',descriptive_rates(extra,'previously_seen_nonoverlap_extension'))
        if '24m' in datasets:
            sensitivity=attempt('composition_sensitivity',lambda:composition_sensitivity(datasets['24m'],datasets))
            if sensitivity is not None:
                tables.update(sensitivity)
                primary_results=attempt('main_matched_results',lambda:main_matched_results(tables))
                if primary_results is not None:
                    tables['main_matched_results']=primary_results
                    uncertainty=attempt('matched_uncertainty',lambda:matched_uncertainty(tables))
                    if uncertainty is not None:tables.update(uncertainty)
                consistency=attempt('consistency_checks',lambda:consistency_checks(tables))
                if consistency is not None:tables.update(consistency)
                support=attempt('common_support_checks',lambda:common_support_checks(datasets['24m'],datasets))
                if support is not None:tables.update(support)
        for window,d in datasets.items():
            folder=export_folder(args.root,window,args)
            quality_path=fetch_path(args.root,folder/'query0a_data_quality.csv')
            if quality_path.is_file():input_paths.append(quality_path)
            quality=attempt(window+'_measurement_quality',lambda:measurement_quality(folder,window,d))
            if quality is not None:
                for name,frame in quality.items():append(name,frame)
        qpath=export_folder(args.root,'24m',args)/Q5B_NAME
        if qpath.is_file():input_paths.append(qpath)
        q=attempt('victim_tier_context',lambda:load_victim_composition(qpath.parent,
            pct_decimals=args.q5b_pct_decimals,money_decimals=args.money_decimals,
            complete=not args.q5b_incomplete,check_average=args.check_q5b_average))
        if q is not None:
            q=q.rename(columns={'victim_tier':'source_quantile_tier_label','total_volume':'victim_traded_notional_usd_not_loss'})
            q['interpretation']='outcome_quantile_context_not_retail_identity_or_H2_test';tables['victim_tier_context']=q
        manifest['status']=overall_status(statuses)
        manifest['input_sha256']={str(p):digest(p) for p in input_paths}
        report_path=out/'reports'/f'{TABLE_PREFIX}evidence_assessment.md'
        write_report(out,tables,statuses)
        written_files.append(report_path)
    except BaseException as exc:
        manifest['status']='failed_or_interrupted';manifest['error']=f'{type(exc).__name__}: {exc}';raise
    finally:
        manifest['finished_utc']=datetime.now(timezone.utc).isoformat();save()
        # out/ is the shared pipeline output directory, so only hash the files this
        # module itself wrote this run -- not every other module's output alongside it.
        manifest['output_sha256']={str(p.relative_to(out)):digest(p) for p in written_files if p.name!=f'{TABLE_PREFIX}run_manifest.json' and p.exists()}
        save()
    print(f'Execution: {manifest["status"]}. H2 identification: not identified. Report: {out}/reports/{TABLE_PREFIX}evidence_assessment.md')
    return 0 if manifest['status']=='completed' else 1


if __name__=='__main__':raise SystemExit(main())






#--------------------------------------------------------------------------------------
