#!/usr/bin/env python3
"""Gate helper: fetch central-bank schedule/announcement pages (calendar metadata only).

Only for FOMC / BOJ meeting-schedule pages (Matrix C7). Never use it for candidate
value series (rates, positions, prices). Pages are saved to an Actions artifact, not
committed; a manifest with URL, HTTP status, bytes and SHA-256 is printed.
Usage: fetch_pages.py OUTDIR URL [URL ...]   (or URLs one per line in env PAGES)
"""
import hashlib, os, re, sys, time, urllib.request
out = sys.argv[1]
urls = sys.argv[2:] or [u.strip() for u in os.environ.get("PAGES", "").split() if u.strip()]
ALLOW = ("https://www.federalreserve.gov/", "https://www.boj.or.jp/")
os.makedirs(out, exist_ok=True)
with open(os.path.join(out, "manifest.tsv"), "w") as m:
    for u in urls:
        if not u.startswith(ALLOW):
            print("SKIP (not a calendar source)", u); continue
        fn = re.sub(r"[^A-Za-z0-9._-]", "_", u.split("://", 1)[1])
        try:
            r = urllib.request.urlopen(urllib.request.Request(u, headers={"User-Agent": "fx-forward-ledger gate (research)"}), timeout=60)
            b = r.read(); st = r.status
        except Exception as e:
            b = b""; st = repr(e)[:80]
        open(os.path.join(out, fn), "wb").write(b)
        line = f"{u}\t{st}\t{len(b)}\t{hashlib.sha256(b).hexdigest()}\t{fn}"
        m.write(line + "\n"); print(line)
        time.sleep(1.0)
