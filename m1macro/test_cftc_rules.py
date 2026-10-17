"""Synthetic/rule tests for the U.S. holiday calendar and CFTC publication-time rules."""
import datetime as dt

from m1macro import cftc_rules as C, uscal
from m1macro.tz import JST, UTC

D = dt.date


def run():
    r = {}
    # holidays
    assert uscal.is_holiday(D(2021, 6, 18)) and not uscal.is_holiday(D(2020, 6, 19))
    assert uscal.is_holiday(D(2021, 12, 31))          # New Year 2022 (Sat) observed Fri 2021-12-31
    assert uscal.is_holiday(D(2017, 1, 20)) and uscal.is_holiday(D(2013, 1, 21))
    assert uscal.next_business_day(D(2025, 12, 23)) == D(2025, 12, 29)
    assert uscal.next_business_day(D(2025, 12, 12)) == D(2025, 12, 15)
    # 2026 official schedule (Release Schedule page) vs normal rule for Tuesday reports
    sched = {D(2025, 12, 30): D(2026, 1, 5), D(2026, 6, 16): D(2026, 6, 22), D(2026, 6, 30): D(2026, 7, 6),
             D(2026, 11, 10): D(2026, 11, 16), D(2026, 11, 24): D(2026, 11, 30), D(2026, 12, 22): D(2026, 12, 28),
             D(2026, 10, 6): D(2026, 10, 9)}
    mism = {str(k): (str(C.normal_release_date(k)), str(v)) for k, v in sched.items() if C.normal_release_date(k) != v}
    r["schedule_2026_mismatch"] = mism
    # usable_from table / shutdown / exclusion / floor
    assert C.usable_from(D(2025, 12, 16))[0] == dt.datetime(2025, 12, 29, 20, 30, tzinfo=UTC)
    assert C.usable_from(D(2013, 10, 15))[1] == "2_SHUTDOWN_2013"
    assert C.usable_from(D(2019, 1, 15)) == (None, "2_GATE_EXCLUDED_2018_2019")
    assert C.usable_from(D(2025, 1, 7))[0].astimezone(JST).date() == D(2025, 1, 14)
    u, rule = C.usable_from(D(2010, 11, 23)); assert rule.endswith("HISTORY_FLOOR")
    # JST meaning: Friday 15:30 ET (summer) = Saturday 04:30 JST
    assert C.expected_release(D(2026, 10, 6)).astimezone(JST) == dt.datetime(2026, 10, 10, 4, 30, tzinfo=JST)
    r["ok"] = not mism
    if mism:
        raise AssertionError(f"normal rule disagrees with official 2026 schedule: {mism}")
    return r
