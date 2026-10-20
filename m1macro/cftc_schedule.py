"""Official CFTC COT Release Schedule page reader (Impl Part 1 V1.2 §2.3 '本番の公表日程').
Releases are at 15:30 ET. A page that cannot be read strictly (all 12 months, valid dates) is a parse failure;
the caller then uses schedule=None (ABSTAIN_SYSTEM, CFTC_RELEASE_SCHEDULE_UNAVAILABLE)."""
import datetime as dt
import html
import re

from m1macro.tz import ET, UTC

MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October",
          "November", "December"]


class ScheduleParseFailure(Exception):
    pass


def _text(b: bytes) -> str:
    t = b.decode("utf-8")
    t = re.sub(r"<script.*?</script>|<style.*?</style>", "", t, flags=re.S)
    t = re.sub(r"<(td|th)[^>]*>", " | ", t)
    t = re.sub(r"</tr>", "\n", t)
    t = re.sub(r"<[^>]+>", " ", t)
    t = html.unescape(t).replace("\xa0", " ")
    return re.sub(r"[ \t]+", " ", t)


def parse(b: bytes):
    """Returns (year, sorted list of release datetimes in UTC)."""
    t = _text(b)
    m = re.search(r"(\d{4}) Release Schedule \| Month \| Dates", t)
    if not m:
        raise ScheduleParseFailure("schedule table not found")
    year = int(m.group(1))
    body = t[m.end():]
    out = []
    for mi, name in enumerate(MONTHS, start=1):
        r = re.search(r"\| " + name + r" ((?:\| [0-9*]* ?)+)", body)
        if not r:
            raise ScheduleParseFailure(f"month {name} missing")
        cells = [c.strip() for c in r.group(1).split("|")]
        days = [c.rstrip("*") for c in cells if c]
        if not 3 <= len(days) <= 5:
            raise ScheduleParseFailure(f"month {name}: {len(days)} dates")
        for d in days:
            if not d.isdigit():
                raise ScheduleParseFailure(f"bad day {d!r}")
            out.append(dt.datetime(year, mi, int(d), 15, 30, tzinfo=ET).astimezone(UTC))
    out.sort()
    if len(out) != len(set(out)) or not 48 <= len(out) <= 54:
        raise ScheduleParseFailure("implausible release count")
    return year, out


def for_tinfo(parsed, tinfo_utc: dt.datetime):
    """Schedule usable for an origin only if it covers the ET year of T_info (else None)."""
    if parsed is None:
        return None
    year, rel = parsed
    return rel if tinfo_utc.astimezone(ET).year == year else None
