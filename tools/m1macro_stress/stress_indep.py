"""Synthetic-only stress test of the INDEPENDENT implementation (m1macro/indep.py), IMPL-FINDINGS-05 F5-a.

No real data is read. Problems mimic the structure of the real estimation input (tools/m1macro_stress/gen.py).
For each case: run indep's own solver (the code under test) and an instrumented copy of the same loop that records
why it stops (LP status, rounds, repeated cuts, violations, exact-certificate attempts). Not part of CODE_MANIFEST_V1.

usage: python -I tools/m1macro_stress/stress_indep.py <out_dir> <shard> <n_shards> <n_epi> <n_kel>
"""
import json
import math
import os
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
    import os
    if kind == "epi":
        n = int(rng.integers(250, 1334)); pool0 = int(rng.integers(2500, 4500))
    else:
        lo, hi = (int(v) for v in os.environ.get("STRESS_KEL_ORIGINS", "1400,2600").split(","))
        n = int(rng.integers(lo, hi)); pool0 = int(rng.integers(4000, 6500))
    gs = gen.problem(rng, n, pool0=pool0, zero_frac=float(rng.choice([0.0, 0.03])), pin=bool(rng.integers(0, 2)))
    return gs, {"kind": kind, "seed": seed, "n_origins": n, "G": len(gs), "N_min": pool0, "N_max": pool0 + n - 1}


def run_one(kind, seed):
    """Full Impl Part 2 §10 comparison as in gate G6: production solve, then indep.compare (independent search,
    exact certification, exact §6 minimum-norm tie-break, UB / beta / mu agreement). Problem from synth.structured_case
    (bit-identical to case())."""
    import os
    from m1macro import solver as S, synth
    lo, hi = (int(v) for v in os.environ.get("STRESS_KEL_ORIGINS", "1400,2600").split(","))
    g = synth.structured_case(kind, seed, kel_origins=(lo, hi))
    _, meta = None, {"kind": kind, "seed": seed, "G": len(g), "N_min": min(len(x.a) for x in g), "N_max": max(len(x.a) for x in g)}
    out = dict(meta); t0 = time.time()
    try:
        r = S.solve(g); out["prod"] = "OK"
    except Exception as e:
        out.update(prod="EXCEPTION", prod_exc=type(e).__name__ + ":" + str(e)[:80]); return out
    out["sec_prod"] = round(time.time() - t0, 1); t1 = time.time()
    try:
        c = indep.compare(g, r, [x.x for x in g[:60]], [x.sigma for x in g[:60]])
        out.update(indep_outcome="RETURNED", **{k: c[k] for k in ("method", "iterations", "termination", "indep_gap",
                   "d_UB", "d_beta_inf", "d_mu_over_sigma", "pass_gap", "pass_UB", "pass_beta", "pass_mu")})
        out["gap"] = c["indep_gap"]
        out["pass_all"] = bool(c["pass_gap"] and c["pass_UB"] and c["pass_beta"] and c["pass_mu"])
    except Exception as e:
        out.update(indep_outcome="EXCEPTION", exc_type=type(e).__name__, exc_msg=str(e)[:160])
    out["sec_indep"] = round(time.time() - t1, 1)
    if os.environ.get("STRESS_BETA_DIAG") == "1":
        out["beta_diag"] = beta_diag(g, r)
    return out


def beta_diag(g, r):
    """Synthetic only: where do production beta* and the independent beta2 sit relative to a tighter reference of
    the exact minimum-norm point (independent §6 continued with a smaller internal tolerance)? Values allowed
    (synthetic data)."""
    P = indep.Prob.from_groups(g)
    _, _, _, _, kterm, st = indep.solve_kelley_fast(P, return_termination=True, return_state=True)
    c = indep.compare(g, r, [x.x for x in g[:5]], [x.sigma for x in g[:5]])
    b_ind = None
    out = {"kelley": kterm}
    refs = {}
    for tol in (1e-13, 1e-14, 3e-15):
        try:
            b2, phi2, lb2, rounds, _ = indep.min_norm_stage(P, st, tol=1e-13, refine=tol, max_rounds=1000)
            refs[tol] = (b2, phi2, lb2, rounds)
        except Exception as e:
            out[f"ref_{tol:g}_error"] = str(e)[:60]
    bp = np.asarray(r.beta, float)
    for tol, (b2, phi2, lb2, rounds) in refs.items():
        out[f"ref_{tol:g}"] = {"beta": [float(v) for v in b2], "phi_minus_lb": float(phi2 - lb2), "rounds": rounds,
                               "norm": float(np.linalg.norm(b2)),
                               "d_prod": float(np.max(np.abs(bp - b2)))}
    out["prod"] = {"beta": [float(v) for v in bp], "norm": float(np.linalg.norm(bp)), "phi": float(P.phi(bp))}
    out["lb_exact"] = float(st["v"][3]) if st else None
    return out


def main(outdir, shard, n_shards, n_epi, n_kel):
    shard, n_shards = int(shard), int(n_shards)
    out = Path(outdir); out.mkdir(parents=True, exist_ok=True)
    f = open(out / f"stress_{shard}.jsonl", "w")
    import os
    seeds = os.environ.get("STRESS_EPI_SEEDS", "")
    epi = [int(x) for x in seeds.split(",") if x] if seeds else [10000 + i for i in range(int(n_epi) * n_shards)]
    k0 = int(os.environ.get("STRESS_KEL_SEED0", "20000"))
    jobs = [("epi", s) for s in epi] + [("kel", k0 + i) for i in range(int(n_kel) * n_shards)]
    for i, (k, s) in enumerate(jobs):
        if i % n_shards == shard:
            f.write(json.dumps(run_one(k, s), sort_keys=True) + "\n"); f.flush()
    f.close()


if __name__ == "__main__":
    main(*sys.argv[1:6])
