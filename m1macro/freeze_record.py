"""Implementation Freeze record transaction (Impl Part 4 §4; IMPL-FINDINGS-04 F1, むすび 2026-10-18: 案(b) + two stages).

  A  freeze record  preregistration/M1-MACRO-IMPL-CODE-V1.freeze.json        create -> push -> remote reread (byte-equal)
  B  COMPLETE marker preregistration/M1-MACRO-IMPL-CODE-V1.freeze_complete.csv  Recorded_At_UTC -> push -> reread (once)
  C  freeze audit   audit_log/m1_macro_freeze_audit.csv                       anchors + D2 -> FINAL / REJECTED -> push -> reread

T_freeze_recorded := Recorded_At_UTC of the COMPLETE marker (runner clock, taken only after A's remote reread succeeded).
Server anchors (GitHub, independent of the runner clock; F1-e, むすび 2026-10-18):
    Run_Started_At_Server_UTC  = run_started_at of this workflow attempt (Actions API)
    Marker_Push_At_Server_UTC  = timestamp of the ONE push to main whose `after` is the marker commit (activity API)
Anchor gate:   Run_Started_At_Server_UTC <= Recorded_At_UTC <= Marker_Push_At_Server_UTC
               (+ runner-internal order Record_Reread_At_UTC <= Recorded_At_UTC <= Marker_Reread_At_UTC)
D2 Freeze-finalization gate (formal boundary, server time):  Marker_Push_At_Server_UTC < A_first(h) for every h,
A_first(h) = T_info(first(h)) - window. The runner times are recorded but are not the D2 evidence.
No push event found within ACTIVITY_WAIT, more than one, or a commit mismatch -> REJECTED (fail closed).
The freeze is FINAL only when the audit row says FINAL on main; a failed push at C leaves it not final (fail closed).
One freeze per Version: any existing record / marker / audit file on main refuses the run before writing.

Host side, standard library only (git on the runner; no numerics). A_first is computed here independently of
freeze_gate.py (fixed +09:00, window from the config) and must equal the container's value.

usage: python3 -I m1macro/freeze_record.py run <container_out_dir> <main_worktree> <candidate_sha>
       python3 -I m1macro/freeze_record.py audit <repo_root>      (fresh audit of main: three files + server anchor)
"""
import csv
import datetime as dt
import hashlib
import io
import json
import os
import subprocess
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RECORD = "preregistration/M1-MACRO-IMPL-CODE-V1.freeze.json"
MARKER = "preregistration/M1-MACRO-IMPL-CODE-V1.freeze_complete.csv"
AUDIT = "audit_log/m1_macro_freeze_audit.csv"
MARKER_FIELDS = ["Run_ID", "Run_Attempt", "Record_Path", "Record_SHA256", "Record_Main_Commit", "Code_SHA256",
                 "Record_Reread_At_UTC", "Status", "Recorded_At_UTC"]
AUDIT_FIELDS = ["Run_ID", "Run_Attempt", "Code_SHA256", "Run_Started_At_Server_UTC", "Record_Reread_At_UTC",
                "Recorded_At_UTC", "Marker_Reread_At_UTC", "Marker_Commit", "Marker_Push_Activity_ID",
                "Marker_Push_At_Server_UTC", "Anchor_Status", "A_First_1D_UTC", "A_First_1W_UTC", "A_First_4W_UTC",
                "D2_Status", "Freeze_Status", "Reject_Reason"]
HORIZONS = ("1D", "1W", "4W")
JST = dt.timezone(dt.timedelta(hours=9))        # Asia/Tokyo has had no DST since 1951
UTC = dt.timezone.utc
PUSH_RETRIES = 5
ACTIVITY_POLLS = 12                  # fixed before the candidate (F1-e): 12 polls x 15 s = up to 180 s for the push
ACTIVITY_POLL_SEC = 15               # event to appear in the activity API; not a statistical parameter
ACTIVITY_MAX_PAGES = 100             # F8-a: every page of the activity list is read (100 x 100 events); more -> fail closed
ACTIONS_ACTOR = "github-actions[bot]"   # F8-a/F8-c: pushes made by a workflow with GITHUB_TOKEN
GATES_WORKFLOW = ".github/workflows/m1macro_gates.yml"
GATES_BRANCH = "m1macro-gates"
GATES_RESULTS_BRANCH = "m1macro-gates-results"
SNAPSHOT_MANIFEST = "data/m1macro/dev_snapshot/manifest.json"


class FreezeRefused(Exception):
    pass


def utc_s(t):
    return t.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_utc(s):
    return dt.datetime.strptime(s, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC)


def row_bytes(fields, row):
    buf = io.StringIO()
    csv.DictWriter(buf, fieldnames=fields, lineterminator="\n", extrasaction="raise").writerow(
        {k: str(row.get(k, "")) for k in fields})
    return buf.getvalue().encode("utf-8")


def header_bytes(fields):
    return (",".join(fields) + "\n").encode("utf-8")


def _rows(b):
    return list(csv.DictReader(io.StringIO(b.decode("utf-8")))) if b else []


def a_first(first: dict, window_hours: int) -> dict:
    """A_first(h) = T_info(first(h)) - window, T_info = 03:00 JST on the Origin day."""
    out = {}
    for h in HORIZONS:
        d = dt.date.fromisoformat(first[h])
        out[h] = dt.datetime(d.year, d.month, d.day, 3, 0, tzinfo=JST) - dt.timedelta(hours=window_hours)
    return out


class PushNotFound(Exception):
    pass


def anchor_ok(run_start, record_reread, recorded, marker_reread, marker_push) -> bool:
    """Server bounds around T_freeze_recorded, plus the runner-internal order."""
    return run_start <= recorded <= marker_push and record_reread <= recorded <= marker_reread


def d2_ok(marker_push, af: dict) -> bool:
    """Formal D2 boundary on the server push time of the COMPLETE marker."""
    return all(marker_push < af[h] for h in HORIZONS)


def find_push(events, commit, ref="refs/heads/main", parent=None, actor=None):
    """events: activity API records. Exactly one push to ref whose `after` is commit -> (id, time).
    F8-a: if parent is given, that push must have moved ref from parent (`before`); if actor is given, it must be the
    pusher. Any other outcome raises PushNotFound (fail closed)."""
    hits = [e for e in events if e.get("activity_type") == "push" and e.get("ref") == ref and e.get("after") == commit]
    if len(hits) != 1:
        raise PushNotFound("PUSH_EVENT_NOT_UNIQUE" if hits else "PUSH_EVENT_NOT_FOUND")
    e = hits[0]
    if parent is not None and e.get("before") != parent:
        raise PushNotFound("PUSH_EVENT_PARENT_MISMATCH")
    if actor is not None and (e.get("actor") or {}).get("login") != actor:
        raise PushNotFound("PUSH_EVENT_ACTOR_MISMATCH")
    return str(e["id"]), parse_utc(e["timestamp"])


def _next_link(resp):
    h = getattr(resp, "headers", None)
    link = h.get("Link") if h is not None else None
    for part in (link or "").split(","):
        if 'rel="next"' in part:
            return part[part.index("<") + 1:part.index(">")]
    return None


def _activity_all(repo, token, ref):
    """F8-a: every page of the push activity of ref (oldest pushes included); a missing page or more than
    ACTIVITY_MAX_PAGES pages raises (fail closed)."""
    from urllib.parse import quote
    url = f"https://api.github.com/repos/{repo}/activity?ref={quote(ref, safe='')}&activity_type=push&per_page=100"
    out = []
    for _ in range(ACTIVITY_MAX_PAGES):
        req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"})
        with urllib.request.urlopen(req, timeout=30) as r:
            page = json.loads(r.read()); url = _next_link(r)
        if not isinstance(page, list):
            raise ValueError("activity page")
        out += page
        if not url:
            return out
    raise PushNotFound("ACTIVITY_PAGES_EXCEEDED")


def activity_lookup(repo, token, sleep=None, ref="refs/heads/main", actor=ACTIONS_ACTOR):
    """Returns push_time(commit, parent=None) -> (activity_id, server time); polls the full activity list of ref with
    the fixed wait. A non-unique, parent-mismatched or actor-mismatched event is final at once (no retry)."""
    import time
    sleep = sleep or time.sleep

    def push_time(commit, parent=None):
        last = None
        for i in range(ACTIVITY_POLLS):
            try:
                return find_push(_activity_all(repo, token, ref), commit, ref, parent, actor)
            except PushNotFound as e:
                last = e
                if str(e) != "PUSH_EVENT_NOT_FOUND":
                    raise
            except Exception:
                last = PushNotFound("ACTIVITY_API_FAILED")
            if i < ACTIVITY_POLLS - 1:
                sleep(ACTIVITY_POLL_SEC)
        raise last
    return push_time


def record_bytes(rec: dict) -> bytes:
    return (json.dumps(rec, indent=1, sort_keys=True, ensure_ascii=False) + "\n").encode("utf-8")


def _push(git, code):
    for i in range(PUSH_RETRIES):
        try:
            git.push(); return
        except Exception:
            if i == PUSH_RETRIES - 1:
                raise FreezeRefused(code)


def transaction(git, rec_b: bytes, ids: dict, run_start, af: dict, now, head_commit, push_time, parent_of=None) -> dict:
    """git: RealGit-like adapter on a main worktree (create/append/ensure_header/push/remote). ids: Run_ID, Run_Attempt,
    Code_SHA256. now() -> aware datetime. head_commit() -> current main commit sha. push_time(commit, parent) ->
    (activity id, server time) or raises PushNotFound. parent_of(commit) -> its first parent (F8-a: the push event
    must have moved main from exactly that commit). Returns the audit row (dict)."""
    for p in (RECORD, MARKER, AUDIT):
        if (git.dir / p).exists():
            raise FreezeRefused("FREEZE_ALREADY_RECORDED")
    git.create(RECORD, rec_b)                                                              # A
    _push(git, "RECORD_PUSH_FAILED")
    try:
        if git.remote(RECORD) != rec_b:
            raise FreezeRefused("RECORD_REREAD_MISMATCH")
    except FreezeRefused:
        raise
    except Exception:
        raise FreezeRefused("RECORD_REREAD_FAILED")
    t_rec = now()
    recorded = now()                                                                       # B
    mrow = {**ids, "Record_Path": RECORD, "Record_SHA256": hashlib.sha256(rec_b).hexdigest(),
            "Record_Main_Commit": head_commit(), "Record_Reread_At_UTC": utc_s(t_rec), "Status": "COMPLETE",
            "Recorded_At_UTC": utc_s(recorded)}
    mb = row_bytes(MARKER_FIELDS, mrow)
    git.ensure_header(MARKER, header_bytes(MARKER_FIELDS)); git.append(MARKER, mb)
    _push(git, "MARKER_PUSH_FAILED")
    try:
        rm = git.remote(MARKER)
    except Exception:
        raise FreezeRefused("MARKER_REREAD_FAILED")
    if sum(1 for ln in rm.split(b"\n") if ln == mb.rstrip(b"\n")) != 1:
        raise FreezeRefused("MARKER_NOT_EXACTLY_ONCE")
    t_mark = now()
    mcommit = head_commit()                              # after B's push: main == the commit that carries the marker
    try:
        parent = parent_of(mcommit) if parent_of else None
    except Exception:
        parent = False
    if parent is False:
        act_id, t_push, reject = "", None, "MARKER_PARENT_UNKNOWN"
    else:
        try:
            act_id, t_push = push_time(mcommit, parent); reject = ""
        except PushNotFound as e:
            act_id, t_push, reject = "", None, str(e)
    # second-resolution strings are what is recorded; the gates compare exactly those values
    rs, tr, rc, tm = (parse_utc(utc_s(x)) for x in (run_start, t_rec, recorded, t_mark))
    if t_push is None:
        anc = d2 = False
    else:
        tp = parse_utc(utc_s(t_push)); anc = anchor_ok(rs, tr, rc, tm, tp); d2 = d2_ok(tp, af)       # C
        reject = "" if (anc and d2) else ("ANCHOR_ORDER" if not anc else "D2_NOT_BEFORE_A_FIRST")
    arow = {**ids, "Run_Started_At_Server_UTC": utc_s(rs), "Record_Reread_At_UTC": utc_s(tr), "Recorded_At_UTC": utc_s(rc),
            "Marker_Reread_At_UTC": utc_s(tm), "Marker_Commit": mcommit, "Marker_Push_Activity_ID": act_id,
            "Marker_Push_At_Server_UTC": utc_s(t_push) if t_push else "", "Anchor_Status": "PASS" if anc else "FAIL",
            **{f"A_First_{h}_UTC": utc_s(af[h]) for h in HORIZONS}, "D2_Status": "PASS" if d2 else "FAIL",
            "Freeze_Status": "FINAL" if (anc and d2) else "REJECTED", "Reject_Reason": reject}
    ab = row_bytes(AUDIT_FIELDS, arow)
    git.ensure_header(AUDIT, header_bytes(AUDIT_FIELDS)); git.append(AUDIT, ab)
    _push(git, "AUDIT_PUSH_FAILED")
    try:
        if sum(1 for ln in git.remote(AUDIT).split(b"\n") if ln == ab.rstrip(b"\n")) != 1:
            raise FreezeRefused("AUDIT_NOT_EXACTLY_ONCE")
    except FreezeRefused:
        raise
    except Exception:
        raise FreezeRefused("AUDIT_REREAD_FAILED")
    return arow


def is_final(rec_b: bytes, marker_b: bytes, audit_b: bytes, code_sha: str, first=None) -> bool:
    """The implementation freeze holds for code_sha: record, exactly one COMPLETE marker bound to the record's bytes,
    exactly one audit row for that run with FINAL (anchors PASS, D2 PASS) and consistent times. first: optional
    {h: date iso} to cross-check against the record."""
    if not rec_b:
        return False
    try:
        rec = json.loads(rec_b)
    except ValueError:
        return False
    if rec.get("Code_SHA256") != code_sha:
        return False
    if first is not None and rec.get("First_Forward_Origin") != first:
        return False
    mk = [r for r in _rows(marker_b) if r.get("Status") == "COMPLETE"]
    if len(_rows(marker_b)) != 1 or len(mk) != 1:
        return False
    m = mk[0]
    if m["Record_SHA256"] != hashlib.sha256(rec_b).hexdigest() or m["Code_SHA256"] != code_sha or m["Record_Path"] != RECORD:
        return False
    au = _rows(audit_b)
    if len(au) != 1:
        return False
    a = au[0]
    if (a["Run_ID"], a["Run_Attempt"], a["Code_SHA256"], a["Recorded_At_UTC"], a["Record_Reread_At_UTC"]) != \
            (m["Run_ID"], m["Run_Attempt"], code_sha, m["Recorded_At_UTC"], m["Record_Reread_At_UTC"]):
        return False
    if not a.get("Marker_Commit") or not a.get("Marker_Push_Activity_ID") or a.get("Reject_Reason"):
        return False
    try:
        times = [parse_utc(a[k]) for k in ("Run_Started_At_Server_UTC", "Record_Reread_At_UTC", "Recorded_At_UTC",
                                           "Marker_Reread_At_UTC", "Marker_Push_At_Server_UTC")]
        af = {h: parse_utc(a[f"A_First_{h}_UTC"]) for h in HORIZONS}
        exp = a_first(rec["First_Forward_Origin"], rec["CFTC_Snapshot_Window_Hours"])
    except (KeyError, ValueError, TypeError):
        return False
    if any(af[h] != exp[h] for h in HORIZONS):
        return False
    return (a["Anchor_Status"] == "PASS" and a["D2_Status"] == "PASS" and a["Freeze_Status"] == "FINAL"
            and anchor_ok(*times) and d2_ok(times[4], af))


def is_final_tree(root, code_sha, first=None) -> bool:
    rd = lambda p: (Path(root) / p).read_bytes() if (Path(root) / p).exists() else b""
    return is_final(rd(RECORD), rd(MARKER), rd(AUDIT), code_sha, first)


# ------------------------------------------------------------------ workflow entry (runner host)
def _sh(*a, cwd=None):
    r = subprocess.run(list(a), cwd=cwd, capture_output=True)
    if r.returncode != 0:
        raise FreezeRefused("GIT_FAILED")
    return r.stdout


def server_run_start(repo, run_id, attempt, token, head_sha):
    """run_started_at of this attempt from the GitHub API (server time); head_sha must be the candidate."""
    req = urllib.request.Request(f"https://api.github.com/repos/{repo}/actions/runs/{run_id}/attempts/{attempt}",
                                 headers={"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        j = json.loads(r.read())
    if j.get("head_sha") != head_sha or str(j.get("run_attempt")) != str(attempt) or str(j.get("id")) != str(run_id):
        raise FreezeRefused("RUN_ANCHOR_MISMATCH")
    return parse_utc(j["run_started_at"])


def gates_run(repo, token, run_id, attempt):
    req = urllib.request.Request(f"https://api.github.com/repos/{repo}/actions/runs/{run_id}/attempts/{attempt}",
                                 headers={"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())


def gate_results(cand_root, code_sha, cand_sha, snapshot_sha=None, api=None):
    """Formal gate results for this Code_SHA256 on branch m1macro-gates-results.
    F1-d: FORMAL run class, this Code_SHA256 and candidate commit, and an all-PASS G1-G9 verdict equal to the one
    recomputed here. F8-c: provenance - the results commit was pushed by a workflow (unique push event, actor
    github-actions[bot]) and names a completed, successful m1macro_gates.yml run attempt on branch m1macro-gates for
    the candidate commit. F8-d: G5 ran on the development snapshot whose manifest SHA-256 is snapshot_sha.
    api: {"run": f(run_id, attempt) -> run json, "push": f(commit) -> (id, time)}; None -> GitHub API from the env."""
    _sh("git", "fetch", "-q", "origin", "m1macro-gates-results", cwd=cand_root)
    commit = _sh("git", "rev-parse", "FETCH_HEAD", cwd=cand_root).decode().strip()
    names = _sh("git", "ls-tree", "--name-only", f"FETCH_HEAD:{code_sha}", cwd=cand_root).decode().split()
    show = lambda n: _sh("git", "show", f"FETCH_HEAD:{code_sha}/{n}", cwd=cand_root)
    if show("code_sha256.txt").decode().strip() != code_sha or show("source_commit.txt").decode().strip() != cand_sha:
        raise FreezeRefused("GATE_RESULTS_NOT_FOR_CANDIDATE")
    if "run_class.txt" not in names or show("run_class.txt").decode().strip() != "FORMAL":
        raise FreezeRefused("GATE_RESULTS_NOT_FORMAL")              # development blind results never qualify
    suite = json.loads(show("suite.json"))
    if not suite or any(v.get("status") != "PASS" for v in suite.values()):
        raise FreezeRefused("GATE_SUITE_NOT_PASS")
    if not json.loads(show("manifest_gate.json")).get("pass"):
        raise FreezeRefused("GATE_MANIFEST_NOT_PASS")
    # F1-d: every formal gate G1-G9 must PASS by the machine-readable verdict, recomputed here from the result files
    if "gates_verdict.json" not in names:
        raise FreezeRefused("GATE_VERDICT_MISSING")
    import tempfile
    from m1macro import gate_verdict
    with tempfile.TemporaryDirectory() as td:
        for n in ("suite.json", "g5_summary.json", "g678_summary.json", "exits.txt"):
            if n in names:
                Path(td, n).write_bytes(show(n))
        recomputed = gate_verdict.verdict(td)
    stored = json.loads(show("gates_verdict.json"))
    if stored != recomputed:
        raise FreezeRefused("GATE_VERDICT_INCONSISTENT")
    if not recomputed.get("all_pass"):
        raise FreezeRefused("GATE_VERDICT_NOT_ALL_PASS")
    # F8-d: the formal gates read the development snapshot the record names
    g5s = json.loads(show("g5_summary.json"))
    if snapshot_sha is None or g5s.get("snapshot_manifest_sha256") != snapshot_sha:
        raise FreezeRefused("GATE_SNAPSHOT_MISMATCH")
    # F8-c: provenance of the results
    if "run_provenance.json" not in names:
        raise FreezeRefused("GATE_PROVENANCE_MISSING")
    try:
        pv = json.loads(show("run_provenance.json"))
        rid, att = str(int(pv["run_id"])), str(int(pv["run_attempt"]))
    except (ValueError, KeyError, TypeError):
        raise FreezeRefused("GATE_PROVENANCE_MISSING")
    if pv.get("sha") != cand_sha or pv.get("ref_name") != GATES_BRANCH:
        raise FreezeRefused("GATE_RUN_MISMATCH")
    if api is None:
        repo, tok = os.environ["GITHUB_REPOSITORY"], os.environ["GITHUB_TOKEN"]
        api = {"run": lambda i, a: gates_run(repo, tok, i, a),
               "push": activity_lookup(repo, tok, ref=f"refs/heads/{GATES_RESULTS_BRANCH}")}
    try:
        j = api["run"](rid, att)
    except Exception:
        raise FreezeRefused("GATE_RUN_LOOKUP_FAILED")
    if (str(j.get("id")) != rid or str(j.get("run_attempt")) != att or j.get("path") != GATES_WORKFLOW
            or j.get("head_branch") != GATES_BRANCH or j.get("head_sha") != cand_sha or j.get("event") != "push"
            or j.get("status") != "completed" or j.get("conclusion") != "success"):
        raise FreezeRefused("GATE_RUN_MISMATCH")
    try:
        parent = _sh("git", "rev-parse", "FETCH_HEAD^", cwd=cand_root).decode().strip() \
            if _sh("git", "rev-list", "--count", "FETCH_HEAD", cwd=cand_root).decode().strip() != "1" else None
        api["push"](commit, parent)
    except PushNotFound as e:
        raise FreezeRefused("GATE_RESULTS_" + str(e))
    except FreezeRefused:
        raise FreezeRefused("GATE_RESULTS_PARENT_UNKNOWN")
    return {"Results_Branch": GATES_RESULTS_BRANCH, "Results_Commit": commit, "Results_Dir": code_sha,
            "Gates_Run": {"Run_ID": rid, "Run_Attempt": att},
            "Files_SHA256": {n: hashlib.sha256(show(n)).hexdigest() for n in sorted(names)}}


def run(cout, main_wt, cand_sha):
    from m1macro import gitrepo, manifest
    cout = Path(cout)
    cfg = json.loads((ROOT / "m1macro" / "config" / "m1macro_config.json").read_text("utf-8"))
    code_sha = manifest.code_sha256()
    if (cout / "code_sha256.txt").read_text().strip() != code_sha:
        raise FreezeRefused("CODE_SHA_HOST_CONTAINER_MISMATCH")
    if manifest.manifest_bytes() != (cout / "code_manifest.txt").read_bytes():
        raise FreezeRefused("MANIFEST_HOST_CONTAINER_MISMATCH")
    mg = json.loads((cout / "manifest_gate.json").read_text()); pre = json.loads((cout / "freeze_gate_pre.json").read_text())
    if not mg.get("pass"):
        raise FreezeRefused("MANIFEST_GATE_FAIL")
    if not pre.get("pass") or not pre.get("main_dir_given"):
        raise FreezeRefused("PRE_FREEZE_GATE_FAIL")
    first = cfg.get("first_forward_origin"); win = int(cfg["cftc_snapshot_window_hours"])
    af = a_first(first, win)
    if {h: utc_s(af[h]) for h in HORIZONS} != pre["a_first_utc"]:
        raise FreezeRefused("A_FIRST_HOST_CONTAINER_MISMATCH")
    if _sh("git", "rev-parse", "HEAD", cwd=ROOT).decode().strip() != cand_sha:
        raise FreezeRefused("CHECKOUT_NOT_CANDIDATE")
    rid, att = os.environ["GITHUB_RUN_ID"], os.environ.get("GITHUB_RUN_ATTEMPT", "1")
    run_start = server_run_start(os.environ["GITHUB_REPOSITORY"], rid, att, os.environ["GITHUB_TOKEN"], cand_sha)
    now = lambda: dt.datetime.now(UTC)
    if not now() < min(af.values()):
        raise FreezeRefused("PAST_A_FIRST")
    snap_b = _sh("git", "show", f"origin/main:{SNAPSHOT_MANIFEST}", cwd=main_wt); snap = json.loads(snap_b)
    rec = {"Spec": "M1-MACRO-IMPL-CODE-V1", "Code_SHA256": code_sha, "Candidate_Commit": cand_sha,
           "CODE_MANIFEST_V1": manifest.manifest_bytes().decode("utf-8"),
           "Image_Digest": (ROOT / "env/IMAGE_DIGEST").read_text().strip(),
           "Requirements_Lock_SHA256": hashlib.sha256((ROOT / "env/requirements.lock").read_bytes()).hexdigest(),
           "Dev_Snapshot": {"Main_Commit": _sh("git", "log", "-1", "--format=%H", "origin/main", "--",
                                              "data/m1macro/dev_snapshot", cwd=main_wt).decode().strip(),
                            "Manifest_SHA256": hashlib.sha256(snap_b).hexdigest(),
                            "Files": {f["source"] + ":" + f["path"]: f["sha256"] for f in snap["files"]}},
           "First_Forward_Origin": first, "CFTC_Snapshot_Window_Hours": win,
           "Gate_Results": gate_results(str(ROOT), code_sha, cand_sha, hashlib.sha256(snap_b).hexdigest()),
           "Run": {"Run_ID": rid, "Run_Attempt": att, "Workflow": os.environ.get("GITHUB_WORKFLOW", "")}}
    git = gitrepo.RealGit(main_wt, message=f"preregistration: M1-MACRO implementation freeze (run {rid})")
    head = lambda: _sh("git", "rev-parse", "HEAD", cwd=main_wt).decode().strip()
    parent_of = lambda c: _sh("git", "rev-parse", f"{c}^", cwd=main_wt).decode().strip()
    arow = transaction(git, record_bytes(rec), {"Run_ID": rid, "Run_Attempt": att, "Code_SHA256": code_sha},
                       run_start, af, now, head, activity_lookup(os.environ["GITHUB_REPOSITORY"], os.environ["GITHUB_TOKEN"]),
                       parent_of)
    print(json.dumps({k: arow[k] for k in ("Anchor_Status", "D2_Status", "Freeze_Status", "Reject_Reason")}))
    return arow["Freeze_Status"] == "FINAL"


def git_binding(root, rec_b, marker_b, audit_row, marker_row) -> bool:
    """F8-b: the audit row's Marker_Commit is a commit of this checkout's history (ancestor of HEAD) that carries
    exactly the current record and marker bytes, and its parent does not yet carry the marker; the marker's
    Record_Main_Commit carries the record bytes. Read-only git."""
    def g(*a):
        r = subprocess.run(["git", *a], cwd=root, capture_output=True)
        return r.returncode, r.stdout
    mc, rc = audit_row.get("Marker_Commit", ""), marker_row.get("Record_Main_Commit", "")
    if len(mc) != 40 or len(rc) != 40:
        return False
    if g("merge-base", "--is-ancestor", mc, "HEAD")[0] != 0 or g("merge-base", "--is-ancestor", rc, mc)[0] != 0:
        return False
    if g("show", f"{mc}:{MARKER}") != (0, marker_b) or g("show", f"{mc}:{RECORD}") != (0, rec_b) \
            or g("show", f"{rc}:{RECORD}") != (0, rec_b):
        return False
    return g("cat-file", "-e", f"{mc}^:{MARKER}")[0] != 0


def fresh_audit(root, repo, token, push_time=None) -> dict:
    """Fresh audit of a freeze on a main checkout (git clone): the canonical three files (is_final), their binding to
    the git history (F8-b), AND the server anchor re-queried now over the full activity list (F8-a): the push whose
    `after` is Marker_Commit, `before` its parent and actor github-actions[bot] must have the recorded id and time.
    Read-only."""
    sys.path.insert(0, str(ROOT))
    from m1macro import manifest
    rd = lambda p: (Path(root) / p).read_bytes() if (Path(root) / p).exists() else b""
    res = {"three_files_final": False, "git_binding": False, "server_anchor_matches": False, "pass": False}
    rec_b = rd(RECORD)
    if not rec_b:
        res["reason"] = "NO_FREEZE_RECORD"; return res
    try:
        code = json.loads(rec_b).get("Code_SHA256")
    except ValueError:
        res["reason"] = "RECORD_NOT_JSON"; return res
    res["code_sha256_record"] = code; res["code_sha256_checkout"] = manifest.code_sha256()
    res["three_files_final"] = is_final(rec_b, rd(MARKER), rd(AUDIT), code)
    a = (_rows(rd(AUDIT)) or [{}])[0]; m = (_rows(rd(MARKER)) or [{}])[0]
    res["git_binding"] = git_binding(root, rec_b, rd(MARKER), a, m)
    pr = subprocess.run(["git", "rev-parse", a.get("Marker_Commit", "") + "^"], cwd=root, capture_output=True)
    parent = pr.stdout.decode().strip() if pr.returncode == 0 else None
    if parent is None:
        res["reason"] = "MARKER_PARENT_UNKNOWN"
    else:
        try:
            aid, t = (push_time or activity_lookup(repo, token))(a.get("Marker_Commit", ""), parent)
            res["server_anchor_matches"] = (aid == a.get("Marker_Push_Activity_ID")
                                            and utc_s(t) == a.get("Marker_Push_At_Server_UTC"))
        except PushNotFound as e:
            res["reason"] = str(e)
    res["pass"] = res["three_files_final"] and res["git_binding"] and res["server_anchor_matches"]
    return res


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "audit":
        r = fresh_audit(sys.argv[2], os.environ["GITHUB_REPOSITORY"], os.environ["GITHUB_TOKEN"])
        print(json.dumps(r, sort_keys=True)); raise SystemExit(0 if r.get("pass") else 1)
    if len(sys.argv) != 5 or sys.argv[1] != "run":
        raise SystemExit(__doc__)
    sys.path.insert(0, str(ROOT))
    try:
        ok = run(sys.argv[2], sys.argv[3], sys.argv[4])
    except FreezeRefused as e:
        print(json.dumps({"freeze": "REFUSED", "reason": str(e)})); raise SystemExit(1)
    raise SystemExit(0 if ok else 1)
