"""
H1 concentration and robustness analysis.

Purpose
-------
This module supplements the project's existing H1 analysis in m2_concentration.py
and m3_bot_dynamics.py.

It has two roles:

1. Strengthen the observable concentration result in H1 using complementary
   concentration metrics and robustness checks.
   

2. Bring the existing scale/activity evidence from m3_bot_dynamics.py into the
   H1 hypothesis report.

Interpretation boundary
-----------------------
The available data identify bot addresses and their observed sandwich activity.
They do not identify unique economic searchers/operators, nor do they directly
measure infrastructure speed or trading-signal quality.

Therefore this module provides:
    - strong evidence about concentration among observed bot addresses
    - descriptive evidence that scale/activity/persistence are associated with
      total sandwich transaction volume

It doesn't establish that scale, faster infrastructure, or superior trading
signals causally produce that concentration.
"""

from __future__ import annotations

import argparse
import csv
import math
import random
import re
from pathlib import Path

METRICS = ["gini", "top_1pct_share", "cr1", "cr4", "cr10", "cr20", "hhi"]
GINI_BENCHMARK = 0.90


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--data-root", default="fetch/data")
    p.add_argument("--windows", default="revised-24m,revised-30m")
    p.add_argument("--bootstrap-resamples", type=int, default=10000)
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--output-dir", default="output")
    return p.parse_args()


def read_csv(path: Path):
    with path.open("r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def write_csv(path: Path, rows, fields):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)


def f(x, *, field_name="value"):
    """Parse a numeric value strictly.

    Blank values are treated as missing. Any nonblank malformed value raises
    ValueError so corrupted input cannot silently change the analysis sample.
    """
    if x is None:
        return None
    s = str(x).strip()
    if s == "":
        return None
    try:
        value = float(s.replace(",", ""))
    except ValueError as exc:
        raise ValueError(f"Malformed numeric {field_name}: {x!r}") from exc
    if not math.isfinite(value):
        raise ValueError(f"Non-finite numeric {field_name}: {x!r}")
    return value


def find_col(cols, keys):
    """Find one expected column deterministically.

    Exact case-insensitive matches are preferred. Substring matching is used
    only as a backward-compatible fallback and only when it identifies exactly
    one column; ambiguous matches raise an error rather than silently choosing
    the first column.
    """
    low_map = {c.lower(): c for c in cols}
    for k in keys:
        if k.lower() in low_map:
            return low_map[k.lower()]

    matches = []
    for c in cols:
        lc = c.lower()
        if any(k.lower() in lc for k in keys):
            matches.append(c)

    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        raise ValueError(
            "Ambiguous column match for expected keys "
            + repr(keys)
            + ": "
            + ", ".join(matches)
        )
    return None


def q(xs, p):
    if not xs:
        return float("nan")
    if len(xs) == 1:
        return xs[0]
    i = (len(xs) - 1) * p
    lo = int(math.floor(i))
    hi = int(math.ceil(i))
    if lo == hi:
        return xs[lo]
    w = i - lo
    return xs[lo] * (1 - w) + xs[hi] * w


# ---------------------------------------------------------------------------
# Gini coefficient
#
# Measures inequality in sandwich volume across bot addresses.
# A value near 0 indicates a relatively even distribution; a value near 1
# indicates extreme inequality. For H1, a very high Gini supports the claim
# that sandwich transaction volume is concentrated among a small number of bot addresses.
# ---------------------------------------------------------------------------
def gini(vals):
    x = sorted(v for v in vals if v is not None and v >= 0)
    n = len(x)
    if n == 0:
        return float("nan")
    s = sum(x)
    if s <= 0:
        return float("nan")
    ws = sum((i + 1) * v for i, v in enumerate(x))
    return (2.0 * ws) / (n * s) - (n + 1) / n


# ---------------------------------------------------------------------------
# Core H1 concentration metrics
#
# These statistics test the observable outcome predicted by H1:
# whether a small number of bot addresses account for a disproportionate
# share of total sandwich-MEV volume.
#
# Reported measures:
#   - Gini: overall inequality in bot volume.
#   - Top 1% share: share accounted for by the highest-volume ceiling(1% * N)
#     addresses, so at least one address is included for small samples.
#   - CR1 / CR4 / CR10 / CR20: share accounted for by the top 1, 4, 10, or 20
#     addresses.
#   - HHI: concentration index based on squared market shares.
#
# These measures establish concentration. They do not identify why the
# concentration exists
# ---------------------------------------------------------------------------
def concentration(vals):
    x = [v for v in vals if v is not None and v >= 0]
    if not x:
        return {k: float("nan") for k in METRICS}
    total = sum(x)
    if total <= 0:
        return {k: float("nan") for k in METRICS}
    s = sorted(x, reverse=True)

    def top_share(k):
        k = min(max(1, k), len(s))
        return sum(s[:k]) / total

    top1k = max(1, int(math.ceil(0.01 * len(s))))
    return {
        "gini": gini(s),
        "top_1pct_share": top_share(top1k),
        "cr1": top_share(1),
        "cr4": top_share(4),
        "cr10": top_share(10),
        "cr20": top_share(20),
        "hhi": 10000.0 * sum((v / total) ** 2 for v in s),
    }


# ---------------------------------------------------------------------------
# Bootstrap robustness for concentration statistics
#
# Resample observed bot addresses with replacement to assess how stable the
# concentration estimates are to address-level resampling.
#
# INTERPRETATION:
#   - These data may approximate a census of identified bot addresses rather
#     than a probability sample. Bootstrap intervals are therefore presented as
#     address-resampling robustness, not classical population-sampling inference.
#   - Gini=0.90 is retained only as a deliberately stringent operational
#     reference for extreme concentration. It is not a universal cutoff, and no
#     benchmark p-value or reject/do-not-reject decision is calculated.
#   - Top-1% share is reported directly as a continuous, interpretable
#     concentration measure. No 90% threshold is imposed on it.
#   - revised-24m is primary; revised-30m is a robustness window.
# ---------------------------------------------------------------------------
def bootstrap(vals, nboot, seed):
    rng = random.Random(seed)
    x = [v for v in vals if v is not None and v >= 0]
    n = len(x)

    if n == 0:
        raise ValueError("bootstrap requires at least one non-negative observation")
    if nboot <= 0:
        raise ValueError("bootstrap_resamples must be greater than zero")

    draws = {k: [] for k in METRICS}
    for _ in range(nboot):
        samp = [x[rng.randrange(n)] for _ in range(n)]
        m = concentration(samp)
        for k in METRICS:
            draws[k].append(m[k])

    out = {}
    for k, arr in draws.items():
        arrs = sorted(arr)
        out[k] = {
            "mean": sum(arr) / len(arr),
            "ci_low": q(arrs, 0.025),
            "ci_high": q(arrs, 0.975),
        }
    return out


def rank_map(vol_by_addr):
    # Equal-volume ties are broken deterministically by address for top-k/group
    # membership. Spearman itself uses average ranks for ties.
    pairs = sorted(
        [(a, v) for a, v in vol_by_addr.items() if v is not None and v > 0],
        key=lambda t: (-t[1], t[0]),
    )
    return {a: i + 1 for i, (a, _) in enumerate(pairs)}


def spearman(v1, v2):
    common = sorted(
        a for a in set(v1) & set(v2)
        if v1[a] is not None and v1[a] > 0
        and v2[a] is not None and v2[a] > 0
    )
    n = len(common)
    if n < 2:
        return None

    def average_ranks(values):
        pairs = sorted(values.items(), key=lambda t: (t[1], t[0]))
        ranks = {}
        i = 0
        while i < len(pairs):
            j = i + 1
            while j < len(pairs) and pairs[j][1] == pairs[i][1]:
                j += 1
            avg_rank = ((i + 1) + j) / 2.0
            for k in range(i, j):
                ranks[pairs[k][0]] = avg_rank
            i = j
        return ranks

    common_v1 = {a: v1[a] for a in common}
    common_v2 = {a: v2[a] for a in common}
    rr1 = average_ranks(common_v1)
    rr2 = average_ranks(common_v2)

    x = [rr1[a] for a in common]
    y = [rr2[a] for a in common]
    mx = sum(x) / n
    my = sum(y) / n

    nume = sum((xi - mx) * (yi - my) for xi, yi in zip(x, y))
    denx = sum((xi - mx) ** 2 for xi in x)
    deny = sum((yi - my) ** 2 for yi in y)

    if denx <= 0 or deny <= 0:
        return None

    return nume / math.sqrt(denx * deny)





def top_k(vol_by_addr, k):
    # Equal-volume ties at the cutoff are broken deterministically by address.
    pairs = sorted(
        [(a, v) for a, v in vol_by_addr.items() if v is not None and v > 0],
        key=lambda t: (-t[1], t[0]),
    )
    return [a for a, _ in pairs[: min(k, len(pairs))]]


def rank_group(rank, n):
    p = rank / n
    if p <= 0.01:
        return "top_1pct"
    if p <= 0.05:
        return "top_5pct"
    if p <= 0.10:
        return "top_10pct"
    return "rest_90pct"


def _parse_m3_estimate(text, *, metric, allow_percent=False):
    """Strictly parse a canonical numeric estimate from table9_bot_dynamics.csv.

    Accepted forms are a numeric estimate with optional significance stars and
    an optional parenthesized standard error. A percentage sign is accepted
    only when allow_percent=True. Arbitrary surrounding text is rejected.
    """
    if text is None or str(text).strip() == "":
        raise ValueError(f"Canonical m3 metric {metric!r} has a missing Value")

    s = str(text).strip()
    number = r"[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?"
    percent = r"%?" if allow_percent else ""
    pattern = rf"^({number}){percent}\s*\*{{0,3}}(?:\s*\(\s*{number}\s*\))?$"
    m = re.fullmatch(pattern, s)
    if not m:
        raise ValueError(
            f"Unexpected Value format for canonical m3 metric {metric!r}: {text!r}"
        )

    value = float(m.group(1))
    if not math.isfinite(value):
        raise ValueError(f"Canonical m3 metric {metric!r} is not finite: {value}")
    return value


def _model_fit_r2(text):
    if text is None:
        return None
    s = str(text)
    m = re.search(
        r"R(?:\^?2|²)\s*[:=]?\s*"
        r"([-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?)",
        s,
        re.I,
    )
    if not m:
        return None
    value = float(m.group(1))
    if not 0.0 <= value <= 1.0:
        raise ValueError(f"Parsed R2 is outside [0, 1]: {value}")
    return value


def _pvalue_from_notes(text, *, metric):
    """Strictly parse a canonical p-value from an m3 Notes field."""
    if text is None or str(text).strip() == "":
        raise ValueError(f"Canonical m3 metric {metric!r} has a missing Notes p-value")
    m = re.search(
        r"(?:Permutation\s+)?p\s*=\s*"
        r"([-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?)",
        str(text),
        re.I,
    )
    if not m:
        raise ValueError(
            f"Could not parse a p-value from canonical m3 metric {metric!r}: {text!r}"
        )
    value = float(m.group(1))
    if not math.isfinite(value) or not 0.0 <= value <= 1.0:
        raise ValueError(
            f"Canonical m3 metric {metric!r} has invalid p-value: {value}"
        )
    return value


# ---------------------------------------------------------------------------
# H1 scale/activity evidence
#
#
# Imported diagnostics (from  m3_bot_dynamics.py):
#   - Spearman(volume, days active)
#   - Spearman(volume, total trades)
#   - Spearman(volume, average trade size)
#   - persistent-bot volume share
#   - descriptive HC3 OLS results
#
# These statistics assess whether greater activity, persistence, and scale
# are associated with greater total sandwich transaction volume.
#
# Not to be interpreted causally. In particular:
#
#     total_volume ~= total_trades * average_trade_size
#
# so some associations are partly mechanical. The available data also contain
# no exogenous variation and no direct measures of latency, infrastructure
# quality, or trading-signal quality.
# ---------------------------------------------------------------------------
def load_scale_activity_results(output_dir: Path):
    """Reuse the canonical H1 scale diagnostics produced by m3_bot_dynamics."""
    path = output_dir / "tables" / "table9_bot_dynamics.csv"
    if not path.exists():
        raise FileNotFoundError(
            f"{path} is required. Run src.m3_bot_dynamics first or run the full pipeline."
        )

    rows = read_csv(path)

    by_metric = {}
    duplicate_metrics = set()
    for r in rows:
        metric = str(r.get("Metric", "")).strip()
        if metric in by_metric:
            duplicate_metrics.add(metric)
        else:
            by_metric[metric] = r

    if duplicate_metrics:
        raise ValueError(
            "Canonical m3 output contains duplicate Metric rows: "
            + ", ".join(sorted(duplicate_metrics))
        )

    required = [
        "Persistent Bot Volume Share (>= 30 days)",
        "Spearman(Volume, Days Active)",
        "Spearman(Volume, Total Trades)",
        "Spearman(Volume, Avg Trade Size)",
        "ln(Days Active)",
        "ln(Intensity)",
        "Model Fit",
    ]
    missing = [m for m in required if m not in by_metric]
    if missing:
        raise ValueError(
            "Canonical m3 output is missing expected H1 scale diagnostics: "
            + ", ".join(missing)
        )

    def row(metric):
        return by_metric[metric]

    persistent_pct = _parse_m3_estimate(
        row("Persistent Bot Volume Share (>= 30 days)")["Value"],
        metric="Persistent Bot Volume Share (>= 30 days)",
        allow_percent=True,
    )
    rho_days = _parse_m3_estimate(
        row("Spearman(Volume, Days Active)")["Value"],
        metric="Spearman(Volume, Days Active)",
    )
    rho_trades = _parse_m3_estimate(
        row("Spearman(Volume, Total Trades)")["Value"],
        metric="Spearman(Volume, Total Trades)",
    )
    rho_size = _parse_m3_estimate(
        row("Spearman(Volume, Avg Trade Size)")["Value"],
        metric="Spearman(Volume, Avg Trade Size)",
    )
    p_days = _pvalue_from_notes(
        row("Spearman(Volume, Days Active)")["Notes"], metric="Spearman(Volume, Days Active)"
    )
    p_trades = _pvalue_from_notes(
        row("Spearman(Volume, Total Trades)")["Notes"], metric="Spearman(Volume, Total Trades)"
    )
    p_size = _pvalue_from_notes(
        row("Spearman(Volume, Avg Trade Size)")["Notes"], metric="Spearman(Volume, Avg Trade Size)"
    )
    ols_days = _parse_m3_estimate(
        row("ln(Days Active)")["Value"],
        metric="ln(Days Active)",
    )
    ols_days_p = _pvalue_from_notes(
        row("ln(Days Active)")["Notes"], metric="ln(Days Active)"
    )
    ols_intensity = _parse_m3_estimate(
        row("ln(Intensity)")["Value"],
        metric="ln(Intensity)",
    )
    ols_intensity_p = _pvalue_from_notes(
        row("ln(Intensity)")["Notes"], metric="ln(Intensity)"
    )
    ols_r2 = _model_fit_r2(row("Model Fit")["Value"])
    if ols_r2 is None:
        raise ValueError(
            "Could not parse a valid R2 value from the canonical m3 'Model Fit' row"
        )

    return {
        "source": str(path),
        "persistent_volume_share": persistent_pct / 100.0 if persistent_pct is not None else None,
        "rho_volume_days_active": rho_days,
        "p_volume_days_active": p_days,
        "rho_volume_total_trades": rho_trades,
        "p_volume_total_trades": p_trades,
        "rho_volume_avg_trade_size": rho_size,
        "p_volume_avg_trade_size": p_size,
        "ols_ln_days_active": ols_days,
        "ols_ln_days_active_p": ols_days_p,
        "ols_ln_intensity": ols_intensity,
        "ols_ln_intensity_p": ols_intensity_p,
        "ols_r2": ols_r2,
    }


# ---------------------------------------------------------------------------
# Load one analysis window and calculate H1 concentration robustness results.
#
#
#
# 
def load_window(window_name, window_dir, nboot, seed):
    q3 = window_dir / "query3_full_bot_distribution_v2.csv"
    if not q3.exists():
        alts = sorted(
            set(window_dir.glob("query3*full*distribution*.csv"))
            | set(window_dir.glob("query3*distribution*.csv"))
        )
        if len(alts) == 1:
            q3 = alts[0]
        elif len(alts) > 1:
            raise FileNotFoundError(
                "Expected query3_full_bot_distribution_v2.csv, but multiple "
                f"alternative Query 3 distribution files were found in {window_dir}: "
                + ", ".join(str(p.name) for p in alts)
            )

    if not q3.exists():
        raise FileNotFoundError(
            f"No Query 3 bot-distribution CSV found in {window_dir}; expected "
            "query3_full_bot_distribution_v2.csv"
        )

    rows = read_csv(q3)
    if not rows:
        raise ValueError(f"{q3} is empty")

    cols = list(rows[0].keys())
    addr_col = find_col(cols, ["bot_address", "address", "searcher"])
    vol_col = find_col(
        cols, ["volume_usd", "sandwich_volume_usd", "total_volume_usd", "volume"]
    )

    if addr_col is None or vol_col is None:
        raise ValueError(
            f"{q3} is missing the required bot-address or volume column"
        )

    vol_by_addr = {}
    measurable = []
    positive = []
    seen_addresses = set()

    for row_number, r in enumerate(rows, start=2):
        a = str(r.get(addr_col, "")).strip()

        if not a:
            raise ValueError(
                f"{q3} contains a missing/blank bot address at row {row_number}"
            )
        if a in seen_addresses:
            raise ValueError(f"{q3} contains duplicate bot address: {a}")
        seen_addresses.add(a)

        v = f(
            r.get(vol_col),
            field_name=f"{vol_col} at {q3.name} row {row_number}",
        )

        if v is not None and v < 0:
            raise ValueError(
                f"{q3} contains negative bot volume at row {row_number}: {v}"
            )

        if a and v is not None:
            vol_by_addr[a] = v
            measurable.append(v)
            if v > 0:
                positive.append(v)

    if not measurable:
        raise ValueError(f"{q3} contains no measurable non-missing bot volumes")

    m = concentration(measurable)
    b = bootstrap(measurable, nboot, seed)
    mp = concentration(positive)

    # Top-k exclusion sensitivity:
    # remove the largest 1, 5, or 10 bot addresses and recompute concentration.
    # This checks whether H1 is driven only by a tiny number of exceptional
    # outliers. If concentration remains extreme, the result is broader than
    # just the single largest bot
    def excl(k):
        s = sorted(
            [v for v in measurable if v is not None and v >= 0], reverse=True
        )
        if k >= len(s):
            return None
        rem = s[k:]
        return {
            "window": window_name,
            "scenario": f"exclude_top_{k}",
            **concentration(rem),
            "remaining_n": len(rem),
        }

    exclusions = [
        result
        for result in (excl(1), excl(5), excl(10))
        if result is not None
    ]

    # Address-clustering sensitivity:
    # the data identify addresses, not underlying economic operators.
    # These illustrative deterministic stress scenarios merge several leading
    # addresses into hypothetical operator groups to examine how concentration
    # changes under alternative multi-address grouping assumptions.
    #
    # This is a sensitivity analysis only. The grouping structures are not
    # estimated ownership probabilities, do not perform entity resolution, and
    # do not claim that any addresses are controlled by the same party.
    def cluster(top_n, groups):
        s = sorted(
            [v for v in measurable if v is not None and v >= 0], reverse=True
        )
        top_n = min(top_n, len(s))
        groups = max(1, min(groups, top_n if top_n else 1))
        head, tail = s[:top_n], s[top_n:]
        merged = [0.0] * groups
        for i, v in enumerate(head):
            merged[i % groups] += v
        z = merged + tail
        return {
            "window": window_name,
            "scenario": f"merge_top_{top_n}_into_{groups}",
            **concentration(z),
            "result_n": len(z),
        }

    clusters = [cluster(5, 1), cluster(10, 2), cluster(20, 4)]

    return {
        "window": window_name,
        "path": str(q3),
        "rows": len(rows),
        "vol_by_addr": vol_by_addr,
        "measurable_n": len(measurable),
        "positive_n": len(positive),
        "main": m,
        "boot": b,
        "positive": mp,
        "exclusions": exclusions,
        "clusters": clusters,
    }


def _finite_number(x):
    if x is None:
        return False
    try:
        return math.isfinite(float(x))
    except (TypeError, ValueError):
        return False


def pct(x):
    return "NA" if not _finite_number(x) else f"{100 * float(x):.2f}%"


def num(x, d=4):
    return "NA" if not _finite_number(x) else f"{float(x):.{d}f}"


# ---------------------------------------------------------------------------
# Main H1 synthesis routine
#
# Produces:
#   - full-window concentration metrics and bootstrap intervals;
#   - top-k exclusion and address-clustering sensitivities;
#   - 24m-vs-30m robustness;
#   - cross-window rank persistence;
#   - scale/activity evidence imported from m3.
# ---------------------------------------------------------------------------
def run_h1_tests(
    data_root="fetch/data",
    windows="revised-24m,revised-30m",
    bootstrap_resamples=10000,
    seed=42,
    output_dir="output",
):
    data_root = Path(data_root)
    out = Path(output_dir)
    windows = [w.strip() for w in windows.split(",") if w.strip()]
    if not windows:
        raise ValueError("At least one analysis window must be specified")
    if len(windows) != len(set(windows)):
        duplicates = sorted({w for w in windows if windows.count(w) > 1})
        raise ValueError(
            "Duplicate analysis window(s) specified: " + ", ".join(duplicates)
        )

    primary = "revised-24m"
    if primary not in windows:
        raise ValueError(
            "The research-design primary window is fixed as 'revised-24m'. "
            "Include revised-24m in --windows; revised-30m is a robustness check only."
        )

    # Bootstrap streams are tied to window identity, not --windows ordering.
    window_seed_offsets = {"revised-24m": 0, "revised-30m": 1000}
    unsupported = [w for w in windows if w not in window_seed_offsets]
    if unsupported:
        raise ValueError(
            "No fixed bootstrap seed offset defined for analysis window(s): "
            + ", ".join(sorted(unsupported))
        )

    results = {}
    for w in windows:
        results[w] = load_window(
            w,
            data_root / w,
            bootstrap_resamples,
            seed + window_seed_offsets[w],
        )

    scale = load_scale_activity_results(out)

    rows_summary = []
    rows_excl = []
    rows_cluster = []
    for w in windows:
        r = results[w]
        m, b = r["main"], r["boot"]
        rows_summary.append(
            {
                "window": w,
                "analysis_role": (
                    "primary"
                    if w == primary
                    else "robustness"
                ),
                "gini": m["gini"],
                "gini_ci_low": b["gini"]["ci_low"],
                "gini_ci_high": b["gini"]["ci_high"],
                "top_1pct_share": m["top_1pct_share"],
                "top_1pct_ci_low": b["top_1pct_share"]["ci_low"],
                "top_1pct_ci_high": b["top_1pct_share"]["ci_high"],
                "cr1": m["cr1"],
                "cr4": m["cr4"],
                "cr10": m["cr10"],
                "cr20": m["cr20"],
                "hhi": m["hhi"],
                "gini_operational_benchmark": GINI_BENCHMARK,
                "gini_ci_low_above_benchmark": b["gini"]["ci_low"] > GINI_BENCHMARK,
            }
        )
        rows_excl.extend(r["exclusions"])
        rows_cluster.extend(r["clusters"])

    scale_rows = [
        {
            "metric": "persistent_bot_volume_share_ge_30_days",
            "estimate": scale["persistent_volume_share"],
            "p_value": "",
            "source": scale["source"],
            "interpretation": "Descriptive persistence/scale association",
        },
        {
            "metric": "spearman_volume_days_active",
            "estimate": scale["rho_volume_days_active"],
            "p_value": scale["p_volume_days_active"],
            "source": scale["source"],
            "interpretation": "Descriptive rank association",
        },
        {
            "metric": "spearman_volume_total_trades",
            "estimate": scale["rho_volume_total_trades"],
            "p_value": scale["p_volume_total_trades"],
            "source": scale["source"],
            "interpretation": "Descriptive rank association; volume is mechanically related to trade count",
        },
        {
            "metric": "spearman_volume_avg_trade_size",
            "estimate": scale["rho_volume_avg_trade_size"],
            "p_value": scale["p_volume_avg_trade_size"],
            "source": scale["source"],
            "interpretation": "Descriptive rank association; volume is mechanically related to average size",
        },
        {
            "metric": "descriptive_ols_ln_days_active",
            "estimate": scale["ols_ln_days_active"],
            "p_value": scale["ols_ln_days_active_p"],
            "source": scale["source"],
            "interpretation": "HC3 descriptive OLS coefficient; not causal",
        },
        {
            "metric": "descriptive_ols_ln_intensity",
            "estimate": scale["ols_ln_intensity"],
            "p_value": scale["ols_ln_intensity_p"],
            "source": scale["source"],
            "interpretation": "HC3 descriptive OLS coefficient; not causal",
        },
        {
            "metric": "descriptive_ols_r2",
            "estimate": scale["ols_r2"],
            "p_value": "",
            "source": scale["source"],
            "interpretation": "Model fit for m3 descriptive OLS",
        },
    ]

    # Window robustness:
    # compare the same concentration measures across the 24m and 30m samples.
    # This tests whether the substantive H1 concentration conclusion depends
    # strongly on the chosen observation window.
    comp_rows = []
    if "revised-24m" in results and "revised-30m" in results:
        left = results["revised-24m"]["main"]
        right = results["revised-30m"]["main"]
        for k in METRICS:
            av, bv = left[k], right[k]
            delta = bv - av
            rel = (delta / abs(av) * 100.0) if av != 0 else float("nan")
            comp_rows.append(
                {
                    "metric": k,
                    "revised-24m": av,
                    "revised-30m": bv,
                    "abs_change_right_minus_left": delta,
                    "rel_change_pct": rel,
                }
            )

    # Cross-window rank persistence:
    # examines whether high-volume addresses retain similar positions when the
    # sample is extended from 24m to 30m. This is a stability/continuity check,
    # not evidence about infrastructure or causal advantage.
    rank_ret, rank_trans, rank_stats = [], [], None
    if "revised-24m" in results and "revised-30m" in results:
        left = results["revised-24m"]["vol_by_addr"]
        right = results["revised-30m"]["vol_by_addr"]
        rl, rr = rank_map(left), rank_map(right)
        common = sorted(set(rl) & set(rr))
        rho = spearman(left, right)

        # IMPORTANT LIMITATION:
        # revised-24m is nested inside revised-30m, so the two rankings are not
        # independent and share much of the same underlying transactions.
        # A permutation null based on random pairing would therefore be too
        # strong and would overstate the evidence for genuine out-of-sample
        # persistence. We keep Spearman rho, top-k retention, and transitions
        # as descriptive stability checks only.
        n1, n2 = len(rl), len(rr)
        k1 = max(1, int(math.ceil(0.01 * n1)))
        k2 = max(1, int(math.ceil(0.01 * n2)))

        for k in sorted(set([1, 4, 10, 20, min(k1, k2)])):
            a_set = set(top_k(left, k))
            b_set = set(top_k(right, k))
            rank_ret.append(
                {
                    "k": k,
                    "retention_revised-24m_in_revised-30m": len(a_set & b_set)
                    / max(1, len(a_set)),
                    "intersection_count": len(a_set & b_set),
                }
            )

        groups = ["top_1pct", "top_5pct", "top_10pct", "rest_90pct"]
        cnt = {(g1, g2): 0 for g1 in groups for g2 in groups}
        for addr in common:
            g1 = rank_group(rl[addr], n1)
            g2 = rank_group(rr[addr], n2)
            cnt[(g1, g2)] += 1

        for g1 in groups:
            total = sum(cnt[(g1, g2)] for g2 in groups)
            for g2 in groups:
                c = cnt[(g1, g2)]
                rank_trans.append(
                    {
                        "from_group": g1,
                        "to_group": g2,
                        "count": c,
                        "row_share": c / total if total else float("nan"),
                    }
                )
        rank_stats = {
            "common": len(common),
            "rho": rho,
            "formal_test_performed": False,
            "formal_test_reason": (
                "Not performed because revised-24m and revised-30m are nested/overlapping; "
                "random-pairing permutation inference would overstate persistence."
            ),
        }

    td = out / "tables"
    rd = out / "reports"

    write_csv(
        td / "h1_summary_metrics.csv",
        rows_summary,
        [
            "window",
            "analysis_role",
            "gini",
            "gini_ci_low",
            "gini_ci_high",
            "top_1pct_share",
            "top_1pct_ci_low",
            "top_1pct_ci_high",
            "cr1",
            "cr4",
            "cr10",
            "cr20",
            "hhi",
            "gini_operational_benchmark",
            "gini_ci_low_above_benchmark",
        ],
    )
    write_csv(
        td / "h1_topk_exclusion_sensitivity.csv",
        rows_excl,
        [
            "window",
            "scenario",
            "gini",
            "top_1pct_share",
            "cr1",
            "cr4",
            "cr10",
            "cr20",
            "hhi",
            "remaining_n",
        ],
    )
    write_csv(
        td / "h1_address_clustering_sensitivity.csv",
        rows_cluster,
        [
            "window",
            "scenario",
            "gini",
            "top_1pct_share",
            "cr1",
            "cr4",
            "cr10",
            "cr20",
            "hhi",
            "result_n",
        ],
    )
    write_csv(
        td / "h1_scale_activity_association.csv",
        scale_rows,
        ["metric", "estimate", "p_value", "source", "interpretation"],
    )

    benchmark_rows = []
    for w in windows:
        bg = results[w]["boot"]["gini"]
        benchmark_rows.append(
            {
                "window": w,
                "analysis_role": "primary" if w == primary else "robustness",
                "metric": "gini",
                "estimate": results[w]["main"]["gini"],
                "operational_benchmark": GINI_BENCHMARK,
                "bootstrap_ci_low": bg["ci_low"],
                "bootstrap_ci_high": bg["ci_high"],
                "ci_low_above_benchmark": bg["ci_low"] > GINI_BENCHMARK,
                "interpretation": (
                    "Address-resampling robustness relative to an operational "
                    "reference; not a formal null-hypothesis test."
                ),
            }
        )

    # Delete the obsolete formal-test output from earlier versions so stale
    # p-values cannot be mistaken for current results.
    stale_formal = td / "h1_formal_hypothesis_tests.csv"
    if stale_formal.exists():
        stale_formal.unlink()

    write_csv(
        td / "h1_gini_benchmark_robustness.csv",
        benchmark_rows,
        [
            "window",
            "analysis_role",
            "metric",
            "estimate",
            "operational_benchmark",
            "bootstrap_ci_low",
            "bootstrap_ci_high",
            "ci_low_above_benchmark",
            "interpretation",
        ],
    )

    # Always overwrite conditional outputs, even when empty, so stale results
    # from a previous run cannot be mistaken for outputs from the current run.
    write_csv(
        td / "h1_window_robustness_24m_vs_30m.csv",
        comp_rows,
        [
            "metric",
            "revised-24m",
            "revised-30m",
            "abs_change_right_minus_left",
            "rel_change_pct",
        ],
    )
    write_csv(
        td / "h1_rank_retention_24m_vs_30m.csv",
        rank_ret,
        ["k", "retention_revised-24m_in_revised-30m", "intersection_count"],
    )
    write_csv(
        td / "h1_rank_transition_matrix_24m_vs_30m.csv",
        rank_trans,
        ["from_group", "to_group", "count", "row_share"],
    )

    rp = results[primary]

    lines = [
        "# H1 Hypothesis Testing",
        "",
        "## Scope",
        "",
        "- H1a: concentration exists in observed sandwich transaction volume across bot addresses.",
        "- H1b mechanism evidence is separated into two parts: operational scale/persistence associations are testable descriptively; infrastructure speed and trading-signal quality are not directly measured.",
        "- The scale/activity results below reuse the canonical diagnostics produced by `m3_bot_dynamics.py`; they are not recalculated here.",
        "",
        "## Methods implemented",
        "",
        f"- Primary analysis window: `{primary}` (fixed by research design).",
        "- `revised-30m` is used only as a robustness/sensitivity window.",
        f"- Address-level bootstrap resamples (main concentration metrics): {bootstrap_resamples}",
        "- Metrics: Gini, Top 1% share (using ceiling(1% of N) addresses), CR1, CR4, CR10, CR20, HHI",
        f"- Primary concentration evidence: continuous Gini estimate in `{primary}`, with address-resampling bootstrap interval.",
        "- Gini=0.90 is retained only as a deliberately stringent operational reference for extreme concentration; no benchmark p-value or reject/do-not-reject decision is calculated.",
        "- Top 1% share is reported directly as an interpretable concentration measure; no 90% null hypothesis is imposed on it.",
        "- Results in the non-primary window are robustness/sensitivity checks rather than independent replication.",
        "- Sensitivity: largest-bot exclusion; top-k exclusions; positive-volume-only; illustrative hypothetical address-clustering stress scenarios",
        "- Window robustness: 24m vs 30m",
        "- Rank persistence: Spearman, top-k retention, and transition matrix are reported descriptively. No formal permutation p-value is reported because the 24m and 30m windows overlap.",
        "- Scale/activity evidence: canonical m3 Spearman permutation tests, persistent-bot volume share, and descriptive HC3 OLS",
        "",
    ]

    for w in windows:
        r = results[w]
        m, b, p = r["main"], r["boot"], r["positive"]
        lines += [
            f"## Window: {w}",
            "",
            f"- Source file: `{r['path']}`; rows={r['rows']}, measurable volumes={r['measurable_n']}, positive volumes={r['positive_n']}",
            f"- Gini: {num(m['gini'])} (95% bootstrap interval {num(b['gini']['ci_low'])} to {num(b['gini']['ci_high'])})",
            f"- Top 1% share: {pct(m['top_1pct_share'])} (95% bootstrap interval {pct(b['top_1pct_share']['ci_low'])} to {pct(b['top_1pct_share']['ci_high'])})",
            f"- CR1={pct(m['cr1'])}, CR4={pct(m['cr4'])}, CR10={pct(m['cr10'])}, CR20={pct(m['cr20'])}",
            f"- HHI={num(m['hhi'],1)}",
            f"- Gini robustness relative to the operational 0.90 reference: 95% address-resampling interval={num(b['gini']['ci_low'])} to {num(b['gini']['ci_high'])}; lower endpoint above 0.90={b['gini']['ci_low'] > GINI_BENCHMARK}.",
            f"- Top 1% share robustness: 95% address-resampling interval={pct(b['top_1pct_share']['ci_low'])} to {pct(b['top_1pct_share']['ci_high'])}. No threshold test is imposed on Top 1% share.",
            f"- Positive-volume-only sensitivity: Gini={num(p['gini'])}, Top 1% share={pct(p['top_1pct_share'])}, CR4={pct(p['cr4'])}, HHI={num(p['hhi'],1)}",
            "",
            "### Top-k exclusion sensitivity",
            "",
            "| Scenario | Gini | Top 1% | CR4 | CR10 | HHI | Remaining N |",
            "|---|---:|---:|---:|---:|---:|---:|",
        ]
        for x in r["exclusions"]:
            lines.append(
                f"| {x['scenario']} | {num(x['gini'])} | {pct(x['top_1pct_share'])} | {pct(x['cr4'])} | {pct(x['cr10'])} | {num(x['hhi'],1)} | {x['remaining_n']} |"
            )

        lines += [
            "",
            "### Address-clustering sensitivity",
            "",
            "| Scenario | Gini | Top 1% | CR4 | CR10 | HHI | Result N |",
            "|---|---:|---:|---:|---:|---:|---:|",
        ]
        for x in r["clusters"]:
            lines.append(
                f"| {x['scenario']} | {num(x['gini'])} | {pct(x['top_1pct_share'])} | {pct(x['cr4'])} | {pct(x['cr10'])} | {num(x['hhi'],1)} | {x['result_n']} |"
            )
        lines.append("")

    lines += [
        "## Operational scale and persistence",
        "",
        f"- Source: `{scale['source']}` (generated by `m3_bot_dynamics.py`).",
        f"- Spearman(volume, days active) = {num(scale['rho_volume_days_active'])}, permutation p = {num(scale['p_volume_days_active'],6)}.",
        f"- Spearman(volume, total trades) = {num(scale['rho_volume_total_trades'])}, permutation p = {num(scale['p_volume_total_trades'],6)}.",
        f"- Spearman(volume, average trade size) = {num(scale['rho_volume_avg_trade_size'])}, permutation p = {num(scale['p_volume_avg_trade_size'],6)}.",
        f"- Bots active at least 30 days account for {pct(scale['persistent_volume_share'])} of positive-volume sandwich transaction volume.",
        f"- Descriptive HC3 OLS: ln(days active) coefficient = {num(scale['ols_ln_days_active'])}, ln(intensity) coefficient = {num(scale['ols_ln_intensity'])}, R2 = {num(scale['ols_r2'])}.",
        "",
        "**Interpretation.** These results provide strong descriptive evidence that greater operational scale, activity and persistence are associated with greater total sandwich transaction volume. They do not establish that scale causes success. Total volume is algebraically related to trade count and average trade size, and the available data do not provide exogenous variation or direct measures of infrastructure speed or trading-signal quality.",
        "",
    ]

    if comp_rows:
        lines += [
            "## 24m vs 30m robustness",
            "",
            "| Metric | 24m | 30m | Abs Change (30m-24m) | Relative Change |",
            "|---|---:|---:|---:|---:|",
        ]
        for r in comp_rows:
            if r["metric"] == "hhi":
                lines.append(
                    f"| {r['metric']} | {num(r['revised-24m'],1)} | {num(r['revised-30m'],1)} | {num(r['abs_change_right_minus_left'],1)} | {num(r['rel_change_pct'],2)}% |"
                )
            else:
                lines.append(
                    f"| {r['metric']} | {pct(r['revised-24m'])} | {pct(r['revised-30m'])} | {pct(r['abs_change_right_minus_left'])} | {num(r['rel_change_pct'],2)}% |"
                )
        lines.append("")

    if rank_stats is not None:
        lines += [
            "## Rank persistence and top-bot retention",
            "",
            f"- Common positive-volume addresses: {rank_stats['common']}; Spearman rank correlation={num(rank_stats['rho'])}",
            f"- Formal rank-persistence test not performed: {rank_stats['formal_test_reason']}",
            "",
            "| k | Retention | Intersection Count |",
            "|---:|---:|---:|",
        ]
        for rr in rank_ret:
            lines.append(
                f"| {rr['k']} | {pct(rr['retention_revised-24m_in_revised-30m'])} | {rr['intersection_count']} |"
            )
        lines.append("")

    pm, pb = rp["main"], rp["boot"]
    ex1 = next(
        (x for x in rp["exclusions"] if x["scenario"] == "exclude_top_1"),
        None,
    )

    lines += [
        "## Statistical limitations",
        "",
        "- Gini=0.90 is an operational reference, not a universally accepted statistical definition of winner-take-most concentration. The continuous estimate, bootstrap interval, and sensitivity analyses carry the evidentiary weight.",
        "- Top 1% share is reported as a continuous descriptive concentration measure; no 90% hypothesis-test threshold is imposed on it.",
        f"- Analysis hierarchy: `{primary}` is the primary window; non-primary-window results are robustness checks rather than independent tests.",
        "- Bootstrap uncertainty is based on resampling observed bot addresses. Because these data may approximate a census rather than a probability sample, the bootstrap is interpreted as address-resampling robustness rather than classical sampling uncertainty.",
        "- Bot addresses are not necessarily unique economic operators, so address-level concentration can differ from true operator-level concentration.",
        "- Address-clustering results are illustrative deterministic stress scenarios, not estimated ownership structures or evidence that particular addresses share an operator.",
        "- The 24m and 30m windows overlap. Cross-window Spearman correlation and retention are therefore descriptive stability checks, not independent replication or formal evidence of persistence beyond the shared sample.",
        "- None of these tests identifies faster infrastructure, superior signals, or other causal mechanisms.",
        "",
        "## Conclusions from data",
        "",
        f"- H1 concentration outcome: In {primary}, concentration is high: Gini={num(pm['gini'])}, Top 1% share={pct(pm['top_1pct_share'])}, CR4={pct(pm['cr4'])}, CR10={pct(pm['cr10'])}, CR20={pct(pm['cr20'])}, HHI={num(pm['hhi'],1)}.",
        f"- Gini robustness in {primary}: 95% address-resampling interval [{num(pb['gini']['ci_low'])}, {num(pb['gini']['ci_high'])}]; its lower endpoint is compared with Gini=0.90 only as an operational reference.",
        f"- Top 1% concentration in {primary}: estimate={pct(pm['top_1pct_share'])}, with 95% address-resampling interval [{pct(pb['top_1pct_share']['ci_low'])}, {pct(pb['top_1pct_share']['ci_high'])}]. No 90% threshold test or benchmark p-value is used.",
        (
            f"- After excluding the largest bot, concentration remains high: Gini={num(ex1['gini'])}, Top 1% share={pct(ex1['top_1pct_share'])}, CR4={pct(ex1['cr4'])}, HHI={num(ex1['hhi'],1)}."
            if ex1 is not None
            else "- Largest-bot exclusion sensitivity is unavailable because the primary window contains fewer than two measurable addresses."
        ),
        f"- Scale/activity association: volume is strongly associated with days active (rho={num(scale['rho_volume_days_active'])}), total trades (rho={num(scale['rho_volume_total_trades'])}), and average trade size (rho={num(scale['rho_volume_avg_trade_size'])}); persistent bots account for {pct(scale['persistent_volume_share'])} of positive-volume sandwich transaction volume.",
        "- Mechanism boundary: these scale/activity relationships are descriptive and partly mechanical; causal attribution to faster infrastructure or better trading signals is not identified by the available data.",
    ]

    if comp_rows:
        g = next(x for x in comp_rows if x["metric"] == "gini")
        t = next(x for x in comp_rows if x["metric"] == "top_1pct_share")
        lines.append(
            f"- 24m vs 30m robustness: Gini change={num(g['abs_change_right_minus_left'])}, Top 1% share change={pct(t['abs_change_right_minus_left'])}."
        )
    if rank_stats is not None:
        lines.append(
            f"- Rank persistence across windows: Spearman rank correlation={num(rank_stats['rho'])} on {rank_stats['common']} common addresses. This is descriptive only because the 24m and 30m windows overlap; no formal permutation p-value is reported."
        )

    lines.append("")
    rd.mkdir(parents=True, exist_ok=True)
    (rd / "h1_hypothesis_tests.md").write_text("\n".join(lines), encoding="utf-8")
    print("[PASS] m8_hypothesis_tests completed: H1 concentration and scale/activity synthesis generated.")


def main():
    a = parse_args()
    run_h1_tests(
        data_root=a.data_root,
        windows=a.windows,
        bootstrap_resamples=a.bootstrap_resamples,
        seed=a.seed,
        output_dir=a.output_dir,
    )


if __name__ == "__main__":
    main()
