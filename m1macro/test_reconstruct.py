"""Reconstruction from the ECB development snapshot reproduces the frozen M0 ledger and S0 output (SHA-256),
and the captured pools match every issued S0 row (Pool_N, Mean_Z)."""
import math
import tempfile

from m1macro import s0link


def run():
    with tempfile.TemporaryDirectory() as td:
        rows, outputs, pools = s0link.reconstruct(td)
    fc = [r for r in outputs if r["Decision_Class"] == "FORECAST"]
    bad = 0
    for r in fc[::97]:
        z = s0link.pool(pools, r["Pair"], r["Horizon"], r["Origin"])
        bad += (len(z) != int(r["Pool_N"])) or (format(math.fsum(z.tolist()) / len(z), ".17g") != r["Mean_Z"])
    assert bad == 0
    hold = {"GBPJPY", "AUDJPY", "CADJPY", "SGDJPY", "KRWJPY"}
    assert not any(r["Pair"] in hold for r in outputs)
    return {"ok": True, "m0_rows": len(rows), "s0_forecast_rows": len(fc), "sampled": len(fc[::97])}
