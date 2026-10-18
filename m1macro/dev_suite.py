"""Development suite entry point: python -I -m m1macro.dev_suite <outdir>. Synthetic only."""
import json
import sys
import time
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def main(outdir):
    out = Path(outdir); out.mkdir(parents=True, exist_ok=True)
    results = {}
    for name in ("test_canon", "test_cftc_rules", "test_cftc_feature", "test_rates", "test_s0link", "test_forecast", "test_cftc_parse", "test_cftc_schedule", "test_features", "test_ledger_tx", "test_gitrepo_tx", "test_forward_commit", "test_deadline_gate", "test_manifest_gate", "test_freeze_gate", "test_freeze_record", "test_estimation", "test_reconstruct", "test_forward_run", "test_solver", "test_fullscale", "test_indep", "test_indep_stall", "test_indep_structured"):
        t0 = time.time()
        try:
            mod = __import__(f"m1macro.{name}", fromlist=["run"])
            results[name] = {"status": "PASS", "detail": mod.run(), "sec": round(time.time() - t0, 2)}
        except Exception:
            results[name] = {"status": "FAIL", "trace": traceback.format_exc()[-3000:]}
    (out / "suite.json").write_text(json.dumps(results, indent=1, sort_keys=True), encoding="utf-8")
    print(json.dumps({k: v["status"] for k, v in results.items()}))


if __name__ == "__main__":
    main(sys.argv[1])
