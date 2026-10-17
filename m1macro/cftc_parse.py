"""CFTC TFF Futures Only annual file reader (Impl Part 1 V1.2 §2.3). Column names fixed in config."""
import csv
import datetime as dt
import io
import json
import zipfile
from pathlib import Path

from m1macro.cftc_feature import Report

HERE = Path(__file__).resolve().parent


class ParseFailure(Exception):
    pass


def cols():
    return json.loads((HERE / "config" / "m1macro_config.json").read_text("utf-8"))["cftc_columns"]


def parse_report_date(s: str) -> dt.date:
    s = s.strip()
    if len(s) == 10 and s[4] == "-":
        return dt.date.fromisoformat(s)
    d = s.split(" ")[0]                  # 'M/D/YYYY 0:00:00' or 'MM/DD/YYYY'
    m, dd, y = d.split("/")
    return dt.date(int(y), int(m), int(dd))


def _int(s):
    s = (s or "").strip()
    if s in ("", "."):
        return None
    return int(s)


def parse_text(text: str, c=None) -> dict:
    c = c or cols()
    rd = csv.reader(io.StringIO(text))
    header = [h.strip() for h in next(rd)]
    date_col = next((d for d in c["report_date_candidates"] if d in header), None)
    need = [c["contract_code"], c["lev_long"], c["lev_short"], c["open_interest"]]
    missing = [n for n in need if n not in header]
    if date_col is None or missing:
        raise ParseFailure(f"missing columns {missing or 'report date'}")
    ix = {n: header.index(n) for n in need + [date_col]}
    out = {}
    for row in rd:
        if not row or len(row) < len(header):
            if row and any(x.strip() for x in row):
                raise ParseFailure("short row")
            continue
        if row[ix[c["contract_code"]]].strip() != c["contract_code_value"]:
            continue
        d = parse_report_date(row[ix[date_col]])
        if d in out:
            raise ParseFailure(f"duplicate report date {d}")
        lo, sh = _int(row[ix[c["lev_long"]]]), _int(row[ix[c["lev_short"]]])
        if lo is None or sh is None:
            raise ParseFailure(f"missing leveraged positions {d}")
        out[d] = Report(d, lo, sh, _int(row[ix[c["open_interest"]]]))
    return out


def parse_zip(b: bytes, c=None) -> dict:
    with zipfile.ZipFile(io.BytesIO(b)) as z:
        names = [n for n in z.namelist() if not n.endswith("/")]
        if len(names) != 1:
            raise ParseFailure(f"expected one member, got {len(names)}")
        raw = z.read(names[0])
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = raw.decode("latin-1")
    return parse_text(text, c)
