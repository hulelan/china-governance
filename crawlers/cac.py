"""
Cyberspace Administration of China (国家互联网信息办公室) crawler.

Crawls policy documents from www.cac.gov.cn. The site uses a JSON API
(POST /cms/JsonList) for paginated listings with channel codes.

Sections crawled:
  - wxfb:  网信发布   (Cyberspace releases)
  - zcfg:  政策法规   (Policies & regulations)

Usage:
    python -m crawlers.cac                    # Crawl all sections
    python -m crawlers.cac --section wxfb     # Crawl only releases
    python -m crawlers.cac --stats            # Show database stats
    python -m crawlers.cac --list-only        # List URLs without fetching
"""

import argparse
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone, timedelta
from pathlib import Path

from crawlers.base import (
    REQUEST_DELAY,
    USER_AGENT,
    fetch,
    init_db,
    log,
    next_id,
    save_raw_html,
    show_stats,
    store_document,
    store_site,
)

SITE_KEY = "cac"
SITE_CFG = {
    "name": "Cyberspace Administration of China",
    "base_url": "https://www.cac.gov.cn",
    "admin_level": "central",
}

CST = timezone(timedelta(hours=8))

SECTIONS = {
    "wxfb": {
        "name": "网信发布",
        "channel_code": "A093702",
        "listing_path": "/wxzw/wxfb/A093702index_1.htm",
    },
    "zcfg": {
        "name": "政策法规",
        "channel_code": "A093703",
        "listing_path": "/zcfg/A093703index_1.htm",
    },
}


def _parse_date(date_str: str) -> int:
    """Convert date string like '2026-03-17' or '2026年03月17日 19:36' to Unix timestamp."""
    date_str = date_str.strip()
    # Handle '2026年03月17日 19:36' format
    m = re.match(r"(\d{4})\D+(\d{2})\D+(\d{2})", date_str)
    if m:
        try:
            dt = datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)), tzinfo=CST)
            return int(dt.timestamp())
        except ValueError:
            return 0
    return 0


def _normalize_url(href: str) -> str:
    """Normalize a CAC URL: protocol-relative URLs to https."""
    href = href.strip()
    if href.startswith("//"):
        href = "https:" + href
    elif href.startswith("/"):
        href = "https://www.cac.gov.cn" + href
    return href


def _post_json_list(channel_code: str, page: int, per_page: int = 20) -> dict:
    """POST to /cms/JsonList and return parsed JSON response."""
    url = "https://www.cac.gov.cn/cms/JsonList"
    data = urllib.parse.urlencode({
        "channelCode": channel_code,
        "perPage": str(per_page),
        "pageno": str(page),
    }).encode("utf-8")

    headers = {
        "User-Agent": USER_AGENT,
        "Content-Type": "application/x-www-form-urlencoded",
        "Referer": "https://www.cac.gov.cn/",
    }

    req = urllib.request.Request(url, data=data, headers=headers)
    for attempt in range(3):
        try:
            resp = urllib.request.urlopen(req, timeout=20)
            text = resp.read().decode("utf-8", errors="replace")
            return json.loads(text)
        except (urllib.error.HTTPError, urllib.error.URLError, OSError, json.JSONDecodeError) as e:
            if attempt < 2:
                wait = 2 ** attempt
                log.warning(f"  Retry {attempt+1}/3 for JsonList page {page}: {e}")
                time.sleep(wait)
                # Rebuild request for retry
                req = urllib.request.Request(url, data=data, headers=headers)
            else:
                log.error(f"  Failed JsonList page {page} after 3 retries: {e}")
                return {}


def _get_total_from_html(html: str) -> int:
    """Extract total item count from the listing page HTML/JS."""
    # Look for total:'400' or total: '400' or total:400 patterns
    m = re.search(r"total\s*[:=]\s*['\"]?(\d+)['\"]?", html)
    if m:
        return int(m.group(1))
    return 0


def _parse_html_listing(html: str) -> list[dict]:
    """Parse document links from the initial HTML listing page.

    Format: <li><h5><a href=//www.cac.gov.cn/... title="Title">Title</a></h5>
            <div class="times">2026-03-17</div></li>
    """
    items = []
    # Match <a> tags with href and title, followed by a date
    for m in re.finditer(
        r'<a\s+href\s*=\s*(["\']?)([^"\'>\s]+)\1[^>]*'
        r'title\s*=\s*["\']?([^"\'<>]+)["\']?[^>]*>.*?'
        r'<div\s+class=["\']times["\']>\s*(\d{4}-\d{2}-\d{2})\s*</div>',
        html,
        re.DOTALL,
    ):
        href = m.group(2)
        title = m.group(3).strip()
        date_str = m.group(4).strip()
        doc_url = _normalize_url(href)
        if title and doc_url:
            items.append({
                "url": doc_url,
                "title": title,
                "date_str": date_str,
            })
    return items


def _parse_json_listing(data: dict) -> list[dict]:
    """Parse items from the JsonList API response."""
    items = []
    for entry in data.get("list", []):
        title = entry.get("topic", "").strip()
        href = entry.get("infourl", "").strip()
        pubtime = entry.get("pubtime", "").strip()

        if not title or not href:
            continue

        doc_url = _normalize_url(href)
        date_str = pubtime[:10] if len(pubtime) >= 10 else pubtime

        items.append({
            "url": doc_url,
            "title": title,
            "date_str": date_str,
        })
    return items


def _extract_body(html: str) -> str:
    """Extract body text from article page.

    Structure: <div class="main-content"><DIV id=BodyLabel>...</DIV></div>
    """
    # Try id=BodyLabel or id="BodyLabel" first
    m = re.search(r'<(?:div|DIV)\s+id\s*=\s*["\']?BodyLabel["\']?[^>]*>', html, re.IGNORECASE)
    if m:
        start = m.end()
        # Find closing </div> or </DIV>
        depth = 1
        pos = start
        while depth > 0 and pos < len(html):
            open_m = re.search(r'<div[^>]*>', html[pos:], re.IGNORECASE)
            close_m = re.search(r'</div>', html[pos:], re.IGNORECASE)
            if close_m is None:
                break
            if open_m and open_m.start() < close_m.start():
                depth += 1
                pos += open_m.end()
            else:
                depth -= 1
                if depth == 0:
                    end = pos + close_m.start()
                    content = html[start:end]
                    return _clean_html(content)
                pos += close_m.end()

    # Fallback: <div class="main-content">
    m = re.search(r'<div\s+class=["\']main-content["\'][^>]*>', html, re.IGNORECASE)
    if m:
        start = m.end()
        end = html.find("</div>", start)
        if end == -1:
            end = start + 50000
        content = html[start:end]
        return _clean_html(content)

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
    """Extract title, date, and source from article page."""
    meta = {}

    # Title: <h1 class="title">
    m = re.search(r'<h1[^>]*class=["\']title["\'][^>]*>(.*?)</h1>', html, re.DOTALL)
    if m:
        meta["title"] = re.sub(r"<[^>]+>", "", m.group(1)).strip()

    # Date: <span id="pubtime">2026年03月17日 19:36</span>
    m = re.search(r'<span[^>]*id=["\']pubtime["\'][^>]*>(.*?)</span>', html, re.DOTALL)
    if m:
        meta["pubtime"] = re.sub(r"<[^>]+>", "", m.group(1)).strip()

    # Source: <span id="source">来源：<a>中国网信网</a></span>
    m = re.search(r'<span[^>]*id=["\']source["\'][^>]*>(.*?)</span>', html, re.DOTALL)
    if m:
        source_text = re.sub(r"<[^>]+>", "", m.group(1)).strip()
        source_text = re.sub(r"^来源[：:]?\s*", "", source_text).strip()
        if source_text:
            meta["source"] = source_text

    return meta


def _extract_doc_number(body_text: str) -> str:
    """Extract document number (e.g. 国办发〔2026〕6号) from body text."""
    head = body_text[:500]
    m = re.search(
        r"([\u4e00-\u9fff]+[\u3014\u3008\u300a\uff08\u2018\u301a〔]"
        r"(?:19|20)\d{2}"
        r"[\u3015\u3009\u300b\uff09\u2019\u301b〕]"
        r"\d+号)",
        head,
    )
    return m.group(1) if m else ""


def _dedup_items(items: list[dict]) -> list[dict]:
    """Remove duplicates by URL."""
    seen = set()
    result = []
    for item in items:
        if item["url"] not in seen:
            seen.add(item["url"])
            result.append(item)
    return result


def crawl_section(conn, section_key: str, section: dict, fetch_bodies: bool = True):
    """Crawl a single CAC section via JsonList API."""
    name = section["name"]
    channel_code = section["channel_code"]
    listing_path = section["listing_path"]
    log.info(f"--- Section: {name} ({section_key}) ---")

    all_items = []

    # 1. Fetch the HTML listing page to get initial items + total count
    listing_url = f"https://www.cac.gov.cn{listing_path}"
    try:
        html = fetch(listing_url)
        html_items = _parse_html_listing(html)
        all_items.extend(html_items)
        total = _get_total_from_html(html)
        log.info(f"  HTML page: {len(html_items)} items, total reported: {total}")
    except Exception as e:
        log.warning(f"  Failed to fetch HTML listing {listing_url}: {e}")
        total = 0

    # 2. Fetch all pages via the JSON API
    per_page = 20
    if total > 0:
        total_pages = (total + per_page - 1) // per_page
    else:
        total_pages = 50  # Conservative max if we can't determine total

    for page in range(1, total_pages + 1):
        try:
            data = _post_json_list(channel_code, page, per_page)
            if not data:
                log.warning(f"  Empty response for page {page}, stopping.")
                break
            page_items = _parse_json_listing(data)
            if not page_items:
                log.info(f"  No items on page {page}, stopping pagination.")
                break
            all_items.extend(page_items)
            if page % 5 == 0:
                log.info(f"  Fetched JSON page {page}/{total_pages}, running total: {len(all_items)} items")
        except Exception as e:
            log.warning(f"  Failed JSON page {page}: {e}")
        time.sleep(REQUEST_DELAY)

    # Deduplicate (HTML page items may overlap with JSON page 1)
    all_items = _dedup_items(all_items)
    log.info(f"  Found {len(all_items)} unique document links")

    stored = 0
    bodies = 0
    skipped = 0
    for item in all_items:
        doc_url = item["url"]
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
        publisher = "国家互联网信息办公室"
        date_published = item["date_str"]
        title = item["title"]

        if fetch_bodies:
            try:
                doc_html = fetch(doc_url)
                meta = _extract_meta(doc_html)
                body_text = _extract_body(doc_html)
                doc_number = _extract_doc_number(body_text) if body_text else ""

                if meta.get("title"):
                    title = meta["title"]
                if meta.get("source"):
                    publisher = meta["source"]
                if meta.get("pubtime"):
                    # Extract date part from '2026年03月17日 19:36'
                    pm = re.match(r"(\d{4})\D+(\d{2})\D+(\d{2})", meta["pubtime"])
                    if pm:
                        date_published = f"{pm.group(1)}-{pm.group(2)}-{pm.group(3)}"

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
    log.info(f"  Done: {stored} new documents stored, {bodies} bodies fetched, {skipped} already existed")
    return stored


def crawl_all(conn, sections: dict = None, fetch_bodies: bool = True):
    """Crawl all (or specified) CAC sections."""
    if sections is None:
        sections = SECTIONS

    store_site(conn, SITE_KEY, SITE_CFG)
    total = 0
    for key, section in sections.items():
        total += crawl_section(conn, key, section, fetch_bodies)
        time.sleep(REQUEST_DELAY)

    log.info(f"=== CAC total: {total} documents ===")


def main():
    parser = argparse.ArgumentParser(description="CAC Policy Crawler")
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
