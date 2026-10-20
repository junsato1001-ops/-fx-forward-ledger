"""D8 Option B (IMPL-FINDINGS-03 修正仕様, むすび PASS 2026-10-18): NOT_ISSUED is an irreversible deadline-audit state;
a later genuine COMPLETE is allowed only as LATE; audit rows are append-only; no pseudo-forecast rows.
Unit checks of deadline_gate plus the host commit path (forward_commit.commit_tx) on a temporary git repository."""
import base64
import json
import subprocess
import tempfile
from pathlib import Path

from m1macro import deadline_gate as DG, forward_commit as FC, gitrepo, ledger_tx as L, manifest
from m1macro.schema import FORECAST_FIELDS
from m1macro.test_gitrepo_tx import _repo

C_H = L.header_bytes(L.COMMIT_FIELDS)
D_H = L.header_bytes(L.DEADLINE_FIELDS)
F_H = L.header_bytes(FORECAST_FIELDS)


def _c(run, origin, hs="1D"):
    return L.row_bytes(L.COMMIT_FIELDS, {"Run_ID": run, "Origin": origin, "Horizons": hs, "Status": "COMPLETE",
                                         "Committed_At_UTC": "x"})


def _d(run, origin, status, verified=""):
    return L.row_bytes(L.DEADLINE_FIELDS, {"Run_ID": run, "Origin": origin, "Committed_At_UTC": verified,
                                           "Verified_At_UTC": verified, "Deadline_UTC": DG.deadline_utc(origin),
                                           "Deadline_Status": status})


def _ni(run, origin):
    return _d(run, origin, "NOT_ISSUED")


def _f(reason):
    return L.row_bytes(FORECAST_FIELDS, {"Model": "M1-MACRO-V1", "Pair": "USDJPY", "Origin": "2026-10-07",
                                         "Horizon": "1D", "Decision_Class": "ABSTAIN_SYSTEM", "Reason_Code": reason})


def unit():
    assert DG.deadline_utc("2026-10-07") == "2026-10-06T23:30:00Z"
    ok_t, late_t = "2026-10-06T23:29:00Z", "2026-10-06T23:31:00Z"
    # clean states
    assert DG.check(b"", b"", b"") == []
    assert DG.check(C_H + _c("R1", "2026-10-07"), D_H + _d("R1", "2026-10-07", "ON_TIME", ok_t), F_H) == []
    # Option B: NOT_ISSUED then a later genuine COMPLETE recorded as LATE (either order) -> PASS
    assert DG.check(C_H + _c("R2", "2026-10-07"), D_H + _ni("A", "2026-10-07") + _d("R2", "2026-10-07", "LATE", late_t), F_H) == []
    assert DG.check(C_H + _c("R2", "2026-10-07"), D_H + _d("R2", "2026-10-07", "LATE", late_t) + _ni("A", "2026-10-07"), F_H) == []
    # NOT_ISSUED with a COMPLETE whose deadline row was never recorded (not ON_TIME) -> PASS (safe side)
    assert DG.check(C_H + _c("R2", "2026-10-07"), D_H + _ni("A", "2026-10-07"), F_H) == []
    # forbidden
    v = lambda c, d, f=F_H: DG.check(C_H + c, D_H + d, f)
    assert "NOT_ISSUED_THEN_ON_TIME" in v(_c("R1", "2026-10-07"), _ni("A", "2026-10-07") + _d("R1", "2026-10-07", "ON_TIME", ok_t))
    assert "NOT_ISSUED_DUPLICATE" in v(b"", _ni("A", "2026-10-07") + _ni("B", "2026-10-07"))
    assert "NOT_ISSUED_MALFORMED" in v(b"", _d("A", "2026-10-07", "NOT_ISSUED", ok_t))
    assert "NOT_ISSUED_MALFORMED" in v(b"", L.row_bytes(L.DEADLINE_FIELDS, {"Run_ID": "A", "Origin": "2026-10-07",
                                                                          "Deadline_UTC": "2026-10-07T23:30:00Z",
                                                                          "Deadline_Status": "NOT_ISSUED"}))
    assert "PSEUDO_ABSTAIN_ROW" in v(b"", b"", F_H + _f("NOT_ISSUED"))
    assert "PSEUDO_ABSTAIN_ROW" in v(b"", b"", F_H + _f("LATE_ISSUE"))
    assert "TIMELINESS_INCONSISTENT" in v(_c("R1", "2026-10-07"), _d("R1", "2026-10-07", "ON_TIME", late_t))
    assert "DEADLINE_ROW_WITHOUT_COMPLETE" in v(b"", _d("R9", "2026-10-07", "LATE", late_t))
    assert "DEADLINE_STATUS_UNKNOWN" in v(b"", _d("R9", "2026-10-07", "PENDING"))
    assert "DOUBLE_ISSUANCE" in v(_c("R1", "2026-10-07") + _c("R2", "2026-10-07"), b"")
    # append-only: adding whole lines passes; editing, deleting, reordering or a partial line fails
    a = D_H + _ni("A", "2026-10-07"); b = a + _ni("B", "2026-10-08")
    assert DG.append_only(a, a) and DG.append_only(a, b) and DG.append_only(b"", b)
    assert not DG.append_only(b, a)                                                       # delete
    assert not DG.append_only(a, a.replace(b"NOT_ISSUED", b"LATE") + _ni("B", "2026-10-08"))  # update
    assert not DG.append_only(b, D_H + _ni("B", "2026-10-08") + _ni("A", "2026-10-07"))   # reorder
    assert not DG.append_only(a, a + b"R,2026")                                             # partial line
    assert DG.history_ok([b"", a, b]) and not DG.history_ok([b"", b, a])


def history_on_git(td):
    """deadline_gate.history over real git history: an edit of a committed audit row is detected."""
    bare, work = _repo(td, "h")
    p = work / DG.DEADLINE; p.parent.mkdir(parents=True)
    git = lambda *a: subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@e", *a], cwd=work, check=True,
                                    capture_output=True)
    rows = [D_H + _ni("A", "2026-10-07"), D_H + _ni("A", "2026-10-07") + _ni("B", "2026-10-08")]
    for b in rows:
        p.write_bytes(b); git("add", DG.DEADLINE); git("commit", "-q", "-m", "a")
    assert DG.history_ok(DG.git_versions(work, DG.DEADLINE))
    p.write_bytes(rows[1].replace(b"NOT_ISSUED\n", b"LATE\n", 1)); git("commit", "-qam", "edit")
    assert not DG.history_ok(DG.git_versions(work, DG.DEADLINE))


def commit_path(td):
    """forward_commit: NOT_ISSUED once; later COMPLETE/LATE accepted; ON_TIME after NOT_ISSUED refused (post gate);
    a pseudo-forecast on the synced tree blocks the run (pre gate)."""
    bare, work = _repo(td, "c")
    old = FC.ROOT; FC.ROOT = work
    try:
        from m1macro.test_freeze_record import write_final
        write_final(work, manifest.code_sha256())
        stage = Path(td, "stage"); stage.mkdir()
        ni = [{"origin": "2026-10-07", "horizons": "1D", "deadline_utc": "2026-10-06T23:30:00Z"}]
        put = lambda tx: (stage / "tx.json").write_text(json.dumps(tx))
        put({"run_id": "A1", "code_sha256": "x", "status": "AFTER_CUTOFF", "txs": [], "not_issued": ni})
        FC.commit_tx(str(stage), gitrepo.RealGit(work, message="t"))
        first = (work / L.DEADLINE).read_bytes()
        FC.commit_tx(str(stage), gitrepo.RealGit(work, message="t"))                     # idempotent
        assert (work / L.DEADLINE).read_bytes() == first and first.count(b",NOT_ISSUED") == 1
        assert not (work / L.FORECASTS).exists()                                          # no pseudo-forecast
        # a wrong deadline for a NOT_ISSUED item is refused
        put({"run_id": "A0", "code_sha256": "x", "status": "AFTER_CUTOFF", "txs": [],
             "not_issued": [{"origin": "2026-10-09", "horizons": "1D", "deadline_utc": "2026-10-09T23:30:00Z"}]})
        try:
            FC.commit_tx(str(stage), gitrepo.RealGit(work, message="t")); raise AssertionError("wrong deadline accepted")
        except FC.PipelineFailure as e:
            assert str(e) == "NOT_ISSUED_DEADLINE_MISMATCH"
        def rows(o):                                                                       # unique rows per origin
            return {L.FEATURES: [f"f,{o}\n".encode()], L.ESTIMATION: [f"e,{o}\n".encode()],
                    L.FORECASTS: [L.row_bytes(FORECAST_FIELDS, {"Model": "M1-MACRO-V1", "Origin": o, "Horizon": "1D",
                                                                "Decision_Class": "FORECAST"})]}
        tx = lambda rid, o: {"run_id": rid, "code_sha256": manifest.code_sha256(), "status": "READY", "not_issued": [],
                             "txs": [{"origin": o, "horizons": "1D", "deadline_utc": DG.deadline_utc(o),
                                      "rows": {k: [base64.b64encode(x).decode() for x in v] for k, v in rows(o).items()}}]}
        # later genuine COMPLETE for the NOT_ISSUED origin -> LATE; NOT_ISSUED row untouched
        put(tx("R2", "2026-10-07"))
        ck = ["2026-10-07T01:00:00Z", "2026-10-07T01:00:05Z"]
        st = FC.commit_tx(str(stage), gitrepo.RealGit(work, message="t"), lambda: ck.pop(0))
        assert st["status"] == "COMPLETE" and st["deadline_status"] == "LATE", st
        after = (work / L.DEADLINE).read_bytes()
        assert after.startswith(first) and after.count(b",NOT_ISSUED") == 1
        assert L.official_run_ids((work / L.COMMITS).read_bytes(), after) == set()      # never confirmatory
        # the reverse order is the same state: COMPLETE/LATE first, then the deadline audit still writes NOT_ISSUED
        put(tx("R3", "2026-10-08"))
        ck = ["2026-10-08T01:00:00Z", "2026-10-08T01:00:05Z"]
        assert FC.commit_tx(str(stage), gitrepo.RealGit(work, message="t"), lambda: ck.pop(0))["deadline_status"] == "LATE"
        put({"run_id": "A2", "code_sha256": "x", "status": "AFTER_CUTOFF", "txs": [],
             "not_issued": [{"origin": "2026-10-08", "horizons": "1D", "deadline_utc": "2026-10-07T23:30:00Z"}]})
        FC.commit_tx(str(stage), gitrepo.RealGit(work, message="t"))
        assert (work / L.DEADLINE).read_bytes().count(b",NOT_ISSUED") == 2
        # an ON_TIME timeliness for a NOT_ISSUED origin (clock injected) is caught by the post gate
        put({"run_id": "A3", "code_sha256": "x", "status": "AFTER_CUTOFF", "txs": [],
             "not_issued": [{"origin": "2026-10-09", "horizons": "1D", "deadline_utc": "2026-10-08T23:30:00Z"}]})
        FC.commit_tx(str(stage), gitrepo.RealGit(work, message="t"))
        put(tx("R4", "2026-10-09"))
        ck = ["2026-10-08T23:00:00Z", "2026-10-08T23:00:05Z"]                              # before the deadline
        try:
            FC.commit_tx(str(stage), gitrepo.RealGit(work, message="t"), lambda: ck.pop(0))
            raise AssertionError("ON_TIME after NOT_ISSUED accepted")
        except FC.PipelineFailure as e:
            assert str(e) == "DEADLINE_AUDIT_GATE_POST"
        # the synced tree now violates the gate -> every later run refuses before writing anything
        before = {p: (work / p).read_bytes() for p in (L.COMMITS, L.DEADLINE, L.FORECASTS)}
        put({"run_id": "A4", "code_sha256": "x", "status": "AFTER_CUTOFF", "txs": [], "not_issued": ni})
        try:
            FC.commit_tx(str(stage), gitrepo.RealGit(work, message="t")); raise AssertionError("pre gate passed")
        except FC.PipelineFailure as e:
            assert str(e) == "DEADLINE_AUDIT_GATE_PRE"
        assert before == {p: (work / p).read_bytes() for p in before}
    finally:
        FC.ROOT = old


def run():
    unit()
    with tempfile.TemporaryDirectory() as td:
        history_on_git(td)
        commit_path(td)
    return {"ok": True}


if __name__ == "__main__":
    print(run())
