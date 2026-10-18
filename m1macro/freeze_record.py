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


def find_push(events, commit):
    """events: activity API records for refs/heads/main. Exactly one push whose `after` is commit -> (id, time)."""
    hits = [e for e in events if e.get("activity_type") == "push" and e.get("ref") == "refs/heads/main"
            and e.get("after") == commit]
    if len(hits) != 1:
        raise PushNotFound("PUSH_EVENT_NOT_UNIQUE" if hits else "PUSH_EVENT_NOT_FOUND")
    return str(hits[0]["id"]), parse_utc(hits[0]["timestamp"])


def activity_lookup(repo, token, sleep=None):
    """Returns push_time(commit) -> (activity_id, server time); polls the activity API with the fixed wait."""
    import time
    sleep = sleep or time.sleep

    def push_time(commit):
        last = None
        for i in range(ACTIVITY_POLLS):
            req = urllib.request.Request(f"https://api.github.com/repos/{repo}/activity?ref=refs/heads/main"
                                         f"&activity_type=push&per_page=100",
                                         headers={"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"})
            try:
                with urllib.request.urlopen(req, timeout=30) as r:
                    return find_push(json.loads(r.read()), commit)
            except PushNotFound as e:
                last = e
                if str(e) == "PUSH_EVENT_NOT_UNIQUE":
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


def transaction(git, rec_b: bytes, ids: dict, run_start, af: dict, now, head_commit, push_time) -> dict:
    """git: RealGit-like adapter on a main worktree (create/append/ensure_header/push/remote). ids: Run_ID, Run_Attempt,
    Code_SHA256. now() -> aware datetime. head_commit() -> current main commit sha. push_time(commit) -> (activity id,
    server time) or raises PushNotFound. Returns the audit row (dict)."""
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
        act_id, t_push = push_time(mcommit); reject = ""
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


def gate_results(cand_root, code_sha, cand_sha):
    """Formal gate results for this Code_SHA256 on branch m1macro-gates-results (reference + minimal sanity checks)."""
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
    return {"Results_Branch": "m1macro-gates-results", "Results_Commit": commit, "Results_Dir": code_sha,
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
    snap = json.loads(_sh("git", "show", "origin/main:data/m1macro/dev_snapshot/manifest.json", cwd=main_wt))
    rec = {"Spec": "M1-MACRO-IMPL-CODE-V1", "Code_SHA256": code_sha, "Candidate_Commit": cand_sha,
           "CODE_MANIFEST_V1": manifest.manifest_bytes().decode("utf-8"),
           "Image_Digest": (ROOT / "env/IMAGE_DIGEST").read_text().strip(),
           "Requirements_Lock_SHA256": hashlib.sha256((ROOT / "env/requirements.lock").read_bytes()).hexdigest(),
           "Dev_Snapshot": {"Main_Commit": _sh("git", "log", "-1", "--format=%H", "origin/main", "--",
                                              "data/m1macro/dev_snapshot", cwd=main_wt).decode().strip(),
                            "Files": {f["source"] + ":" + f["path"]: f["sha256"] for f in snap["files"]}},
           "First_Forward_Origin": first, "CFTC_Snapshot_Window_Hours": win,
           "Gate_Results": gate_results(str(ROOT), code_sha, cand_sha),
           "Run": {"Run_ID": rid, "Run_Attempt": att, "Workflow": os.environ.get("GITHUB_WORKFLOW", "")}}
    git = gitrepo.RealGit(main_wt, message=f"preregistration: M1-MACRO implementation freeze (run {rid})")
    head = lambda: _sh("git", "rev-parse", "HEAD", cwd=main_wt).decode().strip()
    arow = transaction(git, record_bytes(rec), {"Run_ID": rid, "Run_Attempt": att, "Code_SHA256": code_sha},
                       run_start, af, now, head, activity_lookup(os.environ["GITHUB_REPOSITORY"], os.environ["GITHUB_TOKEN"]))
    print(json.dumps({k: arow[k] for k in ("Anchor_Status", "D2_Status", "Freeze_Status", "Reject_Reason")}))
    return arow["Freeze_Status"] == "FINAL"


def fresh_audit(root, repo, token, push_time=None) -> dict:
    """Fresh audit of a freeze on a main checkout: the canonical three files (is_final) AND the server anchor
    re-queried now (the recorded push id/time must equal the activity API's record for Marker_Commit). Read-only."""
    sys.path.insert(0, str(ROOT))
    from m1macro import manifest
    rd = lambda p: (Path(root) / p).read_bytes() if (Path(root) / p).exists() else b""
    res = {"three_files_final": False, "server_anchor_matches": False}
    rec_b = rd(RECORD)
    if not rec_b:
        res["reason"] = "NO_FREEZE_RECORD"; return res
    code = json.loads(rec_b).get("Code_SHA256")
    res["code_sha256_record"] = code; res["code_sha256_checkout"] = manifest.code_sha256()
    res["three_files_final"] = is_final(rec_b, rd(MARKER), rd(AUDIT), code)
    a = (_rows(rd(AUDIT)) or [{}])[0]
    try:
        aid, t = (push_time or activity_lookup(repo, token))(a.get("Marker_Commit", ""))
        res["server_anchor_matches"] = (aid == a.get("Marker_Push_Activity_ID") and utc_s(t) == a.get("Marker_Push_At_Server_UTC"))
    except PushNotFound as e:
        res["reason"] = str(e)
    res["pass"] = res["three_files_final"] and res["server_anchor_matches"]
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
