"""
量子位 (QbitAI) — a leading Chinese AI-industry media outlet.

WordPress site with an open REST API, so we page the JSON feed rather than
scraping: GET /wp-json/wp/v2/posts?per_page=50&page=N returns posts with
title/date/link/content. Body = the rendered content with tags stripped.

Incremental: the feed is newest-first, so a full page of already-held posts ends
the run (`--full` disables the early-exit to backfill).

Usage:
    python -m crawlers.qbitai
    python -m crawlers.qbitai --full          # backfill (no early-exit)
    python -m crawlers.qbitai --list-only     # metadata only
"""
import argparse
import html as H
import json
import re
import time

from crawlers.base import (
    REQUEST_DELAY, fetch, init_db, log, next_id,
    show_stats, store_document, store_site,
)

SITE_KEY = "qbitai"
CFG = {"name": "QbitAI (量子位 · AI media)", "base_url": "https://www.qbitai.com",
       "admin_level": "media"}
API = "https://www.qbitai.com/wp-json/wp/v2/posts"
UA = {"User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                     "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")}
PER_PAGE = 50
MAX_PAGES = 60


def _text(html: str) -> str:
    html = re.sub(r"<script.*?</script>", " ", html, flags=re.S)
    html = re.sub(r"<style.*?</style>", " ", html, flags=re.S)
    html = re.sub(r"<br\s*/?>", "\n", html)
    html = re.sub(r"</p>", "\n", html)
    txt = H.unescape(re.sub(r"<[^>]+>", "", html))
    return re.sub(r"\n\s*\n+", "\n", re.sub(r"[ \t]+", " ", txt)).strip()


def _clean_title(t: str) -> str:
    return H.unescape(re.sub(r"<[^>]+>", "", t)).strip()


def crawl(conn, fetch_bodies=True, full=False):
    store_site(conn, SITE_KEY, CFG)
    stored = 0
    for page in range(1, MAX_PAGES + 1):
        url = f"{API}?per_page={PER_PAGE}&page={page}&_fields=id,date,link,title,content"
        try:
            posts = json.loads(fetch(url, headers=UA))
        except Exception as e:
            log.warning(f"[{SITE_KEY}] page {page}: {e}")
            break
        if not isinstance(posts, list) or not posts:
            break
        all_held = True
        for post in posts:
            link = post.get("link", "")
            if not link:
                continue
            if conn.execute("SELECT 1 FROM documents WHERE url=? AND url != ''", (link,)).fetchone():
                continue
            all_held = False
            title = _clean_title(post.get("title", {}).get("rendered", ""))
            if not title:
                continue
            date_pub = (post.get("date", "") or "")[:10]
            body = _text(post.get("content", {}).get("rendered", "")) if fetch_bodies else ""
            doc_id = next_id(conn)
            store_document(conn, SITE_KEY, {
                "id": doc_id, "title": title, "date_published": date_pub,
                "body_text_cn": body, "url": link,
                "classify_genre_name": "news", "admin_level": "media",
            })
            stored += 1
        conn.commit()
        log.info(f"[{SITE_KEY}] page {page}: total {stored}")
        if not full and all_held:
            break
        time.sleep(REQUEST_DELAY)
    log.info(f"[{SITE_KEY}] done: {stored} new docs")
    return stored


def main():
    ap = argparse.ArgumentParser(description="量子位 QbitAI crawler (WP REST API)")
    ap.add_argument("--full", action="store_true", help="backfill — no incremental early-exit")
    ap.add_argument("--list-only", action="store_true")
    ap.add_argument("--db")
    args = ap.parse_args()
    conn = init_db(args.db) if args.db else init_db()
    crawl(conn, fetch_bodies=not args.list_only, full=args.full)
    show_stats(conn)


if __name__ == "__main__":
    main()
