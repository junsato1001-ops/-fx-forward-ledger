"""CODE_MANIFEST_V1 and Code_SHA256 (Impl Part 4 §4). The file set is fixed here; this file is itself included."""
import hashlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from m1macro import canon  # noqa: E402

PATTERNS = [
    "m1macro/*.py", "m1macro/config/*.json", "m1macro/certs/*.pem", "m1macro/fixtures/*",
    "env/IMAGE", "env/IMAGE_DIGEST", "env/requirements.in", "env/requirements.lock",
    "frozen/m0_walkforward_v1_2.py", "frozen/origin_target_map_v1.py", "frozen/s0_empclim_std_exp_v1_1.py",
    "forward/ledger_builder.py", "tests/fixtures/eurofxref-hist_20261009.zip",
    ".github/workflows/m1macro_*.yml",
]


def files():
    out = set()
    for p in PATTERNS:
        out.update(x for x in ROOT.glob(p) if x.is_file() and "__pycache__" not in x.parts)
    return sorted(out, key=lambda x: x.relative_to(ROOT).as_posix())


def manifest_bytes() -> bytes:
    ents = [(f.relative_to(ROOT).as_posix(), hashlib.sha256(f.read_bytes()).hexdigest()) for f in files()]
    return canon.code_manifest_bytes(ents)


def code_sha256() -> str:
    return hashlib.sha256(manifest_bytes()).hexdigest()


if __name__ == "__main__":
    b = manifest_bytes()
    if len(sys.argv) > 1:
        Path(sys.argv[1]).write_bytes(b)
    print(hashlib.sha256(b).hexdigest())
