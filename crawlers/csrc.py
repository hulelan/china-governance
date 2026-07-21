"""
中国证券监督管理委员会 (China Securities Regulatory Commission) crawler.

Crawls the 政策法规库 (zcfgk) — CSRC rules, regulations, and policy notices.
The zcfgk index is a hub linking ~150 article pages as
`/csrc/c{node}/c{node}/content.shtml` (node IDs, no date in the URL), so we
extract per-article: title from `<title>` (minus the "_中国证券监督管理委员会"
suffix), date from a 发布日期/成文日期 label (falling back to the first date on
the page), 文号 where present, and body from the `class="content"` region.

Usage:
    python -m crawlers.csrc
    python -m crawlers.csrc --list-only
"""
import argparse
import html as H
import re
import time

from crawlers.base import (
    REQUEST_DELAY, fetch, init_db, log, next_id, save_raw_html,
    show_stats, store_document, store_site,
)

SITE_KEY = "csrc"
CFG = {"name": "China Securities Regulatory Commission (证监会)",
       "base_url": "http://www.csrc.gov.cn", "admin_level": "central"}
INDEX_URLS = [
    "http://www.csrc.gov.cn/csrc/xxgk/zcfgk/index.shtml",
]
# CSRC throttles bursts: after a rapid backfill it serves the section index
# (~208 KB, bare "证监会" <title>) instead of the article. We use browser headers +
# a polite delay; throttled responses resolve to a _SKIP_TITLES title, so they are
# skipped (never stored as garbage) rather than corrupting the row.
_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")
_HEADERS = {"User-Agent": _UA, "Referer": INDEX_URLS[0]}
_DELAY = 2.0

_LINK_RE = re.compile(r"(/csrc/c\d+/c\d+/content\.shtml)")
_TITLE_RE = re.compile(r"<title>([^<]+)</title>")
_TITLE_SUFFIX = re.compile(r"[_|]\s*中国证券监督管理委员会.*$")
_DATE_LABEL = re.compile(r"(?:发布日期|成文日期|发文日期)[^0-9]{0,8}(\d{4}-\d{2}-\d{2})")
_DATE_ANY = re.compile(r"(\d{4}-\d{2}-\d{2})")
_DOCNUM_RE = re.compile(r"(证监[^〔]{0,8}〔\d{4}〕\d+号|[一-鿿]{2,10}〔\d{4}〕\d+号|证监会令第\d+号)")
# Body sits between the article header and the 相关附件/相关链接 block; cut there.
_FOOT_RE = re.compile(r"相关(?:附件|链接|稿件|信息|报道)")
_NOISE_RE = re.compile(r"(版权所有|京ICP|主办[：:]|网站标识|联系我们|证监会介绍|扫一扫|分享到|打印本页)")
# Non-document hub/nav pages that appear among the zcfgk links.
_SKIP_TITLES = ("证监会介绍", "联系我们", "网站地图", "更多", "中国证券监督管理委员会", "机构职能")


def _abs(path):
    return path if path.startswith("http") else "http://www.csrc.gov.cn" + path


def _title_of(html):
    m = _TITLE_RE.search(html)
    return _TITLE_SUFFIX.sub("", H.unescape(m.group(1)).strip()) if m else ""


def _body_of(html):
    # Anchor the body just after the publish-date header; cut at the 相关* footer block.
    dm = _DATE_LABEL.search(html)
    start = dm.end() if dm else 0
    fm = _FOOT_RE.search(html, start)
    region = html[start:fm.start() if fm else start + 60_000]
    ps = [H.unescape(re.sub(r"<[^>]+>", "", p)).strip()
          for p in re.findall(r"<p[^>]*>(.*?)</p>", region, re.S)]
    ps = [p for p in ps if len(p) >= 10 and not _NOISE_RE.search(p)]
    return "\n".join(ps)


def crawl(conn, fetch_bodies=True):
    store_site(conn, SITE_KEY, CFG)
    seen, stored = set(), 0
    for idx_url in INDEX_URLS:
        try:
            idx = fetch(idx_url, headers=_HEADERS)
        except Exception as e:
            log.warning(f"index {idx_url}: {e}")
            continue
        links = sorted({_abs(p) for p in _LINK_RE.findall(idx)})
        log.info(f"[{SITE_KEY}] {len(links)} article links")
        for url in links:
            if url in seen:
                continue
            seen.add(url)
            if conn.execute("SELECT 1 FROM documents WHERE url=?", (url,)).fetchone():
                continue
            doc_id = next_id(conn)
            try:
                art = fetch(url, headers=_HEADERS)
            except Exception as e:
                log.warning(f"  article {url}: {e}")
                continue
            title = _title_of(art)
            if not title or title in _SKIP_TITLES:
                continue
            dm = _DATE_LABEL.search(art) or _DATE_ANY.search(art)
            nm = _DOCNUM_RE.search(art)
            body, raw = "", ""
            if fetch_bodies:
                body = _body_of(art)
                raw = save_raw_html(SITE_KEY, doc_id, art)
            store_document(conn, SITE_KEY, {
                "id": doc_id, "title": title,
                "document_number": nm.group(1) if nm else "",
                "date_published": dm.group(1) if dm else "",
                "body_text_cn": body, "url": url,
                "classify_main_name": "政策法规", "raw_html_path": raw,
                "admin_level": "central",
            })
            stored += 1
            time.sleep(_DELAY)
        conn.commit()
    log.info(f"[{SITE_KEY}] done: {stored} new docs")
    return stored


def main():
    ap = argparse.ArgumentParser(description="中国证监会 (CSRC) crawler")
    ap.add_argument("--list-only", action="store_true")
    ap.add_argument("--db")
    args = ap.parse_args()
    conn = init_db(args.db) if args.db else init_db()
    crawl(conn, fetch_bodies=not args.list_only)
    show_stats(conn)


if __name__ == "__main__":
    main()
