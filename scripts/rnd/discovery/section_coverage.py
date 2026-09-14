#!/usr/bin/env python3
"""Section-level coverage: for each doc-ish section a crawled host links but we
appear to be missing, CONFIRM by fetching it and checking whether the articles it
lists are already in our DB (by URL, regardless of stored prefix). This collapses
the false positives (list-section URL != article URL) that the naive prefix diff hits.

Emits rows: site_key<TAB>section<TAB>nav_links<TAB>arts_found<TAB>held_pct<TAB>status<TAB>sample_url
status ∈ {missing_have_scraper, already_crawled, needs_new_scraper, empty_or_blocked}

Usage: section_coverage.py <site_key> <homepage_url>
"""
import sys, re, sqlite3
from collections import Counter
from urllib.parse import urlparse, urljoin
sys.path.insert(0, ".")
from crawlers.base import fetch
from crawlers import govcms as G

DB = "documents.db"
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120 Safari/537.36"}
DOC_KW = re.compile(r"(zhengce|zc|wenjian|wj|gongbao|gb|yaowen|xinwen|fabu|gk|zwgk|xxgk|"
                    r"fagui|flfg|zcfg|gfxwj|tongzhi|tzgg|zcwj|zcjd|zck|content|govpush|"
                    r"guowuyuan|premier|lianbo|jiedu|zhibo|fdzdgk|zcfb)", re.I)
NONDOC = re.compile(r"(images?|img|static|css|js|template|search|about|help|sitemap|"
                    r"video|tupian|photo|special|zhuanti|footer|rss|login|user|gzcy|hdjl)", re.I)


def prefixes(path, depth=1):
    segs = [s for s in path.split("/") if s]
    return ["/" + "/".join(segs[:d]) + "/" for d in range(1, depth + 1) if len(segs) >= d]


def _list_at(url):
    try:
        html = fetch(url, headers=UA, timeout=10, retries=1)
    except Exception:
        return "", []
    if len(html) < 2000:
        return html, []
    return html, G._list_articles(html, url)


def confirm(conn, base, section):
    url = urljoin(base, section)
    html, arts = _list_at(url)
    reachable = bool(html) and len(html) >= 2000
    if not arts:                                   # section is a hub (e.g. /yaowen/ stub) → descend one level
        cands = [urljoin(url, "liebiao/"), urljoin(url, "index.html"), urljoin(url, "index.htm")]
        for m in re.finditer(r'href="([^"]+)"', html or ""):
            c = urljoin(url, m.group(1))
            if c.startswith(url) and c != url:
                cands.append(c)
        for c in list(dict.fromkeys(cands))[:6]:
            h2, a2 = _list_at(c)
            reachable = reachable or (bool(h2) and len(h2) >= 2000)
            if len(a2) >= 3:
                arts, url = a2, c
                break
    if not arts:
        return ("needs_new_scraper" if reachable else "empty_or_blocked", 0, 0, "")
    held = sum(1 for a in arts
               if conn.execute("SELECT 1 FROM documents WHERE url=? AND url!='' LIMIT 1",
                               (a["url"],)).fetchone())
    pct = round(100 * held / len(arts))
    status = "already_crawled" if pct >= 50 else "missing_have_scraper"
    return (status, len(arts), pct, arts[0]["url"])


def main():
    site_key, home = sys.argv[1], sys.argv[2]
    host = urlparse(home).netloc.replace("www.", "")
    conn = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)

    stored = Counter()
    for (url,) in conn.execute("SELECT url FROM documents WHERE site_key=? AND url!=''", (site_key,)):
        if urlparse(url).netloc.replace("www.", "") == host:
            for p in prefixes(urlparse(url).path):
                stored[p] += 1
    try:
        html = fetch(home, headers=UA, timeout=12, retries=1)
    except Exception as e:
        print(f"{site_key}\t-\t0\t0\t0\tHOMEPAGE_UNREACHABLE\t{e}"); return
    nav = Counter()
    for m in re.finditer(r'href="([^"]+)"', html):
        u = urljoin(home, m.group(1))
        if urlparse(u).netloc.replace("www.", "") != host:
            continue
        for p in prefixes(urlparse(u).path):
            nav[p] += 1

    for pre, links in nav.most_common():
        held = stored.get(pre, 0)
        if held < 5 and DOC_KW.search(pre) and not NONDOC.search(pre) and links >= 2:
            status, n, pct, sample = confirm(conn, home, pre)
            print(f"{site_key}\t{pre}\t{links}\t{n}\t{pct}\t{status}\t{sample}")


if __name__ == "__main__":
    main()
