#!/usr/bin/env python3
"""Reproduction gate for the forward runner.

1. On the frozen ECB snapshot (SHA-256 f36e0aff...), forward/ledger_builder.py must
   reproduce frozen formal_forecast_ledger_v1.csv byte for byte (SHA-256 e4edb850...).
2. Frozen S0 v1.1 run on that ledger must reproduce s0_formal_opportunities_v1_1.csv
   byte for byte (SHA-256 98e94866...).
3. Simulated forward issuance (data truncated at Last_Available_Fix) for a fixed set of
   historical origins must give exactly the same M0/S0 forecast values as the frozen
   outputs, which were computed with the full history. This proves the leakage guard
   and the forward-origin path do not change any number.
Exit code 0 only if every check passes.
"""
import csv
import datetime as dt
import hashlib
import io
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "forward"))
import ledger_builder as lb  # noqa: E402
import issue  # noqa: E402

FIXTURE = ROOT / "tests" / "fixtures" / "eurofxref-hist_20261009.zip"
EXP = {
    "zip": "f36e0affc225bc572cc589d4183352c5815f178769f04c2b27a452567c6f7649",
    "ledger": "e4edb850c480626398d192e5232e8e88bdedb8e82697ceaa6e94470f36c38120",
    "s0": "98e94866251a0b72377a241fddc3b2aa2bce912248511a3df8b30421afe3fcc1",
}
SIM_ORIGINS = [
    ("2026-10-09", "1D"), ("2026-10-05", "1D"), ("2026-09-15", "1D"), ("2024-08-05", "1D"),
    ("2011-03-14", "1D"), ("2026-10-04", "1W"), ("2026-10-04", "4W"), ("2026-09-13", "4W"),
    ("2020-03-15", "1W"), ("2020-03-15", "4W"), ("2017-10-01", "4W"),
]


def sha(b):
    return hashlib.sha256(b).hexdigest()


def main():
    fails = []
    zb = FIXTURE.read_bytes()
    if sha(zb) != EXP["zip"]:
        fails.append("fixture zip sha")
    m0, mp, s0 = lb.load_frozen()
    _, raw = lb.read_ecb_zip(zb)
    rows = lb.build_rows(m0, mp, raw)
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "ledger.csv"
        lb.write_csv(p, rows)
        got = sha(p.read_bytes())
        print("ledger sha", got, "OK" if got == EXP["ledger"] else "FAIL")
        if got != EXP["ledger"]:
            fails.append("ledger sha")
        ledger_rows = s0.load_csv(p)
        out = s0.generate_s0(ledger_rows)
        q = Path(td) / "s0.csv"
        s0.write_csv(q, out)
        got = sha(q.read_bytes())
        print("s0 sha", got, "OK" if got == EXP["s0"] else "FAIL")
        if got != EXP["s0"]:
            fails.append("s0 sha")
    led = {(r["Pair"], r["Origin"], r["Horizon"]): r for r in lb.to_strings(rows)}
    s0r = {(r["Pair"], r["Origin"], r["Horizon"]): r for r in out}
    cols_m0 = ["Last_Available_Fix", "Target_Start", "Target_End", "H_Canonical_Intervals", "Sigma_H",
               "M0_P_Down", "M0_P_Neutral", "M0_P_Up", "M0_PI10", "M0_PI90", "Prereq_Status"]
    cols_s0 = ["Pool_N", "Mean_Z", "Q10_Z", "Q90_Z", "S0_Point_LogReturn", "P_Down", "P_Neutral", "P_Up",
               "PI10", "PI90", "S0_Status", "Decision_Class"]
    for o, h in SIM_ORIGINS:
        L, S, laf = issue.issue_forecasts(m0, mp, s0, raw, dt.date.fromisoformat(o), h)
        for k in L:
            bad = [c for c in cols_m0 if L[k][c] != led[k][c]] + [c for c in cols_s0 if S[k][c] != s0r[k][c]]
            if bad:
                fails.append(f"sim {k} {bad}")
        print("sim", o, h, "laf", laf, "OK" if not any(f.startswith(f"sim ('") and o in f for f in fails) else "FAIL")
    print("RESULT", "PASS" if not fails else "FAIL", fails[:10])
    sys.exit(0 if not fails else 1)


if __name__ == "__main__":
    main()
