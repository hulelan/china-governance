"""
Ministry of Science and Technology (科技部) crawler.

Crawls policy documents from www.most.gov.cn. TRS CMS with static HTML pagination
(index.html, index_1.html, index_2.html, ...). Two listing formats: table (xxgk
sections with doc numbers) and simple list (tztg, kjbgz).

Sections crawled:
  - gfxwj:  规范性文件  (Normative documents, ~500 docs)
  - zcjd:   政策解读    (Policy interpretations, ~170 docs)
  - tztg:   通知通告    (Notices, ~500 docs)
  - kjbgz:  科技部工作  (Ministry work updates, ~500 docs)

Usage:
    python -m crawlers.most                    # Crawl all sections
    python -m crawlers.most --section gfxwj    # Crawl only normative documents
    python -m crawlers.most --stats            # Show database stats
    python -m crawlers.most --list-only        # List URLs without fetching
"""

import argparse
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

SITE_KEY = "most"
SITE_CFG = {
    "name": "Ministry of Science and Technology",
    "base_url": "https://www.most.gov.cn",
    "admin_level": "central",
}

CST = timezone(timedelta(hours=8))

SECTIONS = {
    "gfxwj": {
        "name": "规范性文件",
        "path": "/xxgk/xinxifenlei/fdzdgknr/fgzc/gfxwj/",
        "listing_type": "table",
    },
    "zcjd": {
        "name": "政策解读",
        "path": "/xxgk/xinxifenlei/fdzdgknr/fgzc/zcjd/",
        "listing_type": "list",
    },
    "tztg": {
        "name": "通知通告",
        "path": "/tztg/",
        "listing_type": "list",
    },
    "kjbgz": {
        "name": "科技部工作",
        "path": "/kjbgz/",
        "listing_type": "list",
    },
}


def _parse_date(date_str: str) -> int:
    """Convert date string to Unix timestamp at midnight CST."""
    date_str = (
        date_str.replace("/", "-")
        .replace("年", "-")
        .replace("月", "-")
        .replace("日", "")
        .strip()
    )
    try:
        dt = datetime.strptime(date_str[:10], "%Y-%m-%d").replace(tzinfo=CST)
        return int(dt.timestamp())
    except ValueError:
        return 0


def _listing_url(base_path: str, page: int) -> str:
    """Build listing page URL. Page 0 = index.html, page N = index_N.html."""
    base = f"https://www.most.gov.cn{base_path}"
    if page == 0:
        return base  # directory URL serves index.html
    return base + f"index_{page}.html"


def _get_total_pages(html: str) -> int:
    """Extract total page count from pagination_script_config.total or similar."""
    m = re.search(r"total\s*[:=]\s*['\"]?(\d+)['\"]?", html)
    if m:
        return int(m.group(1))
    m = re.search(r"createPageHTML\((\d+),", html)
    if m:
        return int(m.group(1))
    return 1


def _parse_list_listing(html: str, base_url: str) -> list[dict]:
    """Parse simple list format: ul.info_list2 > li > a + span.date."""
    items = []
    for m in re.finditer(
        r'<li>.*?<a\s+href="([^"]+)"[^>]*title="([^"]*)"[^>]*>.*?'
        r'<span\s+class="date[^"]*">(\d{4}-\d{2}-\d{2})</span>',
        html,
        re.DOTALL,
    ):
        href, title, date_str = m.group(1), m.group(2), m.group(3)
        doc_url = urljoin(base_url, href)
        items.append({"url": doc_url, "title": title.strip(), "date_str": date_str})
    # Fallback: a without title attr but with text content
    if not items:
        for m in re.finditer(
            r'<li>.*?<a\s+href="([^"]+)"[^>]*>\s*([^<]+?)\s*</a>.*?'
            r'<span\s+class="date[^"]*">(\d{4}-\d{2}-\d{2})</span>',
            html,
            re.DOTALL,
        ):
            href, title, date_str = m.group(1), m.group(2), m.group(3)
            doc_url = urljoin(base_url, href)
            items.append({"url": doc_url, "title": title.strip(), "date_str": date_str})
    return items


def _parse_table_listing(html: str, base_url: str) -> list[dict]:
    """Parse xxgk data_list format: <li> with <a class="list-main-li-item"> + date/docnum divs."""
    items = []
    for m in re.finditer(
        r'<a\s+[^>]*href="([^"]+)"[^>]*title=\'([^\']*)\''
        r'.*?w_list_fwzh">\s*(.*?)\s*</div>'
        r'.*?w_list_rq">\s*(.*?)\s*</div>',
        html,
        re.DOTALL,
    ):
        href = m.group(1)
        title = m.group(2).strip()
        doc_number = re.sub(r"<[^>]+>", "", m.group(3)).strip()
        date_str = m.group(4).strip()
        doc_url = urljoin(base_url, href)
        items.append({
            "url": doc_url,
            "title": title,
            "date_str": date_str,
            "document_number": doc_number,
        })
    return items


def _extract_body(html: str) -> str:
    """Extract body text from div#Zoom or TRS_UEDITOR (TRS CMS variants)."""
    start_marker = html.find('id="Zoom"')
    if start_marker == -1:
        start_marker = html.find('id=Zoom')
    if start_marker == -1:
        # Newer TRS CMS uses class-based editor divs
        start_marker = html.find('trs_editor_view')
    if start_marker == -1:
        start_marker = html.find('TRS_Editor')
    if start_marker == -1:
        # Last resort: try generic content divs
        start_marker = html.find('class="text wide')
    if start_marker == -1:
        return ""

    gt = html.find(">", start_marker)
    if gt == -1:
        return ""
    content_start = gt + 1

    # Find end: ContentEnd meta tag or major section break
    end_pos = len(html)
    for marker in ['<meta name="ContentEnd"', 'div_qrcode', 'xxgk_detail_table',
                    'chnldesc-correlation', '<script', '<!-- footer']:
        pos = html.find(marker, content_start)
        if pos != -1 and pos < end_pos:
            end_pos = pos

    content = html[content_start:end_pos]
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
    """Extract metadata from <meta> tags."""
    meta = {}
    for name in ("ArticleTitle", "PubDate", "ContentSource", "Keywords", "ColumnName"):
        m = re.search(
            rf'<meta\s+name=["\']?{name}["\']?\s+content=["\']([^"\']*)["\']',
            html, re.IGNORECASE,
        )
        if m:
            meta[name] = m.group(1).strip()
    return meta


def _extract_doc_number_from_page(html: str) -> str:
    """Extract document number from the xxgk metadata table."""
    m = re.search(
        r'<b>发文字号[：:]?\s*</b>\s*</td>\s*<td[^>]*>\s*([^<]+)',
        html, re.DOTALL,
    )
    if m:
        num = m.group(1).strip()
        if num:
            return num
    # Fallback: extract from body text
    body = _extract_body(html)
    if body:
        head = body[:500]
        m = re.search(
            r"([\u4e00-\u9fff]+[\u3014\u3008\u300a\uff08\u2018\u301a〔]"
            r"(?:19|20)\d{2}"
            r"[\u3015\u3009\u300b\uff09\u2019\u301b〕]"
            r"\d+号)",
            head,
        )
        if m:
            return m.group(1)
    return ""


def crawl_section(conn, section_key: str, section: dict, fetch_bodies: bool = True):
    """Crawl a single section."""
    name = section["name"]
    path = section["path"]
    listing_type = section["listing_type"]
    log.info(f"--- Section: {name} ({section_key}) ---")

    first_url = _listing_url(path, 0)
    try:
        html = fetch(first_url)
    except Exception as e:
        log.error(f"Failed to fetch {first_url}: {e}")
        return 0

    total_pages = _get_total_pages(html)
    log.info(f"  {total_pages} listing pages")

    parse_fn = _parse_table_listing if listing_type == "table" else _parse_list_listing
    all_items = parse_fn(html, first_url)

    for page in range(1, total_pages):
        page_url = _listing_url(path, page)
        try:
            page_html = fetch(page_url)
            all_items.extend(parse_fn(page_html, page_url))
        except Exception as e:
            log.warning(f"  Failed page {page}: {e}")
        time.sleep(REQUEST_DELAY)

    log.info(f"  Found {len(all_items)} document links")

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
        doc_number = item.get("document_number", "")
        publisher = "科技部"
        date_published = item["date_str"]

        if fetch_bodies:
            try:
                doc_html = fetch(doc_url)
                meta = _extract_meta(doc_html)
                body_text = _extract_body(doc_html)
                page_doc_number = _extract_doc_number_from_page(doc_html)
                doc_number = doc_number or page_doc_number
                publisher = meta.get("ContentSource", publisher) or publisher
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
            "title": item["title"],
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
            log.info(f"  Progress: {stored}/{len(all_items)} stored, {bodies} bodies, {skipped} skipped")

    conn.commit()
    log.info(f"  Done: {stored} stored, {bodies} bodies, {skipped} skipped")
    return stored


def crawl_all(conn, sections: dict = None, fetch_bodies: bool = True):
    """Crawl all (or specified) MOST sections."""
    if sections is None:
        sections = SECTIONS

    store_site(conn, SITE_KEY, SITE_CFG)
    total = 0
    for key, section in sections.items():
        total += crawl_section(conn, key, section, fetch_bodies)
        time.sleep(REQUEST_DELAY)

    log.info(f"=== MOST total: {total} documents ===")


def main():
    parser = argparse.ArgumentParser(description="MOST Policy Crawler")
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
