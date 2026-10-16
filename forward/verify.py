#!/usr/bin/env python3
"""Storage Verification Gate.

After the ledger commit has been pushed, re-read the files from the remote
(origin/main) and check that every row written in this run exists exactly once
with every field identical, and that the remote files are byte-identical to the
local files. Any shortfall, mismatch or read failure -> exit 1 (FAIL).
"""
import csv
import io
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def remote_bytes(path: str) -> bytes:
    return subprocess.run(["git", "show", f"origin/main:{path}"], cwd=ROOT, check=True, capture_output=True).stdout


def main():
    exp = json.loads((ROOT / "expected_this_run.json").read_text(encoding="utf-8"))
    d = exp["ledger_dir"]
    subprocess.run(["git", "fetch", "origin", "main"], cwd=ROOT, check=True, capture_output=True)
    fails = []
    for name, key in (("forecasts.csv", "forecasts"), ("outcomes.csv", "outcomes"), ("runs.csv", None)):
        rel = f"{d}/{name}"
        want = [exp["run"]] if key is None else exp[key]
        if not want:
            continue
        try:
            rb = remote_bytes(rel)
        except subprocess.CalledProcessError:
            fails.append(f"REREAD_FAILED {rel}")
            continue
        lb = (ROOT / rel).read_bytes()
        if rb != lb:
            fails.append(f"REMOTE_LOCAL_MISMATCH {rel}")
        rows = list(csv.DictReader(io.StringIO(rb.decode("utf-8"))))
        for w in want:
            n = sum(1 for r in rows if all((r.get(k) or "") == (v or "") for k, v in w.items()))
            if n != 1:
                fails.append(f"ROW_COUNT_{n} {rel} {w.get('Model', '')} {w.get('Pair', '')} {w.get('Origin', '')} {w.get('Horizon', '')}")
    n_fc, n_out = len(exp["forecasts"]), len(exp["outcomes"])
    if fails:
        print("FAIL")
        for f in fails[:50]:
            print(" ", f)
        sys.exit(1)
    print(f"SUCCESS run={exp['run_id']} forecasts={n_fc} outcomes={n_out} run_row=1 (remote re-read, all fields identical)")


if __name__ == "__main__":
    main()
