"""Official source URLs (Impl Part 1 V1.2 §2, §3) and the HTTP fetch used by every M1-MACRO run."""
import datetime as dt
import hashlib
import time
import urllib.request

from m1macro import tls

UA = {"User-Agent": "fx-forward-ledger research (github.com/junsato1001-ops)"}
TIMEOUT = 120


def treasury_url(year: int) -> str:
    return ("https://home.treasury.gov/resource-center/data-chart-center/interest-rates/daily-treasury-rates.csv/"
            f"{year}/all?type=daily_treasury_yield_curve&field_tdr_date_value={year}&page&_format=csv")


MOF_ALL = "https://www.mof.go.jp/jgbs/reference/interest_rate/data/jgbcm_all.csv"
MOF_CURRENT = "https://www.mof.go.jp/jgbs/reference/interest_rate/jgbcm.csv"
CFTC_SCHEDULE = "https://www.cftc.gov/MarketReports/CommitmentsofTraders/ReleaseSchedule/index.htm"
CFTC_2006_2016 = "https://www.cftc.gov/files/dea/history/fin_fut_txt_2006_2016.zip"
TREASURY_FIRST_YEAR = 1990


def cftc_year_url(year: int) -> str:
    return f"https://www.cftc.gov/files/dea/history/fut_fin_txt_{year}.zip"


class FetchFailure(Exception):
    pass


def fetch(url: str) -> dict:
    """Returns {url, http, bytes(b), n, sha256, retrieved_at_utc}. Raises FetchFailure (no detail from the body)."""
    try:
        req = urllib.request.Request(url, headers=UA)
        with urllib.request.urlopen(req, timeout=TIMEOUT, context=tls.context_for(url)) as r:
            b = r.read(); st = r.status
    except Exception as e:
        raise FetchFailure(type(e).__name__)
    if st != 200:
        raise FetchFailure(f"HTTP {st}")
    t = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return {"url": url, "http": st, "b": b, "n": len(b), "sha256": hashlib.sha256(b).hexdigest(), "retrieved_at_utc": t}


def fetch_retry(url: str, tries: int = 3, wait: float = 10.0) -> dict:
    last = None
    for i in range(tries):
        try:
            return fetch(url)
        except FetchFailure as e:
            last = e; time.sleep(wait)
    raise last
