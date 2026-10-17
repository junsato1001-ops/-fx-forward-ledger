"""G1: synthetic cases A-E on the production solver (Impl Part 2 §12, Part 4 §5)."""
import math
import time

import numpy as np

from m1macro import solver as S
from m1macro import synth


def _phi(groups, b):
    return S.piece(groups, b)[2]


def run(seed=7):
    rng = np.random.default_rng(seed)
    out = {}
    g, c = synth.case_A(rng)
    r = S.solve(g)
    out["A"] = dict(ok=bool(abs(_phi(g, r.beta) - _phi(g, c)) <= S.EPS_TIE and np.linalg.norm(r.beta) <= np.linalg.norm(c) + 1e-15),
                    phi_diff=_phi(g, r.beta) - _phi(g, c), norm_diff=float(np.linalg.norm(r.beta) - np.linalg.norm(c)),
                    it=(r.stage1_iter, r.stage2_iter), ub_lb=r.ub_minus_lb, phi2_lb=r.phi2_minus_lb)
    g, e = synth.case_B(); r = S.solve(g)
    out["B"] = dict(ok=float(np.abs(r.beta - e).max()) <= 1e-12, err=float(np.abs(r.beta - e).max()),
                    beta=r.beta.tolist(), ub_lb=r.ub_minus_lb, phi2_lb=r.phi2_minus_lb)
    for tilt in (2.5e-9, 1e-10, 1e-11, 1e-12, 1e-14):
        g, e = synth.case_C(tilt); r = S.solve(g)
        out[f"C_{tilt:.0e}"] = dict(ok=float(np.abs(r.beta - e).max()) <= 1e-12, err=float(np.abs(r.beta - e).max()),
                                   ub_lb=r.ub_minus_lb, phi2_lb=r.phi2_minus_lb)
    for G, N in ((600, 800), (3000, 2000)):
        g = synth.case_random(rng, G, N); t0 = time.time(); r = S.solve(g)
        out[f"D_{G}x{N}"] = dict(ok=abs(r.ub_minus_lb) <= S.EPS_TIE and abs(r.phi2_minus_lb) <= S.EPS_TIE,
                                 sec=round(time.time() - t0, 1), it=(r.stage1_iter, r.stage2_iter),
                                 ub_lb=r.ub_minus_lb, phi2_lb=r.phi2_minus_lb)
    g = synth.case_random(rng, 400, 600, zero_col=True); r = S.solve(g)
    out["E"] = dict(ok=bool(r.beta[0] == 0.0 and 0 not in r.nonzero_cols), beta_us_hex=float(r.beta[0]).hex())
    out["ALL_OK"] = all(v["ok"] for v in out.values() if isinstance(v, dict))
    return out
