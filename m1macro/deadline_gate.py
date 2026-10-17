"""D8 Option B gates on the deadline audit and the M1 ledgers (IMPL-FINDINGS-03 修正仕様, むすび PASS 2026-10-18).

NOT_ISSUED is an issuance/audit state, never a forecast state:
  - a due Origin without an ON_TIME COMPLETE at its deadline gets exactly one irreversible NOT_ISSUED audit row;
  - a later genuine COMPLETE for that Origin may exist, but only as LATE (never ON_TIME);
  - audit rows are append-only (no update, no delete, no overwrite by a later COMPLETE);
  - no pseudo-forecast (ABSTAIN rows with NOT_ISSUED / LATE_ISSUE) is ever written to the forecast ledger.
Standard library only (runs on the runner host, like forward_commit.py).

usage: python3 -I m1macro/deadline_gate.py history     # every committed version of the audit file is append-only
"""
import csv
import datetime as dt
import io
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEADLINE = "audit_log/m1_macro_issue_deadline.csv"     # same path as ledger_tx.DEADLINE (kept literal: no import)
STATUSES = {"ON_TIME", "LATE", "NOT_ISSUED"}
PSEUDO_REASONS = {"NOT_ISSUED", "LATE_ISSUE"}
JST = dt.timezone(dt.timedelta(hours=9))


def _rows(b):
    return list(csv.DictReader(io.StringIO(b.decode("utf-8")))) if b else []


def deadline_utc(origin_iso: str) -> str:
    """Issuance deadline of an Origin (08:30 JST on the Origin day) as 'YYYY-MM-DDTHH:MM:SSZ'."""
    d = dt.date.fromisoformat(origin_iso)
    t = dt.datetime(d.year, d.month, d.day, 8, 30, tzinfo=JST).astimezone(dt.timezone.utc)
    return t.strftime("%Y-%m-%dT%H:%M:%SZ")


def check(commits: bytes, deadline: bytes, forecasts: bytes) -> list:
    """Return the sorted list of violation codes (empty = PASS) for one consistent snapshot of the three files."""
    bad = set()
    drows = _rows(deadline)
    complete = {}                                                       # Run_ID -> Origin
    per_key = {}
    for r in _rows(commits):
        if r.get("Status") == "COMPLETE":
            if r["Run_ID"] in complete:
                bad.add("COMPLETE_DUPLICATE_RUN")
            complete[r["Run_ID"]] = r["Origin"]
            for h in (r.get("Horizons") or "").split(";"):
                per_key[(r["Origin"], h)] = per_key.get((r["Origin"], h), 0) + 1
    if any(n > 1 for n in per_key.values()):
        bad.add("DOUBLE_ISSUANCE")
    ni_origins = {}
    status_by_run = {}
    for r in drows:
        s = r.get("Deadline_Status")
        if s not in STATUSES:
            bad.add("DEADLINE_STATUS_UNKNOWN"); continue
        if s == "NOT_ISSUED":
            o = r["Origin"]
            ni_origins[o] = ni_origins.get(o, 0) + 1
            if r.get("Committed_At_UTC") or r.get("Verified_At_UTC") or r.get("Deadline_UTC") != deadline_utc(o):
                bad.add("NOT_ISSUED_MALFORMED")
        else:
            if complete.get(r["Run_ID"]) != r["Origin"]:
                bad.add("DEADLINE_ROW_WITHOUT_COMPLETE")
            status_by_run.setdefault(r["Run_ID"], set()).add(s)
            if (s == "ON_TIME") != (bool(r.get("Verified_At_UTC")) and r["Verified_At_UTC"] <= r.get("Deadline_UTC", "")):
                bad.add("TIMELINESS_INCONSISTENT")
    if any(n > 1 for n in ni_origins.values()):
        bad.add("NOT_ISSUED_DUPLICATE")
    if any(len(v) > 1 for v in status_by_run.values()):
        bad.add("RUN_WITH_TWO_DEADLINE_STATES")
    for run, o in complete.items():                                    # NOT_ISSUED -> later COMPLETE must be LATE
        if o in ni_origins and "ON_TIME" in status_by_run.get(run, set()):
            bad.add("NOT_ISSUED_THEN_ON_TIME")
    for r in _rows(forecasts):
        if r.get("Reason_Code") in PSEUDO_REASONS:
            bad.add("PSEUDO_ABSTAIN_ROW")
    return sorted(bad)


def append_only(old: bytes, new: bytes) -> bool:
    """new keeps every byte of old in place (no row updated, deleted or reordered) and only adds whole lines."""
    return new.startswith(old) and (old == b"" or old.endswith(b"\n")) and (new == old or new.endswith(b"\n"))


def history_ok(versions) -> bool:
    """versions: the file's bytes at each commit, oldest first."""
    return all(append_only(a, b) for a, b in zip(versions, versions[1:]))


def git_versions(repo, rel, ref="HEAD"):
    """Bytes of rel at every commit on ref's first-parent history that touched it, oldest first (deleted = b'')."""
    g = lambda *a: subprocess.run(["git", *a], cwd=repo, capture_output=True)
    shas = g("log", "--first-parent", "--format=%H", "--reverse", ref, "--", rel).stdout.decode().split()
    out = []
    for s in shas:
        r = g("show", f"{s}:{rel}")
        out.append(r.stdout if r.returncode == 0 else b"")
    return out


if __name__ == "__main__":
    if sys.argv[1:] == ["history"]:
        vs = git_versions(ROOT, DEADLINE)
        res = {"gate": "DEADLINE_AUDIT_APPEND_ONLY", "versions": len(vs), "pass": history_ok(vs)}
        print(json.dumps(res))
        raise SystemExit(0 if res["pass"] else 1)
    raise SystemExit("usage: deadline_gate.py history")
