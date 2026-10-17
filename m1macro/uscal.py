"""U.S. federal holidays (5 U.S.C. 6103) and closures listed in Impl Part 1 V1.1 §2.3.2.

Rule-based for the statutory holidays (observed: Saturday -> preceding Friday, Sunday -> following Monday).
Inauguration Day (5 U.S.C. 6103(c), Washington D.C. area, where the CFTC is located) is included.
"""
import datetime as dt

SPECIAL_CLOSURES = {
    dt.date(2018, 12, 5): "National Day of Mourning (George H. W. Bush)",
    dt.date(2025, 1, 9): "National Day of Mourning (James E. Carter)",
    dt.date(2025, 12, 24): "Executive Order 14371 closure",
    dt.date(2025, 12, 26): "Executive Order 14371 closure",
}


def _nth_weekday(y, m, weekday, n):
    d = dt.date(y, m, 1)
    d += dt.timedelta(days=(weekday - d.weekday()) % 7)
    return d + dt.timedelta(weeks=n - 1)


def _last_weekday(y, m, weekday):
    d = dt.date(y + (m == 12), m % 12 + 1, 1) - dt.timedelta(days=1)
    return d - dt.timedelta(days=(d.weekday() - weekday) % 7)


def _observed(d):
    if d.weekday() == 5:
        return d - dt.timedelta(days=1)
    if d.weekday() == 6:
        return d + dt.timedelta(days=1)
    return d


def statutory_holidays(y):
    out = {}
    def add(d, name):
        out[d] = name
    for yy in (y, y + 1):  # New Year's Day of y+1 may be observed on Dec 31 of y
        add(_observed(dt.date(yy, 1, 1)), "New Year's Day")
    add(_nth_weekday(y, 1, 0, 3), "Birthday of Martin Luther King, Jr.")
    add(_nth_weekday(y, 2, 0, 3), "Washington's Birthday")
    add(_last_weekday(y, 5, 0), "Memorial Day")
    if y >= 2021:
        add(_observed(dt.date(y, 6, 19)), "Juneteenth National Independence Day")
    add(_observed(dt.date(y, 7, 4)), "Independence Day")
    add(_nth_weekday(y, 9, 0, 1), "Labor Day")
    add(_nth_weekday(y, 10, 0, 2), "Columbus Day")
    add(_observed(dt.date(y, 11, 11)), "Veterans Day")
    add(_nth_weekday(y, 11, 3, 4), "Thanksgiving Day")
    add(_observed(dt.date(y, 12, 25)), "Christmas Day")
    if (y - 1965) % 4 == 0:
        inaug = dt.date(y, 1, 20)
        if inaug.weekday() == 6:
            inaug += dt.timedelta(days=1)
        if inaug.weekday() < 5:
            out.setdefault(inaug, "Inauguration Day (D.C. area)")
    return {d: n for d, n in out.items() if d.year == y}


_cache = {}


def is_holiday(d):
    if d.year not in _cache:
        _cache[d.year] = statutory_holidays(d.year)
    return d in _cache[d.year] or d in SPECIAL_CLOSURES


def is_business_day(d):
    return d.weekday() < 5 and not is_holiday(d)


def next_business_day(d):
    d += dt.timedelta(days=1)
    while not is_business_day(d):
        d += dt.timedelta(days=1)
    return d
