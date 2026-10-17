"""CFTC TFF publication-time rules (Matrix §3, Transform 2-A §2.3, Impl Part 1 V1.1 §2.3).

Usable_From(R): upper bound of the publication time (look-ahead guard).
Expected_Release(R): time under the normal publication rule (staleness).
Both are aware datetimes in UTC; None = report not usable (gate excluded).
"""
import datetime as dt

from m1macro import uscal
from m1macro.tz import ET, UTC

ET_1530 = dt.time(15, 30)
TFF_HISTORY_FLOOR_ET = dt.datetime(2010, 12, 7, 0, 0, tzinfo=ET)   # CFTC Gate: history usable after end of 2010-12-06 ET
TFF_FIRST_ORIGIN = dt.date(2010, 12, 8)

# Impl Part 1 V1.1 §2.3.2 (rule 1: dated special announcements / conservative next business day)
TABLE_USABLE = {
    dt.date(2025, 9, 30): dt.date(2025, 11, 19), dt.date(2025, 10, 7): dt.date(2025, 11, 21),
    dt.date(2025, 10, 14): dt.date(2025, 11, 25), dt.date(2025, 10, 21): dt.date(2025, 12, 2),
    dt.date(2025, 10, 28): dt.date(2025, 12, 5), dt.date(2025, 11, 4): dt.date(2025, 12, 9),
    dt.date(2025, 11, 10): dt.date(2025, 12, 11), dt.date(2025, 11, 18): dt.date(2025, 12, 15),
    dt.date(2025, 11, 25): dt.date(2025, 12, 16), dt.date(2025, 12, 2): dt.date(2025, 12, 18),
    dt.date(2025, 12, 9): dt.date(2025, 12, 22), dt.date(2025, 12, 16): dt.date(2025, 12, 29),
    dt.date(2025, 12, 23): dt.date(2025, 12, 30),
}
CARTER_WEEK = (dt.date(2025, 1, 6), dt.date(2025, 1, 12), dt.date(2025, 1, 13))   # week of report 2025-01-07 -> 01-13
SHUTDOWN_2013 = (dt.date(2013, 10, 1), dt.date(2013, 10, 29), dt.date(2013, 11, 8))
EXCLUDED_2018 = (dt.date(2018, 12, 24), dt.date(2019, 3, 5))


def _at(d):
    return dt.datetime.combine(d, ET_1530, tzinfo=ET).astimezone(UTC)


def normal_release_date(report_date):
    """Rule 3/5: Friday of the report's Mon-Sun week; next Monday if a federal holiday falls on Tue-Fri."""
    monday = report_date - dt.timedelta(days=report_date.weekday())
    if any(uscal.is_holiday(monday + dt.timedelta(days=i)) for i in range(1, 5)):
        return monday + dt.timedelta(days=7)
    return monday + dt.timedelta(days=4)


def expected_release(report_date):
    return _at(normal_release_date(report_date))


def usable_from(report_date):
    """Rules 1-5 in order; floor at the TFF history publication."""
    if report_date in TABLE_USABLE:
        t = _at(TABLE_USABLE[report_date]); rule = "1_TABLE"
    elif CARTER_WEEK[0] <= report_date <= CARTER_WEEK[1]:
        t = _at(CARTER_WEEK[2]); rule = "1_NOTICE_2025_01"
    elif SHUTDOWN_2013[0] <= report_date <= SHUTDOWN_2013[1]:
        t = _at(SHUTDOWN_2013[2]); rule = "2_SHUTDOWN_2013"
    elif EXCLUDED_2018[0] <= report_date <= EXCLUDED_2018[1]:
        return None, "2_GATE_EXCLUDED_2018_2019"
    else:
        t = expected_release(report_date); rule = "3_5_NORMAL"   # rule 4 (2014-07 early release) = scheduled date
    floor = TFF_HISTORY_FLOOR_ET.astimezone(UTC)
    if t < floor:
        t = floor; rule += "+HISTORY_FLOOR"
    return t, rule
