"""F_POS selection (Transform 1 §2, Transform 2-A §2.3, Impl Part 1 V1.1 §2.3, §2.3.1).

Forward order (V1.1): pre-T_info snapshot -> timestamp/SHA/normality -> Snapshot Gate -> report choice -> F_POS.
Values are always read from the chosen pre-T_info snapshot; data fetched after T_info never enters.
"""
import datetime as dt
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from m1macro import cftc_rules as R

WINDOW = dt.timedelta(hours=6)


@dataclass(frozen=True)
class Report:
    report_date: dt.date
    long: int
    short: int
    oi: Optional[int]


@dataclass
class Snapshot:
    retrieved_at_utc: dt.datetime
    sha256: str
    normal: bool                       # Impl Part 1 §1.1 checks passed
    reports: Dict[dt.date, Report] = field(default_factory=dict)


@dataclass
class FPos:
    status: str                        # OK / MODEL_PREREQ_UNAVAILABLE / ABSTAIN_SYSTEM
    reason: str = ""
    subreason: str = ""
    value: Optional[float] = None
    report_date: Optional[dt.date] = None
    usable_from: Optional[dt.datetime] = None
    expected_release: Optional[dt.datetime] = None
    snapshot_sha256: str = ""
    snapshot_retrieved_at: Optional[dt.datetime] = None


def _value(rep: Report, out: FPos) -> FPos:
    if rep.oi is None:
        out.status, out.reason, out.subreason = "MODEL_PREREQ_UNAVAILABLE", "FEATURE_NOT_COMPUTABLE", "TOTAL_OI_MISSING"
        return out
    if rep.oi == 0:
        out.status, out.reason, out.subreason = "MODEL_PREREQ_UNAVAILABLE", "FEATURE_NOT_COMPUTABLE", "TOTAL_OI_ZERO"
        return out
    out.value = float(rep.long - rep.short) / float(rep.oi)
    out.status = "OK"
    return out


def _choose(dates: List[dt.date], tinfo: dt.datetime):
    usable = [d for d in dates if (u := R.usable_from(d)[0]) is not None and u <= tinfo]
    return max(usable) if usable else None


def historical(origin: dt.date, tinfo: dt.datetime, reports: Dict[dt.date, Report]) -> FPos:
    """Past reconstruction: rules 1-5 only (no snapshots existed)."""
    if origin < R.TFF_FIRST_ORIGIN:
        return FPos("MODEL_PREREQ_UNAVAILABLE", "FEATURE_NOT_YET_AVAILABLE")
    dates = sorted(reports)
    k = _choose(dates, tinfo)
    if k is None:
        return FPos("MODEL_PREREQ_UNAVAILABLE", "FEATURE_STALE", "NO_USABLE_REPORT")
    out = FPos("", report_date=k, usable_from=R.usable_from(k)[0], expected_release=R.expected_release(k))
    later = [d for d in dates if d > k]
    if later:
        nxt = later[0]
        u_n = R.usable_from(nxt)[0]
        if R.expected_release(nxt) <= tinfo:
            if u_n is None:
                out.status, out.reason = "MODEL_PREREQ_UNAVAILABLE", "FEATURE_GATE_EXCLUDED"
                return out
            if tinfo < u_n:
                out.status, out.reason, out.subreason = "MODEL_PREREQ_UNAVAILABLE", "FEATURE_STALE", "CFTC_EXPECTED_RELEASE_PASSED"
                return out
    return _value(reports[k], out)


def forward(origin: dt.date, tinfo: dt.datetime, snapshots: List[Snapshot], schedule: Optional[List[dt.datetime]]) -> FPos:
    """Forward: CFTC Forward Snapshot Gate (V1.1 §2.3.1). schedule = official release times (UTC) or None if
    the official schedule could not be fetched/parsed."""
    if origin < R.TFF_FIRST_ORIGIN:
        return FPos("MODEL_PREREQ_UNAVAILABLE", "FEATURE_NOT_YET_AVAILABLE")
    cands = [s for s in snapshots if s.normal and tinfo - WINDOW < s.retrieved_at_utc <= tinfo]
    if not cands:
        return FPos("ABSTAIN_SYSTEM", "FEATURE_UNAVAILABLE", "CFTC_PRE_TINFO_SNAPSHOT_UNAVAILABLE")
    snap = max(cands, key=lambda s: (s.retrieved_at_utc, s.sha256))
    if schedule is None:
        return FPos("ABSTAIN_SYSTEM", "FEATURE_UNAVAILABLE", "CFTC_RELEASE_SCHEDULE_UNAVAILABLE",
                    snapshot_sha256=snap.sha256, snapshot_retrieved_at=snap.retrieved_at_utc)
    k = _choose(sorted(snap.reports), tinfo)
    if k is None:
        return FPos("MODEL_PREREQ_UNAVAILABLE", "FEATURE_STALE", "NO_USABLE_REPORT",
                    snapshot_sha256=snap.sha256, snapshot_retrieved_at=snap.retrieved_at_utc)
    out = FPos("", report_date=k, usable_from=R.usable_from(k)[0], expected_release=R.expected_release(k),
               snapshot_sha256=snap.sha256, snapshot_retrieved_at=snap.retrieved_at_utc)
    nxt = [t for t in schedule if t > out.expected_release]
    if nxt and min(nxt) <= tinfo:
        out.status, out.reason, out.subreason = "MODEL_PREREQ_UNAVAILABLE", "FEATURE_STALE", "CFTC_EXPECTED_RELEASE_PASSED"
        return out
    return _value(snap.reports[k], out)
