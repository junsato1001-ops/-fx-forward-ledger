"""Blind gate runner on real data (Impl Part 4 §5: G5-G9). Writes ONLY the permitted fields.

Sealed values (beta, its sign, mu, J*/UB, CRPS, forecasts, M1-S0 differences) are never written, printed or put in
exception text. Every record passes through _emit(), which rejects any key outside the allow-list. Exceptions are
reduced to their type name. stdout/stderr of this process are discarded by the workflow.

usage: gates.py g5 <out> <manifest> <public_dir> <private_dir>
       gates.py g678 <out> <manifest> <public_dir> <private_dir> <shard> <n_shards> <run_label>
       gates.py aggregate <out> <dir_with_shard_outputs>
"""
import json
import math
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

ALLOWED_G6 = {"t", "h", "state", "subreason", "stage1_iter", "stage2_iter", "ub_minus_lb", "phi2_minus_lb",
              "indep_method", "indep_iter", "indep_gap", "d_UB", "d_beta_inf", "d_mu_over_sigma",
              "pass_checks", "pass_UB", "pass_beta", "pass_mu", "pass_all", "error_type", "sec"}
ALLOWED_HASH = {"t", "h", "e_sha256", "beta_sha256", "state"}         # artifact only; compared, never committed
ALLOWED_G8 = {"t", "h", "n_mu_zero_rows", "n_match", "n_mismatch"}
EPS = 1e-13


def th_keyset(keys):
    """F7-a (むすび 2026-10-19): uniqueness of the (t, h) universe, checked without deduplication or repair.
    keys: every (t, h) occurrence, duplicates included. Returns counts and the SHA-256 of the sorted distinct keys
    (dates and horizons only)."""
    import hashlib
    ks = [(str(t), str(h)) for t, h in keys]
    u = sorted(set(ks))
    return {"n": len(ks), "n_unique": len(u), "n_duplicate": len(ks) - len(u),
            "sha256": hashlib.sha256("".join(f"{t}|{h}\n" for t, h in u).encode("utf-8")).hexdigest()}


def _emit(fh, rec, allowed):
    bad = set(rec) - allowed
    if bad:
        raise RuntimeError("emit: field not permitted")
    fh.write(json.dumps(rec, sort_keys=True) + "\n")


def _ctx(manifest, pub, priv, td):
    from m1macro import pipeline
    us, jp, reports, _ = pipeline.load_dev_snapshot(manifest, pub, priv)
    return pipeline.Context(td, us, jp, reports), (us, jp, reports)


def g5(out, manifest, pub, priv):
    """Features and calendars (values allowed, Part 1 §9)."""
    from m1macro import features, pipeline, rates, jpcal, uscal
    from m1macro.estimation import HOLDOUT_PAIRS
    import datetime as dt
    us, jp, reports, man = pipeline.load_dev_snapshot(manifest, pub, priv)
    with tempfile.TemporaryDirectory() as td:
        ctx = pipeline.Context(td, us, jp, reports)
    rows = []
    for o in sorted(ctx.feats):
        fus, fjp, fpos = ctx.feats[o]["_obj"]
        r = features.feature_row(dt.date.fromisoformat(o), fus, fjp, fpos, reports, {}, "", "", "")
        r["F_US_Raw"] = r["F_US_Raw_Lag"] = "PRIVATE_SOURCE"      # Treasury raw values are not republished in bulk (Part 1 §4)
        rows.append(r)
    import csv
    with open(Path(out, "g5_features_reconstruction.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=features.FEATURE_FIELDS, lineterminator="\n"); w.writeheader(); w.writerows(rows)
    summ = {}
    for k in ("F_US", "F_JP", "F_POS"):
        c = {}
        for r in rows:
            key = r[f"{k}_Status"] + ("/" + r[f"{k}_Reason"] if r[f"{k}_Reason"] else "") + \
                  ("/" + r[f"{k}_Subreason"] if r[f"{k}_Subreason"] else "")
            c[key] = c.get(key, 0) + 1
        summ[k] = c
    lo, hi = min(us), max(us)
    an_us = rates.calendar_anomalies(list(us), uscal.is_treasury_expected_business_day, max(lo, dt.date(2010, 1, 1)), hi)
    an_jp = rates.calendar_anomalies(list(jp), jpcal.is_expected_business_day, max(min(jp), dt.date(2026, 1, 1)), max(jp))   # JP expected calendar: forward years >= 2026
    res = {"gate": "G5", "n_origins": len(rows), "status_counts": summ,
           "treasury": {"n_dates": len(us), "min": str(lo), "max": str(hi)},
           "mof": {"n_dates": len(jp), "min": str(min(jp)), "max": str(max(jp))},
           "cftc": {"n_reports": len(reports), "min": str(min(reports)), "max": str(max(reports))},
           "calendar_anomalies_us_since_2010": len(an_us), "calendar_anomalies_jp_since_2026": len(an_jp),
           "anomalies_us_sample": [str(a) for a in an_us[:40]], "anomalies_jp_sample": [str(a) for a in an_jp[:40]],
           "n_th": {h: sum(1 for x in ctx.th if x[1] == h) for h in pipeline.HORIZONS},
           "th_universe": th_keyset((x[0], x[1]) for x in ctx.th),       # F7-a: expected universe itself unique
           "n_static_groups": {h: len(v) for h, v in ctx.recs.items()},
           "holdout_rows": sum(1 for k in list(ctx.opp) + list(ctx.s0) if k[0] in HOLDOUT_PAIRS)}
    Path(out, "g5_summary.json").write_text(json.dumps(res, indent=1, sort_keys=True), encoding="utf-8")


def g678(out, manifest, pub, priv, shard, n_shards, label):
    from m1macro import canon, estimation as E, indep
    from m1macro.forecast import forecast_fields, mu as mu_fn, n_of
    shard, n_shards = int(shard), int(n_shards)
    out = Path(out); out.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as td:
        ctx, _ = _ctx(manifest, pub, priv, td)
    mine = [x for i, x in enumerate(ctx.th) if i % n_shards == shard]
    lim = int(__import__("os").environ.get("M1_GATE_LIMIT", "0"))      # smoke tests only
    if lim:
        mine = mine[-lim:]
    cache = {h: {} for h in ("1D", "1W", "4W")}
    f6 = open(out / f"g6_{label}_{shard}.jsonl", "w"); fh = open(out / f"hash_{label}_{shard}.jsonl", "w")
    f8 = open(out / f"g8_{label}_{shard}.jsonl", "w")
    for t, h, laf in mine:
        t0 = time.time(); rec = {"t": t, "h": h}
        try:
            el = ctx.eligible_pairs(t, h)
            if not el:
                rec["state"] = "NOT_EVALUATED"
                _emit(fh, {"t": t, "h": h, "state": "NOT_EVALUATED", "e_sha256": "", "beta_sha256": ""}, ALLOWED_HASH)
                _emit(f6, rec, ALLOWED_G6); continue
            e = ctx.e_input(t, h, laf)
            est = E.estimate(e, True, cache[h])
            rec["state"] = est.state; rec["subreason"] = est.subreason
            bb = canon.beta_bytes(t, h, est.state, est.beta if est.beta is not None else None)
            _emit(fh, {"t": t, "h": h, "state": est.state, "e_sha256": e.e_sha256,
                       "beta_sha256": canon.sha256_hex(bb)}, ALLOWED_HASH)
            if est.state == "ESTIMATED" and label == "A":          # run B: production only (G7 replicate)
                r = est.result
                rec.update(stage1_iter=r.stage1_iter, stage2_iter=r.stage2_iter, ub_minus_lb=r.ub_minus_lb,
                           phi2_minus_lb=r.phi2_minus_lb)
                feats = ctx.feats[t]
                xs = [((float(feats["US"][3]) if p == "USDJPY" else 0.0), float(feats["JP"][3]), float(feats["POS"][3]))
                      for p in el]
                sg = [float(ctx.s0[(p, t, h)]["Sigma_H"]) for p in el]
                c = indep.compare(E.solver_groups(e, cache[h]), r, xs, sg)
                pc = abs(r.ub_minus_lb) <= EPS and abs(r.phi2_minus_lb) <= EPS and c["pass_gap"]
                rec.update(indep_method=c["method"], indep_iter=c["iterations"], indep_gap=c["indep_gap"], d_UB=c["d_UB"],
                           d_beta_inf=c["d_beta_inf"], d_mu_over_sigma=c["d_mu_over_sigma"], pass_checks=bool(pc),
                           pass_UB=c["pass_UB"], pass_beta=c["pass_beta"], pass_mu=c["pass_mu"],
                           pass_all=bool(pc and c["pass_UB"] and c["pass_beta"] and c["pass_mu"]))
            if est.state in ("ESTIMATED", "DEFAULT_PARENT") and label == "A":
                nz = nm = nmm = 0
                for p in el:
                    m = mu_fn(p, est.beta, {k: ctx.feats[t][k][3] for k in n_of(p)})
                    if m == 0.0:
                        nz += 1
                        s = ctx.s0[(p, t, h)]
                        f = forecast_fields(s, m, None)
                        ok = all(f[a] == s[b] for a, b in (("Point_LogReturn", "S0_Point_LogReturn"), ("PI10", "PI10"),
                                 ("PI90", "PI90"), ("P_Down", "P_Down"), ("P_Neutral", "P_Neutral"), ("P_Up", "P_Up")))
                        nm += ok; nmm += (not ok)
                _emit(f8, {"t": t, "h": h, "n_mu_zero_rows": nz, "n_match": nm, "n_mismatch": nmm}, ALLOWED_G8)
        except Exception as ex:                        # type name only: messages may quote values
            rec["error_type"] = type(ex).__name__
        rec["sec"] = round(time.time() - t0, 2)
        _emit(f6, rec, ALLOWED_G6)
    for f in (f6, fh, f8):
        f.close()


def shardsum(tmp, out, shard):
    """Inside the container: G7 counts from the two runs' hashes (hash files stay in the container's /tmp)."""
    tmp = Path(tmp); out = Path(out); out.mkdir(parents=True, exist_ok=True)
    ra = [json.loads(l) for l in open(tmp / f"hash_A_{shard}.jsonl")]
    rb = [json.loads(l) for l in open(tmp / f"hash_B_{shard}.jsonl")]
    ha = {(r["t"], r["h"]): r for r in ra}
    hb = {(r["t"], r["h"]): r for r in rb}
    keys = set(ha) | set(hb)
    res = {"shard": int(shard), "n_keys": len(keys), "n_run_A": len(ha), "n_run_B": len(hb),
           "n_rows_A": len(ra), "n_rows_B": len(rb),                    # F7-a: rows, before any keying
           "e_input_sha_mismatch": sum(1 for k in keys if k not in ha or k not in hb or ha[k]["e_sha256"] != hb[k]["e_sha256"]),
           "beta_sha_or_state_mismatch": sum(1 for k in keys if k not in ha or k not in hb
                                             or ha[k]["beta_sha256"] != hb[k]["beta_sha256"] or ha[k]["state"] != hb[k]["state"])}
    (out / f"g7_{shard}.json").write_text(json.dumps(res, sort_keys=True))
    for name in (f"g6_A_{shard}.jsonl", f"g8_A_{shard}.jsonl"):
        (out / name).write_bytes((tmp / name).read_bytes())


def aggregate(out, d):
    d = Path(d); out = Path(out)
    g6 = [json.loads(l) for p in sorted(d.glob("g6_A_*.jsonl")) for l in open(p)]
    g8 = [json.loads(l) for p in sorted(d.glob("g8_A_*.jsonl")) for l in open(p)]
    g7 = [json.loads(p.read_text()) for p in sorted(d.glob("g7_*.json"))]
    st = {}
    for r in g6:
        st[(r["h"], r.get("state", "ERROR"))] = st.get((r["h"], r.get("state", "ERROR")), 0) + 1
    est = [r for r in g6 if r.get("state") == "ESTIMATED"]
    def mx(k):
        v = [abs(r[k]) for r in est if k in r]
        return max(v) if v else None
    def mn(k):
        v = [r[k] for r in est if k in r]
        return min(v) if v else None
    res = {"G6": {"n_th": len(g6), "th_keyset": th_keyset((r["t"], r["h"]) for r in g6), "state_counts": {f"{h}/{s}": n for (h, s), n in sorted(st.items())},
                  "errors": sum(1 for r in g6 if "error_type" in r),
                  "error_types": sorted({r["error_type"] for r in g6 if "error_type" in r}),
                  "subreasons": sorted({r["subreason"] for r in g6 if r.get("subreason")}),
                  "n_estimated": len(est), "n_pass_all": sum(1 for r in est if r.get("pass_all")),
                  "max_abs_ub_minus_lb": mx("ub_minus_lb"), "min_ub_minus_lb": mn("ub_minus_lb"),
                  "max_abs_phi2_minus_lb": mx("phi2_minus_lb"), "min_phi2_minus_lb": mn("phi2_minus_lb"),
                  "max_indep_gap": mx("indep_gap"), "max_d_UB": mx("d_UB"), "max_d_beta_inf": mx("d_beta_inf"),
                  "max_d_mu_over_sigma": mx("d_mu_over_sigma"),
                  "max_stage1_iter": max((r["stage1_iter"] for r in est), default=None),
                  "max_stage2_iter": max((r["stage2_iter"] for r in est), default=None),
                  "total_sec": round(sum(r.get("sec", 0) for r in g6), 1)},
           "G7": {"n_shards": len(g7), "n_keys": sum(x["n_keys"] for x in g7), "n_run_A": sum(x["n_run_A"] for x in g7),
                  "n_run_B": sum(x["n_run_B"] for x in g7),
                  "n_rows_A": sum(x["n_rows_A"] for x in g7), "n_rows_B": sum(x["n_rows_B"] for x in g7),
                  "e_input_sha_mismatch": sum(x["e_input_sha_mismatch"] for x in g7),
                  "beta_sha_or_state_mismatch": sum(x["beta_sha_or_state_mismatch"] for x in g7)},
           "G8": {"n_mu_zero_rows": sum(r["n_mu_zero_rows"] for r in g8), "n_match": sum(r["n_match"] for r in g8),
                  "n_mismatch": sum(r["n_mismatch"] for r in g8)}}
    (out / "g678_summary.json").write_text(json.dumps(res, indent=1, sort_keys=True), encoding="utf-8")
    with open(out / "g6_records.jsonl", "w") as f:              # permitted fields only
        for r in sorted(g6, key=lambda r: (r["h"], r["t"])):
            _emit(f, r, ALLOWED_G6)


if __name__ == "__main__":
    cmd = sys.argv[1]
    {"g5": g5, "g678": g678, "shardsum": shardsum, "aggregate": aggregate}[cmd](*sys.argv[2:])
