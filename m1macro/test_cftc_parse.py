"""CFTC reader and pinned-root tests (Impl Part 1 V1.2 §2.3, §3)."""
import datetime as dt
import io
import zipfile

from m1macro import cftc_parse as P, tls

H = "Market_and_Exchange_Names,Report_Date_as_YYYY-MM-DD,CFTC_Contract_Market_Code,Open_Interest_All,Lev_Money_Positions_Long_All,Lev_Money_Positions_Short_All\n"


def _zip(text, members=1):
    b = io.BytesIO()
    with zipfile.ZipFile(b, "w") as z:
        for i in range(members):
            z.writestr(f"F{i}.txt", text)
    return b.getvalue()


def run():
    assert tls.check_pin().name.endswith("R46.pem")
    assert tls.context_for("https://www.cftc.gov/files/dea/history/x.zip") is not None
    assert tls.context_for("https://www.cftc.gov.evil.example/x") is None
    assert tls.context_for("https://home.treasury.gov/x") is None
    orig = tls._cfg
    try:
        tls._cfg = lambda: dict(orig(), root_sha256="00" * 32)
        try:
            tls.check_pin(); raise AssertionError("pin mismatch not detected")
        except tls.PinMismatch:
            pass
    finally:
        tls._cfg = orig
    for s, d in (("2026-10-13", dt.date(2026, 10, 13)), ("01/04/2011", dt.date(2011, 1, 4)),
                 ("1/4/2011 0:00:00", dt.date(2011, 1, 4)), ("12/28/2010 12:00:00 AM", dt.date(2010, 12, 28))):
        assert P.parse_report_date(s) == d, s
    t = H + '"JAPANESE YEN - CME",2026-10-13,097741,  373502,   65309,   98982\n"EURO FX",2026-10-13,099741,1,1,1\n' \
          + '"JAPANESE YEN - CME",2026-10-06,097741,,1,2\n'
    r = P.parse_zip(_zip(t))
    assert set(r) == {dt.date(2026, 10, 13), dt.date(2026, 10, 6)}
    assert r[dt.date(2026, 10, 13)].long == 65309 and r[dt.date(2026, 10, 13)].oi == 373502
    assert r[dt.date(2026, 10, 6)].oi is None
    old = H + '"JAPANESE YEN",12/27/2016 12:00:00 AM,097741,170000.000000,30369.000000,40000.000000\n'
    assert P.parse_zip(_zip(old))[dt.date(2016, 12, 27)].long == 30369
    try:
        P.parse_zip(_zip(H + '"JPY",2026-10-13,097741,1,1.5,1\n')); raise AssertionError("fraction accepted")
    except P.ParseFailure:
        pass               # -> TOTAL_OI_MISSING downstream
    for bad in (H + '"JPY",2026-10-13,097741,1,1,1\n"JPY",2026-10-13,097741,1,1,1\n',   # duplicate date
                H.replace("Lev_Money_Positions_Short_All", "X") + '"JPY",2026-10-13,097741,1,1,1\n',  # missing column
                H + '"JPY",2026-10-13,097741,1,,1\n'):                                  # missing positions
        try:
            P.parse_zip(_zip(bad)); raise AssertionError("bad file accepted")
        except P.ParseFailure:
            pass
    try:
        P.parse_zip(_zip(t, members=2)); raise AssertionError("two members accepted")
    except P.ParseFailure:
        pass
    return {"ok": True}
