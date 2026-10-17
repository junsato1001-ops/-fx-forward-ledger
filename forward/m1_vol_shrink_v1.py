"""M1-VOL-SHRINK-V1 reference implementation (Pilot).

Specification: preregistration/M1-VOL-SHRINK-V1.md
  SHA-256 511ecaea39029d9ef99b88787dfb2a6442f42b7437db7466a5bc77be9b261977
  (frozen 2026-10-16 21:36:58 JST, commit 5356a890...)
Parent: S0-EMPCLIM-STD-EXP-V1. Evaluation: EVAL-SPEC-V1.

Input: the formal forecast-ready ledger rows (as strings, ledger_builder.to_strings)
and the ECB raw rows (ledger_builder.read_ecb_zip) used to build that ledger.
Output: one row per (Pair, Origin, Horizon), in ledger order.

Processing is chronological by Origin within each Horizon; w is common to the
three pairs (spec 3), pools are per Pair x Horizon (spec 4.1).
"""
from __future__ import annotations

import bisect
import math
from collections import defaultdict

SPEC_ID = "M1-VOL-SHRINK-V1"
SPEC_SHA256 = "511ecaea39029d9ef99b88787dfb2a6442f42b7437db7466a5bc77be9b261977"
KAPPA = 0.25
GRID = [k / 100 for k in range(101)]           # 0.00 .. 1.00
NOMINAL = {"1D": (1, 1), "1W": (7, 7), "4W": (7, 28)}   # origin interval, horizon days
PARAM_MIN = 250                                 # spec 3.3
DIST_MIN = 100                                  # spec 4.1 (same as S0)

OUT_FIELDS = [
    "Pair", "Origin", "Horizon", "Last_Available_Fix", "Target_Start", "Target_End", "H_Canonical_Intervals",
    "Sigma_M0", "V_EWMA", "V_Long", "W", "Parameter_State", "N_Param_Origins", "Sigma_M1",
    "Pool_N", "Mean_Z", "Q10_Z", "Q90_Z", "Point_LogReturn", "P_Down", "P_Neutral", "P_Up", "PI10", "PI90",
    "Realized_LogReturn", "Outcome_Status", "M1_Status", "Decision_Class", "Reason_Code",
]


def _f(x):
    if x is None or x == "":
        return None
    v = float(x)
    return v if math.isfinite(v) else None


def fmt(x):
    if x is None:
        return ""
    if isinstance(x, float):
        if not math.isfinite(x):
            raise ValueError("non-finite output")
        return format(x, ".17g")
    return str(x)


def vlong_lookup(raw, pairs):
    """v_long,p(L) = mean(r^2) of all canonical one-session log-returns of pair p
    with end date <= L, from the pair's first canonical return (spec 2).
    Returns {pair: (sorted_end_dates_iso, prefix_sum_list)}; sums accumulate in date order."""
    out = {}
    for p, (a, b) in pairs.items():
        dates, sums = [], [0.0]
        prev = None
        for r in raw:
            if r[a] is None or r[b] is None:
                continue
            rate = r[a] / r[b]
            if prev is not None:
                rr = math.log(rate / prev)
                dates.append(r["Date"].isoformat())
                sums.append(sums[-1] + rr * rr)
            prev = rate
        out[p] = (dates, sums)
    return out


def v_long_at(table, pair, laf_iso):
    dates, sums = table[pair]
    k = bisect.bisect_right(dates, laf_iso)
    return None if k == 0 else sums[k] / k


def qlike(h, vl, ve, y, w):
    s2 = h * (w * vl + (1.0 - w) * ve)
    return math.log(s2) + y * y / s2


def generate(ledger_rows, raw, pairs):
    vt = vlong_lookup(raw, pairs)
    rows_by_h = defaultdict(list)
    for r in ledger_rows:
        rows_by_h[r["Horizon"]].append(r)
    results = {}
    for h, rows in rows_by_h.items():
        num, den = NOMINAL[h]
        if num >= den:
            num, den = 1, 1
        else:
            g = math.gcd(num, den)
            num, den = num // g, den // g
        by_origin = defaultdict(list)
        for r in rows:
            by_origin[r["Origin"]].append(r)
        origins = sorted(by_origin)
        # Each FORECAST_READY opportunity gets a recorded state (v_long, v_ewma, sigma_m1) when processed.
        state = {}
        # Estimation accumulators (origin-cluster equal weight, spec 3.2)
        est_pending = []           # (target_end, origin) of processed origins awaiting maturity for estimation
        est_total = [0.0] * len(GRID)
        est_n = 0
        pool_pending = defaultdict(list)   # pair -> list of (target_end, key) awaiting maturity for Z pool
        pools = defaultdict(list)          # pair -> sorted Z_M1
        pool_ptr = defaultdict(int)
        est_ptr = 0
        first_estimated = None
        for o in origins:
            cluster = by_origin[o]
            laf = next((r["Last_Available_Fix"] for r in cluster if r["Last_Available_Fix"]), "")
            # --- mature estimation set: origins whose Target_End <= laf ---
            est_pending.sort()
            while est_ptr < len(est_pending) and laf and est_pending[est_ptr][0] <= laf:
                _, oo = est_pending[est_ptr]
                est_ptr += 1
                vec = [0.0] * len(GRID)
                cnt = 0
                for r in by_origin[oo]:
                    st = state.get((r["Pair"], oo))
                    if st is None:
                        continue
                    y = _f(r["Realized_LogReturn"])
                    hh = int(r["H_Canonical_Intervals"]) if r["H_Canonical_Intervals"] else 0
                    vl, ve, s0 = st["v_long"], st["v_ewma"], st["sigma_m0"]
                    if r["Outcome_Status"] != "OBSERVED" or y is None or hh <= 0:
                        continue
                    if s0 is None or not (s0 > 0):
                        continue
                    if vl is None or ve is None or not (vl > 0) or not (ve > 0):
                        continue
                    for k, w in enumerate(GRID):
                        vec[k] += qlike(hh, vl, ve, y, w)
                    cnt += 1
                if cnt:
                    for k in range(len(GRID)):
                        est_total[k] += vec[k] / cnt
                    est_n += 1
            if est_n * num >= PARAM_MIN * den:
                m = min(est_total)
                kmin = est_total.index(m)       # first minimum -> smallest w on ties
                w, pstate = GRID[kmin], "ESTIMATED"
                if first_estimated is None:
                    first_estimated = o
            else:
                w, pstate = 0.0, "DEFAULT_PARENT"
            # --- mature Z pools per pair ---
            for p in pairs:
                pend = pool_pending[p]
                pend.sort()
                i = pool_ptr[p]
                while i < len(pend) and laf and pend[i][0] <= laf:
                    _, key = pend[i]
                    i += 1
                    st = state[key]
                    y = st["y"]
                    if st["outcome"] == "OBSERVED" and y is not None and st["sigma_m1"] is not None and st["sigma_m1"] > 0:
                        bisect.insort(pools[p], y / st["sigma_m1"])
                pool_ptr[p] = i
            # --- issue for this origin ---
            for r in cluster:
                p = r["Pair"]
                out = {k: "" for k in OUT_FIELDS}
                for k in ("Pair", "Origin", "Horizon", "Last_Available_Fix", "Target_Start", "Target_End",
                          "H_Canonical_Intervals", "Realized_LogReturn", "Outcome_Status"):
                    out[k] = r.get(k, "")
                prereq = r["Prereq_Status"]
                if prereq in ("PRE_LISTING", "PRE_SCOPE"):
                    out.update(M1_Status=prereq, Decision_Class="NOT_APPLICABLE", Reason_Code=prereq)
                    results[(p, o, h)] = out
                    continue
                if prereq != "FORECAST_READY":
                    out.update(M1_Status="M1_VOL_STATE_UNAVAILABLE", Decision_Class="MODEL_PREREQ_UNAVAILABLE",
                               Reason_Code=prereq)
                    results[(p, o, h)] = out
                    continue
                hh = int(r["H_Canonical_Intervals"])
                ve = _f(r["EWMA_Var_1"])
                s0 = _f(r["Sigma_H"])
                vl = v_long_at(vt, p, r["Last_Available_Fix"])
                vm1 = w * vl + (1.0 - w) * ve
                sm1 = math.sqrt(hh * vm1)
                if not math.isfinite(sm1):
                    out.update(M1_Status="PIPELINE_FAILURE", Decision_Class="ABSTAIN_SYSTEM", Reason_Code="PIPELINE_FAILURE")
                    results[(p, o, h)] = out
                    continue
                key = (p, o)
                state[key] = {"v_long": vl, "v_ewma": ve, "sigma_m0": s0, "sigma_m1": sm1,
                              "y": _f(r["Realized_LogReturn"]), "outcome": r["Outcome_Status"]}
                pool_pending[p].append((r["Target_End"], key))
                out.update(Sigma_M0=fmt(s0), V_EWMA=fmt(ve), V_Long=fmt(vl), W=fmt(w), Parameter_State=pstate,
                           N_Param_Origins=str(est_n), Sigma_M1=fmt(sm1))
                pool = pools[p]
                n = len(pool)
                out["Pool_N"] = str(n)
                if n * num < DIST_MIN * den:
                    out.update(M1_Status="M1_WARMUP_INSUFFICIENT", Decision_Class="MODEL_PREREQ_UNAVAILABLE",
                               Reason_Code="M1_WARMUP_INSUFFICIENT")
                    results[(p, o, h)] = out
                    continue
                k10, k90 = (n + 9) // 10, (9 * n + 9) // 10
                mean_z = math.fsum(pool) / n
                if sm1 == 0.0:
                    pd, pn, pu, pt, lo, hi = 0.0, 1.0, 0.0, 0.0, 0.0, 0.0
                else:
                    b = KAPPA * s0
                    xs = [sm1 * z for z in pool]          # y-space (spec 4.2); monotone in z
                    left = bisect.bisect_left(xs, -b)
                    right = bisect.bisect_right(xs, b)
                    pd, pn, pu = left / n, (right - left) / n, (n - right) / n
                    pt, lo, hi = sm1 * mean_z, sm1 * pool[k10 - 1], sm1 * pool[k90 - 1]
                out.update(Mean_Z=fmt(mean_z), Q10_Z=fmt(pool[k10 - 1]), Q90_Z=fmt(pool[k90 - 1]),
                           Point_LogReturn=fmt(pt), P_Down=fmt(pd), P_Neutral=fmt(pn), P_Up=fmt(pu),
                           PI10=fmt(lo), PI90=fmt(hi), M1_Status="FORECAST", Decision_Class="FORECAST")
                results[(p, o, h)] = out
            te = next((r["Target_End"] for r in cluster if r["Target_End"]), "")
            if te and any((r["Pair"], o) in state for r in cluster):
                est_pending.append((te, o))   # Target_End is common to all pairs of an origin
        results[("__meta__", h)] = {"first_estimated_origin": first_estimated}
    ordered = [results[(r["Pair"], r["Origin"], r["Horizon"])] for r in ledger_rows]
    meta = {h: results[("__meta__", h)] for h in rows_by_h}
    return ordered, meta
