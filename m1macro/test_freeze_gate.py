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
    every = lambda d, h: True
    t0 = dt.datetime(2026, 10, 20, 0, 0, tzinfo=UTC)
    ok = F.pre_freeze(cfg, [t0], {}, every)
    assert ok["pass"], ok
    # not set / not a formal origin / check time at or after A_first
    assert F.pre_freeze({}, [t0], {}, every)["violations"] == ["FIRST_FORWARD_ORIGIN_NOT_SET"]
    assert F.pre_freeze({"first_forward_origin": {"1D": "2026-11-10"}}, [t0], {}, every)["violations"] == ["FIRST_FORWARD_ORIGIN_NOT_SET"]
    assert "NOT_A_FORMAL_ORIGIN:1W" in F.pre_freeze(cfg, [t0], {}, lambda d, h: h != "1W")["violations"]
    r = F.pre_freeze(cfg, [t0, af["1D"]], {}, every)
    assert r["violations"] == ["CHECK_TIME_NOT_BEFORE_A_FIRST:1D"]
    assert F.pre_freeze(cfg, [af["1D"] - dt.timedelta(seconds=1)], {}, every)["pass"]
    # production acquisition already started on main / ledger rows already exist
    fh = b"Run_ID,Source,Retrieved_At_UTC\n"
    early = {F.FETCHES: fh + b"R,cftc,2026-11-09T11:59:59Z\n"}
    assert F.pre_freeze(cfg, [t0], early, every)["pass"]
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
