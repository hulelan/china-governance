"""
Ministry of Finance (财政部) crawler.

Crawls policy documents from www.mof.gov.cn. The site uses static HTML with
createPageHTML() pagination (same pattern as NDRC).

Two content types:
  - HTML articles: policy releases, news, regulation texts
  - PDF bulletins (财政文告): monthly compendiums of formal regulations

Usage:
    python -m crawlers.mof                    # Crawl all sections
    python -m crawlers.mof --section zcfb     # Crawl only policy releases
    python -m crawlers.mof --stats            # Show database stats
    python -m crawlers.mof --list-only        # List URLs without fetching
"""

import argparse
import io
import re
import time
import urllib.request
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
    USER_AGENT,
)

SITE_KEY = "mof"
SITE_CFG = {
    "name": "Ministry of Finance",
    "base_url": "https://www.mof.gov.cn",
    "admin_level": "central",
}

CST = timezone(timedelta(hours=8))

# Sections to crawl.  (path_segment, label, content_type)
SECTIONS = {
    "zcfb": {
        "name": "政策发布",
        "path": "/zhengwuxinxi/zhengcefabu/",
        "type": "html",
    },
    "czxw": {
        "name": "财政新闻",
        "path": "/zhengwuxinxi/caizhengxinwen/",
        "type": "html",
    },
    "czwg": {
        "name": "财政文告",
        "path": "/gkml/caizhengwengao/",
        "type": "pdf",
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
        dt = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=CST)
        return int(dt.timestamp())
    except ValueError:
        return 0


# --- HTML listing/detail helpers ---

def _listing_url(base_path: str, page: int) -> str:
    """Build listing page URL."""
    base = f"https://www.mof.gov.cn{base_path}"
    if page == 0:
        return base + "index.htm"
    return base + f"index_{page}.htm"


def _get_total_pages(html: str) -> int:
    """Extract total page count from createPageHTML(N, ...) or var countPage."""
    m = re.search(r"createPageHTML\((\d+),", html)
    if m:
        return int(m.group(1))
    m = re.search(r"var\s+countPage\s*=\s*(\d+)", html)
    if m:
        return int(m.group(1))
    return 1


def _parse_listing(html: str, base_url: str) -> list[dict]:
    """Parse listing page: <li><a href="..." title='...'>Title</a><span>Date</span></li>."""
    items = []
    # MOF uses <span> for dates and sometimes single-quoted title attrs
    for m in re.finditer(
        r'<li>\s*<a\s+href="([^"]+)"[^>]*>(.*?)</a>\s*<span>(\d{4}-\d{2}-\d{2})</span>\s*</li>',
        html,
        re.DOTALL,
    ):
        href, title, date_str = m.group(1), m.group(2), m.group(3)
        title = re.sub(r"<[^>]+>", "", title).strip()
        doc_url = urljoin(base_url, href)
        items.append({"url": doc_url, "title": title, "date_str": date_str})
    # Fallback: bare date without <span> (used in some sections)
    if not items:
        for m in re.finditer(
            r'<li>\s*<a\s+href="([^"]+)"[^>]*>(.*?)</a>\s*(\d{4}-\d{2}-\d{2})\s*</li>',
            html,
            re.DOTALL,
        ):
            href, title, date_str = m.group(1), m.group(2), m.group(3)
            title = re.sub(r"<[^>]+>", "", title).strip()
            doc_url = urljoin(base_url, href)
            items.append({"url": doc_url, "title": title, "date_str": date_str})
    return items


def _extract_body(html: str) -> str:
    """Extract body text from div.my_conboxzw."""
    m = re.search(r'<div\s+class="my_conboxzw"[^>]*>(.*?)</div>\s*(?:<div|<script)',
                  html, re.DOTALL)
    if not m:
        # Broader fallback
        m = re.search(r'<div\s+class="my_conboxzw"[^>]*>(.*?)</div>', html, re.DOTALL)
    if not m:
        return ""
    content = m.group(1)
    content = re.sub(r"<br\s*/?\s*>", "\n", content)
    content = re.sub(r"<p[^>]*>", "\n", content)
    content = re.sub(r"</p>", "", content)
    text = re.sub(r"<[^>]+>", "", content)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n\s*\n", "\n", text)
    text = (
        text.replace("&nbsp;", " ")
        .replace("&lt;", "<")
        .replace("&gt;", ">")
        .replace("&amp;", "&")
        .strip()
    )
    return text if len(text) > 20 else ""


def _extract_doc_number(title: str) -> str:
    """Extract 文号 from title if present."""
    m = re.search(r"[（(]([^）)]*[〕\]][^）)]*号)[）)]", title)
    if m:
        return m.group(1)
    return ""


def _extract_meta(html: str) -> dict:
    """Extract metadata from <meta> tags or page content."""
    meta = {}
    for name in ("ArticleTitle", "PubDate", "ContentSource", "Keywords",
                 "ColumnName", "description"):
        m = re.search(
            rf'<meta\s+name=["\']?{name}["\']?\s+content=["\']([^"\']*)["\']',
            html, re.IGNORECASE,
        )
        if m:
            meta[name] = m.group(1).strip()
    return meta


# --- PDF helpers ---

def _fetch_pdf_bytes(url: str) -> bytes:
    """Download a PDF and return raw bytes."""
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    resp = urllib.request.urlopen(req, timeout=30)
    return resp.read()


def _extract_pdf_text(pdf_bytes: bytes) -> str:
    """Extract text from PDF using PyMuPDF (fitz)."""
    try:
        import fitz
    except ImportError:
        log.warning("PyMuPDF not installed — skipping PDF text extraction")
        return ""

    text_parts = []
    with fitz.open(stream=pdf_bytes, filetype="pdf") as doc:
        for page in doc:
            text_parts.append(page.get_text())
    text = "\n".join(text_parts)
    # Clean up
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


# --- Crawl logic ---

def crawl_html_section(conn, section_key: str, section: dict, fetch_bodies: bool = True):
    """Crawl an HTML listing section."""
    name = section["name"]
    path = section["path"]
    log.info(f"--- Section: {name} ({section_key}) ---")

    first_url = _listing_url(path, 0)
    try:
        html = fetch(first_url)
    except Exception as e:
        log.error(f"Failed to fetch {first_url}: {e}")
        return 0

    total_pages = _get_total_pages(html)
    log.info(f"  {total_pages} listing pages")

    all_items = _parse_listing(html, first_url)

    for page in range(1, total_pages):
        page_url = _listing_url(path, page)
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
        doc_number = _extract_doc_number(item["title"])
        publisher = "财政部"
        date_published = item["date_str"]

        if fetch_bodies:
            try:
                doc_html = fetch(doc_url)
                meta = _extract_meta(doc_html)
                body_text = _extract_body(doc_html)
                publisher = meta.get("ContentSource", publisher)
                doc_number = doc_number or _extract_doc_number(
                    meta.get("ArticleTitle", "")
                )
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
            "date_written": _parse_date(date_published),
            "date_published": date_published,
            "body_text_cn": body_text,
            "url": doc_url,
            "classify_main_name": name,
            "raw_html_path": raw_html_path,
        })
        stored += 1

        if stored % 20 == 0:
            conn.commit()
            log.info(f"  Progress: {stored}/{len(all_items)} stored, {bodies} bodies")

    conn.commit()
    log.info(f"  Done: {stored} documents stored, {bodies} bodies fetched")
    return stored


def crawl_pdf_section(conn, section_key: str, section: dict, fetch_bodies: bool = True):
    """Crawl a PDF bulletin section — each PDF is stored as one document."""
    name = section["name"]
    path = section["path"]
    log.info(f"--- Section: {name} ({section_key}, PDF) ---")

    first_url = _listing_url(path, 0)
    try:
        html = fetch(first_url)
    except Exception as e:
        log.error(f"Failed to fetch {first_url}: {e}")
        return 0

    total_pages = _get_total_pages(html)
    log.info(f"  {total_pages} listing pages")

    # PDF listings use slightly different HTML — links go to .pdf files
    all_items = []
    for m in re.finditer(
        r'<li>\s*<a\s+href="([^"]+\.pdf)"[^>]*>(.*?)</a>\s*(\d{4}-\d{2}-\d{2})\s*</li>',
        html,
        re.DOTALL,
    ):
        href, title, date_str = m.group(1), m.group(2), m.group(3)
        title = re.sub(r"<[^>]+>", "", title).strip()
        all_items.append({
            "url": urljoin(first_url, href),
            "title": title,
            "date_str": date_str,
        })

    for page in range(1, total_pages):
        page_url = _listing_url(path, page)
        try:
            page_html = fetch(page_url)
            for m in re.finditer(
                r'<li>\s*<a\s+href="([^"]+\.pdf)"[^>]*>(.*?)</a>\s*(\d{4}-\d{2}-\d{2})\s*</li>',
                page_html,
                re.DOTALL,
            ):
                href, title, date_str = m.group(1), m.group(2), m.group(3)
                title = re.sub(r"<[^>]+>", "", title).strip()
                all_items.append({
                    "url": urljoin(page_url, href),
                    "title": title,
                    "date_str": date_str,
                })
        except Exception as e:
            log.warning(f"  Failed page {page}: {e}")
        time.sleep(REQUEST_DELAY)

    log.info(f"  Found {len(all_items)} PDF links")

    stored = 0
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

        if fetch_bodies:
            try:
                log.info(f"  Downloading PDF: {item['title']}")
                pdf_bytes = _fetch_pdf_bytes(doc_url)
                body_text = _extract_pdf_text(pdf_bytes)
                if body_text:
                    log.info(f"    Extracted {len(body_text)} chars from PDF")
                else:
                    log.warning(f"    No text extracted from PDF")
            except Exception as e:
                log.warning(f"  Failed to fetch PDF {doc_url}: {e}")
            time.sleep(REQUEST_DELAY)

        store_document(conn, SITE_KEY, {
            "id": doc_id,
            "title": item["title"],
            "document_number": "",
            "publisher": "财政部",
            "date_written": _parse_date(item["date_str"]),
            "date_published": item["date_str"],
            "body_text_cn": body_text,
            "url": doc_url,
            "classify_main_name": name,
        })
        stored += 1

        if stored % 10 == 0:
            conn.commit()
            log.info(f"  Progress: {stored}/{len(all_items)}")

    conn.commit()
    log.info(f"  Done: {stored} PDF documents stored")
    return stored


def crawl_all(conn, sections: dict = None, fetch_bodies: bool = True):
    """Crawl all (or specified) MOF sections."""
    if sections is None:
        sections = SECTIONS

    store_site(conn, SITE_KEY, SITE_CFG)
    total = 0
    for key, section in sections.items():
        if section["type"] == "pdf":
            total += crawl_pdf_section(conn, key, section, fetch_bodies)
        else:
            total += crawl_html_section(conn, key, section, fetch_bodies)
        time.sleep(REQUEST_DELAY)

    log.info(f"=== MOF total: {total} documents ===")


def main():
    parser = argparse.ArgumentParser(description="MOF Policy Crawler")
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
