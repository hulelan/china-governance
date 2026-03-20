"""
Shanghai Municipality (上海市) crawler.

Crawls policy documents from www.shanghai.gov.cn. Shanghai organizes documents
by section, each with year-based archive pages using a jQuery pagination plugin.

URL patterns:
  Section index: /nw{section_id}/index.html
  Year archive:  /{prefix}{YYYY}/index.html (prefix varies by section/year)
  Pagination:    /{prefix}{YYYY}/index.html, index_2.html, index_3.html, ...
  Detail:        /nw12344/YYYYMMDD/{uuid}.html (or other prefixes)
  Body:          div.Article_content

Sections crawled:
  - nw39220: 沪府文件 (Municipal gov documents)
  - nw2407:  沪府令 (Municipal gov orders)
  - nw11407: 沪府发 (Municipal gov directives)
  - nw11408: 沪府办发 (Municipal office directives)
  - nw39221: 沪府办 (Municipal office documents)
  - nw42944: 沪府规 (Municipal gov regulations)

Usage:
    python -m crawlers.shanghai                     # Crawl all sections
    python -m crawlers.shanghai --section nw39220   # Crawl one section
    python -m crawlers.shanghai --stats             # Show database stats
    python -m crawlers.shanghai --list-only         # List without fetching bodies
"""

import argparse
import re
import time
from datetime import datetime, timedelta, timezone
from html import unescape
from urllib.parse import urljoin

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

SITE_KEY = "sh"
SITE_CFG = {
    "name": "Shanghai Municipality",
    "base_url": "https://www.shanghai.gov.cn",
    "admin_level": "provincial",
}

CST = timezone(timedelta(hours=8))

# Section ID -> section name
SECTIONS = {
    "nw39220": "沪府文件",
    "nw2407": "沪府令",
    "nw11407": "沪府发",
    "nw11408": "沪府办发",
    "nw39221": "沪府办",
    "nw42944": "沪府规",
}

_BASE_URL = "https://www.shanghai.gov.cn"


def _get_year_archive_urls(section_id: str) -> list[tuple[str, str]]:
    """Scrape year-archive links from a section's main index page.

    Returns list of (year_label, archive_url) tuples.
    Year-archive URL prefixes are inconsistent across sections and years,
    so we discover them dynamically rather than hardcoding.
    """
    url = f"{_BASE_URL}/{section_id}/index.html"
    html = fetch(url)
    archives = []
    # Year links may have nested tags: <a href="..."><h4>2024年</h4></a>
    # or plain text: <a href="...">2024年</a>
    for m in re.finditer(
        r'<a\s+href="(/[^"]+/index\.html)"[^>]*>.*?(\d{4})\s*年.*?</a>',
        html,
        re.DOTALL,
    ):
        href, year = m.group(1).strip(), m.group(2)
        full_url = urljoin(_BASE_URL, href)
        archives.append((year, full_url))
    return archives


def _get_total_pages(html: str) -> int:
    """Extract total page count from jQuery pagination plugin.

    Shanghai uses: $(".pagination").pagination({ totalPage: N, ... })
    """
    m = re.search(r"totalPage\s*:\s*(\d+)", html)
    if m:
        return int(m.group(1))
    return 1


def _page_url(base_index_url: str, page: int) -> str:
    """Build paginated URL from a year-archive base URL.

    Page 1 -> index.html, Page N (N>1) -> index_N.html
    """
    if page <= 1:
        return base_index_url
    return base_index_url.replace("index.html", f"index_{page}.html")


def _parse_listing(html: str, base_url: str) -> list[dict]:
    """Parse a Shanghai listing page.

    Items are <li> elements with:
      <li><a href="..." title="TITLE">text</a> <span class="time">YYYY-MM-DD</span></li>
    The page also has commented-out duplicates (<!-- ... -->) to skip.
    """
    # Strip HTML comments to avoid matching duplicates
    clean = re.sub(r'<!--.*?-->', '', html, flags=re.DOTALL)

    items = []
    # Pattern: <li>...<a href="URL" title="TITLE">...</a>...<span class="time">DATE</span></li>
    for m in re.finditer(
        r'<li[\s>][^<]*<a\s+href="([^"]+)"[^>]*title="([^"]*)"[^>]*>'
        r'[^<]*</a>\s*<span[^>]*class="time"[^>]*>(\d{4}-\d{2}-\d{2})</span>',
        clean,
    ):
        href, title, date_str = m.group(1), m.group(2), m.group(3)
        doc_url = urljoin(base_url, href.strip())
        items.append({
            "url": doc_url,
            "title": unescape(title.strip()),
            "date_str": date_str,
        })

    if items:
        return items

    # Fallback: date as plain text after </a>
    for m in re.finditer(
        r'<li[\s>][^<]*<a\s+href="([^"]+)"[^>]*title="([^"]*)"[^>]*>'
        r'[^<]*</a>\s*(\d{4}-\d{2}-\d{2})',
        clean,
    ):
        href, title, date_str = m.group(1), m.group(2), m.group(3)
        doc_url = urljoin(base_url, href.strip())
        items.append({
            "url": doc_url,
            "title": unescape(title.strip()),
            "date_str": date_str,
        })

    return items


def _parse_date(date_str: str) -> int:
    """Convert date string to Unix timestamp at midnight CST."""
    date_str = (
        date_str.replace("/", "-")
        .replace("年", "-")
        .replace("月", "-")
        .replace("日", "")
    )
    try:
        dt = datetime.strptime(date_str.strip(), "%Y-%m-%d").replace(tzinfo=CST)
        return int(dt.timestamp())
    except ValueError:
        return 0


def _extract_meta(html: str) -> dict:
    """Extract metadata from detail page."""
    meta = {}

    # Shanghai doesn't use standard <meta> tags for document metadata.
    # Look for document number patterns in the body text.
    m = re.search(r"(沪府[办规任发令]*〔\d{4}〕\d+号)", html)
    if m:
        meta["document_number"] = m.group(1)

    # Look for publisher
    m = re.search(r"(上海市人民政府[办公厅]*)", html)
    if m:
        meta["publisher"] = m.group(1)

    # Look for dates in structured format
    for m in re.finditer(
        r'(印发日期|发布日期|成文日期)[：:]\s*(\d{4}[-年]\d{1,2}[-月]\d{1,2}日?)',
        html,
    ):
        label, date_val = m.group(1), m.group(2)
        date_val = (
            date_val.replace("年", "-").replace("月", "-").replace("日", "")
        )
        if "印发" in label or "成文" in label:
            meta["date_written_str"] = date_val
        elif "发布" in label:
            meta["date_published_str"] = date_val

    return meta


def _extract_body(html: str) -> str:
    """Extract plain text body from document detail page.

    Shanghai uses div.Article_content as the main content container.
    """
    content = ""
    for pattern in [
        r'<div[^>]*class="[^"]*\bArticle_content\b[^"]*"[^>]*>(.*?)</div>\s*(?:<div|</div>)',
        r'<div[^>]*class="[^"]*\barticle[_-]?content\b[^"]*"[^>]*>(.*?)</div>',
        r'<div[^>]*id=["\']ivs_content["\'][^>]*>(.*?)</div>',
        r'<div[^>]*class="[^"]*\bTRS_Editor\b[^"]*"[^>]*>(.*?)</div>',
    ]:
        m = re.search(pattern, html, re.DOTALL | re.IGNORECASE)
        if m:
            content = m.group(1)
            break

    if not content:
        return ""

    content = re.sub(r"<br\s*/?\s*>", "\n", content)
    content = re.sub(r"</p>", "\n", content)
    text = re.sub(r"<[^>]+>", "", content)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n\s*\n", "\n", text)
    text = text.strip()
    text = unescape(text)
    text = text.replace("\xa0", " ")

    if len(text) > 20:
        return text
    return ""


def _extract_doc_number(title: str) -> str:
    """Extract document number from title if present."""
    m = re.search(r"[（(]([^）)]*[〕][^）)]*号)[）)]", title)
    if m:
        return m.group(1)
    return ""


def crawl_section(
    conn, section_id: str, section_name: str, fetch_bodies: bool = True
):
    """Crawl all year archives in a section and fetch document details."""
    log.info(f"--- Section: {section_name} ({section_id}) ---")

    # Discover year-archive URLs from section index
    try:
        archives = _get_year_archive_urls(section_id)
    except Exception as e:
        log.error(f"Failed to fetch section index for {section_id}: {e}")
        return 0

    if not archives:
        log.warning(f"  No year archives found for {section_id}")
        return 0

    log.info(f"  Found {len(archives)} year archives: {', '.join(y for y, _ in archives)}")

    all_items = []
    for year, archive_url in archives:
        try:
            html = fetch(archive_url)
        except Exception as e:
            log.warning(f"  Failed to fetch {year} archive: {e}")
            continue

        total_pages = _get_total_pages(html)
        items = _parse_listing(html, archive_url)

        for page in range(2, total_pages + 1):
            page_url = _page_url(archive_url, page)
            try:
                page_html = fetch(page_url)
                items.extend(_parse_listing(page_html, page_url))
            except Exception as e:
                log.warning(f"  Failed {year} page {page}: {e}")
            time.sleep(REQUEST_DELAY)

        log.info(f"  {year}: {len(items)} docs ({total_pages} pages)")
        all_items.extend(items)
        time.sleep(REQUEST_DELAY)

    log.info(f"  Total: {len(all_items)} document links")

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
        doc_number = _extract_doc_number(item["title"])
        publisher = ""
        date_published = item["date_str"]
        date_written = _parse_date(item["date_str"])

        if fetch_bodies:
            try:
                doc_html = fetch(doc_url)
                meta = _extract_meta(doc_html)
                body_text = _extract_body(doc_html)

                publisher = meta.get("publisher", "")
                doc_number = meta.get("document_number", "") or doc_number
                if meta.get("date_written_str"):
                    date_written = _parse_date(meta["date_written_str"])
                if meta.get("date_published_str"):
                    date_published = meta["date_published_str"]

                if doc_html:
                    raw_html_path = save_raw_html(SITE_KEY, doc_id, doc_html)
                    bodies += 1
            except Exception as e:
                log.warning(f"  Failed to fetch {doc_url}: {e}")
            time.sleep(REQUEST_DELAY)

        store_document(conn, SITE_KEY, {
            "id": doc_id,
            "title": item["title"],
            "document_number": doc_number,
            "publisher": publisher,
            "date_written": date_written,
            "date_published": date_published,
            "body_text_cn": body_text,
            "url": doc_url,
            "classify_main_name": section_name,
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
    """Crawl all (or specified) Shanghai sections."""
    if sections is None:
        sections = SECTIONS

    store_site(conn, SITE_KEY, SITE_CFG)
    total = 0
    for section_id, name in sections.items():
        total += crawl_section(conn, section_id, name, fetch_bodies)
        time.sleep(REQUEST_DELAY)

    log.info(f"=== Shanghai total: {total} documents ===")


def main():
    parser = argparse.ArgumentParser(
        description="Shanghai Municipality Policy Crawler"
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
        {args.section: SECTIONS[args.section]} if args.section else None
    )
    crawl_all(conn, sections, fetch_bodies=not args.list_only)
    show_stats(conn)
    conn.close()


if __name__ == "__main__":
    main()
