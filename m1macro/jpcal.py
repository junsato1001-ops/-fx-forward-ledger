"""Japanese Expected Publication Calendar (Impl Part 1 V1.2 §1.2): weekends, national holidays
(国民の祝日に関する法律: holidays, substitute holidays, citizens' holidays) and Dec 31 - Jan 3.
Used only for forward expected dates and staleness (years >= 2026)."""
import datetime as dt

# 国立天文台 暦要項 (published in February of the previous year). Later years: formula, flagged.
EQUINOX_OFFICIAL = {2026: (dt.date(2026, 3, 20), dt.date(2026, 9, 23)),
                    2027: (dt.date(2027, 3, 21), dt.date(2027, 9, 23))}
MIN_YEAR = 2026


def _nth_monday(y, m, n):
    d = dt.date(y, m, 1)
    d += dt.timedelta(days=(0 - d.weekday()) % 7)
    return d + dt.timedelta(weeks=n - 1)


def equinoxes(y):
    if y in EQUINOX_OFFICIAL:
        return EQUINOX_OFFICIAL[y] + ("OFFICIAL",)
    k = y - 1980
    sp = int(20.8431 + 0.242194 * k - int(k / 4)); au = int(23.2488 + 0.242194 * k - int(k / 4))
    return dt.date(y, 3, sp), dt.date(y, 9, au), "FORMULA"


def national_holidays(y):
    if y < MIN_YEAR:
        raise ValueError("Japanese expected calendar is defined for forward years >= 2026 only")
    sp, au, _ = equinoxes(y)
    base = {dt.date(y, 1, 1), _nth_monday(y, 1, 2), dt.date(y, 2, 11), dt.date(y, 2, 23), sp,
            dt.date(y, 4, 29), dt.date(y, 5, 3), dt.date(y, 5, 4), dt.date(y, 5, 5), _nth_monday(y, 7, 3),
            dt.date(y, 8, 11), _nth_monday(y, 9, 3), au, _nth_monday(y, 10, 2), dt.date(y, 11, 3), dt.date(y, 11, 23)}
    hol = set(base)
    for d in sorted(base):                     # substitute holiday
        if d.weekday() == 6:
            n = d + dt.timedelta(days=1)
            while n in hol:
                n += dt.timedelta(days=1)
            hol.add(n)
    for d in sorted(base):                     # citizens' holiday (sandwiched, not Sunday)
        mid = d + dt.timedelta(days=1); nxt = d + dt.timedelta(days=2)
        if mid not in hol and nxt in base and mid.weekday() != 6:
            hol.add(mid)
    return hol


_c = {}


def is_expected_business_day(d):
    if d.weekday() >= 5:
        return False
    if (d.month == 12 and d.day == 31) or (d.month == 1 and d.day <= 3):
        return False
    if d.year not in _c:
        _c[d.year] = national_holidays(d.year)
    return d not in _c[d.year]
