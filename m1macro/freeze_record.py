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
No push event found within the fixed retry window (12 x 15 s, one transaction), more than one, a parent / pusher
mismatch, or a commit mismatch -> REJECTED (fail closed).
The freeze is FINAL only when the audit row says FINAL on main; a failed push at C leaves it not final (fail closed).
One freeze transaction per Version (F8-e, むすび 2026-10-19): a REJECTED audit row consumes the Version for good
(retry = a new Version); any existing record / marker / audit file refuses the run before writing; the three files
are write-once (the fresh audit fails if any of them is touched by a second commit).
Fresh audit (F8-a/b/f): three files, git binding, write-once, auditor code = candidate, server marker anchor and the
gate evidence chain. Server records must be re-fetched and equal for 14 days after the marker push
(SERVER_REVERIFY_WINDOW); afterwards an unavailable record is tolerated, a disagreeing one never.

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
SERVER_REVERIFY_WINDOW = dt.timedelta(days=14)   # むすび 2026-10-19: server records must be re-fetched up to 14 days
                                                 # after the marker push (activity retention: 30 days); later -> long-term


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


ZERO_SHA = "0" * 40


def find_push(events, commit, ref="refs/heads/main", parent=None, actor=None, kind="push"):
    """events: activity API records. Exactly one event of `kind` on ref whose `after` is commit -> (id, time).
    kind: "push" (an existing branch moved) or "branch_creation" (F11-a: the FIRST push of a branch is recorded by
    GitHub as branch_creation, before = 40 zeros, never as push). F8-a: if parent is given, the event must have moved
    ref from parent (`before`); if actor is given, it must be the pusher. Any other outcome raises PushNotFound."""
    if kind not in ("push", "branch_creation"):
        raise PushNotFound("PUSH_EVENT_KIND_INVALID")
    hits = [e for e in events if e.get("activity_type") == kind and e.get("ref") == ref and e.get("after") == commit]
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


def _activity_all(repo, token, ref, kind="push"):
    """F8-a: every page of the push activity of ref (oldest pushes included); a missing page or more than
    ACTIVITY_MAX_PAGES pages raises (fail closed)."""
    from urllib.parse import quote
    url = (f"https://api.github.com/repos/{repo}/activity?ref={quote(ref, safe='')}&activity_type={quote(kind)}"
           f"&per_page=100")
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

    def push_time(commit, parent=None, kind="push"):
        last = None
        for i in range(ACTIVITY_POLLS):
            try:
                return find_push(_activity_all(repo, token, ref, kind), commit, ref, parent, actor, kind)
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
    rd = lambda p: (git.dir / p).read_bytes() if (git.dir / p).exists() else b""
    st = freeze_state(rd(RECORD), rd(MARKER), rd(AUDIT))
    if st != "NONE":                       # F8-e: one freeze transaction per Version; REJECTED is final (consumed)
        raise FreezeRefused({"FINAL": "FREEZE_ALREADY_FINAL", "REJECTED": "VERSION_CONSUMED_REJECTED"}.get(
            st, "VERSION_INCOMPLETE_PRIOR_TRANSACTION"))
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


def freeze_state(rec_b: bytes, marker_b: bytes, audit_b: bytes) -> str:
    """F8-e (むすび 2026-10-19): NONE (no file) | REJECTED (an audit row says REJECTED: the Version is consumed and can
    never become FINAL) | FINAL (one audit row, FINAL) | INCOMPLETE (anything else: a prior transaction stopped
    before its audit row, or the files are inconsistent). Only NONE admits a freeze transaction."""
    if not (rec_b or marker_b or audit_b):
        return "NONE"
    rows = _rows(audit_b) if audit_b else []
    if any(r.get("Freeze_Status") == "REJECTED" for r in rows):
        return "REJECTED"
    if len(rows) == 1 and rows[0].get("Freeze_Status") == "FINAL":
        return "FINAL"
    return "INCOMPLETE"


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
        pre = rec["Pre_Freeze_Gate"]
        ap = {h: parse_utc(pre["a_previous_utc"][h]) for h in HORIZONS}
    except (KeyError, ValueError, TypeError):
        return False
    if any(af[h] != exp[h] for h in HORIZONS):
        return False
    # F10-a (Part 3 §2): first(h) is the first Origin after the freeze -> marker push >= A_first(prev(h)) for every h
    if pre.get("pass") is not True or pre.get("a_first_utc") != {h: utc_s(af[h]) for h in HORIZONS} \
            or pre.get("first_forward_origin") != rec["First_Forward_Origin"] or not all(ap[h] <= times[4] for h in HORIZONS):
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


def gate_results(cand_root, code_sha, cand_sha, snapshot_sha=None, api=None, results_commit=None, server_required=True):
    """Formal gate results for this Code_SHA256 on branch m1macro-gates-results.
    F1-d: FORMAL run class, this Code_SHA256 and candidate commit, and an all-PASS G1-G9 verdict equal to the one
    recomputed here from the raw result files. F8-c: provenance - run_provenance.json names a completed, successful
    m1macro_gates.yml run attempt on branch m1macro-gates for the candidate commit (Actions API: the binding), and the
    results commit was pushed in one unique push event (activity API; actor github-actions[bot] is an auxiliary check).
    F8-d: G5 and every G6-G8 shard ran on the development snapshot whose manifest SHA-256 is snapshot_sha.
    results_commit: None -> the branch tip (freeze); a sha -> that commit, which must be on the branch (F8-f fresh
    audit). server_required=False (F8-f long-term audit mode only): an UNAVAILABLE server record is tolerated, but a
    server record that disagrees always refuses.
    api: {"run": f(run_id, attempt) -> run json, "push": f(commit, parent) -> (id, time)}; None -> GitHub API (env)."""
    _sh("git", "fetch", "-q", "origin", GATES_RESULTS_BRANCH, cwd=cand_root)
    tip = _sh("git", "rev-parse", "FETCH_HEAD", cwd=cand_root).decode().strip()
    commit = results_commit or tip
    if results_commit is not None:
        r = subprocess.run(["git", "merge-base", "--is-ancestor", commit, tip], cwd=cand_root, capture_output=True)
        if len(commit) != 40 or r.returncode != 0:
            raise FreezeRefused("GATE_RESULTS_COMMIT_NOT_ON_BRANCH")
    names = _sh("git", "ls-tree", "--name-only", f"{commit}:{code_sha}", cwd=cand_root).decode().split()
    show = lambda n: _sh("git", "show", f"{commit}:{code_sha}/{n}", cwd=cand_root)
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
    server = {}
    try:
        j = api["run"](rid, att)
    except Exception:
        j = None
        if server_required:
            raise FreezeRefused("GATE_RUN_LOOKUP_FAILED")
    if j is None:
        server["run"] = "UNAVAILABLE"
    elif (str(j.get("id")) != rid or str(j.get("run_attempt")) != att or j.get("path") != GATES_WORKFLOW
            or j.get("head_branch") != GATES_BRANCH or j.get("head_sha") != cand_sha or j.get("event") != "push"
            or j.get("status") != "completed" or j.get("conclusion") != "success"):
        raise FreezeRefused("GATE_RUN_MISMATCH")                    # a disagreeing server record refuses in every mode
    else:
        server["run"] = "VERIFIED"
    try:
        parent = _sh("git", "rev-parse", f"{commit}^", cwd=cand_root).decode().strip() \
            if _sh("git", "rev-list", "--count", commit, cwd=cand_root).decode().strip() != "1" else None
    except FreezeRefused:
        raise FreezeRefused("GATE_RESULTS_PARENT_UNKNOWN")
    push = None
    try:
        # F11-a: the first results commit of the branch is a branch_creation event (before = zeros), later ones pushes
        aid, t = api["push"](commit, parent or ZERO_SHA, "push" if parent else "branch_creation")
        push = {"Activity_ID": aid, "At_Server_UTC": utc_s(t)}; server["push"] = "VERIFIED"
    except PushNotFound as e:
        if server_required or str(e) not in ("PUSH_EVENT_NOT_FOUND", "ACTIVITY_API_FAILED"):
            raise FreezeRefused("GATE_RESULTS_" + str(e))
        server["push"] = "UNAVAILABLE"
    return {"Results_Branch": GATES_RESULTS_BRANCH, "Results_Commit": commit, "Results_Dir": code_sha,
            "Gates_Run": {"Run_ID": rid, "Run_Attempt": att}, "Results_Push": push, "Server_Evidence": server,
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
           "Pre_Freeze_Gate": {k: pre[k] for k in ("pass", "first_forward_origin", "a_first_utc", "previous_origin",
                                                   "a_previous_utc", "check_times_utc")},
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


def _git(root, *a):
    r = subprocess.run(["git", *a], cwd=root, capture_output=True)
    return r.returncode, r.stdout


def git_binding(root, rec_b, marker_b, audit_row, marker_row) -> bool:
    """F8-b: the audit row's Marker_Commit is a commit of this checkout's history (ancestor of HEAD) that carries
    exactly the current record and marker bytes, and its parent does not yet carry the marker; the marker's
    Record_Main_Commit carries the record bytes and precedes Marker_Commit. Read-only git."""
    g = lambda *a: _git(root, *a)
    mc, rc = audit_row.get("Marker_Commit", ""), marker_row.get("Record_Main_Commit", "")
    if len(mc) != 40 or len(rc) != 40:
        return False
    if g("merge-base", "--is-ancestor", mc, "HEAD")[0] != 0 or g("merge-base", "--is-ancestor", rc, mc)[0] != 0:
        return False
    if g("show", f"{mc}:{MARKER}") != (0, marker_b) or g("show", f"{mc}:{RECORD}") != (0, rec_b) \
            or g("show", f"{rc}:{RECORD}") != (0, rec_b):
        return False
    return g("cat-file", "-e", f"{mc}^:{MARKER}")[0] != 0


def write_once(root, audit_row, marker_row) -> bool:
    """F8-e: record, marker and audit file are each written by exactly ONE commit of HEAD's history and never touched
    again; those commits are Record_Main_Commit, Marker_Commit and a descendant of Marker_Commit. A REJECTED row can
    therefore never be turned into FINAL (nor a second row added) without failing the fresh audit."""
    commits = {}
    for p in (RECORD, MARKER, AUDIT):
        rc, out = _git(root, "log", "--format=%H", "HEAD", "--", p)
        cs = out.decode().split()
        if rc != 0 or len(cs) != 1:
            return False
        commits[p] = cs[0]
    if commits[RECORD] != marker_row.get("Record_Main_Commit") or commits[MARKER] != audit_row.get("Marker_Commit"):
        return False
    return _git(root, "merge-base", "--is-ancestor", commits[MARKER], commits[AUDIT])[0] == 0 \
        and commits[MARKER] != commits[AUDIT]


def server_now(repo, token):
    """GitHub server time (HTTP Date header of an API response)."""
    from email.utils import parsedate_to_datetime
    req = urllib.request.Request(f"https://api.github.com/repos/{repo}",
                                 headers={"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return parsedate_to_datetime(r.headers["Date"]).astimezone(UTC)


def audit_mode(now, t_push) -> str:
    """WINDOW while now <= marker push + SERVER_REVERIFY_WINDOW (14 days, inclusive), and whenever either time is
    unknown (fail closed: the strict mode). LONG_TERM afterwards."""
    if now is None or t_push is None:
        return "WINDOW"
    return "WINDOW" if now <= t_push + SERVER_REVERIFY_WINDOW else "LONG_TERM"


def fresh_audit(root, repo, token, push_time=None, api=None, now=None, auditor_code_sha=None) -> dict:
    """Fresh audit of a freeze on a main checkout (git clone with origin). Re-verifies the evidence chain; nothing
    is re-estimated. PASS requires all of:
      three_files_final  record + one COMPLETE marker + one FINAL audit row (is_final)
      git_binding        F8-b   files bound to the git history
      write_once         F8-e   each file written by exactly one commit, never edited (REJECTED stays REJECTED)
      auditor_code       the auditing code is the frozen candidate (Code_SHA256 equal), so the verdict recomputation
                         below is the candidate's own gate_verdict
      server_anchor      F8-a   marker push re-queried over the full activity list (after = Marker_Commit,
                                before = its parent, github-actions[bot]): id and time equal to the audit row
      gate_evidence      F8-f   the record's Gate_Results re-verified at Results_Commit: provenance (Actions run),
                                candidate commit / Code_SHA256, FORMAL, snapshot binding, raw files -> recomputed
                                verdict equal to the stored one and all PASS, files SHA-256 equal to the record
    Mode (むすび 2026-10-19): WINDOW (<= 14 days after the marker push by GitHub server time, or server time unknown):
    every server record must be re-fetched and equal. LONG_TERM: a server record that is no longer available is
    tolerated (evidence = the stored audit row + git binding); a server record that disagrees always fails.
    now: datetime, callable or None (-> GitHub server time)."""
    sys.path.insert(0, str(ROOT))
    from m1macro import manifest
    rd = lambda p: (Path(root) / p).read_bytes() if (Path(root) / p).exists() else b""
    res = {"mode": None, "three_files_final": False, "git_binding": False, "write_once": False, "auditor_code": False,
           "server_anchor": "NOT_CHECKED", "gate_evidence": False, "pass": False}
    rec_b = rd(RECORD)
    if not rec_b:
        res["reason"] = "NO_FREEZE_RECORD"; return res
    try:
        rec = json.loads(rec_b)
    except ValueError:
        res["reason"] = "RECORD_NOT_JSON"; return res
    code = rec.get("Code_SHA256")
    aud = auditor_code_sha if auditor_code_sha is not None else manifest.code_sha256()
    res["code_sha256_record"] = code; res["code_sha256_auditor"] = aud; res["auditor_code"] = (aud == code)
    res["three_files_final"] = is_final(rec_b, rd(MARKER), rd(AUDIT), code)
    a = (_rows(rd(AUDIT)) or [{}])[0]; m = (_rows(rd(MARKER)) or [{}])[0]
    res["git_binding"] = git_binding(root, rec_b, rd(MARKER), a, m)
    res["write_once"] = write_once(root, a, m)
    try:
        t_push = parse_utc(a.get("Marker_Push_At_Server_UTC", ""))
    except ValueError:
        t_push = None
    try:
        t_now = now() if callable(now) else (now if now is not None else server_now(repo, token))
    except Exception:
        t_now = None
    res["mode"] = mode = audit_mode(t_now, t_push)
    strict = mode == "WINDOW"
    # F8-a server anchor
    pr = _git(root, "rev-parse", a.get("Marker_Commit", "") + "^")
    parent = pr[1].decode().strip() if pr[0] == 0 else None
    if parent is None:
        res["server_anchor"] = "FAILED"; res["reason"] = "MARKER_PARENT_UNKNOWN"
    else:
        try:
            aid, t = (push_time or activity_lookup(repo, token))(a.get("Marker_Commit", ""), parent)
            ok = aid == a.get("Marker_Push_Activity_ID") and utc_s(t) == a.get("Marker_Push_At_Server_UTC")
            res["server_anchor"] = "VERIFIED" if ok else "MISMATCH"
        except PushNotFound as e:
            unavailable = str(e) in ("PUSH_EVENT_NOT_FOUND", "ACTIVITY_API_FAILED")
            res["server_anchor"] = "UNAVAILABLE" if unavailable else "FAILED"; res["reason"] = str(e)
    anchor_ok_ = res["server_anchor"] == "VERIFIED" or (not strict and res["server_anchor"] == "UNAVAILABLE")
    # F8-f gate evidence chain
    try:
        gr = rec["Gate_Results"]; snap = rec["Dev_Snapshot"]["Manifest_SHA256"]
        got = gate_results(str(root), code, rec["Candidate_Commit"], snap, api, results_commit=gr["Results_Commit"],
                           server_required=strict)
        same = all(got[k] == gr.get(k) for k in ("Results_Branch", "Results_Commit", "Results_Dir", "Gates_Run",
                                                  "Files_SHA256"))
        if got["Results_Push"] is not None and got["Results_Push"] != gr.get("Results_Push"):
            same = False
        if strict and got["Results_Push"] is None:
            same = False
        res["gate_evidence"] = same
        res["gate_server_evidence"] = got["Server_Evidence"]
        if not same:
            res["gate_reason"] = "GATE_EVIDENCE_DIFFERS_FROM_RECORD"
    except FreezeRefused as e:
        res["gate_reason"] = str(e)
    except (KeyError, TypeError):
        res["gate_reason"] = "RECORD_GATE_RESULTS_MISSING"
    res["pass"] = bool(res["three_files_final"] and res["git_binding"] and res["write_once"] and res["auditor_code"]
                       and anchor_ok_ and res["gate_evidence"])
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
