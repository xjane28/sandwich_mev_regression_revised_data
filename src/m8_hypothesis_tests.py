from __future__ import annotations

import argparse
import csv
import hashlib
import math
import random
from collections import defaultdict
from datetime import datetime
from pathlib import Path

METRICS = ["gini", "top_1pct_share", "cr1", "cr4", "cr10", "cr20", "hhi"]
THRESHOLDS = {"gini": 0.90, "top_1pct_share": 0.90}


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--data-root", default="fetch/data")
    p.add_argument("--windows", default="revised-24m,revised-30m")
    p.add_argument("--primary-window", default="revised-24m")
    p.add_argument("--bootstrap-resamples", type=int, default=10000)
    p.add_argument("--period-bootstrap-resamples", type=int, default=2000)
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


def f(x):
    if x is None:
        return None
    s = str(x).strip()
    if s == "":
        return None
    try:
        return float(s.replace(",", ""))
    except ValueError:
        return None


def find_col(cols, keys):
    low = [c.lower() for c in cols]
    for k in keys:
        for i, c in enumerate(low):
            if k in c:
                return cols[i]
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


def bootstrap(vals, nboot, seed):
    rng = random.Random(seed)
    x = [v for v in vals if v is not None and v >= 0]
    n = len(x)
    draws = {k: [] for k in METRICS}
    for _ in range(nboot):
        samp = [x[rng.randrange(n)] for _ in range(n)]
        m = concentration(samp)
        for k in METRICS:
            draws[k].append(m[k])
    out = {}
    for k, arr in draws.items():
        arrs = sorted(arr)
        pv = None
        rej = None
        if k in THRESHOLDS:
            t = THRESHOLDS[k]
            pv = (sum(1 for v in arr if v <= t) + 1.0) / (len(arr) + 1.0)
            rej = pv < 0.05
        out[k] = {
            "mean": sum(arr) / len(arr),
            "ci_low": q(arrs, 0.025),
            "ci_high": q(arrs, 0.975),
            "threshold": THRESHOLDS.get(k),
            "p_one_sided": pv,
            "reject_h0": rej,
        }
    return out


def stable_offset(text):
    return int(hashlib.sha256(text.encode("utf-8")).hexdigest()[:12], 16) % 1000000


def infer_month(s):
    s = str(s).strip()
    if len(s) >= 7 and s[4] == "-":
        return s[:7]
    for fmt in ["%Y-%m-%d", "%Y/%m/%d", "%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S"]:
        try:
            dt = datetime.strptime(s[:19], fmt)
            return f"{dt.year:04d}-{dt.month:02d}"
        except ValueError:
            pass
    return None


def month_to_quarter(m):
    y = int(m[:4])
    mo = int(m[5:7])
    return f"{y:04d}-Q{((mo - 1) // 3) + 1}"


def slope(y):
    n = len(y)
    if n < 2:
        return float("nan")
    xm = (n - 1) / 2.0
    ym = sum(y) / n
    num = sum((i - xm) * (v - ym) for i, v in enumerate(y))
    den = sum((i - xm) ** 2 for i in range(n))
    return num / den if den else float("nan")


def changepoint(periods, y):
    n = len(y)
    if n < 6:
        return {"available": False, "reason": "insufficient_periods"}
    best = None
    for t in range(2, n - 2):
        l = y[:t]
        r = y[t:]
        lm = sum(l) / len(l)
        rm = sum(r) / len(r)
        sse = sum((v - lm) ** 2 for v in l) + sum((v - rm) ** 2 for v in r)
        if best is None or sse < best[0]:
            best = (sse, t, lm, rm)
    _, t, lm, rm = best
    return {
        "available": True,
        "split_period": periods[t],
        "mean_before": lm,
        "mean_after": rm,
        "delta_after_minus_before": rm - lm,
    }


def find_period_file(window_dir: Path):
    fixed = [
        "query3_bot_volume_by_month_v2.csv",
        "query3_full_bot_distribution_monthly_v2.csv",
        "query3_bot_volume_by_period_v2.csv",
        "query3_full_bot_distribution_time_v2.csv",
        "query3_bot_volume_monthly_v2.csv",
    ]
    for n in fixed:
        p = window_dir / n
        if p.exists():
            return p
    cands = sorted(window_dir.glob("query3*month*.csv")) + sorted(window_dir.glob("query3*period*.csv"))
    return cands[0] if cands else None


def rank_map(vol_by_addr):
    pairs = sorted([(a, v) for a, v in vol_by_addr.items() if v is not None and v > 0], key=lambda t: (-t[1], t[0]))
    return {a: i + 1 for i, (a, _) in enumerate(pairs)}


def spearman(r1, r2):
    common = sorted(set(r1) & set(r2))
    n = len(common)
    if n < 2:
        return None
    d2 = sum((r1[a] - r2[a]) ** 2 for a in common)
    return 1.0 - (6.0 * d2) / (n * (n * n - 1.0))


def top_k(vol_by_addr, k):
    pairs = sorted([(a, v) for a, v in vol_by_addr.items() if v is not None and v > 0], key=lambda t: (-t[1], t[0]))
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


def load_window(window_name, window_dir, nboot, nboot_period, seed):
    q3 = window_dir / "query3_full_bot_distribution_v2.csv"
    if not q3.exists():
        alts = sorted(window_dir.glob("query3*full*distribution*.csv")) + sorted(window_dir.glob("query3*distribution*.csv"))
        if alts:
            q3 = alts[0]
    rows = read_csv(q3)
    cols = list(rows[0].keys())
    addr_col = find_col(cols, ["bot_address", "address", "searcher"])
    vol_col = find_col(cols, ["volume_usd", "sandwich_volume_usd", "total_volume_usd", "volume"])
    vol_by_addr = {}
    measurable = []
    positive = []
    for r in rows:
        a = str(r.get(addr_col, "")).strip()
        v = f(r.get(vol_col))
        if a and v is not None:
            vol_by_addr[a] = v
            measurable.append(v)
            if v > 0:
                positive.append(v)

    m = concentration(measurable)
    b = bootstrap(measurable, nboot, seed)
    mp = concentration(positive)

    def excl(k):
        s = sorted([v for v in measurable if v is not None and v >= 0], reverse=True)
        rem = s[k:] if k < len(s) else []
        return {"window": window_name, "scenario": f"exclude_top_{k}", **concentration(rem), "remaining_n": len(rem)}

    exclusions = [excl(1), excl(5), excl(10)]

    def cluster(top_n, groups):
        s = sorted([v for v in measurable if v is not None and v >= 0], reverse=True)
        top_n = min(top_n, len(s))
        groups = max(1, min(groups, top_n if top_n else 1))
        head, tail = s[:top_n], s[top_n:]
        merged = [0.0] * groups
        for i, v in enumerate(head):
            merged[i % groups] += v
        z = merged + tail
        return {"window": window_name, "scenario": f"merge_top_{top_n}_into_{groups}", **concentration(z), "result_n": len(z)}

    clusters = [cluster(5, 1), cluster(10, 2), cluster(20, 4)]

    monthly_rows, quarterly_rows = [], []
    stability = {"available": False, "reason": "period_file_not_found"}
    pfile = find_period_file(window_dir)
    if pfile is not None:
        r = read_csv(pfile)
        cols = list(r[0].keys()) if r else []
        a_col = find_col(cols, ["bot_address", "address", "searcher"])
        v_col = find_col(cols, ["volume_usd", "sandwich_volume_usd", "total_volume_usd", "volume"])
        t_col = find_col(cols, ["month", "period", "date", "bucket"])
        if a_col and v_col and t_col:
            by_month = defaultdict(lambda: defaultdict(float))
            for row in r:
                month = infer_month(row.get(t_col, ""))
                addr = str(row.get(a_col, "")).strip()
                vol = f(row.get(v_col))
                if month and addr and vol is not None and vol >= 0:
                    by_month[month][addr] += vol
            by_quarter = defaultdict(list)
            for month in sorted(by_month):
                vals = list(by_month[month].values())
                mm = concentration(vals)
                bb = bootstrap(vals, nboot_period, seed + stable_offset(month))
                monthly_rows.append({
                    "window": window_name,
                    "period": month,
                    "n_addresses": len(vals),
                    "gini": mm["gini"],
                    "gini_ci_low": bb["gini"]["ci_low"],
                    "gini_ci_high": bb["gini"]["ci_high"],
                    "top_1pct_share": mm["top_1pct_share"],
                    "top_1pct_ci_low": bb["top_1pct_share"]["ci_low"],
                    "top_1pct_ci_high": bb["top_1pct_share"]["ci_high"],
                    "cr4": mm["cr4"],
                    "cr10": mm["cr10"],
                    "hhi": mm["hhi"],
                })
                by_quarter[month_to_quarter(month)].extend(vals)
            for qtr in sorted(by_quarter):
                vals = by_quarter[qtr]
                mm = concentration(vals)
                bb = bootstrap(vals, nboot_period, seed + stable_offset(qtr))
                quarterly_rows.append({
                    "window": window_name,
                    "period": qtr,
                    "n_addresses": len(vals),
                    "gini": mm["gini"],
                    "gini_ci_low": bb["gini"]["ci_low"],
                    "gini_ci_high": bb["gini"]["ci_high"],
                    "top_1pct_share": mm["top_1pct_share"],
                    "top_1pct_ci_low": bb["top_1pct_share"]["ci_low"],
                    "top_1pct_ci_high": bb["top_1pct_share"]["ci_high"],
                    "cr4": mm["cr4"],
                    "cr10": mm["cr10"],
                    "hhi": mm["hhi"],
                })
            if monthly_rows:
                gs = [r["gini"] for r in monthly_rows]
                ts = [r["top_1pct_share"] for r in monthly_rows]
                ps = [r["period"] for r in monthly_rows]
                stability = {
                    "available": True,
                    "months_count": len(monthly_rows),
                    "share_months_gini_gt_0_90": sum(1 for x in gs if x > 0.90) / len(gs),
                    "share_months_top1pct_gt_0_90": sum(1 for x in ts if x > 0.90) / len(ts),
                    "gini_trend_slope_per_month": slope(gs),
                    "top1pct_trend_slope_per_month": slope(ts),
                    "gini_changepoint": changepoint(ps, gs),
                    "top1pct_changepoint": changepoint(ps, ts),
                }

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
        "monthly": monthly_rows,
        "quarterly": quarterly_rows,
        "stability": stability,
    }


def pct(x):
    return "NA" if x is None or (isinstance(x, float) and math.isnan(x)) else f"{100*x:.2f}%"


def num(x, d=4):
    return "NA" if x is None or (isinstance(x, float) and math.isnan(x)) else f"{x:.{d}f}"


def main():
    a = parse_args()
    data_root = Path(a.data_root)
    out = Path(a.output_dir)
    windows = [w.strip() for w in a.windows.split(",") if w.strip()]

    results = {}
    for i, w in enumerate(windows):
        results[w] = load_window(w, data_root / w, a.bootstrap_resamples, a.period_bootstrap_resamples, a.seed + i * 1000)

    rows_summary = []
    rows_excl = []
    rows_cluster = []
    rows_month = []
    rows_qtr = []
    for w in windows:
        r = results[w]
        m, b = r["main"], r["boot"]
        rows_summary.append({
            "window": w,
            "gini": m["gini"],
            "gini_ci_low": b["gini"]["ci_low"],
            "gini_ci_high": b["gini"]["ci_high"],
            "top_1pct_share": m["top_1pct_share"],
            "top_1pct_ci_low": b["top_1pct_share"]["ci_low"],
            "top_1pct_ci_high": b["top_1pct_share"]["ci_high"],
            "cr1": m["cr1"], "cr4": m["cr4"], "cr10": m["cr10"], "cr20": m["cr20"], "hhi": m["hhi"],
            "benchmark_gini_threshold": THRESHOLDS["gini"],
            "benchmark_gini_pvalue_one_sided": b["gini"]["p_one_sided"],
            "benchmark_top1pct_threshold": THRESHOLDS["top_1pct_share"],
            "benchmark_top1pct_pvalue_one_sided": b["top_1pct_share"]["p_one_sided"],
        })
        rows_excl.extend(r["exclusions"])
        rows_cluster.extend(r["clusters"])
        rows_month.extend(r["monthly"])
        rows_qtr.extend(r["quarterly"])

    comp_rows = []
    if "revised-24m" in results and "revised-30m" in results:
        l = results["revised-24m"]["main"]
        r = results["revised-30m"]["main"]
        for k in METRICS:
            av, bv = l[k], r[k]
            delta = bv - av
            rel = (delta / abs(av) * 100.0) if av != 0 else float("nan")
            comp_rows.append({"metric": k, "revised-24m": av, "revised-30m": bv, "abs_change_right_minus_left": delta, "rel_change_pct": rel})

    rank_ret, rank_trans, rank_stats = [], [], None
    if "revised-24m" in results and "revised-30m" in results:
        left = results["revised-24m"]["vol_by_addr"]
        right = results["revised-30m"]["vol_by_addr"]
        rl, rr = rank_map(left), rank_map(right)
        common = sorted(set(rl) & set(rr))
        rho = spearman(rl, rr)
        n1, n2 = len(rl), len(rr)
        k1 = max(1, int(math.ceil(0.01 * n1)))
        k2 = max(1, int(math.ceil(0.01 * n2)))
        for k in sorted(set([1, 4, 10, 20, min(k1, k2)])):
            a_set = set(top_k(left, k))
            b_set = set(top_k(right, k))
            rank_ret.append({"k": k, "retention_revised-24m_in_revised-30m": len(a_set & b_set) / max(1, len(a_set)), "intersection_count": len(a_set & b_set)})
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
                rank_trans.append({"from_group": g1, "to_group": g2, "count": c, "row_share": (c / total if total else float("nan"))})
        rank_stats = {"common": len(common), "rho": rho}

    td = out / "tables"
    rd = out / "reports"
    write_csv(td / "h1_summary_metrics.csv", rows_summary, ["window", "gini", "gini_ci_low", "gini_ci_high", "top_1pct_share", "top_1pct_ci_low", "top_1pct_ci_high", "cr1", "cr4", "cr10", "cr20", "hhi", "benchmark_gini_threshold", "benchmark_gini_pvalue_one_sided", "benchmark_top1pct_threshold", "benchmark_top1pct_pvalue_one_sided"])
    write_csv(td / "h1_topk_exclusion_sensitivity.csv", rows_excl, ["window", "scenario", "gini", "top_1pct_share", "cr1", "cr4", "cr10", "cr20", "hhi", "remaining_n"])
    write_csv(td / "h1_address_clustering_sensitivity.csv", rows_cluster, ["window", "scenario", "gini", "top_1pct_share", "cr1", "cr4", "cr10", "cr20", "hhi", "result_n"])
    if comp_rows:
        write_csv(td / "h1_window_robustness_24m_vs_30m.csv", comp_rows, ["metric", "revised-24m", "revised-30m", "abs_change_right_minus_left", "rel_change_pct"])
    if rank_ret:
        write_csv(td / "h1_rank_retention_24m_vs_30m.csv", rank_ret, ["k", "retention_revised-24m_in_revised-30m", "intersection_count"])
    if rank_trans:
        write_csv(td / "h1_rank_transition_matrix_24m_vs_30m.csv", rank_trans, ["from_group", "to_group", "count", "row_share"])
    if rows_month:
        write_csv(td / "h1_monthly_concentration.csv", rows_month, ["window", "period", "n_addresses", "gini", "gini_ci_low", "gini_ci_high", "top_1pct_share", "top_1pct_ci_low", "top_1pct_ci_high", "cr4", "cr10", "hhi"])
    if rows_qtr:
        write_csv(td / "h1_quarterly_concentration.csv", rows_qtr, ["window", "period", "n_addresses", "gini", "gini_ci_low", "gini_ci_high", "top_1pct_share", "top_1pct_ci_low", "top_1pct_ci_high", "cr4", "cr10", "hhi"])

    primary = a.primary_window if a.primary_window in results else windows[0]
    rp = results[primary]
    lines = ["# H1 Hypothesis Testing", "", "## Scope", "", "- H1a: concentration exists in sandwich-MEV volume captured by bot addresses.", "- H1b: concentration is caused by scale/infrastructure advantages.", "- This script tests H1a directly and reports H1b as non-identified in the available files.", "", "## Methods implemented", "", f"- Bootstrap resamples (main): {a.bootstrap_resamples}", f"- Bootstrap resamples (monthly/quarterly): {a.period_bootstrap_resamples}", "- Metrics: Gini, Top 1% share, CR1, CR4, CR10, CR20, HHI", "- One-sided benchmark tests: Gini > 0.90; Top 1% share > 90%", "- Sensitivity: largest-bot exclusion; top-k exclusions; positive-volume-only; clustering scenarios", "- Time checks: monthly/quarterly concentration and stability when period-level files are available", "- Window robustness: 24m vs 30m", "- Rank persistence: Spearman, top-k retention, transition matrix", ""]
    for w in windows:
        r = results[w]
        m, b, p = r["main"], r["boot"], r["positive"]
        lines += [f"## Window: {w}", "", f"- Source file: `{r['path']}`; rows={r['rows']}, measurable volumes={r['measurable_n']}, positive volumes={r['positive_n']}", f"- Gini: {num(m['gini'])} (95% CI {num(b['gini']['ci_low'])} to {num(b['gini']['ci_high'])})", f"- Top 1% share: {pct(m['top_1pct_share'])} (95% CI {pct(b['top_1pct_share']['ci_low'])} to {pct(b['top_1pct_share']['ci_high'])})", f"- CR1={pct(m['cr1'])}, CR4={pct(m['cr4'])}, CR10={pct(m['cr10'])}, CR20={pct(m['cr20'])}", f"- HHI={num(m['hhi'],1)}", f"- Benchmark test Gini>0.90: p={num(b['gini']['p_one_sided'],6)}, reject_h0={b['gini']['reject_h0']}", f"- Benchmark test Top1%>90%: p={num(b['top_1pct_share']['p_one_sided'],6)}, reject_h0={b['top_1pct_share']['reject_h0']}", f"- Positive-volume-only sensitivity: Gini={num(p['gini'])}, Top 1% share={pct(p['top_1pct_share'])}, CR4={pct(p['cr4'])}, HHI={num(p['hhi'],1)}", "", "### Top-k exclusion sensitivity", "", "| Scenario | Gini | Top 1% | CR4 | CR10 | HHI | Remaining N |", "|---|---:|---:|---:|---:|---:|---:|"]
        for x in r["exclusions"]:
            lines.append(f"| {x['scenario']} | {num(x['gini'])} | {pct(x['top_1pct_share'])} | {pct(x['cr4'])} | {pct(x['cr10'])} | {num(x['hhi'],1)} | {x['remaining_n']} |")
        lines += ["", "### Address-clustering sensitivity", "", "| Scenario | Gini | Top 1% | CR4 | CR10 | HHI | Result N |", "|---|---:|---:|---:|---:|---:|---:|"]
        for x in r["clusters"]:
            lines.append(f"| {x['scenario']} | {num(x['gini'])} | {pct(x['top_1pct_share'])} | {pct(x['cr4'])} | {pct(x['cr10'])} | {num(x['hhi'],1)} | {x['result_n']} |")
        s = r["stability"]
        lines += ["", "### Time stability", ""]
        if s.get("available"):
            lines.append(f"- Months analyzed: {s['months_count']}; share months with Gini>0.90={pct(s['share_months_gini_gt_0_90'])}; share months with Top1%>90%={pct(s['share_months_top1pct_gt_0_90'])}")
            lines.append(f"- Monthly trend slope: Gini={num(s['gini_trend_slope_per_month'])}, Top1%={num(s['top1pct_trend_slope_per_month'])}")
            gc, tc = s.get("gini_changepoint", {}), s.get("top1pct_changepoint", {})
            if gc.get("available"):
                lines.append(f"- Gini changepoint split at {gc['split_period']}: before={num(gc['mean_before'])}, after={num(gc['mean_after'])}, delta={num(gc['delta_after_minus_before'])}")
            if tc.get("available"):
                lines.append(f"- Top1% changepoint split at {tc['split_period']}: before={pct(tc['mean_before'])}, after={pct(tc['mean_after'])}, delta={pct(tc['delta_after_minus_before'])}")
        else:
            lines.append(f"- Period-level concentration test unavailable: {s.get('reason')}")
        lines.append("")

    if comp_rows:
        lines += ["## 24m vs 30m robustness", "", "| Metric | 24m | 30m | Abs Change (30m-24m) | Relative Change |", "|---|---:|---:|---:|---:|"]
        for r in comp_rows:
            if r["metric"] == "hhi":
                lines.append(f"| {r['metric']} | {num(r['revised-24m'],1)} | {num(r['revised-30m'],1)} | {num(r['abs_change_right_minus_left'],1)} | {num(r['rel_change_pct'],2)}% |")
            else:
                lines.append(f"| {r['metric']} | {pct(r['revised-24m'])} | {pct(r['revised-30m'])} | {pct(r['abs_change_right_minus_left'])} | {num(r['rel_change_pct'],2)}% |")
        lines.append("")

    if rank_stats is not None:
        lines += ["## Rank persistence and top-bot retention", "", f"- Common positive-volume addresses: {rank_stats['common']}; Spearman rank correlation={num(rank_stats['rho'])}", "", "| k | Retention | Intersection Count |", "|---:|---:|---:|"]
        for rr in rank_ret:
            lines.append(f"| {rr['k']} | {pct(rr['retention_revised-24m_in_revised-30m'])} | {rr['intersection_count']} |")
        lines.append("")

    pm, pb = rp["main"], rp["boot"]
    ex1 = rp["exclusions"][0]
    lines += ["## Conclusions from data", "", f"- H1a: In {primary}, concentration is high: Gini={num(pm['gini'])}, Top 1% share={pct(pm['top_1pct_share'])}, CR4={pct(pm['cr4'])}, CR10={pct(pm['cr10'])}, CR20={pct(pm['cr20'])}, HHI={num(pm['hhi'],1)}.", f"- H1a benchmark tests: Gini CI [{num(pb['gini']['ci_low'])}, {num(pb['gini']['ci_high'])}] against 0.90 (p={num(pb['gini']['p_one_sided'],6)}), Top 1% CI [{pct(pb['top_1pct_share']['ci_low'])}, {pct(pb['top_1pct_share']['ci_high'])}] against 90% (p={num(pb['top_1pct_share']['p_one_sided'],6)}).", f"- After excluding the largest bot, concentration remains high: Gini={num(ex1['gini'])}, Top 1% share={pct(ex1['top_1pct_share'])}, CR4={pct(ex1['cr4'])}, HHI={num(ex1['hhi'],1)}."]
    if comp_rows:
        g = next(x for x in comp_rows if x["metric"] == "gini")
        t = next(x for x in comp_rows if x["metric"] == "top_1pct_share")
        lines.append(f"- 24m vs 30m robustness: Gini change={num(g['abs_change_right_minus_left'])}, Top 1% share change={pct(t['abs_change_right_minus_left'])}.")
    if rank_stats is not None:
        lines.append(f"- Rank persistence across windows: Spearman rank correlation={num(rank_stats['rho'])} on {rank_stats['common']} common addresses.")
    lines.append("- H1b: causal attribution to infrastructure/scale advantages is not identified by these tests.")
    lines.append("")

    rd.mkdir(parents=True, exist_ok=True)
    (rd / "h1_hypothesis_tests.md").write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    main()
