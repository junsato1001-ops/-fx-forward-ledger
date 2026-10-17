#!/usr/bin/env python3
"""Data Implementation Gate: CFTC TFF metadata only (M1-MACRO-DATA-AVAILABILITY-V1 sec.3).

Reads ONLY these columns of the CFTC Traders in Financial Futures annual text files:
market/exchange name, contract market code, report date. Position columns are never
parsed, stored or printed (PERFORMANCE_SEAL / no candidate values before the
Transformation Spec is frozen). Report dates are NOT publication dates.
Output: gate/cftc_tff_jpy_metadata.json
"""
import csv, hashlib, io, json, sys, urllib.request, zipfile, datetime as dt
from pathlib import Path

BASE = "https://www.cftc.gov/files/dea/history/"
FILES = ["fin_fut_txt_2006_2016.zip"] + [f"fut_fin_txt_{y}.zip" for y in range(2010, dt.date.today().year + 1)]
OUT = Path(__file__).resolve().parents[2] / "gate" / "cftc_tff_jpy_metadata.json"

def col(header, *keys):
    for h in header:
        n = h.strip().lower()
        if all(k in n for k in keys):
            return h
    raise KeyError(keys)

def main():
    res = {"generated_utc": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
           "note": "metadata only; report dates are not publication dates", "files": {}}
    for fn in FILES:
        url = BASE + fn
        try:
            b = urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "fx-forward-ledger gate"}), timeout=120).read()
        except Exception as e:
            res["files"][fn] = {"error": repr(e)[:200]}
            continue
        info = {"url": url, "zip_sha256": hashlib.sha256(b).hexdigest(), "members": {}}
        z = zipfile.ZipFile(io.BytesIO(b))
        for m in z.namelist():
            text = z.read(m).decode("latin-1")
            r = csv.reader(io.StringIO(text))
            header = next(r)
            cn = col(header, "market", "exchange"); cc = col(header, "contract", "code"); cd = col(header, "report_date")
            i_n, i_c, i_d = header.index(cn), header.index(cc), header.index(cd)
            groups = {}
            nrows = 0
            for row in r:
                nrows += 1
                name, code, d = row[i_n].strip(), row[i_c].strip(), row[i_d].strip()[:10]
                if "YEN" in name.upper() or code == "097741":
                    g = groups.setdefault((code, name), [])
                    g.append(d)
            info["members"][m] = {"rows_total": nrows, "header_columns_used": [cn, cc, cd], "n_header_columns": len(header),
                                  "jpy_like_contracts": [{"code": k[0], "name": k[1], "n_reports": len(v), "n_unique_report_dates": len(set(v)),
                                                          "first_report_date": min(v), "last_report_date": max(v), "report_dates": sorted(set(v))}
                                                         for k, v in sorted(groups.items())]}
        res["files"][fn] = info
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    for fn, i in res["files"].items():
        if "error" in i:
            print(fn, "ERROR", i["error"])
            continue
        for m, mi in i["members"].items():
            for c in mi["jpy_like_contracts"]:
                print(fn, m, c["code"], c["name"], c["n_reports"], c["first_report_date"], c["last_report_date"])

if __name__ == "__main__":
    main()
