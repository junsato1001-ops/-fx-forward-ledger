"""G4 on a temporary git repository (Impl Part 4 §5 G4): transaction steps against a real bare remote, with
push rejections injected by a pre-receive hook and remote-read failures, before/after the deadline."""
import os
import subprocess
import tempfile
from pathlib import Path

from m1macro import gitrepo, ledger_tx as L
from m1macro.test_ledger_tx import _rows, DL


def _repo(td, name):
    bare = Path(td, name + ".git"); work = Path(td, name)
    subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(bare)], check=True)
    subprocess.run(["git", "clone", "-q", str(bare), str(work)], check=True, capture_output=True)
    (work / "README").write_text("x\n")
    for a in (["add", "README"], ["-c", "user.name=t", "-c", "user.email=t@e", "commit", "-q", "-m", "init"],
              ["push", "-q", "origin", "HEAD:main"]):
        subprocess.run(["git", *a], cwd=work, check=True, capture_output=True)
    return bare, work


def _hook(bare, reject_pushes):
    """Reject the k-th incoming push for k in reject_pushes (counter file in the bare repo)."""
    h = bare / "hooks" / "pre-receive"
    h.write_text("#!/bin/sh\nc=$(cat \"$GIT_DIR/cnt\" 2>/dev/null || echo 0); c=$((c+1)); echo $c > \"$GIT_DIR/cnt\"\n"
                 "case \" " + " ".join(map(str, reject_pushes)) + " \" in *\" $c \"*) exit 1;; esac\nexit 0\n")
    h.chmod(0o755)


def _run(td, name, reject=(), clock=("2026-11-01T22:00:00Z", "2026-11-01T22:01:00Z"), fail_remote=()):
    bare, work = _repo(td, name)
    _hook(bare, reject)
    g = gitrepo.RealGit(work, message="test")
    orig = g.remote
    def remote(p):
        if p in fail_remote:
            raise gitrepo.GitError("injected")
        return orig(p)
    g.remote = remote
    ck = list(clock)
    rows, fields = _rows()
    st = L.run_transaction(g, rows, fields, "R1", "2026-11-02", "1D", DL, lambda: ck.pop(0))
    def rb(p):
        r = subprocess.run(["git", "--git-dir", str(bare), "show", f"main:{p}"], capture_output=True)
        return r.stdout if r.returncode == 0 else b""
    return st, L.official_run_ids(rb(L.COMMITS), rb(L.DEADLINE)), rb


def run():
    out = {}
    with tempfile.TemporaryDirectory() as td:
        st, off, rb = _run(td, "ok"); assert st["status"] == "COMPLETE" and off == {"R1"}, st
        assert rb(L.FORECASTS).count(b"\n") == 4                                  # header + 3 rows, exactly once
        st, off, rb = _run(td, "p4", reject=(1, 2, 3, 4, 5)); assert st["failed_step"] == 4 and off == set()
        assert rb(L.FEATURES) == b""
        st, off, rb = _run(td, "p7", reject=(2, 3, 4, 5, 6)); assert st["failed_step"] == 7 and off == set()
        assert rb(L.FEATURES) != b"" and rb(L.COMMITS) == b""                      # UNCOMMITTED rows stay
        st, off, rb = _run(td, "p4retry", reject=(1, 2)); assert st["status"] == "COMPLETE" and off == {"R1"}
        st, off, rb = _run(td, "r5", fail_remote=(L.ESTIMATION,)); assert st["failed_step"] == 5 and off == set()
        st, off, rb = _run(td, "r8", fail_remote=(L.COMMITS,))
        assert st["status"] == "UNKNOWN_PENDING_REREAD" and off == set() and rb(L.COMMITS) != b""
        st, off, rb = _run(td, "p9", reject=(3, 4, 5, 6, 7)); assert st["deadline_status"] == "NOT_RECORDED" and off == set()
        st, off, rb = _run(td, "late", clock=("2026-11-01T23:29:59Z", "2026-11-01T23:30:01Z"))
        assert st["deadline_status"] == "LATE" and off == set() and b"LATE" in rb(L.DEADLINE)
        st, off, rb = _run(td, "edge", clock=("2026-11-01T23:29:58Z", "2026-11-01T23:30:00Z")); assert off == {"R1"}
    out["ok"] = True
    return out
