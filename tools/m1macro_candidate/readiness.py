"""Candidate readiness machine check (IMPL-FINDINGS-10, むすび 2026-10-19 candidate assembly). Read-only.

Checks the CURRENT checkout (the candidate) against origin/main. No real data is read, nothing sealed is computed.
Outside CODE_MANIFEST_V1 (tools/). Exit 0 only if every check passes.

usage: python3 tools/m1macro_candidate/readiness.py <out_json> [--planned-freeze-utc YYYY-MM-DDTHH:MM:SSZ]
"""
import ast
import datetime as dt
import hashlib
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

REQUIRED_COMMITS = {        # fixes that must be in the candidate (ancestors of HEAD)
    "83f5025": "independent exact LB certification (IMPL-FINDINGS-03)",
    "9cfd825": "epigraph stall exact certification / Kelley exact dual simplex (F5-a)",
    "5abe8aa": "independent §6 exact min-norm stage",
    "5045178": "independent §6 internal refine 1e-14 (F6-a)",
    "f2aa130": "40 shards, full completion required (F5-b)",
    "e72e2d8": "F7-a (t, h) uniqueness",
    "15bb31d": "F8-a..F8-d",
    "4f21436": "F8-f, 14-day window, F8-e",
    "6f9e09d": "candidate-1: F10-a Part 3 §2 lower bound, F10-b debug path removed",
    "fb5e415": "F11-a activity type from git topology (root -> branch_creation, else push)",
}
ALLOWED_ENV = {"GITHUB_RUN_ID", "GITHUB_RUN_ATTEMPT", "GITHUB_REPOSITORY", "GITHUB_TOKEN", "GITHUB_WORKFLOW"}
SNAPSHOT_MAIN_COMMIT = "8ed83c23c42566fe5d91364ba035f750c5754041"     # one-shot acquisition (run 39045282957)
PRIVATE_SNAPSHOT_COMMIT = "f424840"
FROZEN_SOLVER = {"EPS_TIE": 1e-13, "LAMBDA_LEV": 0.3, "BOX_B": 10.0, "CAND_SIZES": (8, 12, 16, 24), "STAGE1_MAX": 3000,
                 "STAGE2_MAX": 100, "LP_TOL": 1e-10}                  # Impl Part 2 V1 (frozen)


def sh(*a):
    r = subprocess.run(list(a), cwd=ROOT, capture_output=True)
    return r.returncode, r.stdout


def main(argv):
    out_path = Path(argv[0]); args = dict(zip(argv[1::2], argv[2::2]))
    res = {"checks": {}, "info": {}}
    def check(name, ok, **info):
        res["checks"][name] = bool(ok)
        if info:
            res["info"][name] = info

    head = sh("git", "rev-parse", "HEAD")[1].decode().strip()
    res["candidate_commit"] = head
    check("worktree_clean", sh("git", "status", "--porcelain", "--untracked-files=no")[1].strip() == b"")
    sh("git", "fetch", "-q", "origin", "main")

    # 1. every fix is in the candidate
    missing = [c for c in REQUIRED_COMMITS if sh("git", "merge-base", "--is-ancestor", c, "HEAD")[0] != 0]
    check("all_fixes_are_ancestors", not missing, missing=missing, required=REQUIRED_COMMITS)

    # 2. fixed constants and rules (frozen values, read from the code)
    from m1macro import solver, indep, gate_verdict, freeze_record as FR, manifest, manifest_gate
    sv = {k: (tuple(getattr(solver, k)) if k == "CAND_SIZES" else getattr(solver, k)) for k in FROZEN_SOLVER}
    cfg = json.loads((ROOT / "m1macro/config/m1macro_config.json").read_text("utf-8"))
    cs = {k: (tuple(v) if isinstance(v, list) else v) for k, v in cfg["solver_constants"].items()}
    check("solver_constants_frozen", sv == FROZEN_SOLVER == cs, solver=str(sv))
    src = (ROOT / "m1macro/indep.py").read_text("utf-8")
    check("indep_refine_1e-14_fixed", indep.REFINE_TOL == 1e-14)
    check("indep_criteria_unchanged", all(x in src for x in ("pass_UB=bool(d_ub <= 2e-13)", "pass_beta=bool(d_beta <= 1e-6)",
                                                               "pass_mu=bool(dmu <= 1e-4)")))
    check("verdict_eps_tie_1e-13", gate_verdict.EPS_TIE == 1e-13)
    wf = (ROOT / ".github/workflows/m1macro_gates.yml").read_text("utf-8")
    nsh = re.search(r'N_SHARDS: "(\d+)"', wf).group(1)
    matrix = re.search(r"shard: \[([0-9, ]+)\]", wf.split("g678:")[1]).group(1)
    check("forty_shards_everywhere", gate_verdict.N_SHARDS == 40 == int(nsh)
          and [int(x) for x in matrix.split(",")] == list(range(40)))
    frs0 = (ROOT / "m1macro/freeze_record.py").read_text("utf-8")
    check("f11a_kind_from_topology", 'api["push"](commit, parent or ZERO_SHA, "push" if parent else "branch_creation")' in frs0
          and (ROOT / "m1macro/test_activity_kind.py").exists())
    check("server_reverify_window_14d", FR.SERVER_REVERIFY_WINDOW == dt.timedelta(days=14))
    check("activity_retry_fixed_12x15s", (FR.ACTIVITY_POLLS, FR.ACTIVITY_POLL_SEC) == (12, 15))
    st = {k: FR.freeze_state(*v) for k, v in {"none": (b"", b"", b""), "incomplete": (b"r", b"", b""),
          "rejected": (b"r", b"m", FR.header_bytes(FR.AUDIT_FIELDS) + FR.row_bytes(FR.AUDIT_FIELDS, {"Freeze_Status": "REJECTED"}))}.items()}
    with tempfile.TemporaryDirectory() as td:          # INCOMPLETE and REJECTED are terminal: transaction refuses
        class G:
            dir = Path(td)
        (Path(td) / FR.RECORD).parent.mkdir(parents=True); (Path(td) / FR.RECORD).write_bytes(b"{}")
        try:
            FR.transaction(G(), b"{}", {}, None, {}, None, None, None); refused = None
        except FR.FreezeRefused as e:
            refused = str(e)
    check("incomplete_and_rejected_terminal", st == {"none": "NONE", "incomplete": "INCOMPLETE", "rejected": "REJECTED"}
          and refused == "VERSION_INCOMPLETE_PRIOR_TRANSACTION", states=st, refused=refused)

    # 3. CODE_MANIFEST_V1 complete (D10 gate, independent path) and Code_SHA256
    with tempfile.TemporaryDirectory() as td:
        mp = Path(td, "m.txt"); mp.write_bytes(manifest.manifest_bytes())
        mg = json.loads(subprocess.run([sys.executable, "-I", "m1macro/manifest_gate.py", str(mp)], cwd=ROOT,
                                       capture_output=True).stdout or b"{}")
    listed = {l.rsplit(",", 1)[0] for l in manifest.manifest_bytes().decode().splitlines()[1:] if l.strip()}
    want = {p.relative_to(ROOT).as_posix() for p in list((ROOT / "m1macro").glob("*.py"))
            + list((ROOT / ".github/workflows").glob("m1macro_*.yml"))} | {"m1macro/config/m1macro_config.json"}
    check("manifest_gate_pass", mg.get("pass") is True, workflows=mg.get("workflows"))
    check("manifest_covers_code_config_workflows", want <= listed, missing=sorted(want - listed))
    res["code_sha256"] = manifest.code_sha256()
    res["n_manifest_entries"] = len(listed)

    # 4. config: concrete first origins, nothing pending, frozen spec hashes equal main's frozen documents
    from m1macro import freeze_gate as FG
    first = FG.first_origins(cfg)
    check("first_forward_origin_concrete", first is not None and cfg.get("pending") == [],
          first_forward_origin=cfg.get("first_forward_origin"))
    spec_ok = {}
    for k, v in cfg["frozen_specs"].items():
        rc, b = sh("git", "show", f"origin/main:preregistration/{k}.freeze.json")
        rc2, md = sh("git", "show", f"origin/main:preregistration/{k}.md")
        spec_ok[k] = rc == 0 and rc2 == 0 and json.loads(b).get("sha256") == v == hashlib.sha256(md).hexdigest()
    check("frozen_spec_hashes_match_main", all(spec_ok.values()) and spec_ok, specs=spec_ok)

    # 5. Pre-Freeze D2 gate (both bounds) against main: now, and the planned freeze window
    files = {rel: (sh("git", "show", f"origin/main:{rel}")[1] if sh("git", "cat-file", "-e", f"origin/main:{rel}")[0] == 0
                   else b"") for rel in (FG.FETCHES,) + FG.LEDGER_FILES}
    fo = FG._formal_origin_fn()
    now = dt.datetime.now(dt.timezone.utc).replace(microsecond=0)
    pre_now = FG.pre_freeze(cfg, [now], files, fo)
    lo = max(FG._utc(v) for v in pre_now.get("a_previous_utc", {}).values()) if pre_now.get("a_previous_utc") else None
    hi = min(FG._utc(v) for v in pre_now.get("a_first_utc", {}).values()) if pre_now.get("a_first_utc") else None
    res["freeze_window_utc"] = {"from_inclusive": FG._s(lo), "until_exclusive": FG._s(hi)} if lo and hi else None
    pre_lo = FG.pre_freeze(cfg, [lo], files, fo) if lo else {"pass": False}
    pre_hi = FG.pre_freeze(cfg, [hi - dt.timedelta(seconds=1)], files, fo) if hi else {"pass": False}
    check("pre_freeze_gate_passable_in_window", bool(lo and hi and lo < hi and pre_lo["pass"] and pre_hi["pass"]),
          now=pre_now, window_start=pre_lo.get("violations"), window_end=pre_hi.get("violations"))
    check("now_not_past_window", bool(hi and now < hi))
    if "--planned-freeze-utc" in args:
        pp = FG.pre_freeze(cfg, [FG._utc(args["--planned-freeze-utc"])], files, fo)
        check("pre_freeze_gate_at_planned_time", pp["pass"], violations=pp["violations"])

    # 6. one-shot snapshot fixed
    rc, mb = sh("git", "show", f"origin/main:{FR.SNAPSHOT_MANIFEST}")
    commits = sh("git", "log", "--format=%H", "origin/main", "--", "data/m1macro/dev_snapshot")[1].decode().split()
    trm = sh("git", "show", "origin/main:data/m1macro/treasury_raw_manifest.csv")[1].decode()
    check("snapshot_one_shot_on_main", rc == 0 and commits == [SNAPSHOT_MAIN_COMMIT] and PRIVATE_SNAPSHOT_COMMIT in trm,
          manifest_sha256=hashlib.sha256(mb).hexdigest() if rc == 0 else None, commits=commits)
    from m1macro import snapshot_acq
    check("snapshot_reacquire_guard", snapshot_acq.CANONICAL_MANIFEST == FR.SNAPSHOT_MANIFEST
          and "CANONICAL_SNAPSHOT_EXISTS" in (ROOT / "m1macro/snapshot_acq.py").read_text("utf-8"))

    # 7. no dev-only / debug path in the formal code and workflows
    env_reads = []
    for p in sorted((ROOT / "m1macro").glob("*.py")):
        if p.name.startswith("test_"):
            continue
        t = (p).read_text("utf-8")
        for m in re.finditer(r"environ(?:\.get)?\(?\[?\s*[\"']([A-Z0-9_]+)[\"']", t):
            if m.group(1) not in ALLOWED_ENV:
                env_reads.append(f"{p.name}:{m.group(1)}")
        if "__import__(\"os\")" in t or "getenv(" in t:
            env_reads.append(f"{p.name}:dynamic")
    check("no_debug_env_switches", not env_reads, found=env_reads)
    formal_wf = [p for p in (ROOT / ".github/workflows").glob("m1macro_*.yml") if p.name != "m1macro_dev.yml"]
    bad = [p.name for p in formal_wf if re.search(r"tools/|dev_indep|M1_GATE_LIMIT|STRESS_", p.read_text("utf-8"))]
    check("formal_workflows_no_dev_paths", not bad, found=bad)
    dev = (ROOT / ".github/workflows/m1macro_dev.yml").read_text("utf-8")
    check("dev_workflow_only_on_dev_branch", re.search(r"branches:\s*\[\s*m1macro-dev\s*\]", dev) is not None
          and "m1macro-gates-results" not in dev)
    check("formal_results_only_from_formal_branch",
          "github.ref_name == 'm1macro-gates' && 'm1macro-gates-results' || 'm1macro-devblind-results'" in wf
          and "github.ref_name == 'm1macro-gates' && 'FORMAL' || 'DEVELOPMENT_BLIND'" in wf)

    # 8. after the candidate nothing changes silently: the formal gates and the freeze bind this exact Code_SHA256
    frs = (ROOT / "m1macro/freeze_record.py").read_text("utf-8")
    check("code_sha_bound_in_gates_and_freeze", all(x in frs for x in ("GATE_RESULTS_NOT_FOR_CANDIDATE",
          "CODE_SHA_HOST_CONTAINER_MISMATCH", "CHECKOUT_NOT_CANDIDATE", "GATE_RUN_MISMATCH")))

    res["pass"] = all(res["checks"].values())
    out_path.write_text(json.dumps(res, indent=1, sort_keys=True, default=str) + "\n", encoding="utf-8")
    print(json.dumps({"pass": res["pass"], "failed": sorted(k for k, v in res["checks"].items() if not v),
                      "code_sha256": res["code_sha256"], "candidate_commit": head}))
    return 0 if res["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
