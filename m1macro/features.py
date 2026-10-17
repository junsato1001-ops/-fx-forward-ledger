"""Per-origin feature rows (Impl Part 3 §6.1) and the point-in-time feature table used by E_{t,h} (Part 3 §4)."""
import datetime as dt
from typing import Dict, Iterable, Optional

from m1macro import cftc_feature, rates
from m1macro.forecast import f17
from m1macro.tz import JST, UTC

from m1macro.schema import FEATURE_FIELDS  # noqa: E402,F401


def tinfo_utc(origin: dt.date) -> dt.datetime:
    return dt.datetime(origin.year, origin.month, origin.day, 3, 0, 0, tzinfo=JST).astimezone(UTC)


def utc_s(t: Optional[dt.datetime]) -> str:
    return "" if t is None else t.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _d(x):
    return "" if x is None else x.isoformat()


def _num(x):
    return "" if x is None else f17(x)


def state(f) -> tuple:
    return (f.status, f.reason, f.subreason, f.value if f.status == "OK" else None)


def feature_row(origin: dt.date, fus, fjp, fpos, reports: Dict, sources: Dict[str, dict], anomalies: str,
                code_sha: str, run_id: str) -> dict:
    r = {"Origin": origin.isoformat(), "T_info_UTC": utc_s(tinfo_utc(origin)), "Calendar_Anomalies": anomalies,
         "Code_SHA256": code_sha, "Run_ID": run_id}
    for k, f in (("F_US", fus), ("F_JP", fjp)):
        r.update({k: _num(f.value if f.status == "OK" else None), f"{k}_Status": f.status, f"{k}_Reason": f.reason,
                  f"{k}_Subreason": f.subreason, f"{k}_Date": _d(f.date), f"{k}_Lag_Date": _d(f.date_lag),
                  f"{k}_Raw": f.raw, f"{k}_Raw_Lag": f.raw_lag, f"{k}_Expected_Date": _d(f.expected_date),
                  f"{k}_Stale_Days": str(f.stale_days)})
    rep = reports.get(fpos.report_date) if fpos.report_date else None
    r.update({"F_POS": _num(fpos.value if fpos.status == "OK" else None), "F_POS_Status": fpos.status,
              "F_POS_Reason": fpos.reason, "F_POS_Subreason": fpos.subreason,
              "F_POS_Report_Date": _d(fpos.report_date), "F_POS_Usable_From_UTC": utc_s(fpos.usable_from),
              "F_POS_Expected_Release_UTC": utc_s(fpos.expected_release),
              "F_POS_Long": "" if rep is None else str(rep.long), "F_POS_Short": "" if rep is None else str(rep.short),
              "F_POS_Total_OI": "" if rep is None or rep.oi is None else str(rep.oi),
              "F_POS_Snapshot_Retrieved_At_UTC": utc_s(fpos.snapshot_retrieved_at), "F_POS_Snapshot_SHA256": fpos.snapshot_sha256})
    for pre, src in (("Treasury", "treasury"), ("MOF", "mof"), ("CFTC", "cftc")):
        s = sources.get(src, {})
        r[f"{pre}_Retrieved_At_UTC"] = s.get("retrieved_at_utc", ""); r[f"{pre}_Bytes"] = str(s.get("bytes", ""))
        r[f"{pre}_SHA256"] = s.get("sha256", "")
        r[f"{pre}_Private_Path" if pre == "Treasury" else f"{pre}_Path"] = s.get("path", "")
    return r


def historical_table(origins: Iterable[dt.date], us: Dict, jp: Dict, reports: Dict) -> Dict[str, dict]:
    """Past reconstruction from the development snapshot, each origin under its own T_info rules (Part 3 §4).
    Returns {origin_iso: {"US": state, "JP": state, "POS": state, "_obj": (fus, fjp, fpos)}}."""
    out = {}
    for o in sorted(set(origins)):
        fus = rates.f_us(o, us, forward=False)
        fjp = rates.f_jp(o, jp, forward=False)
        fpos = cftc_feature.historical(o, tinfo_utc(o), reports)
        out[o.isoformat()] = {"US": state(fus), "JP": state(fjp), "POS": state(fpos), "_obj": (fus, fjp, fpos)}
    return out
