"""F1 (むすび 2026-10-18): two-stage implementation-freeze transaction on a temporary git repository.
FINAL only with record + one COMPLETE marker + audit row with anchor and D2 PASS; every failure path is not final."""
import datetime as dt
import hashlib
import json
import tempfile
from pathlib import Path

from m1macro import freeze_record as F, gitrepo
from m1macro.test_gitrepo_tx import _hook, _repo

FIRST = {"1D": "2026-11-10", "1W": "2026-11-15", "4W": "2026-11-15"}
UTC = dt.timezone.utc


def _rec(code="c" * 64, first=FIRST):
    return F.record_bytes({"Spec": "M1-MACRO-IMPL-CODE-V1", "Code_SHA256": code, "First_Forward_Origin": first,
                           "CFTC_Snapshot_Window_Hours": 6})


def _clock(*ts):
    q = [dt.datetime.fromisoformat(t).replace(tzinfo=UTC) for t in ts]
    return lambda: q.pop(0)


def write_final(root, code_sha, first=FIRST):
    """Test fixture: a consistent FINAL freeze state (record, marker, audit) in a working tree."""
    root = Path(root); rec = _rec(code_sha, first); af = F.a_first(first, 6)
    t0 = min(af.values()) - dt.timedelta(days=2)                     # freeze well before every A_first(h)
    ts = lambda s: F.utc_s(t0 + dt.timedelta(seconds=s))
    m = {"Run_ID": "FZ", "Run_Attempt": "1", "Record_Path": F.RECORD, "Record_SHA256": hashlib.sha256(rec).hexdigest(),
         "Record_Main_Commit": "0" * 40, "Code_SHA256": code_sha, "Record_Reread_At_UTC": ts(10),
         "Status": "COMPLETE", "Recorded_At_UTC": ts(11)}
    a = {"Run_ID": "FZ", "Run_Attempt": "1", "Code_SHA256": code_sha, "Run_Started_At_Server_UTC": ts(0),
         "Record_Reread_At_UTC": m["Record_Reread_At_UTC"], "Recorded_At_UTC": m["Recorded_At_UTC"],
         "Marker_Reread_At_UTC": ts(20), "Anchor_Status": "PASS",
         **{f"A_First_{h}_UTC": F.utc_s(af[h]) for h in F.HORIZONS}, "D2_Status": "PASS", "Freeze_Status": "FINAL"}
    for p, b in ((F.RECORD, rec), (F.MARKER, F.header_bytes(F.MARKER_FIELDS) + F.row_bytes(F.MARKER_FIELDS, m)),
                 (F.AUDIT, F.header_bytes(F.AUDIT_FIELDS) + F.row_bytes(F.AUDIT_FIELDS, a))):
        (root / p).parent.mkdir(parents=True, exist_ok=True); (root / p).write_bytes(b)


def _tx(td, name, run_start, clock, reject=(), fail_remote=(), first=FIRST):
    bare, work = _repo(td, name)
    _hook(bare, reject)
    g = gitrepo.RealGit(work, message="freeze")
    orig = g.remote
    def remote(p):
        if p in fail_remote:
            raise gitrepo.GitError("injected")
        return orig(p)
    g.remote = remote
    ids = {"Run_ID": "R9", "Run_Attempt": "1", "Code_SHA256": "c" * 64}
    rs = dt.datetime.fromisoformat(run_start).replace(tzinfo=UTC)
    head = lambda: "h" * 40
    try:
        out = F.transaction(g, _rec(first=first), ids, rs, F.a_first(first, 6), clock, head)
    except F.FreezeRefused as e:
        out = {"refused": str(e)}
    import subprocess                                   # finality is judged on the REMOTE main (what forward runs sync)
    rd = lambda p: subprocess.run(["git", "--git-dir", str(bare), "show", f"main:{p}"], capture_output=True).stdout
    final = F.is_final(rd(F.RECORD), rd(F.MARKER), rd(F.AUDIT), "c" * 64, first)
    return out, final, work, bare


def run():
    af = F.a_first(FIRST, 6)
    assert F.utc_s(af["1D"]) == "2026-11-09T12:00:00Z" and F.utc_s(af["1W"]) == "2026-11-14T12:00:00Z"
    # independent of freeze_gate (zoneinfo + cftc_feature.WINDOW): same values; config window == code window
    from m1macro import cftc_feature, freeze_gate
    cfg = json.loads((F.ROOT / "m1macro/config/m1macro_config.json").read_text("utf-8"))
    assert cftc_feature.WINDOW == dt.timedelta(hours=int(cfg["cftc_snapshot_window_hours"]))
    fg = freeze_gate.a_first(freeze_gate.first_origins({"first_forward_origin": FIRST}))
    assert {h: F.utc_s(fg[h]) for h in F.HORIZONS} == {h: F.utc_s(af[h]) for h in F.HORIZONS}
    ok_clock = lambda: _clock("2026-10-20T00:00:10", "2026-10-20T00:00:11", "2026-10-20T00:00:20")
    with tempfile.TemporaryDirectory() as td:
        # 1) success: FINAL, three files on the remote, exactly one marker and one audit row
        out, final, work, bare = _tx(td, "ok", "2026-10-20T00:00:00", ok_clock())
        assert out["Freeze_Status"] == "FINAL" and final, out
        assert out["Recorded_At_UTC"] == "2026-10-20T00:00:11Z"
        # 2) a second freeze on the same tree is refused before writing
        g = gitrepo.RealGit(work, message="again")
        try:
            F.transaction(g, _rec(), {"Run_ID": "R10", "Run_Attempt": "1", "Code_SHA256": "c" * 64},
                          dt.datetime(2026, 10, 20, tzinfo=UTC), af, ok_clock(), lambda: "h")
            raise AssertionError("second freeze accepted")
        except F.FreezeRefused as e:
            assert str(e) == "FREEZE_ALREADY_RECORDED"
        # 3) anchor violations -> REJECTED, not final
        out, final, *_ = _tx(td, "early", "2026-10-20T00:00:15", ok_clock())          # runner clock before server start
        assert out["Anchor_Status"] == "FAIL" and out["Freeze_Status"] == "REJECTED" and not final
        # 4) D2: Recorded_At at A_first(1D) -> REJECTED (strict inequality)
        out, final, *_ = _tx(td, "late", "2026-11-09T11:59:00",
                             _clock("2026-11-09T11:59:59", "2026-11-09T12:00:00", "2026-11-09T12:00:01"))
        assert out["Anchor_Status"] == "PASS" and out["D2_Status"] == "FAIL" and not final
        out, final, *_ = _tx(td, "edge", "2026-11-09T11:59:00",
                             _clock("2026-11-09T11:59:58", "2026-11-09T11:59:59", "2026-11-09T12:00:30"))
        assert out["Freeze_Status"] == "FINAL" and final                                   # marker reread may be later
        # 5) push failures at A, B, C and reread failures -> refused, not final; partial files stay on the remote
        # pushes are counted per attempt (5 retries): A = 1, B = 2, C = 3 when nothing fails
        for i, (rej, fr, code) in enumerate((((1, 2, 3, 4, 5), (), "RECORD_PUSH_FAILED"),
                                            ((), (F.RECORD,), "RECORD_REREAD_FAILED"),
                                            ((2, 3, 4, 5, 6), (), "MARKER_PUSH_FAILED"),
                                            ((), (F.MARKER,), "MARKER_REREAD_FAILED"),
                                            ((3, 4, 5, 6, 7), (), "AUDIT_PUSH_FAILED"),
                                            ((), (F.AUDIT,), "AUDIT_REREAD_FAILED"))):
            out, final, *_ = _tx(td, f"f{i}", "2026-10-20T00:00:00", ok_clock(), reject=rej, fail_remote=fr)
            # the audit row did reach main when only its reread failed: main decides (FINAL), the run reports failure
            assert out == {"refused": code} and final == (code == "AUDIT_REREAD_FAILED"), (code, out, final)
    # 6) is_final rejects tampering: record bytes changed, second marker, audit edited, wrong first origins, wrong code
    with tempfile.TemporaryDirectory() as td:
        write_final(td, "c" * 64)
        assert F.is_final_tree(td, "c" * 64, FIRST) and F.is_final_tree(td, "c" * 64)
        assert not F.is_final_tree(td, "d" * 64) and not F.is_final_tree(td, "c" * 64, {**FIRST, "1D": "2026-11-11"})
        p = Path(td)
        orig = {x: (p / x).read_bytes() for x in (F.RECORD, F.MARKER, F.AUDIT)}
        for path, new in ((F.RECORD, orig[F.RECORD].replace(b"\n}", b',"x":1\n}')),
                          (F.MARKER, orig[F.MARKER] + orig[F.MARKER].split(b"\n", 1)[1]),
                          (F.AUDIT, orig[F.AUDIT].replace(b"2026-11-07T12:00:00Z", b"2026-11-07T12:00:12Z")),  # start > reread
                          (F.AUDIT, orig[F.AUDIT].replace(b"FINAL", b"REJECTED")),
                          (F.AUDIT, orig[F.AUDIT].replace(b"2026-11-09T12:00:00Z", b"2026-11-09T13:00:00Z")),
                          (F.AUDIT, b"")):
            (p / path).write_bytes(new)
            assert not F.is_final_tree(td, "c" * 64), path
            (p / path).write_bytes(orig[path])
        assert F.is_final_tree(td, "c" * 64)
    return {"ok": True}


if __name__ == "__main__":
    print(run())
