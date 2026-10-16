#!/usr/bin/env python3
"""Gate helper: fetch FOMC/BOJ schedule pages and keep only factual metadata excerpts:
page title, links (href + anchor text), and text lines containing dates. No candidate
value series are fetched (allowlist). Output JSON per page into OUTDIR."""
import hashlib, html, json, os, re, sys, time, urllib.request, urllib.parse
from html.parser import HTMLParser
ALLOW = ("https://www.federalreserve.gov/", "https://www.boj.or.jp/")
DATE = re.compile(r"(January|February|March|April|May|June|July|August|September|October|November|December|Jan\.|Feb\.|Aug\.|Sept\.|Oct\.|Nov\.|Dec\.)\s*\d|\d{4}年|\d{1,2}月\s*\d{1,2}日|\d{1,2}/\d{1,2}|\d{4}-\d{2}-\d{2}|unscheduled|Unscheduled|conference call|延期|変更|臨時")
class P(HTMLParser):
    def __init__(s):
        super().__init__(); s.links=[]; s.cur=None; s.txt=[]; s.title=""; s.intitle=False; s.skip=0
    def handle_starttag(s,t,a):
        a=dict(a)
        if t in("script","style"): s.skip+=1
        if t=="title": s.intitle=True
        if t=="a" and a.get("href"): s.cur=[a["href"],""]
        if t in("br","p","div","tr","li","h1","h2","h3","h4","td","th","table"): s.txt.append("\n")
        if t in("td","th"): s.txt.append(" | ")
    def handle_endtag(s,t):
        if t in("script","style"): s.skip-=1
        if t=="title": s.intitle=False
        if t=="a" and s.cur: s.links.append(s.cur); s.cur=None
    def handle_data(s,d):
        if s.skip: return
        if s.intitle: s.title+=d
        if s.cur is not None: s.cur[1]+=d
        s.txt.append(d)
def main():
    out=sys.argv[1]; os.makedirs(out,exist_ok=True)
    urls=[u for u in os.environ.get("PAGES","").split() if u.strip()]
    man=[]
    for u in urls:
        if not u.startswith(ALLOW): man.append({"url":u,"status":"SKIP"}); continue
        try:
            r=urllib.request.urlopen(urllib.request.Request(u,headers={"User-Agent":"fx-forward-ledger gate (research)"}),timeout=60); b=r.read(); st=r.status
        except Exception as e:
            b=b""; st=repr(e)[:100]
        enc="utf-8"
        m=re.search(rb'charset=["\']?([A-Za-z0-9_-]+)',b[:3000])
        if m: enc=m.group(1).decode()
        try: t=b.decode(enc,errors="replace")
        except LookupError: t=b.decode("utf-8",errors="replace")
        p=P(); p.feed(t)
        text="".join(p.txt)
        lines=[re.sub(r"\s+"," ",l).strip() for l in text.split("\n")]
        lines=[l for l in lines if l and DATE.search(l)]
        links=[[urllib.parse.urljoin(u,h),re.sub(r"\s+"," ",x).strip()] for h,x in p.links]
        rec={"url":u,"status":st,"bytes":len(b),"sha256":hashlib.sha256(b).hexdigest(),"title":re.sub(r"\s+"," ",p.title).strip(),"date_lines":lines,"links":links}
        fn=re.sub(r"[^A-Za-z0-9._-]","_",u.split("://",1)[1])+".json"
        json.dump(rec,open(os.path.join(out,fn),"w",encoding="utf-8"),ensure_ascii=False,indent=0)
        man.append({"url":u,"status":st,"bytes":len(b),"sha256":rec["sha256"],"file":fn})
        time.sleep(1.0)
    json.dump(man,open(os.path.join(out,"_manifest.json"),"w"),indent=1)
main()
