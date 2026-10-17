#!/usr/bin/env python3
"""Build a forecast-ready formal ledger without conflating forecast issuance with outcome availability.

Inputs in same directory:
  eurofxref-hist.zip
  m0_walkforward_v1_2.py
  origin_target_map_v1.py

This wrapper does NOT modify M0 E2E v1.1.  It is an operational/evaluation
ledger builder added after the M0 E2E package was closed.

Key rule:
- Prereq_Status tells whether a forecast can be issued at Origin.
- Outcome_Status tells whether the realized target outcome is already observable.
- A row may therefore be FORECAST_READY + PENDING.
"""
from __future__ import annotations
from pathlib import Path
import csv, io, zipfile, hashlib, math, datetime as dt, importlib.util, sys

BASE=Path(__file__).resolve().parent
ZIP=BASE/"eurofxref-hist.zip"
M0=BASE/"m0_walkforward_v1_2.py"
MAP=BASE/"origin_target_map_v1.py"

EXPECTED_ZIP="f36e0affc225bc572cc589d4183352c5815f178769f04c2b27a452567c6f7649"
EXPECTED_M0="4ca2f37ab729d08f24f008d75c5ceb95f11d79d5bf9575941f44ffd32a77e3d5"
EXPECTED_MAP="902f0b43a84a0ec309a6e99b6617ca2816e240054bd77e9dbf7d3b2812f3c988"

FIELDS=[
 "Pair","Origin","Cutoff_JST","Horizon","Last_Available_Fix","Target_Start","Ideal_Target_End","Target_End",
 "H_Canonical_Intervals","EWMA_Var_1","Sigma_H","M0_Point_LogReturn","M0_P_Down","M0_P_Neutral","M0_P_Up",
 "M0_PI10","M0_PI90","Realized_LogReturn","Normalized_Error","Abs_Error","Prereq_Status","Outcome_Status"
]

def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def load(name,p):
    spec=importlib.util.spec_from_file_location(name,p)
    mod=importlib.util.module_from_spec(spec); sys.modules[name]=mod; spec.loader.exec_module(mod); return mod

def num(x):
    x=(x or "").strip()
    return None if not x or x=="N/A" else float(x)

def fmt(v):
    if isinstance(v,dt.date): return v.isoformat()
    if isinstance(v,float): return format(v,".17g")
    if v is None: return ""
    return v

def main():
    if sha(ZIP)!=EXPECTED_ZIP: raise RuntimeError("ECB ZIP SHA mismatch")
    if sha(M0)!=EXPECTED_M0: raise RuntimeError("M0 SHA mismatch")
    if sha(MAP)!=EXPECTED_MAP: raise RuntimeError("MAP SHA mismatch")
    m0=load("m0_forecast_ledger",M0)
    mp=load("map_forecast_ledger",MAP)

    with zipfile.ZipFile(ZIP) as z:
        if z.testzip() is not None: raise RuntimeError("ZIP CRC failure")
        text=z.read("eurofxref-hist.csv").decode("utf-8-sig")
    rdr=csv.DictReader(io.StringIO(text))
    cols=[c for c in (rdr.fieldnames or []) if c]
    raw=[]
    for r in rdr:
        d=dt.date.fromisoformat(r["Date"])
        raw.append({c:(d if c=="Date" else num(r.get(c,""))) for c in cols})
    raw.sort(key=lambda r:r["Date"])
    obs=[r["Date"] for r in raw]
    defs={"USDJPY":("JPY","USD"),"CHFJPY":("JPY","CHF"),"INRJPY":("JPY","INR")}
    pdata={p:[] for p in defs}
    for r in raw:
        for p,(a,b) in defs.items():
            if r[a] is not None and r[b] is not None:
                pdata[p].append((r["Date"],r[a]/r[b]))

    rows=[]
    for pair,vals in pdata.items():
        dates=[d for d,_ in vals]; rates=[v for _,v in vals]; pos={d:i for i,d in enumerate(dates)}
        def one(origin,horizon):
            if mp.next_target_day_on_or_after(origin)<dates[0]:
                return {"Pair":pair,"Origin":origin,"Horizon":horizon,"Prereq_Status":"PRE_LISTING","Outcome_Status":"NOT_APPLICABLE"}
            if origin==obs[0] and horizon=="1D":
                return {"Pair":pair,"Origin":origin,"Horizon":horizon,"Prereq_Status":"PRE_SCOPE","Outcome_Status":"NOT_APPLICABLE"}
            z=mp.map_origin(origin,horizon)
            base={"Pair":pair,"Origin":origin,"Cutoff_JST":"08:30","Horizon":horizon,
                  "Last_Available_Fix":z.last_available_fix,"Target_Start":z.target_start,
                  "Ideal_Target_End":z.ideal_target_end,"Target_End":z.target_end,
                  "H_Canonical_Intervals":z.h_canonical_intervals}
            if z.last_available_fix not in pos:
                if z.last_available_fix<dates[0]:
                    return {**base,"Prereq_Status":"PRE_LISTING","Outcome_Status":"NOT_APPLICABLE"}
                return {**base,"Prereq_Status":"PAIR_COMPONENT_GAP","Outcome_Status":"UNAVAILABLE"}
            j=pos[z.last_available_fix]
            realized=None; outcome="PENDING"
            if z.target_start in pos and z.target_end in pos:
                s=pos[z.target_start]; e=pos[z.target_end]
                if s!=j+1: raise RuntimeError("ORIGIN_START_ADJACENCY_FAIL")
                realized=math.log(rates[e]/rates[s]); outcome="OBSERVED"
            if j<252:
                return {**base,"Realized_LogReturn":realized,
                        "Prereq_Status":"M0_VOL_WARMUP_INSUFFICIENT","Outcome_Status":outcome}
            hr=rates[j-252:j+1]
            rets=[math.log(hr[k+1]/hr[k]) for k in range(252)]
            v=m0.finite_ewma_variance(rets)
            sig=m0.sigma_h_from_variance(v,z.h_canonical_intervals)
            pd,pn,pu=m0.m0_category_probabilities(0.25,sig)
            lo,hi=m0.prediction_interval(sig,coverage=0.80)
            return {**base,"EWMA_Var_1":v,"Sigma_H":sig,"M0_Point_LogReturn":0.0,
                    "M0_P_Down":pd,"M0_P_Neutral":pn,"M0_P_Up":pu,"M0_PI10":lo,"M0_PI90":hi,
                    "Realized_LogReturn":realized,
                    "Normalized_Error":None if realized is None or sig==0 else realized/sig,
                    "Abs_Error":None if realized is None else abs(realized),
                    "Prereq_Status":"FORECAST_READY","Outcome_Status":outcome}
        for d in obs: rows.append(one(d,"1D"))
        d=obs[0]
        while d.weekday()!=6: d+=dt.timedelta(days=1)
        while d<=obs[-1]:
            rows.append(one(d,"1W")); rows.append(one(d,"4W")); d+=dt.timedelta(days=7)

    out=BASE/"formal_forecast_ledger_v1.csv"
    with out.open("w",encoding="utf-8-sig",newline="") as f:
        w=csv.DictWriter(f,fieldnames=FIELDS); w.writeheader()
        for r in rows: w.writerow({k:fmt(r.get(k,"")) for k in FIELDS})
    print(f"rows={len(rows)}")
    print(f"sha256={sha(out)}")
if __name__=="__main__":
    main()
