#!/usr/bin/env python3
"""Own tally: CCDI investigation announcements held in the corpus, by year.

Counts DISTINCT title subjects of the standard CCDI announcement headline

    <post><name>接受中央纪委国家监委(纪律)审查(和监察)调查

over `documents.title` (LIKE, so no FTS blind spot). This is a tally of what the
corpus HOLDS, not of what the CCDI published: no ccdi.gov.cn site is crawled, so
every hit is a reprint on a media or government mirror. Compare it with the
official 中管干部 aggregates in data/purges/officials.json (ladder) to see the
undercount; never add the two.

Read-only. Run on the droplet:

    ssh root@104.236.88.45 'cd /root/china-governance && .venv/bin/python3 -' \
        < scripts/rnd/purges/tally_announcements.py
"""
import collections
import json
import re
import sqlite3
import sys

DB = sys.argv[1] if len(sys.argv) > 1 else "documents.db"
HEAD = re.compile(r"^(?P<subj>.{2,60}?)(?:涉嫌严重违纪违法)?[，,]?(?:目前)?(?:正)?接受中央纪委国家监委"
                  r"(?:纪律)?审查(?:和监察)?调查")


def main():
    c = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    rows = c.execute(
        "SELECT id, site_key, substr(date_published,1,4), title FROM documents "
        "WHERE title LIKE '%接受中央纪委国家监委%调查%'").fetchall()
    by_year = collections.defaultdict(dict)
    for i, site, year, title in rows:
        t = re.sub(r"\s+", "", title or "")
        t = re.sub(r"^[^｜|丨:：]{0,12}[｜|丨:：]", "", t)      # "快讯｜", "打虎！" style prefixes
        m = HEAD.match(t)
        if not m:
            continue
        subj = m.group("subj")
        by_year[year or "undated"].setdefault(subj, []).append([i, site])
    out = {y: {"distinct_subjects": len(s), "subjects": {k: v[:3] for k, v in sorted(s.items())}}
           for y, s in sorted(by_year.items())}
    print(json.dumps({"n_title_rows": len(rows), "by_year": out}, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
