"""E_{t,h} assembly tests on synthetic inputs (Part 3 §4, Part 4 §2.3, Model 2-B §2, G9 holdout)."""
import math
from fractions import Fraction

import numpy as np

from m1macro import canon, estimation as E, s0link
from m1macro.test_s0link import _rows


def _setup():
    rng = np.random.default_rng(11)
    rows = _rows(rng, n=420)
    s0 = s0link.load_s0()
    outputs, pools = s0link.regenerate(s0, rows)
    opp = {(r["Pair"], r["Origin"], r["Horizon"]): r for r in rows}
    s0o = {(r["Pair"], r["Origin"], r["Horizon"]): r for r in outputs}
    feats = {}
    for r in rows:
        o = r["Origin"]
        if o not in feats:
            feats[o] = {"US": ("OK", "", "", float(rng.normal(0, .2))), "JP": ("OK", "", "", float(rng.normal(0, .1))),
                        "POS": ("OK", "", "", float(rng.uniform(-.3, .3)))}
    return rows, opp, s0o, feats, pools


def run():
    rows, opp, s0o, feats, pools = _setup()
    origins = sorted({r["Origin"] for r in rows})
    t = origins[-1]; laf = opp[("USDJPY", t, "1D")]["Last_Available_Fix"]
    e = E.assemble(t, "1D", laf, opp, s0o, feats, pools)
    assert all(r["origin"] < t for r in e.rows)
    assert all(opp[(r["pair"], r["origin"], "1D")]["Target_End"] <= laf for r in e.rows)
    keys = [(r["origin"], r["pair"]) for r in e.rows]; assert keys == sorted(keys)
    assert e.n_e == len({r["origin"] for r in e.rows})
    w = sum(Fraction(1, e.n_e * r["n_p"]) for r in e.rows); assert w == 1
    assert all(canon.f64hex(r["x_us"]) == "0000000000000000" for r in e.rows if r["pair"] != "USDJPY")
    e2 = E.assemble(t, "1D", laf, opp, s0o, feats, pools); assert e2.e_bytes == e.e_bytes   # determinism
    for r, z in zip(e.rows, e.pools):
        assert len(z) == int(s0o[(r["pair"], r["origin"], "1D")]["Pool_N"])
        assert format(math.fsum(z) / len(z), ".17g") == s0o[(r["pair"], r["origin"], "1D")]["Mean_Z"]
    # F_US failure at one origin removes only USDJPY there (Part 3 §3 note)
    o1 = e.rows[0]["origin"]
    f2 = dict(feats); f2[o1] = dict(feats[o1], US=("MODEL_PREREQ_UNAVAILABLE", "FEATURE_STALE", "", None))
    e3 = E.assemble(t, "1D", laf, opp, s0o, f2, pools)
    assert [r["pair"] for r in e3.rows if r["origin"] == o1] == ["CHFJPY"] and e3.n_e == e.n_e
    assert e3.e_sha256 != e.e_sha256
    # all features failing at one origin removes it from E
    f3 = dict(feats); f3[o1] = {k: ("ABSTAIN_SYSTEM", "FEATURE_UNAVAILABLE", "", None) for k in ("US", "JP", "POS")}
    assert E.assemble(t, "1D", laf, opp, s0o, f3, pools).n_e == e.n_e - 1
    # outcome not yet observed at t is excluded (Target_End > LAF_t)
    early = E.assemble(t, "1D", origins[300], opp, s0o, feats, pools)
    assert max(r["origin"] for r in early.rows) < origins[300] and early.n_e < e.n_e
    # a tampered issued pool size -> PIPELINE_FAILURE
    k = (e.rows[5]["pair"], e.rows[5]["origin"], "1D")
    s0b = dict(s0o); s0b[k] = dict(s0o[k], Pool_N=str(int(s0o[k]["Pool_N"]) + 1))
    try:
        E.assemble(t, "1D", laf, opp, s0b, feats, pools); raise AssertionError("pool size mismatch not detected")
    except s0link.PipelineFailure:
        pass
    # holdout pair anywhere in the input -> refused (G9)
    hk = ("GBPJPY", origins[0], "1D")
    try:
        E.assemble(t, "1D", laf, {**opp, hk: opp[("USDJPY", origins[0], "1D")]}, s0o, feats, pools)
        raise AssertionError("holdout accepted")
    except E.HoldoutBreach:
        pass
    # warm-up and NOT_EVALUATED
    assert E.estimate(None, False).state == "NOT_EVALUATED"
    small = E.assemble(origins[200], "1D", opp[("USDJPY", origins[200], "1D")]["Last_Available_Fix"], opp, s0o, feats, pools)
    assert small.n_e < 250 and E.estimate(small, True).state == "DEFAULT_PARENT"
    est = E.estimate(e, True)            # synthetic data only (not under the seal)
    assert e.n_e >= 250 and est.state == "ESTIMATED", est.state
    return {"ok": True, "n_e": e.n_e, "groups": len(e.rows), "solver_status": est.state,
            "ub_minus_lb": est.result.ub_minus_lb}
