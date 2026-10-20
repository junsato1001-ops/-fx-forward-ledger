"""Feature row/table tests on synthetic series (Part 3 §6.1, §4)."""
import datetime as dt
from decimal import Decimal

from m1macro import features as F, uscal
from m1macro.cftc_feature import Report


def run():
    d = dt.date(2025, 6, 2); us = {}; jp = {}; i = 0
    while d < dt.date(2025, 10, 1):
        if d.weekday() < 5:
            us[d] = Decimal(f"{4 + i / 1000:.3f}"); jp[d] = Decimal(f"{0.7 + i / 2000:.4f}"); i += 1
        d += dt.timedelta(days=1)
    reps = {}
    t = dt.date(2025, 6, 3)
    while t < dt.date(2025, 10, 1):
        reps[t] = Report(t, 100 + t.day, 50, 1000); t += dt.timedelta(days=7)
    o = dt.date(2025, 9, 10)
    tab = F.historical_table([o, o], us, jp, reps)
    assert list(tab) == ["2025-09-10"]
    e = tab["2025-09-10"]
    fus, fjp, fpos = e["_obj"]
    assert e["US"][0] == "OK" and fus.date == dt.date(2025, 9, 8)                  # last obs <= D-2
    assert fjp.date == dt.date(2025, 9, 8)                                           # 2nd-to-last obs before D
    assert e["US"][3] == float(us[fus.date] - us[fus.date_lag])
    assert fpos.report_date == dt.date(2025, 9, 2) and e["POS"][3] == (100 + 2 - 50) / 1000
    row = F.feature_row(o, fus, fjp, fpos, reps, {"treasury": {"retrieved_at_utc": "x", "bytes": 1, "sha256": "s", "path": "p"}},
                        "", "c", "r")
    assert set(row) == set(F.FEATURE_FIELDS) and row["T_info_UTC"] == "2025-09-09T18:00:00Z"
    assert row["F_POS_Long"] == "102" and row["F_US_Raw"] == str(us[fus.date])
    return {"ok": True}
