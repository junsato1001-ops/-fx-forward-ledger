"""D10 workflow-set completeness gate on a GENERATED CODE_MANIFEST_V1 (IMPL-FINDINGS-03 修正仕様, むすび PASS 2026-10-18).

Checks the manifest file as produced (not the PATTERNS that produced it):
  1. required entries are present: m1macro/manifest.py, this gate, and the three named m1macro workflows;
  2. {repository .github/workflows/m1macro_*.yml} == {workflows listed in the manifest} (missing or extra -> FAIL);
  3. every manifest entry's SHA-256 equals the file on disk, and the manifest is well formed.
Independent path by design: nothing is imported from manifest.py or canon.py, the repository side is enumerated with
os.scandir + an explicit name rule (not Path.glob of PATTERNS), and hashes are recomputed here. Standard library only.

usage: python -I m1macro/manifest_gate.py <generated_manifest_file> [<repo_root>]   (prints JSON; exit 1 on FAIL)
"""
import hashlib
import json
import os
import re
import sys
from pathlib import Path

WF_DIR = ".github/workflows"
WF_NAME = re.compile(r"\Am1macro_[^/]*\.yml\Z")
REQUIRED = ("m1macro/manifest.py", "m1macro/manifest_gate.py", ".github/workflows/m1macro_forward.yml",
            ".github/workflows/m1macro_snapshot_acquire.yml", ".github/workflows/m1macro_gates.yml")
LINE = re.compile(r"\A([^,\n\r]+),([0-9a-f]{64})\Z")


def parse(b: bytes):
    """CODE_MANIFEST_V1 bytes -> list of (path, sha256). Raises ValueError if malformed."""
    if not b.endswith(b"\n"):
        raise ValueError("no final newline")
    lines = b.decode("utf-8").split("\n")[:-1]
    if not lines or lines[0] != "CODE_MANIFEST_V1":
        raise ValueError("bad header")
    out = []
    for ln in lines[1:]:
        m = LINE.match(ln)
        if not m:
            raise ValueError("bad line")
        out.append((m.group(1), m.group(2)))
    paths = [p for p, _ in out]
    if paths != sorted(paths) or len(set(paths)) != len(paths):
        raise ValueError("not sorted or duplicated")
    return out


def repo_workflows(root) -> set:
    d = os.path.join(root, WF_DIR)
    if not os.path.isdir(d):
        return set()
    with os.scandir(d) as it:
        return {f"{WF_DIR}/{e.name}" for e in it if e.is_file(follow_symlinks=False) and WF_NAME.match(e.name)}


def check(manifest_bytes: bytes, root) -> dict:
    res = {"gate": "D10_CODE_MANIFEST_WORKFLOW_SET", "pass": False, "violations": []}
    try:
        ents = parse(manifest_bytes)
    except ValueError as e:
        res["violations"].append("MANIFEST_MALFORMED:" + str(e)); return res
    listed = {p for p, _ in ents}
    in_manifest_wf = {p for p in listed if p.startswith(WF_DIR + "/") and WF_NAME.match(p[len(WF_DIR) + 1:])}
    on_disk_wf = repo_workflows(root)
    res["workflows_repository"] = sorted(on_disk_wf)
    res["workflows_manifest"] = sorted(in_manifest_wf)
    for p in REQUIRED:
        if p not in listed:
            res["violations"].append("REQUIRED_MISSING:" + p)
    for p in sorted(on_disk_wf - in_manifest_wf):
        res["violations"].append("WORKFLOW_NOT_IN_MANIFEST:" + p)
    for p in sorted(in_manifest_wf - on_disk_wf):
        res["violations"].append("MANIFEST_WORKFLOW_NOT_IN_REPOSITORY:" + p)
    for p, h in ents:
        f = Path(root, p)
        if not f.is_file():
            res["violations"].append("ENTRY_FILE_MISSING:" + p)
        elif hashlib.sha256(f.read_bytes()).hexdigest() != h:
            res["violations"].append("ENTRY_SHA_MISMATCH:" + p)
    res["n_entries"] = len(ents)
    res["manifest_sha256"] = hashlib.sha256(manifest_bytes).hexdigest()
    res["pass"] = not res["violations"]
    return res


if __name__ == "__main__":
    if len(sys.argv) not in (2, 3):
        raise SystemExit("usage: manifest_gate.py <generated_manifest_file> [<repo_root>]")
    root = sys.argv[2] if len(sys.argv) == 3 else str(Path(__file__).resolve().parent.parent)
    r = check(Path(sys.argv[1]).read_bytes(), root)
    print(json.dumps(r, sort_keys=True))
    raise SystemExit(0 if r["pass"] else 1)
