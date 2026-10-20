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


@dataclass
class GroupRec:
    """Time-invariant part of a candidate group (p, i, h): everything except the Target_End <= LAF_t test."""
    origin: str
    pair: str
    target_end: str
    zero_scale: bool
    x: tuple = ()
    sigma: float = 0.0
    y: float = 0.0
    pool_sha256: str = ""
    z: object = None


def static_groups(horizon: str, opp: Dict, s0: Dict, feats: Dict, pools) -> List[GroupRec]:
    for key in list(opp) + list(s0):
        if key[0] in HOLDOUT_PAIRS:
            raise HoldoutBreach("holdout pair present in M1 estimation input")
    out = []
    for (pair, oi, h), o in opp.items():
        if h != horizon or pair not in DEV_PAIRS or not o.get("Target_End"):
            continue
        srow = s0.get((pair, oi, h))
        if srow is None or srow.get("Decision_Class") != "FORECAST":
            continue
        if o.get("Outcome_Status") != "OBSERVED" or not _ok(feats.get(oi), pair):
            continue
        sig = float(srow["Sigma_H"])
        if not (math.isfinite(sig) and sig > 0.0):
            out.append(GroupRec(oi, pair, o["Target_End"], True)); continue
        f = feats[oi]
        z = canon.pool_sorted_np(s0link.pool(pools, pair, horizon, oi))
        if len(z) != int(srow["Pool_N"]):
            raise s0link.PipelineFailure("POOL_N_MISMATCH")
        x = (float(f["US"][3]) if pair == "USDJPY" else 0.0, float(f["JP"][3]), float(f["POS"][3]))
        out.append(GroupRec(oi, pair, o["Target_End"], False, x, sig, float(o["Realized_LogReturn"]),
                            canon.pool_sha256_np(pair, oi, horizon, z), z))
    out.sort(key=lambda r: (r.origin, r.pair))
    return out


def assemble_from(recs: List[GroupRec], origin_t: str, horizon: str, laf_t: str) -> EInput:
    sel = [r for r in recs if r.origin < origin_t and r.target_end <= laf_t]
    zero_scale = sum(1 for r in sel if r.zero_scale)
    sel = [r for r in sel if not r.zero_scale]
    npi: Dict[str, int] = {}
    for r in sel:
        npi[r.origin] = npi.get(r.origin, 0) + 1
    n_e = len(npi)
    rows = [{"origin": r.origin, "pair": r.pair, "n_p": npi[r.origin], "x_us": r.x[0], "x_jp": r.x[1], "x_pos": r.x[2],
             "sigma": r.sigma, "y": r.y, "pool_sha256": r.pool_sha256} for r in sel]
    eb = canon.e_input_bytes(origin_t, horizon, n_e, rows)
    e = EInput(origin_t, horizon, n_e, rows, [r.z for r in sel], zero_scale, eb, canon.sha256_hex(eb))
    e.recs = sel
    return e


def assemble(origin_t: str, horizon: str, laf_t: str, opp: Dict, s0: Dict, feats: Dict, pools) -> EInput:
    return assemble_from(static_groups(horizon, opp, s0, feats, pools), origin_t, horizon, laf_t)


def solver_groups(e: EInput, cache: Optional[dict] = None):
    """Solver groups with omega = 1 / (|E| * |P_i|). cache: {(pair, origin): Group} reused across t (omega replaced)."""
    import dataclasses
    out = []
    for r, z in zip(e.rows, e.pools):
        w = 1.0 / (e.n_e * r["n_p"])
        k = (r["pair"], r["origin"])
        if cache is not None and k in cache:
            out.append(dataclasses.replace(cache[k], omega=w)); continue
        g = solver.make_group((r["x_us"], r["x_jp"], r["x_pos"]), r["sigma"], w, r["y"], z)
        if cache is not None:
            cache[k] = g
        out.append(g)
    return out


@dataclass
class Estimate:
    state: str                              # ESTIMATED / DEFAULT_PARENT / ESTIMATION_FAILED / NOT_EVALUATED
    beta: Optional[tuple]
    subreason: str = ""
    result: Optional[object] = None


def estimate(e: Optional[EInput], any_pair_eligible: bool, cache: Optional[dict] = None) -> Estimate:
    """Part 3 §3 steps 8-10 for one (t, h); beta shared across pairs."""
    if not any_pair_eligible:
        return Estimate("NOT_EVALUATED", None)
    if e.n_e < WARMUP_MIN:
        return Estimate("DEFAULT_PARENT", (0.0, 0.0, 0.0))
    try:
        res = solver.solve(solver_groups(e, cache))
    except solver.SolverFailure as f:
        return Estimate("ESTIMATION_FAILED", None, f.subreason)
    return Estimate("ESTIMATED", tuple(float(b) for b in res.beta), "", res)
