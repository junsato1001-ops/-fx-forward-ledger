"""Synthetic tests: CFTC Snapshot Gate ordering; data fetched after T_info never enters (むすび 19:48)."""
import datetime as dt

from m1macro import cftc_feature as F, cftc_rules as R
from m1macro.tz import JST, UTC

D = dt.date


def T(y, m, d, hh, mm):
    return dt.datetime(y, m, d, hh, mm, tzinfo=JST).astimezone(UTC)


def rep(d, l, s, oi):
    return F.Report(d, l, s, oi)


def run():
    out = {}
    tues = [D(2026, 9, 22), D(2026, 9, 29), D(2026, 10, 6), D(2026, 10, 13)]
    hist = {d: rep(d, 100 + i, 50, 1000) for i, d in enumerate(tues)}
    sched = [R.expected_release(d) for d in tues] + [R.expected_release(D(2026, 10, 20))]
    origin = D(2026, 10, 13); tinfo = T(2026, 10, 13, 3, 0)     # Tue 03:00 JST; report 10-06 released Sat 10-10 04:30 JST
    pre = F.Snapshot(T(2026, 10, 13, 2, 40), "pre", True, {d: hist[d] for d in tues[:3]})
    post = F.Snapshot(T(2026, 10, 13, 4, 40), "post", True, {d: rep(d, 999, 1, 1000) for d in tues})   # different values
    # (a) normal: pre-T_info snapshot used, values from it
    r = F.forward(origin, tinfo, [pre, post], sched)
    assert r.status == "OK" and r.report_date == D(2026, 10, 6) and r.snapshot_sha256 == "pre" and r.value == (102 - 50) / 1000
    # (b) only post-T_info snapshot -> ABSTAIN, never the post data
    r = F.forward(origin, tinfo, [post], sched)
    assert r.status == "ABSTAIN_SYSTEM" and r.subreason == "CFTC_PRE_TINFO_SNAPSHOT_UNAVAILABLE" and r.value is None
    # (c) snapshot of a previous origin (outside the 6 h window) -> ABSTAIN, no fallback
    old = F.Snapshot(T(2026, 10, 12, 2, 40), "old", True, pre.reports)
    r = F.forward(origin, tinfo, [old, post], sched)
    assert r.status == "ABSTAIN_SYSTEM" and r.snapshot_sha256 == ""
    # (d) abnormal pre snapshot only -> ABSTAIN
    bad = F.Snapshot(T(2026, 10, 13, 2, 40), "bad", False, pre.reports)
    assert F.forward(origin, tinfo, [bad, post], sched).status == "ABSTAIN_SYSTEM"
    # (e) report released after T_info is in the post file but never used even if rules say Usable_From <= T_info
    weird = F.Snapshot(T(2026, 10, 13, 2, 40), "pre2", True, {d: hist[d] for d in tues[:2]})   # 10-06 not yet in pre file
    r = F.forward(origin, tinfo, [weird, post], sched)
    assert r.report_date == D(2026, 9, 29) and r.status == "MODEL_PREREQ_UNAVAILABLE" and r.reason == "FEATURE_STALE"
    # (f) schedule unavailable -> ABSTAIN
    assert F.forward(origin, tinfo, [pre], None).subreason == "CFTC_RELEASE_SCHEDULE_UNAVAILABLE"
    # (g) OI zero / missing
    z = F.Snapshot(T(2026, 10, 13, 1, 0), "z", True, {**pre.reports, D(2026, 10, 6): rep(D(2026, 10, 6), 1, 1, 0)})
    assert F.forward(origin, tinfo, [z], sched).subreason == "TOTAL_OI_ZERO"
    # historical path: availability start, 2013 shutdown staleness, 2018-19 exclusion
    assert F.historical(D(2010, 12, 7), T(2010, 12, 7, 3, 0), hist).reason == "FEATURE_NOT_YET_AVAILABLE"
    h13 = {d: rep(d, 1, 0, 10) for d in (D(2013, 9, 24), D(2013, 10, 1), D(2013, 10, 8))}
    r = F.historical(D(2013, 10, 6), T(2013, 10, 6, 3, 0), h13)
    assert r.report_date == D(2013, 9, 24) and r.reason == "FEATURE_STALE"
    h18 = {d: rep(d, 1, 0, 10) for d in (D(2018, 12, 18), D(2018, 12, 24), D(2019, 1, 1))}
    r = F.historical(D(2019, 1, 6), T(2019, 1, 6, 3, 0), h18)
    assert r.report_date == D(2018, 12, 18) and r.reason == "FEATURE_GATE_EXCLUDED"
    out["ok"] = True
    return out
