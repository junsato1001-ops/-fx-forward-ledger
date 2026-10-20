"""Machine-readable verdict of gates G1-G9 (Impl Part 4 §5) from the published gate result files
(IMPL-FINDINGS-05 F1-d, むすび 2026-10-18: the freeze must verify that every formal gate PASSed, not only a label).

Reads only allow-listed result files (suite.json, g5_summary.json, g678_summary.json, exits.txt). Standard library
only. Every criterion is a fixed rule of the frozen gate table; no tolerance is introduced here except the frozen
ε_tie = 1e-13 (Impl Part 2 §10 criterion 1) and the gate counts.

usage: python3 -I m1macro/gate_verdict.py <result_dir> [<out_json>]
"""
import json
import sys
from pathlib import Path

EPS_TIE = 1e-13
N_SHARDS = 40            # = m1macro_gates.yml N_SHARDS (F5-b, むすび 2026-10-19); infrastructure only
G1_TESTS = ("test_solver",)
G2_TESTS = ("test_fullscale",)
G3_TESTS = ("test_indep",)
G4_TESTS = ("test_ledger_tx", "test_gitrepo_tx", "test_forward_commit", "test_deadline_gate")


def _hex64(v):
    return isinstance(v, str) and len(v) == 64 and all(c in "0123456789abcdef" for c in v)


def _load(d, name):
    p = Path(d, name)
    return json.loads(p.read_text("utf-8")) if p.exists() else None


def verdict(d) -> dict:
    suite = _load(d, "suite.json"); g5 = _load(d, "g5_summary.json"); g678 = _load(d, "g678_summary.json")
    ex = Path(d, "exits.txt")
    exits = ex.read_text("utf-8").strip() if ex.exists() else None
    out = {}

    def gate(name, checks):
        out[name] = {"pass": all(checks.values()), "checks": checks}

    s_ok = lambda ts: suite is not None and all(suite.get(t, {}).get("status") == "PASS" for t in ts)
    det = lambda t, k: bool(suite and (suite.get(t, {}).get("detail") or {}).get(k))
    gate("G1", {"suite_present": suite is not None, "tests_pass": s_ok(G1_TESTS), "all_ok": det("test_solver", "ALL_OK")})
    gate("G2", {"tests_pass": s_ok(G2_TESTS), "margin_ok": det("test_fullscale", "margin_ok_neg_side_le_1e-14")})
    gate("G3", {"tests_pass": s_ok(G3_TESTS), "all_pass": det("test_indep", "ALL_PASS")})
    gate("G4", {"tests_pass": s_ok(G4_TESTS)})
    out["SUITE_ALL"] = {"pass": bool(suite) and all(v.get("status") == "PASS" for v in suite.values()),
                        "checks": {"n_tests": len(suite or {})}}
    n_th5 = sum((g5 or {}).get("n_th", {}).values()) if g5 else None
    U = (g5 or {}).get("th_universe") or {}
    K6 = ((g678 or {}).get("G6") or {}).get("th_keyset") or {}
    # F7-a (むすび 2026-10-19): the expected (t, h) universe and the G6 rows must each be duplicate-free and must be
    # the same key set. Any duplicate fails the gate; nothing is deduplicated or repaired.
    gate("G5", {"summary_present": g5 is not None, "n_origins_positive": bool(g5 and g5.get("n_origins", 0) > 0),
                "th_universe_unique": n_th5 is not None and U.get("n") == n_th5 == U.get("n_unique")
                and U.get("n_duplicate") == 0 and bool(U.get("sha256")),
                "snapshot_identified": _hex64((g5 or {}).get("snapshot_manifest_sha256")),
                "every_origin_has_three_statuses": bool(g5) and all(sum(c.values()) == g5["n_origins"]
                                                                       for c in g5.get("status_counts", {}).values())
                and set(g5.get("status_counts", {})) == {"F_US", "F_JP", "F_POS"}})
    G6 = (g678 or {}).get("G6", {}); G7 = (g678 or {}).get("G7", {}); G8 = (g678 or {}).get("G8", {})
    num = lambda v: v if isinstance(v, (int, float)) else None
    le = lambda v: num(v) is not None and abs(v) <= EPS_TIE
    gate("G6", {"summary_present": bool(G6), "all_th_covered": n_th5 is not None and G6.get("n_th") == n_th5,
                "th_rows_unique": n_th5 is not None and K6.get("n") == G6.get("n_th") == K6.get("n_unique") == n_th5
                and K6.get("n_duplicate") == 0,
                "th_keyset_equals_universe": bool(K6.get("sha256")) and K6.get("sha256") == U.get("sha256"),
                "no_errors": G6.get("errors") == 0 and not G6.get("error_types"),
                "all_estimated_pass": num(G6.get("n_estimated")) is not None and G6.get("n_pass_all") == G6.get("n_estimated"),
                "ub_minus_lb_le_eps": G6.get("n_estimated") == 0 or (le(G6.get("max_abs_ub_minus_lb"))),
                "phi2_minus_lb_le_eps": G6.get("n_estimated") == 0 or (le(G6.get("max_abs_phi2_minus_lb")))})
    gate("G7", {"all_shards": G7.get("n_shards") == N_SHARDS,
                "both_runs_complete": n_th5 is not None and G7.get("n_keys") == G7.get("n_run_A") == G7.get("n_run_B") == n_th5,
                "no_duplicate_rows": n_th5 is not None and G7.get("n_rows_A") == G7.get("n_rows_B") == n_th5,
                "same_snapshot_as_g5": _hex64((g5 or {}).get("snapshot_manifest_sha256"))
                and G7.get("snapshot_manifest_sha256") == [g5["snapshot_manifest_sha256"]],
                "e_input_identical": G7.get("e_input_sha_mismatch") == 0, "beta_identical": G7.get("beta_sha_or_state_mismatch") == 0})
    gate("G8", {"summary_present": bool(G8), "no_mismatch": G8.get("n_mismatch") == 0,
                "all_match": num(G8.get("n_match")) is not None and G8.get("n_match") == G8.get("n_mu_zero_rows")})
    gate("G9", {"holdout_rows_zero": bool(g5) and g5.get("holdout_rows") == 0,
                "no_holdout_breach": "HoldoutBreach" not in (G6.get("error_types") or [])})
    out["RUN"] = {"pass": exits == "", "checks": {"exits_file_present": exits is not None, "no_job_exit_codes": exits == ""}}
    out["all_pass"] = all(v["pass"] for k, v in out.items() if isinstance(v, dict))
    return out


if __name__ == "__main__":
    v = verdict(sys.argv[1])
    b = json.dumps(v, indent=1, sort_keys=True)
    if len(sys.argv) > 2:
        Path(sys.argv[2]).write_text(b + "\n", encoding="utf-8")
    print(json.dumps({"all_pass": v["all_pass"], "failed": sorted(k for k, x in v.items() if isinstance(x, dict) and not x["pass"])}))
