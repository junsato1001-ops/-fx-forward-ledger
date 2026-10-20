"""D2: Pre-Freeze and Freeze-finalization gates. A_first(h) = T_info(first(h)) - WINDOW (earliest belonging acquisition)."""
import datetime as dt

from m1macro import freeze_gate as F
from m1macro.tz import JST, UTC


def run():
    cfg = {"first_forward_origin": {"1D": "2026-11-10", "1W": "2026-11-15", "4W": "2026-11-15"}}
    af = F.a_first(F.first_origins(cfg))
    # T_info 03:00 JST on the Origin day, window 6 h -> 21:00 JST the day before (before the 00:40 JST schedule)
    assert af["1D"] == dt.datetime(2026, 11, 9, 21, 0, tzinfo=JST) and F._s(af["1D"]) == "2026-11-09T12:00:00Z"
    assert af["1W"] == af["4W"] == dt.datetime(2026, 11, 14, 21, 0, tzinfo=JST)
    every = lambda d, h: h == "1D" or d.weekday() == 6        # formal Origins: 1D every day here, 1W/4W on Sundays
    t0 = dt.datetime(2026, 11, 9, 0, 0, tzinfo=UTC)        # inside (A_first(prev(1D)), A_first(1D)) = 11-08 12Z .. 11-09 12Z
    ok = F.pre_freeze(cfg, [t0], {}, every)
    assert ok["pass"], ok
    assert ok["previous_origin"] == {"1D": "2026-11-09", "1W": "2026-11-08", "4W": "2026-11-08"}
    # F10-a (Part 3 §2): first(h) must be the first Origin after the freeze -> too early is refused
    ap1 = F._utc(ok["a_previous_utc"]["1D"]); assert ap1 == af["1D"] - dt.timedelta(days=1)
    assert F.pre_freeze(cfg, [ap1], {}, every)["pass"]                                    # boundary: A_prev <= t
    assert F.pre_freeze(cfg, [ap1 - dt.timedelta(seconds=1)], {}, every)["violations"] == ["CHECK_TIME_BEFORE_PREVIOUS_ORIGIN:1D"]
    early = F.pre_freeze(cfg, [dt.datetime(2026, 10, 20, tzinfo=UTC)], {}, every)["violations"]
    assert early == ["CHECK_TIME_BEFORE_PREVIOUS_ORIGIN:1D", "CHECK_TIME_BEFORE_PREVIOUS_ORIGIN:1W",
                     "CHECK_TIME_BEFORE_PREVIOUS_ORIGIN:4W"], early
    # first origins whose freeze windows do not overlap can never pass (one freeze time for all horizons)
    daily = lambda d, h: True
    assert F.pre_freeze(cfg, [t0], {}, daily)["violations"] == ["CHECK_TIME_BEFORE_PREVIOUS_ORIGIN:1W",
                                                                "CHECK_TIME_BEFORE_PREVIOUS_ORIGIN:4W"]
    assert F.pre_freeze(cfg, [t0], {}, lambda d, h: d == F.first_origins(cfg)[h])["violations"] == \
        ["PREVIOUS_ORIGIN_UNKNOWN:1D", "PREVIOUS_ORIGIN_UNKNOWN:1W", "PREVIOUS_ORIGIN_UNKNOWN:4W"]
    # not set / not a formal origin / check time at or after A_first
    assert F.pre_freeze({}, [t0], {}, every)["violations"] == ["FIRST_FORWARD_ORIGIN_NOT_SET"]
    assert F.pre_freeze({"first_forward_origin": {"1D": "2026-11-10"}}, [t0], {}, every)["violations"] == ["FIRST_FORWARD_ORIGIN_NOT_SET"]
    assert "NOT_A_FORMAL_ORIGIN:1W" in F.pre_freeze(cfg, [t0], {}, lambda d, h: every(d, h) and h != "1W")["violations"]
    r = F.pre_freeze(cfg, [t0, af["1D"]], {}, every)
    assert r["violations"] == ["CHECK_TIME_NOT_BEFORE_A_FIRST:1D"]
    assert F.pre_freeze(cfg, [af["1D"] - dt.timedelta(seconds=1)], {}, every)["pass"]
    # production acquisition already started on main / ledger rows already exist
    fh = b"Run_ID,Source,Retrieved_At_UTC\n"
    early_f = {F.FETCHES: fh + b"R,cftc,2026-11-09T11:59:59Z\n"}
    assert F.pre_freeze(cfg, [t0], early_f, every)["pass"]
    late = {F.FETCHES: fh + b"R,cftc,2026-11-09T12:00:00Z\n"}
    assert F.pre_freeze(cfg, [t0], late, every)["violations"] == ["PRODUCTION_ACQUISITION_STARTED"]
    led = {F.LEDGER_FILES[4]: b"Run_ID,Origin,Deadline_Status\nA,2026-11-10,NOT_ISSUED\n"}
    assert F.pre_freeze(cfg, [t0], led, every)["violations"] == ["LEDGER_ROWS_EXIST:" + F.LEDGER_FILES[4]]
    old = {F.LEDGER_FILES[0]: b"Origin\n2026-11-09\n"}
    assert F.pre_freeze(cfg, [t0], old, every)["pass"]
    # finalization: strict inequality for every horizon; no source of T_freeze_recorded -> fail closed
    assert F.finalization(af["1D"] - dt.timedelta(seconds=1), cfg)["pass"]
    assert F.finalization(af["1D"], cfg)["violations"] == ["FREEZE_NOT_BEFORE_A_FIRST:1D"]
    assert F.finalization(af["1W"], cfg)["violations"] == ["FREEZE_NOT_BEFORE_A_FIRST:1D", "FREEZE_NOT_BEFORE_A_FIRST:1W",
                                                           "FREEZE_NOT_BEFORE_A_FIRST:4W"]
    assert F.finalization(None, cfg)["violations"] == ["T_FREEZE_RECORDED_UNAVAILABLE"]
    assert F.finalization(t0, {})["violations"] == ["FIRST_FORWARD_ORIGIN_NOT_SET"]
    # the candidate config today: first_forward_origin not yet set -> the Pre-Freeze Gate does not pass
    cur = F.pre_freeze(F._cfg(), [t0], {}, every)
    return {"ok": True, "current_config_pre_freeze": cur["violations"]}


if __name__ == "__main__":
    print(run())
