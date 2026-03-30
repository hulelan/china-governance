"""
Phoenix News 风声 (凤凰网评论) crawler.

Crawls policy commentary articles from the 风声 (Fengsheng) column on
news.ifeng.com. Server-rendered HTML with og: meta tags.

The channel page shows recent articles. Run regularly for incremental capture.

Usage:
    python -m crawlers.ifeng                   # Crawl all available articles
    python -m crawlers.ifeng --stats           # Show database stats
    python -m crawlers.ifeng --list-only       # List URLs without fetching
"""

import argparse
import re
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path

from crawlers.base import (
    REQUEST_DELAY,
    fetch,
    init_db,
    log,
    next_id,
    save_raw_html,
    show_stats,
    store_document,
    store_site,
)

SITE_KEY = "ifeng"
SITE_CFG = {
    "name": "Phoenix News (凤凰网风声)",
    "base_url": "https://news.ifeng.com",
    "admin_level": "media",
}

CST = timezone(timedelta(hours=8))
BROWSER_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)

# 风声 uses ifeng's "大风号" media account system (account ID 7408).
# The API returns JSONP with ~10 articles per page.
FENGSHENG_API = (
    "https://shankapi.ifeng.com/season/ishare/getShareListData"
    "/7408/doc/{page}/ifengnewsh5/getListData"
)
MAX_PAGES = 10  # ~100 articles total


def _parse_date(date_str: str) -> int:
    """Convert date string to Unix timestamp at midnight CST."""
    date_str = date_str.strip()[:10]
    try:
        dt = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=CST)
        return int(dt.timestamp())
    except ValueError:
        return 0


def _discover_articles() -> list[dict]:
    """Fetch article URLs from the 风声 ishare API (paginated JSONP)."""
    import json as _json
    seen = set()
    articles = []
    for page in range(1, MAX_PAGES + 1):
        url = FENGSHENG_API.format(page=page)
        try:
            raw = fetch(url, headers={"User-Agent": BROWSER_UA})
        except Exception as e:
            log.warning(f"  API page {page} failed: {e}")
            break
        # Strip JSONP wrapper: getListData({...})
        m = re.search(r'getListData\((.+)\)\s*$', raw, re.DOTALL)
        if not m:
            log.warning(f"  Page {page}: unexpected JSONP format")
            break
        try:
            data = _json.loads(m.group(1))
        except _json.JSONDecodeError:
            log.warning(f"  Page {page}: invalid JSON")
            break
        items = data.get("data", [])
        if not items:
            break
        for item in items:
            base62 = item.get("base62Id", "")
            if not base62 or base62 in seen:
                continue
            seen.add(base62)
            article_url = f"https://news.ifeng.com/c/{base62}"
            articles.append({
                "url": article_url,
                "title": item.get("title", ""),
                "date": item.get("newsTime", "")[:10],
            })
        log.info(f"  API page {page}: {len(items)} items")
        time.sleep(REQUEST_DELAY)
    return articles


def _extract_article(html: str) -> dict:
    """Extract article metadata and body from an article page."""
    meta = {}

    # Title from og:title
    m = re.search(r'property="og:title"\s+content="([^"]+)"', html)
    if m:
        meta["title"] = m.group(1).strip()

    # Date from og:article:published_time or inline date
    m = re.search(r'property="article:published_time"\s+content="([^"]+)"', html)
    if m:
        meta["date_published"] = m.group(1).strip()
    else:
        # Fallback: look for date in page
        m = re.search(r'"publishTime"\s*:\s*"(\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2})', html)
        if m:
            meta["date_published"] = m.group(1)[:10]

    # Keywords
    m = re.search(r'<meta\s+name="keywords"\s+content="([^"]+)"', html)
    if m:
        meta["keywords"] = m.group(1).strip()

    # Description / abstract
    m = re.search(r'property="og:description"\s+content="([^"]+)"', html)
    if m:
        meta["abstract"] = m.group(1).strip()

    # Body text — ifeng uses CSS-module hashed class names like index_text_XXXXX
    start = -1
    for pattern in ['index_text_', 'main_content', 'text_box']:
        m_body = re.search(rf'class="[^"]*{pattern}[^"]*"', html)
        if m_body:
            start = m_body.start()
            break
    if start != -1:
        gt = html.find(">", start)
        if gt != -1:
            content_start = gt + 1
            end_pos = len(html)
            for marker in ['<div class="comment', '<div class="relate',
                            '<div class="bottom', '<div class="share',
                            '<script', '<!-- end content']:
                pos = html.find(marker, content_start)
                if pos != -1 and pos < end_pos:
                    end_pos = pos
            content = html[content_start:end_pos]
            # Strip HTML
            content = re.sub(r"<br\s*/?\s*>", "\n", content)
            content = re.sub(r"<p[^>]*>", "\n", content)
            content = re.sub(r"</p>", "", content)
            content = re.sub(r"<div[^>]*>", "\n", content)
            content = re.sub(r"</div>", "", content)
            content = re.sub(r"<img[^>]*>", "", content)
            text = re.sub(r"<[^>]+>", "", content)
            text = re.sub(r"[ \t]+", " ", text)
            text = re.sub(r"\n\s*\n", "\n", text)
            text = (
                text.replace("&nbsp;", " ")
                .replace("\u3000", " ")
                .replace("&lt;", "<")
                .replace("&gt;", ">")
                .replace("&amp;", "&")
                .strip()
            )
            if len(text) > 50:
                meta["body_text_cn"] = text

    return meta


def crawl(conn, list_only: bool = False):
    """Crawl Phoenix/风声 articles."""
    store_site(conn, SITE_KEY, SITE_CFG)

    log.info("Fetching 风声 articles via ishare API...")
    articles = _discover_articles()
    log.info(f"Found {len(articles)} articles on channel page")

    if list_only:
        for a in articles:
            print(f"  {a['url']}")
        return len(articles)

    stored = 0
    skipped = 0
    for i, article in enumerate(articles):
        url = article["url"]

        existing = conn.execute(
            "SELECT id, body_text_cn FROM documents WHERE url = ?", (url,)
        ).fetchone()
        if existing and existing[1]:
            skipped += 1
            continue

        try:
            article_html = fetch(url, headers={"User-Agent": BROWSER_UA})
        except Exception as e:
            log.warning(f"  Failed to fetch {url}: {e}")
            continue

        meta = _extract_article(article_html)
        if not meta.get("title"):
            log.warning(f"  No title for {url}, skipping")
            continue

        doc_id = existing[0] if existing else next_id(conn)
        date_str = meta.get("date_published", "")[:10]
        raw_html_path = save_raw_html(SITE_KEY, doc_id, article_html)

        store_document(conn, SITE_KEY, {
            "id": doc_id,
            "title": meta["title"],
            "publisher": "凤凰网风声",
            "keywords": meta.get("keywords", ""),
            "abstract": meta.get("abstract", ""),
            "date_written": _parse_date(date_str),
            "date_published": date_str,
            "body_text_cn": meta.get("body_text_cn", ""),
            "url": url,
            "classify_main_name": "媒体报道",
            "raw_html_path": raw_html_path,
        })
        stored += 1
        time.sleep(REQUEST_DELAY)

    conn.commit()
    log.info(f"=== Phoenix/风声: {stored} new, {skipped} skipped, {len(articles)} on page ===")
    return stored


def main():
    parser = argparse.ArgumentParser(description="Phoenix/风声 Crawler")
    parser.add_argument("--stats", action="store_true", help="Show database stats")
    parser.add_argument("--list-only", action="store_true",
                        help="List article URLs without fetching")
    parser.add_argument("--db", type=str,
                        help="Path to SQLite database (default: documents.db)")
    args = parser.parse_args()

    conn = init_db(Path(args.db) if args.db else None)

    if args.stats:
        show_stats(conn)
        conn.close()
        return

    crawl(conn, list_only=args.list_only)
    show_stats(conn)
    conn.close()


if __name__ == "__main__":
    main()
