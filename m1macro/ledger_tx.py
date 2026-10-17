"""M1-MACRO ledgers and the issuance transaction (Impl Part 3 §6, Part 4 §2.5, §3).

Steps: 1 build rows -> 2 canonical bytes + range SHA-256 -> 3 append 3 ledgers -> 4 push -> 5 remote reread
(each row exactly once, byte-identical, range SHA match) -> 6 append COMPLETE (Committed_At_UTC) -> 7 push
-> 8 remote reread of COMPLETE (Verified_At_UTC) -> 9 append deadline audit (ON_TIME iff Verified_At <= deadline)
and push. Official issuance = COMPLETE on remote AND ON_TIME audit row on remote. Partial rows stay (UNCOMMITTED).
"""
import csv
import hashlib
import io
from typing import Callable, Dict, List

FEATURES = "ledger/m1_macro_features.csv"
ESTIMATION = "ledger/m1_macro_estimation.csv"
FORECASTS = "ledger/m1_macro_forecasts.csv"
COMMITS = "ledger/m1_macro_issue_commits.csv"
DEADLINE = "audit_log/m1_macro_issue_deadline.csv"
DATA_FILES = (FEATURES, ESTIMATION, FORECASTS)
COMMIT_FIELDS = ["Run_ID", "Origin", "Horizons", "Features_Rows", "Features_Range_SHA256", "Estimation_Rows",
                 "Estimation_Range_SHA256", "Forecasts_Rows", "Forecasts_Range_SHA256", "Status", "Committed_At_UTC"]
DEADLINE_FIELDS = ["Run_ID", "Origin", "Committed_At_UTC", "Verified_At_UTC", "Deadline_UTC", "Deadline_Status"]
PUSH_RETRIES = 5


def row_bytes(fields: List[str], row: Dict[str, str]) -> bytes:
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=fields, lineterminator="\n", quoting=csv.QUOTE_MINIMAL, extrasaction="raise")
    w.writerow({k: ("" if row.get(k) is None else str(row[k])) for k in fields})
    return buf.getvalue().encode("utf-8")


def header_bytes(fields):
    return (",".join(fields) + "\n").encode("utf-8")


def sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


class TxFailure(Exception):
    def __init__(self, step, detail=""):
        super().__init__(f"step {step}: {detail}"); self.step = step


def _count(hay: bytes, needle: bytes) -> int:
    lines = hay.split(b"\n"); n = needle.rstrip(b"\n")
    return sum(1 for ln in lines if ln == n)


def run_transaction(git, rows: Dict[str, List[bytes]], fields: Dict[str, List[str]], run_id: str, origin: str,
                    horizons: str, deadline_utc: str, now: Callable[[], str]) -> dict:
    """git: object with append(path, bytes), ensure_header(path, bytes), push() (raises on failure),
    remote(path) -> bytes (raises on failure). now() -> 'YYYY-MM-DDTHH:MM:SSZ'. Returns a status dict."""
    st = {"run_id": run_id, "status": "UNCOMMITTED", "deadline_status": "", "failed_step": None}
    try:
        rng = {f: sha(b"".join(rows[f])) for f in DATA_FILES}                       # step 2
        for f in DATA_FILES:                                                          # step 3
            git.ensure_header(f, header_bytes(fields[f]))
            for b in rows[f]:
                git.append(f, b)
        _push(git, 4)
        for f in DATA_FILES:                                                          # step 5
            try:
                rb = git.remote(f)
            except Exception as e:
                raise TxFailure(5, f"reread {f}: {e!r}")
            for b in rows[f]:
                if _count(rb, b) != 1:
                    raise TxFailure(5, f"row not exactly once in {f}")
        committed = now()                                                             # step 6
        crow = {"Run_ID": run_id, "Origin": origin, "Horizons": horizons, "Status": "COMPLETE", "Committed_At_UTC": committed}
        for f, key in ((FEATURES, "Features"), (ESTIMATION, "Estimation"), (FORECASTS, "Forecasts")):
            crow[f"{key}_Rows"] = str(len(rows[f])); crow[f"{key}_Range_SHA256"] = rng[f]
        cb = row_bytes(COMMIT_FIELDS, crow)
        git.ensure_header(COMMITS, header_bytes(COMMIT_FIELDS)); git.append(COMMITS, cb)
        _push(git, 7)
        try:                                                                          # step 8
            rc = git.remote(COMMITS)
        except Exception as e:
            st["status"] = "UNKNOWN_PENDING_REREAD"; st["failed_step"] = 8; return st
        if _count(rc, cb) != 1:
            raise TxFailure(8, "COMPLETE row not exactly once")
        verified = now()
        st["status"] = "COMPLETE"; st["committed_at"] = committed; st["verified_at"] = verified
        dstat = "ON_TIME" if verified <= deadline_utc else "LATE"                     # step 9
        drow = {"Run_ID": run_id, "Origin": origin, "Committed_At_UTC": committed, "Verified_At_UTC": verified,
                "Deadline_UTC": deadline_utc, "Deadline_Status": dstat}
        git.ensure_header(DEADLINE, header_bytes(DEADLINE_FIELDS)); git.append(DEADLINE, row_bytes(DEADLINE_FIELDS, drow))
        try:
            _push(git, 9)
            st["deadline_status"] = dstat
        except TxFailure:
            st["deadline_status"] = "NOT_RECORDED"; st["failed_step"] = 9
        return st
    except TxFailure as e:
        st["failed_step"] = e.step
        return st


def _push(git, step):
    last = None
    for _ in range(PUSH_RETRIES):
        try:
            git.push(); return
        except Exception as e:
            last = e
    raise TxFailure(step, f"push failed: {last!r}")


def official_run_ids(remote_commits: bytes, remote_deadline: bytes) -> set:
    """Run_IDs with exactly one COMPLETE row and an ON_TIME deadline audit row (Part 4 §3, §7)."""
    def rows(b):
        return list(csv.DictReader(io.StringIO(b.decode("utf-8")))) if b else []
    comp = {}
    for r in rows(remote_commits):
        if r.get("Status") == "COMPLETE":
            comp[r["Run_ID"]] = comp.get(r["Run_ID"], 0) + 1
    ontime = {r["Run_ID"] for r in rows(remote_deadline) if r.get("Deadline_Status") == "ON_TIME"}
    return {k for k, n in comp.items() if n == 1 and k in ontime}
