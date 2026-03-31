"""
Heilongjiang Province (黑龙江省) crawler.

Crawls policy documents from www.hlj.gov.cn.  Heilongjiang uses a custom CMS
with a JSON API at /common/search/{channelId} for document listings.  The API
returns full content (plain text and HTML) directly, so detail-page fetching
is only needed as a fallback.

API pattern:
  Listing: /common/search/{channelId}?page={p}&_pageSize=15&_isAgg=true&_isJson=true&_template=index
  Returns: { data: { total, page, rows, results: [ { title, url, content, contentHtml,
            publishedTimeStr, subTitle, domainMetaList: [ { resultList: [ { key, value } ] } ] } ] } }

Metadata keys in domainMetaList:
  refno        = document number (文号), e.g. "黑政发〔2026〕4号"
  writedate    = composition date (成文日期)
  pubdate      = publication date (发文日期)
  indexnumber   = index number (索引号)
  theme        = topic classification (主题分类)
  source       = source (来源)

Detail page:
  Body:  div.article_content > UCAPCONTENT
  Meta:  UCAPTITLE, PUBLISHTIME, source span

Sections crawled (highest-value policy channels):
  - guizhang:     规章 (Provincial regulations)
  - xzgfxwj_szf:  省政府行政规范性文件 (Provincial gov normative docs)
  - xzgfxwj_bgt:  省政府办公厅行政规范性文件 (Provincial office normative docs)
  - hzf:          黑政发 (Provincial gov dispatches)
  - hzbf:         黑政办发 (Provincial office dispatches)
  - hzh:          黑政函 (Provincial gov letters)
  - zfl:          政府令 (Government orders/decrees)
  - zcjd:         政策解读-文字 (Policy interpretation - text)

Usage:
    python -m crawlers.heilongjiang                    # Crawl all sections
    python -m crawlers.heilongjiang --section hzf      # Crawl one section
    python -m crawlers.heilongjiang --stats            # Show database stats
    python -m crawlers.heilongjiang --list-only        # List without fetching bodies
    python -m crawlers.heilongjiang --db /tmp/hlj.db   # Use alternate database
"""

import argparse
import json
import re
import time
from datetime import datetime, timedelta, timezone
from html import unescape
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

SITE_KEY = "hlj"
SITE_CFG = {
    "name": "Heilongjiang Province",
    "base_url": "https://www.hlj.gov.cn",
    "admin_level": "provincial",
}

CST = timezone(timedelta(hours=8))
_BASE_URL = "https://www.hlj.gov.cn"
_PAGE_SIZE = 15

# Section key -> (display name, channel UUID for the API)
SECTIONS = {
    "guizhang":    ("规章",                       "817052cbb3a94d0d8217824e7a3aca53"),
    "xzgfxwj_szf": ("省政府行政规范性文件",       "b9e6fb997e274f05a8f8b0f2b7582a1c"),
    "xzgfxwj_bgt": ("省政府办公厅行政规范性文件", "779f8eda2ae847c2a46893fcc05284fc"),
    "hzf":         ("黑政发",                     "c7eb6a51b99845ea906d5ec83b0f8e27"),
    "hzbf":        ("黑政办发",                   "846ad3c5e14b4c37a37f824dbedd3cd7"),
    "hzh":         ("黑政函",                     "3353015959114703a571ccc3d27abb3c"),
    "zfl":         ("政府令",                     "c947f2e53a7c471b8f51976dd0c6dd00"),
    "zcjd":        ("政策解读-文字",              "6af535e7c17640ababf8f17adbaddac0"),
}


def _api_url(channel_id: str, page: int = 1) -> str:
    """Build the JSON API URL for a channel listing page."""
    return (
        f"{_BASE_URL}/common/search/{channel_id}"
        f"?page={page}&_pageSize={_PAGE_SIZE}"
        f"&_isAgg=true&_isJson=true&_template=index"
    )


def _parse_date(date_str: str) -> int:
    """Convert date string to Unix timestamp at midnight CST.

    Handles formats: "YYYY-MM-DD HH:MM:SS", "YYYY-MM-DD", "YYYY年MM月DD日"
    """
    if not date_str:
        return 0
    date_str = (
        date_str.replace("年", "-")
        .replace("月", "-")
        .replace("日", "")
        .strip()
    )
    # Take only the date part (YYYY-MM-DD)
    date_str = date_str[:10]
    try:
        dt = datetime.strptime(date_str.strip(), "%Y-%m-%d").replace(tzinfo=CST)
        return int(dt.timestamp())
    except ValueError:
        return 0


def _extract_meta(result: dict) -> dict:
    """Extract metadata from a single API result's domainMetaList.

    The API returns metadata in nested structures; this flattens it into
    a simple dict keyed by the metadata key names (refno, writedate, etc.).
    """
    meta = {}
    for domain in result.get("domainMetaList") or []:
        for item in domain.get("resultList") or []:
            key = item.get("key", "")
            value = item.get("value", "")
            if key and value and value not in ("null", "undefined"):
                meta[key] = value
    return meta


def _clean_text(text: str) -> str:
    """Clean HTML entities and whitespace from text content."""
    if not text:
        return ""
    # Unescape HTML entities
    text = unescape(text)
    # Replace HTML-encoded spaces
    text = text.replace("&ensp;", " ").replace("&emsp;", "  ")
    text = text.replace("\xa0", " ")
    # Clean whitespace
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n\s*\n", "\n", text)
    text = text.strip()
    if len(text) > 20:
        return text
    return ""


def _extract_body_from_html(html: str) -> str:
    """Extract plain text body from document detail page HTML.

    Used as a fallback when the API content field is empty.
    Heilongjiang uses div.article_content with <UCAPCONTENT> tags.
    """
    content = ""
    for pattern in [
        r"<UCAPCONTENT>(.*?)</UCAPCONTENT>",
        r'<div[^>]*class="[^"]*\barticle_content\b[^"]*"[^>]*>(.*?)</div>\s*(?:<div[^>]*class="[^"]*article_appendix|</div>)',
        r'<div[^>]*class="[^"]*\bTRS_Editor\b[^"]*"[^>]*>(.*?)</div>',
        r'<div[^>]*id=["\']zoomcon["\'][^>]*>(.*?)</div>',
    ]:
        m = re.search(pattern, html, re.DOTALL)
        if m:
            content = m.group(1)
            break

    if not content:
        return ""

    # Replace <br> and </p> with newlines
    content = re.sub(r"<br\s*/?\s*>", "\n", content)
    content = re.sub(r"</p>", "\n", content)
    # Strip HTML tags
    text = re.sub(r"<[^>]+>", "", content)
    return _clean_text(text)


def _fetch_api_page(channel_id: str, page: int = 1) -> dict | None:
    """Fetch one page from the search API and return parsed JSON."""
    url = _api_url(channel_id, page)
    try:
        text = fetch(url, timeout=30)
        data = json.loads(text)
        return data.get("data", {})
    except Exception as e:
        log.error(f"API request failed: {url}: {e}")
        return None


def crawl_section(
    conn, section_key: str, section_name: str, fetch_bodies: bool = True
):
    """Crawl all pages of a section via the API."""
    _, channel_id = SECTIONS[section_key]
    log.info(f"--- Section: {section_name} ({section_key}) ---")

    # Fetch first page to get total count
    data = _fetch_api_page(channel_id, page=1)
    if not data:
        log.error(f"  Failed to fetch first page for {section_name}")
        return 0

    total = data.get("total", 0)
    total_pages = (total + _PAGE_SIZE - 1) // _PAGE_SIZE if total > 0 else 0
    log.info(f"  {total} documents across {total_pages} pages")

    if total == 0:
        return 0

    stored = 0
    bodies = 0

    for page in range(1, total_pages + 1):
        if page > 1:
            time.sleep(REQUEST_DELAY)
            data = _fetch_api_page(channel_id, page)
            if not data:
                log.warning(f"  Failed to fetch page {page}")
                continue

        results = data.get("results") or []
        for result in results:
            doc_url = result.get("url", "")
            if doc_url and not doc_url.startswith("http"):
                doc_url = _BASE_URL + doc_url

            title = result.get("title", "").strip()
            if not title:
                continue

            # Skip if already stored with body text
            existing = conn.execute(
                "SELECT id, body_text_cn FROM documents WHERE url = ?",
                (doc_url,),
            ).fetchone()
            if existing and existing[1]:
                stored += 1
                continue

            doc_id = existing[0] if existing else next_id(conn)

            # Extract metadata from domainMetaList
            meta = _extract_meta(result)

            doc_number = meta.get("refno", "")
            identifier = meta.get("indexnumber", "")
            publisher = meta.get("source", "")
            theme = meta.get("theme", "")
            date_published = result.get("publishedTimeStr", "")[:10]
            date_written_str = meta.get("writedate", "")
            pub_date_str = meta.get("pubdate", "")

            # Use composition date (writedate) if available, else publication date
            date_written = _parse_date(date_written_str) or _parse_date(pub_date_str) or _parse_date(date_published)

            # Extract body text from API content field
            body_text = ""
            raw_html_path = ""

            if fetch_bodies:
                # The API returns content as plain text directly
                api_content = result.get("content", "")
                body_text = _clean_text(api_content)

                # If API content is empty, try fetching the detail page
                if not body_text and doc_url:
                    try:
                        doc_html = fetch(doc_url)
                        body_text = _extract_body_from_html(doc_html)
                        if doc_html:
                            raw_html_path = save_raw_html(SITE_KEY, doc_id, doc_html)
                    except Exception as e:
                        log.warning(f"  Failed to fetch detail {doc_url}: {e}")
                    time.sleep(REQUEST_DELAY)
                elif body_text:
                    bodies += 1

                # Save the contentHtml as raw HTML if we got it from the API
                if not raw_html_path and result.get("contentHtml"):
                    raw_html_path = save_raw_html(
                        SITE_KEY, doc_id, result["contentHtml"]
                    )

            store_document(conn, SITE_KEY, {
                "id": doc_id,
                "title": title,
                "document_number": doc_number,
                "identifier": identifier,
                "publisher": publisher,
                "date_written": date_written,
                "date_published": date_published,
                "body_text_cn": body_text,
                "url": doc_url,
                "classify_main_name": section_name,
                "classify_theme_name": theme,
                "raw_html_path": raw_html_path,
            })
            stored += 1

            if stored % 50 == 0:
                conn.commit()
                log.info(f"  Progress: {stored}/{total} stored, {bodies} bodies")

        conn.commit()

    log.info(f"  Done: {stored} documents stored, {bodies} bodies from API")
    return stored


def crawl_all(conn, sections: dict = None, fetch_bodies: bool = True):
    """Crawl all (or specified) Heilongjiang sections."""
    if sections is None:
        sections = {k: v[0] for k, v in SECTIONS.items()}

    store_site(conn, SITE_KEY, SITE_CFG)
    total = 0
    for section_key, name in sections.items():
        total += crawl_section(conn, section_key, name, fetch_bodies)
        time.sleep(REQUEST_DELAY)

    log.info(f"=== Heilongjiang total: {total} documents ===")


def main():
    parser = argparse.ArgumentParser(
        description="Heilongjiang Province Policy Crawler"
    )
    parser.add_argument(
        "--section",
        choices=list(SECTIONS.keys()),
        help="Crawl only this section",
    )
    parser.add_argument("--stats", action="store_true", help="Show database stats")
    parser.add_argument(
        "--list-only",
        action="store_true",
        help="List document URLs without fetching bodies",
    )
    parser.add_argument(
        "--db", type=str, help="Path to SQLite database (default: documents.db)",
    )
    args = parser.parse_args()

    conn = init_db(Path(args.db) if args.db else None)

    if args.stats:
        show_stats(conn)
        conn.close()
        return

    sections = (
        {args.section: SECTIONS[args.section][0]} if args.section else None
    )
    crawl_all(conn, sections, fetch_bodies=not args.list_only)
    show_stats(conn)
    conn.close()


if __name__ == "__main__":
    main()
