"""Synthetic tests for Treasury/MOF parsing, F_US/F_JP value dates, staleness and calendars."""
import datetime as dt
from decimal import Decimal

from m1macro import jpcal, rates as RT, uscal

D = dt.date


def _us_series(lo, hi):
    out = {}; d = lo; i = 0
    while d <= hi:
        if uscal.is_treasury_expected_business_day(d):
            out[d] = Decimal("3.50") + Decimal(i) / Decimal(100); i += 1
        d += dt.timedelta(days=1)
    return out


def _jp_series(lo, hi):
    out = {}; d = lo; i = 0
    while d <= hi:
        if jpcal.is_expected_business_day(d):
            out[d] = Decimal("1.000") + Decimal(i) / Decimal(1000); i += 1
        d += dt.timedelta(days=1)
    return out


def run():
    r = {}
    # parsers
    tcsv = b'Date,"1 Mo","2 Yr","10 Yr"\n10/16/2026,4.0,3.51,4.1\n10/15/2026,4.0,N/A,4.1\n10/14/2026,4.0,3.49,4.1\n'
    t = RT.parse_treasury_csv(tcsv); assert t == {D(2026, 10, 16): Decimal("3.51"), D(2026, 10, 14): Decimal("3.49")}
    mcsv = ("国債金利情報,,\n基準日,1年,2年\nR8.10.1,1.668,1.939\nR8.10.2,1.65,-\n,,\n※注記,,\n").encode("shift_jis")
    m = RT.parse_mof_csv(mcsv); assert m == {D(2026, 10, 1): Decimal("1.939")}
    assert RT._era_date("S49.9.24") == D(1974, 9, 24) and RT._era_date("H31.4.30") == D(2019, 4, 30)
    for bad in (b"x,y\n1,2\n",):
        try:
            RT.parse_treasury_csv(bad); raise AssertionError
        except RT.ParseError:
            pass
    # Japanese expected calendar 2026: known holidays and the 9/22 citizens' holiday
    for d in (D(2026, 1, 12), D(2026, 3, 20), D(2026, 5, 6), D(2026, 9, 21), D(2026, 9, 22), D(2026, 9, 23), D(2026, 11, 23), D(2026, 12, 31)):
        assert not jpcal.is_expected_business_day(d), d
    assert jpcal.is_expected_business_day(D(2026, 10, 16))
    assert jpcal.equinoxes(2028)[2] == "FORMULA"
    # F_US historical: value date strictly before D-1, lag 20 observed days
    us = _us_series(D(2026, 7, 1), D(2026, 10, 16))
    f = RT.f_us(D(2026, 10, 19), us, forward=False)        # Mon origin -> D-2 = Sat -> last obs Fri 10-16
    assert f.status == "OK" and f.date == D(2026, 10, 16) and f.value == float(Decimal("0.20"))
    f = RT.f_us(D(2026, 10, 17), us, forward=False); assert f.date == D(2026, 10, 15)
    # F_US forward: expected 10-16, latest observed 10-14 -> 2 business days stale -> allowed
    us2 = {d: v for d, v in us.items() if d <= D(2026, 10, 14)}
    f = RT.f_us(D(2026, 10, 19), us2, forward=True); assert f.status == "OK" and f.stale_days == 2 and f.date == D(2026, 10, 14)
    us3 = {d: v for d, v in us.items() if d <= D(2026, 10, 13)}
    f = RT.f_us(D(2026, 10, 19), us3, forward=True); assert f.reason == "FEATURE_STALE" and f.stale_days == 3
    # 2021-01-20 Inauguration Day is a Treasury publication day (expected calendar)
    us21 = _us_series(D(2020, 11, 1), D(2021, 1, 22))
    assert D(2021, 1, 20) in us21
    f = RT.f_us(D(2021, 1, 22), us21, forward=True); assert f.date == D(2021, 1, 20) and f.stale_days == 0
    # F_JP historical: second-to-last observed date before D
    jp = _jp_series(D(2026, 7, 1), D(2026, 10, 16))
    f = RT.f_jp(D(2026, 10, 19), jp, forward=False); assert f.date == D(2026, 10, 15)
    f = RT.f_jp(D(2026, 10, 19), jp, forward=True); assert f.date == D(2026, 10, 15) and f.stale_days == 0
    f = RT.f_jp(D(2026, 9, 24), jp, forward=True); assert f.date == D(2026, 9, 17)   # 9/21-9/23 holidays: e1 = 9/18, u = 9/17
    # NOT_COMPUTABLE when fewer than 20 earlier observed values
    f = RT.f_jp(D(2026, 7, 10), jp, forward=False); assert f.reason == "FEATURE_NOT_COMPUTABLE"
    # calendar integrity
    assert RT.calendar_integrity({D(2026, 10, 1), D(2026, 10, 2), D(2026, 10, 5)}, {D(2026, 10, 1), D(2026, 10, 5), D(2026, 10, 6)}) == "CALENDAR_INTEGRITY"
    assert RT.calendar_integrity({D(2026, 10, 1), D(2026, 10, 5)}, {D(2026, 10, 1)}) == "CALENDAR_INTEGRITY"
    assert RT.calendar_integrity({D(2026, 10, 1)}, {D(2026, 10, 1), D(2026, 10, 2)}) == ""
    # anomalies are audit records only
    an = RT.calendar_anomalies({D(2026, 10, 16)}, uscal.is_treasury_expected_business_day, D(2026, 10, 15), D(2026, 10, 17))
    assert an == [("2026-10-15", "EXPECTED_NOT_OBSERVED")]
    r["ok"] = True
    return r
