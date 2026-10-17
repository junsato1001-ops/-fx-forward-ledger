"""D2 Freeze boundary gates (IMPL-FINDINGS-03 修正仕様, むすび PASS 2026-10-18).

A_first(h): the earliest instant at which a production acquisition belonging to the first forward Origin of horizon h
can occur, derived mechanically from the config and the production selection rule (never typed in). An acquisition
belongs to Origin t iff T_info(t) - WINDOW < Retrieved_At <= T_info(t) (CFTC Forward Snapshot Gate,
cftc_feature.forward); the other sources are fetched after T_info(t). Hence A_first(h) = T_info(first(h)) - WINDOW,
which is no later than the scheduled 00:40 JST pre-T_info acquisition.

Pre-Freeze Gate (candidate creation / audit): every first_forward_origin(h) is set, is a formal Origin of h, every
check time (now, and the planned freeze time if given) is strictly before A_first(h), and the formal main branch holds
no acquisition at or after min_h A_first(h) and no M1 ledger or audit row for an Origin >= min_h first(h).

Freeze-finalization Gate: T_freeze_recorded < A_first(h) for all h (strict, UTC).
NOT WIRED: the canonical source of T_freeze_recorded (an auditable Recorded_At_UTC of the freeze-record transaction,
fixed after push/reread) does not exist in the repository yet (Finding, 2026-10-18). finalization() takes the value
as an argument and nothing in this repository supplies it; no client-entered time is accepted as a substitute.

usage: python -I m1macro/freeze_gate.py pre [--main-dir DIR] [--planned-freeze-utc YYYY-MM-DDTHH:MM:SSZ]
"""
import csv
import datetime as dt
import io
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from m1macro import cftc_feature, features  # noqa: E402
from m1macro.tz import UTC  # noqa: E402

HORIZONS = ("1D", "1W", "4W")
FETCHES = "data/m1macro/source_fetches.csv"
LEDGER_FILES = ("ledger/m1_macro_features.csv", "ledger/m1_macro_estimation.csv", "ledger/m1_macro_forecasts.csv",
                "ledger/m1_macro_issue_commits.csv", "audit_log/m1_macro_issue_deadline.csv")


def _cfg():
    return json.loads((ROOT / "m1macro" / "config" / "m1macro_config.json").read_text("utf-8"))


def _utc(s):
    return dt.datetime.strptime(s, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC)


def _s(t):
    return t.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def first_origins(cfg):
    v = cfg.get("first_forward_origin")
    if not isinstance(v, dict) or any(not v.get(h) for h in HORIZONS):
        return None
    return {h: dt.date.fromisoformat(v[h]) for h in HORIZONS}


def a_first(first):
    return {h: features.tinfo_utc(d) - cftc_feature.WINDOW for h, d in first.items()}


def _rows(b):
    return list(csv.DictReader(io.StringIO(b.decode("utf-8")))) if b else []


def pre_freeze(cfg, check_times, main_files, is_formal_origin):
    """check_times: datetimes (UTC); main_files: {rel: bytes} from the formal main branch (absent = b'');
    is_formal_origin(date, h) -> bool (frozen ORIGIN_TARGET_MAP). Returns a result dict."""
    res = {"gate": "D2_PRE_FREEZE", "pass": False, "violations": []}
    first = first_origins(cfg)
    if first is None:
        res["violations"].append("FIRST_FORWARD_ORIGIN_NOT_SET"); return res
    af = a_first(first)
    res["first_forward_origin"] = {h: first[h].isoformat() for h in HORIZONS}
    res["a_first_utc"] = {h: _s(af[h]) for h in HORIZONS}
    res["check_times_utc"] = [_s(t) for t in check_times]
    for h in HORIZONS:
        if not is_formal_origin(first[h], h):
            res["violations"].append(f"NOT_A_FORMAL_ORIGIN:{h}")
        for t in check_times:
            if not t < af[h]:
                res["violations"].append(f"CHECK_TIME_NOT_BEFORE_A_FIRST:{h}")
    lo = min(af.values()); first_min = min(first.values()).isoformat()
    for r in _rows(main_files.get(FETCHES, b"")):
        if r.get("Retrieved_At_UTC") and _utc(r["Retrieved_At_UTC"]) >= lo:
            res["violations"].append("PRODUCTION_ACQUISITION_STARTED"); break
    for rel in LEDGER_FILES:
        if any(r.get("Origin", "") >= first_min for r in _rows(main_files.get(rel, b""))):
            res["violations"].append("LEDGER_ROWS_EXIST:" + rel)
    res["violations"] = sorted(set(res["violations"]))
    res["pass"] = not res["violations"]
    return res


def finalization(t_freeze_recorded, cfg):
    """T_freeze_recorded < A_first(h) for every h (strict). t_freeze_recorded must come from the auditable freeze-record
    transaction; its source is not implemented yet (see module docstring)."""
    res = {"gate": "D2_FREEZE_FINALIZATION", "pass": False, "violations": []}
    first = first_origins(cfg)
    if first is None:
        res["violations"].append("FIRST_FORWARD_ORIGIN_NOT_SET"); return res
    if t_freeze_recorded is None:
        res["violations"].append("T_FREEZE_RECORDED_UNAVAILABLE"); return res
    af = a_first(first)
    res["t_freeze_recorded_utc"] = _s(t_freeze_recorded)
    res["a_first_utc"] = {h: _s(af[h]) for h in HORIZONS}
    for h in HORIZONS:
        if not t_freeze_recorded < af[h]:
            res["violations"].append(f"FREEZE_NOT_BEFORE_A_FIRST:{h}")
    res["pass"] = not res["violations"]
    return res


def _formal_origin_fn():
    sys.path.insert(0, str(ROOT / "forward"))
    import ledger_builder as lb
    _, mp, _ = lb.load_frozen()
    return mp.is_formal_origin


def main(argv):
    if not argv or argv[0] != "pre":
        raise SystemExit(__doc__)
    args = dict(zip(argv[1::2], argv[2::2]))
    times = [dt.datetime.now(UTC)]
    if "--planned-freeze-utc" in args:
        times.append(_utc(args["--planned-freeze-utc"]))
    md = Path(args["--main-dir"]) if "--main-dir" in args else None
    files = {rel: ((md / rel).read_bytes() if md and (md / rel).exists() else b"") for rel in (FETCHES,) + LEDGER_FILES}
    res = pre_freeze(_cfg(), times, files, _formal_origin_fn())
    res["main_dir_given"] = md is not None
    if md is None:
        res["violations"].append("MAIN_BRANCH_FILES_NOT_PROVIDED"); res["pass"] = False
    print(json.dumps(res, sort_keys=True))
    return 0 if res["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
