"""E_{t,h} assembly (Impl Part 3 §4, Model 2-B §2, Part 4 §2.3) and the per-(t,h) estimation step.

Inputs are point-in-time tables; nothing here re-derives past features from later files:
  opp[(pair, origin, horizon)]  M0 opportunity row (Target_End, Last_Available_Fix, Outcome_Status, Realized_LogReturn)
  s0[(pair, origin, horizon)]   issued S0 row (Decision_Class, Sigma_H, Pool_N, ...)
  feats[origin][k] = (status, reason, subreason, value)  for k in US/JP/POS, as issued/rebuilt at origin i
  pools                         s0link.regenerate() output (pools traced directly from the frozen S0 run)
"""
import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from m1macro import canon, s0link, solver
from m1macro.forecast import n_of

DEV_PAIRS = ("CHFJPY", "INRJPY", "USDJPY")                       # ASCII order
HOLDOUT_PAIRS = ("AUDJPY", "CADJPY", "GBPJPY", "KRWJPY", "SGDJPY")  # RFX-HOLDOUT-A-V1: never enters
WARMUP_MIN = 250


class HoldoutBreach(Exception):
    pass


@dataclass
class EInput:
    origin_t: str
    horizon: str
    n_e: int
    rows: List[dict]                       # canonical-order group dicts (canon.e_input_bytes)
    pools: List = field(default_factory=list)
    n_excluded_zero_scale: int = 0
    e_bytes: bytes = b""
    e_sha256: str = ""


def _ok(feats_i, pair):
    if feats_i is None:
        return False
    return all(feats_i.get(k) is not None and feats_i[k][0] == "OK" for k in n_of(pair))


def assemble(origin_t: str, horizon: str, laf_t: str, opp: Dict, s0: Dict, feats: Dict, pools) -> EInput:
    for key in list(opp) + list(s0):
        if key[0] in HOLDOUT_PAIRS:
            raise HoldoutBreach("holdout pair present in M1 estimation input")
    cand: Dict[str, List[tuple]] = {}
    zero_scale = 0
    for (pair, oi, h), o in opp.items():
        if h != horizon or pair not in DEV_PAIRS or oi >= origin_t:
            continue
        if not (o.get("Target_End") and o["Target_End"] <= laf_t):           # result known at t
            continue
        srow = s0.get((pair, oi, h))
        if srow is None or srow.get("Decision_Class") != "FORECAST":
            continue
        if o.get("Outcome_Status") != "OBSERVED":
            continue
        if not _ok(feats.get(oi), pair):
            continue
        sig = float(srow["Sigma_H"])
        if not (math.isfinite(sig) and sig > 0.0):
            zero_scale += 1
            continue
        cand.setdefault(oi, []).append((pair, sig, float(o["Realized_LogReturn"])))
    origins = sorted(cand)
    n_e = len(origins)
    rows, zs = [], []
    for oi in origins:
        ps = sorted(cand[oi])
        for pair, sig, y in ps:
            f = feats[oi]
            x_us = float(f["US"][3]) if pair == "USDJPY" else 0.0
            z = canon.pool_sorted(s0link.pool(pools, pair, horizon, oi).tolist())
            if len(z) != int(s0[(pair, oi, horizon)]["Pool_N"]):
                raise s0link.PipelineFailure("POOL_N_MISMATCH")
            rows.append({"origin": oi, "pair": pair, "n_p": len(ps), "x_us": x_us, "x_jp": float(f["JP"][3]),
                         "x_pos": float(f["POS"][3]), "sigma": sig, "y": y,
                         "pool_sha256": canon.pool_sha256(pair, oi, horizon, z)})
            zs.append(z)
    eb = canon.e_input_bytes(origin_t, horizon, n_e, rows)
    return EInput(origin_t, horizon, n_e, rows, zs, zero_scale, eb, canon.sha256_hex(eb))


def solver_groups(e: EInput):
    return [solver.make_group((r["x_us"], r["x_jp"], r["x_pos"]), r["sigma"], 1.0 / (e.n_e * r["n_p"]), r["y"], z)
            for r, z in zip(e.rows, e.pools)]


@dataclass
class Estimate:
    state: str                              # ESTIMATED / DEFAULT_PARENT / ESTIMATION_FAILED / NOT_EVALUATED
    beta: Optional[tuple]
    subreason: str = ""
    result: Optional[object] = None


def estimate(e: Optional[EInput], any_pair_eligible: bool) -> Estimate:
    """Part 3 §3 steps 8-10 for one (t, h); beta shared across pairs."""
    if not any_pair_eligible:
        return Estimate("NOT_EVALUATED", None)
    if e.n_e < WARMUP_MIN:
        return Estimate("DEFAULT_PARENT", (0.0, 0.0, 0.0))
    try:
        res = solver.solve(solver_groups(e))
    except solver.SolverFailure as f:
        return Estimate("ESTIMATION_FAILED", None, f.subreason)
    return Estimate("ESTIMATED", tuple(float(b) for b in res.beta), "", res)
