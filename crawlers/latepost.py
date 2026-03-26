"""
LatePost (晚点LatePost) crawler via 163.com (NetEase).

Scrapes articles from LatePost's channel page on 163.com. Server-rendered HTML
with structured metadata (og: tags, post_body div). No API needed.

The channel page shows ~85 recent articles. Deeper archive requires JS execution
which this crawler does not support — run it regularly to capture new articles.

Usage:
    python -m crawlers.latepost                  # Crawl all available articles
    python -m crawlers.latepost --stats          # Show database stats
    python -m crawlers.latepost --list-only      # List URLs without fetching
    python -m crawlers.latepost --db alt.db      # Write to alternate database
"""

import argparse
import re
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path
from urllib.parse import urljoin

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

SITE_KEY = "latepost"
SITE_CFG = {
    "name": "LatePost (晚点LatePost)",
    "base_url": "https://www.163.com",
    "admin_level": "media",
}

# LatePost's channel page on 163.com
CHANNEL_URL = "https://www.163.com/dy/media/T1596162548889.html"
# All LatePost articles share this publisher segment in their URL
PUBLISHER_SEGMENT = "0531M1CO"

CST = timezone(timedelta(hours=8))


def _parse_date(date_str: str) -> int:
    """Convert ISO 8601 or YYYY-MM-DD date string to Unix timestamp at midnight CST."""
    if not date_str:
        return 0
    try:
        # Handle ISO 8601: 2026-03-18T18:47:13+08:00
        if "T" in date_str:
            date_str = date_str[:10]
        dt = datetime.strptime(date_str[:10], "%Y-%m-%d").replace(tzinfo=CST)
        return int(dt.timestamp())
    except ValueError:
        return 0


def _discover_articles(html: str) -> list[dict]:
    """Extract article URLs and IDs from the channel page HTML."""
    pattern = rf"https://www\.163\.com/dy/article/([A-Za-z0-9]+{PUBLISHER_SEGMENT})\.html"
    seen = set()
    articles = []
    for m in re.finditer(pattern, html):
        article_id = m.group(1)
        if article_id not in seen:
            seen.add(article_id)
            articles.append({
                "article_id": article_id,
                "url": f"https://www.163.com/dy/article/{article_id}.html",
            })
    return articles


def _extract_article(html: str) -> dict:
    """Extract article metadata and body from an article page.

    Uses og: meta tags for title/date and the post_body div for content.
    """
    meta = {}

    # Title from og:title
    m = re.search(r'<meta\s+property="og:title"\s+content="([^"]+)"', html)
    if m:
        meta["title"] = m.group(1).strip()

    # Date from article:published_time
    m = re.search(r'<meta\s+property="article:published_time"\s+content="([^"]+)"', html)
    if m:
        meta["date_published"] = m.group(1).strip()

    # Keywords from meta name="keywords"
    m = re.search(r'<meta\s+name="keywords"\s+content="([^"]+)"', html)
    if m:
        meta["keywords"] = m.group(1).strip()

    # Description from og:description
    m = re.search(r'<meta\s+property="og:description"\s+content="([^"]+)"', html)
    if m:
        meta["abstract"] = m.group(1).strip()

    # Body text from post_body div
    content = ""
    start = html.find('class="post_body"')
    if start != -1:
        gt = html.find(">", start)
        if gt != -1:
            content_start = gt + 1
            end_pos = len(html)
            for marker in ['<div class="post_recommends', '<div class="post_author',
                            '<div class="ndi_', '<div id="post_comment',
                            '<div class="ep-', '<!-- post_body end']:
                pos = html.find(marker, content_start)
                if pos != -1 and pos < end_pos:
                    end_pos = pos
            content = html[content_start:end_pos]

    if content:
        # Strip HTML to plain text
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
            .replace("&quot;", '"')
            .strip()
        )
        if len(text) > 20:
            meta["body_text_cn"] = text

    return meta


def crawl(conn, list_only: bool = False):
    """Crawl LatePost articles from 163.com channel page."""
    store_site(conn, SITE_KEY, SITE_CFG)

    log.info("Fetching LatePost channel page...")
    try:
        html = fetch(CHANNEL_URL, headers={
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                          "AppleWebKit/537.36 (KHTML, like Gecko) "
                          "Chrome/131.0.0.0 Safari/537.36",
        })
    except Exception as e:
        log.error(f"Failed to fetch channel page: {e}")
        return 0

    articles = _discover_articles(html)
    log.info(f"Found {len(articles)} articles on channel page")

    if list_only:
        for a in articles:
            print(f"  {a['article_id']}  {a['url']}")
        return len(articles)

    stored = 0
    skipped = 0
    for i, article in enumerate(articles):
        url = article["url"]

        # Skip if already crawled (check by URL)
        existing = conn.execute(
            "SELECT id, body_text_cn FROM documents WHERE url = ?", (url,)
        ).fetchone()
        if existing and existing[1]:
            skipped += 1
            continue

        try:
            article_html = fetch(url, headers={
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                              "AppleWebKit/537.36 (KHTML, like Gecko) "
                              "Chrome/131.0.0.0 Safari/537.36",
            })
        except Exception as e:
            log.warning(f"  Failed to fetch {url}: {e}")
            continue

        meta = _extract_article(article_html)
        if not meta.get("title"):
            log.warning(f"  No title found for {url}, skipping")
            continue

        doc_id = existing[0] if existing else next_id(conn)
        date_str = meta.get("date_published", "")[:10]

        raw_html_path = save_raw_html(SITE_KEY, doc_id, article_html)

        store_document(conn, SITE_KEY, {
            "id": doc_id,
            "title": meta["title"],
            "publisher": "晚点LatePost",
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

        if stored % 10 == 0:
            conn.commit()
            log.info(f"  Progress: {stored} stored, {skipped} skipped ({i+1}/{len(articles)})")

        time.sleep(REQUEST_DELAY)

    conn.commit()
    log.info(f"=== LatePost: {stored} new, {skipped} skipped, {len(articles)} total on page ===")
    return stored


def main():
    parser = argparse.ArgumentParser(description="LatePost Crawler (via 163.com)")
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
