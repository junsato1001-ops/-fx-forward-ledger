"""Host-side data commit (Part 4 §8): staged public files + fetch records + Treasury manifest rows reach the remote
byte-identically; a staged file that conflicts with an existing different file is refused."""
import json
import subprocess
import tempfile
from pathlib import Path

from m1macro import forward_commit as FC, gitrepo
from m1macro.test_gitrepo_tx import _repo


def run():
    with tempfile.TemporaryDirectory() as td:
        bare, work = _repo(td, "d")
        stage = Path(td, "stage"); (stage / "public" / "data/m1macro/mof").mkdir(parents=True)
        (stage / "public" / "data/m1macro/mof/x.csv").write_bytes(b"a,b\n")
        (stage / "fetches.json").write_text(json.dumps([{"Run_ID": "R", "Source": "mof", "Normal": "true", "SHA256": "s"}]))
        (stage / "treasury_staged.json").write_text(json.dumps([{"url": "u", "retrieved_at_utc": "t", "bytes": 3,
                                                               "sha256": "h", "private_path": "p"}]))
        (stage / "private_commit.txt").write_text("c" * 40 + "\n")
        old = FC.ROOT; FC.ROOT = work
        try:
            FC.commit_data(str(stage), gitrepo.RealGit(work, message="d"))
            show = lambda p: subprocess.run(["git", "--git-dir", str(bare), "show", f"main:{p}"], capture_output=True).stdout
            assert show("data/m1macro/mof/x.csv") == b"a,b\n"
            assert b"R,mof,,,,s,,true" in show(FC.FETCHES)
            assert show(FC.TREASURY_MANIFEST).splitlines()[1].endswith(b",p," + b"c" * 40)
            (stage / "public" / "data/m1macro/mof/x.csv").write_bytes(b"changed\n")
            try:
                FC.commit_data(str(stage), gitrepo.RealGit(work, message="d")); raise AssertionError("conflict accepted")
            except FC.PipelineFailure:
                pass
        finally:
            FC.ROOT = old
    return {"ok": True}
