"""
Ministry of Industry and Information Technology (工信部) crawler.

Crawls policy documents from www.miit.gov.cn via the site's Elasticsearch-based
search API (search-front-server/api/search/info). The listing pages redirect
to a JS search interface, so we use the API directly.

Sections crawled (by category ID):
  - wjfb:   文件发布    (Document releases, category=51)
  - zcfb:   政策发布    (Policy releases, category=183)
  - zcjd:   政策解读    (Policy interpretations, category=163)

Usage:
    python -m crawlers.miit                    # Crawl all sections
    python -m crawlers.miit --section wjfb     # Crawl only document releases
    python -m crawlers.miit --stats            # Show database stats
    python -m crawlers.miit --list-only        # List URLs without fetching
"""

import argparse
import re
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path

from crawlers.base import (
    REQUEST_DELAY,
    fetch,
    fetch_json,
    init_db,
    log,
    next_id,
    save_raw_html,
    show_stats,
    store_document,
    store_site,
)

SITE_KEY = "miit"
SITE_CFG = {
    "name": "Ministry of Industry and Information Technology",
    "base_url": "https://www.miit.gov.cn",
    "admin_level": "central",
}

CST = timezone(timedelta(hours=8))

API_BASE = "https://www.miit.gov.cn/search-front-server/api/search/info"
WEBSITE_ID = "110000000000000"

SECTIONS = {
    "wjfb": {
        "name": "文件发布",
        "category": "51",
    },
    "zcfb": {
        "name": "政策发布",
        "category": "183",
    },
    "zcjd": {
        "name": "政策解读",
        "category": "163",
    },
}


def _parse_date(date_str: str) -> int:
    """Convert date string to Unix timestamp at midnight CST."""
    date_str = date_str.strip()[:10]
    try:
        dt = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=CST)
        return int(dt.timestamp())
    except ValueError:
        return 0


def _search_api(category: str, page: int, per_page: int = 15) -> dict:
    """Call MIIT search API and return parsed JSON."""
    url = (
        f"{API_BASE}?websiteid={WEBSITE_ID}"
        f"&category={category}&pg={per_page}&p={page}&q="
    )
    return fetch_json(url, headers={
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                      "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    })


def _parse_api_results(data: dict) -> list[dict]:
    """Parse search API results into item dicts."""
    items = []
    sr = data.get("data", {}).get("searchResult", {})
    for r in sr.get("dataResults", []):
        d = r.get("data", {})
        title = d.get("title", "").strip()
        url = d.get("url", "").strip()
        date_str = d.get("jsearch_date", "")[:10]

        if not title or not url:
            continue

        # Normalize relative URLs
        if url.startswith("/"):
            url = f"https://www.miit.gov.cn{url}"
        elif not url.startswith("http"):
            url = f"https://www.miit.gov.cn/{url}"

        items.append({
            "url": url,
            "title": title,
            "date_str": date_str,
        })
    return items


def _extract_body(html: str) -> str:
    """Extract body text from MIIT article page."""
    # Try xxgk-detail format first (div.xxgk-con or similar)
    for selector in ['class="xxgk_con"', 'class="article_con"', 'id="con_con"',
                      'class="cntent_con_box"', 'class="page-content"',
                      'class="con_text"', 'class="content"']:
        pos = html.find(selector)
        if pos != -1:
            gt = html.find(">", pos)
            if gt == -1:
                continue
            content_start = gt + 1
            end_pos = len(html)
            for marker in ['<div class="page', '<div class="share', '<div class="bot',
                            '<script', '<!-- footer', '<div class="foot']:
                mp = html.find(marker, content_start)
                if mp != -1 and mp < end_pos:
                    end_pos = mp
            content = html[content_start:end_pos]
            text = _clean_html(content)
            if text:
                return text

    # Fallback: find the largest text block in the page
    return ""


def _clean_html(content: str) -> str:
    """Strip HTML tags and normalize whitespace."""
    if not content.strip():
        return ""
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
    return text if len(text) > 20 else ""


def _extract_meta(html: str) -> dict:
    """Extract metadata from MIIT article page."""
    meta = {}
    for name in ("ArticleTitle", "PubDate", "ContentSource", "Keywords"):
        m = re.search(
            rf'<meta\s+name=["\']?{name}["\']?\s+content=["\']([^"\']*)["\']',
            html, re.IGNORECASE,
        )
        if m:
            meta[name] = m.group(1).strip()
    return meta


def _extract_doc_number(body_text: str) -> str:
    """Extract document number from body text."""
    head = body_text[:500]
    m = re.search(
        r"([\u4e00-\u9fff]+[\u3014\u3008\u300a\uff08\u2018\u301a〔]"
        r"(?:19|20)\d{2}"
        r"[\u3015\u3009\u300b\uff09\u2019\u301b〕]"
        r"\d+号)",
        head,
    )
    return m.group(1) if m else ""


def crawl_section(conn, section_key: str, section: dict, fetch_bodies: bool = True):
    """Crawl a single MIIT section via search API."""
    name = section["name"]
    category = section["category"]
    log.info(f"--- Section: {name} ({section_key}, category={category}) ---")

    all_items = []
    page = 1
    max_pages = 200  # Safety limit

    while page <= max_pages:
        try:
            data = _search_api(category, page)
            page_items = _parse_api_results(data)
            if not page_items:
                break
            all_items.extend(page_items)
            if page % 10 == 0:
                log.info(f"  Page {page}: {len(all_items)} items so far")
        except Exception as e:
            log.warning(f"  Failed page {page}: {e}")
            break
        page += 1
        time.sleep(REQUEST_DELAY)

    # Deduplicate by URL
    seen = set()
    unique_items = []
    for item in all_items:
        if item["url"] not in seen:
            seen.add(item["url"])
            unique_items.append(item)
    all_items = unique_items

    log.info(f"  Found {len(all_items)} unique document links across {page-1} pages")

    stored = 0
    bodies = 0
    skipped = 0
    for item in all_items:
        doc_url = item["url"]

        # Skip external URLs (some results link to subdomain sites)
        if "miit.gov.cn" not in doc_url:
            continue

        existing = conn.execute(
            "SELECT id, body_text_cn FROM documents WHERE url = ?", (doc_url,)
        ).fetchone()
        if existing and existing[1]:
            skipped += 1
            continue

        doc_id = existing[0] if existing else next_id(conn)
        body_text = ""
        raw_html_path = ""
        doc_number = ""
        publisher = "工业和信息化部"
        date_published = item["date_str"]
        title = item["title"]

        if fetch_bodies:
            try:
                doc_html = fetch(doc_url, headers={
                    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                                  "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
                })
                meta = _extract_meta(doc_html)
                body_text = _extract_body(doc_html)
                doc_number = _extract_doc_number(body_text) if body_text else ""
                if meta.get("ArticleTitle"):
                    title = meta["ArticleTitle"]
                if meta.get("ContentSource"):
                    publisher = meta["ContentSource"]
                if meta.get("PubDate"):
                    date_published = meta["PubDate"][:10]
                if doc_html:
                    raw_html_path = save_raw_html(SITE_KEY, doc_id, doc_html)
                    bodies += 1
            except Exception as e:
                log.warning(f"  Failed to fetch {doc_url}: {e}")
            time.sleep(REQUEST_DELAY)

        store_document(conn, SITE_KEY, {
            "id": doc_id,
            "title": title,
            "document_number": doc_number,
            "publisher": publisher,
            "date_written": _parse_date(date_published),
            "date_published": date_published,
            "body_text_cn": body_text,
            "url": doc_url,
            "classify_main_name": name,
            "raw_html_path": raw_html_path,
            "keywords": "",
        })
        stored += 1

        if stored % 20 == 0:
            conn.commit()
            log.info(f"  Progress: {stored} stored, {bodies} bodies, {skipped} skipped")

    conn.commit()
    log.info(f"  Done: {stored} stored, {bodies} bodies, {skipped} skipped")
    return stored


def crawl_all(conn, sections: dict = None, fetch_bodies: bool = True):
    """Crawl all (or specified) MIIT sections."""
    if sections is None:
        sections = SECTIONS

    store_site(conn, SITE_KEY, SITE_CFG)
    total = 0
    for key, section in sections.items():
        total += crawl_section(conn, key, section, fetch_bodies)
        time.sleep(REQUEST_DELAY)

    log.info(f"=== MIIT total: {total} documents ===")


def main():
    parser = argparse.ArgumentParser(description="MIIT Policy Crawler")
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
