#!/usr/bin/env python3
"""Join China admin-divisions enumeration to our crawl coverage → completion picture.

Reads:  docs/working/china-admin-divisions.csv      (the denominator — every provincial +
                                                     prefecture-level unit of the PRC)
        docs/working/coverage-sites-snapshot.tsv    (the numerator — our crawled sites)
Writes: docs/working/china-admin-coverage.csv       (denominator + covered/our_docs/site_keys)
        + prints a covered/total + docs summary by level & type.

Matching a division to our sites: (1) name_cn (or its de-suffixed core) is a substring of
our site NAME; (2) exact pinyin(name_en) == site_key; (3) an ALIAS map for abbreviation
keys (gd=广东, hlj=黑龙江, js=江苏, zj=浙江, bj/sh/cq/sz…). "covered" = ≥1 matching site with
docs>0 — this counts a unit's OWN portal OR any sub-department/district site whose name
carries the unit name, so it means "we have SOME presence", not full coverage.

Refresh the numerator snapshot from the droplet (source of truth):
    ssh root@104.236.88.45 'cd /root/china-governance && sqlite3 -separator "|" documents.db \
      "SELECT s.site_key, s.name, s.admin_level, COALESCE(d.n,0) FROM sites s \
       LEFT JOIN (SELECT site_key, COUNT(*) n FROM documents GROUP BY site_key) d \
       ON s.site_key=d.site_key ORDER BY 4 DESC;"' > docs/working/coverage-sites-snapshot.tsv
"""
import csv, re, sys
import os
REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
SITES = f"{REPO}/docs/working/coverage-sites-snapshot.tsv"

# our covered sites: site_key|name|admin_level|docs
sites = []
for line in open(SITES, encoding="utf-8"):
    p = line.rstrip("\n").split("|")
    if len(p) >= 4:
        sites.append({"key": p[0], "name": p[1], "level": p[2], "docs": int(p[3] or 0)})

# manual aliases for abbreviation site_keys whose name lacks the Chinese string
ALIAS = {  # name_cn core -> site_key
    "北京": "bj", "上海": "sh", "天津": "tj", "重庆": "cq", "深圳": "sz",
    "广州": "gz", "西安": "xa", "连云港": "lyg", "红河": "hh", "胡杨河": "nqs",
    "阿拉尔": "ale", "北屯": "bts", "五家渠": "wjq", "潜江": "hbqj",
    "广东": "gd", "黑龙江": "hlj", "江苏": "js", "浙江": "zj",
}
KEYS = {s["key"] for s in []}  # placeholder, set below

def norm_en(s):
    return re.sub(r'[^a-z]', '', s.lower())
SUFFIX = re.compile(r'(市|省|自治区|自治州|地区|盟|林区|特别行政区|回族|藏族|壮族|维吾尔|蒙古|哈萨克|朝鲜族|傣族|白族|彝族|苗族|侗族|羌族|柯尔克孜|土家族)+$')

def core(name):
    return SUFFIX.sub("", name)

def match_sites(name_cn, name_en):
    c = core(name_cn)
    en = norm_en(name_en)
    hits = []
    for s in sites:
        nm = s["name"]
        if name_cn in nm or (len(c) >= 2 and c in nm):
            hits.append(s)
        elif len(en) >= 4 and s["key"] == en:          # exact pinyin(name_en) == site_key
            hits.append(s)
    # alias fallback for abbreviation keys (gd, hlj, js, zj, bj, …)
    if not hits and c in ALIAS:
        hits = [s for s in sites if s["key"] == ALIAS[c]]
    return hits

rows = list(csv.DictReader(open(f"{REPO}/docs/working/china-admin-divisions.csv", encoding="utf-8")))
out_path = f"{REPO}/docs/working/china-admin-coverage.csv"
fields = list(rows[0].keys()) + ["covered", "our_docs", "our_site_keys"]
with open(out_path, "w", encoding="utf-8", newline="") as f:
    w = csv.DictWriter(f, fieldnames=fields)
    w.writeheader()
    for r in rows:
        hits = match_sites(r["name_cn"], r["name_en"])
        docs = sum(h["docs"] for h in hits)
        keys = ";".join(sorted({h["key"] for h in hits}))
        r["covered"] = "Y" if docs > 0 else ""
        r["our_docs"] = docs
        r["our_site_keys"] = keys
        w.writerow(r)

# summary
from collections import defaultdict
agg = defaultdict(lambda: [0, 0, 0])  # (level,type) -> [total, covered, docs]
for r in csv.DictReader(open(out_path, encoding="utf-8")):
    k = (r["level"], r["type"])
    agg[k][0] += 1
    if r["covered"] == "Y":
        agg[k][1] += 1
    agg[k][2] += int(r["our_docs"])
print(f"{'level':11} {'type':22} {'covered/total':>14} {'docs':>9}")
print("-" * 60)
tot = [0, 0, 0]
for (lvl, typ), (t, c, d) in sorted(agg.items()):
    print(f"{lvl:11} {typ:22} {c:>6}/{t:<7} {d:>9,}")
    tot[0] += t; tot[1] += c; tot[2] += d
print("-" * 60)
print(f"{'TOTAL':11} {'':22} {tot[1]:>6}/{tot[0]:<7} {tot[2]:>9,}")
print(f"\nWrote {out_path}")
