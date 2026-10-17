"""Decision order and forecast fields (M1-MACRO-IMPL-PART3-V1 §3, §5)."""
import math
from bisect import bisect_left, bisect_right
from typing import Dict, List, Optional, Sequence

N_USD = {"USDJPY": ("US", "JP", "POS")}
DEFAULT_N = ("JP", "POS")
IDX = {"US": 0, "JP": 1, "POS": 2}


def n_of(pair):
    return N_USD.get(pair, DEFAULT_N)


def f17(x: float) -> str:
    if not math.isfinite(x):
        raise ValueError("non-finite output")
    return format(x, ".17g")


def mu(pair: str, beta: Sequence[float], feats: Dict[str, float]) -> float:
    """Part 3 §5.1: fsum of rounded products over N(p)."""
    return math.fsum(float(beta[IDX[k]]) * float(feats[k]) for k in n_of(pair))


def forecast_fields(s0_row: dict, mu_val: float, pool_z: Optional[Sequence[float]]) -> dict:
    """Part 3 §5.2 / §5.3. s0_row: issued S0 strings. pool_z: sorted S0 pool (needed only when mu != 0)."""
    keys = ("S0_Point_LogReturn", "PI10", "PI90", "P_Down", "P_Neutral", "P_Up")
    if mu_val == 0.0:                                  # also -0.0
        return {"Point_LogReturn": s0_row["S0_Point_LogReturn"], "PI10": s0_row["PI10"], "PI90": s0_row["PI90"],
                "P_Down": s0_row["P_Down"], "P_Neutral": s0_row["P_Neutral"], "P_Up": s0_row["P_Up"], "Mu_Copy": "S0"}
    sigma = float(s0_row["Sigma_H"])
    out = {"Point_LogReturn": f17(float(s0_row["S0_Point_LogReturn"]) + mu_val),
           "PI10": f17(float(s0_row["PI10"]) + mu_val), "PI90": f17(float(s0_row["PI90"]) + mu_val)}
    pd, pn, pu = class_probs(pool_z, sigma, mu_val)
    out.update(P_Down=f17(pd), P_Neutral=f17(pn), P_Up=f17(pu), Mu_Copy="")
    return out


def _xp(z, sigma, mu_val):
    return (sigma * z) + mu_val          # two separate roundings (Python floats never fuse)


def class_probs_canonical(pool_z, sigma, mu_val):
    """Canonical y-space count over all points (Part 3 §5.3)."""
    b = 0.25 * sigma
    n = len(pool_z); dn = up = 0
    for z in pool_z:
        x = _xp(float(z), sigma, mu_val)
        if x < -b:
            dn += 1
        elif x > b:
            up += 1
    return dn / n, (n - dn - up) / n, up / n


def class_probs(pool_z, sigma, mu_val):
    """Binary search with the same y-space predicate (x' monotone in Z for sigma >= 0)."""
    z = [float(v) for v in pool_z]; n = len(z); b = 0.25 * sigma
    lo, hi = 0, n                                       # count x' < -b
    while lo < hi:
        m = (lo + hi) // 2
        if _xp(z[m], sigma, mu_val) < -b:
            lo = m + 1
        else:
            hi = m
    dn = lo
    lo, hi = 0, n                                       # count x' <= b
    while lo < hi:
        m = (lo + hi) // 2
        if _xp(z[m], sigma, mu_val) <= b:
            lo = m + 1
        else:
            hi = m
    up = n - lo
    return dn / n, (n - dn - up) / n, up / n


def decide(issued_ok: bool, s0_row: dict, pipeline_failure: bool, feat_status: Dict[str, tuple], pair: str,
           warmup_ok: Optional[bool], solver_failure: Optional[str]):
    """Part 3 §3 order. feat_status[k] = (status, reason, subreason). Returns
    (Decision_Class, Reason_Code, subreason, Parameter_State)."""
    if not issued_ok:
        return "ABSTAIN_SYSTEM", "NOT_ISSUED", "", ""
    dc = s0_row.get("Decision_Class", "")
    if dc == "NOT_APPLICABLE":
        return "NOT_APPLICABLE", s0_row.get("Reason_Code", ""), "", ""
    if pipeline_failure:
        return "ABSTAIN_SYSTEM", "PIPELINE_FAILURE", "", ""
    if dc == "ABSTAIN_SYSTEM":
        return "ABSTAIN_SYSTEM", "PARENT_ABSTAIN_SYSTEM", "", ""
    for k in n_of(pair):
        st, rc, sub = feat_status[k]
        if st == "ABSTAIN_SYSTEM":
            return "ABSTAIN_SYSTEM", rc, sub, ""
    if dc == "MODEL_PREREQ_UNAVAILABLE":
        return "MODEL_PREREQ_UNAVAILABLE", "PARENT_PREREQ_UNAVAILABLE", "", ""
    order = ("FEATURE_NOT_YET_AVAILABLE", "FEATURE_GATE_EXCLUDED", "FEATURE_STALE", "FEATURE_NOT_COMPUTABLE")
    worst = None
    for k in n_of(pair):
        st, rc, sub = feat_status[k]
        if st == "MODEL_PREREQ_UNAVAILABLE":
            if worst is None or order.index(rc) < order.index(worst[0]):
                worst = (rc, sub)
    if worst:
        return "MODEL_PREREQ_UNAVAILABLE", worst[0], worst[1], ""
    if dc != "FORECAST":
        return "ABSTAIN_SYSTEM", "PIPELINE_FAILURE", "UNKNOWN_PARENT_STATE", ""
    if warmup_ok is False:
        return "FORECAST", "", "", "DEFAULT_PARENT"
    if solver_failure:
        return "ABSTAIN_SYSTEM", "SOLVER_FAILURE", solver_failure, "ESTIMATION_FAILED"
    return "FORECAST", "", "", "ESTIMATED"
