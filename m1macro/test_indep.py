"""G3: independent implementation agreement on synthetic data (Part 2 §10)."""
import numpy as np

from m1macro import indep, solver as S, synth


def run(seed=13):
    rng = np.random.default_rng(seed)
    out = {}
    cases = {"D_600x800": synth.case_random(rng, 600, 800), "D_3000x2000": synth.case_random(rng, 3000, 2000),
             "E_zero_col": synth.case_random(rng, 400, 600, zero_col=True), "C_2.5e-9": synth.case_C(2.5e-9)[0]}
    for name, g in cases.items():
        r = S.solve(g)
        xs = [gg.x for gg in g[:50]]; ss = [gg.sigma for gg in g[:50]]
        out[name] = indep.compare(g, r, xs, ss)
    out["ALL_PASS"] = all(v["pass_UB"] and v["pass_beta"] and v.get("pass_mu", True) for v in out.values() if isinstance(v, dict))
    return out
