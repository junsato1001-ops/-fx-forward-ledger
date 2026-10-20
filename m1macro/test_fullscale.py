"""G2: full-scale synthetic (groups 12000, pool 6000): time, convergence, eps_tie margin (Part 2 §11, Part 4 §5)."""
import time

import numpy as np

from m1macro import solver as S
from m1macro import synth


def run(seed=11, reps=3):
    rng = np.random.default_rng(seed)
    out = {}
    neg = []
    for r_ in range(reps):
        t0 = time.time(); g = synth.case_random(rng, 12000, 6000); tb = time.time() - t0
        t1 = time.time(); r = S.solve(g); ts = time.time() - t1
        neg += [min(0.0, r.ub_minus_lb), min(0.0, r.phi2_minus_lb)]
        out[f"rep{r_}"] = dict(build_sec=round(tb, 1), solve_sec=round(ts, 1), it=(r.stage1_iter, r.stage2_iter),
                               ub_lb=r.ub_minus_lb, phi2_lb=r.phi2_minus_lb, n_cuts=r.n_cuts)
        del g
    out["most_negative"] = min(neg)
    out["margin_ok_neg_side_le_1e-14"] = bool(min(neg) >= -1e-14)
    return out
