"""Part 3 §3/§5 tests: decision order, S0 copy at mu=0, canonical y-space probabilities."""
import numpy as np

from m1macro import forecast as F


def run():
    rng = np.random.default_rng(3)
    s0 = {"Decision_Class": "FORECAST", "Reason_Code": "", "Sigma_H": "0.0061", "S0_Point_LogReturn": "0.0001",
          "PI10": "-0.007", "PI90": "0.0072", "P_Down": "0.3", "P_Neutral": "0.4", "P_Up": "0.3"}
    out = F.forecast_fields(s0, -0.0, None)
    assert out["Mu_Copy"] == "S0" and out["P_Up"] == "0.3"
    # canonical vs fast count on many random pools, including points placed exactly at the boundaries
    for t in range(300):
        z = np.sort(rng.standard_t(4, 501)); sig = float(rng.uniform(.002, .01)); m = float(rng.normal(0, .002))
        b = 0.25 * sig
        z[::50] = (b - m) / sig; z[1::50] = (-b - m) / sig; z = np.sort(z)
        assert F.class_probs(z, sig, m) == F.class_probs_canonical(z, sig, m), t
    assert F.class_probs([0.0, 1.0], 0.0, -1e-9) == (1.0, 0.0, 0.0)        # sigma = 0: all points at mu
    assert F.class_probs([0.0, 1.0], 0.0, 0.0) == (0.0, 1.0, 0.0)
    ok = ("OK", "", "")
    fs = {"US": ok, "JP": ok, "POS": ok}
    assert F.decide(True, s0, False, fs, "USDJPY", True, None) == ("FORECAST", "", "", "ESTIMATED")
    assert F.decide(True, s0, False, fs, "USDJPY", False, None)[3] == "DEFAULT_PARENT"
    assert F.decide(True, s0, False, fs, "USDJPY", True, "GAP_NOT_REACHED")[:2] == ("ABSTAIN_SYSTEM", "SOLVER_FAILURE")
    bad_us = dict(fs, US=("ABSTAIN_SYSTEM", "FEATURE_UNAVAILABLE", "CALENDAR_INTEGRITY"))
    assert F.decide(True, s0, False, bad_us, "USDJPY", True, None)[1] == "FEATURE_UNAVAILABLE"
    assert F.decide(True, s0, False, bad_us, "CHFJPY", True, None)[0] == "FORECAST"          # F_US not in N(CHFJPY)
    pre = dict(s0, Decision_Class="MODEL_PREREQ_UNAVAILABLE")
    assert F.decide(True, pre, False, bad_us, "USDJPY", True, None)[1] == "FEATURE_UNAVAILABLE"   # system before prereq
    stale = dict(fs, POS=("MODEL_PREREQ_UNAVAILABLE", "FEATURE_STALE", "x"))
    assert F.decide(True, pre, False, stale, "USDJPY", True, None)[1] == "PARENT_PREREQ_UNAVAILABLE"
    assert F.decide(True, s0, False, stale, "USDJPY", False, None)[1] == "FEATURE_STALE"          # no DEFAULT_PARENT switch
    assert F.decide(True, dict(s0, Decision_Class="ABSTAIN_SYSTEM"), False, fs, "USDJPY", True, None)[1] == "PARENT_ABSTAIN_SYSTEM"
    assert F.decide(True, dict(s0, Decision_Class="NOT_APPLICABLE", Reason_Code="PRE_SCOPE"), True, fs, "USDJPY", True, None)[:2] == ("NOT_APPLICABLE", "PRE_SCOPE")
    assert abs(F.mu("CHFJPY", [5.0, 0.1, 0.2], {"US": 9.0, "JP": 1.0, "POS": 1.0}) - 0.3) < 1e-15
    return {"ok": True}
