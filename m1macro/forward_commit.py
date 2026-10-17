"""Host-side phases of the M1-MACRO forward run (Impl Part 4 §3, §8): public data commit and the issuance
transaction. Standard library only (runs on the runner host, where git is available; no numerics here)."""
import base64
import csv
import datetime as dt
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from m1macro import deadline_gate as DG, ledger_tx as L, manifest  # noqa: E402
from m1macro.schema import (ESTIMATION_FIELDS, FEATURE_FIELDS, FETCH_FIELDS, FORECAST_FIELDS,  # noqa: E402
                            TREASURY_FIELDS)

CFG = json.loads((ROOT / "m1macro" / "config" / "m1macro_config.json").read_text("utf-8"))
DATA = "data/m1macro"
FETCHES = f"{DATA}/source_fetches.csv"
TREASURY_MANIFEST = f"{DATA}/treasury_raw_manifest.csv"
FREEZE_REL = "preregistration/M1-MACRO-IMPL-CODE-V1.freeze.json"
UTC = dt.timezone.utc


class PipelineFailure(Exception):
    pass


def run_id():
    return os.environ.get("GITHUB_RUN_ID", "local") + "-" + os.environ.get("GITHUB_RUN_ATTEMPT", "1")


def utc_s(t):
    return t.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def read_csv(rel):
    p = ROOT / rel
    if not p.exists():
        return []
    with open(p, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def _freeze_ok(code_sha):
    fz = ROOT / FREEZE_REL
    if not fz.exists():
        return False
    fr = json.loads(fz.read_text("utf-8"))
    return fr.get("Code_SHA256") == code_sha


def _complete_keys():
    """(origin, horizon) with a COMPLETE row on the synced tree (Part 4 §3: never issue twice)."""
    out = set()
    for r in read_csv(L.COMMITS):
        if r.get("Status") == "COMPLETE":
            for h in (r.get("Horizons") or "").split(";"):
                out.add((r["Origin"], h))
    return out


def commit_data(stage, git):
    """Copy staged public raw files and append fetch / Treasury manifest rows; push and reread (data, not ledger)."""
    pub = Path(stage, "public")
    for p in sorted(pub.rglob("*")) if pub.exists() else []:
        if p.is_file():
            rel = p.relative_to(pub).as_posix(); dst = ROOT / rel
            if dst.exists():
                if dst.read_bytes() != p.read_bytes():
                    raise PipelineFailure("STAGED_FILE_CONFLICT")
                continue
            dst.parent.mkdir(parents=True, exist_ok=True); dst.write_bytes(p.read_bytes()); git.touched.add(rel)
            git.pending = True
    recs = json.loads(Path(stage, "fetches.json").read_text()) if Path(stage, "fetches.json").exists() else []
    if recs:
        git.ensure_header(FETCHES, L.header_bytes(FETCH_FIELDS))
        for r in recs:
            git.append(FETCHES, L.row_bytes(FETCH_FIELDS, r))
    tre_p = Path(stage, "treasury_staged.json")
    if tre_p.exists() and json.loads(tre_p.read_text()):
        pc = Path(stage, "private_commit.txt").read_text().strip()
        git.ensure_header(TREASURY_MANIFEST, L.header_bytes(TREASURY_FIELDS))
        for t in json.loads(tre_p.read_text()):
            git.append(TREASURY_MANIFEST, L.row_bytes(TREASURY_FIELDS, {
                "Retrieved_At_UTC": t["retrieved_at_utc"], "Source_URL": t["url"], "Byte_Count": str(t["bytes"]),
                "SHA256": t["sha256"], "Private_Repository": CFG["private_raw_storage"]["Private_Repository"],
                "Private_Path": t["private_path"], "Private_Commit": pc}))
    for i in range(L.PUSH_RETRIES):
        try:
            git.push(); break
        except Exception:
            if i == L.PUSH_RETRIES - 1:
                raise PipelineFailure("DATA_PUSH_FAILED")
    for rel in sorted(git.touched):
        if git.remote(rel) != (ROOT / rel).read_bytes():
            raise PipelineFailure("DATA_REREAD_MISMATCH")


def _ontime_keys():
    """(origin, horizon) covered by a COMPLETE run that has an ON_TIME deadline audit row (formal issuance)."""
    ontime = {r["Run_ID"] for r in read_csv(L.DEADLINE) if r.get("Deadline_Status") == "ON_TIME"}
    out = set()
    for r in read_csv(L.COMMITS):
        if r.get("Status") == "COMPLETE" and r["Run_ID"] in ontime:
            for h in (r.get("Horizons") or "").split(";"):
                out.add((r["Origin"], h))
    return out


def _ledger_bytes(read):
    return tuple(read(p) for p in (L.COMMITS, L.DEADLINE, L.FORECASTS))


def _local(rel):
    p = ROOT / rel
    return p.read_bytes() if p.exists() else b""


def _audit_gate(commits, deadline, forecasts, code):
    v = DG.check(commits, deadline, forecasts)
    if v:
        print(json.dumps({"deadline_audit_gate": "FAIL", "violations": v}))
        raise PipelineFailure(code)


def record_not_issued(git, items, rid):
    """D8 Option B: deadline audit rows with Deadline_Status = NOT_ISSUED. Written once per Origin whose due horizons
    had no ON_TIME COMPLETE at the deadline (a COMPLETE that became LATE does not prevent it). Never duplicated,
    never updated or deleted. Committed_At_UTC / Verified_At_UTC stay empty. No forecast row is written."""
    have = {r["Origin"] for r in read_csv(L.DEADLINE) if r.get("Deadline_Status") == "NOT_ISSUED"}
    done = _ontime_keys(); n = 0
    if any(it["deadline_utc"] != DG.deadline_utc(it["origin"]) for it in items):     # validate before any write
        raise PipelineFailure("NOT_ISSUED_DEADLINE_MISMATCH")
    for it in items:
        hs = it["horizons"].split(";")
        if it["origin"] in have or all((it["origin"], h) in done for h in hs):
            continue
        git.ensure_header(L.DEADLINE, L.header_bytes(L.DEADLINE_FIELDS))
        git.append(L.DEADLINE, L.row_bytes(L.DEADLINE_FIELDS, {"Run_ID": rid, "Origin": it["origin"], "Committed_At_UTC": "",
                                                              "Verified_At_UTC": "", "Deadline_UTC": it["deadline_utc"],
                                                              "Deadline_Status": "NOT_ISSUED"}))
        have.add(it["origin"]); n += 1
    if n:
        for i in range(L.PUSH_RETRIES):
            try:
                git.push(); break
            except Exception:
                if i == L.PUSH_RETRIES - 1:
                    raise PipelineFailure("AUDIT_PUSH_FAILED")
        if git.remote(L.DEADLINE) != (ROOT / L.DEADLINE).read_bytes():
            raise PipelineFailure("AUDIT_REREAD_MISMATCH")
    return n


def commit_tx(stage, git, now_fn=None):
    tx = json.loads(Path(stage, "tx.json").read_text())
    pre = _ledger_bytes(_local)
    _audit_gate(*pre, "DEADLINE_AUDIT_GATE_PRE")                  # fail closed on an inconsistent synced tree
    res = []
    if tx.get("txs"):
        res = _commit_txs(tx, git, now_fn)
    if tx.get("not_issued"):
        print(json.dumps({"not_issued_recorded": record_not_issued(git, tx["not_issued"], tx["run_id"])}))
    if tx.get("txs") or tx.get("not_issued"):                    # after the writes: the remote, freshly reread
        try:                                                      # a file absent locally was never written: b""
            post = _ledger_bytes(lambda p: git.remote(p) if (ROOT / p).exists() else b"")
        except Exception:
            raise PipelineFailure("DEADLINE_AUDIT_REREAD_FAILED")
        if not DG.append_only(pre[1], post[1]):
            print(json.dumps({"deadline_audit_gate": "FAIL", "violations": ["AUDIT_ROW_UPDATED_OR_DELETED"]}))
            raise PipelineFailure("DEADLINE_AUDIT_GATE_POST")
        _audit_gate(*post, "DEADLINE_AUDIT_GATE_POST")
    if not tx.get("txs"):
        print(json.dumps({"status": tx["status"]})); return None
    return res[-1] if len(res) == 1 else res


def _commit_txs(tx, git, now_fn):
    if manifest.code_sha256() != tx["code_sha256"] or not _freeze_ok(tx["code_sha256"]):
        raise PipelineFailure("CODE_SHA_CHANGED")
    fields = {L.FEATURES: FEATURE_FIELDS, L.ESTIMATION: ESTIMATION_FIELDS, L.FORECASTS: FORECAST_FIELDS}
    res = []
    for i, t in enumerate(tx["txs"]):
        if any((t["origin"], h) in _complete_keys() for h in t["horizons"].split(";")):
            res.append({"origin": t["origin"], "status": "ALREADY_COMPLETE"}); continue
        rows = {k: [base64.b64decode(x) for x in v] for k, v in t["rows"].items()}
        rid = tx["run_id"] if len(tx["txs"]) == 1 else f"{tx['run_id']}-{i}"
        st = L.run_transaction(git, rows, fields, rid, t["origin"], t["horizons"], t["deadline_utc"],
                               now_fn or (lambda: utc_s(dt.datetime.now(UTC))))
        res.append({"origin": t["origin"], **{k: st.get(k) for k in ("run_id", "status", "deadline_status", "failed_step")}})
    print(json.dumps(res))
    return res


def main(argv):
    cmd, stage = argv[0], argv[1]
    from m1macro import gitrepo
    if cmd == "commit-data":
        commit_data(stage, gitrepo.RealGit(ROOT, message=f"data: M1-MACRO sources run {run_id()}"))
    elif cmd == "commit-tx":
        commit_tx(stage, gitrepo.RealGit(ROOT, message=f"ledger: M1-MACRO run {run_id()}"))
    else:
        raise SystemExit("unknown command")


if __name__ == "__main__":
    main(sys.argv[1:])
