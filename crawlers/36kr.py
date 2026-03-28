"""
36Kr (36氪) crawler via RSS feed.

Crawls tech/startup news articles from 36kr.com. Uses the RSS feed for article
discovery and fetches full article content from window.initialState on article
pages.

The RSS feed returns ~30 recent items. Run regularly for incremental capture.

Usage:
    python -m crawlers.36kr                    # Crawl all available articles
    python -m crawlers.36kr --stats            # Show database stats
    python -m crawlers.36kr --list-only        # List URLs without fetching
"""

import argparse
import json
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

SITE_KEY = "36kr"
SITE_CFG = {
    "name": "36Kr (36氪)",
    "base_url": "https://36kr.com",
    "admin_level": "media",
}

CST = timezone(timedelta(hours=8))
RSS_URL = "https://36kr.com/feed"
BROWSER_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)


def _parse_date(date_str: str) -> int:
    """Convert date string to Unix timestamp at midnight CST.

    RSS format: '2026-03-28 09:24:38 +0800'
    """
    date_str = date_str.strip()
    try:
        dt = datetime.strptime(date_str[:10], "%Y-%m-%d").replace(tzinfo=CST)
        return int(dt.timestamp())
    except ValueError:
        return 0


def _parse_rss(xml: str) -> list[dict]:
    """Parse RSS feed items. Returns list of {url, title, date_str, description}."""
    items = []
    for m in re.finditer(
        r'<item>\s*'
        r'<title>(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?</title>\s*'
        r'<link>(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?</link>\s*'
        r'<pubDate>(.*?)</pubDate>',
        xml,
        re.DOTALL,
    ):
        title = m.group(1).strip()
        url = m.group(2).strip().split("?")[0]  # strip ?f=rss
        date_str = m.group(3).strip()

        # Skip newsflashes — only want full articles (/p/ URLs)
        if "/p/" not in url:
            continue

        items.append({
            "url": url,
            "title": title,
            "date_str": date_str[:10],
        })
    return items


def _extract_article(html: str) -> dict:
    """Extract article content from window.initialState on article page."""
    meta = {}

    # Title from og:title
    m = re.search(r'<meta\s+property="og:title"\s+content="([^"]+)"', html)
    if m:
        meta["title"] = m.group(1).strip()

    # Description from og:description
    m = re.search(r'<meta\s+property="og:description"\s+content="([^"]+)"', html)
    if m:
        meta["abstract"] = m.group(1).strip()

    # Try extracting widgetContent from initialState
    m = re.search(r'"widgetContent"\s*:\s*"(.*?)(?:","|\",\")', html)
    if m:
        raw = m.group(1)
        # Unescape JSON string
        try:
            content = json.loads(f'"{raw}"')
        except (json.JSONDecodeError, ValueError):
            content = raw
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
            .replace("&lt;", "<")
            .replace("&gt;", ">")
            .replace("&amp;", "&")
            .replace("&quot;", '"')
            .strip()
        )
        if len(text) > 50:
            meta["body_text_cn"] = text

    # Keywords from meta
    m = re.search(r'<meta\s+name="keywords"\s+content="([^"]+)"', html)
    if m:
        meta["keywords"] = m.group(1).strip()

    # Author
    m = re.search(r'"authorName"\s*:\s*"([^"]+)"', html)
    if m:
        meta["publisher"] = m.group(1).strip()

    return meta


def crawl(conn, list_only: bool = False):
    """Crawl 36Kr articles from RSS feed."""
    store_site(conn, SITE_KEY, SITE_CFG)

    log.info("Fetching 36Kr RSS feed...")
    try:
        xml = fetch(RSS_URL, headers={"User-Agent": BROWSER_UA})
    except Exception as e:
        log.error(f"Failed to fetch RSS feed: {e}")
        return 0

    articles = _parse_rss(xml)
    log.info(f"Found {len(articles)} articles in RSS feed")

    if list_only:
        for a in articles:
            print(f"  {a['date_str']}  {a['url']}  {a['title'][:60]}")
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
        title = meta.get("title", article["title"])
        if not title:
            log.warning(f"  No title for {url}, skipping")
            continue

        doc_id = existing[0] if existing else next_id(conn)
        raw_html_path = save_raw_html(SITE_KEY, doc_id, article_html)

        store_document(conn, SITE_KEY, {
            "id": doc_id,
            "title": title,
            "publisher": meta.get("publisher", "36氪"),
            "keywords": meta.get("keywords", ""),
            "abstract": meta.get("abstract", ""),
            "date_written": _parse_date(article["date_str"]),
            "date_published": article["date_str"],
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
    log.info(f"=== 36Kr: {stored} new, {skipped} skipped, {len(articles)} in feed ===")
    return stored


def main():
    parser = argparse.ArgumentParser(description="36Kr Crawler (via RSS)")
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
