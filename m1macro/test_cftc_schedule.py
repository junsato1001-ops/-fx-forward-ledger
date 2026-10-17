"""CFTC schedule reader test on a captured page (fixture from dev run 39038642316, public domain)."""
import datetime as dt
from pathlib import Path

from m1macro import cftc_rules as R, cftc_schedule as S
from m1macro.tz import UTC

FIX = Path(__file__).resolve().parent / "fixtures" / "cftc_release_schedule_2026.html"


def run():
    y, rel = S.parse(FIX.read_bytes())
    assert y == 2026 and len(rel) == 52
    days = {t.astimezone(R.ET).date() for t in rel}
    for d in ("2026-01-05", "2026-06-22", "2026-07-06", "2026-11-16", "2026-11-30", "2026-12-28", "2026-10-16"):
        assert dt.date.fromisoformat(d) in days, d
    assert all(t.astimezone(R.ET).time() == dt.time(15, 30) for t in rel)
    # every scheduled release equals the rule-based Expected_Release of the preceding Tuesday report
    mism = [t for t in rel if R.expected_release(_tuesday_before(t.astimezone(R.ET).date())) != t]
    assert not mism, mism[:3]
    assert S.for_tinfo((y, rel), dt.datetime(2027, 1, 4, 18, tzinfo=UTC)) is None
    for bad in (b"<html>nothing</html>", FIX.read_bytes().replace(b"November", b"Novembre")):
        try:
            S.parse(bad); raise AssertionError("bad page accepted")
        except S.ScheduleParseFailure:
            pass
    return {"ok": True, "n_releases": len(rel)}


def _tuesday_before(d):
    x = d - dt.timedelta(days=1)
    while x.weekday() != 1:
        x -= dt.timedelta(days=1)
    return x
