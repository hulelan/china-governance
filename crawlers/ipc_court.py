"""
Supreme People's Court IP Tribunal (最高人民法院知识产权法庭) crawler.

Crawls case reports, news, and legal analysis from ipc.court.gov.cn.
The site is an SPA with no paginated listing, so we discover articles
from the homepage and iterate known ID ranges for historical content.

Usage:
    python -m crawlers.ipc_court                   # Crawl (listing + recent IDs)
    python -m crawlers.ipc_court --deep            # Crawl all IDs 1-max
    python -m crawlers.ipc_court --stats           # Show database stats
    python -m crawlers.ipc_court --list-only       # List URLs without fetching
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

SITE_KEY = "ipc_court"
SITE_CFG = {
    "name": "Supreme Court IP Tribunal (最高人民法院知识产权法庭)",
    "base_url": "https://ipc.court.gov.cn",
    "admin_level": "central",
}

BASE_URL = "https://ipc.court.gov.cn"
CST = timezone(timedelta(hours=8))
BROWSER_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)


def _parse_date(date_str: str) -> int:
    date_str = date_str.replace(".", "-").replace("/", "-").strip()
    try:
        dt = datetime.strptime(date_str[:10], "%Y-%m-%d").replace(tzinfo=CST)
        return int(dt.timestamp())
    except ValueError:
        return 0


def _discover_articles_from_listing() -> list[int]:
    """Get article IDs from the news listing page."""
    html = fetch(f"{BASE_URL}/zh-cn/news/index.html", headers={"User-Agent": BROWSER_UA})
    if not html:
        log.error("Failed to fetch listing page")
        return []
    ids = [int(x) for x in re.findall(r'view-(\d+)\.html', html)]
    return sorted(set(ids))


def _extract_article(html: str) -> dict:
    """Extract metadata and body from an article page."""
    meta = {}

    # Title
    m = re.search(r'<title>([^<]+?)(?:\s*-\s*最高人民法院知识产权法庭)?</title>', html)
    if m:
        meta["title"] = m.group(1).strip()

    # Date — look in article body area
    m = re.search(r'class="article"', html)
    if m:
        start = html.find(">", m.start()) + 1
        # Look for date near top of article
        date_m = re.search(r'(\d{4}-\d{2}-\d{2})', html[start:start + 500])
        if date_m:
            meta["date_published"] = date_m.group(1)

    # Source/author
    m = re.search(r'来源[：:]\s*([^\s<]+)', html)
    if m:
        meta["source"] = m.group(1).strip()

    # Body text from <article> or class="article"
    body = ""
    for pattern in [r'<article[^>]*>(.*?)</article>',
                    r'class="article"[^>]*>(.*?)(?:</div>\s*</div>|<div class="share)']:
        m = re.search(pattern, html, re.DOTALL)
        if m:
            content = m.group(1)
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
                body = text
                break

    meta["body_text_cn"] = body
    return meta


def crawl(conn, list_only: bool = False, deep: bool = False):
    """Crawl IP Tribunal articles."""
    store_site(conn, SITE_KEY, SITE_CFG)

    # Discover IDs from listing page
    listing_ids = _discover_articles_from_listing()
    max_listing_id = max(listing_ids) if listing_ids else 5500
    log.info(f"Listing page: {len(listing_ids)} articles (max ID: {max_listing_id})")

    if deep:
        # Iterate all IDs from 1 to max
        all_ids = list(range(1, max_listing_id + 1))
        log.info(f"Deep mode: will try {len(all_ids)} IDs")
    else:
        # Just use listing IDs + recent range above max known
        all_ids = listing_ids
        # Also try IDs above max listing to catch very recent articles
        for extra_id in range(max_listing_id + 1, max_listing_id + 50):
            if extra_id not in all_ids:
                all_ids.append(extra_id)

    if list_only:
        for aid in sorted(all_ids):
            print(f"  {BASE_URL}/zh-cn/news/view-{aid}.html")
        return len(all_ids)

    stored = 0
    bodies = 0
    skipped = 0
    errors = 0
    consecutive_errors = 0

    for aid in sorted(all_ids):
        url = f"{BASE_URL}/zh-cn/news/view-{aid}.html"

        existing = conn.execute(
            "SELECT id, body_text_cn FROM documents WHERE url = ?", (url,)
        ).fetchone()
        if existing and existing[1]:
            skipped += 1
            consecutive_errors = 0
            continue

        try:
            html = fetch(url, headers={"User-Agent": BROWSER_UA})
            consecutive_errors = 0
        except Exception as e:
            err_str = str(e)
            if "404" in err_str or "451" in err_str:
                # Article doesn't exist at this ID
                consecutive_errors += 1
                if deep and consecutive_errors > 20:
                    log.info(f"  20 consecutive missing IDs at {aid}, skipping ahead")
                    consecutive_errors = 0
                continue
            log.warning(f"  Failed {url}: {err_str[:60]}")
            errors += 1
            if errors > 10:
                log.warning("  Too many errors, stopping")
                break
            time.sleep(REQUEST_DELAY * 2)
            continue

        meta = _extract_article(html)
        if not meta.get("title"):
            continue

        doc_id = existing[0] if existing else next_id(conn)
        date_str = meta.get("date_published", "")
        raw_html_path = save_raw_html(SITE_KEY, doc_id, html) if html else ""

        store_document(conn, SITE_KEY, {
            "id": doc_id,
            "title": meta["title"],
            "publisher": meta.get("source", "最高人民法院知识产权法庭"),
            "date_written": _parse_date(date_str),
            "date_published": date_str,
            "body_text_cn": meta.get("body_text_cn", ""),
            "url": url,
            "classify_main_name": "知识产权法庭",
            "raw_html_path": raw_html_path,
        })
        stored += 1
        if meta.get("body_text_cn"):
            bodies += 1

        if stored % 20 == 0:
            conn.commit()
            log.info(f"  Progress: {stored} stored, {bodies} bodies, {skipped} skipped")

        time.sleep(REQUEST_DELAY)

    conn.commit()
    log.info(f"=== IP Tribunal: {stored} new, {skipped} skipped, {bodies} bodies, {errors} errors ===")
    return stored


def main():
    parser = argparse.ArgumentParser(description="Supreme Court IP Tribunal Crawler")
    parser.add_argument("--stats", action="store_true", help="Show database stats")
    parser.add_argument("--list-only", action="store_true",
                        help="List article URLs without fetching")
    parser.add_argument("--deep", action="store_true",
                        help="Crawl all IDs (slow, for initial backfill)")
    parser.add_argument("--db", type=str,
                        help="Path to SQLite database (default: documents.db)")
    args = parser.parse_args()

    conn = init_db(Path(args.db) if args.db else None)

    if args.stats:
        show_stats(conn)
        conn.close()
        return

    crawl(conn, list_only=args.list_only, deep=args.deep)
    show_stats(conn)
    conn.close()


if __name__ == "__main__":
    main()
