"""
中国人民银行 (People's Bank of China) crawler — 条法司 regulations + normative docs.

PBOC's list pages don't put dates next to anchors, which stumps generic scrapers;
the trick is that each article's URL node-id is a **timestamp**, e.g.
`/tiaofasi/144941/144957/2026052217462526593/index.html` → published 2026-05-22.
So we take the title (rich — it carries the 令号/文号) from the list anchor and the
date from the node-id, and the body from the article's `<div id="zoom">`.

Covers the two document subsections of 条法司 (Legal Affairs Dept):
  - 3581332 规范性文件 (normative documents)
  - 144957  部门规章 (PBOC orders / 令)
(The 法律/行政法规 subsections link out to external law texts; 工作信息/简介/意见征集
are nav.) Adding a section is one SECTIONS entry.

Usage:
    python -m crawlers.pbc
    python -m crawlers.pbc --list-only
"""
import argparse
import html as H
import re
import time

from crawlers.base import (
    REQUEST_DELAY, fetch, init_db, log, next_id, save_raw_html,
    show_stats, store_document, store_site,
)

SITE_KEY = "pbc"
CFG = {"name": "People's Bank of China (中国人民银行)",
       "base_url": "http://www.pbc.gov.cn", "admin_level": "central"}
BASE = "http://www.pbc.gov.cn"
UA = {"User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                     "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"),
      "Referer": "http://www.pbc.gov.cn/"}

# (section path under the site root, human label)
SECTIONS = [
    ("tiaofasi/144941/3581332", "规范性文件"),
    ("tiaofasi/144941/144957", "部门规章"),
]

_DOCNUM_RE = re.compile(r"(中国人民银行(?:公告|令)〔\d{4}〕第?\d+号|银发〔\d{4}〕\d+号|[一-鿿]{2,10}〔\d{4}〕\d+号)")


def _get(url):
    return fetch(url, headers=UA)


def _rows(list_html, section):
    """(node_id, title) for each article on a section list page."""
    pat = re.compile(rf'href=["\'](?:{re.escape(BASE)})?/{re.escape(section)}/(\d{{15,}})/index\.html["\'][^>]*>\s*([^<]{{4,}})')
    out, seen = [], set()
    for nid, title in pat.findall(list_html):
        if nid in seen:
            continue
        seen.add(nid)
        out.append((nid, H.unescape(title).strip()))
    return out


def _body_of(html):
    i = html.find('id="zoom"')
    if i < 0:
        return ""
    region = html[i:i + 80_000]
    ps = [H.unescape(re.sub(r"<[^>]+>", "", p)).strip()
          for p in re.findall(r"<p[^>]*>(.*?)</p>", region, re.S)]
    body = "\n".join(p for p in ps if len(p) >= 2)
    if len(body) < 30:   # some PBOC bodies aren't in <p>; fall back to stripped text
        txt = re.sub(r"<script.*?</script>", " ", html[i:i + 80_000], flags=re.S)
        txt = H.unescape(re.sub(r"<[^>]+>", " ", txt))
        body = re.sub(r"\s{2,}", "\n", txt).strip()
    return body


def crawl(conn, fetch_bodies=True):
    store_site(conn, SITE_KEY, CFG)
    stored = 0
    for section, label in SECTIONS:
        try:
            lp = _get(f"{BASE}/{section}/index.html")
        except Exception as e:
            log.warning(f"[{SITE_KEY}] list {section}: {e}")
            continue
        rows = _rows(lp, section)
        log.info(f"[{SITE_KEY}] {label} ({section}): {len(rows)} docs")
        for nid, title in rows:
            url = f"{BASE}/{section}/{nid}/index.html"
            if conn.execute("SELECT 1 FROM documents WHERE url=?", (url,)).fetchone():
                continue
            if not title:
                continue
            date_pub = f"{nid[:4]}-{nid[4:6]}-{nid[6:8]}"
            doc_id = next_id(conn)
            body, raw = "", ""
            if fetch_bodies:
                try:
                    art = _get(url)
                    body = _body_of(art)
                    raw = save_raw_html(SITE_KEY, doc_id, art)
                except Exception as e:
                    log.warning(f"  body {url}: {e}")
                time.sleep(REQUEST_DELAY)
            nm = _DOCNUM_RE.search(title) or _DOCNUM_RE.search(body[:200])
            store_document(conn, SITE_KEY, {
                "id": doc_id, "title": title,
                "document_number": nm.group(1) if nm else "",
                "date_published": date_pub,
                "body_text_cn": body, "url": url,
                "classify_main_name": label, "raw_html_path": raw,
                "admin_level": "central",
            })
            stored += 1
        conn.commit()
    log.info(f"[{SITE_KEY}] done: {stored} new docs")
    return stored


def main():
    ap = argparse.ArgumentParser(description="中国人民银行 (PBOC) crawler")
    ap.add_argument("--list-only", action="store_true")
    ap.add_argument("--db")
    args = ap.parse_args()
    conn = init_db(args.db) if args.db else init_db()
    crawl(conn, fetch_bodies=not args.list_only)
    show_stats(conn)


if __name__ == "__main__":
    main()
