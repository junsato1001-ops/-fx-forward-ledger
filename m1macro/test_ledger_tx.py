"""G4: transaction fault injection on an in-memory repository (Part 4 §3, §5; Part 3 §8 items 5-7)."""
from m1macro import ledger_tx as L


class FakeGit:
    def __init__(self, fail=None, clock=None):
        self.local = {}; self.remote_files = {}; self.fail = fail or {}; self.pushes = 0; self.clock = clock or []
        self.reads = 0

    def ensure_header(self, p, h):
        if p not in self.local:
            self.local[p] = h

    def append(self, p, b):
        self.local[p] = self.local.get(p, b"") + b

    def push(self):
        self.pushes += 1
        if self.pushes in self.fail.get("push", ()):
            raise RuntimeError("push rejected")
        if self.pushes in self.fail.get("push_corrupt", ()):
            self.remote_files = {k: v.replace(b"0.1", b"0.2") for k, v in self.local.items()}; return
        self.remote_files = dict(self.local)

    def remote(self, p):
        self.reads += 1
        if p in self.fail.get("reread", ()):
            raise RuntimeError("fetch failed")
        return self.remote_files.get(p, b"")

    def now(self):
        return self.clock.pop(0)


def _rows():
    fields = {L.FEATURES: ["Origin", "F_US"], L.ESTIMATION: ["Origin", "Horizon", "Beta_JP"],
              L.FORECASTS: ["Pair", "Origin", "Horizon", "P_Up"]}
    rows = {L.FEATURES: [L.row_bytes(fields[L.FEATURES], {"Origin": "2026-11-02", "F_US": "0.1"})],
            L.ESTIMATION: [L.row_bytes(fields[L.ESTIMATION], {"Origin": "2026-11-02", "Horizon": "1D", "Beta_JP": "0.01"})],
            L.FORECASTS: [L.row_bytes(fields[L.FORECASTS], {"Pair": p, "Origin": "2026-11-02", "Horizon": "1D", "P_Up": "0.3"})
                          for p in ("USDJPY", "CHFJPY", "INRJPY")]}
    return rows, fields


DL = "2026-11-01T23:30:00Z"   # 08:30 JST on 2026-11-02


def _run(fail=None, clock=("2026-11-01T22:00:00Z", "2026-11-01T22:01:00Z"), run_id="R1"):
    g = FakeGit(fail, list(clock)); rows, fields = _rows()
    st = L.run_transaction(g, rows, fields, run_id, "2026-11-02", "1D", DL, g.now)
    off = L.official_run_ids(g.remote_files.get(L.COMMITS, b""), g.remote_files.get(L.DEADLINE, b""))
    return st, off, g


def run():
    out = {}
    st, off, _ = _run(); assert st["status"] == "COMPLETE" and st["deadline_status"] == "ON_TIME" and off == {"R1"}
    # step 4 push fails 5 times -> UNCOMMITTED, not official
    st, off, _ = _run({"push": {1, 2, 3, 4, 5}}); assert st["failed_step"] == 4 and off == set()
    # step 5 reread failure / corrupted remote bytes
    st, off, _ = _run({"reread": {L.FEATURES}}); assert st["failed_step"] == 5 and off == set()
    st, off, _ = _run({"push_corrupt": {1}}); assert st["failed_step"] == 5 and off == set()
    # step 7 COMPLETE push fails -> partial data rows stay on remote, not official
    st, off, g = _run({"push": {2, 3, 4, 5, 6}}); assert st["failed_step"] == 7 and off == set()
    assert L.FEATURES in g.remote_files and L.COMMITS not in g.remote_files
    # step 8 reread fails -> unknown, not official (no ON_TIME audit written)
    st, off, _ = _run({"reread": {L.COMMITS}}); assert st["status"] == "UNKNOWN_PENDING_REREAD" and off == set()
    # step 9 audit push fails -> COMPLETE exists but no ON_TIME -> not official (fail-closed)
    st, off, g = _run({"push": {3, 4, 5, 6, 7}}); assert st["deadline_status"] == "NOT_RECORDED" and off == set()
    # deadline: marker created 08:29:59 JST, verified 08:30:03 JST -> LATE, not official
    st, off, _ = _run(clock=("2026-11-01T23:29:59Z", "2026-11-01T23:30:03Z"))
    assert st["status"] == "COMPLETE" and st["deadline_status"] == "LATE" and off == set()
    # exactly at the deadline -> ON_TIME
    st, off, _ = _run(clock=("2026-11-01T23:29:00Z", "2026-11-01T23:30:00Z")); assert off == {"R1"}
    # duplicate COMPLETE rows for one Run_ID are not official
    dup = L.header_bytes(L.COMMIT_FIELDS) + 2 * L.row_bytes(L.COMMIT_FIELDS, {"Run_ID": "R9", "Status": "COMPLETE"})
    dl = L.header_bytes(L.DEADLINE_FIELDS) + L.row_bytes(L.DEADLINE_FIELDS, {"Run_ID": "R9", "Deadline_Status": "ON_TIME"})
    assert L.official_run_ids(dup, dl) == set()
    out["ok"] = True
    return out
