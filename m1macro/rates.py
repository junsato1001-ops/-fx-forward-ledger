"""U.S. Treasury 2 Yr and MOF JGB 2-year readers and F_US / F_JP (Transform 1 §2, Impl Part 1 V1.2 §1-§2.2).

Values are parsed from the published strings as Decimal; the difference is converted once to binary64
(Impl Part 2 §3). Observed Source Calendar = dates with a value; Expected Publication Calendar only for
forward expected dates and staleness.
"""
import csv
import datetime as dt
import io
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Dict, Optional

from m1macro import jpcal, uscal

TREASURY_DATASET = "Daily Treasury Par Yield Curve Rates"
TREASURY_COLUMN = "2 Yr"
MOF_COLUMN = "2年"
LAG = 20
MAX_STALE = 2


class ParseError(Exception):
    pass


def parse_treasury_csv(b: bytes) -> Dict[dt.date, Decimal]:
    try:
        rows = list(csv.reader(io.StringIO(b.decode("utf-8-sig"))))
    except UnicodeDecodeError as e:
        raise ParseError(str(e))
    if not rows or "Date" not in rows[0] or TREASURY_COLUMN not in rows[0]:
        raise ParseError("expected columns missing")
    iD = rows[0].index("Date"); iV = rows[0].index(TREASURY_COLUMN)
    out = {}
    for r in rows[1:]:
        if not r or not r[iD].strip():
            continue
        try:
            d = dt.datetime.strptime(r[iD].strip(), "%m/%d/%Y").date()
        except ValueError:
            raise ParseError(f"bad date {r[iD]!r}")
        v = r[iV].strip() if iV < len(r) else ""
        if v in ("", "N/A"):
            continue
        try:
            val = Decimal(v)
        except InvalidOperation:
            raise ParseError("bad value")
        if d in out and out[d] != val:
            raise ParseError("duplicate date with different value")
        out[d] = val
    return out


_ERA = {"S": 1925, "H": 1988, "R": 2018}


def _era_date(s):
    s = s.strip()
    if not s or s[0] not in _ERA:
        return None
    y, m, d = s[1:].split(".")
    return dt.date(_ERA[s[0]] + int(y), int(m), int(d))


def parse_mof_csv(b: bytes) -> Dict[dt.date, Decimal]:
    try:
        txt = b.decode("shift_jis")
    except UnicodeDecodeError as e:
        raise ParseError(str(e))
    rows = list(csv.reader(io.StringIO(txt)))
    hdr_i = next((i for i, r in enumerate(rows[:5]) if r and r[0] == "基準日"), None)
    if hdr_i is None or MOF_COLUMN not in rows[hdr_i]:
        raise ParseError("expected columns missing")
    iV = rows[hdr_i].index(MOF_COLUMN)
    out = {}
    for r in rows[hdr_i + 1:]:
        if not r or not r[0].strip():
            continue
        d = _era_date(r[0])
        if d is None:
            if r[0].startswith("※"):
                continue
            raise ParseError(f"bad date {r[0]!r}")
        v = r[iV].strip()
        if v in ("", "-"):
            continue
        try:
            out[d] = Decimal(v)
        except InvalidOperation:
            raise ParseError(f"bad value {v!r}")
    return out


def merge(*parts: Dict[dt.date, Decimal]) -> Dict[dt.date, Decimal]:
    out = {}
    for p in parts:
        for d, v in p.items():
            if d in out and out[d] != v:
                raise ParseError(f"overlapping files disagree on {d}")
            out[d] = v
    return out


def calendar_integrity(prev_dates, new_dates):
    """Impl Part 1 §1.1 checks 3-4. Returns '' or the failure subreason."""
    if prev_dates:
        lo, hi = min(new_dates, default=None), max(new_dates, default=None)
        overlap = {d for d in prev_dates if lo is not None and lo <= d <= max(prev_dates)}
        if not overlap <= set(new_dates):
            return "CALENDAR_INTEGRITY"
        if hi is None or hi < max(prev_dates):
            return "CALENDAR_INTEGRITY"
    return ""


@dataclass
class Feature:
    status: str                 # OK / MODEL_PREREQ_UNAVAILABLE / ABSTAIN_SYSTEM
    reason: str = ""
    subreason: str = ""
    value: Optional[float] = None
    date: Optional[dt.date] = None
    date_lag: Optional[dt.date] = None
    raw: str = ""
    raw_lag: str = ""
    stale_days: int = 0
    expected_date: Optional[dt.date] = None


def _diff(series, d, lag_d, out):
    out.raw = str(series[d]); out.raw_lag = str(series[lag_d])
    out.value = float(series[d] - series[lag_d])       # % difference = units of 100bp (Decimal -> binary64 once)
    out.status = "OK"
    return out


def _lag_date(obs, d):
    i = obs.index(d)
    return obs[i - LAG] if i >= LAG else None


def f_us(origin: dt.date, series: Dict[dt.date, Decimal], forward: bool) -> Feature:
    obs = sorted(series)
    limit = origin - dt.timedelta(days=2)                       # strictly before D-1 (calendar)
    cand = [d for d in obs if d <= limit]
    if forward:
        e = limit
        while not uscal.is_treasury_expected_business_day(e):
            e -= dt.timedelta(days=1)
        cand = [d for d in cand if d <= e]
    if not cand:
        return Feature("MODEL_PREREQ_UNAVAILABLE", "FEATURE_STALE", "NO_VALUE")
    v = cand[-1]
    out = Feature("", date=v)
    if forward:
        out.expected_date = e
        k = 0; x = v + dt.timedelta(days=1)
        while x <= e:
            k += uscal.is_treasury_expected_business_day(x); x += dt.timedelta(days=1)
        out.stale_days = k
        if k > MAX_STALE:
            out.status, out.reason, out.subreason = "MODEL_PREREQ_UNAVAILABLE", "FEATURE_STALE", "RATE_SOURCE_BUSINESS_DAYS"
            return out
    lag = _lag_date(obs, v)
    if lag is None:
        out.status, out.reason, out.subreason = "MODEL_PREREQ_UNAVAILABLE", "FEATURE_NOT_COMPUTABLE", "NO_LAG_VALUE"
        return out
    out.date_lag = lag
    return _diff(series, v, lag, out)


def f_jp(origin: dt.date, series: Dict[dt.date, Decimal], forward: bool) -> Feature:
    obs = sorted(series)
    if not forward:
        before = [d for d in obs if d < origin]
        if len(before) < 2:
            return Feature("MODEL_PREREQ_UNAVAILABLE", "FEATURE_STALE", "NO_VALUE")
        u = before[-2]; out = Feature("", date=u)
    else:
        e1 = origin - dt.timedelta(days=1)
        while not jpcal.is_expected_business_day(e1):
            e1 -= dt.timedelta(days=1)
        e = e1 - dt.timedelta(days=1)
        while not jpcal.is_expected_business_day(e):
            e -= dt.timedelta(days=1)
        cand = [d for d in obs if d <= e]
        if not cand:
            return Feature("MODEL_PREREQ_UNAVAILABLE", "FEATURE_STALE", "NO_VALUE")
        u = cand[-1]; out = Feature("", date=u, expected_date=e)
        k = 0; x = u + dt.timedelta(days=1)
        while x <= e:
            k += jpcal.is_expected_business_day(x); x += dt.timedelta(days=1)
        out.stale_days = k
        if k > MAX_STALE:
            out.status, out.reason, out.subreason = "MODEL_PREREQ_UNAVAILABLE", "FEATURE_STALE", "RATE_SOURCE_BUSINESS_DAYS"
            return out
    lag = _lag_date(obs, u)
    if lag is None:
        out.status, out.reason, out.subreason = "MODEL_PREREQ_UNAVAILABLE", "FEATURE_NOT_COMPUTABLE", "NO_LAG_VALUE"
        return out
    out.date_lag = lag
    return _diff(series, u, lag, out)


def calendar_anomalies(series_dates, expected_fn, lo, hi):
    """Dates where observed and expected calendars disagree (audit only; values unchanged)."""
    obs = set(series_dates); out = []
    d = lo
    while d <= hi:
        exp = expected_fn(d)
        if (d in obs) != exp:
            out.append((d.isoformat(), "OBSERVED_NOT_EXPECTED" if d in obs else "EXPECTED_NOT_OBSERVED"))
        d += dt.timedelta(days=1)
    return out
