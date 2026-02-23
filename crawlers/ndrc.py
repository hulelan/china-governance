"""
NDRC (National Development and Reform Commission) crawler.

Crawls policy documents from www.ndrc.gov.cn. The site uses static HTML
with predictable pagination via createPageHTML(totalPages, currentIdx, "index", "html").

Usage:
    python -m crawlers.ndrc                    # Crawl all sections
    python -m crawlers.ndrc --section tz       # Crawl only 通知 (notices)
    python -m crawlers.ndrc --stats            # Show database stats
    python -m crawlers.ndrc --list-only        # List document URLs without fetching bodies
"""

import argparse
import re
import time
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

SITE_KEY = "ndrc"
SITE_CFG = {
    "name": "National Development and Reform Commission",
    "base_url": "https://www.ndrc.gov.cn",
    "admin_level": "central",
}

# Sections under /xxgk/zcfb/
SECTIONS = {
    "fzggwl": "发展改革委令",   # NDRC Orders
    "ghxwj":  "规范性文件",     # Normative Documents
    "ghwb":   "规划文本",       # Planning Documents
    "gg":     "公告",           # Announcements
    "tz":     "通知",           # Notices
}


def _section_url(section: str, page: int = 0) -> str:
    """Build listing page URL for a section."""
    base = f"https://www.ndrc.gov.cn/xxgk/zcfb/{section}/"
    if page == 0:
        return base + "index.html"
    return base + f"index_{page}.html"


def _get_total_pages(html: str) -> int:
    """Extract total page count from createPageHTML(N, ...) call."""
    m = re.search(r"createPageHTML\((\d+),", html)
    if m:
        return int(m.group(1))
    return 1


def _parse_listing(html: str, base_url: str) -> list[dict]:
    """Parse a listing page and extract document links, titles, dates."""
    items = []
    # Match each <li> block with an <a> and <span> for date
    # Pattern: <li>\n<a href="./YYYYMM/t..." ... title="FULL TITLE">TEXT</a>...<span>YYYY/MM/DD</span>
    for m in re.finditer(
        r'<li>\s*<a\s+href="([^"]+)"[^>]*title="([^"]*)"[^>]*>.*?</a>'
        r'.*?<span>(\d{4}/\d{2}/\d{2})</span>\s*</li>',
        html,
        re.DOTALL,
    ):
        href, title, date_str = m.group(1), m.group(2), m.group(3)
        doc_url = urljoin(base_url, href)
        items.append({
            "url": doc_url,
            "title": title.strip(),
            "date_str": date_str,  # YYYY/MM/DD
        })
    return items


def _extract_meta(html: str) -> dict:
    """Extract structured metadata from <meta> tags on a detail page."""
    meta = {}
    for name in ("ArticleTitle", "PubDate", "ContentSource", "ColumnName", "ColumnType", "Keywords"):
        m = re.search(rf'<meta\s+name="{name}"\s+content="([^"]*)"', html)
        if m:
            meta[name] = m.group(1).strip()
    return meta


def _extract_body(html: str) -> str:
    """Extract body text from div.article_con."""
    m = re.search(r'<div\s+class="article_con">(.*?)</div>\s*<div\s+class="attachment"',
                  html, re.DOTALL)
    if not m:
        # Fallback: try broader match
        m = re.search(r'<div\s+class="article_con">(.*?)</div>', html, re.DOTALL)
    if not m:
        return ""
    content = m.group(1)
    # Replace <br> with newlines for readability
    content = re.sub(r'<br\s*/?\s*>', '\n', content)
    # Strip HTML tags
    text = re.sub(r'<[^>]+>', '', content)
    # Clean whitespace
    text = re.sub(r'[ \t]+', ' ', text)
    text = re.sub(r'\n\s*\n', '\n', text)
    text = text.strip()
    # Unescape HTML entities
    text = text.replace("&nbsp;", " ").replace("&lt;", "<")
    text = text.replace("&gt;", ">").replace("&amp;", "&")
    if len(text) > 20:
        return text
    return ""


def _extract_doc_number(title: str) -> str:
    """Extract document number (文号) from title if present.

    NDRC titles often end with the doc number in parentheses, e.g.:
    '关于...的通知(发改办投资〔2026〕88号)'
    """
    m = re.search(r'[（(]([^）)]*[〕][^）)]*号)[）)]', title)
    if m:
        return m.group(1)
    return ""


def crawl_section(conn, section: str, section_name: str, fetch_bodies: bool = True):
    """Crawl all listing pages in a section and fetch document details."""
    log.info(f"--- Section: {section_name} ({section}) ---")

    # Get first page to determine total pages
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

    # Fetch each document
    stored = 0
    bodies = 0
    for item in all_items:
        doc_url = item["url"]

        # Check if already stored with body text
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
        date_published = item["date_str"].replace("/", "-")

        if fetch_bodies:
            try:
                doc_html = fetch(doc_url)
                meta = _extract_meta(doc_html)
                body_text = _extract_body(doc_html)
                publisher = meta.get("ContentSource", "")
                doc_number = doc_number or _extract_doc_number(meta.get("ArticleTitle", ""))
                if meta.get("PubDate"):
                    date_published = meta["PubDate"]

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
    """Crawl all (or specified) NDRC sections."""
    if sections is None:
        sections = SECTIONS

    store_site(conn, SITE_KEY, SITE_CFG)
    total = 0
    for section, name in sections.items():
        total += crawl_section(conn, section, name, fetch_bodies)
        time.sleep(REQUEST_DELAY)

    log.info(f"=== NDRC total: {total} documents ===")


def main():
    parser = argparse.ArgumentParser(description="NDRC Policy Crawler")
    parser.add_argument("--section", choices=list(SECTIONS.keys()),
                        help="Crawl only this section")
    parser.add_argument("--stats", action="store_true", help="Show database stats")
    parser.add_argument("--list-only", action="store_true",
                        help="List document URLs without fetching bodies")
    args = parser.parse_args()

    conn = init_db()

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
