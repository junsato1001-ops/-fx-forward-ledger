"""End-to-end forward issuance on a temporary repository with SYNTHETIC feature sources (Treasury/MOF/CFTC are
generated here; ECB prices and S0 are the frozen development data). Checks: refusal before the freeze, the
compute -> transaction path, COMPLETE/ON_TIME, no double issuance, deterministic E_Input_SHA256, S0 nesting at mu=0.
No real feature data is used, so the estimates are not M1-MACRO-V1 estimates and are not printed."""
import base64
import csv
import datetime as dt
import hashlib
import io
import json
import random
import shutil
import subprocess
import tempfile
import zipfile
from pathlib import Path

from m1macro import forward_run as FR, ledger_tx as L, manifest, pipeline, s0link
from m1macro.tz import JST, UTC

FIX = Path(__file__).resolve().parent / "fixtures" / "cftc_release_schedule_2026.html"
D = dt.date(2026, 10, 8)


def _series(end):
    random.seed(3)
    d = dt.date(2009, 1, 2); out = []; v, w = 1.0, 0.3
    while d <= end:
        if d.weekday() < 5:
            v += random.gauss(0, .02); w += random.gauss(0, .01); out.append((d, v, w))
        d += dt.timedelta(days=1)
    return out


def _treasury_bytes(rows):
    return ("Date,\"1 Mo\",\"2 Yr\"\n" + "\n".join(f"{x.strftime('%m/%d/%Y')},0.1,{a:.2f}" for x, a, _ in reversed(rows)) + "\n").encode()


def _mof_bytes(rows):
    era = lambda x: f"R{x.year - 2018}.{x.month}.{x.day}" if x.year >= 2019 else f"H{x.year - 1988}.{x.month}.{x.day}"
    return ("国債金利情報,,\n基準日,1年,2年\n" + "\n".join(f"{era(x)},0.1,{b:.3f}" for x, _, b in rows) + "\n").encode("shift_jis")


def _cftc_bytes(last):
    random.seed(4)
    H = ("Market_and_Exchange_Names,Report_Date_as_YYYY-MM-DD,CFTC_Contract_Market_Code,Open_Interest_All,"
         "Lev_Money_Positions_Long_All,Lev_Money_Positions_Short_All\n")
    t = dt.date(2006, 6, 13); L_ = []
    while t <= last:
        L_.append(f'"JAPANESE YEN",{t.isoformat()},097741,{random.randint(150000, 300000)},'
                  f'{random.randint(20000, 90000)},{random.randint(20000, 90000)}'); t += dt.timedelta(days=7)
    b = io.BytesIO()
    with zipfile.ZipFile(b, "w") as z:
        z.writestr("F.txt", H + "\n".join(L_) + "\n")
    return b.getvalue()


def _git(root, *a):
    subprocess.run(["git", *a], cwd=root, check=True, capture_output=True)


def run():
    out = {}
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        # synthetic development snapshot (features) -> reconstruction context
        rows = _series(dt.date(2026, 10, 9))
        dev = td / "dev"; (dev / "pub" / "mof").mkdir(parents=True); (dev / "pub" / "cftc").mkdir(); (dev / "priv" / "treasury").mkdir(parents=True)
        files = [("treasury", "treasury/t.csv", dev / "priv", _treasury_bytes(rows)), ("mof", "mof/m.csv", dev / "pub", _mof_bytes(rows)),
                 ("cftc", "cftc/c.zip", dev / "pub", _cftc_bytes(dt.date(2026, 10, 6)))]
        for src, rel, base, b in files:
            (base / rel).write_bytes(b)
        (dev / "manifest.json").write_text(json.dumps({"files": [{"source": s, "path": r, "bytes": len(b),
                                           "sha256": hashlib.sha256(b).hexdigest()} for s, r, _, b in files]}))
        us, jp, reps, _ = pipeline.load_dev_snapshot(dev / "manifest.json", dev / "pub", dev / "priv")
        ctx = pipeline.Context(str(td), us, jp, reps)
        # temporary repository = public main
        bare = td / "pub.git"; root = td / "root"
        _git(td, "init", "-q", "--bare", "-b", "main", str(bare)); _git(td, "clone", "-q", str(bare), str(root))
        with zipfile.ZipFile(s0link.ECB_DEV_ZIP) as z:
            (root / "data" / "ecb").mkdir(parents=True); (root / "data" / "ecb" / "eurofxref-hist.csv").write_bytes(z.read("eurofxref-hist.csv"))
        s0k = {k: v for k, v in ctx.s0.items() if k[1] == D.isoformat() and k[2] == "1D"}
        assert len(s0k) == 3 and all(v["Decision_Class"] == "FORECAST" for v in s0k.values())
        (root / "ledger").mkdir()
        with open(root / "ledger" / "forecasts.csv", "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=["Model", "Pair", "Origin", "Horizon", "Last_Available_Fix", "Target_Start",
                                              "Target_End", "Sigma_H", "Point_LogReturn", "P_Down", "P_Neutral", "P_Up",
                                              "PI10", "PI90", "Pool_N", "Mean_Z", "Q10_Z", "Q90_Z", "Decision_Class",
                                              "Reason_Code", "Run_ID"], lineterminator="\n")
            w.writeheader()
            for (p, o, h), s in sorted(s0k.items()):
                m = ctx.opp[(p, o, h)]
                w.writerow({"Model": FR.PARENT, "Pair": p, "Origin": o, "Horizon": h, "Last_Available_Fix": m["Last_Available_Fix"],
                            "Target_Start": m["Target_Start"], "Target_End": m["Target_End"], "Sigma_H": s["Sigma_H"],
                            "Point_LogReturn": s["S0_Point_LogReturn"], **{k: s[k] for k in ("P_Down", "P_Neutral", "P_Up", "PI10",
                            "PI90", "Pool_N", "Mean_Z", "Q10_Z", "Q90_Z", "Decision_Class", "Reason_Code")}, "Run_ID": "S0RUN"})
        _git(root, "add", "-A"); _git(root, "-c", "user.name=t", "-c", "user.email=t@e", "commit", "-q", "-m", "init")
        _git(root, "push", "-q", "origin", "HEAD:main")
        old_root, old_cfg, old_rid = FR.ROOT, dict(FR.CFG), FR.run_id
        FR.ROOT = root; FR.FC.ROOT = root
        try:
            FR.CFG["first_forward_origin"] = {"1D": D.isoformat(), "1W": "2026-10-11", "4W": "2026-10-11"}
            rid = "R1"
            FR.run_id = lambda: rid
            stage = td / "stage"; stage.mkdir()
            now = dt.datetime(2026, 10, 8, 5, 0, tzinfo=JST)
            # 1) refused before the freeze (no beta/mu computed)
            assert FR.compute(str(stage), str(dev / "priv"), now.isoformat())["status"] == "REFUSED_NOT_FROZEN"
            (root / "preregistration").mkdir()
            (root / FR.FREEZE_REL).write_text(json.dumps({"Code_SHA256": manifest.code_sha256()}))
            # 2) sources of this run (synthetic), as commit-data would leave them on main
            tb = _treasury_bytes([r for r in rows if r[0] <= dt.date(2026, 10, 7)])
            pp = stage / "private" / "m1macro_forward" / "treasury" / "t.csv"; pp.parent.mkdir(parents=True); pp.write_bytes(tb)
            mb = _mof_bytes([r for r in rows if r[0] <= dt.date(2026, 10, 7)])
            cb = _cftc_bytes(dt.date(2026, 9, 29))
            for rel, b in (("data/m1macro/mof/a.csv", mb), ("data/m1macro/mof/b.csv", mb), ("data/m1macro/cftc/s.zip", cb),
                           ("data/m1macro/cftc_schedule/s.html", FIX.read_bytes())):
                (root / rel).parent.mkdir(parents=True, exist_ok=True); (root / rel).write_bytes(b)
            sh = lambda b: hashlib.sha256(b).hexdigest()
            fe = [{"Run_ID": rid, "Source": "treasury", "Retrieved_At_UTC": "2026-10-07T20:00:00Z", "Byte_Count": str(len(tb)),
                   "SHA256": sh(tb), "Path": "private:m1macro_forward/treasury/t.csv", "Normal": "true"},
                  {"Run_ID": rid, "Source": "mof", "Retrieved_At_UTC": "2026-10-07T20:00:00Z", "Byte_Count": str(len(mb)),
                   "SHA256": sh(mb), "Path": "data/m1macro/mof/a.csv", "Normal": "true"},
                  {"Run_ID": rid, "Source": "mof", "Retrieved_At_UTC": "2026-10-07T20:00:00Z", "Byte_Count": str(len(mb)),
                   "SHA256": sh(mb), "Path": "data/m1macro/mof/b.csv", "Normal": "true"},
                  {"Run_ID": "C1", "Source": "cftc", "Retrieved_At_UTC": "2026-10-07T17:40:00Z", "Byte_Count": str(len(cb)),
                   "SHA256": sh(cb), "Path": "data/m1macro/cftc/s.zip", "Normal": "true"},
                  {"Run_ID": "C0", "Source": "cftc", "Retrieved_At_UTC": "2026-10-07T18:00:01Z", "Byte_Count": str(len(cb)),
                   "SHA256": "0" * 64, "Path": "data/m1macro/cftc/after_tinfo.zip", "Normal": "true"},   # after T_info: never used
                  {"Run_ID": rid, "Source": "cftc_schedule", "Retrieved_At_UTC": "2026-10-07T20:00:00Z",
                   "SHA256": sh(FIX.read_bytes()), "Path": "data/m1macro/cftc_schedule/s.html", "Normal": "true"}]
            with open(root / FR.FETCHES, "w", newline="") as f:
                w = csv.DictWriter(f, fieldnames=FR.FETCH_FIELDS, lineterminator="\n"); w.writeheader(); w.writerows(fe)
            with open(root / FR.TREASURY_MANIFEST, "w", newline="") as f:
                w = csv.DictWriter(f, fieldnames=FR.TREASURY_FIELDS, lineterminator="\n"); w.writeheader()
                w.writerow({"Retrieved_At_UTC": "2026-10-07T20:00:00Z", "SHA256": sh(tb), "Private_Path": "m1macro_forward/treasury/t.csv",
                            "Private_Commit": "c" * 40, "Byte_Count": str(len(tb))})
            # 3) compute (ctx injected to reuse the synthetic reconstruction)
            res = FR.build_rows_for_origin(D, now.astimezone(UTC), rid, manifest.code_sha256(), str(stage), None, ctx=ctx)
            res2 = FR.build_rows_for_origin(D, now.astimezone(UTC), rid, manifest.code_sha256(), str(stage), None, ctx=ctx)
            fr, er, fc = res
            assert er == res2[1] and fc == res2[2]                                          # determinism
            assert len(fr) == 1 and len(er) == 1 and len(fc) == 3
            assert fr[0]["F_US_Status"] == fr[0]["F_JP_Status"] == fr[0]["F_POS_Status"] == "OK"
            assert fr[0]["F_POS_Snapshot_SHA256"] == sh(cb) and fr[0]["F_POS_Report_Date"] == "2026-09-29"
            assert er[0]["Parameter_State"] in ("ESTIMATED", "DEFAULT_PARENT") and len(er[0]["E_Input_SHA256"]) == 64
            assert int(er[0]["N_Warmup"]) >= 250 and er[0]["N_Gap_Origins"] == "0"
            assert all(r["Decision_Class"] == "FORECAST" and r["Parent_Run_ID"] == "S0RUN" for r in fc)
            assert {r["Pair"] for r in fc} == {"USDJPY", "CHFJPY", "INRJPY"} and all(r["Beta_US"] == "" for r in fc if r["Pair"] != "USDJPY")
            # 4) transaction on the temporary repository (deadline 08:30 JST)
            tx = {"run_id": rid, "code_sha256": manifest.code_sha256(), "status": "READY",
                  "txs": [FR._tx(D.isoformat(), "1D", fr, er, fc)]}
            (stage / "tx.json").write_text(json.dumps(tx))
            from m1macro import gitrepo
            ck = ["2026-10-07T21:00:00Z", "2026-10-07T21:00:05Z"]
            st = FR.commit_tx(str(stage), gitrepo.RealGit(root, message="t"), lambda: ck.pop(0))
            assert st["status"] == "COMPLETE" and st["deadline_status"] == "ON_TIME", st
            # 5) no second issuance of the same (origin, horizon)
            assert FR.build_rows_for_origin(D, now.astimezone(UTC), rid, manifest.code_sha256(), str(stage), None, ctx=ctx) is None
            assert FR.commit_tx(str(stage), gitrepo.RealGit(root, message="t"))["status"] == "ALREADY_COMPLETE"
            # 6) after the cutoff, a due origin without COMPLETE gets ABSTAIN_SYSTEM rows (NOT_ISSUED / LATE_ISSUE)
            FR.CFG["first_forward_origin"] = {"1D": "2026-10-07", "1W": "2026-10-11", "4W": "2026-10-11"}
            ab = FR.abstain_txs(dt.datetime(2026, 10, 8, 9, 0, tzinfo=JST), rid, "c")
            assert [(t["origin"], t["horizons"]) for t in ab] == [("2026-10-07", "1D")]
            rr = base64.b64decode(ab[0]["rows"][L.FORECASTS][0])
            assert b"NOT_ISSUED" in rr and ab[0]["rows"][L.FEATURES] == []
            out.update(ok=True, parameter_state=er[0]["Parameter_State"], n_warmup=int(er[0]["N_Warmup"]))
        finally:
            FR.ROOT = old_root; FR.FC.ROOT = old_root; FR.CFG.clear(); FR.CFG.update(old_cfg); FR.run_id = old_rid
    return out
