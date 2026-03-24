"""
Ministry of Ecology and Environment (生态环境部) crawler.

Crawls policy documents from www.mee.gov.cn. Static HTML with .shtml extension
and path-based pagination (index_NNNNN_N.shtml).

Sections crawled:
  - zcwj/gwywj:  国务院有关文件  (State Council documents)
  - zcwj/sthjbwj: 生态环境部文件  (MEE departmental documents)
  - ywgz/fgbz/fl: 法律            (Laws)
  - ywgz/fgbz/xzfg: 行政法规      (Administrative regulations)
  - ywgz/fgbz/guizhang: 规章      (Departmental rules)
  - ywgz/fgbz/bz: 标准            (Standards)

Usage:
    python -m crawlers.mee                    # Crawl all sections
    python -m crawlers.mee --section gwywj    # Crawl only State Council docs
    python -m crawlers.mee --stats            # Show database stats
    python -m crawlers.mee --list-only        # List URLs without fetching
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

SITE_KEY = "mee"
SITE_CFG = {
    "name": "Ministry of Ecology and Environment",
    "base_url": "https://www.mee.gov.cn",
    "admin_level": "central",
}

CST = timezone(timedelta(hours=8))

SECTIONS = {
    "gwywj": {
        "name": "国务院有关文件",
        "path": "/zcwj/gwywj/",
    },
    "sthjbwj": {
        "name": "生态环境部文件",
        "path": "/zcwj/sthjbwj/",
    },
    "fl": {
        "name": "法律",
        "path": "/ywgz/fgbz/fl/",
    },
    "xzfg": {
        "name": "行政法规",
        "path": "/ywgz/fgbz/xzfg/",
    },
    "guizhang": {
        "name": "规章",
        "path": "/ywgz/fgbz/guizhang/",
    },
    "bz": {
        "name": "标准",
        "path": "/ywgz/fgbz/bz/",
    },
}


def _parse_date(date_str: str) -> int:
    """Convert date string to Unix timestamp at midnight CST."""
    date_str = date_str.replace("/", "-").strip()
    try:
        dt = datetime.strptime(date_str[:10], "%Y-%m-%d").replace(tzinfo=CST)
        return int(dt.timestamp())
    except ValueError:
        return 0


def _listing_url(base_path: str, page: int, page_id: str) -> str:
    """Build listing page URL with .shtml extension."""
    base = f"https://www.mee.gov.cn{base_path}"
    if page == 0:
        return base + "index.shtml"
    return base + f"index_{page_id}_{page}.shtml"


def _get_pagination_info(html: str) -> tuple[int, str]:
    """Extract total pages and page ID from pagination JS.

    Returns (total_pages, page_id).
    MEE uses index_PAGEID_N.shtml where PAGEID is a numeric string.
    """
    cp = re.search(r"countPage\s*=\s*(\d+)", html)
    total = int(cp.group(1)) if cp else 1

    # Find the page ID from AJAX patterns like index_8597_1.shtml
    pid = re.search(r"index_(\d+)_\d+\.shtml", html)
    page_id = pid.group(1) if pid else "0"

    return total, page_id


def _parse_listing(html: str, base_url: str) -> list[dict]:
    """Parse listing: <li><span class="date">YYYY-MM-DD</span><a href="...">Title</a></li>."""
    items = []
    for m in re.finditer(
        r'<li>\s*<span\s+class="date">(\d{4}-\d{2}-\d{2})</span>\s*'
        r'<a\s+href="([^"]+)"[^>]*>([^<]+)</a>\s*</li>',
        html,
        re.DOTALL,
    ):
        date_str, href, title = m.group(1), m.group(2), m.group(3)
        doc_url = urljoin(base_url, href)
        items.append({
            "url": doc_url,
            "title": title.strip(),
            "date_str": date_str,
        })
    return items


def _extract_body(html: str) -> str:
    """Extract body text from div.content_body_box."""
    start = html.find('class="content_body_box"')
    if start == -1:
        return ""
    gt = html.find(">", start)
    if gt == -1:
        return ""
    content_start = gt + 1

    # Find end boundary: next major section div or script
    end_pos = -1
    for marker in ['<div class="con_', '<div class="recommend', '<div id="recommend',
                   '<div class="page_', "<!-- ", "<script"]:
        pos = html.find(marker, content_start)
        if pos != -1 and (end_pos == -1 or pos < end_pos):
            end_pos = pos

    if end_pos == -1:
        end_pos = content_start + 50000

    content = html[content_start:end_pos]
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
    """Extract metadata from <meta> tags."""
    meta = {}
    for name in ("ArticleTitle", "PubDate", "ContentSource", "Keywords",
                 "ColumnName", "contentid", "publishdate"):
        m = re.search(
            rf'<meta\s+name=["\']?{name}["\']?\s+content=["\']([^"\']*)["\']',
            html, re.IGNORECASE,
        )
        if m:
            meta[name] = m.group(1).strip()
    return meta


def _extract_doc_number(body_text: str) -> str:
    """Extract document number from body text.

    MEE docs often have the doc number in the first few lines, e.g.:
    国办发〔2026〕6号
    """
    # Look in the first 500 chars of body text
    head = body_text[:500]
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
    log.info(f"--- Section: {name} ({section_key}) ---")

    first_url = _listing_url(path, 0, "0")
    try:
        html = fetch(first_url)
    except Exception as e:
        log.error(f"Failed to fetch {first_url}: {e}")
        return 0

    total_pages, page_id = _get_pagination_info(html)
    log.info(f"  {total_pages} listing pages (page_id={page_id})")

    all_items = _parse_listing(html, first_url)

    for page in range(1, total_pages):
        page_url = _listing_url(path, page, page_id)
        try:
            page_html = fetch(page_url)
            all_items.extend(_parse_listing(page_html, page_url))
        except Exception as e:
            log.warning(f"  Failed page {page}: {e}")
        time.sleep(REQUEST_DELAY)

    log.info(f"  Found {len(all_items)} document links")

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
        doc_number = ""
        publisher = "生态环境部"
        date_published = item["date_str"]

        if fetch_bodies:
            try:
                doc_html = fetch(doc_url)
                meta = _extract_meta(doc_html)
                body_text = _extract_body(doc_html)
                doc_number = _extract_doc_number(body_text)
                publisher = meta.get("ContentSource", publisher)
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
            log.info(f"  Progress: {stored}/{len(all_items)} stored, {bodies} bodies")

    conn.commit()
    log.info(f"  Done: {stored} documents stored, {bodies} bodies fetched")
    return stored


def crawl_all(conn, sections: dict = None, fetch_bodies: bool = True):
    """Crawl all (or specified) MEE sections."""
    if sections is None:
        sections = SECTIONS

    store_site(conn, SITE_KEY, SITE_CFG)
    total = 0
    for key, section in sections.items():
        total += crawl_section(conn, key, section, fetch_bodies)
        time.sleep(REQUEST_DELAY)

    log.info(f"=== MEE total: {total} documents ===")


def main():
    parser = argparse.ArgumentParser(description="MEE Policy Crawler")
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
