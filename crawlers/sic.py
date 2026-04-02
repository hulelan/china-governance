"""
State Information Center (国家信息中心) crawler.

Crawls research publications and policy analysis from www.sic.gov.cn.
Same CMS as NDA — static HTML with JS-driven pagination.

Key sections: digital economy, informatization research, macroeconomic analysis.

Usage:
    python -m crawlers.sic                    # Crawl all sections
    python -m crawlers.sic --section digital  # One section only
    python -m crawlers.sic --stats            # Show database stats
    python -m crawlers.sic --list-only        # List URLs without fetching
"""

import argparse
import json
import math
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

SITE_KEY = "sic"
SITE_CFG = {
    "name": "State Information Center (国家信息中心)",
    "base_url": "https://www.sic.gov.cn",
    "admin_level": "central",
}

BASE_URL = "https://www.sic.gov.cn"
CST = timezone(timedelta(hours=8))

SECTIONS = {
    "digital": {
        "name": "大数据与数字中国",
        "path": "/sic/608/609/list/",
    },
    "informatization": {
        "name": "信息化与产业发展研究",
        "path": "/sic/82/566/list/",
    },
    "egov": {
        "name": "电子政务网络",
        "path": "/sic/200/571/462/list/",
    },
    "macro": {
        "name": "宏观经济分析",
        "path": "/sic/81/455/list/",
    },
    "news": {
        "name": "政务要闻",
        "path": "/sic/83/634/list/",
    },
    "achievements": {
        "name": "工作成果",
        "path": "/sic/93/552/592/list/",
    },
}


def _parse_date(date_str: str) -> int:
    """Convert date string to Unix timestamp at midnight CST."""
    date_str = date_str.replace(".", "-").replace("/", "-").strip()
    try:
        dt = datetime.strptime(date_str[:10], "%Y-%m-%d").replace(tzinfo=CST)
        return int(dt.timestamp())
    except ValueError:
        return 0


def _listing_url(base_path: str, page: int) -> str:
    return f"{BASE_URL}{base_path}index_pc_{page}.html"


def _get_total_pages(html: str) -> int:
    """Extract total pages from JS pagination or '共X页' text."""
    # Try JS pagination config first (same as NDA)
    m_total = re.search(r"totalData:\s*(\d+)", html)
    m_per = re.search(r"showData:\s*(\d+)", html)
    if m_total and m_per:
        total = int(m_total.group(1))
        per_page = int(m_per.group(1))
        if per_page > 0:
            return math.ceil(total / per_page)
    if m_total:
        return math.ceil(int(m_total.group(1)) / 20)
    # Fallback: look for 共X页
    m = re.search(r"共(\d+)页", html)
    if m:
        return int(m.group(1))
    return 1


def _parse_listing(html: str) -> list[dict]:
    """Parse listing page items.

    SIC uses <ul class="u-list"> or similar list structures with
    <li><a href="...">Title</a><span>YYYY-MM-DD</span></li>
    """
    items = []

    # Find all article links — SIC article URLs contain timestamp IDs
    # Pattern: /sic/.../{MMDD}/{YYYYMMDDHHMMSS}{ID}_pc.html
    for m in re.finditer(
        r'<a\s+href="(/sic/[^"]+_pc\.html)"[^>]*(?:title="([^"]*)")?[^>]*>(.*?)</a>',
        html, re.DOTALL
    ):
        href = m.group(1)
        title = m.group(2) or ""
        if not title:
            # Extract title from link text
            title = re.sub(r"<[^>]+>", "", m.group(3)).strip()
        if not title or "/list/" in href:
            continue

        # Find the date near this link
        after = html[m.end():m.end() + 200]
        date_match = re.search(r"(\d{4}[-./]\d{2}[-./]\d{2})", after)
        date_str = date_match.group(1).replace(".", "-").replace("/", "-") if date_match else ""

        doc_url = urljoin(BASE_URL, href)
        if doc_url not in [i["url"] for i in items]:
            items.append({"url": doc_url, "title": title, "date_str": date_str})

    return items


def _extract_body(html: str) -> str:
    """Extract body text from article page."""
    # Try articleDetailsText first (SIC-specific), then article (NDA-style)
    for class_name in ["articleDetailsText", "article", "TRS_Editor"]:
        m = re.search(rf'class="{class_name}"', html)
        if not m:
            continue
        start = html.find(">", m.start()) + 1
        # Find end — look for common terminators
        end = len(html)
        for marker in ['class="filelist"', 'class="article-footer"',
                       'class="share"', 'class="relation"',
                       'id="div_curr498"', '<!-- end article']:
            pos = html.find(marker, start)
            if pos != -1 and pos < end:
                end = pos
        content = html[start:end]
        # Clean HTML to text
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
            .replace("&ldquo;", "\u201c")
            .replace("&rdquo;", "\u201d")
            .strip()
        )
        if len(text) > 50:
            return text
    return ""


def _extract_meta(html: str) -> dict:
    """Extract metadata from <meta> tags."""
    meta = {}
    for name in ("ArticleTitle", "PubDate", "ContentSource", "Keywords",
                 "ColumnName", "Description", "Author"):
        m = re.search(
            rf'<meta\s+name=["\']?{name}["\']?\s+content=["\']([^"\']*)["\']',
            html, re.IGNORECASE,
        )
        if m:
            meta[name] = m.group(1).strip()
    return meta


def crawl_section(conn, section_key: str, section: dict, fetch_bodies: bool = True):
    """Crawl a single section."""
    name = section["name"]
    path = section["path"]
    log.info(f"--- Section: {name} ({section_key}) ---")

    first_url = _listing_url(path, 1)
    try:
        html = fetch(first_url)
    except Exception as e:
        log.error(f"Failed to fetch {first_url}: {e}")
        return 0

    total_pages = _get_total_pages(html)
    log.info(f"  {total_pages} listing pages")

    all_items = _parse_listing(html)

    for page in range(2, total_pages + 1):
        page_url = _listing_url(path, page)
        try:
            page_html = fetch(page_url)
            all_items.extend(_parse_listing(page_html))
        except Exception as e:
            log.warning(f"  Failed page {page}: {e}")
        time.sleep(REQUEST_DELAY)

    log.info(f"  Found {len(all_items)} document links")

    if not fetch_bodies:
        for item in all_items:
            print(f"  {item['date_str']}  {item['url']}")
            print(f"             {item['title']}")
        return len(all_items)

    stored = 0
    bodies = 0
    for item in all_items:
        doc_url = item["url"]
        existing = conn.execute(
            "SELECT id, body_text_cn FROM documents WHERE url = ?", (doc_url,)
        ).fetchone()
        if existing and existing[1]:
            stored += 1
            continue

        doc_id = existing[0] if existing else next_id(conn)
        body_text = ""
        raw_html_path = ""
        publisher = "国家信息中心"
        date_published = item["date_str"]

        try:
            doc_html = fetch(doc_url)
            meta = _extract_meta(doc_html)
            body_text = _extract_body(doc_html)
            publisher = meta.get("ContentSource", publisher) or publisher
            if meta.get("PubDate"):
                date_published = meta["PubDate"].replace(".", "-")[:10]
            if doc_html:
                raw_html_path = save_raw_html(SITE_KEY, doc_id, doc_html)
                bodies += 1
        except Exception as e:
            log.warning(f"  Failed to fetch {doc_url}: {e}")
        time.sleep(REQUEST_DELAY)

        store_document(conn, SITE_KEY, {
            "id": doc_id,
            "title": item["title"],
            "publisher": publisher,
            "keywords": meta.get("Keywords", "") if 'meta' in dir() else "",
            "abstract": meta.get("Description", "") if 'meta' in dir() else "",
            "date_written": _parse_date(date_published),
            "date_published": date_published,
            "body_text_cn": body_text,
            "url": doc_url,
            "classify_main_name": name,
            "raw_html_path": raw_html_path,
        })
        stored += 1

        if stored % 20 == 0:
            conn.commit()
            log.info(f"  Progress: {stored}/{len(all_items)} stored, {bodies} bodies")

    conn.commit()
    log.info(f"  Done: {stored} documents stored, {bodies} bodies fetched")
    return stored


def crawl_all(conn, sections: dict = None, fetch_bodies: bool = True):
    if sections is None:
        sections = SECTIONS
    store_site(conn, SITE_KEY, SITE_CFG)
    total = 0
    for key, section in sections.items():
        total += crawl_section(conn, key, section, fetch_bodies)
        time.sleep(REQUEST_DELAY)
    log.info(f"=== SIC total: {total} documents ===")


def main():
    parser = argparse.ArgumentParser(description="SIC (国家信息中心) Crawler")
    parser.add_argument("--section", choices=list(SECTIONS.keys()),
                        help="Crawl only this section")
    parser.add_argument("--stats", action="store_true", help="Show database stats")
    parser.add_argument("--list-only", action="store_true",
                        help="List URLs without fetching bodies")
    parser.add_argument("--db", type=str,
                        help="Path to SQLite database (default: documents.db)")
    args = parser.parse_args()

    conn = init_db(Path(args.db) if args.db else None)

    if args.stats:
        show_stats(conn)
        conn.close()
        return

    sections = {args.section: SECTIONS[args.section]} if args.section else None
    crawl_all(conn, sections, fetch_bodies=not args.list_only)
    show_stats(conn)
    conn.close()


if __name__ == "__main__":
    main()
