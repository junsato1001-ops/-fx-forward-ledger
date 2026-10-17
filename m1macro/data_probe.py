"""Format probe of the official source files (headers, encodings, date ranges). Input inspection only
(Impl Part 1 V1.1 §9). U.S. Treasury: header and metadata only (raw bytes are not redistributed, §4)."""
import csv
import hashlib
import io
import json
import sys
import time
import urllib.request
import zipfile
from pathlib import Path

UA = {"User-Agent": "fx-forward-ledger research (github.com/junsato1001-ops)"}
SRC = {
    "treasury_2026": "https://home.treasury.gov/resource-center/data-chart-center/interest-rates/daily-treasury-rates.csv/2026/all?type=daily_treasury_yield_curve&field_tdr_date_value=2026&page&_format=csv",
    "treasury_2010": "https://home.treasury.gov/resource-center/data-chart-center/interest-rates/daily-treasury-rates.csv/2010/all?type=daily_treasury_yield_curve&field_tdr_date_value=2010&page&_format=csv",
    "mof_all": "https://www.mof.go.jp/jgbs/reference/interest_rate/data/jgbcm_all.csv",
    "mof_current": "https://www.mof.go.jp/jgbs/reference/interest_rate/jgbcm.csv",
    "cftc_2026": "https://www.cftc.gov/files/dea/history/fut_fin_txt_2026.zip",
    "cftc_schedule": "https://www.cftc.gov/MarketReports/CommitmentsofTraders/ReleaseSchedule/index.htm",
}


def _ctx(url, outdir):
    import ssl
    if "cftc.gov" not in url:
        return None
    ctx = ssl.create_default_context()
    pem = Path(outdir, "R46_from_host.pem")
    if pem.exists():
        ctx.load_verify_locations(cafile=str(pem))
    return ctx


def get(url, outdir="out"):
    t0 = time.time()
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=120, context=_ctx(url, outdir)) as r:
        b = r.read(); st = r.status; ct = r.headers.get("Content-Type")
    return b, st, ct, round(time.time() - t0, 1)


def main(outdir):
    out = {}
    for k, u in SRC.items():
        try:
            b, st, ct, sec = get(u, outdir)
            rec = {"url": u, "http": st, "content_type": ct, "bytes": len(b), "sha256": hashlib.sha256(b).hexdigest(), "sec": sec}
            if k.startswith("treasury"):
                txt = b.decode("utf-8-sig", errors="replace").splitlines()
                rec.update(header=txt[0] if txt else "", n_lines=len(txt),
                           first_col_first=(txt[1].split(",")[0] if len(txt) > 1 else ""),
                           first_col_last=(txt[-1].split(",")[0] if len(txt) > 1 else ""))
            elif k.startswith("mof"):
                for enc in ("shift_jis", "cp932", "utf-8"):
                    try:
                        txt = b.decode(enc).splitlines(); rec["encoding"] = enc; break
                    except UnicodeDecodeError:
                        continue
                rec.update(head=txt[:4], tail=txt[-3:], n_lines=len(txt))
            elif k.startswith("cftc_2026"):
                z = zipfile.ZipFile(io.BytesIO(b)); rec["members"] = z.namelist()
                raw = z.read(z.namelist()[0]).decode("utf-8", errors="replace")
                rd = list(csv.reader(io.StringIO(raw)))
                hdr = rd[0]; rec["header"] = hdr
                jp = [r for r in rd[1:] if len(r) > 3 and "097741" in r]
                rec["jpy_rows"] = len(jp)
                rec["jpy_sample"] = [dict(zip(hdr, r)) for r in jp[:2]]
                rec["n_rows"] = len(rd) - 1
            else:
                t = b.decode("utf-8", errors="replace")
                import re
                i = t.find("Release Schedule")
                rec["text_sample"] = re.sub(r"<[^>]+>", " ", t[i:i + 6000])[:3000]
            out[k] = rec
        except Exception as e:
            out[k] = {"url": u, "error": repr(e)}
    Path(outdir, "data_probe.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({k: (v.get("http"), v.get("bytes"), v.get("error")) for k, v in out.items()}))


if __name__ == "__main__":
    main(sys.argv[1])
