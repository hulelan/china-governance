#!/usr/bin/env python3
"""Find document sections a crawled host EXPOSES but we DON'T crawl.

Per site: diff the URL path-prefixes we've stored docs from against the prefixes
the site links from its own homepage. A prefix the homepage links but we hold ~0
docs from (and whose slug looks document-ish) is a missing "docs folder" like /yaowen/.

Usage: find_missing_sections.py <site_key> <homepage_url>
"""
import sys, re, sqlite3
from collections import Counter
from urllib.parse import urlparse, urljoin
sys.path.insert(0, ".")
from crawlers.base import fetch

DB = "documents.db"
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120 Safari/537.36"}
# slugs that signal a DOCUMENT section (policy/notice/gazette/news-with-primary-text)
DOC_KW = re.compile(r"(zhengce|zc|wenjian|wj|gongbao|gb|yaowen|xinwen|fabu|gk|zwgk|xxgk|"
                    r"fagui|flfg|zcfg|gfxwj|tongzhi|tzgg|zcwj|zcjd|zck|content|govpush|"
                    r"guowuyuan|premier|lianbo|jiedu|zhibo)", re.I)
NONDOC = re.compile(r"(images?|img|static|css|js|template|search|about|help|sitemap|"
                    r"video|tupian|photo|special|zhuanti|footer|rss|login|user)", re.I)


def prefixes(path, depth=2):
    segs = [s for s in path.split("/") if s]
    return ["/" + "/".join(segs[:d]) + "/" for d in range(1, depth + 1) if len(segs) >= d]


def main():
    site_key, home = sys.argv[1], sys.argv[2]
    host = urlparse(home).netloc
    conn = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)

    stored = Counter()
    for (url,) in conn.execute("SELECT url FROM documents WHERE site_key=? AND url!=''", (site_key,)):
        if urlparse(url).netloc.replace("www.", "") == host.replace("www.", ""):
            for p in prefixes(urlparse(url).path):
                stored[p] += 1

    try:
        html = fetch(home, headers=UA, timeout=12, retries=1)
    except Exception as e:
        print(f"homepage fetch failed: {e}"); return
    nav = Counter()
    for m in re.finditer(r'href="([^"]+)"', html):
        u = urljoin(home, m.group(1))
        if urlparse(u).netloc.replace("www.", "") != host.replace("www.", ""):
            continue
        for p in prefixes(urlparse(u).path):
            nav[p] += 1

    # missing = linked by the site, doc-ish slug, we hold ~0
    print(f"[{site_key}] {host}: hold {sum(stored.values())} docs across {len(stored)} prefixes")
    print(f"{'nav-links':>9}  {'our-docs':>8}  section")
    missing = []
    for pre, links in nav.most_common():
        segs = [s for s in pre.split("/") if s]
        if len(segs) != 1:            # rank on top-level sections; depth-2 shown as detail
            continue
        held = stored.get(pre, 0)
        if held < 5 and DOC_KW.search(pre) and not NONDOC.search(pre) and links >= 2:
            missing.append((pre, links, held))
    for pre, links, held in missing:
        print(f"{links:>9}  {held:>8}  {pre}   <-- MISSING (doc-ish, linked, we hold {held})")
    if not missing:
        print("  (no obvious missing doc sections)")


if __name__ == "__main__":
    main()
