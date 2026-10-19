"""IMPL-FINDINGS-09 (むすび 2026-10-19): fresh audit of the whole freeze evidence chain on real git repositories,
with synthetic gate results and fake GitHub APIs (no network, no real data).

  F8-f  gate evidence re-verified at the recorded Results_Commit (provenance, FORMAL, candidate, snapshot, verdict)
  14-day SERVER_REVERIFY_WINDOW: server records must be re-fetched and equal inside it (or when server time is
        unknown); afterwards an unavailable record is tolerated, a disagreeing one never
  F8-e  REJECTED consumes the Version: no second transaction; the audit file is write-once (REJECTED -> FINAL by
        editing fails the fresh audit)"""
import datetime as dt
import json
import subprocess
import tempfile
from pathlib import Path

from m1macro import freeze_record as F, gitrepo
from m1macro.test_freeze_record import FIRST, SNAP, _clock, _passing_results, _pre, _t
from m1macro.test_gitrepo_tx import _hook, _repo

CS, CAND = "c" * 64, "a" * 40
RUN = {"id": 555, "run_attempt": 1, "path": F.GATES_WORKFLOW, "head_branch": F.GATES_BRANCH, "head_sha": CAND,
       "event": "push", "status": "completed", "conclusion": "success"}
P = _t("2026-10-20T00:00:14")               # marker push (server)
T_RES = _t("2026-10-19T23:00:00")           # results push (server)


def _formal_files():
    rf, v, _ = _passing_results()
    return {"code_sha256.txt": (CS + "\n").encode(), "source_commit.txt": (CAND + "\n").encode(),
            "manifest_gate.json": b'{"pass": true}', "run_class.txt": b"FORMAL\n", **rf,
            "gates_verdict.json": json.dumps(v).encode(),
            "run_provenance.json": json.dumps({"ref_name": F.GATES_BRANCH, "run_attempt": "1", "run_id": "555",
                                               "sha": CAND}).encode()}


class Api:
    """Fake Actions + activity APIs. run: 'ok' | 'down' | dict override; push: 'ok' | PushNotFound code | ('id', time)."""
    def __init__(self, work, res_commit, run="ok", push="ok"):
        self.work, self.res_commit, self.run_mode, self.push_mode = work, res_commit, run, push

    def run(self, i, a):
        assert (i, a) == ("555", "1")
        if self.run_mode == "down":
            raise OSError("down")
        return {**RUN, **(self.run_mode if isinstance(self.run_mode, dict) else {})}

    def push(self, commit, parent=None, kind="push"):
        assert commit == self.res_commit and kind == "push"      # results commit with a parent: a push event
        assert parent == subprocess.run(["git", "rev-parse", commit + "^"], cwd=self.work, capture_output=True,
                                        check=True).stdout.decode().strip()
        if isinstance(self.push_mode, tuple):
            return self.push_mode
        if self.push_mode != "ok":
            raise F.PushNotFound(self.push_mode)
        return "9", T_RES

    def api(self):
        return {"run": self.run, "push": self.push}


def _setup(td, name, marker_push="ok"):
    """A FINAL (or, with marker_push='MISSING', REJECTED) freeze on a real main + a results branch with two commits."""
    bare, work = _repo(td, name); _hook(bare, ())
    git = lambda *a: subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@e", *a], cwd=work, check=True,
                                    capture_output=True).stdout.decode().strip()
    git("checkout", "-q", "--orphan", F.GATES_RESULTS_BRANCH); git("rm", "-rq", "--cached", ".")
    Path(work, "seed").mkdir(); Path(work, "seed", "x").write_text("x"); git("add", "seed"); git("commit", "-qm", "seed")
    git("rm", "-rq", "--cached", ".")
    for n, b in _formal_files().items():
        p = Path(work, CS, n); p.parent.mkdir(parents=True, exist_ok=True); p.write_bytes(b)
    git("add", CS); git("commit", "-qm", "FORMAL gates"); res_commit = git("rev-parse", "HEAD")
    git("push", "-q", "origin", F.GATES_RESULTS_BRANCH); git("checkout", "-q", "-f", "main")
    api = Api(work, res_commit)
    gr = F.gate_results(str(work), CS, CAND, SNAP, api.api())
    assert gr["Server_Evidence"] == {"run": "VERIFIED", "push": "VERIFIED"} and gr["Results_Commit"] == res_commit
    rec = F.record_bytes({"Spec": "M1-MACRO-IMPL-CODE-V1", "Code_SHA256": CS, "Candidate_Commit": CAND,
                          "First_Forward_Origin": FIRST, "CFTC_Snapshot_Window_Hours": 6,
                          "Dev_Snapshot": {"Manifest_SHA256": SNAP}, "Gate_Results": gr, "Pre_Freeze_Gate": _pre()})
    g = gitrepo.RealGit(work, message="freeze")
    head = lambda: git("rev-parse", "HEAD")
    parent_of = lambda c: git("rev-parse", c + "^")

    def push_time(c, parent=None):
        if marker_push == "MISSING":
            raise F.PushNotFound("PUSH_EVENT_NOT_FOUND")
        return "4242", P
    out = F.transaction(g, rec, {"Run_ID": "R9", "Run_Attempt": "1", "Code_SHA256": CS}, _t("2026-10-20T00:00:00"),
                        F.a_first(FIRST, 6), _clock("2026-10-20T00:00:10", "2026-10-20T00:00:11", "2026-10-20T00:00:20"),
                        head, push_time, parent_of)
    return work, git, api, out


def _marker_pt(work, mode="ok"):
    def pt(c, parent=None):
        audit = F._rows(Path(work, F.AUDIT).read_bytes())[0]
        assert c == audit["Marker_Commit"] and parent == subprocess.run(
            ["git", "rev-parse", c + "^"], cwd=work, capture_output=True, check=True).stdout.decode().strip()
        if isinstance(mode, tuple):
            return mode
        if mode != "ok":
            raise F.PushNotFound(mode)
        return "4242", P
    return pt


def run():
    out_cases = {}
    # unit: window boundary (inclusive 14 days) and fail-closed unknown time
    assert F.SERVER_REVERIFY_WINDOW == dt.timedelta(days=14)
    assert F.audit_mode(P + dt.timedelta(days=14), P) == "WINDOW"
    assert F.audit_mode(P + dt.timedelta(days=14, seconds=1), P) == "LONG_TERM"
    assert F.audit_mode(None, P) == "WINDOW" and F.audit_mode(P, None) == "WINDOW"
    # unit: freeze_state
    hdr = F.header_bytes(F.AUDIT_FIELDS)
    row = lambda st: F.row_bytes(F.AUDIT_FIELDS, {"Freeze_Status": st})
    assert F.freeze_state(b"", b"", b"") == "NONE"
    assert F.freeze_state(b"r", b"m", hdr + row("FINAL")) == "FINAL"
    assert F.freeze_state(b"r", b"m", hdr + row("REJECTED")) == "REJECTED"
    assert F.freeze_state(b"r", b"m", hdr + row("REJECTED") + row("FINAL")) == "REJECTED"   # never revived
    assert F.freeze_state(b"r", b"m", hdr + row("FINAL") + row("FINAL")) == "INCOMPLETE"
    assert F.freeze_state(b"r", b"", b"") == "INCOMPLETE"

    with tempfile.TemporaryDirectory() as td:
        work, git, api, out = _setup(td, "ok")
        assert out["Freeze_Status"] == "FINAL"

        def fa(now=P + dt.timedelta(days=1), marker="ok", run="ok", push="ok", code=CS):
            a = Api(work, api.res_commit, run, push)
            return F.fresh_audit(work, "o/r", "t", push_time=_marker_pt(work, marker), api=a.api(), now=now,
                                 auditor_code_sha=code)

        def expect(name, r, ok, **want):
            assert r["pass"] == ok, (name, r)
            for k, v in want.items():
                assert r.get(k) == v, (name, k, r)
            out_cases[name] = "PASS" if ok else "FAIL"

        L = P + dt.timedelta(days=15)
        expect("window_all_verified", fa(), True, mode="WINDOW", server_anchor="VERIFIED", gate_evidence=True,
               write_once=True, git_binding=True)
        expect("window_boundary_14d_marker_missing", fa(now=P + dt.timedelta(days=14), marker="PUSH_EVENT_NOT_FOUND"),
               False, mode="WINDOW", server_anchor="UNAVAILABLE")
        expect("window_marker_missing", fa(marker="PUSH_EVENT_NOT_FOUND"), False, server_anchor="UNAVAILABLE")
        expect("window_marker_api_down", fa(marker="ACTIVITY_API_FAILED"), False)
        expect("window_marker_time_differs", fa(marker=("4242", P + dt.timedelta(seconds=1))), False,
               server_anchor="MISMATCH")
        expect("window_run_lookup_down", fa(run="down"), False, gate_evidence=False, gate_reason="GATE_RUN_LOOKUP_FAILED")
        expect("window_results_push_missing", fa(push="PUSH_EVENT_NOT_FOUND"), False,
               gate_reason="GATE_RESULTS_PUSH_EVENT_NOT_FOUND")
        expect("window_results_push_differs", fa(push=("10", T_RES)), False,
               gate_reason="GATE_EVIDENCE_DIFFERS_FROM_RECORD")
        expect("server_time_unknown_is_window", fa(now=lambda: (_ for _ in ()).throw(OSError("x")),
                                                    marker="PUSH_EVENT_NOT_FOUND"), False, mode="WINDOW")
        # long-term mode: unavailable records tolerated, disagreeing records never
        expect("longterm_all_unavailable", fa(now=L, marker="PUSH_EVENT_NOT_FOUND", run="down", push="PUSH_EVENT_NOT_FOUND"),
               True, mode="LONG_TERM", server_anchor="UNAVAILABLE")
        expect("longterm_all_verified", fa(now=L), True, mode="LONG_TERM", server_anchor="VERIFIED")
        expect("longterm_marker_time_differs", fa(now=L, marker=("4242", P + dt.timedelta(seconds=1))), False)
        expect("longterm_marker_parent_mismatch", fa(now=L, marker="PUSH_EVENT_PARENT_MISMATCH"), False,
               server_anchor="FAILED")
        expect("longterm_marker_not_unique", fa(now=L, marker="PUSH_EVENT_NOT_UNIQUE"), False)
        expect("longterm_run_mismatch", fa(now=L, run={"head_sha": "b" * 40}), False, gate_reason="GATE_RUN_MISMATCH")
        expect("longterm_run_conclusion_failure", fa(now=L, run={"conclusion": "failure"}), False)
        expect("longterm_results_push_actor", fa(now=L, push="PUSH_EVENT_ACTOR_MISMATCH"), False,
               gate_reason="GATE_RESULTS_PUSH_EVENT_ACTOR_MISMATCH")
        expect("longterm_results_push_differs", fa(now=L, push=("10", T_RES)), False)
        expect("auditor_code_not_candidate", fa(code="d" * 64), False, auditor_code=False)

        # results branch rewritten (the recorded Results_Commit no longer on it) -> FAIL in every mode
        orig = git("rev-parse", f"origin/{F.GATES_RESULTS_BRANCH}")
        git("checkout", "-q", "--orphan", "tmp"); git("rm", "-rq", "--cached", ".")
        Path(work, "other").write_text("o"); git("add", "other"); git("commit", "-qm", "rewrite")
        git("push", "-qf", "origin", f"tmp:{F.GATES_RESULTS_BRANCH}"); git("checkout", "-q", "-f", "main")
        expect("results_commit_not_on_branch", fa(now=L), False, gate_reason="GATE_RESULTS_COMMIT_NOT_ON_BRANCH")
        git("push", "-qf", "origin", f"{orig}:refs/heads/{F.GATES_RESULTS_BRANCH}")
        expect("results_branch_restored", fa(), True)

        # F8-e write-once: an edit of the audit file in a later commit fails, even if the content still says FINAL
        au = Path(work, F.AUDIT); a0 = au.read_bytes()
        au.write_bytes(a0 + b"\n"); git("commit", "-qam", "edit audit")          # rows unchanged, file touched
        expect("audit_edited_later", fa(), False, write_once=False, three_files_final=True)
        git("reset", "-q", "--hard", "HEAD^")
        expect("audit_restored", fa(), True)

    with tempfile.TemporaryDirectory() as td:
        # F8-e: a REJECTED transaction consumes the Version
        work, git, api, out = _setup(td, "rej", marker_push="MISSING")
        assert out["Freeze_Status"] == "REJECTED" and out["Reject_Reason"] == "PUSH_EVENT_NOT_FOUND"
        assert F.freeze_state(*(Path(work, p).read_bytes() for p in (F.RECORD, F.MARKER, F.AUDIT))) == "REJECTED"
        g = gitrepo.RealGit(work, message="retry")
        try:
            F.transaction(g, b"{}", {"Run_ID": "R10", "Run_Attempt": "1", "Code_SHA256": CS}, P, F.a_first(FIRST, 6),
                          _clock(), lambda: "h", lambda c, p=None: ("1", P), lambda c: "p")
            raise AssertionError("retry on a REJECTED Version accepted")
        except F.FreezeRefused as e:
            assert str(e) == "VERSION_CONSUMED_REJECTED"
        out_cases["rejected_version_retry_refused"] = "REFUSED"
        # rewriting the REJECTED row into a FINAL-looking row (with a real push id/time) in a later commit
        au = Path(work, F.AUDIT); row = F._rows(au.read_bytes())[0]
        row.update(Marker_Push_Activity_ID="4242", Marker_Push_At_Server_UTC=F.utc_s(P), Anchor_Status="PASS",
                   D2_Status="PASS", Freeze_Status="FINAL", Reject_Reason="")
        au.write_bytes(F.header_bytes(F.AUDIT_FIELDS) + F.row_bytes(F.AUDIT_FIELDS, row)); git("commit", "-qam", "revive")
        r = F.fresh_audit(work, "o/r", "t", push_time=_marker_pt(work), api=Api(work, api.res_commit).api(),
                          now=P + dt.timedelta(days=1), auditor_code_sha=CS)
        assert r["three_files_final"] and not r["write_once"] and not r["pass"], r   # the content alone would pass
        out_cases["rejected_to_final_rewrite"] = "FAIL"
    return {"ok": True, "cases": out_cases}


if __name__ == "__main__":
    print(run())
