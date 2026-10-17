"""Git adapter for the issuance transaction (Impl Part 4 §3). Works on a clone of the public repository."""
import subprocess
from pathlib import Path


class GitError(Exception):
    pass


class RealGit:
    def __init__(self, repo_dir, branch="main", message="m1macro"):
        self.dir = Path(repo_dir); self.branch = branch; self.message = message
        self.touched = set(); self.pending = False

    def _g(self, *args, check=True):
        r = subprocess.run(["git", *args], cwd=self.dir, capture_output=True)
        if check and r.returncode != 0:
            raise GitError(f"git {args[0]} failed")           # no stderr text (could echo URLs)
        return r

    def ensure_header(self, path, header: bytes):
        p = self.dir / path
        if not p.exists():
            p.parent.mkdir(parents=True, exist_ok=True); p.write_bytes(header)
        elif not p.read_bytes().startswith(header):
            raise GitError(f"header mismatch {path}")
        self.touched.add(path)

    def append(self, path, b: bytes):
        with open(self.dir / path, "ab") as f:
            f.write(b)
        self.touched.add(path); self.pending = True

    def push(self):
        if self.pending:
            self._g("add", *sorted(self.touched))
            self._g("-c", "user.name=fx-forward-ledger-bot",
                    "-c", "user.email=41898282+github-actions[bot]@users.noreply.github.com", "commit", "-q", "-m", self.message)
            self.pending = False
        if self._g("push", "-q", "origin", f"HEAD:{self.branch}", check=False).returncode != 0:
            self._g("pull", "-q", "--rebase", "origin", self.branch, check=False)
            raise GitError("push rejected")

    def remote(self, path) -> bytes:
        self._g("fetch", "-q", "origin", self.branch)
        r = self._g("show", f"origin/{self.branch}:{path}", check=False)
        if r.returncode != 0:
            raise GitError(f"not on remote: {path}")
        return r.stdout
