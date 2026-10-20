"""IMPL-FINDINGS-06: the independent epigraph stalls when the LP leaves an existing cut violated by more than the
separation tolerance (LP feasibility tolerance 1e-10 > 1e-13). Forced here by perturbing the LP solution by -5e-11 in
the epigraph variables; the fixed solver must stop searching and certify the lower bound exactly (gap <= 1e-13)
and agree with the production solver. Synthetic only."""
import numpy as np

from m1macro import indep, solver as S, synth


def run(seed=7):
    rng = np.random.default_rng(seed)
    g = synth.case_random(rng, 400, 600)
    P = indep.Prob.from_groups(g)
    orig = indep.linprog
    def perturbed(c, A_ub=None, b_ub=None, bounds=None, **k):
        res = orig(c, A_ub=A_ub, b_ub=b_ub, bounds=bounds, **k)
        if res.status == 0 and len(res.x) > 4:                         # the per-group epigraph master only
            res.x = np.r_[res.x[:3], res.x[3:] - 5e-11]
        return res
    indep.linprog = perturbed
    try:
        beta, ub, lb, it, term = indep.solve_epigraph(P)[:5]
    finally:
        indep.linprog = orig
    gap = float(P.phi(beta) - lb)
    assert term == "EPIGRAPH_STALLED_EXACT_CERT", term
    assert 0 <= gap <= 1e-13 or abs(gap) <= 1e-13, gap
    r = S.solve(g)
    c = indep.compare(g, r, [x.x for x in g[:50]], [x.sigma for x in g[:50]])
    assert c["pass_gap"] and c["pass_UB"] and c["pass_beta"] and c["pass_mu"], c
    # unperturbed: unchanged behaviour (clean convergence)
    b2, u2, l2, it2, t2 = indep.solve_epigraph(P)[:5]
    assert t2 == "EPIGRAPH_CONVERGED" and abs(P.phi(b2) - l2) <= 1e-13
    return {"ok": True, "stalled_gap": gap, "iterations": it, "d_UB_vs_production": c["d_UB"]}


if __name__ == "__main__":
    print(run())
