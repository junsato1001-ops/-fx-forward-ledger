"""F1 (むすび 2026-10-18): two-stage implementation-freeze transaction on a temporary git repository.
FINAL only with record + one COMPLETE marker + audit row with server anchors (run start, marker push) and D2 PASS
on the SERVER push time; every failure path is not final. F1-d: freeze requires a consistent all-PASS G1-G9 verdict."""
import datetime as dt
import hashlib
import io
import json
import subprocess
import tempfile
from pathlib import Path

from m1macro import freeze_record as F, gate_verdict, gates, gitrepo
from m1macro.test_gitrepo_tx import _hook, _repo

FIRST = {"1D": "2026-11-10", "1W": "2026-11-15", "4W": "2026-11-15"}
UTC = dt.timezone.utc
SNAP = "5" * 64


def _rec(code="c" * 64, first=FIRST):
    return F.record_bytes({"Spec": "M1-MACRO-IMPL-CODE-V1", "Code_SHA256": code, "First_Forward_Origin": first,
                           "CFTC_Snapshot_Window_Hours": 6})


def _t(s):
    return dt.datetime.fromisoformat(s).replace(tzinfo=UTC)


def _clock(*ts):
    q = [_t(t) for t in ts]
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
         "Marker_Reread_At_UTC": ts(20), "Marker_Commit": "1" * 40, "Marker_Push_Activity_ID": "77",
         "Marker_Push_At_Server_UTC": ts(14), "Anchor_Status": "PASS",
         **{f"A_First_{h}_UTC": F.utc_s(af[h]) for h in F.HORIZONS}, "D2_Status": "PASS", "Freeze_Status": "FINAL",
         "Reject_Reason": ""}
    for p, b in ((F.RECORD, rec), (F.MARKER, F.header_bytes(F.MARKER_FIELDS) + F.row_bytes(F.MARKER_FIELDS, m)),
                 (F.AUDIT, F.header_bytes(F.AUDIT_FIELDS) + F.row_bytes(F.AUDIT_FIELDS, a))):
        (root / p).parent.mkdir(parents=True, exist_ok=True); (root / p).write_bytes(b)


def _tx(td, name, run_start, clock, push=None, reject=(), fail_remote=(), first=FIRST, parent_fail=False):
    """push: None -> server push time = 2 s after the marker reread clock value; a string -> that server time;
    'MISSING' -> no push event."""
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
    head = lambda: subprocess.run(["git", "rev-parse", "HEAD"], cwd=work, capture_output=True).stdout.decode().strip()
    seen = {}
    def push_time(commit, parent=None):
        seen["commit"] = commit; seen["parent"] = parent
        if push == "MISSING":
            raise F.PushNotFound("PUSH_EVENT_NOT_FOUND")
        rp = lambda r: subprocess.run(["git", "--git-dir", str(bare), "rev-parse", r], capture_output=True).stdout.decode().strip()
        assert commit == rp("main") and parent == rp("main^")   # the commit queried is on the remote; F8-a its parent
        return "4242", _t(push)
    parent_of = lambda c: subprocess.run(["git", "rev-parse", c + ("^^^^^^^^^" if parent_fail else "^")], cwd=work,
                                         capture_output=True, check=True).stdout.decode().strip()
    try:
        out = F.transaction(g, _rec(first=first), ids, _t(run_start), F.a_first(first, 6), clock, head, push_time, parent_of)
    except F.FreezeRefused as e:
        out = {"refused": str(e)}
    rd = lambda p: subprocess.run(["git", "--git-dir", str(bare), "show", f"main:{p}"], capture_output=True).stdout
    final = F.is_final(rd(F.RECORD), rd(F.MARKER), rd(F.AUDIT), "c" * 64, first)    # judged on the REMOTE main
    return out, final, work, bare, seen


def unit_find_push():
    c = "a" * 40
    ev = lambda **k: {"id": 1, "activity_type": "push", "ref": "refs/heads/main", "after": c, "before": "p" * 40,
                      "actor": {"login": F.ACTIONS_ACTOR}, "timestamp": "2026-10-20T00:00:14Z", **k}
    assert F.find_push([ev(), ev(after="b" * 40, id=2)], c) == ("1", _t("2026-10-20T00:00:14"))
    for evs, code in (([], "PUSH_EVENT_NOT_FOUND"), ([ev(after="b" * 40)], "PUSH_EVENT_NOT_FOUND"),
                      ([ev(ref="refs/heads/x")], "PUSH_EVENT_NOT_FOUND"), ([ev(activity_type="force_push")], "PUSH_EVENT_NOT_FOUND"),
                      ([ev(), ev(id=2)], "PUSH_EVENT_NOT_UNIQUE")):
        try:
            F.find_push(evs, c); raise AssertionError(code)
        except F.PushNotFound as e:
            assert str(e) == code
    # F8-a: parent (`before`) and pusher must match when required
    assert F.find_push([ev()], c, parent="p" * 40, actor=F.ACTIONS_ACTOR) == ("1", _t("2026-10-20T00:00:14"))
    for kw, code in (({"parent": "q" * 40}, "PUSH_EVENT_PARENT_MISMATCH"), ({"actor": "someone"}, "PUSH_EVENT_ACTOR_MISMATCH")):
        try:
            F.find_push([ev()], c, **kw); raise AssertionError(code)
        except F.PushNotFound as e:
            assert str(e) == code
    # activity_lookup: fixed polling (the event appears on the 3rd poll), then fail closed after ACTIVITY_POLLS
    import urllib.request
    calls = {"n": 0, "sleep": []}
    class Resp(io.BytesIO):
        headers = {}
        def __enter__(self): return self
        def __exit__(self, *a): return False
    def fake(req, timeout=30):
        calls["n"] += 1
        return Resp(json.dumps([ev()] if calls["n"] >= 3 else []).encode())
    orig = urllib.request.urlopen; urllib.request.urlopen = fake
    try:
        pt = F.activity_lookup("o/r", "t", sleep=lambda s: calls["sleep"].append(s))
        assert pt(c) == ("1", _t("2026-10-20T00:00:14")) and calls["n"] == 3 and calls["sleep"] == [F.ACTIVITY_POLL_SEC] * 2
        calls["n"] = -10**6
        try:
            pt(c); raise AssertionError("not found accepted")
        except F.PushNotFound as e:
            assert str(e) == "PUSH_EVENT_NOT_FOUND"
        # F8-a: the event is on page 3 of the activity list (Link rel="next" followed); other pushes on pages 1-2
        pages = {"p1": ([ev(after="x" * 40)] * 100, "p2"), "p2": ([ev(after="y" * 40)] * 100, "p3"), "p3": ([ev()], None)}
        def paged(req, timeout=30):
            key = req.full_url.rsplit("cur=", 1)[1] if "cur=" in req.full_url else "p1"
            body, nxt = pages[key]
            r = Resp(json.dumps(body).encode())
            r.headers = {"Link": f'<https://api.github.com/x?cur={nxt}>; rel="next"'} if nxt else {}
            return r
        urllib.request.urlopen = paged
        assert F.activity_lookup("o/r", "t", sleep=lambda s: None)(c, "p" * 40) == ("1", _t("2026-10-20T00:00:14"))
        for kw, code in ((("q" * 40,), "PUSH_EVENT_PARENT_MISMATCH"),):
            try:
                F.activity_lookup("o/r", "t", sleep=lambda s: (_ for _ in ()).throw(AssertionError("retried")))(c, *kw)
                raise AssertionError(code)
            except F.PushNotFound as e:
                assert str(e) == code                      # final at once, no polling
        try:
            F.activity_lookup("o/r", "t", sleep=lambda s: None, actor="other")(c)
            raise AssertionError("actor")
        except F.PushNotFound as e:
            assert str(e) == "PUSH_EVENT_ACTOR_MISMATCH"
        # endless pagination -> fail closed (never a partial list)
        def endless(req, timeout=30):
            r = Resp(b"[]"); r.headers = {"Link": '<https://api.github.com/x?cur=z>; rel="next"'}; return r
        urllib.request.urlopen = endless
        try:
            F.activity_lookup("o/r", "t", sleep=lambda s: None)(c); raise AssertionError("pages")
        except F.PushNotFound as e:
            assert str(e) == "ACTIVITY_PAGES_EXCEEDED"
        # API down for the whole fixed wait -> fail closed
        def down(req, timeout=30):
            raise OSError("down")
        urllib.request.urlopen = down; n_sleep = []
        try:
            F.activity_lookup("o/r", "t", sleep=n_sleep.append)(c); raise AssertionError("down")
        except F.PushNotFound as e:
            assert str(e) == "ACTIVITY_API_FAILED" and len(n_sleep) == F.ACTIVITY_POLLS - 1
    finally:
        urllib.request.urlopen = orig
    assert F.ACTIVITY_POLLS * F.ACTIVITY_POLL_SEC == 180


def run():
    gate_results_negative()
    unit_find_push()
    af = F.a_first(FIRST, 6)
    assert F.utc_s(af["1D"]) == "2026-11-09T12:00:00Z" and F.utc_s(af["1W"]) == "2026-11-14T12:00:00Z"
    from m1macro import cftc_feature, freeze_gate               # independent of freeze_gate: same values
    cfg = json.loads((F.ROOT / "m1macro/config/m1macro_config.json").read_text("utf-8"))
    assert cftc_feature.WINDOW == dt.timedelta(hours=int(cfg["cftc_snapshot_window_hours"]))
    fg = freeze_gate.a_first(freeze_gate.first_origins({"first_forward_origin": FIRST}))
    assert {h: F.utc_s(fg[h]) for h in F.HORIZONS} == {h: F.utc_s(af[h]) for h in F.HORIZONS}
    ok_clock = lambda: _clock("2026-10-20T00:00:10", "2026-10-20T00:00:11", "2026-10-20T00:00:20")
    P = "2026-10-20T00:00:14"
    with tempfile.TemporaryDirectory() as td:
        # 1) success: FINAL; the queried commit is the remote main carrying the marker
        out, final, work, bare, seen = _tx(td, "ok", "2026-10-20T00:00:00", ok_clock(), push=P)
        assert out["Freeze_Status"] == "FINAL" and final and out["Reject_Reason"] == "", out
        assert out["Marker_Push_At_Server_UTC"] == "2026-10-20T00:00:14Z" and out["Marker_Commit"] == seen["commit"]
        fresh_audit_git(work, out, seen)
        # 2) a second freeze on the same tree is refused before writing (no automatic second freeze)
        g = gitrepo.RealGit(work, message="again")
        try:
            F.transaction(g, _rec(), {"Run_ID": "R10", "Run_Attempt": "1", "Code_SHA256": "c" * 64},
                          _t("2026-10-20T00:00:00"), af, ok_clock(), lambda: "h", lambda c: ("1", _t(P)))
            raise AssertionError("second freeze accepted")
        except F.FreezeRefused as e:
            assert str(e) == "FREEZE_ALREADY_RECORDED"
        # 3) server anchors: runner Recorded_At before the server run start; Recorded_At after the server push
        out, final, *_ = _tx(td, "early", "2026-10-20T00:00:15", ok_clock(), push="2026-10-20T00:00:30")
        assert out["Anchor_Status"] == "FAIL" and out["Reject_Reason"] == "ANCHOR_ORDER" and not final
        out, final, *_ = _tx(td, "pushbefore", "2026-10-20T00:00:00", ok_clock(), push="2026-10-20T00:00:05")
        assert out["Anchor_Status"] == "FAIL" and not final
        # 3b) F8-a: the marker commit's parent cannot be determined -> REJECTED, the push event is not even queried
        out, final, _, _, seen2 = _tx(td, "noparent", "2026-10-20T00:00:00", ok_clock(), push=P, parent_fail=True)
        assert out["Freeze_Status"] == "REJECTED" and out["Reject_Reason"] == "MARKER_PARENT_UNKNOWN" and not final
        assert "commit" not in seen2
        # 4) no push event (or not unique) within the fixed wait -> REJECTED, fail closed
        out, final, *_ = _tx(td, "missing", "2026-10-20T00:00:00", ok_clock(), push="MISSING")
        assert out["Freeze_Status"] == "REJECTED" and out["Reject_Reason"] == "PUSH_EVENT_NOT_FOUND" and not final
        # 5) D2 on the SERVER push time (strict): runner times before A_first but push at A_first -> REJECTED
        late = _clock("2026-11-09T11:59:57", "2026-11-09T11:59:58", "2026-11-09T11:59:59")
        out, final, *_ = _tx(td, "late", "2026-11-09T11:59:00", late, push="2026-11-09T12:00:00")
        assert out["Anchor_Status"] == "PASS" and out["D2_Status"] == "FAIL" and out["Reject_Reason"] == "D2_NOT_BEFORE_A_FIRST"
        assert not final
        edge = _clock("2026-11-09T11:59:57", "2026-11-09T11:59:58", "2026-11-09T12:00:30")
        out, final, *_ = _tx(td, "edge", "2026-11-09T11:59:00", edge, push="2026-11-09T11:59:59")
        assert out["Freeze_Status"] == "FINAL" and final                                   # 1 s before: FINAL
        # 6) push failures at A, B, C and reread failures -> refused; pushes counted per attempt (A=1, B=2, C=3)
        for i, (rej, fr, code) in enumerate((((1, 2, 3, 4, 5), (), "RECORD_PUSH_FAILED"),
                                            ((), (F.RECORD,), "RECORD_REREAD_FAILED"),
                                            ((2, 3, 4, 5, 6), (), "MARKER_PUSH_FAILED"),
                                            ((), (F.MARKER,), "MARKER_REREAD_FAILED"),
                                            ((3, 4, 5, 6, 7), (), "AUDIT_PUSH_FAILED"),
                                            ((), (F.AUDIT,), "AUDIT_REREAD_FAILED"))):
            out, final, *_ = _tx(td, f"f{i}", "2026-10-20T00:00:00", ok_clock(), push=P, reject=rej, fail_remote=fr)
            # F1-a: only the final reread failed -> canonical main is FINAL; the run itself reports failure
            assert out == {"refused": code} and final == (code == "AUDIT_REREAD_FAILED"), (code, out, final)
    # 7) is_final rejects tampering
    with tempfile.TemporaryDirectory() as td:
        write_final(td, "c" * 64)
        assert F.is_final_tree(td, "c" * 64, FIRST) and F.is_final_tree(td, "c" * 64)
        assert not F.is_final_tree(td, "d" * 64) and not F.is_final_tree(td, "c" * 64, {**FIRST, "1D": "2026-11-11"})
        p = Path(td)
        orig = {x: (p / x).read_bytes() for x in (F.RECORD, F.MARKER, F.AUDIT)}
        for path, new in ((F.RECORD, orig[F.RECORD].replace(b"\n}", b',"x":1\n}')),
                          (F.MARKER, orig[F.MARKER] + orig[F.MARKER].split(b"\n", 1)[1]),
                          (F.AUDIT, orig[F.AUDIT].replace(b"2026-11-07T12:00:00Z", b"2026-11-07T12:00:12Z")),  # start > recorded
                          (F.AUDIT, orig[F.AUDIT].replace(b"2026-11-07T12:00:14Z", b"2026-11-09T12:00:00Z")),  # push at A_first
                          (F.AUDIT, orig[F.AUDIT].replace(b"2026-11-07T12:00:14Z", b"")),                        # no push time
                          (F.AUDIT, orig[F.AUDIT].replace(b",77,", b",,")),                                       # no activity id
                          (F.AUDIT, orig[F.AUDIT].replace(b"FINAL", b"REJECTED")),
                          (F.AUDIT, orig[F.AUDIT].replace(b"2026-11-09T12:00:00Z", b"2026-11-09T13:00:00Z")),
                          (F.AUDIT, b"")):
            (p / path).write_bytes(new)
            assert not F.is_final_tree(td, "c" * 64), (path, new[-200:])
            (p / path).write_bytes(orig[path])
        assert F.is_final_tree(td, "c" * 64)
        # F8-b: three FINAL files that are not bound to a git history never pass the fresh audit
        a = F._rows(orig[F.AUDIT])[0]
        rs = F.fresh_audit(td, "o/r", "t", push_time=lambda c, parent=None: ("77", F.parse_utc(a["Marker_Push_At_Server_UTC"])))
        assert rs["three_files_final"] and not rs["git_binding"] and not rs["pass"], rs
    return {"ok": True}


def fresh_audit_git(work, out, seen):
    """F8-a/F8-b: fresh audit of a real FINAL freeze on a git checkout. Pass only with the three files FINAL, bound to
    the git history, and the server push re-queried (after = Marker_Commit, before = its parent) equal to the record."""
    P = F.parse_utc(out["Marker_Push_At_Server_UTC"])
    q = {}
    def pt(commit, parent=None):
        q["c"], q["p"] = commit, parent
        return "4242", P
    rs = F.fresh_audit(work, "o/r", "t", push_time=pt)
    assert rs["pass"] and rs["git_binding"] and rs["server_anchor_matches"], rs
    assert q == {"c": seen["commit"], "p": seen["parent"]}
    for bad in (lambda c, parent=None: ("4243", P), lambda c, parent=None: ("4242", P + dt.timedelta(seconds=1))):
        assert not F.fresh_audit(work, "o/r", "t", push_time=bad)["pass"]
    def gone(c, parent=None):
        raise F.PushNotFound("PUSH_EVENT_NOT_FOUND")
    r = F.fresh_audit(work, "o/r", "t", push_time=gone)
    assert not r["pass"] and r["reason"] == "PUSH_EVENT_NOT_FOUND"
    git = lambda *a: subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@e", *a], cwd=work, check=True,
                                    capture_output=True)
    m, au = Path(work, F.MARKER), Path(work, F.AUDIT)
    m0, a0 = m.read_bytes(), au.read_bytes()
    # audit row names a different commit (the record commit): not the commit that carries the marker
    rc = F._rows(m0)[0]["Record_Main_Commit"]
    au.write_bytes(a0.replace(out["Marker_Commit"].encode(), rc.encode()))
    assert not F.fresh_audit(work, "o/r", "t", push_time=pt)["git_binding"]
    au.write_bytes(a0)
    # marker rewritten in a later commit: the current marker is not the one in Marker_Commit
    m.write_bytes(m0.replace(b"COMPLETE", b"COMPLETE ")); git("commit", "-qam", "edit")
    assert not F.fresh_audit(work, "o/r", "t", push_time=pt)["pass"]
    git("reset", "-q", "--hard", "HEAD^")
    assert F.fresh_audit(work, "o/r", "t", push_time=pt)["pass"]


def _passing_results():
    """A complete, all-PASS formal gate result set (synthetic numbers), with its verdict."""
    s = {"test_solver": {"status": "PASS", "detail": {"ALL_OK": True}},
         "test_fullscale": {"status": "PASS", "detail": {"margin_ok_neg_side_le_1e-14": True}},
         "test_indep": {"status": "PASS", "detail": {"ALL_PASS": True}},
         **{t: {"status": "PASS", "detail": {}} for t in gate_verdict.G4_TESTS}}
    g5 = {"n_origins": 10, "n_th": {"1D": 6, "1W": 2, "4W": 2}, "holdout_rows": 0,
          "status_counts": {"F_US": {"OK": 10}, "F_JP": {"OK": 10}, "F_POS": {"OK": 7, "X": 3}}}
    keys = [(f"2020-01-{d:02d}", "1D") for d in range(1, 7)] + [(f"2020-02-{d:02d}", h) for d in (1, 2) for h in ("1W", "4W")]
    g5["th_universe"] = gates.th_keyset(keys)                              # F7-a
    g5["snapshot_manifest_sha256"] = SNAP                                  # F8-d
    g678 = {"G6": {"n_th": 10, "th_keyset": gates.th_keyset(keys), "errors": 0, "error_types": [], "n_estimated": 4, "n_pass_all": 4,
                   "max_abs_ub_minus_lb": 9e-14, "max_abs_phi2_minus_lb": 8e-14},
            "G7": {"n_shards": gate_verdict.N_SHARDS, "n_keys": 10, "n_run_A": 10, "n_run_B": 10, "n_rows_A": 10, "n_rows_B": 10,
                   "snapshot_manifest_sha256": [SNAP],
                   "e_input_sha_mismatch": 0,
                   "beta_sha_or_state_mismatch": 0},
            "G8": {"n_mu_zero_rows": 3, "n_match": 3, "n_mismatch": 0}}
    files = {"suite.json": json.dumps(s).encode(), "g5_summary.json": json.dumps(g5).encode(),
             "g678_summary.json": json.dumps(g678).encode(), "exits.txt": b""}
    with tempfile.TemporaryDirectory() as td:
        for n, b in files.items():
            Path(td, n).write_bytes(b)
        v = gate_verdict.verdict(td)
    assert v["all_pass"], v
    return files, v, g678


def gate_results_negative():
    """F5 / F1-d: freeze_record.gate_results accepts only FORMAL results for this Code_SHA256 and commit, with a
    gates_verdict.json that is all-PASS and equal to the verdict recomputed from the result files."""
    cs, cand = "c" * 64, "a" * 40
    def results(td, name, files):
        bare, work = _repo(td, name)
        git = lambda *a: subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@e", *a], cwd=work, check=True,
                                        capture_output=True)
        git("checkout", "-q", "--orphan", "m1macro-gates-results"); git("rm", "-rq", "--cached", ".")
        for n, b in files.items():
            p = Path(work, cs, n); p.parent.mkdir(parents=True, exist_ok=True); p.write_bytes(b)
        git("add", cs); git("commit", "-q", "-m", "r"); git("push", "-q", "origin", "m1macro-gates-results")
        git("checkout", "-q", "-f", "main")
        return work
    rf, v, g678 = _passing_results()
    vb = json.dumps(v).encode()
    prov = lambda **k: json.dumps({"ref_name": "m1macro-gates", "run_attempt": "1", "run_id": "555", "sha": cand, **k}).encode()
    base = {"code_sha256.txt": (cs + "\n").encode(), "source_commit.txt": (cand + "\n").encode(),
            "manifest_gate.json": b'{"pass": true}', "run_class.txt": b"FORMAL\n", **rf, "gates_verdict.json": vb,
            "run_provenance.json": prov()}
    RUN = {"id": 555, "run_attempt": 1, "path": F.GATES_WORKFLOW, "head_branch": "m1macro-gates", "head_sha": cand,
           "event": "push", "status": "completed", "conclusion": "success"}
    bad6 = json.loads(json.dumps(g678)); bad6["G6"]["errors"] = 3; bad6["G6"]["error_types"] = ["RuntimeError"]
    with tempfile.TemporaryDirectory() as td:
        for n, b in rf.items():
            Path(td, n).write_bytes(b)
        Path(td, "g678_summary.json").write_text(json.dumps(bad6))
        v_bad = gate_verdict.verdict(td)
    assert not v_bad["all_pass"] and not v_bad["G6"]["pass"]
    no = lambda k: {x: y for x, y in base.items() if x != k}
    cases = [(base, None),
             ({**base, "run_class.txt": b"DEVELOPMENT_BLIND\n"}, "GATE_RESULTS_NOT_FORMAL"),
             (no("run_class.txt"), "GATE_RESULTS_NOT_FORMAL"),
             ({**base, "source_commit.txt": b"b" * 40 + b"\n"}, "GATE_RESULTS_NOT_FOR_CANDIDATE"),
             ({**base, "suite.json": b'{"test_x": {"status": "FAIL"}}'}, "GATE_SUITE_NOT_PASS"),
             ({**base, "manifest_gate.json": b'{"pass": false}'}, "GATE_MANIFEST_NOT_PASS"),
             (no("gates_verdict.json"), "GATE_VERDICT_MISSING"),
             ({**base, "g678_summary.json": json.dumps(bad6).encode()}, "GATE_VERDICT_INCONSISTENT"),   # stored says PASS
             ({**base, "g678_summary.json": json.dumps(bad6).encode(), "gates_verdict.json": json.dumps(v_bad).encode()},
              "GATE_VERDICT_NOT_ALL_PASS"),
             ({**base, "exits.txt": b"SHARD_EXIT=1\n"}, "GATE_VERDICT_INCONSISTENT"),
             # F8-c provenance
             (no("run_provenance.json"), "GATE_PROVENANCE_MISSING"),
             ({**base, "run_provenance.json": b"{}"}, "GATE_PROVENANCE_MISSING"),
             ({**base, "run_provenance.json": prov(ref_name="m1macro-devblind")}, "GATE_RUN_MISMATCH"),
             ({**base, "run_provenance.json": prov(sha="b" * 40)}, "GATE_RUN_MISMATCH")]
    api_cases = [({}, None, "GATE_RUN_MISMATCH", "head_branch", "m1macro-devblind"),
                 ({}, None, "GATE_RUN_MISMATCH", "head_sha", "b" * 40),
                 ({}, None, "GATE_RUN_MISMATCH", "path", ".github/workflows/other.yml"),
                 ({}, None, "GATE_RUN_MISMATCH", "conclusion", "failure"),
                 ({}, None, "GATE_RUN_MISMATCH", "status", "in_progress"),
                 ({}, None, "GATE_RUN_MISMATCH", "run_attempt", 2),
                 ({}, "RUN_DOWN", "GATE_RUN_LOOKUP_FAILED", None, None),
                 ({}, "PUSH_EVENT_NOT_FOUND", "GATE_RESULTS_PUSH_EVENT_NOT_FOUND", None, None),
                 ({}, "PUSH_EVENT_ACTOR_MISMATCH", "GATE_RESULTS_PUSH_EVENT_ACTOR_MISMATCH", None, None)]
    def api(err=None, field=None, value=None):
        def run(i, a):
            if err == "RUN_DOWN":
                raise OSError("down")
            assert (i, a) == ("555", "1")
            return {**RUN, **({field: value} if field else {})}
        def push(commit, parent=None):
            if err and err != "RUN_DOWN":
                raise F.PushNotFound(err)
            return "9", F.parse_utc("2026-10-20T00:00:00Z")
        return {"run": run, "push": push}
    with tempfile.TemporaryDirectory() as td:
        for i, (files, want) in enumerate(cases):
            work = results(td, f"g{i}", files)
            try:
                r = F.gate_results(str(work), cs, cand, SNAP, api()); got = None
                assert r["Results_Dir"] == cs and set(r["Files_SHA256"]) == set(files)
                assert r["Gates_Run"] == {"Run_ID": "555", "Run_Attempt": "1"}
            except F.FreezeRefused as e:
                got = str(e)
            assert got == want, (i, got, want)
        work = results(td, "gapi", base)
        for j, (_, err, want, field, value) in enumerate(api_cases):
            try:
                F.gate_results(str(work), cs, cand, SNAP, api(err, field, value)); got = None
            except F.FreezeRefused as e:
                got = str(e)
            assert got == want, (j, got, want)
        # F8-d: results from another snapshot (or none named) are refused
        for snap in ("6" * 64, None):
            try:
                F.gate_results(str(work), cs, cand, snap, api()); raise AssertionError("snapshot")
            except F.FreezeRefused as e:
                assert str(e) == "GATE_SNAPSHOT_MISMATCH"


if __name__ == "__main__":
    print(run())
