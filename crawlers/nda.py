"""
National Data Administration (国家数据局) crawler.

Crawls policy documents from www.nda.gov.cn. Static HTML with JS-driven
client-side pagination (totalData/showData variables, page URLs at
index_pc_N.html).

Every document is about AI/data governance — a small but high-value corpus.

Sections crawled:
  - zcfb: 政策发布 (Policy releases)
  - tzgg: 通知公告 (Notices & announcements)
  - zcjd: 政策解读 (Policy interpretation)
  - zjjd: 专家解读 (Expert interpretation)
  - gknr: 政府信息公开目录 (Info disclosure)

Usage:
    python -m crawlers.nda                    # Crawl all sections
    python -m crawlers.nda --section zcfb     # Crawl only policy releases
    python -m crawlers.nda --stats            # Show database stats
    python -m crawlers.nda --list-only        # List URLs without fetching
    python -m crawlers.nda --db alt.db        # Write to alternate database
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

SITE_KEY = "nda"
SITE_CFG = {
    "name": "National Data Administration",
    "base_url": "https://www.nda.gov.cn",
    "admin_level": "central",
}

BASE_URL = "https://www.nda.gov.cn"
CST = timezone(timedelta(hours=8))

# Sections to crawl.
SECTIONS = {
    "zcfb": {
        "name": "政策发布",
        "path": "/sjj/zwgk/zcfb/list/",
    },
    "tzgg": {
        "name": "通知公告",
        "path": "/sjj/zwgk/tzgg/list/",
    },
    "zcjd": {
        "name": "政策解读",
        "path": "/sjj/zwgk/zcjd/list/",
    },
    "zjjd": {
        "name": "专家解读",
        "path": "/sjj/zwgk/zjjd/list/",
    },
    "gknr": {
        "name": "政府信息公开目录",
        "path": "/sjj/xxgk/gknr/list/",
    },
}


def _parse_date(date_str: str) -> int:
    """Convert date string (YYYY.MM.DD or YYYY-MM-DD) to Unix timestamp at midnight CST."""
    date_str = date_str.replace(".", "-").replace("/", "-").strip()
    try:
        dt = datetime.strptime(date_str[:10], "%Y-%m-%d").replace(tzinfo=CST)
        return int(dt.timestamp())
    except ValueError:
        return 0


def _listing_url(base_path: str, page: int) -> str:
    """Build listing page URL. Pages are 1-indexed: index_pc_1.html, index_pc_2.html, ..."""
    return f"{BASE_URL}{base_path}index_pc_{page}.html"


def _get_total_pages(html: str) -> int:
    """Extract total page count from JS pagination config.

    The page uses: $('.pages').pagination({ totalData: 34, showData: 15, ... })
    """
    m_total = re.search(r"totalData:\s*(\d+)", html)
    m_per = re.search(r"showData:\s*(\d+)", html)
    if m_total and m_per:
        total = int(m_total.group(1))
        per_page = int(m_per.group(1))
        if per_page > 0:
            return math.ceil(total / per_page)
    if m_total:
        # Fallback: assume 15 per page
        return math.ceil(int(m_total.group(1)) / 15)
    return 1


def _parse_listing(html: str) -> list[dict]:
    """Parse listing page items from <ul class="u-list">.

    Each top-level item is:
        <li><a href="/sjj/zwgk/zcfb/..." title="...">Title</a>
            [optional: <strong>解读</strong> <div class="popbox">...</div>]
            <span>YYYY.MM.DD</span>
        </li>

    The popbox contains nested <ul><li> with interpretation links (zjjd/ytdd)
    which would confuse naive <li> splitting.  Instead, strip popbox divs first,
    then parse the clean top-level list items.
    """
    items = []
    # Extract the u-list block (outermost only — the closing </ul> after
    # all top-level items, NOT the nested popbox <ul>)
    ul_start = html.find('<ul class="u-list">')
    if ul_start == -1:
        return items
    # Find the matching </ul> — skip nested <ul> inside popbox divs
    # Easier: strip all popbox divs first, then find </ul>
    block = html[ul_start:]
    # Remove nested popbox content (contains <ul><li>... that would confuse parsing)
    block = re.sub(r'<div\s+class="popbox">.*?</div>\s*', "", block, flags=re.DOTALL)
    # Now find the closing </ul>
    ul_end = block.find("</ul>")
    if ul_end == -1:
        return items
    ul_content = block[len('<ul class="u-list">'):ul_end]

    # Now split into top-level <li>...</li> blocks safely
    li_blocks = re.findall(r"<li[^>]*>(.+?)</li>", ul_content, re.DOTALL)

    for li in li_blocks:
        if not li.strip():
            continue

        # Extract the <a> tag with policy document link
        a_match = re.search(
            r'<a\s+href="([^"]+)"[^>]*title="([^"]*)"[^>]*>',
            li,
        )
        if not a_match:
            continue

        href = a_match.group(1)
        title = a_match.group(2).strip()
        if not title:
            continue

        # Only pick up links under /sjj/ (skip external/navigation links)
        if "/sjj/" not in href or "/list/" in href:
            continue

        # Extract date from <span>
        date_match = re.search(r"<span>(\d{4}\.\d{2}\.\d{2})</span>", li)
        date_str = date_match.group(1) if date_match else ""

        doc_url = urljoin(BASE_URL, href)
        items.append({"url": doc_url, "title": title, "date_str": date_str})

    return items


def _extract_body(html: str) -> str:
    """Extract body text from <div class="article">."""
    m = re.search(r'<div\s+class="article">(.*?)</div>\s*(?:<div\s+class="filelist"|</div>\s*</div>)',
                  html, re.DOTALL)
    if not m:
        # Broader fallback
        m = re.search(r'<div\s+class="article">(.*?)<div\s+class="filelist"', html, re.DOTALL)
    if not m:
        # Even broader: grab everything in the article div
        start = html.find('class="article"')
        if start == -1:
            return ""
        gt = html.find(">", start)
        if gt == -1:
            return ""
        # Find the filelist div or end of containing div
        end = html.find('class="filelist"', gt)
        if end == -1:
            end = gt + 50000
        m_text = html[gt + 1:end]
        if not m_text.strip():
            return ""
        content = m_text
    else:
        content = m.group(1)

    # Clean HTML to text
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
        .replace("&ldquo;", "\u201c")
        .replace("&rdquo;", "\u201d")
        .strip()
    )
    return text if len(text) > 20 else ""


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


def _extract_doc_number(text: str) -> str:
    """Extract document number (文号) from body text.

    NDA docs have numbers like: 国数政策〔2026〕6号
    Look in the first 500 chars.
    """
    head = text[:500]
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


def _extract_attachments(html: str) -> list[dict]:
    """Extract attachment links from <div class="filelist">."""
    attachments = []
    fl_match = re.search(r'<div\s+class="filelist">(.*?)</div>\s*</div>',
                         html, re.DOTALL)
    if not fl_match:
        return attachments

    for a_match in re.finditer(
        r'<a\s+href="([^"]+)"[^>]*>([^<]+)</a>',
        fl_match.group(1),
    ):
        href, name = a_match.group(1), a_match.group(2).strip()
        if href and name:
            attachments.append({
                "url": urljoin(BASE_URL, href),
                "name": name,
            })
    return attachments


def crawl_section(conn, section_key: str, section: dict, fetch_bodies: bool = True):
    """Crawl a single section."""
    name = section["name"]
    path = section["path"]
    log.info(f"--- Section: {name} ({section_key}) ---")

    # Fetch first page
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
        # List-only mode: print URLs and return
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
        doc_number = ""
        publisher = "国家数据局"
        date_published = item["date_str"].replace(".", "-")
        attachments = []

        try:
            doc_html = fetch(doc_url)
            meta = _extract_meta(doc_html)
            body_text = _extract_body(doc_html)
            doc_number = _extract_doc_number(body_text)
            publisher = meta.get("ContentSource", publisher) or publisher
            if meta.get("PubDate"):
                date_published = meta["PubDate"].replace(".", "-")[:10]
            attachments = _extract_attachments(doc_html)
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
            "attachments_json": json.dumps(attachments, ensure_ascii=False) if attachments else "[]",
        })
        stored += 1

        if stored % 10 == 0:
            conn.commit()
            log.info(f"  Progress: {stored}/{len(all_items)} stored, {bodies} bodies")

    conn.commit()
    log.info(f"  Done: {stored} documents stored, {bodies} bodies fetched")
    return stored


def crawl_all(conn, sections: dict = None, fetch_bodies: bool = True):
    """Crawl all (or specified) NDA sections."""
    if sections is None:
        sections = SECTIONS

    store_site(conn, SITE_KEY, SITE_CFG)
    total = 0
    for key, section in sections.items():
        total += crawl_section(conn, key, section, fetch_bodies)
        time.sleep(REQUEST_DELAY)

    log.info(f"=== NDA total: {total} documents ===")


def main():
    parser = argparse.ArgumentParser(description="NDA Policy Crawler")
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
