"""
elsewhere.news (别处 · Elsewhere) — Chinese VC / AI-tech news & analysis.

A Next.js + Supabase app, but the pages are SERVER-rendered and the Supabase
REST API is service_role-gated (anon gets 401), so we scrape the rendered HTML.
Articles live at `/zh/<section>/<slug>` (section = author-<id>, crossing,
elsewhere, brands…; the single-segment `/zh/articles`, `/zh/brands`, `/zh/about`
are index/nav pages). Each article page carries clean metadata:
  - og:title                       → title
  - article:published_time (ISO)   → date
  - article:author                 → publisher
  - <article> / .prose container   → body (<p> text)

Discovery = collect 2-segment /zh/ links from the homepage + section indexes.
There is no deep pagination exposed; the indexes surface the recent window.

Usage:
    python -m crawlers.elsewhere
    python -m crawlers.elsewhere --list-only
"""
import argparse
import html as H
import re
import time

from crawlers.base import (
    REQUEST_DELAY, fetch, init_db, log, next_id, save_raw_html,
    show_stats, store_document, store_site,
)

SITE_KEY = "elsewhere"
CFG = {"name": "Elsewhere (别处 · VC/AI tech news)",
       "base_url": "https://elsewhere.news", "admin_level": "media"}
BASE = "https://elsewhere.news"
UA = {"User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                     "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")}
INDEX_PAGES = ["/zh", "/zh/articles", "/zh/brands", "/zh/crossing", "/zh/elsewhere"]

# 2-segment article paths only (/zh/<section>/<slug>); single-segment = index/nav.
_ART_LINK = re.compile(r'href="(/zh/[^/"?#]+/[^"?#]+)"')
_OG_TITLE = re.compile(r'<meta\s+property="og:title"\s+content="([^"]*)"')
_PUB_TIME = re.compile(r'<meta\s+property="article:published_time"\s+content="([^"]*)"')
_AUTHOR = re.compile(r'<meta\s+property="article:author"\s+content="([^"]*)"')


def _get(url):
    return fetch(url, headers=UA)


def _body_of(html):
    """Extract the article body: the <p> paragraphs inside <article>…</article>.
    Scripts/styles are stripped first so the JSON-LD schema block (a <script> whose
    text would otherwise survive tag-stripping) doesn't pollute the body."""
    m = re.search(r"<article\b", html)
    if not m:
        return ""
    end = html.find("</article>", m.start())
    region = html[m.start():end if end > 0 else m.start() + 120_000]
    region = re.sub(r"<script.*?</script>", " ", region, flags=re.S)
    region = re.sub(r"<style.*?</style>", " ", region, flags=re.S)
    ps = [H.unescape(re.sub(r"<[^>]+>", "", p)).strip()
          for p in re.findall(r"<p[^>]*>(.*?)</p>", region, re.S)]
    return "\n".join(p for p in ps if len(p) >= 2)


def _discover_links():
    urls = set()
    for path in INDEX_PAGES:
        try:
            html = _get(BASE + path)
        except Exception as e:
            log.warning(f"[{SITE_KEY}] index {path}: {e}")
            continue
        for href in _ART_LINK.findall(html):
            urls.add(BASE + href)
    return sorted(urls)


def crawl(conn, fetch_bodies=True):
    store_site(conn, SITE_KEY, CFG)
    links = _discover_links()
    log.info(f"[{SITE_KEY}] discovered {len(links)} article links")
    stored = 0
    for url in links:
        if conn.execute("SELECT 1 FROM documents WHERE url=? AND url != ''", (url,)).fetchone():
            continue
        try:
            art = _get(url)
        except Exception as e:
            log.warning(f"  {url}: {e}")
            continue
        tm = _OG_TITLE.search(art)
        title = H.unescape(tm.group(1)).strip() if tm else ""
        if not title:
            continue
        pt = _PUB_TIME.search(art)
        date_pub = pt.group(1)[:10] if pt else ""
        am = _AUTHOR.search(art)
        doc_id = next_id(conn)
        body, raw = "", ""
        if fetch_bodies:
            body = _body_of(art)
            raw = save_raw_html(SITE_KEY, doc_id, art)
            time.sleep(REQUEST_DELAY)
        store_document(conn, SITE_KEY, {
            "id": doc_id, "title": title,
            "publisher": H.unescape(am.group(1)).strip() if am else "",
            "date_published": date_pub,
            "body_text_cn": body, "url": url,
            "classify_genre_name": "news", "raw_html_path": raw,
            "admin_level": "media",
        })
        stored += 1
        conn.commit()
    log.info(f"[{SITE_KEY}] done: {stored} new docs")
    return stored


def main():
    ap = argparse.ArgumentParser(description="elsewhere.news (别处) crawler")
    ap.add_argument("--list-only", action="store_true", help="metadata only, skip bodies")
    ap.add_argument("--db")
    args = ap.parse_args()
    conn = init_db(args.db) if args.db else init_db()
    crawl(conn, fetch_bodies=not args.list_only)
    show_stats(conn)


if __name__ == "__main__":
    main()
