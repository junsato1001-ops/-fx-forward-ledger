"""Synthetic-only stress test of the INDEPENDENT implementation (m1macro/indep.py), IMPL-FINDINGS-05 F5-a.

No real data is read. Problems mimic the structure of the real estimation input (tools/m1macro_stress/gen.py).
For each case: run indep's own solver (the code under test) and an instrumented copy of the same loop that records
why it stops (LP status, rounds, repeated cuts, violations, exact-certificate attempts). Not part of CODE_MANIFEST_V1.

usage: python -I tools/m1macro_stress/stress_indep.py <out_dir> <shard> <n_shards> <n_epi> <n_kel>
"""
import json
import math
import sys
import time
import traceback
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1])); sys.path.insert(0, str(HERE))
import numpy as np  # noqa: E402
from scipy.optimize import linprog  # noqa: E402

from m1macro import indep  # noqa: E402
import gen  # noqa: E402


def epigraph_traced(P, tol=1e-13, maxr=200):
    """Same algorithm as indep.solve_epigraph, with a trace."""
    G = len(P.a); cuts = {}
    for g in range(G):
        for mu0 in (P.a[g][0] - 1.0, P.a[g][-1] + 1.0):
            cuts[(g, round(mu0, 15))] = P.group_piece(g, mu0)
    tr = {"rounds": [], "stop": None}
    for r in range(maxr):
        keys = sorted(cuts); m = len(keys)
        A = np.zeros((m, 3 + G)); b = np.zeros(m)
        for i, (g, _) in enumerate(keys):
            s, c = cuts[(g, _)]
            A[i, :3] = s * P.X[g]; A[i, 3 + g] = -1.0; b[i] = -c
        res = linprog(np.r_[np.zeros(3), P.om], A_ub=A, b_ub=b, bounds=indep._bounds(P) + [(None, None)] * G,
                      method="highs-ds", options=indep.OPT)
        rec = {"r": r, "n_cuts": m, "lp_status": int(res.status)}
        if res.status != 0:
            rec["lp_message"] = str(res.message)[:120]; tr["rounds"].append(rec); tr["stop"] = f"LP_STATUS_{res.status}"
            return tr
        beta = res.x[:3]; t = res.x[3:]; m_ = P.mu(beta); added = 0; repeated = 0; maxv = 0.0; maxv_rep = 0.0
        # existing-cut residual: how far below an EXISTING cut the LP leaves t (LP feasibility tolerance)
        exist_res = max((s * m_[g] + c - t[g]) for (g, _), (s, c) in cuts.items())
        for g in range(G):
            s, c = P.group_piece(g, m_[g])
            v = s * m_[g] + c - t[g]
            if v > tol:
                key = (g, round(m_[g], 15))
                rep = key in cuts or any(cuts[k] == (s, c) for k in cuts if k[0] == g)
                cuts[key] = (s, c); added += 1; repeated += rep; maxv = max(maxv, v)
                if rep:
                    maxv_rep = max(maxv_rep, v)
        rec.update(added=added, repeated=repeated, max_violation=maxv, max_violation_repeated=maxv_rep,
                   max_existing_cut_residual=float(exist_res), fun=float(res.fun))
        tr["rounds"].append(rec)
        if added == 0:
            tr["stop"] = "CONVERGED"; tr["gap"] = float(P.phi(beta) - res.fun); return tr
    tr["stop"] = "MAXR"
    return tr


def kelley_traced(P, tol=1e-13, maxit=600, lam=0.5):
    """Same algorithm as indep.solve_kelley_fast, with a trace of the exact-certification stage."""
    F = indep.FastProb(P); cuts = []; best = (math.inf, None); pts = [np.zeros(3)]; bnd = indep._bounds(P)
    tr = {"first_float_gap_le_1e10": None, "exact_attempts": 0, "exact_none": 0, "exact_gaps": [], "stop": None,
          "float_gaps_tail": []}
    for it in range(maxit):
        for p in pts:
            s, c, v = F.eval(p); cuts.append((s, c))
            if v < best[0]:
                best = (v, np.array(p))
        A = np.array([np.r_[s, -1.0] for s, _ in cuts]); b = np.array([-c for _, c in cuts])
        res = linprog(np.r_[np.zeros(3), 1.0], A_ub=A, b_ub=b, bounds=bnd + [(None, None)], method="highs-ds",
                      options=indep.OPT)
        if res.status != 0:
            tr["stop"] = f"LP_STATUS_{res.status}"; tr["it"] = it; return tr
        lb = res.fun; gap = best[0] - lb; xm = res.x[:3]
        tr["float_gaps_tail"] = (tr["float_gaps_tail"] + [float(gap)])[-6:]
        if gap <= 1e-10:
            if tr["first_float_gap_le_1e10"] is None:
                tr["first_float_gap_le_1e10"] = it
            tr["exact_attempts"] += 1
            v = indep.exact_lb(cuts, bnd, res.x)
            if v is None:
                tr["exact_none"] += 1
            else:
                lb = float(v[3]); xm = np.array([float(q) for q in v[:3]])
                tr["exact_gaps"] = (tr["exact_gaps"] + [float(best[0] - lb)])[-6:]
                if best[0] - lb <= tol:
                    tr["stop"] = "CERTIFIED"; tr["it"] = it + 1; return tr
        lev = lb + lam * (best[0] - lb)
        A2 = np.array([np.r_[s, 0.0] for s, _ in cuts] + [np.r_[np.eye(3)[j], -1.0] for j in range(3)]
                      + [np.r_[-np.eye(3)[j], -1.0] for j in range(3)])
        b2 = np.r_[[lev - c for _, c in cuts], best[1], -best[1]]
        r2 = linprog(np.r_[np.zeros(3), 1.0], A_ub=A2, b_ub=b2, bounds=bnd + [(0, None)], method="highs-ds",
                     options=indep.OPT)
        pts = [xm] + ([r2.x[:3]] if r2.status == 0 else [])
    tr["stop"] = "MAXIT"; tr["it"] = maxit
    return tr


def case(kind, seed):
    rng = np.random.default_rng(seed)
    if kind == "epi":
        n = int(rng.integers(250, 1334)); pool0 = int(rng.integers(2500, 4500))
    else:
        n = int(rng.integers(1400, 2600)); pool0 = int(rng.integers(4000, 6500))
    gs = gen.problem(rng, n, pool0=pool0, zero_frac=float(rng.choice([0.0, 0.03])), pin=bool(rng.integers(0, 2)))
    return gs, {"kind": kind, "seed": seed, "n_origins": n, "G": len(gs), "N_min": pool0, "N_max": pool0 + n - 1}


def run_one(kind, seed):
    gs, meta = case(kind, seed)
    P = indep.Prob.from_groups(gs); out = dict(meta); t0 = time.time()
    try:
        if kind == "epi":
            beta, ub, lb, it = indep.solve_epigraph(P); method = "epigraph"
        else:
            beta, ub, lb, it = indep.solve_kelley_fast(P); method = "kelley_fast_longdouble"
        g = float(P.phi(beta) - lb)
        out.update(indep_outcome="RETURNED", method=method, iterations=it, gap=g, pass_gap=abs(g) <= 1e-13)
    except Exception as e:
        out.update(indep_outcome="EXCEPTION", exc_type=type(e).__name__, exc_msg=str(e)[:160])
    out["sec_indep"] = round(time.time() - t0, 1)
    if out.get("indep_outcome") == "EXCEPTION" or not out.get("pass_gap", False):
        t1 = time.time()
        try:
            out["trace"] = epigraph_traced(P) if kind == "epi" else kelley_traced(P)
        except Exception:
            out["trace_error"] = traceback.format_exc()[-600:]
        out["sec_trace"] = round(time.time() - t1, 1)
    return out


def main(outdir, shard, n_shards, n_epi, n_kel):
    shard, n_shards = int(shard), int(n_shards)
    out = Path(outdir); out.mkdir(parents=True, exist_ok=True)
    f = open(out / f"stress_{shard}.jsonl", "w")
    jobs = [("epi", 10000 + i) for i in range(int(n_epi) * n_shards)] + [("kel", 20000 + i) for i in range(int(n_kel) * n_shards)]
    for i, (k, s) in enumerate(jobs):
        if i % n_shards == shard:
            f.write(json.dumps(run_one(k, s), sort_keys=True) + "\n"); f.flush()
    f.close()


if __name__ == "__main__":
    main(*sys.argv[1:6])
