"""
最高人民检察院 (Supreme People's Procuratorate) crawler.

Crawls the 法律法规库 (flfgk) — the constitution, laws, and judicial
interpretations the SPP publishes. Static TRS WCM: the index lists articles as
`/spp/{sec}/{YYYYMM}/t{YYYYMMDD}_{id}.shtml`, so the publish date is encoded in
the URL. Each article's body lives in `<div id="fontzoom">` (bounded by the
`xgxw` = 相关新闻 block that follows it); the title is the `<title>` minus the
"_最高人民检察院门户网" suffix.

Complements the corpus's judiciary coverage (最高法 IP Tribunal via
crawlers.ipc_court) with the procuratorate side.

Usage:
    python -m crawlers.spp
    python -m crawlers.spp --list-only     # metadata, skip bodies
"""
import argparse
import html as H
import re
import time

from crawlers.base import (
    REQUEST_DELAY, fetch, init_db, log, next_id, save_raw_html,
    show_stats, store_document, store_site,
)

SITE_KEY = "spp"
CFG = {"name": "Supreme People's Procuratorate (最高人民检察院)",
       "base_url": "https://www.spp.gov.cn", "admin_level": "central"}

# The 法律法规库 hub + its category sub-pages (laws / judicial interpretations / etc.).
INDEX_URLS = [
    "https://www.spp.gov.cn/spp/flfgk/index.shtml",
]

_LINK_RE = re.compile(r'href=["\']([^"\']*?/t(\d{8})_\d+\.shtml)["\']')
_TITLE_RE = re.compile(r"<title>([^<]+)</title>")
_TITLE_SUFFIX = re.compile(r"[_|]\s*最高人民检察院.*$")
_DOCNUM_RE = re.compile(r"([一-鿿〔\[]{0,15}〔\d{4}〕[^号]{0,8}号|[一-鿿]{2,10}〔\d{4}〕\d+号)")


def _abs(url):
    if url.startswith("http"):
        return url
    return "https://www.spp.gov.cn" + url


def _extract_body(html: str) -> str:
    s = html.find('id="fontzoom"')
    if s < 0:
        return ""
    e = html.find('id="xgxw"', s)
    region = html[s:e if e > s else s + 80_000]
    ps = [re.sub(r"<[^>]+>", "", p).strip() for p in re.findall(r"<p[^>]*>(.*?)</p>", region, re.S)]
    return "\n".join(H.unescape(p) for p in ps if len(p.strip()) >= 2)


def _title_of(html: str) -> str:
    m = _TITLE_RE.search(html)
    return _TITLE_SUFFIX.sub("", H.unescape(m.group(1)).strip()) if m else ""


def crawl(conn, fetch_bodies=True):
    store_site(conn, SITE_KEY, CFG)
    seen, stored = set(), 0
    for idx_url in INDEX_URLS:
        try:
            idx = fetch(idx_url)
        except Exception as e:
            log.warning(f"index {idx_url}: {e}")
            continue
        links = [(_abs(u), d) for u, d in _LINK_RE.findall(idx)]
        log.info(f"[{SITE_KEY}] {idx_url.rsplit('/', 2)[-2]}: {len(links)} article links")
        for url, d8 in links:
            if url in seen:
                continue
            seen.add(url)
            if conn.execute("SELECT 1 FROM documents WHERE url=? AND url != ''", (url,)).fetchone():
                continue
            date_pub = f"{d8[:4]}-{d8[4:6]}-{d8[6:8]}"
            doc_id = next_id(conn)
            title, body, raw = "", "", ""
            try:
                art = fetch(url)
                title = _title_of(art)
                if fetch_bodies:
                    body = _extract_body(art)
                    raw = save_raw_html(SITE_KEY, doc_id, art)
            except Exception as e:
                log.warning(f"  article {url}: {e}")
                continue
            if not title:
                continue
            dm = _DOCNUM_RE.search(title) or _DOCNUM_RE.search(body[:200])
            store_document(conn, SITE_KEY, {
                "id": doc_id, "title": title,
                "document_number": dm.group(1) if dm else "",
                "date_published": date_pub,
                "body_text_cn": body, "url": url,
                "classify_main_name": "法律法规", "raw_html_path": raw,
                "admin_level": "central",
            })
            stored += 1
            if fetch_bodies:
                time.sleep(REQUEST_DELAY)
        conn.commit()
    log.info(f"[{SITE_KEY}] done: {stored} new docs")
    return stored


def main():
    ap = argparse.ArgumentParser(description="最高人民检察院 (SPP) crawler")
    ap.add_argument("--list-only", action="store_true", help="metadata only, skip bodies")
    ap.add_argument("--db")
    args = ap.parse_args()
    conn = init_db(args.db) if args.db else init_db()
    crawl(conn, fetch_bodies=not args.list_only)
    show_stats(conn)


if __name__ == "__main__":
    main()
