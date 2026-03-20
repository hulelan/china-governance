"""
Zhejiang Province (浙江省) crawler.

Crawls policy documents from www.zj.gov.cn. The site uses a custom CMS
("浙江政务服务网") with static HTML listing pages and path-based pagination
via createPageHTML(N, idx, "art_...", "html").

URL patterns:
  Listing: /art/YYYY/M/D/art_{SECTION_ID}_{PAGE_ID}.html
  Detail:  /art/YYYY/M/D/art_{CAT_ID}_{ART_ID}.html
  Body:    div#zoom or div.content
  Meta:    <meta name="ArticleTitle"> + table.xxgk_table rows

Sections crawled:
  - Provincial government orders (省政府令)
  - Normative documents (省政府规范性文件)
  - Provincial government documents (省政府文件)
  - Department documents (省级部门文件)
  - Policy interpretations (政策解读)

Usage:
    python -m crawlers.zhejiang                    # Crawl all sections
    python -m crawlers.zhejiang --section gfxwj    # Crawl normative documents only
    python -m crawlers.zhejiang --stats            # Show database stats
    python -m crawlers.zhejiang --list-only        # List without fetching bodies
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

SITE_KEY = "zj"
SITE_CFG = {
    "name": "Zhejiang Province",
    "base_url": "https://www.zj.gov.cn",
    "admin_level": "provincial",
}

CST = timezone(timedelta(hours=8))

# Section key -> (section name, listing page art ID)
# The art IDs are the CMS category identifiers embedded in Zhejiang's URL scheme.
# Each maps to a policy document listing under /col/ or /art/ paths.
SECTIONS = {
    "szfl": ("省政府令", "1229543497"),              # Provincial government orders
    "gfxwj": ("省政府规范性文件", "1229543498"),     # Normative documents
    "szfwj": ("省政府文件", "1229543499"),            # Provincial gov documents
    "sjbmwj": ("省级部门文件", "1229543500"),         # Department documents
    "zcjd": ("政策解读", "1229543501"),               # Policy interpretations
}

# Base URL for listing pages
_LIST_BASE = "https://www.zj.gov.cn/col/"


def _section_url(section: str, page: int = 0) -> str:
    """Build listing page URL for a section.

    Zhejiang uses /col/{art_id}/index.html for page 0
    and /col/{art_id}/index_{page}.html for subsequent pages.
    """
    _, art_id = SECTIONS[section]
    base = f"{_LIST_BASE}{art_id}/"
    if page == 0:
        return base + "index.html"
    return base + f"index_{page}.html"


def _get_total_pages(html: str) -> int:
    """Extract total page count from createPageHTML(N, ...) call.

    Zhejiang uses the same createPageHTML pattern as many Chinese gov sites.
    """
    m = re.search(r"createPageHTML\((\d+),", html)
    if m:
        return int(m.group(1))
    return 1


def _parse_listing(html: str, base_url: str) -> list[dict]:
    """Parse a listing page and extract document links, titles, dates.

    Zhejiang listing pages use <li> elements with structured links.
    Common patterns:
      <li><a href="./YYYYMM/t..." title="FULL TITLE">TEXT</a>
          <span>YYYY-MM-DD</span></li>
    or:
      <li><a href="/art/YYYY/M/D/art_NNN_NNN.html" title="...">...</a>
          <span class="date">YYYY-MM-DD</span></li>
    """
    items = []
    # Pattern 1: Standard listing with title attribute and date span
    for m in re.finditer(
        r'<li[^>]*>\s*<a\s+href="([^"]+)"[^>]*title="([^"]*)"[^>]*>.*?</a>'
        r'.*?<span[^>]*>(\d{4}[-/]\d{2}[-/]\d{2})</span>\s*</li>',
        html,
        re.DOTALL,
    ):
        href, title, date_str = m.group(1), m.group(2), m.group(3)
        doc_url = urljoin(base_url, href)
        items.append({
            "url": doc_url,
            "title": unescape(title.strip()),
            "date_str": date_str.replace("/", "-"),
        })

    if items:
        return items

    # Pattern 2: Alternate list format without title attribute
    for m in re.finditer(
        r'<li[^>]*>\s*<a\s+href="([^"]+)"[^>]*>([^<]+)</a>'
        r'.*?<span[^>]*>(\d{4}[-/]\d{2}[-/]\d{2})</span>\s*</li>',
        html,
        re.DOTALL,
    ):
        href, title, date_str = m.group(1), m.group(2), m.group(3)
        doc_url = urljoin(base_url, href)
        items.append({
            "url": doc_url,
            "title": unescape(title.strip()),
            "date_str": date_str.replace("/", "-"),
        })

    return items


def _parse_date(date_str: str) -> int:
    """Convert date string to Unix timestamp at midnight CST.

    Handles common formats: YYYY-MM-DD, YYYY/MM/DD, YYYY年MM月DD日
    """
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
    """Extract metadata from detail page.

    Checks two sources:
    1. <meta> tags (ArticleTitle, PubDate, ContentSource, etc.)
    2. table.xxgk_table rows (发文字号, 发文机关, 成文日期, etc.)
    """
    meta = {}

    # Source 1: <meta> tags
    for name in ("ArticleTitle", "PubDate", "ContentSource",
                 "ColumnName", "Keywords"):
        m = re.search(
            rf'<meta\s+name="{name}"\s+content="([^"]*)"', html, re.IGNORECASE
        )
        if m:
            meta[name] = m.group(1).strip()

    # Source 2: xxgk_table (government info disclosure table)
    # Rows look like: <th>发文字号</th><td>浙政发〔2026〕1号</td>
    for m in re.finditer(
        r'<t[hd][^>]*>\s*([^<]*(?:发文字号|发文机关|成文日期|发布日期|'
        r'主题分类|索引号|文号)[^<]*)\s*</t[hd]>\s*<td[^>]*>\s*(.*?)\s*</td>',
        html,
        re.DOTALL,
    ):
        label = m.group(1).strip()
        value = re.sub(r"<[^>]+>", "", m.group(2)).strip()
        if "发文字号" in label or "文号" in label:
            meta["document_number"] = value
        elif "发文机关" in label:
            meta["publisher"] = value
        elif "成文日期" in label:
            meta["date_written_str"] = value
        elif "发布日期" in label:
            meta["date_published_str"] = value
        elif "主题分类" in label:
            meta["classify_theme_name"] = value
        elif "索引号" in label:
            meta["identifier"] = value

    return meta


def _extract_body(html: str) -> str:
    """Extract plain text body from document detail page.

    Tries multiple container selectors used across Zhejiang's templates:
    1. div#zoom (primary government doc container)
    2. div.content (alternate layout)
    3. div.art_con (article content)
    4. div.TRS_Editor (TRS CMS content)
    """
    content = ""
    for pattern in [
        r'<div[^>]*id=["\']zoom["\'][^>]*>(.*?)</div>\s*(?:<div|</div>)',
        r'<div[^>]*class="[^"]*\bcontent\b[^"]*"[^>]*>(.*?)</div>\s*(?:<div[^>]*class="[^"]*page|</div>)',
        r'<div[^>]*class="[^"]*\bart_con\b[^"]*"[^>]*>(.*?)</div>',
        r'<div[^>]*class="[^"]*\bTRS_Editor\b[^"]*"[^>]*>(.*?)</div>',
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
    # Clean whitespace
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n\s*\n", "\n", text)
    text = text.strip()
    # Unescape HTML entities
    text = unescape(text)
    text = text.replace("\xa0", " ")

    if len(text) > 20:
        return text
    return ""


def _extract_doc_number(title: str) -> str:
    """Extract document number (文号) from title if present.

    Zhejiang titles often contain the doc number in parentheses:
    '关于...的通知（浙政发〔2026〕1号）'
    """
    m = re.search(r"[（(]([^）)]*[〕][^）)]*号)[）)]", title)
    if m:
        return m.group(1)
    return ""


def crawl_section(
    conn, section: str, section_name: str, fetch_bodies: bool = True
):
    """Crawl all listing pages in a section and fetch document details."""
    log.info(f"--- Section: {section_name} ({section}) ---")

    first_url = _section_url(section, 0)
    try:
        html = fetch(first_url)
    except Exception as e:
        log.error(f"Failed to fetch {first_url}: {e}")
        return 0

    total_pages = _get_total_pages(html)
    log.info(f"  {total_pages} listing pages")

    # Parse first page
    all_items = _parse_listing(html, first_url)

    # Fetch remaining pages
    for page in range(1, total_pages):
        page_url = _section_url(section, page)
        try:
            page_html = fetch(page_url)
            items = _parse_listing(page_html, page_url)
            all_items.extend(items)
        except Exception as e:
            log.warning(f"  Failed page {page}: {e}")
        time.sleep(REQUEST_DELAY)

    log.info(f"  Found {len(all_items)} document links")

    stored = 0
    bodies = 0
    for item in all_items:
        doc_url = item["url"]

        # Skip if already stored with body text
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
        identifier = ""
        classify_theme = ""

        if fetch_bodies:
            try:
                doc_html = fetch(doc_url)
                meta = _extract_meta(doc_html)
                body_text = _extract_body(doc_html)

                # Merge metadata
                publisher = meta.get("publisher", meta.get("ContentSource", ""))
                doc_number = (
                    meta.get("document_number", "")
                    or doc_number
                    or _extract_doc_number(meta.get("ArticleTitle", ""))
                )
                identifier = meta.get("identifier", "")
                classify_theme = meta.get("classify_theme_name", "")

                if meta.get("date_written_str"):
                    date_written = _parse_date(meta["date_written_str"])
                if meta.get("PubDate"):
                    date_published = meta["PubDate"]
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
            "identifier": identifier,
            "publisher": publisher,
            "date_written": date_written,
            "date_published": date_published,
            "body_text_cn": body_text,
            "url": doc_url,
            "classify_main_name": section_name,
            "classify_theme_name": classify_theme,
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
    """Crawl all (or specified) Zhejiang sections."""
    if sections is None:
        sections = {k: v[0] for k, v in SECTIONS.items()}

    store_site(conn, SITE_KEY, SITE_CFG)
    total = 0
    for section, name in sections.items():
        total += crawl_section(conn, section, name, fetch_bodies)
        time.sleep(REQUEST_DELAY)

    log.info(f"=== Zhejiang total: {total} documents ===")


def main():
    parser = argparse.ArgumentParser(description="Zhejiang Province Policy Crawler")
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
