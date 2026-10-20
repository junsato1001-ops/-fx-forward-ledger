"""IMPL-FINDINGS-06 regression (synthetic, real-input structure): the two failure modes of the independent
implementation reproduced in the pinned image, now certified and in agreement with production.

  epi seed 10140 (G 1308): before the fix 'epigraph not converged' (fixed point of re-added cuts at the LP
      feasibility tolerance). Now: EPIGRAPH_STALLED_EXACT_CERT.
  kel seed 30074 (G 9147): before the fix KELLEY_MAXIT at 600 iterations, gap 1.2394529846915248e-12 (the float LP basis
      was exactly infeasible by 1e-13..3e-12, so stage 1 never found an exact basis). Now: KELLEY_CERTIFIED.
  Both now also pass Impl Part 2 §6 in the independent implementation (exact minimum-norm tie-break, min_norm_stage):
  without it, seed 30074 certified but its beta differed from production's min-norm beta* by 1.15e-6 > 1e-6.
Production solver, criterion 1e-13 and iteration caps unchanged."""
import time

from m1macro import indep, solver as S, synth


def _one(kind, seed, want_term):
    g = synth.structured_case(kind, seed)
    t0 = time.time(); r = S.solve(g); t_prod = time.time() - t0
    t1 = time.time()
    c = indep.compare(g, r, [x.x for x in g[:60]], [x.sigma for x in g[:60]])
    t_ind = time.time() - t1
    assert c["termination"] == want_term, (kind, seed, c["termination"])
    assert c["pass_gap"] and c["pass_UB"] and c["pass_beta"] and c["pass_mu"], (kind, seed, c)
    return {"G": len(g), "termination": c["termination"], "iterations": c["iterations"], "indep_gap": c["indep_gap"],
            "d_UB": c["d_UB"], "d_beta_inf": c["d_beta_inf"], "sec_prod": round(t_prod, 1), "sec_indep": round(t_ind, 1)}


def run():
    return {"ok": True,
            "epi_10140": _one("epi", 10140, "EPIGRAPH_STALLED_EXACT_CERT+MINNORM_OK"),
            "kel_30074": _one("kel", 30074, "KELLEY_CERTIFIED+MINNORM_OK")}


if __name__ == "__main__":
    print(run())
