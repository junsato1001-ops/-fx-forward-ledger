"""Development snapshot acquisition (Impl Part 1 V1.2 §6, Part 4 §4, §8).

Fetches the full history of the three sources once:
  U.S. Treasury daily par yield curve, every year file 1990..current -> private storage only (raw bytes)
  MOF jgbcm_all.csv + jgbcm.csv                                      -> public
  CFTC fin_fut_txt_2006_2016.zip + fut_fin_txt_2017..current.zip     -> public
mode 'check': fetch and validate, write metadata only (no raw bytes anywhere; Treasury header/metadata only).
mode 'acquire': also write raw files under <out>/public and <out>/private for the workflow to commit.
"""
import datetime as dt
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from m1macro import cftc_parse, rates, sources as S  # noqa: E402


def plan(today: dt.date):
    out = [("treasury", f"treasury/daily_treasury_yield_curve_{y}.csv", S.treasury_url(y))
           for y in range(S.TREASURY_FIRST_YEAR, today.year + 1)]
    out += [("mof", "mof/jgbcm_all.csv", S.MOF_ALL), ("mof", "mof/jgbcm.csv", S.MOF_CURRENT)]
    out += [("cftc", "cftc/fin_fut_txt_2006_2016.zip", S.CFTC_2006_2016)]
    out += [("cftc", f"cftc/fut_fin_txt_{y}.zip", S.cftc_year_url(y)) for y in range(2017, today.year + 1)]
    return out


def validate(src, b):
    if src == "treasury":
        s = rates.parse_treasury_csv(b)
        return {"n_dates": len(s), "min": str(min(s)) if s else "", "max": str(max(s)) if s else ""}
    if src == "mof":
        s = rates.parse_mof_csv(b)
        return {"n_dates": len(s), "min": str(min(s)), "max": str(max(s))}
    r = cftc_parse.parse_zip(b)
    return {"n_reports": len(r), "min": str(min(r)), "max": str(max(r)),
            "oi_missing": sum(1 for x in r.values() if x.oi is None), "oi_zero": sum(1 for x in r.values() if x.oi == 0)}


CANONICAL_MANIFEST = "data/m1macro/dev_snapshot/manifest.json"   # canonical one-shot snapshot (むすび 2026-10-18)


class SnapshotExists(Exception):
    pass


def main(outdir, mode, today=None):
    if mode == "acquire" and (Path(__file__).resolve().parent.parent / CANONICAL_MANIFEST).exists():
        raise SnapshotExists("CANONICAL_SNAPSHOT_EXISTS")   # one-shot guard (the workflow also checks main + private)
    today = today or dt.datetime.now(dt.timezone.utc).date()
    out = Path(outdir); recs = []; ok = True
    for src, rel, url in plan(today):
        rec = {"source": src, "path": rel, "url": url}
        try:
            f = S.fetch_retry(url)
            rec.update(retrieved_at_utc=f["retrieved_at_utc"], bytes=f["n"], sha256=f["sha256"])
            try:
                rec["check"] = validate(src, f["b"])
            except Exception as e:
                rec["check_error"] = type(e).__name__; ok = False   # no message text (may quote values)
            if mode == "acquire":
                dest = out / ("private" if src == "treasury" else "public") / rel
                dest.parent.mkdir(parents=True, exist_ok=True); dest.write_bytes(f["b"])
        except S.FetchFailure as e:
            rec["fetch_error"] = str(e); ok = False
        recs.append(rec)
    man = {"format": "M1MACRO_DEV_SNAPSHOT_V1", "mode": mode, "ok": ok, "files": recs}
    (out / "dev_snapshot_manifest.json").write_text(json.dumps(man, indent=1, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({"ok": ok, "n_files": len(recs), "errors": [r["path"] for r in recs if "fetch_error" in r or "check_error" in r]}))
    return ok


if __name__ == "__main__":
    sys.exit(0 if main(sys.argv[1], sys.argv[2]) else 1)
