"""M1-MACRO-V1 forward issuance (Impl Part 1 §2.3.1, §3, §4; Part 3 §2-§6; Part 4 §3, §4, §8).

Phases (the workflow runs them in this order; compute phases inside the pinned image):
  cftc-snapshot <stage>          pre-T_info CFTC snapshot (00:40 / 02:40 JST): fetch, normality, stage raw + record
  fetch <stage>                  Treasury (Y-1, Y), MOF (all, current), CFTC release schedule: stage raw + records
  [shell: Treasury raw -> private repository; fresh-clone readback; writes <stage>/private_commit.txt]
  commit-data <stage>            host: public raw files + manifests -> main (push, reread)
  compute <stage> <priv_dev_dir> host-free: features, E_{t,h}, estimation, forecast rows -> <stage>/tx.json
  commit-tx <stage>              host: Part 4 §3 transaction (3 ledgers -> COMPLETE -> deadline audit)
All phases read the repository working tree, which the workflow has synced to origin/main.
"""
import base64
import csv
import datetime as dt
import hashlib
import io
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from m1macro import (canon, cftc_feature, cftc_parse, cftc_schedule, estimation as E, features, ledger_tx as L,  # noqa
                     manifest, rates, s0link, sources as S)
from m1macro.forecast import decide, f17, forecast_fields, mu as mu_fn, n_of  # noqa: E402
from m1macro.tz import JST, UTC  # noqa: E402
from m1macro import forward_commit as FC  # noqa: E402
from m1macro.forward_commit import (PipelineFailure, _complete_keys, _freeze_ok, commit_data, commit_tx,  # noqa: E402,F401
                                    read_csv, utc_s, FREEZE_REL, FETCHES, TREASURY_MANIFEST)
from m1macro.schema import ESTIMATION_FIELDS, FETCH_FIELDS, FORECAST_FIELDS, TREASURY_FIELDS  # noqa: E402,F401

CFG = json.loads((ROOT / "m1macro" / "config" / "m1macro_config.json").read_text("utf-8"))
DATA = "data/m1macro"
HORIZONS = ("1D", "1W", "4W")
CUTOFF = dt.time(8, 30)
MODEL = "M1-MACRO-V1"
PARENT = "S0-EMPCLIM-STD-EXP-V1"


def parse_utc(s):
    return dt.datetime.strptime(s, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC)


def run_id():
    return os.environ.get("GITHUB_RUN_ID", "local") + "-" + os.environ.get("GITHUB_RUN_ATTEMPT", "1")


def _now(args_now=None):
    return dt.datetime.fromisoformat(args_now).astimezone(UTC) if args_now else dt.datetime.now(UTC)


def _stage_put(stage, rel, b):
    p = Path(stage, "public", rel); p.parent.mkdir(parents=True, exist_ok=True); p.write_bytes(b)


def _rec_append(stage, name, row):
    p = Path(stage, name)
    rows = json.loads(p.read_text()) if p.exists() else []
    rows.append(row); p.write_text(json.dumps(rows, indent=1))


def _stamp(t):
    return t.astimezone(UTC).strftime("%Y%m%dT%H%M%SZ")


def _prev_accepted(source):
    rows = [r for r in read_csv(FETCHES) if r["Source"] == source and r["Normal"] == "true"]
    if not rows:
        return None
    p = ROOT / rows[-1]["Dates_Path"]
    return [dt.date.fromisoformat(x) for x in p.read_text().split()]


def _dates_file(source, sha, dates):
    rel = f"{DATA}/accepted_dates/{source}_{sha[:16]}.txt"
    return rel, ("\n".join(d.isoformat() for d in sorted(dates)) + "\n").encode()


# ------------------------------------------------------------------ CFTC pre-T_info snapshot
def cftc_snapshot(stage, now=None):
    now = _now(now); rid = run_id()
    year = now.astimezone(JST).year
    url = S.cftc_year_url(year)
    rec = {"Run_ID": rid, "Source": "cftc", "Source_URL": url, "Normal": "false", "Subreason": ""}
    try:
        f = S.fetch_retry(url, tries=2, wait=5)
    except S.FetchFailure as e:
        rec.update(Retrieved_At_UTC=utc_s(_now()), Subreason="FETCH_FAILED")
        _rec_append(stage, "fetches.json", rec); return rec
    rel = f"{DATA}/cftc/{year}/{_stamp(parse_utc(f['retrieved_at_utc']))}_{f['sha256'][:12]}.zip"
    rec.update(Retrieved_At_UTC=f["retrieved_at_utc"], Byte_Count=str(f["n"]), SHA256=f["sha256"], Path=rel)
    _stage_put(stage, rel, f["b"])
    try:
        reps = cftc_parse.parse_zip(f["b"])
        dates = list(reps)
        sub = rates.calendar_integrity(_prev_accepted("cftc"), dates) if reps else "EMPTY"
        if not sub:
            drel, db = _dates_file("cftc", f["sha256"], dates); _stage_put(stage, drel, db)
            rec.update(Normal="true", Dates_Path=drel)
        else:
            rec["Subreason"] = sub
    except cftc_parse.ParseFailure:
        rec["Subreason"] = "PARSE_FAILED"
    _rec_append(stage, "fetches.json", rec)
    return rec


# ------------------------------------------------------------------ fetch (after T_info)
def fetch(stage, now=None):
    now = _now(now); rid = run_id(); y = now.astimezone(JST).year
    tre = []
    for yy in (y - 1, y):
        url = S.treasury_url(yy)
        try:
            f = S.fetch_retry(url)
        except S.FetchFailure:
            _rec_append(stage, "fetches.json", {"Run_ID": rid, "Source": "treasury", "Source_URL": url,
                                                "Retrieved_At_UTC": utc_s(_now()), "Normal": "false",
                                                "Subreason": "FETCH_FAILED"})
            tre = None; break
        p = Path(stage, "private", f"m1macro_forward/treasury/{_stamp(parse_utc(f['retrieved_at_utc']))}_{yy}_{f['sha256'][:12]}.csv")
        p.parent.mkdir(parents=True, exist_ok=True); p.write_bytes(f["b"])
        tre.append({"url": url, "retrieved_at_utc": f["retrieved_at_utc"], "bytes": f["n"], "sha256": f["sha256"],
                    "private_path": p.relative_to(Path(stage, "private")).as_posix()})
    Path(stage, "treasury_staged.json").write_text(json.dumps(tre))
    # Treasury normality (§1.1): parse every file, merge, integrity against the previous accepted snapshot.
    if tre is not None:
        try:
            parts = [rates.parse_treasury_csv(Path(stage, "private", t["private_path"]).read_bytes()) for t in tre]
            us = rates.merge(*parts)
            sub = rates.calendar_integrity(_prev_accepted("treasury"), list(us)) if us else "EMPTY"
        except rates.ParseError:
            us, sub = None, "PARSE_FAILED"
        drel = ""
        if not sub:
            h = hashlib.sha256("".join(t["sha256"] for t in tre).encode()).hexdigest()
            drel, db = _dates_file("treasury", h, list(us)); _stage_put(stage, drel, db)
        for t in tre:
            _rec_append(stage, "fetches.json", {"Run_ID": rid, "Source": "treasury", "Source_URL": t["url"],
                        "Retrieved_At_UTC": t["retrieved_at_utc"], "Byte_Count": str(t["bytes"]), "SHA256": t["sha256"],
                        "Path": "private:" + t["private_path"], "Normal": "false" if sub else "true", "Subreason": sub,
                        "Dates_Path": drel})
    mof = []
    for name, url in (("mof_all", S.MOF_ALL), ("mof_current", S.MOF_CURRENT)):
        try:
            f = S.fetch_retry(url)
        except S.FetchFailure:
            mof = None; break
        rel = f"{DATA}/mof/{_stamp(parse_utc(f['retrieved_at_utc']))}_{name}_{f['sha256'][:12]}.csv"
        _stage_put(stage, rel, f["b"]); mof.append((name, url, f, rel))
    if mof is None:
        _rec_append(stage, "fetches.json", {"Run_ID": rid, "Source": "mof", "Source_URL": S.MOF_ALL,
                    "Retrieved_At_UTC": utc_s(_now()), "Normal": "false", "Subreason": "FETCH_FAILED"})
    else:
        try:
            jp = rates.merge(*[rates.parse_mof_csv(f["b"]) for _, _, f, _ in mof])
            sub = rates.calendar_integrity(_prev_accepted("mof"), list(jp)) if jp else "EMPTY"
        except rates.ParseError:
            jp, sub = None, "PARSE_FAILED"
        drel = ""
        if not sub:
            h = hashlib.sha256("".join(f["sha256"] for _, _, f, _ in mof).encode()).hexdigest()
            drel, db = _dates_file("mof", h, list(jp)); _stage_put(stage, drel, db)
        for name, url, f, rel in mof:
            _rec_append(stage, "fetches.json", {"Run_ID": rid, "Source": "mof", "Source_URL": url,
                        "Retrieved_At_UTC": f["retrieved_at_utc"], "Byte_Count": str(f["n"]), "SHA256": f["sha256"],
                        "Path": rel, "Normal": "false" if sub else "true", "Subreason": sub, "Dates_Path": drel})
    rec = {"Run_ID": rid, "Source": "cftc_schedule", "Source_URL": S.CFTC_SCHEDULE, "Normal": "false", "Subreason": ""}
    try:
        f = S.fetch_retry(S.CFTC_SCHEDULE)
        rel = f"{DATA}/cftc_schedule/{_stamp(parse_utc(f['retrieved_at_utc']))}_{f['sha256'][:12]}.html"
        rec.update(Retrieved_At_UTC=f["retrieved_at_utc"], Byte_Count=str(f["n"]), SHA256=f["sha256"], Path=rel)
        _stage_put(stage, rel, f["b"])
        try:
            cftc_schedule.parse(f["b"]); rec["Normal"] = "true"
        except cftc_schedule.ScheduleParseFailure:
            rec["Subreason"] = "PARSE_FAILED"
    except S.FetchFailure:
        rec.update(Retrieved_At_UTC=utc_s(_now()), Subreason="FETCH_FAILED")
    _rec_append(stage, "fetches.json", rec)


# ------------------------------------------------------------------ compute (pinned image; no git, no token)
def first_forward():
    v = CFG.get("first_forward_origin")
    if not v or any(not v.get(h) for h in HORIZONS):
        return None
    return {h: v[h] for h in HORIZONS}


def _this_run_fetches(source, rid):
    return [r for r in read_csv(FETCHES) if r["Source"] == source and r["Run_ID"] == rid]


def _load_verified(rel, sha):
    b = (ROOT / rel).read_bytes()
    if hashlib.sha256(b).hexdigest() != sha:
        raise PipelineFailure("RAW_SHA_MISMATCH")
    return b


def forward_features(D: dt.date, rid: str, stage):
    """F_US, F_JP from this run's normal snapshots; F_POS via the CFTC Forward Snapshot Gate."""
    tinfo = features.tinfo_utc(D)
    unavailable = lambda sub: rates.Feature("ABSTAIN_SYSTEM", "FEATURE_UNAVAILABLE", sub)
    srcinfo = {}
    tr = _this_run_fetches("treasury", rid)
    man = {r["SHA256"]: r for r in read_csv(TREASURY_MANIFEST)}
    if not tr or any(r["Normal"] != "true" for r in tr):
        fus = unavailable(next((r["Subreason"] for r in tr if r["Subreason"]), "FETCH_FAILED"))
    else:
        parts = []
        for r in tr:
            if r["SHA256"] not in man:
                raise PipelineFailure("TREASURY_NOT_IN_PUBLIC_MANIFEST")
            b = Path(stage, "private", r["Path"].split(":", 1)[1]).read_bytes()
            if hashlib.sha256(b).hexdigest() != r["SHA256"]:
                raise PipelineFailure("TREASURY_PRIVATE_SHA_MISMATCH")
            parts.append(rates.parse_treasury_csv(b))
        fus = rates.f_us(D, rates.merge(*parts), forward=True)
        srcinfo["treasury"] = {"retrieved_at_utc": tr[-1]["Retrieved_At_UTC"], "bytes": ";".join(r["Byte_Count"] for r in tr),
                               "sha256": ";".join(r["SHA256"] for r in tr),
                               "path": ";".join(man[r["SHA256"]]["Private_Path"] + "@" + man[r["SHA256"]]["Private_Commit"][:12] for r in tr)}
    mo = _this_run_fetches("mof", rid)
    if len(mo) != 2 or any(r["Normal"] != "true" for r in mo):
        fjp = unavailable(next((r["Subreason"] for r in mo if r["Subreason"]), "FETCH_FAILED"))
    else:
        jp = rates.merge(*[rates.parse_mof_csv(_load_verified(r["Path"], r["SHA256"])) for r in mo])
        fjp = rates.f_jp(D, jp, forward=True)
        srcinfo["mof"] = {"retrieved_at_utc": mo[-1]["Retrieved_At_UTC"], "bytes": ";".join(r["Byte_Count"] for r in mo),
                          "sha256": ";".join(r["SHA256"] for r in mo), "path": ";".join(r["Path"] for r in mo)}
    snaps, reports_by_sha = [], {}
    for r in read_csv(FETCHES):
        if r["Source"] != "cftc" or r["Normal"] != "true":
            continue
        t = parse_utc(r["Retrieved_At_UTC"])
        if not (tinfo - cftc_feature.WINDOW < t <= tinfo):
            continue
        reps = cftc_parse.parse_zip(_load_verified(r["Path"], r["SHA256"]))
        snaps.append(cftc_feature.Snapshot(t, r["SHA256"], True, reps)); reports_by_sha[r["SHA256"]] = (reps, r)
    sch = _this_run_fetches("cftc_schedule", rid)
    parsed = None
    if sch and sch[-1]["Normal"] == "true":
        parsed = cftc_schedule.parse(_load_verified(sch[-1]["Path"], sch[-1]["SHA256"]))
    fpos = cftc_feature.forward(D, tinfo, snaps, cftc_schedule.for_tinfo(parsed, tinfo))
    reps = {}
    if fpos.snapshot_sha256:
        reps, r = reports_by_sha[fpos.snapshot_sha256]
        srcinfo["cftc"] = {"retrieved_at_utc": r["Retrieved_At_UTC"], "bytes": r["Byte_Count"], "sha256": r["SHA256"],
                           "path": r["Path"]}
    return fus, fjp, fpos, reps, srcinfo


def _ledger_parent_rows(D_iso, h):
    return {r["Pair"]: r for r in read_csv("ledger/forecasts.csv")
            if r["Model"] == PARENT and r["Origin"] == D_iso and r["Horizon"] == h}


def _s0_as_frozen(r):
    """Ledger S0 row -> the frozen S0 output field names used by forecast_fields."""
    return dict(r, S0_Point_LogReturn=r["Point_LogReturn"])


def forward_groups(h, origin_t, laf_t, first_h, mp, s0mod, lb):
    """Groups of forward origins i (>= first forward origin) from the formal ledgers (Part 3 §4, Forward column).
    Pools: frozen S0 regenerated on the stored ECB history (<= LAF_t) and verified against the issued S0 rows."""
    tinfo_t = features.tinfo_utc(dt.date.fromisoformat(origin_t))
    off = {r["Run_ID"] for r in read_csv(L.COMMITS) if r.get("Status") == "COMPLETE"}   # UNCOMMITTED rows never enter
    feats = {}
    for r in read_csv(L.FEATURES):
        if r["Run_ID"] in off and first_h <= r["Origin"] < origin_t:
            feats[r["Origin"]] = {k: (r[f"F_{k}_Status"], r[f"F_{k}_Reason"], r[f"F_{k}_Subreason"],
                                      float(r[f"F_{k}"]) if r[f"F_{k}_Status"] == "OK" else None) for k in ("US", "JP", "POS")}
    s0rows = {(r["Pair"], r["Origin"], r["Horizon"]): r for r in read_csv("ledger/forecasts.csv")
              if r["Model"] == PARENT and r["Horizon"] == h and first_h <= r["Origin"] < origin_t}
    outc = {}
    for r in read_csv("ledger/outcomes.csv"):
        if r["Horizon"] == h and r["Outcome_Status"] == "OBSERVED" and parse_utc(r["Recorded_At_UTC"]) <= tinfo_t:
            outc[(r["Pair"], r["Origin"], r["Horizon"])] = r
    if not s0rows:
        return []
    raw_csv = (ROOT / "data" / "ecb" / "eurofxref-hist.csv").read_bytes()
    import zipfile
    zb = io.BytesIO()
    with zipfile.ZipFile(zb, "w") as z:
        z.writestr("eurofxref-hist.csv", raw_csv)
    _, raw = lb.read_ecb_zip(zb.getvalue())
    raw = [x for x in raw if x["Date"] <= dt.date.fromisoformat(laf_t)]
    extra = sorted({(p, dt.date.fromisoformat(o), hh) for (p, o, hh) in s0rows}, key=lambda k: (k[1], k[0]))
    rows = lb.to_strings(lb.build_rows(lb.load_frozen()[0], mp, raw, extra_origins=()))
    have = {(r["Pair"], r["Origin"], r["Horizon"]) for r in rows}
    extra = [k for k in extra if (k[0], k[1].isoformat(), k[2]) not in have]
    rows = lb.to_strings(lb.build_rows(lb.load_frozen()[0], mp, raw, extra_origins=extra))
    outputs, pools = s0link.regenerate(s0mod, rows)
    s0link.verify_against_issued(outputs, s0rows)
    opp = {}
    for k, r in s0rows.items():
        o = outc.get(k)
        opp[k] = {"Target_End": r["Target_End"], "Outcome_Status": "OBSERVED" if o else "",
                  "Realized_LogReturn": o["Realized_LogReturn"] if o else ""}
    return E.static_groups(h, opp, s0rows, feats, pools)


def gap_origins(h, recon_last, first_h, laf_t, mp):
    n = 0
    d = dt.date.fromisoformat(recon_last) + dt.timedelta(days=1)
    while d < dt.date.fromisoformat(first_h):
        if mp.is_formal_origin(d, h) and mp.map_origin(d, h).target_end <= dt.date.fromisoformat(laf_t):
            n += 1
        d += dt.timedelta(days=1)
    return n


def build_rows_for_origin(D, now, rid, code_sha, stage, priv_dev_dir, ctx=None):
    """All M1 rows for origin D (every horizon due at D). Returns (features_rows, estimation_rows, forecast_rows)."""
    sys.path.insert(0, str(ROOT / "forward"))
    import ledger_builder as lb
    from m1macro import pipeline
    m0, mp, s0mod = lb.load_frozen()
    first = first_forward()
    D_iso = D.isoformat()
    hs = [h for h in HORIZONS if mp.is_formal_origin(D, h) and D_iso >= first[h] and (D_iso, h) not in _complete_keys()]
    if not hs:
        return None
    fus, fjp, fpos, reps, srcinfo = forward_features(D, rid, stage)
    frow = features.feature_row(D, fus, fjp, fpos, reps, srcinfo, "", code_sha, rid)
    fstate = {"US": features.state(fus), "JP": features.state(fjp), "POS": features.state(fpos)}
    if ctx is None:
        us, jp, creps, _ = pipeline.load_dev_snapshot(ROOT / DATA / "dev_snapshot" / "manifest.json",
                                                       ROOT / DATA / "dev_snapshot", priv_dev_dir)
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            ctx = pipeline.Context(td, us, jp, creps)
    erows, frows = [], []
    issued = utc_s(now)
    for h in hs:
        parents = _ledger_parent_rows(D_iso, h)
        if set(parents) != set(E.DEV_PAIRS):
            raise PipelineFailure("PARENT_ROWS_MISSING")       # caller retries in a later run before the cutoff
        laf = parents["USDJPY"]["Last_Available_Fix"] or next(p["Last_Available_Fix"] for p in parents.values())
        pipe_fail = False
        try:
            fw = forward_groups(h, D_iso, laf, first[h], mp, s0mod, lb)
            rec = [r for r in ctx.recs[h] if r.origin < first[h]] + fw
            rec.sort(key=lambda r: (r.origin, r.pair))
            e = E.assemble_from(rec, D_iso, h, laf)
            recon_last = max(k[1] for k in ctx.opp if k[2] == h)
            ngap = gap_origins(h, recon_last, first[h], laf, mp)
        except (s0link.PipelineFailure, PipelineFailure, E.HoldoutBreach):
            pipe_fail = True; e = None; ngap = 0
        # Part 3 §3 note: estimate only if some pair passes steps 1-7 (decide() with no warm-up/solver input)
        elig = [p for p in E.DEV_PAIRS
                if decide(True, parents[p], pipe_fail, {k: fstate[k][:3] for k in fstate}, p, None, None)[0] == "FORECAST"]
        est = E.estimate(e, bool(elig)) if not pipe_fail else E.Estimate("NOT_EVALUATED", None)
        b = est.beta
        r = est.result
        erows.append({"Origin": D_iso, "Horizon": h, "Parameter_State": est.state,
                      "N_Warmup": "" if e is None else str(e.n_e), "N_Groups": "" if e is None else str(len(e.rows)),
                      "N_Gap_Origins": str(ngap), "N_Excluded_Zero_Scale": "" if e is None else str(e.n_excluded_zero_scale),
                      "E_Input_SHA256": "" if e is None else e.e_sha256,
                      "Beta_US": f17(b[0]) if b else "", "Beta_JP": f17(b[1]) if b else "", "Beta_POS": f17(b[2]) if b else "",
                      "Solver_Status": "OPTIMAL" if est.state == "ESTIMATED" else ("FAILED" if est.state == "ESTIMATION_FAILED" else ""),
                      "Solver_Subreason": est.subreason,
                      "Stage1_Iterations": str(r.stage1_iter) if r else "", "Stage2_Iterations": str(r.stage2_iter) if r else "",
                      "UB_minus_LB": repr(r.ub_minus_lb) if r else "", "Phi_beta2_minus_LB": repr(r.phi2_minus_lb) if r else "",
                      "J_Star": f17(r.ub) if r else "", "Code_SHA256": code_sha, "Run_ID": rid})
        for p in E.DEV_PAIRS:
            s0r = parents[p]
            warm = None if est.state == "NOT_EVALUATED" else (est.state != "DEFAULT_PARENT")
            dc, rc, sub, ps = decide(True, s0r, pipe_fail, {k: fstate[k][:3] for k in fstate}, p, warm,
                                     est.subreason if est.state == "ESTIMATION_FAILED" else None)
            row = {"Model": MODEL, "Pair": p, "Origin": D_iso, "Horizon": h, "Cutoff_JST": "08:30",
                   "Last_Available_Fix": s0r["Last_Available_Fix"], "Target_Start": s0r["Target_Start"],
                   "Target_End": s0r["Target_End"], "Pool_N": s0r["Pool_N"], "Mean_Z": s0r["Mean_Z"], "Q10_Z": s0r["Q10_Z"],
                   "Q90_Z": s0r["Q90_Z"], "Decision_Class": dc, "Reason_Code": rc, "Issued_At_UTC": issued,
                   "Code_SHA256": code_sha, "Run_ID": rid, "Parent": PARENT, "Parent_Run_ID": s0r["Run_ID"],
                   "Sigma_M0": s0r["Sigma_H"], "Parameter_State": ps, "Feature_Row_Origin": D_iso,
                   "Estimation_Row_Key": f"{D_iso}|{h}"}
            if dc == "FORECAST":
                m = mu_fn(p, b, {k: fstate[k][3] for k in n_of(p)})
                pool = None
                if m != 0.0:
                    pool = canon.pool_sorted_np(_pool_for(p, D_iso, h, laf, mp, s0mod, lb))
                    if len(pool) != int(s0r["Pool_N"]):
                        raise PipelineFailure("POOL_N_MISMATCH_AT_ORIGIN")
                ff = forecast_fields(_s0_as_frozen(s0r), m, pool)
                row.update({k: ff[k] for k in ("Point_LogReturn", "PI10", "PI90", "P_Down", "P_Neutral", "P_Up")})
                row.update(Beta_US=f17(b[0]) if p == "USDJPY" else "", Beta_JP=f17(b[1]), Beta_POS=f17(b[2]), Mu=f17(m))
            frows.append(row)
    return [frow], erows, frows


_POOL_CACHE = {}


def _pool_for(p, D_iso, h, laf, mp, s0mod, lb):
    """S0 pool at the forecast origin (frozen S0 on the stored ECB history <= LAF), verified against the issued row."""
    if (D_iso, h, laf) in _POOL_CACHE:
        return s0link.pool(_POOL_CACHE[(D_iso, h, laf)], p, h, D_iso)
    import zipfile
    zb = io.BytesIO()
    with zipfile.ZipFile(zb, "w") as z:
        z.writestr("eurofxref-hist.csv", (ROOT / "data" / "ecb" / "eurofxref-hist.csv").read_bytes())
    _, raw = lb.read_ecb_zip(zb.getvalue())
    raw = [x for x in raw if x["Date"] <= dt.date.fromisoformat(laf)]
    D = dt.date.fromisoformat(D_iso)
    rows = lb.to_strings(lb.build_rows(lb.load_frozen()[0], mp, raw, extra_origins=[(q, D, h) for q in E.DEV_PAIRS]))
    outputs, pools = s0link.regenerate(s0mod, rows)
    s0link.verify_against_issued(outputs, {k: v for k, v in
                                           {(r["Pair"], r["Origin"], r["Horizon"]): r for r in read_csv("ledger/forecasts.csv")
                                            if r["Model"] == PARENT and r["Origin"] == D_iso and r["Horizon"] == h}.items()})
    _POOL_CACHE.clear(); _POOL_CACHE[(D_iso, h, laf)] = pools
    return s0link.pool(pools, p, h, D_iso)


def _tx(origin, horizons, fr, er, fc):
    return {"origin": origin, "horizons": horizons,
            "deadline_utc": utc_s(dt.datetime.combine(dt.date.fromisoformat(origin), CUTOFF, tzinfo=JST)),
            "rows": {L.FEATURES: [base64.b64encode(L.row_bytes(features.FEATURE_FIELDS, r)).decode() for r in fr],
                     L.ESTIMATION: [base64.b64encode(L.row_bytes(ESTIMATION_FIELDS, r)).decode() for r in er],
                     L.FORECASTS: [base64.b64encode(L.row_bytes(FORECAST_FIELDS, r)).decode() for r in fc]}}


def not_issued(now):
    """D8 Option B (むすび 2026-10-18): an Origin whose deadline passed while a due horizon had no ON_TIME COMPLETE
    is recorded as NOT_ISSUED in the deadline audit only (an issuance/audit state, not a forecast). A COMPLETE that
    became LATE does not prevent it. No prediction rows are written. One transaction covers every due horizon of an
    Origin, so a mix (some due horizons ON_TIME, others not) cannot arise; it is refused if it ever does."""
    sys.path.insert(0, str(ROOT / "forward"))
    import ledger_builder as lb
    _, mp, _ = lb.load_frozen()
    first = first_forward(); done = FC._ontime_keys()
    d = dt.date.fromisoformat(min(first.values())); out = []
    while d <= now.astimezone(JST).date():
        dl = dt.datetime.combine(d, CUTOFF, tzinfo=JST)
        if now >= dl:
            due = [h for h in HORIZONS if mp.is_formal_origin(d, h) and d.isoformat() >= first[h]]
            hs = [h for h in due if (d.isoformat(), h) not in done]
            if hs and len(hs) != len(due):
                raise PipelineFailure("PARTIAL_ISSUANCE")
            if hs:
                out.append({"origin": d.isoformat(), "horizons": ";".join(hs), "deadline_utc": utc_s(dl)})
        d += dt.timedelta(days=1)
    return out


def compute(stage, priv_dev_dir, now=None):
    now = _now(now); rid = run_id(); code_sha = manifest.code_sha256()
    out = {"run_id": rid, "code_sha256": code_sha, "status": "", "txs": [], "not_issued": []}
    if not _freeze_ok(code_sha) or first_forward() is None:
        out["status"] = "REFUSED_NOT_FROZEN"          # never compute beta/mu on real data before the freeze
    else:
        D = now.astimezone(JST).date()
        out["not_issued"] = not_issued(now)
        if now < features.tinfo_utc(D):
            out["status"] = "BEFORE_TINFO"
        elif now >= dt.datetime.combine(D, CUTOFF, tzinfo=JST):
            out["status"] = "AFTER_CUTOFF"
        else:
            try:
                res = build_rows_for_origin(D, now, rid, code_sha, stage, priv_dev_dir)
                if res is None:
                    out["status"] = "NOTHING_DUE"
                else:
                    fr, er, fc = res
                    out["status"] = "READY"
                    out["txs"].append(_tx(D.isoformat(), ";".join(r["Horizon"] for r in er), fr, er, fc))
            except PipelineFailure as e:
                out["status"] = "PIPELINE_FAILURE:" + str(e)[:60] if str(e).isupper() else "PIPELINE_FAILURE"
            except Exception as e:                        # unexpected: type name only (messages may quote values)
                out["status"] = "PIPELINE_FAILURE:" + type(e).__name__
    Path(stage, "tx.json").write_text(json.dumps(out))
    print(json.dumps({"run_id": rid, "status": out["status"], "n_tx": len(out["txs"]), "n_not_issued": len(out["not_issued"])}))          # no values
    return out


def main(argv):
    cmd, stage = argv[0], argv[1]
    Path(stage).mkdir(parents=True, exist_ok=True)
    if cmd == "cftc-snapshot":
        r = cftc_snapshot(stage); print(json.dumps({k: r.get(k) for k in ("Source", "Normal", "Subreason", "Retrieved_At_UTC")}))
    elif cmd == "fetch":
        fetch(stage)
    elif cmd == "compute":
        compute(stage, argv[2])
    else:
        raise SystemExit("unknown command")


if __name__ == "__main__":
    main(sys.argv[1:])
