"""
Chongqing Municipality (重庆市) crawler.

Crawls policy documents from www.cq.gov.cn.  Chongqing uses a custom CMS with
static HTML listing pages under the government information disclosure section.

URL patterns:
  Listing:  /zwgk/zfxxgkml/szfwj/{section}/index.html  (page 0)
            /zwgk/zfxxgkml/szfwj/{section}/index_N.html (page N)
  Detail:   ./{YYYYMM}/t{YYYYMMDD}_{ID}.html
  Body:     div.trs_editor_view (TRS CMS)
  Meta:     <meta> tags (ArticleTitle, PubDate, ContentSource)

Sections crawled:
  - xzgfxwj/szfbgt: 市政府办公厅行政规范性文件  (Municipal Office normative docs)
  - xzgfxwj/szf:    市政府行政规范性文件        (Municipal Gov normative docs)
  - zfgz/zfgz:      政府规章 / 渝府令           (Government regulations)

Pagination:
  JS function createPage(totalPages, currentIndex, "index", "html").
  Page 0 -> index.html, page N -> index_N.html.  ~10 items per page.

Usage:
    python -m crawlers.chongqing                    # Crawl all sections
    python -m crawlers.chongqing --section szfbgt   # Crawl one section
    python -m crawlers.chongqing --stats            # Show database stats
    python -m crawlers.chongqing --list-only        # List without fetching bodies
"""

import argparse
import re
import time
from datetime import datetime, timedelta, timezone
from html import unescape
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

SITE_KEY = "cq"
SITE_CFG = {
    "name": "Chongqing Municipality",
    "base_url": "https://www.cq.gov.cn",
    "admin_level": "municipal",
}

CST = timezone(timedelta(hours=8))
_BASE_URL = "https://www.cq.gov.cn"

# Section key -> (display name, URL path relative to /zwgk/zfxxgkml/szfwj/, listing format)
# listing format: "xzgfxwj" (table with zcwjk-list) or "zfgz" (list with listpc-item)
SECTIONS = {
    "szfbgt": ("市政府办公厅行政规范性文件", "xzgfxwj/szfbgt", "xzgfxwj"),
    "szf":    ("市政府行政规范性文件",     "xzgfxwj/szf",    "xzgfxwj"),
    "zfgz":   ("政府规章（渝府令）",       "zfgz/zfgz",      "zfgz"),
}


def _section_url(section_key: str, page: int = 0) -> str:
    """Build listing page URL for a section."""
    _, path, _ = SECTIONS[section_key]
    base = f"{_BASE_URL}/zwgk/zfxxgkml/szfwj/{path}/"
    if page == 0:
        return base + "index.html"
    return base + f"index_{page}.html"


def _get_total_pages(html: str) -> int:
    """Extract total page count from createPage() call.

    Chongqing uses: createPage(totalPages, currentIndex, "index", "html")
    """
    m = re.search(r"createPage\((\d+),\s*\d+,", html)
    if m:
        return int(m.group(1))
    return 1


def _parse_listing_xzgfxwj(html: str, base_url: str) -> list[dict]:
    """Parse listing for 行政规范性文件 sections (szfbgt, szf).

    Structure:
      <tr class="zcwjk-list-c ...">
        <td class="num">N</td>
        <td class="title">
          <a href="./YYYYMM/tYYYYMMDD_ID.html">
            <p class="tit">TITLE</p>
            <p class="info">
              <i class="kh">(</i>
              <span>发文字号：DOC_NUMBER</span>
              <span class="time">成文日期 ：YYYY-MM-DD</span>
              <i class="kh">)</i>
            </p>
          </a>
        </td>
        ...
      </tr>
    """
    items = []
    for m in re.finditer(
        r'<tr[^>]*class="zcwjk-list-c[^"]*"[^>]*>(.*?)</tr>',
        html,
        re.DOTALL,
    ):
        row = m.group(1)

        # Extract link
        href_m = re.search(r'<a[^>]*href="([^"]+)"', row)
        if not href_m:
            continue
        href = href_m.group(1)
        doc_url = urljoin(base_url, href)

        # Extract title
        title_m = re.search(r'<p\s+class="tit"[^>]*>(.*?)</p>', row, re.DOTALL)
        if not title_m:
            continue
        title = re.sub(r"<[^>]+>", "", title_m.group(1)).strip()

        # Extract document number (发文字号)
        doc_number = ""
        dn_m = re.search(r'发文字号[：:]\s*([^<]+)', row)
        if dn_m:
            doc_number = dn_m.group(1).strip()
            # Clean up any trailing whitespace or zero-width chars
            doc_number = re.sub(r'[\u200b\u200c\u200d\ufeff\s]+$', '', doc_number)

        # Extract date (成文日期)
        date_str = ""
        date_m = re.search(r'成文日期\s*[：:]\s*(\d{4}-\d{2}-\d{2})', row)
        if date_m:
            date_str = date_m.group(1)

        if title:
            items.append({
                "url": doc_url,
                "title": unescape(title),
                "date_str": date_str,
                "document_number": doc_number,
            })

    return items


def _parse_listing_zfgz(html: str, base_url: str) -> list[dict]:
    """Parse listing for 政府规章 section (渝府令).

    Structure:
      <a class="listpc-item" href="./YYYYMM/tYYYYMMDD_ID.html">
        <li class="pub-unit ... fbjg-val" title="市政府">市政府</li>
        <li class="file-title" title="TITLE">TITLE</li>
        <li class="file-code">渝府令〔YYYY〕NNN号</li>
        <li class="pub-time">YYYY-MM-DD</li>
      </a>
    """
    items = []
    for m in re.finditer(
        r'<a\s+class="listpc-item"[^>]*href="([^"]+)"[^>]*>(.*?)</a>',
        html,
        re.DOTALL,
    ):
        href, inner = m.group(1), m.group(2)
        doc_url = urljoin(base_url, href)

        # Extract title
        title_m = re.search(
            r'<li[^>]*class="file-title"[^>]*title="([^"]*)"', inner
        )
        if not title_m:
            title_m = re.search(
                r'<li[^>]*class="file-title"[^>]*>(.*?)</li>', inner, re.DOTALL
            )
            if not title_m:
                continue
            title = re.sub(r"<[^>]+>", "", title_m.group(1)).strip()
        else:
            title = title_m.group(1).strip()

        # Extract document number
        doc_number = ""
        dn_m = re.search(
            r'<li[^>]*class="file-code"[^>]*>(.*?)</li>', inner, re.DOTALL
        )
        if dn_m:
            doc_number = re.sub(r"<[^>]+>", "", dn_m.group(1)).strip()

        # Extract date
        date_str = ""
        date_m = re.search(
            r'<li[^>]*class="pub-time"[^>]*>(\d{4}-\d{2}-\d{2})</li>', inner
        )
        if date_m:
            date_str = date_m.group(1)

        # Extract publisher
        publisher = ""
        pub_m = re.search(
            r'<li[^>]*class="[^"]*fbjg-val[^"]*"[^>]*title="([^"]*)"', inner
        )
        if pub_m:
            publisher = pub_m.group(1).strip()

        if title:
            items.append({
                "url": doc_url,
                "title": unescape(title),
                "date_str": date_str,
                "document_number": doc_number,
                "publisher": publisher,
            })

    return items


def _parse_listing(html: str, base_url: str, fmt: str) -> list[dict]:
    """Dispatch to the correct listing parser."""
    if fmt == "zfgz":
        return _parse_listing_zfgz(html, base_url)
    return _parse_listing_xzgfxwj(html, base_url)


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
    """Extract metadata from detail page <meta> tags and body patterns."""
    meta = {}

    # Standard gov.cn <meta> tags
    for name in ("ArticleTitle", "PubDate", "ContentSource", "Keywords",
                 "Description", "ColumnName"):
        m = re.search(
            rf'<meta\s+name="{name}"\s+content="([^"]*)"', html, re.IGNORECASE
        )
        if m:
            meta[name] = m.group(1).strip()

    # Extract document number from body text (渝府发/渝府办发/渝府令 patterns)
    dn_m = re.search(r'(渝府[办令发规]*[〔\[]\d{4}[〕\]]\d+号)', html)
    if dn_m:
        meta["document_number"] = dn_m.group(1)

    # Look for publisher in body
    pub_m = re.search(r'(重庆市人民政府[办公厅]*)', html)
    if pub_m:
        meta["publisher"] = pub_m.group(1)

    return meta


def _extract_body(html: str) -> str:
    """Extract plain text body from document detail page.

    Chongqing uses div.trs_editor_view as the main content container,
    inside a div.content wrapper.
    """
    content = ""
    for pattern in [
        r'<div[^>]*class="[^"]*\btrs_editor_view\b[^"]*"[^>]*>(.*?)</div>\s*(?:\s*<script|</div>)',
        r'<div[^>]*class="[^"]*\bTRS_UEDITOR\b[^"]*"[^>]*>(.*?)</div>',
        r'<div[^>]*class="[^"]*\bcontent\b[^"]*"[^>]*>(.*?)</div>',
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


def crawl_section(
    conn, section_key: str, section_name: str, fetch_bodies: bool = True
):
    """Crawl all listing pages in a section and fetch document details."""
    _, _, fmt = SECTIONS[section_key]
    log.info(f"--- Section: {section_name} ({section_key}) ---")

    first_url = _section_url(section_key, 0)
    try:
        html = fetch(first_url)
    except Exception as e:
        log.error(f"Failed to fetch {first_url}: {e}")
        return 0

    total_pages = _get_total_pages(html)
    log.info(f"  {total_pages} listing pages")

    # Parse first page
    all_items = _parse_listing(html, first_url, fmt)

    # Fetch remaining pages
    for page in range(1, total_pages):
        page_url = _section_url(section_key, page)
        try:
            page_html = fetch(page_url)
            items = _parse_listing(page_html, page_url, fmt)
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
        doc_number = item.get("document_number", "")
        publisher = item.get("publisher", "")
        date_published = item.get("date_str", "")
        date_written = _parse_date(item.get("date_str", ""))

        if fetch_bodies:
            try:
                doc_html = fetch(doc_url)
                meta = _extract_meta(doc_html)
                body_text = _extract_body(doc_html)

                # Merge metadata
                publisher = (
                    publisher
                    or meta.get("publisher", "")
                    or meta.get("ContentSource", "")
                )
                doc_number = meta.get("document_number", "") or doc_number

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
    """Crawl all (or specified) Chongqing sections."""
    if sections is None:
        sections = {k: v[0] for k, v in SECTIONS.items()}

    store_site(conn, SITE_KEY, SITE_CFG)
    total = 0
    for section_key, name in sections.items():
        total += crawl_section(conn, section_key, name, fetch_bodies)
        time.sleep(REQUEST_DELAY)

    log.info(f"=== Chongqing total: {total} documents ===")


def main():
    parser = argparse.ArgumentParser(
        description="Chongqing Municipality Policy Crawler"
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
