#!/usr/bin/env python3
"""Formal forward issuance for M0-RW0 v1.2 and S0-EMPCLIM-STD-EXP-V1 (impl v1.1).

One run does, in order:
  1. Get the ECB reference-rate history (eurofxref-hist.zip) and record its SHA-256.
  2. Verify the frozen modules' SHA-256 and the configuration.
  3. For every scheduled formal origin from the pre-registered first origin up to
     today (JST):
       - today's origin, before the 08:30 JST cutoff, with the required last fix
         published  -> issue M0 and S0 forecasts (Decision_Class FORECAST / ...).
       - an origin whose cutoff has passed and that has no record
         -> ABSTAIN_SYSTEM (NOT_ISSUED / DATA_UNAVAILABLE / LATE_ISSUE).
     Forecasts are never issued for an origin whose cutoff has passed.
  4. Record outcomes (OBSERVED / UNAVAILABLE) of issued forecasts. PENDING is the
     absence of an outcome row while Target_End has not yet been published.
  5. Append rows to ledger/*.csv. Existing bytes are never changed (append-only).
  6. Write ledger/expected_this_run.json so verify.py can re-read the pushed files
     and check every key, value and timestamp (Storage Verification Gate).

Leakage guard: the ECB history is truncated to dates <= Last_Available_Fix of the
origin being issued. Data after that date can never enter a forecast.
"""
from __future__ import annotations

import argparse
import csv
import math
import datetime as dt
import io
import json
import os
import sys
import time
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ledger_builder as lb  # noqa: E402
import m1_vol_shrink_v1 as m1  # noqa: E402

ROOT = lb.ROOT
LEDGER = ROOT / "ledger"
DATA = ROOT / "data" / "ecb"
CONFIG = json.loads((ROOT / "forward" / "config.json").read_text(encoding="utf-8"))

ECB_URL = "https://www.ecb.europa.eu/stats/eurofxref/eurofxref-hist.zip"
JST = dt.timezone(dt.timedelta(hours=9))
CUTOFF = dt.time(8, 30)
HORIZONS = ("1D", "1W", "4W")

FORECAST_FIELDS = [
    "Model", "Pair", "Origin", "Horizon", "Cutoff_JST", "Last_Available_Fix", "Target_Start", "Target_End",
    "H_Canonical_Intervals", "Sigma_H", "Point_LogReturn", "P_Down", "P_Neutral", "P_Up", "PI10", "PI90",
    "Pool_N", "Mean_Z", "Q10_Z", "Q90_Z", "Sigma_Model", "W", "Parameter_State", "N_Param_Origins", "V_Long",
    "Decision_Class", "Reason_Code", "Issued_At_UTC", "Data_Zip_SHA256", "Data_Last_Date", "Code_SHA256", "Run_ID",
]
OUTCOME_FIELDS = [
    "Pair", "Origin", "Horizon", "Target_Start", "Target_End", "Realized_LogReturn", "Outcome_Status",
    "Recorded_At_UTC", "Data_Zip_SHA256", "Data_Last_Date", "Run_ID",
]
RUN_FIELDS = [
    "Run_ID", "Mode", "Started_At_UTC", "Started_At_JST", "Data_Zip_SHA256", "Data_CSV_SHA256", "Data_Last_Date",
    "Forecast_Rows", "Abstain_Rows", "Outcome_Rows", "Status", "Note",
]
MODELS = ("M0-RW0", "S0-EMPCLIM-STD-EXP-V1", "M1-VOL-SHRINK-V1")


def utc_iso(t: dt.datetime) -> str:
    return t.astimezone(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def code_sha() -> str:
    """Hash of the issuing code: frozen modules + forward runner + config."""
    parts = []
    for name in sorted(lb.FROZEN_SHA256):
        parts.append(f"{name}:{lb.sha256_file(lb.FROZEN / name)}")
    for p in ("forward/ledger_builder.py", "forward/m1_vol_shrink_v1.py", "forward/issue.py", "forward/config.json"):
        parts.append(f"{p}:{lb.sha256_file(ROOT / p)}")
    return lb.sha256_bytes("\n".join(parts).encode())


def fetch_zip(path: str | None) -> bytes:
    if path:
        return Path(path).read_bytes()
    last = None
    for attempt in range(4):
        try:
            req = urllib.request.Request(ECB_URL, headers={"User-Agent": "fx-forward-ledger/1.0"})
            with urllib.request.urlopen(req, timeout=60) as r:
                return r.read()
        except Exception as e:  # retried, then surfaced as DATA_UNAVAILABLE
            last = e
            time.sleep(15 * (attempt + 1))
    raise RuntimeError(f"ECB download failed: {last}")


def read_csv(path: Path):
    if not path.exists():
        return []
    with open(path, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def append_rows(path: Path, fields, rows):
    """Append-only write. Header is written only when the file is new."""
    if not rows:
        return
    new = not path.exists()
    before = path.read_bytes() if path.exists() else b""
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=fields, lineterminator="\n")
    if new:
        w.writeheader()
    for r in rows:
        w.writerow({k: r.get(k, "") for k in fields})
    with open(path, "ab") as f:
        f.write(buf.getvalue().encode("utf-8"))
    after = path.read_bytes()
    if not after.startswith(before):
        raise RuntimeError(f"APPEND_ONLY_VIOLATION: {path}")


def scheduled_origins(mp, first, last_date):
    """All formal origins (date, horizon) with first[h] <= date <= last_date."""
    out = []
    d = min(first.values())
    while d <= last_date:
        if d >= first["1D"] and mp.is_formal_origin(d, "1D"):
            out.append((d, "1D"))
        for h in ("1W", "4W"):
            if d >= first[h] and mp.is_formal_origin(d, h):
                out.append((d, h))
        d += dt.timedelta(days=1)
    return out


def issue_forecasts(m0, mp, s0mod, raw_all, origin, horizon, issued_m1_sigma=None):
    """Return (ledger rows, S0 rows, M1 rows, laf) for the forward origin, or raise NotReady.

    issued_m1_sigma: {(pair, origin_iso, horizon): Sigma_Model} of M1 rows already in the formal
    ledger. The prequential replay must reproduce every one of them exactly (issued sigma is
    immutable); otherwise PIPELINE_FAILURE."""
    start = mp.next_target_day_on_or_after(origin)
    laf = mp.previous_target_day(start)
    raw = [r for r in raw_all if r["Date"] <= laf]  # leakage guard
    if not raw or raw[-1]["Date"] != laf:
        raise NotReady(f"LAST_FIX_NOT_PUBLISHED laf={laf} data_last={raw_all[-1]['Date']}")
    extra = [(p, origin, horizon) for p in lb.PAIRS]
    rows = lb.build_rows(m0, mp, raw, extra_origins=extra)
    srows = lb.to_strings(rows)
    s0_out = s0mod.generate_s0(srows)
    key = {(p, origin.isoformat(), horizon) for p in lb.PAIRS}
    led = {(r["Pair"], r["Origin"], r["Horizon"]): r for r in srows if (r["Pair"], r["Origin"], r["Horizon"]) in key}
    s0r = {(r["Pair"], r["Origin"], r["Horizon"]): r for r in s0_out if (r["Pair"], r["Origin"], r["Horizon"]) in key}
    if len(led) != len(lb.PAIRS) or len(s0r) != len(lb.PAIRS):
        raise RuntimeError("PIPELINE_FAILURE: forward origin rows missing")
    rows_h = [r for r in srows if r["Horizon"] == horizon]
    m1_out, _ = m1.generate(rows_h, raw, lb.PAIRS)
    m1_all = {(r["Pair"], r["Origin"], r["Horizon"]): r for r in m1_out}
    for k, sig in (issued_m1_sigma or {}).items():
        if k[2] == horizon and k in m1_all and m1_all[k]["Sigma_M1"] != sig:
            raise RuntimeError(f"PIPELINE_FAILURE: M1_ISSUED_SIGMA_MISMATCH {k}")
    m1r = {k: m1_all[k] for k in key}
    return led, s0r, m1r, laf


class NotReady(Exception):
    pass


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["formal", "dryrun"], default="dryrun")
    ap.add_argument("--zip", help="use a local ECB zip instead of downloading (tests)")
    ap.add_argument("--now", help="override current time, ISO8601 with offset (dryrun/tests only)")
    ap.add_argument("--ledger-dir", help="ledger directory (default: ledger/ or ledger_dryrun/)")
    args = ap.parse_args()

    if args.mode == "formal" and (args.now or args.zip):
        raise SystemExit("--now/--zip are not allowed in formal mode")

    now = dt.datetime.fromisoformat(args.now) if args.now else dt.datetime.now(dt.timezone.utc)
    now_jst = now.astimezone(JST)
    run_id = os.environ.get("GITHUB_RUN_ID", "local") + "-" + os.environ.get("GITHUB_RUN_ATTEMPT", "1")
    ledger_dir = Path(args.ledger_dir) if args.ledger_dir else (LEDGER if args.mode == "formal" else ROOT / "ledger_dryrun")
    ledger_dir.mkdir(parents=True, exist_ok=True)
    f_fc, f_out, f_run = ledger_dir / "forecasts.csv", ledger_dir / "outcomes.csv", ledger_dir / "runs.csv"

    m0, mp, s0mod = lb.load_frozen()
    csha = code_sha()
    first = {h: dt.date.fromisoformat(CONFIG["first_origin"][h]) for h in HORIZONS}

    run = {"Run_ID": run_id, "Mode": args.mode, "Started_At_UTC": utc_iso(now),
           "Started_At_JST": now_jst.strftime("%Y-%m-%dT%H:%M:%S+09:00")}
    new_fc, new_out = [], []
    zip_sha = csv_sha = data_last = ""
    raw_all = None
    note = []
    try:
        zb = fetch_zip(args.zip)
        zip_sha = lb.sha256_bytes(zb)
        csv_bytes, raw_all = lb.read_ecb_zip(zb)
        csv_sha = lb.sha256_bytes(csv_bytes)
        data_last = raw_all[-1]["Date"].isoformat()
        if args.mode == "formal":
            DATA.mkdir(parents=True, exist_ok=True)
            (DATA / "eurofxref-hist.csv").write_bytes(csv_bytes)
    except Exception as e:
        note.append(f"DATA_UNAVAILABLE: {e}")

    existing = {(r["Model"], r["Pair"], r["Origin"], r["Horizon"]) for r in read_csv(f_fc)}
    existing_out = {(r["Pair"], r["Origin"], r["Horizon"]) for r in read_csv(f_out)}
    today = now_jst.date()
    issued_m1 = {(r["Pair"], r["Origin"], r["Horizon"]): r["Sigma_Model"] for r in read_csv(f_fc)
                 if r["Model"] == "M1-VOL-SHRINK-V1" and r["Decision_Class"] != "ABSTAIN_SYSTEM"}
    pipeline_failure = False

    for origin, h in scheduled_origins(mp, first, today):
        keys = [(m, p, origin.isoformat(), h) for m in MODELS for p in lb.PAIRS]
        if all(k in existing for k in keys):
            continue
        cutoff_at = dt.datetime.combine(origin, CUTOFF, tzinfo=JST)
        before_cutoff = now < cutoff_at
        reason = None
        if before_cutoff and origin == today:
            if raw_all is None:
                continue  # retry in a later run before the cutoff
            try:
                led, s0r, m1r, laf = issue_forecasts(m0, mp, s0mod, raw_all, origin, h, issued_m1)
            except NotReady as e:
                note.append(f"{origin} {h}: {e}")
                continue  # retry in a later run before the cutoff
            except RuntimeError as e:
                note.append(f"{origin} {h}: {e}")
                pipeline_failure = True
                continue
            issued_at = utc_iso(dt.datetime.now(dt.timezone.utc)) if not args.now else utc_iso(now)
            for p in lb.PAIRS:
                L = led[(p, origin.isoformat(), h)]
                S = s0r[(p, origin.isoformat(), h)]
                common = {"Pair": p, "Origin": origin.isoformat(), "Horizon": h, "Cutoff_JST": "08:30",
                          "Last_Available_Fix": L["Last_Available_Fix"], "Target_Start": L["Target_Start"],
                          "Target_End": L["Target_End"], "H_Canonical_Intervals": L["H_Canonical_Intervals"],
                          "Sigma_H": L["Sigma_H"], "Issued_At_UTC": issued_at, "Data_Zip_SHA256": zip_sha,
                          "Data_Last_Date": data_last, "Code_SHA256": csha, "Run_ID": run_id}
                m0_ok = L["Prereq_Status"] == "FORECAST_READY"
                new_fc.append({**common, "Model": "M0-RW0",
                               "Point_LogReturn": L["M0_Point_LogReturn"], "P_Down": L["M0_P_Down"],
                               "P_Neutral": L["M0_P_Neutral"], "P_Up": L["M0_P_Up"],
                               "PI10": L["M0_PI10"], "PI90": L["M0_PI90"],
                               "Decision_Class": "FORECAST" if m0_ok else "MODEL_PREREQ_UNAVAILABLE",
                               "Reason_Code": "" if m0_ok else L["Prereq_Status"]})
                new_fc.append({**common, "Model": "S0-EMPCLIM-STD-EXP-V1",
                               "Point_LogReturn": S["S0_Point_LogReturn"], "P_Down": S["P_Down"],
                               "P_Neutral": S["P_Neutral"], "P_Up": S["P_Up"], "PI10": S["PI10"], "PI90": S["PI90"],
                               "Pool_N": S["Pool_N"], "Mean_Z": S["Mean_Z"], "Q10_Z": S["Q10_Z"],
                               "Q90_Z": S["Q90_Z"], "Sigma_Model": L["Sigma_H"], "Decision_Class": S["Decision_Class"],
                               "Reason_Code": S["Reason_Code"]})
                M = m1r[(p, origin.isoformat(), h)]
                new_fc.append({**common, "Model": "M1-VOL-SHRINK-V1",
                               "Point_LogReturn": M["Point_LogReturn"], "P_Down": M["P_Down"],
                               "P_Neutral": M["P_Neutral"], "P_Up": M["P_Up"], "PI10": M["PI10"], "PI90": M["PI90"],
                               "Pool_N": M["Pool_N"], "Mean_Z": M["Mean_Z"], "Q10_Z": M["Q10_Z"], "Q90_Z": M["Q90_Z"],
                               "Sigma_Model": M["Sigma_M1"], "W": M["W"], "Parameter_State": M["Parameter_State"],
                               "N_Param_Origins": M["N_Param_Origins"], "V_Long": M["V_Long"],
                               "Decision_Class": M["Decision_Class"], "Reason_Code": M["Reason_Code"]})
            continue
        if before_cutoff:
            continue  # future origin (should not happen) - never pre-issue
        # Cutoff has passed and no record exists: system abstention, never a late forecast.
        if origin < today:
            reason = "NOT_ISSUED"
        elif raw_all is None:
            reason = "DATA_UNAVAILABLE"
        else:
            reason = "LATE_ISSUE"
        for m, p, o, hh in keys:
            if (m, p, o, hh) in existing:
                continue
            new_fc.append({"Model": m, "Pair": p, "Origin": o, "Horizon": hh, "Cutoff_JST": "08:30",
                           "Decision_Class": "ABSTAIN_SYSTEM", "Reason_Code": reason,
                           "Issued_At_UTC": utc_iso(now), "Data_Zip_SHA256": zip_sha,
                           "Data_Last_Date": data_last, "Code_SHA256": csha, "Run_ID": run_id})

    # Outcomes for issued forecasts (one outcome row per pair x origin x horizon).
    if raw_all is not None:
        pdata = lb.pair_series(raw_all)
        series_map = {p: dict(v) for p, v in pdata.items()}
        published_last = raw_all[-1]["Date"]
        all_fc = read_csv(f_fc) + new_fc
        seen = set()
        for r in all_fc:
            if r["Decision_Class"] != "FORECAST":
                continue
            k = (r["Pair"], r["Origin"], r["Horizon"])
            if k in existing_out or k in seen:
                continue
            te = dt.date.fromisoformat(r["Target_End"])
            ts = dt.date.fromisoformat(r["Target_Start"])
            if te > published_last:
                continue  # PENDING
            seen.add(k)
            series = series_map[r["Pair"]]
            if ts in series and te in series:
                val = lb.fmt(math.log(series[te] / series[ts]))
                status = "OBSERVED"
            else:
                val, status = "", "UNAVAILABLE"
            new_out.append({"Pair": r["Pair"], "Origin": r["Origin"], "Horizon": r["Horizon"],
                            "Target_Start": r["Target_Start"], "Target_End": r["Target_End"],
                            "Realized_LogReturn": val, "Outcome_Status": status,
                            "Recorded_At_UTC": utc_iso(now), "Data_Zip_SHA256": zip_sha,
                            "Data_Last_Date": data_last, "Run_ID": run_id})

    n_fc = sum(1 for r in new_fc if r["Decision_Class"] != "ABSTAIN_SYSTEM")
    n_ab = len(new_fc) - n_fc
    status = "PIPELINE_FAILURE" if pipeline_failure else ("OK" if raw_all is not None else "DATA_UNAVAILABLE")
    run.update({"Data_Zip_SHA256": zip_sha, "Data_CSV_SHA256": csv_sha, "Data_Last_Date": data_last,
                "Forecast_Rows": n_fc, "Abstain_Rows": n_ab, "Outcome_Rows": len(new_out),
                "Status": status, "Note": " | ".join(note)[:500]})

    append_rows(f_fc, FORECAST_FIELDS, new_fc)
    append_rows(f_out, OUTCOME_FIELDS, new_out)
    append_rows(f_run, RUN_FIELDS, [run])
    if args.mode == "formal" and zip_sha:
        append_rows(DATA / "snapshots.csv", ["Run_ID", "Retrieved_At_UTC", "Data_Zip_SHA256", "Data_CSV_SHA256", "Data_Last_Date"],
                    [{"Run_ID": run_id, "Retrieved_At_UTC": utc_iso(now), "Data_Zip_SHA256": zip_sha,
                      "Data_CSV_SHA256": csv_sha, "Data_Last_Date": data_last}])

    expected = {"ledger_dir": str(ledger_dir.relative_to(ROOT)) if ledger_dir.is_relative_to(ROOT) else str(ledger_dir),
                "run_id": run_id,
                "forecasts": [{k: r.get(k, "") for k in FORECAST_FIELDS} for r in new_fc],
                "outcomes": [{k: r.get(k, "") for k in OUTCOME_FIELDS} for r in new_out],
                "run": {k: str(run.get(k, "")) for k in RUN_FIELDS}}
    (ROOT / "expected_this_run.json").write_text(json.dumps(expected, ensure_ascii=False, indent=1), encoding="utf-8")
    if pipeline_failure:
        print("PIPELINE_FAILURE: " + run["Note"], file=sys.stderr)
    print(json.dumps({"run_id": run_id, "mode": args.mode, "now_jst": run["Started_At_JST"], "data_last": data_last,
                      "forecast_rows": n_fc, "abstain_rows": n_ab, "outcome_rows": len(new_out), "note": run["Note"]},
                     ensure_ascii=False))
    if pipeline_failure:
        sys.exit(1)


if __name__ == "__main__":
    main()
