"""Reconstruction-period pipeline (Impl Part 1 §6, Part 3 §4, Part 4 §5 G5-G8): development snapshot ->
point-in-time features -> S0 rows/pools (frozen, SHA-checked) -> E_{t,h} for every (t, h)."""
import datetime as dt
import hashlib
import json
from pathlib import Path

from m1macro import cftc_parse, estimation as E, features, rates, s0link
from m1macro.forecast import n_of

HORIZONS = ("1D", "1W", "4W")


class SnapshotMismatch(Exception):
    pass


def load_dev_snapshot(manifest_path, public_dir, private_dir):
    """Read the development snapshot; every file's SHA-256 must equal the manifest (else PIPELINE_FAILURE)."""
    man = json.loads(Path(manifest_path).read_text("utf-8"))
    us_parts, jp_parts, reports = [], [], {}
    for f in man["files"]:
        base = Path(private_dir if f["source"] == "treasury" else public_dir)
        b = (base / f["path"]).read_bytes()
        if hashlib.sha256(b).hexdigest() != f["sha256"] or len(b) != f["bytes"]:
            raise SnapshotMismatch(f["path"])
        if f["source"] == "treasury":
            us_parts.append(rates.parse_treasury_csv(b))
        elif f["source"] == "mof":
            jp_parts.append(rates.parse_mof_csv(b))
        else:
            for d, r in cftc_parse.parse_zip(b).items():
                if d in reports and reports[d] != r:
                    raise cftc_parse.ParseFailure(f"overlapping CFTC files disagree on {d}")
                reports[d] = r
    return rates.merge(*us_parts), rates.merge(*jp_parts), reports, man


class Context:
    def __init__(self, tmpdir, us, jp, reports):
        rows, outputs, pools = s0link.reconstruct(tmpdir)
        self.opp = {(r["Pair"], r["Origin"], r["Horizon"]): r for r in rows if r["Pair"] in E.DEV_PAIRS}
        self.s0 = {(r["Pair"], r["Origin"], r["Horizon"]): r for r in outputs if r["Pair"] in E.DEV_PAIRS}
        if any(k[0] in E.HOLDOUT_PAIRS for k in list(self.opp) + list(self.s0)):
            raise E.HoldoutBreach("holdout in reconstruction")
        self.pools = pools
        origins = sorted({dt.date.fromisoformat(k[1]) for k in self.opp})
        self.feats = features.historical_table(origins, us, jp, reports)
        self.recs = {h: E.static_groups(h, self.opp, self.s0, self.feats, pools) for h in HORIZONS}
        self.th = []
        for h in HORIZONS:
            for t in sorted({k[1] for k in self.opp if k[2] == h}):
                lafs = {self.opp[(p, t, h)]["Last_Available_Fix"] for p in E.DEV_PAIRS if (p, t, h) in self.opp} - {""}
                if len(lafs) > 1:
                    raise s0link.PipelineFailure("LAF_DIFFERS_ACROSS_PAIRS")
                self.th.append((t, h, lafs.pop() if lafs else ""))   # "" -> no pair applicable -> NOT_EVALUATED

    def eligible_pairs(self, t, h):
        """Pairs that pass Part 3 §3 steps 1-7 at (t, h) in the reconstruction (issued; S0 FORECAST; N(p) OK)."""
        out = []
        f = self.feats.get(t)
        for p in E.DEV_PAIRS:
            s = self.s0.get((p, t, h))
            if s is None or s.get("Decision_Class") != "FORECAST" or f is None:
                continue
            if all(f[k][0] == "OK" for k in n_of(p)):
                out.append(p)
        return out

    def e_input(self, t, h, laf):
        return E.assemble_from(self.recs[h], t, h, laf)
