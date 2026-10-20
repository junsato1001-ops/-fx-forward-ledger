"""IMPL-FINDINGS-07 F7-a (むすび 2026-10-19): fail-closed uniqueness of the (t, h) universe and of the G6/G7 rows;
IMPL-FINDINGS-08 F8-d: one development snapshot for G5 and every G6-G8 shard.

A duplicate anywhere fails the gate. Nothing is deduplicated or repaired: equal counts with a duplicate on one side
and a missing key on the other must FAIL. Synthetic numbers only."""
import json
import tempfile
from pathlib import Path

from m1macro import gate_verdict as V, gates
from m1macro.test_freeze_record import _passing_results


def _verdict(files, g5=None, g678=None):
    with tempfile.TemporaryDirectory() as td:
        for n, b in files.items():
            Path(td, n).write_bytes(b)
        if g5 is not None:
            Path(td, "g5_summary.json").write_text(json.dumps(g5))
        if g678 is not None:
            Path(td, "g678_summary.json").write_text(json.dumps(g678))
        return V.verdict(td)


def run():
    # th_keyset counts every occurrence; it never collapses duplicates silently
    k = gates.th_keyset([("2020-01-02", "1D"), ("2020-01-02", "1D"), ("2020-01-03", "1W")])
    assert (k["n"], k["n_unique"], k["n_duplicate"]) == (3, 2, 1), k
    assert gates.th_keyset([("2020-01-03", "1W"), ("2020-01-02", "1D")])["sha256"] == \
        gates.th_keyset([("2020-01-02", "1D"), ("2020-01-03", "1W")])["sha256"]          # order-free key set
    assert gates.th_keyset([("2020-01-02", "1D")])["sha256"] != gates.th_keyset([("2020-01-02", "1W")])["sha256"]

    files, v, g678 = _passing_results()
    assert v["all_pass"] and v["G5"]["checks"]["th_universe_unique"] and v["G6"]["checks"]["th_rows_unique"] \
        and v["G6"]["checks"]["th_keyset_equals_universe"] and v["G7"]["checks"]["no_duplicate_rows"]
    g5 = json.loads(files["g5_summary.json"])
    keys = [(f"2020-01-{d:02d}", "1D") for d in range(1, 7)] + [(f"2020-02-{d:02d}", h) for d in (1, 2) for h in ("1W", "4W")]

    def cp(x):
        return json.loads(json.dumps(x))

    cases = []
    # 1. expected universe itself has a duplicate (counts all agree: G6 built from the same universe)
    dup = keys[:-1] + [keys[0]]
    b5 = cp(g5); b5["th_universe"] = gates.th_keyset(dup)
    b6 = cp(g678); b6["G6"]["th_keyset"] = gates.th_keyset(dup)
    cases.append(("universe_duplicate", b5, b6, ("G5", "th_universe_unique")))
    # 2. G6 rows: one key duplicated, one missing -> n_th still equal to the expected count
    b6 = cp(g678); b6["G6"]["th_keyset"] = gates.th_keyset(keys[:-1] + [keys[0]])
    cases.append(("g6_duplicate_and_missing", None, b6, ("G6", "th_rows_unique")))
    # 3. G6 rows unique and of the right count, but a different key set (a key outside the universe)
    b6 = cp(g678); b6["G6"]["th_keyset"] = gates.th_keyset(keys[:-1] + [("1999-01-01", "4W")])
    cases.append(("g6_foreign_key", None, b6, ("G6", "th_keyset_equals_universe")))
    # 4. G6 summary without the key set (older aggregate) -> fail closed
    b6 = cp(g678); del b6["G6"]["th_keyset"]
    cases.append(("g6_keyset_missing", None, b6, ("G6", "th_rows_unique")))
    # 5. G5 summary without the universe -> fail closed
    b5 = cp(g5); del b5["th_universe"]
    cases.append(("universe_missing", b5, None, ("G5", "th_universe_unique")))
    # 6. G7: a shard hash file with a repeated row (keyed counts unchanged)
    b6 = cp(g678); b6["G7"]["n_rows_A"] += 1
    cases.append(("g7_row_duplicate", None, b6, ("G7", "no_duplicate_rows")))
    b6 = cp(g678); del b6["G7"]["n_rows_B"]
    cases.append(("g7_rows_missing", None, b6, ("G7", "no_duplicate_rows")))
    # F8-d: every G6-G8 shard read the snapshot G5 read
    b6 = cp(g678); b6["G7"]["snapshot_manifest_sha256"] = sorted([g5["snapshot_manifest_sha256"], "6" * 64])
    cases.append(("g7_two_snapshots", None, b6, ("G7", "same_snapshot_as_g5")))
    b6 = cp(g678); b6["G7"]["snapshot_manifest_sha256"] = ["6" * 64]
    cases.append(("g7_other_snapshot", None, b6, ("G7", "same_snapshot_as_g5")))
    b5 = cp(g5); del b5["snapshot_manifest_sha256"]
    cases.append(("g5_snapshot_missing", b5, None, ("G5", "snapshot_identified")))
    out = {}
    for name, b5, b6, (gate, check) in cases:
        r = _verdict(files, b5, b6)
        assert not r["all_pass"] and not r[gate]["pass"] and not r[gate]["checks"][check], (name, r[gate])
        out[name] = f"{gate}.{check}=FAIL"
    return {"ok": True, "cases": out}


if __name__ == "__main__":
    print(run())
