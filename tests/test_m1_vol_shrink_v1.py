#!/usr/bin/env python3
"""Self-test for M1-VOL-SHRINK-V1 on the frozen development snapshot.

Checks
 1. Every output row exists, one per ledger row.
 2. S0 identity (spec 4.4): before the first ESTIMATED origin of each horizon, every M1
    FORECAST row equals the frozen S0 v1.1 output exactly (probabilities, point, PI, pool N,
    mean/quantiles of Z) and Decision_Class matches.
 3. Prequential: w and Parameter_State only depend on the past (re-running on data
    truncated at a past Last_Available_Fix reproduces the same issued rows).
 4. Probabilities sum to 1; PI10 <= PI90; Parameter_State transitions DEFAULT_PARENT -> ESTIMATED.
Writes tests/output/m1_vol_shrink_v1_replay.csv (historical prequential replay).
"""
import csv
import datetime as dt
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "forward"))
import ledger_builder as lb  # noqa: E402
import m1_vol_shrink_v1 as m1  # noqa: E402

FIX = ROOT / "tests" / "fixtures" / "eurofxref-hist_20261009.zip"


def main():
    fails = []
    m0, mp, s0 = lb.load_frozen()
    _, raw = lb.read_ecb_zip(FIX.read_bytes())
    led = lb.to_strings(lb.build_rows(m0, mp, raw))
    s0_out = {(r["Pair"], r["Origin"], r["Horizon"]): r for r in s0.generate_s0(led)}
    out, meta = m1.generate(led, raw, lb.PAIRS)
    if len(out) != len(led):
        fails.append("row count")
    first = {h: meta[h]["first_estimated_origin"] for h in meta}
    n_cmp = {h: 0 for h in meta}
    for r in out:
        k = (r["Pair"], r["Origin"], r["Horizon"])
        if r["Decision_Class"] == "FORECAST":
            pd, pn, pu = float(r["P_Down"]), float(r["P_Neutral"]), float(r["P_Up"])
            if abs(pd + pn + pu - 1) > 1e-12:
                fails.append(f"probsum {k}")
            if float(r["PI10"]) > float(r["PI90"]):
                fails.append(f"PI order {k}")
        fe = first[r["Horizon"]]
        if r["Parameter_State"] and fe is not None and r["Origin"] >= fe and r["Parameter_State"] != "ESTIMATED":
            fails.append(f"state regress {k}")
        if fe is None or r["Origin"] < fe:
            S = s0_out[k]
            if (S["Decision_Class"] == "FORECAST") != (r["Decision_Class"] == "FORECAST"):
                fails.append(f"S0 identity decision {k} {S['Decision_Class']} {r['Decision_Class']}")
                continue
            if r["Decision_Class"] == "FORECAST":
                pairs = [("P_Down", "P_Down"), ("P_Neutral", "P_Neutral"), ("P_Up", "P_Up"), ("Point_LogReturn", "S0_Point_LogReturn"),
                         ("PI10", "PI10"), ("PI90", "PI90"), ("Pool_N", "Pool_N"), ("Mean_Z", "Mean_Z"),
                         ("Q10_Z", "Q10_Z"), ("Q90_Z", "Q90_Z"), ("Sigma_M1", "Sigma_H")]
                bad = [a for a, b in pairs if r[a] != S[b]]
                if bad:
                    fails.append(f"S0 identity {k} {bad}")
                n_cmp[r["Horizon"]] += 1
    # prequential check on a few origins: truncate data at LAF and recompute
    for o, h in [("2024-03-04", "1D"), ("2021-06-06", "1W"), ("2023-09-03", "4W")]:
        k = ("USDJPY", o, h)
        full = next(r for r in out if (r["Pair"], r["Origin"], r["Horizon"]) == k)
        laf = dt.date.fromisoformat(full["Last_Available_Fix"])
        rt = [x for x in raw if x["Date"] <= laf]
        lt = lb.to_strings(lb.build_rows(m0, mp, rt, extra_origins=[(p, dt.date.fromisoformat(o), h) for p in lb.PAIRS]))
        ot, _ = m1.generate(lt, rt, lb.PAIRS)
        tr = next(r for r in ot if (r["Pair"], r["Origin"], r["Horizon"]) == k)
        cols = ["W", "Parameter_State", "N_Param_Origins", "Sigma_M1", "Pool_N", "P_Down", "P_Neutral", "P_Up", "PI10", "PI90", "Point_LogReturn"]
        bad = [c for c in cols if tr[c] != full[c]]
        if bad:
            fails.append(f"prequential {k} {bad}")
    od = ROOT / "tests" / "output"
    od.mkdir(exist_ok=True)
    p = od / "m1_vol_shrink_v1_replay.csv"
    with open(p, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=m1.OUT_FIELDS, lineterminator="\n")
        w.writeheader()
        for r in out:
            w.writerow(r)
    from collections import Counter
    summary = {"result": "PASS" if not fails else "FAIL", "fails": fails[:20], "n_fails": len(fails),
               "first_estimated_origin": first, "s0_identity_rows_compared": n_cmp,
               "decision_counts": dict(Counter(r["Decision_Class"] for r in out)),
               "parameter_state_counts": dict(Counter(r["Parameter_State"] for r in out if r["Parameter_State"])),
               "replay_csv_sha256": hashlib.sha256(p.read_bytes()).hexdigest(),
               "m1_code_sha256": hashlib.sha256((ROOT / "forward" / "m1_vol_shrink_v1.py").read_bytes()).hexdigest()}
    print(json.dumps(summary, indent=1))
    sys.exit(0 if not fails else 1)


if __name__ == "__main__":
    main()
