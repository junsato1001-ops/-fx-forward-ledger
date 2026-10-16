#!/usr/bin/env python3
"""Calendar Gate builder: BOJ / FOMC point-in-time meeting-schedule event log.

Inputs : excerpt JSON files produced by tools/gate/extract_pages.py on branch gate-work
         (path given as argv[1], e.g. a clone of branch gate-work, folder 'calendar').
Outputs: gate/calendar_event_log.csv, gate/calendar_gate_summary.json (argv[2] = repo root).

Only meeting dates and announcement dates are handled (no market values; Performance Seal).

Rules (CALENDAR_GATE_PLAN, approved by むすび 2026-10-17 02:19 JST):
  R1 announcement with known time  -> effective from first T_info (Origin 03:00 JST) >= that time
     announcement with date only     -> effective from first T_info after the END of that date
                                        in the source's local time zone (never the same-day Origin)
  R2 unscheduled meetings / conference calls without a pre-announcement -> recorded as facts;
     effective (as 'known to have happened') only after the end of the meeting day.
  R3 BOJ periods without the schedule document -> RULE_RECONSTRUCTED from the documented
     publication rule + actual dates + documented change notices; else GAP.
  R4 every actual meeting is reconciled with the schedule known before it; unexplained -> GAP.
"""
import csv, datetime as dt, glob, hashlib, json, os, re, sys, unicodedata
from zoneinfo import ZoneInfo

SRC = sys.argv[1]
OUT = sys.argv[2]
JST = ZoneInfo("Asia/Tokyo"); ET = ZoneInfo("America/New_York")
TINFO = dt.time(3, 0)
MONTHS = {m: i for i, m in enumerate(["january", "february", "march", "april", "may", "june", "july", "august",
                                      "september", "october", "november", "december"], 1)}
MABBR = {"jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6, "jul": 7, "aug": 8, "sep": 9, "sept": 9,
         "oct": 10, "nov": 11, "dec": 12}

# ---------------------------------------------------------------- helpers
_pages = {}
def page(url):
    if url in _pages:
        return _pages[url]
    best = None
    for f in glob.glob(os.path.join(SRC, "*", "*.json")):
        if f.endswith("_manifest.json"):
            continue
        d = json.load(open(f, encoding="utf-8"))
        if d.get("url") == url and d.get("bytes", 0) > 0:
            if best is None or len(d.get("text_lines", [])) > len(best.get("text_lines", [])):
                best = d
    if best is None:
        raise KeyError(url)
    _pages[url] = best
    return best

def eff_from(ann_date, ann_time, tz):
    """First Origin date (JST) whose T_info (03:00 JST) is at/after the announcement."""
    if ann_time is not None:
        t = dt.datetime.combine(ann_date, ann_time, tz)
    else:
        t = dt.datetime.combine(ann_date + dt.timedelta(days=1), dt.time(0, 0), tz)
    tj = t.astimezone(JST)
    d = tj.date()
    if tj.time() > TINFO:
        d += dt.timedelta(days=1)
    return d

def after_day(day, tz):
    return eff_from(day, None, tz)

def nz(s):
    s = unicodedata.normalize("NFKC", s)
    s = re.sub(r"(?<=\d)\s+(?=\d)", "", s)
    return s

ROWS = []
def add(**k):
    base = dict(Central_Bank="", Announcement_Date="", Announcement_Time="", Effective_From_Tinfo="",
                Event_Type="", Old_Meeting_Start="", Old_Meeting_End="", New_Meeting_Start="", New_Meeting_End="",
                Actual_Start="", Actual_End="", Reconstruction_Status="", Source_URL="", Source_SHA256="", Note="")
    base.update({a: (b.isoformat() if isinstance(b, (dt.date, dt.time)) else (b if b is not None else "")) for a, b in k.items()})
    ROWS.append(base)

# ================================================================ FOMC
FED = "https://www.federalreserve.gov"
def fed_ranges(text, year):
    """Parse 'January 29-30', 'April 30-May 1', 'Tuesday, January 26, and Wednesday, January 27',
    'January 31-February 1, 2017', 'March 18' -> (start, end)."""
    t = text.replace("–", "-").replace(" - ", "-")
    m = re.match(r"^(?:\w+day,\s*)?([A-Za-z]+)\s+(\d{1,2}),?\s*(?:and\s+\w+day,\s*([A-Za-z]+)\s+(\d{1,2}))?(?:,\s*(\d{4}))?", t)
    m2 = re.match(r"^([A-Za-z]+)\s+(\d{1,2})\s*-\s*(?:([A-Za-z]+)\s+)?(\d{1,2})(?:,\s*(\d{4}))?", t)
    if m2 and m2.group(1).lower() in MONTHS:
        y = int(m2.group(5)) if m2.group(5) else year
        m_a = MONTHS[m2.group(1).lower()]; m_b = MONTHS[m2.group(3).lower()] if m2.group(3) else m_a
        return dt.date(y, m_a, int(m2.group(2))), dt.date(y, m_b, int(m2.group(4)))
    if m and m.group(1).lower() in MONTHS:
        y = int(m.group(5)) if m.group(5) else year
        a = dt.date(y, MONTHS[m.group(1).lower()], int(m.group(2)))
        b = dt.date(y, MONTHS[m.group(3).lower()], int(m.group(4))) if m.group(3) else a
        return a, b
    return None

FED_SCHED = [  # (url, release date, release time ET or None, schedule year)
    (FED + "/boarddocs/press/general/1998/199809292/default.htm", "1998-09-29", None, 1999),
    (FED + "/boarddocs/press/general/2001/20010716/default.htm", "2001-07-16", None, 2002),
    (FED + "/boarddocs/press/monetary/2002/20020705/default.htm", "2002-07-05", None, 2003),
    (FED + "/boarddocs/press/monetary/2003/20030610/default.htm", "2003-06-10", None, 2004),
    (FED + "/boarddocs/press/monetary/2004/20040625/default.htm", "2004-06-25", None, 2005),
    (FED + "/boarddocs/press/monetary/2005/20050629/default.htm", "2005-06-29", None, 2006),
    (FED + "/newsevents/pressreleases/monetary20060720b.htm", "2006-07-20", None, 2007),
    (FED + "/newsevents/pressreleases/monetary20070601b.htm", "2007-06-01", None, 2008),
    (FED + "/newsevents/pressreleases/monetary20080603b.htm", "2008-06-03", None, 2009),
    (FED + "/newsevents/pressreleases/monetary20090604a.htm", "2009-06-04", "10:00", 2010),
    (FED + "/newsevents/pressreleases/monetary20100528b.htm", "2010-05-28", "10:00", 2011),
    (FED + "/newsevents/pressreleases/monetary20110325a.htm", "2011-03-25", "16:00", 2012),
    (FED + "/newsevents/pressreleases/monetary20120516b.htm", "2012-05-16", "14:00", 2012),  # revised 2012 + 2013
    (FED + "/newsevents/pressreleases/monetary20130405a.htm", "2013-04-05", "11:30", 2014),
    (FED + "/newsevents/pressreleases/monetary20140605b.htm", "2014-06-05", "14:00", 2015),
    (FED + "/newsevents/pressreleases/monetary20150511a.htm", "2015-05-11", "10:30", 2016),
    (FED + "/newsevents/pressreleases/monetary20160628a.htm", "2016-06-28", "14:00", 2017),
    (FED + "/newsevents/pressreleases/monetary20170511b.htm", "2017-05-11", "14:00", 2018),
    (FED + "/newsevents/pressreleases/monetary20180525a.htm", "2018-05-25", "12:00", 2019),
    (FED + "/newsevents/pressreleases/monetary20190517a.htm", "2019-05-17", "10:00", 2020),
    (FED + "/newsevents/pressreleases/monetary20200702a.htm", "2020-07-02", "10:00", 2021),
    (FED + "/newsevents/pressreleases/monetary20210604a.htm", "2021-06-04", "11:00", 2022),
    (FED + "/newsevents/pressreleases/monetary20220624a.htm", "2022-06-24", "14:00", 2023),
    (FED + "/newsevents/pressreleases/monetary20230623a.htm", "2023-06-23", "11:30", 2024),
    (FED + "/newsevents/pressreleases/monetary20240809a.htm", "2024-08-09", "13:30", 2025),  # 2025 and 2026
    (FED + "/newsevents/pressreleases/monetary20250905a.htm", "2025-09-05", "13:30", 2027),
]
# Documented changes to a previously announced FOMC schedule (read from the cited releases).
FED_CHANGES = [
    ("2005-09-09", None, "MEETING_SHORTENED", ("2006-01-31", "2006-02-01"), ("2006-01-31", "2006-01-31"),
     FED + "/boarddocs/press/monetary/2005/20050909/default.htm"),
    ("2006-02-08", None, "MEETING_EXTENDED", ("2006-03-28", "2006-03-28"), ("2006-03-27", "2006-03-28"),
     FED + "/newsevents/pressreleases/monetary20060208a.htm"),
    ("2006-07-20", None, "MEETING_EXTENDED", ("2006-10-24", "2006-10-24"), ("2006-10-24", "2006-10-25"),
     FED + "/newsevents/pressreleases/monetary20060720b.htm"),
    ("2008-11-20", "14:00", "MEETING_EXTENDED", ("2008-12-16", "2008-12-16"), ("2008-12-15", "2008-12-16"),
     FED + "/newsevents/pressreleases/monetary20081120a.htm"),
    ("2009-02-13", "10:00", "MEETING_EXTENDED", ("2009-03-17", "2009-03-17"), ("2009-03-17", "2009-03-18"),
     FED + "/newsevents/pressreleases/monetary20090213a.htm"),
    ("2009-02-13", "10:00", "MEETING_EXTENDED", ("2009-08-11", "2009-08-11"), ("2009-08-11", "2009-08-12"),
     FED + "/newsevents/pressreleases/monetary20090213a.htm"),
    ("2009-02-13", "10:00", "MEETING_EXTENDED", ("2009-09-22", "2009-09-22"), ("2009-09-22", "2009-09-23"),
     FED + "/newsevents/pressreleases/monetary20090213a.htm"),
    ("2009-02-13", "10:00", "MEETING_EXTENDED", ("2009-12-15", "2009-12-15"), ("2009-12-15", "2009-12-16"),
     FED + "/newsevents/pressreleases/monetary20090213a.htm"),
    ("2020-03-15", "17:00", "MEETING_CANCELLED", ("2020-03-17", "2020-03-18"), (None, None),
     FED + "/newsevents/pressreleases/monetary20200315a.htm"),
    # September 2011: no release found; first public evidence = minutes of Aug 9 (released 2011-08-30 14:00 ET)
    ("2011-08-30", "14:00", "MEETING_EXTENDED", ("2011-09-20", "2011-09-20"), ("2011-09-20", "2011-09-21"),
     FED + "/monetarypolicy/fomcminutes20110809.htm"),
    ("2012-05-16", "14:00", "MEETING_EXTENDED", ("2012-07-31", "2012-07-31"), ("2012-07-31", "2012-08-01"),
     FED + "/newsevents/pressreleases/monetary20120516b.htm"),
    ("2012-05-16", "14:00", "MEETING_EXTENDED", ("2012-09-12", "2012-09-12"), ("2012-09-12", "2012-09-13"),
     FED + "/newsevents/pressreleases/monetary20120516b.htm"),
    ("2012-05-16", "14:00", "MEETING_EXTENDED", ("2012-12-11", "2012-12-11"), ("2012-12-11", "2012-12-12"),
     FED + "/newsevents/pressreleases/monetary20120516b.htm"),
]
TODAY = dt.date(2026, 10, 17)
# Pre-announced unscheduled actions: statement release time is the first public knowledge.
FED_UNSCHED_ANN = {("2020-03-02", "2020-03-02"): ("2020-03-03", "10:00", FED + "/newsevents/pressreleases/monetary20200303a.htm"),
                   ("2020-03-15", "2020-03-15"): ("2020-03-15", "17:00", FED + "/newsevents/pressreleases/monetary20200315a.htm")}

def fed_actual():
    out = []
    for y in range(1999, 2021):
        d = page(f"{FED}/monetarypolicy/fomchistorical{y}.htm")
        for l in d["text_lines"]:
            m = re.match(r"^(.*?)\s*(\((unscheduled|cancelled)\)\s*)?(Meeting|Conference Call|Conference call)\s*-\s*(\d{4})$", l)
            if not m:
                continue
            txt = m.group(1).strip(); kind = (m.group(3) or "") + ("CALL" if "Call" in m.group(4) or "call" in m.group(4) else "MEETING")
            mm = re.match(r"^([A-Za-z]+)/([A-Za-z]+)\s+(\d+)-(\d+)$", txt)
            if mm:
                def mo(s):
                    s = s.lower(); return MONTHS.get(s) or MABBR[s[:3]]
                a = dt.date(y, mo(mm.group(1)), int(mm.group(3))); b = dt.date(y, mo(mm.group(2)), int(mm.group(4)))
            else:
                a, b = fed_ranges(txt, y)
            out.append((a, b, kind, d["url"], d["sha256"]))
    # 2021-2026 from the current calendars page (meetings already held = those with a Statement link date passed)
    d = page(FED + "/monetarypolicy/fomccalendars.htm")
    tl = d["text_lines"]; year = None
    for i, l in enumerate(tl):
        m = re.match(r"^(\d{4}) FOMC Meetings$", l)
        if m:
            year = int(m.group(1)); continue
        if year and year >= 2021 and l.lower() in MONTHS | {"apr/may": 0} or (year and year >= 2021 and re.match(r"^[A-Za-z]+/[A-Za-z]+$", l)):
            nxt = tl[i + 1] if i + 1 < len(tl) else ""
            m2 = re.match(r"^(\d{1,2})(?:-(\d{1,2}))?(\*)?(\s*\(\w+\))?", nxt)
            if not m2:
                continue
            parts = l.split("/")
            def mo(s):
                s = s.lower(); return MONTHS.get(s) or MABBR[s[:3]]
            a = dt.date(year, mo(parts[0]), int(m2.group(1)))
            b = dt.date(year, mo(parts[-1]), int(m2.group(2) or m2.group(1)))
            kind = "MEETING"
            if "unscheduled" in nxt: kind = "unscheduledMEETING"
            if "cancel" in nxt: kind = "cancelledMEETING"
            if "notation" in nxt.lower(): kind = "NOTATION"
            if b < TODAY:
                out.append((a, b, kind, d["url"], d["sha256"]))
    return out

def build_fed():
    sched = []  # (ann_date, ann_time, start, end, url, sha)
    for url, rd, rt, yr in FED_SCHED:
        d = page(url)
        lines = d.get("text_lines") or d["date_lines"]
        rdate = dt.date.fromisoformat(rd)
        seen = 0
        cur_y = yr; last_m = 0
        for l in lines:
            l = l.strip()
            if re.match(r"^(Release Date|For release|Federal|FRB|The Federal Open|Additionally|Last Update|\d{4} Monetary)", l):
                continue
            if re.match(r"^[A-Z][a-z]+ \d{2}, \d{4}$", l):   # the release-date line itself
                continue
            # 1999 release lists two columns per line: 'February 2-3 August 24'
            chunks = re.findall(r"(?:\w+day,\s*)?[A-Z][a-z]+\s+\d{1,2}(?:\s*-\s*(?:[A-Z][a-z]+\s+)?\d{1,2})?(?:,?\s*and\s+\w+day,\s*[A-Z][a-z]+\s+\d{1,2})?(?:,\s*\d{4})?", l)
            for c in chunks:
                c = c.strip()
                if c.lower().split()[0] in ("release",):
                    continue
                explicit = re.search(r",\s*\d{4}$", c) is not None
                mo = MONTHS.get(c.split()[1].rstrip(",").lower() if c.split()[0].endswith("day,") else c.split()[0].lower())
                if mo is None:
                    continue
                if not explicit and rd != "1998-09-29":   # 1999 release is printed in two columns
                    if mo < last_m:
                        cur_y += 1
                    last_m = mo
                r = fed_ranges(c, cur_y)
                if not r:
                    continue
                a, b = r
                if a <= rdate or (a.month, a.day) == (rdate.month, rdate.day):
                    continue
                sched.append((rdate, rt, a, b, url, d["sha256"])); seen += 1
        if seen < 8:
            print("WARN few dates", url, seen)
    # de-duplicate (same meeting announced twice: first announcement wins as SCHEDULE_ANNOUNCED, later ones are re-confirmations)
    first = {}
    for s in sorted(sched, key=lambda x: x[0]):
        k = (s[2], s[3])
        if k not in first:
            first[k] = s
    actual = fed_actual()
    act_by_end = {}
    for a, b, kind, u, h in actual:
        act_by_end.setdefault(b, []).append((a, b, kind, u, h))
    # apply documented changes
    changed_new = {}
    for ad, at, typ, old, new, url in FED_CHANGES:
        d = page(url); ann = dt.date.fromisoformat(ad); t = dt.time.fromisoformat(at) if at else None
        o = (dt.date.fromisoformat(old[0]), dt.date.fromisoformat(old[1]))
        n = (dt.date.fromisoformat(new[0]), dt.date.fromisoformat(new[1])) if new[0] else (None, None)
        add(Central_Bank="FOMC", Announcement_Date=ann, Announcement_Time=(at + " ET") if at else "", Effective_From_Tinfo=eff_from(ann, t, ET),
            Event_Type=typ, Old_Meeting_Start=o[0], Old_Meeting_End=o[1], New_Meeting_Start=n[0], New_Meeting_End=n[1],
            Reconstruction_Status="DIRECT_SOURCE", Source_URL=url, Source_SHA256=d["sha256"])
        changed_new[o] = (n, ann)
    # scheduled meetings
    matched = set()
    for (a, b), s in sorted(first.items()):
        ann, at, _, _, url, sha = s
        t = dt.time.fromisoformat(at) if at else None
        act = [x for x in actual if x[2] == "MEETING" and x[0] == a and x[1] == b]
        n = changed_new.get((a, b))
        if not act and n and n[0][0]:
            act = [x for x in actual if x[2] == "MEETING" and x[0] == n[0][0] and x[1] == n[0][1]]
        for x in act:
            matched.add((x[0], x[1]))
        add(Central_Bank="FOMC", Announcement_Date=ann, Announcement_Time=(at + " ET") if at else "", Effective_From_Tinfo=eff_from(ann, t, ET),
            Event_Type="SCHEDULE_ANNOUNCED", New_Meeting_Start=a, New_Meeting_End=b,
            Actual_Start=act[0][0] if act else "", Actual_End=act[0][1] if act else "",
            Reconstruction_Status="DIRECT_SOURCE", Source_URL=url, Source_SHA256=sha,
            Note="" if act or a > dt.date(2026, 10, 16) or (n and n[0][0] is None) else "SCHEDULED_NOT_FOUND_IN_ACTUAL")
    # actual events not explained by a schedule
    gaps = []
    for a, b, kind, u, h in actual:
        if kind == "MEETING" and (a, b) in matched:
            continue
        if kind == "cancelledMEETING":
            continue
        if kind in ("CALL", "unscheduledMEETING", "NOTATION"):
            pre = FED_UNSCHED_ANN.get((a.isoformat(), b.isoformat()))
            if pre:
                ad, at, url = pre; d = page(url)
                add(Central_Bank="FOMC", Announcement_Date=ad, Announcement_Time=at + " ET",
                    Effective_From_Tinfo=eff_from(dt.date.fromisoformat(ad), dt.time.fromisoformat(at), ET),
                    Event_Type="UNSCHEDULED_MEETING", Actual_Start=a, Actual_End=b, Reconstruction_Status="DIRECT_SOURCE",
                    Source_URL=url, Source_SHA256=d["sha256"], Note="statement release is the first public knowledge")
            else:
                add(Central_Bank="FOMC", Effective_From_Tinfo=after_day(b, ET),
                    Event_Type="CONFERENCE_CALL" if kind == "CALL" else "UNSCHEDULED_MEETING", Actual_Start=a, Actual_End=b,
                    Reconstruction_Status="DIRECT_SOURCE", Source_URL=u, Source_SHA256=h,
                    Note="no pre-announcement found; known only after the event (rule R2)")
            continue
        # a regular meeting with no announcement found -> GAP
        add(Central_Bank="FOMC", Event_Type="ACTUAL_MEETING_SCHEDULE_UNKNOWN", Actual_Start=a, Actual_End=b,
            Reconstruction_Status="GAP", Source_URL=u, Source_SHA256=h,
            Note="no primary-source announcement of this meeting date before it was held")
        gaps.append((a, b))
    return gaps

# ================================================================ BOJ
BOJ = "https://www.boj.or.jp"
def jdate(y, m, d):
    return dt.date(int(y), int(m), int(d))

def boj_actual():
    out = []
    for y in range(1998, 2027):
        d = page(f"{BOJ}/mopo/mpmsche_minu/minu_{y}/index.htm")
        for href, txt in d["links"]:
            t = nz(txt)
            m = re.match(r"^(\d{1,2})月(\d{1,2})日?(?:[、,]\s*(?:(\d{1,2})月)?(\d{1,2})日)?開催分", t)
            if not m:
                continue
            a = jdate(y, m.group(1), m.group(2))
            b = jdate(y, m.group(3) or m.group(1), m.group(4)) if m.group(4) else a
            out.append((a, b, href, d["sha256"]))
    # meetings of 2026 whose minutes are not out yet: from the current schedule page, held before today
    d = page(f"{BOJ}/mopo/mpmsche_minu/index.htm")
    tl = d["text_lines"]; i0 = next(i for i, l in enumerate(tl) if l.startswith("表 2026年"))
    i1 = next((i for i in range(i0 + 1, len(tl)) if tl[i].startswith("表 ")), i0 + 80)
    cells = [nz(l) for l in tl[i0:i1] if l.startswith("|")]
    for c in cells:
        m = re.match(r"^\|\s*(\d{1,2})月(\d{1,2})日\(.\)・(\d{1,2})日\(.\)", c)
        if m:
            a = jdate(2026, m.group(1), m.group(2)); b = jdate(2026, m.group(1), m.group(3))
            if b < dt.date(2026, 10, 17) and (a, b) not in {(x[0], x[1]) for x in out}:
                out.append((a, b, d["url"], d["sha256"]))
    # de-dup (corrected minutes etc.)
    seen = {}; res = []
    for x in sorted(out):
        if (x[0], x[1]) not in seen:
            seen[(x[0], x[1])] = 1; res.append(x)
    return res

def parse_boj_pdf_schedule(url, year_hint):
    """Annual schedule PDFs (2015-08 onward): the first date at the start of each data line is the meeting."""
    d = page(url); out = []
    cur_y, cur_m = year_hint, None
    for raw in d["text_lines"]:
        l = re.sub(r"\s+", "", nz(raw)).replace("<", "(").replace(">", ")").replace("･", "・")
        m = re.match(r"^(?:(\d{4})年)?(?:(\d{1,2})月)?(\d{1,2})日\(.\)・(?:(\d{1,2})月)?(\d{1,2})日\(.\)", l)
        m1 = re.match(r"^(?:(\d{4})年)?(?:(\d{1,2})月)?(\d{1,2})日\(.\)(?=\d|―|─)", l)
        if m:
            if m.group(1): cur_y = int(m.group(1))
            elif m.group(2) and cur_m is not None and int(m.group(2)) < cur_m: cur_y += 1
            if m.group(2): cur_m = int(m.group(2))
            if cur_m is None: continue
            a = jdate(cur_y, cur_m, m.group(3)); mb = int(m.group(4)) if m.group(4) else cur_m
            yb = cur_y + (1 if mb < cur_m else 0)
            b = jdate(yb, mb, m.group(5)); out.append((a, b))
            cur_m = mb
        elif m1 and cur_m is not None and not m1.group(2):
            # single-day interim meeting in the same month (pre-2016 tables: '30 日(金) 11月 25日 ...')
            a = jdate(cur_y, cur_m, m1.group(3)); out.append((a, a))
    return out, d["sha256"]

BOJ_ANNUAL = [  # (url, published (JST date), first year in doc)
    (BOJ + "/mopo/mpmsche_minu/m_ref/rel150807c.pdf", "2015-08-07", 2015),
    (BOJ + "/mopo/mpmsche_minu/m_ref/rel160729b.pdf", "2016-07-29", 2017),
    (BOJ + "/mopo/mpmsche_minu/m_ref/rel170616c.pdf", "2017-06-16", 2018),
    (BOJ + "/mopo/mpmsche_minu/m_ref/rel180731b.pdf", "2018-07-31", 2019),
    (BOJ + "/mopo/mpmsche_minu/m_ref/rel190730a.pdf", "2019-07-30", 2020),
    (BOJ + "/mopo/mpmsche_minu/m_ref/rel200715a.pdf", "2020-07-15", 2021),
    (BOJ + "/mopo/mpmsche_minu/m_ref/rel210716a.pdf", "2021-07-16", 2022),
    (BOJ + "/mopo/mpmsche_minu/m_ref/rel220721a.pdf", "2022-07-21", 2023),
    (BOJ + "/mopo/mpmsche_minu/m_ref/mref230728a.pdf", "2023-07-28", 2024),
    (BOJ + "/mopo/mpmsche_minu/m_ref/mref240731a.pdf", "2024-07-31", 2025),
    (BOJ + "/mopo/mpmsche_minu/m_ref/mref250731a.pdf", "2025-07-31", 2026),
    (BOJ + "/mopo/mpmsche_minu/m_ref/mref260731a.pdf", "2026-07-31", 2027),
]
M = BOJ + "/mopo/mpmsche_minu/m_ref/"
# Documented BOJ changes (read from the struck-through tables / notices).
BOJ_CHANGES = [
    ("2009-01-22", "SCHEDULE_CHANGED", ("2009-03-16", "2009-03-17"), ("2009-03-17", "2009-03-18"), M + "ads0122.htm"),
    ("2009-11-20", "SCHEDULE_CHANGED", ("2010-04-27", "2010-04-27"), ("2010-04-30", "2010-04-30"), M + "ads1120.htm"),
    ("2010-10-28", "SCHEDULE_CHANGED", ("2010-11-15", "2010-11-16"), ("2010-11-04", "2010-11-05"), M + "ads101028.htm"),
    ("2011-03-11", "MEETING_SHORTENED", ("2011-03-14", "2011-03-15"), ("2011-03-14", "2011-03-14"), M + "rel110311g.htm"),
    ("2019-12-19", "SCHEDULE_CHANGED", ("2020-07-21", "2020-07-22"), ("2020-07-14", "2020-07-15"), M + "rel191219a.htm"),
    ("2020-03-16", "SCHEDULE_CHANGED", ("2020-03-18", "2020-03-19"), ("2020-03-16", "2020-03-16"), M + "rel200316l.htm"),
    ("2020-04-27", "MEETING_SHORTENED", ("2020-04-27", "2020-04-28"), ("2020-04-27", "2020-04-27"), M + "rel200427a.htm"),
]
# Unscheduled meetings with a call notice (臨時招集).
BOJ_UNSCHED = [
    ("2003-03-24", "2003-03-25", M + "k030324.htm"),
    ("2008-10-14", "2008-10-14", M + "un0810d.htm"),
    ("2008-12-01", "2008-12-02", M + "un0812a.htm"),
    ("2009-12-01", "2009-12-01", M + "un0912a.htm"),
    ("2010-05-10", "2010-05-10", M + "un1005c.pdf"),
    ("2010-08-30", "2010-08-30", M + "un1008c.pdf"),
    ("2020-05-19", "2020-05-22", M + "rel200519a.pdf"),
]
# Known schedule documents inside the rule period: (url, published, window start, window end, columns per row)
D = dt.date.fromisoformat
# Schedule tables attached to notices inside the rule period.
# Old tables (1997, 2000, 2001) have irregular cells -> meeting dates transcribed by hand from the table
# (meeting column only; struck-through values in other columns are release dates).
BOJ_SNAP_MANUAL = [
    (BOJ + "/mopo/mpmdeci/mpr_1997/mpm9712a.htm", "1997-12-26", "1998-01-01", "1998-06-30",
     ["1998-01-16", "1998-02-13", "1998-02-26", "1998-03-13", "1998-03-26", "1998-04-09", "1998-04-24", "1998-05-19",
      "1998-06-12", "1998-06-25"], "Apr-Jun 1998 marked provisional (to be re-decided under the new BOJ Act)"),
    (M + "mpm0009a.htm", "2000-09-08", "2000-07-01", "2000-12-31",
     ["2000-07-17", "2000-08-11", "2000-09-14", "2000-10-13", "2000-10-30", "2000-11-17", "2000-11-30", "2000-12-15"], ""),
    (M + "mpm0104a.htm", "2001-04-03", "2001-04-01", "2001-09-30",
     ["2001-04-12/2001-04-13", "2001-04-25", "2001-05-17/2001-05-18", "2001-06-14/2001-06-15", "2001-06-28",
      "2001-07-12/2001-07-13", "2001-08-13/2001-08-14", "2001-09-18/2001-09-19"], "revised table (two-day meetings)"),
]
BOJ_SNAP_AUTO = [  # (url, published, window start, window end, ncol)  tables with regular 4-column cells
    (M + "ads0122.htm", "2009-01-22", "2009-01-01", "2009-12-31", 4),
    (M + "ads1120.htm", "2009-11-20", "2009-07-01", "2010-06-30", 4),
    (M + "ads101028.htm", "2010-10-28", "2010-07-01", "2011-06-30", 4),
]
BOJ_SNAP_PDF = [  # revised schedule PDFs: underline marks are lost; old/new pairs resolved below
    (M + "rel110314e.pdf", "2011-03-14", "2011-01-01", "2011-12-31", 2011),
    (M + "rel110804b.pdf", "2011-08-04", "2011-07-01", "2012-06-30", 2011),
]
# 2001-04-03 notice changed one-day meetings to two days (struck old dates in the meeting column).
BOJ_CHANGES += [
    ("2001-04-03", "MEETING_EXTENDED", ("2001-04-13", "2001-04-13"), ("2001-04-12", "2001-04-13"), M + "mpm0104a.htm"),
    ("2001-04-03", "MEETING_EXTENDED", ("2001-05-18", "2001-05-18"), ("2001-05-17", "2001-05-18"), M + "mpm0104a.htm"),
    ("2001-04-03", "MEETING_EXTENDED", ("2001-06-15", "2001-06-15"), ("2001-06-14", "2001-06-15"), M + "mpm0104a.htm"),
    ("2001-04-03", "SCHEDULE_CHANGED", ("2001-07-16", "2001-07-16"), ("2001-07-12", "2001-07-13"), M + "mpm0104a.htm"),
    ("2001-04-03", "SCHEDULE_CHANGED", ("2001-08-15", "2001-08-15"), ("2001-08-13", "2001-08-14"), M + "mpm0104a.htm"),
    ("2001-04-03", "MEETING_EXTENDED", ("2001-09-18", "2001-09-18"), ("2001-09-18", "2001-09-19"), M + "mpm0104a.htm"),
    ("2011-08-04", "MEETING_SHORTENED", ("2011-08-04", "2011-08-05"), ("2011-08-04", "2011-08-04"), M + "rel110804b.pdf"),
]
GAP_WINDOWS_BOJ = [
    ("2004-01-01", "2004-06-30", "2004-01-20 change notice (ads0120): the revised table is not available as text "
     "(EN page: crossed-out = dates first announced 2003-12-16); changed meetings cannot be identified", M + "ads0120.htm"),
]

def parse_snapshot(url, ncol, ystart):
    d = page(url); tl = d["text_lines"]
    i0 = next(i for i, l in enumerate(tl) if "会合開催" in l)
    toks = []
    for l in tl[i0 + 1:]:
        if "〒103-0021" in l or l.startswith("（注") or l.startswith("各公表資料") or l.startswith("第2章"):
            break
        l2 = re.sub(r"\s+", "", nz(l))
        if l2.startswith("|"):
            toks.append(["cell", l2[1:]])
        elif "~~[" in l2 and toks:
            toks[-1].append(l2)
    y = ystart; mon = None; group = []; meetings = []
    for t in toks:
        v = t[1]
        mm = re.match(r"^(?:(\d{4})年)?(\d{1,2})月$", v)
        if mm:
            if mm.group(1):
                y = int(mm.group(1))
            mon = int(mm.group(2)); group = []; continue
        if v in ("", "会合開催") or mon is None:
            continue
        group.append(t)
        if len(group) == 1:
            dm = re.match(r"^(?:(\d{1,2})月)?(\d{1,2})日\(.\)(?:・(?:(\d{1,2})月)?(\d{1,2})日\(.\))?", v)
            if dm:
                ma = int(dm.group(1) or mon); a = jdate(y, ma, dm.group(2))
                b = jdate(y, int(dm.group(3) or ma), dm.group(4)) if dm.group(4) else a
                meetings.append((a, b))
        if len(group) == ncol:
            group = []
    return meetings, d["sha256"]

def boj_rule_publications():
    """Documented publication rules -> (publication date [conservative: last day of the month], window start, window end, source)."""
    pubs = []
    # 1997-12-26: 'あらかじめ各4半期末に、翌月以降6ヶ月分' (confirmed in force by the 2000-09-08 note: Mar/Jun/Sep/Dec)
    for y in range(1998, 2008):
        for qm in (3, 6, 9, 12):
            pd = dt.date(y + (qm == 12), (qm % 12) + 1, 1) - dt.timedelta(days=1)
            if pd >= dt.date(2007, 6, 1):
                continue
            ws = pd + dt.timedelta(days=1)
            we = dt.date(ws.year + (ws.month + 6 > 12), (ws.month + 6 - 1) % 12 + 1, 1) - dt.timedelta(days=1)
            pubs.append((pd, ws, we, BOJ + "/mopo/mpmdeci/mpr_1997/mpm9712a.htm"))
    # 2007-06-08: at the June and December meetings, one year ahead (first: June 2007 -> to June 2008)
    for y in range(2007, 2015):
        for mo in (6, 12):
            pd = dt.date(y, mo, 30 if mo == 6 else 31)
            ws = pd + dt.timedelta(days=1); we = dt.date(ws.year + 1, ws.month, 1) - dt.timedelta(days=1)
            pubs.append((pd, ws, we, BOJ + "/mopo/mpmdeci/mpr_2007/mpm0706b.htm"))
    return pubs

def build_boj():
    actual = boj_actual()
    act_set = {(a, b) for a, b, _, _ in actual}
    gaps = []
    explained = set()
    changes_by_new = {}; changes_by_old = {}
    for ad, typ, old, new, url in BOJ_CHANGES:
        d = page(url); ann = D(ad)
        o = (D(old[0]), D(old[1])); n = (D(new[0]), D(new[1]))
        add(Central_Bank="BOJ", Announcement_Date=ann, Effective_From_Tinfo=eff_from(ann, None, JST), Event_Type=typ,
            Old_Meeting_Start=o[0], Old_Meeting_End=o[1], New_Meeting_Start=n[0], New_Meeting_End=n[1],
            Actual_Start=n[0] if n in act_set else "", Actual_End=n[1] if n in act_set else "",
            Reconstruction_Status="DIRECT_SOURCE", Source_URL=url, Source_SHA256=d["sha256"])
        changes_by_new[n] = (o, ann); changes_by_old[o] = (n, ann)
    for ad, md, url in BOJ_UNSCHED:
        d = page(url); a = D(md); ann = D(ad)
        hit = [x for x in actual if x[0] == a]
        add(Central_Bank="BOJ", Announcement_Date=ann, Effective_From_Tinfo=eff_from(ann, None, JST), Event_Type="UNSCHEDULED_MEETING",
            Actual_Start=hit[0][0] if hit else a, Actual_End=hit[0][1] if hit else a, Reconstruction_Status="DIRECT_SOURCE",
            Source_URL=url, Source_SHA256=d["sha256"], Note="call notice (臨時招集)" + ("" if hit else "; NOT_FOUND_IN_MINUTES_INDEX"))
        for x in hit:
            explained.add((x[0], x[1]))

    def matches_actual(m, pub):
        """A scheduled (as of pub) meeting is consistent with reality if it was held, or a documented change after pub explains it."""
        if m in act_set:
            return True
        ch = changes_by_old.get(m)
        return bool(ch and ch[1] >= pub)

    # ---- all schedule documents (snapshots): (pub, ws, we, [meetings], url, sha, note)
    snaps = []
    for url, pub, ws, we, ml, note in BOJ_SNAP_MANUAL:
        ms = []
        for x in ml:
            a, _, b = x.partition("/"); ms.append((D(a), D(b or a)))
        snaps.append((D(pub), D(ws), D(we), ms, url, page(url)["sha256"], note or "table transcribed by hand from the notice"))
    for url, pub, ws, we, ncol in BOJ_SNAP_AUTO:
        ms, sha = parse_snapshot(url, ncol, D(ws).year)
        snaps.append((D(pub), D(ws), D(we), [m for m in ms if D(ws) <= m[0] <= D(we)], url, sha, "table attached to a change notice"))
    for url, pub, ws, we, y0 in BOJ_SNAP_PDF:
        ms, sha = parse_boj_pdf_schedule(url, y0)
        ms = [m for m in ms if D(ws) <= m[0] <= D(we)]
        # same start date listed twice = old/new pair of a revision on this date: keep the one that is consistent
        res = []
        for m in ms:
            twins = [x for x in ms if x[0] == m[0] and x != m]
            if twins and m not in act_set and any(t in act_set for t in twins):
                continue
            res.append(m)
        snaps.append((D(pub), D(ws), D(we), res, url, sha, "revised schedule PDF (underline marks lost; old/new pair resolved)"))
    for url, pub, y0 in BOJ_ANNUAL:
        ms, sha = parse_boj_pdf_schedule(url, y0)
        p = D(pub); ms = [m for m in ms if m[0] > p]
        if len(ms) < 5:
            print("WARN few BOJ dates", url, len(ms))
        snaps.append((p, min(m[0] for m in ms), max(m[1] for m in ms), ms, url, sha, "annual schedule document"))
    first_direct_regime = D("2015-08-07")

    snap_conflict = {}   # actual meeting -> snapshot that contradicts it
    for p, ws, we, ms, url, sha, note in snaps:
        for m in ms:
            if m[0] <= p:
                continue
            ok = matches_actual(m, p)
            add(Central_Bank="BOJ", Announcement_Date=p, Effective_From_Tinfo=eff_from(p, None, JST), Event_Type="SCHEDULE_ANNOUNCED",
                New_Meeting_Start=m[0], New_Meeting_End=m[1], Actual_Start=m[0] if m in act_set else "", Actual_End=m[1] if m in act_set else "",
                Reconstruction_Status="DIRECT_SOURCE" if ok or m[0] >= TODAY else "GAP", Source_URL=url, Source_SHA256=sha,
                Note=note + ("" if ok or m[0] >= TODAY else "; SCHEDULED_BUT_NOT_HELD_AND_NO_CHANGE_NOTICE"))
            if not ok and m[0] < TODAY:
                gaps.append(m)
        for a, b, _, _ in actual:
            if p < a and ws <= a <= we and (a, b) not in ms and (a, b) not in explained and (a, b) not in changes_by_new:
                snap_conflict.setdefault((a, b), url)
    in_snap_before = lambda m: [s for s in snaps if s[0] < m[0] and m in s[3]]

    pubs = boj_rule_publications()
    gapw = [(D(s), D(e), n, u) for s, e, n, u in GAP_WINDOWS_BOJ]
    for a, b, href, sha in actual:
        m = (a, b)
        if m in explained:
            continue
        if m in changes_by_new and changes_by_new[m][1] <= a and a >= first_direct_regime:
            continue   # documented change (DIRECT row already written)
        gw = [g for g in gapw if g[0] <= a <= g[1]]
        if m in snap_conflict or gw:
            add(Central_Bank="BOJ", Event_Type="ACTUAL_MEETING_SCHEDULE_UNKNOWN", Actual_Start=a, Actual_End=b,
                Reconstruction_Status="GAP", Source_URL=(gw[0][3] if gw else snap_conflict[m]), Source_SHA256=sha,
                Note=(gw[0][2] if gw else "held, but a schedule table published before it shows a different date and no change notice explains it"))
            gaps.append(m); continue
        if a >= first_direct_regime:
            if not in_snap_before(m):
                add(Central_Bank="BOJ", Event_Type="ACTUAL_MEETING_SCHEDULE_UNKNOWN", Actual_Start=a, Actual_End=b,
                    Reconstruction_Status="GAP", Source_URL=href, Source_SHA256=sha, Note="held but not in any schedule document published before it")
                gaps.append(m)
            continue
        cand = [p for p in pubs if p[1] <= a <= p[2] and p[0] < a]
        if not cand:
            if not in_snap_before(m):
                add(Central_Bank="BOJ", Event_Type="ACTUAL_MEETING_SCHEDULE_UNKNOWN", Actual_Start=a, Actual_End=b,
                    Reconstruction_Status="GAP", Source_URL=href, Source_SHA256=sha, Note="no documented publication rule or document covers this date")
                gaps.append(m)
            continue
        pd, ws, we, rsrc = max(cand, key=lambda p: p[0])  # LATEST publication before the meeting (conservative)
        ch = changes_by_new.get(m)
        if ch and ch[1] > pd:
            o, ann = ch
            add(Central_Bank="BOJ", Announcement_Date=pd, Effective_From_Tinfo=eff_from(pd, None, JST), Event_Type="SCHEDULE_ANNOUNCED",
                New_Meeting_Start=o[0], New_Meeting_End=o[1], Actual_Start=a, Actual_End=b, Reconstruction_Status="RULE_RECONSTRUCTED",
                Source_URL=rsrc, Source_SHA256=page(rsrc)["sha256"], Note=f"date as originally scheduled; changed by notice of {ann}")
        else:
            add(Central_Bank="BOJ", Announcement_Date=pd, Effective_From_Tinfo=eff_from(pd, None, JST), Event_Type="SCHEDULE_ANNOUNCED",
                New_Meeting_Start=a, New_Meeting_End=b, Actual_Start=a, Actual_End=b, Reconstruction_Status="RULE_RECONSTRUCTED",
                Source_URL=rsrc, Source_SHA256=page(rsrc)["sha256"],
                Note="actual date taken as published at the latest rule publication before the meeting (last day of the publication month)")
    return gaps, sorted(snap_conflict)


def main():
    fed_gaps = build_fed()
    boj_gaps, snap_unexpl = build_boj()
    ROWS.sort(key=lambda r: (r["Central_Bank"], r["New_Meeting_Start"] or r["Actual_Start"] or r["Old_Meeting_Start"], r["Announcement_Date"]))
    os.makedirs(os.path.join(OUT, "gate"), exist_ok=True)
    p = os.path.join(OUT, "gate", "calendar_event_log.csv")
    with open(p, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(ROWS[0].keys()), lineterminator="\n"); w.writeheader(); w.writerows(ROWS)
    summ = {}
    for cb in ("FOMC", "BOJ"):
        rs = [r for r in ROWS if r["Central_Bank"] == cb]
        cnt = {}
        for r in rs:
            cnt[r["Reconstruction_Status"]] = cnt.get(r["Reconstruction_Status"], 0) + 1
        g = sorted((r["Actual_Start"] or r["New_Meeting_Start"], r["Actual_End"] or r["New_Meeting_End"],
                    ("[scheduled, not held] " if not r["Actual_Start"] else "") + r["Note"]) for r in rs if r["Reconstruction_Status"] == "GAP")
        last_gap = max((x[1] for x in g), default=None)
        summ[cb] = {"rows": len(rs), "status_counts": cnt,
                    "gap_meetings": [{"start": a, "end": b, "note": n} for a, b, n in g],
                    "last_gap_meeting_end": last_gap,
                    "continuous_from_origin": after_day(dt.date.fromisoformat(last_gap), ET if cb == "FOMC" else JST).isoformat() if last_gap else None,
                    "event_types": sorted({r["Event_Type"] for r in rs}),
                    "scheduled_not_found_in_actual": [(r["New_Meeting_Start"], r["New_Meeting_End"], r["Source_URL"]) for r in rs if "SCHEDULED_NOT_FOUND" in r["Note"]]}
    summ["generated_from"] = "branch gate-work calendar/*; tools/gate/calendar_build.py"
    summ["event_log_sha256"] = hashlib.sha256(open(p, "rb").read()).hexdigest()
    json.dump(summ, open(os.path.join(OUT, "gate", "calendar_gate_summary.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(json.dumps({k: (v if k in ("generated_from", "event_log_sha256") else {kk: vv for kk, vv in v.items() if kk != "gap_meetings"}) for k, v in summ.items()}, ensure_ascii=False, indent=1))

if __name__ == "__main__":
    main()
