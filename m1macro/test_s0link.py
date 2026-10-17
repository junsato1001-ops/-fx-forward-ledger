"""Synthetic test: S0 pool regeneration with the frozen S0 code and verification against issued rows."""
import datetime as dt
import math

import numpy as np

from m1macro import s0link


def _rows(rng, n=400):
    out = []
    d0 = dt.date(2020, 1, 6)
    for i in range(n):
        o = d0 + dt.timedelta(days=i)
        for pair in ("USDJPY", "CHFJPY"):
            sig = float(rng.uniform(.004, .008)); y = float(rng.normal(0, sig))
            out.append({"Pair": pair, "Origin": o.isoformat(), "Cutoff_JST": "08:30", "Horizon": "1D",
                        "Last_Available_Fix": (o - dt.timedelta(days=1)).isoformat(),
                        "Target_Start": o.isoformat(), "Target_End": (o + dt.timedelta(days=1)).isoformat(),
                        "H_Canonical_Intervals": "1", "Sigma_H": format(sig, ".17g"),
                        "Realized_LogReturn": format(y, ".17g"), "Prereq_Status": "FORECAST_READY",
                        "Outcome_Status": "OBSERVED"})
    return out


def run():
    rng = np.random.default_rng(5)
    s0 = s0link.load_s0()
    rows = _rows(rng)
    outputs, pools = s0link.regenerate(s0, rows)
    issued = {(r["Pair"], r["Origin"], r["Horizon"]): dict(r) for r in outputs}
    n = s0link.verify_against_issued(outputs, issued)
    fc = [r for r in outputs if r["Decision_Class"] == "FORECAST"]
    r0 = fc[-1]
    z = s0link.pool(pools, r0["Pair"], r0["Horizon"], r0["Origin"])
    assert len(z) == int(r0["Pool_N"]) and format(math.fsum(z.tolist()) / len(z), ".17g") == r0["Mean_Z"]
    tampered = dict(issued); k = next(iter(k for k in issued if issued[k]["Decision_Class"] == "FORECAST"))
    tampered[k] = dict(issued[k], Q90_Z="0.123")
    try:
        s0link.verify_against_issued(outputs, tampered); raise AssertionError("tamper not detected")
    except s0link.PipelineFailure:
        pass
    return {"ok": True, "issued_checked": n, "forecast_rows": len(fc)}
