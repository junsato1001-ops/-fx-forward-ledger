"""Link to the parent S0 (Impl Part 1 §2.4, Part 3 §4): regenerate S0 pools with the frozen S0 code and
verify them against the issued S0 rows. Any mismatch -> PIPELINE_FAILURE. M1 never rebuilds pools itself.

Pools are captured from the frozen S0 run (its empirical_summary receives the exact sorted pool). They are
stored compactly as (candidate z array in S0's candidate order, pool size n) after checking, for every
captured pool, that it equals the sorted first-n candidates byte for byte.
"""
import hashlib
import importlib.util
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
S0_PATH = ROOT / "frozen" / "s0_empclim_std_exp_v1_1.py"
CHECK_FIELDS = ("Pool_N", "Mean_Z", "Q10_Z", "Q90_Z", "Decision_Class")


class PipelineFailure(Exception):
    pass


def load_frozen():
    """Frozen M0, ORIGIN_TARGET_MAP and S0 modules, loaded only after their SHA-256 match (forward/ledger_builder)."""
    import sys
    sys.path.insert(0, str(ROOT / "forward"))
    import ledger_builder as lb
    return lb.load_frozen()


def load_s0():
    return load_frozen()[2]


def _digest(arr):
    return hashlib.sha256(np.ascontiguousarray(arr, dtype=">f8").tobytes()).hexdigest()


def regenerate(s0mod, srows):
    """Run the frozen generate_s0 on the M0 opportunity rows; return (outputs, pools) where
    pools[(pair, horizon)] = {"cand": z array, "n": {origin_iso: n}}."""
    captured = []
    orig = s0mod.empirical_summary

    def cap(sorted_z, sigma_t):
        captured.append((len(sorted_z), _digest(np.asarray(sorted_z, dtype=np.float64))))
        return orig(sorted_z, sigma_t)

    s0mod.empirical_summary = cap
    try:
        outputs = s0mod.generate_s0(srows)
    finally:
        s0mod.empirical_summary = orig
    groups = s0mod._group_rows(srows)
    cands = {k: np.array([c.z for c in s0mod._candidate_pool_source(g)], dtype=np.float64) for k, g in groups.items()}
    pools = {k: {"cand": v, "n": {}} for k, v in cands.items()}
    it = iter(captured)
    for r in outputs:
        if r["Decision_Class"] != "FORECAST":
            continue
        n, dg = next(it)
        k = (r["Pair"], r["Horizon"])
        if str(n) != r["Pool_N"]:
            raise PipelineFailure(f"POOL_N_CAPTURE_MISMATCH {k} {r['Origin']}")
        if _digest(np.sort(pools[k]["cand"][:n], kind="stable")) != dg:
            raise PipelineFailure(f"POOL_NOT_PREFIX_OF_CANDIDATES {k} {r['Origin']}")
        pools[k]["n"][r["Origin"]] = n
    if next(it, None) is not None:
        raise PipelineFailure("UNMATCHED_POOL_CAPTURES")
    return outputs, pools


def verify_against_issued(outputs, issued):
    """issued: {(pair, origin, horizon): row of the issued S0 (frozen reference output or formal ledger)}.
    Every issued key must be regenerated with identical Pool_N, Mean_Z, Q10_Z, Q90_Z, Decision_Class strings."""
    regen = {(r["Pair"], r["Origin"], r["Horizon"]): r for r in outputs}
    bad = []
    for k, row in issued.items():
        g = regen.get(k)
        if g is None:
            bad.append((k, "MISSING")); continue
        for f in CHECK_FIELDS:
            if (g.get(f) or "") != (row.get(f) or ""):
                bad.append((k, f))
    if bad:
        raise PipelineFailure(f"S0_ISSUED_MISMATCH n={len(bad)} first={bad[:3]}")
    return len(issued)


def pool(pools, pair, horizon, origin_iso):
    p = pools[(pair, horizon)]
    return np.sort(p["cand"][:p["n"][origin_iso]], kind="stable")


FROZEN_SHA = {   # tests/test_reproduce_frozen.py (frozen formal ledger and S0 v1.1 outputs)
    "zip": "f36e0affc225bc572cc589d4183352c5815f178769f04c2b27a452567c6f7649",
    "ledger": "e4edb850c480626398d192e5232e8e88bdedb8e82697ceaa6e94470f36c38120",
    "s0": "98e94866251a0b72377a241fddc3b2aa2bce912248511a3df8b30421afe3fcc1",
}
ECB_DEV_ZIP = ROOT / "tests" / "fixtures" / "eurofxref-hist_20261009.zip"


def reconstruct(tmpdir):
    """Reconstruction period (Part 3 §4): M0 rows and S0 outputs from the ECB development snapshot, each checked
    byte for byte against the frozen SHA-256 (ledger e4edb850..., S0 98e94866...). Pools are captured from that
    same frozen S0 run. Returns (m0_rows_as_loaded, s0_outputs, pools)."""
    import sys
    sys.path.insert(0, str(ROOT / "forward"))
    import ledger_builder as lb
    zb = ECB_DEV_ZIP.read_bytes()
    if hashlib.sha256(zb).hexdigest() != FROZEN_SHA["zip"]:
        raise PipelineFailure("ECB_DEV_SNAPSHOT_SHA")
    m0, mp, s0 = lb.load_frozen()
    _, raw = lb.read_ecb_zip(zb)
    p = Path(tmpdir) / "m0_ledger.csv"
    lb.write_csv(p, lb.build_rows(m0, mp, raw))
    if hashlib.sha256(p.read_bytes()).hexdigest() != FROZEN_SHA["ledger"]:
        raise PipelineFailure("M0_LEDGER_SHA")
    rows = s0.load_csv(p)
    outputs, pools = regenerate(s0, rows)
    q = Path(tmpdir) / "s0.csv"
    s0.write_csv(q, outputs)
    if hashlib.sha256(q.read_bytes()).hexdigest() != FROZEN_SHA["s0"]:
        raise PipelineFailure("S0_OUTPUT_SHA")
    return rows, outputs, pools
