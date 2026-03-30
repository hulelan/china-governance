"""
State Administration for Market Regulation (国家市场监督管理总局 / SAMR) crawler.

Crawls policy documents and news from www.samr.gov.cn. The site uses a
jpaas-publish-server API that returns rendered HTML for listing pages
(paginated, 20 per page). Article detail pages contain body text in
static HTML within <div class="Three_xilan_07"> and metadata in <meta> tags.

SAMR regulates product safety, food safety, anti-monopoly, anti-unfair
competition, standards, metrology, certification, and market order --
highly relevant to AI product standards, algorithm regulation, and
platform governance.

Sections crawled:
  - zjwj:  总局文件 (Bureau documents / policy releases, ~2,000 docs)
  - zcjd:  政策解读 (Policy interpretations, ~470 docs)
  - xw_zj: 新闻-总局 (Bureau news, ~3,600 docs)
  - xw_sj: 新闻-司局 (Division news, ~900 docs)
  - xw_df: 新闻-地方 (Local/regional news, ~8,000 docs)

Usage:
    python -m crawlers.samr                    # Crawl all sections
    python -m crawlers.samr --section zjwj     # Bureau documents only
    python -m crawlers.samr --section zcjd     # Policy interpretations only
    python -m crawlers.samr --section xw_zj    # Bureau news only
    python -m crawlers.samr --stats            # Show database stats
    python -m crawlers.samr --list-only        # List URLs without fetching
    python -m crawlers.samr --db alt.db        # Write to alternate database
"""

import argparse
import json
import re
import time
import urllib.parse
from datetime import datetime, timezone, timedelta
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

SITE_KEY = "samr"
SITE_CFG = {
    "name": "State Administration for Market Regulation",
    "base_url": "https://www.samr.gov.cn",
    "admin_level": "central",
}

BASE_URL = "https://www.samr.gov.cn"
CST = timezone(timedelta(hours=8))

# The site uses a unified API for all listing pages. Each section is
# identified by its pageId (same as the ColId from the HTML meta tag).
# webId and tplSetId are site-wide constants.
API_URL = (
    "https://www.samr.gov.cn/api-gateway/jpaas-publish-server"
    "/front/page/build/unit"
)
WEB_ID = "29e9522dc89d4e088a953d8cede72f4c"
TPL_SET_ID = "5c30fb89ae5e48b9aefe3cdf49853830"
ROWS_PER_PAGE = 20

BROWSER_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)

# --- Sections ---

SECTIONS = {
    "zjwj": {
        "name": "总局文件",
        "page_id": "5a1c443ecf8c471bb9577ba1ae5d2883",
        "referer": "/zw/zjwj/index.html",
    },
    "zcjd": {
        "name": "政策解读",
        "page_id": "f6a995f86b4f4362836c3c2d7ce72889",
        "referer": "/zw/zjwj/zcjd/index.html",
    },
    "xw_zj": {
        "name": "新闻-总局",
        "page_id": "39cd9de1f309431483ef3008309f39ca",
        "referer": "/xw/zj/index.html",
    },
    "xw_sj": {
        "name": "新闻-司局",
        "page_id": "e1d3514242304e589aa2f3da490d63fb",
        "referer": "/xw/sj/index.html",
    },
    "xw_df": {
        "name": "新闻-地方",
        "page_id": "82103d93eb114af2944a1cfd363f45cb",
        "referer": "/xw/df/index.html",
    },
    "xw_mtjj": {
        "name": "媒体聚焦",
        "page_id": "fd590d1789974f8b9f1db6d2e7da751a",
        "referer": "/xw/mtjj/index.html",
    },
}


def _parse_date(date_str: str) -> int:
    """Convert date string (YYYY-MM-DD ...) to Unix timestamp at midnight CST."""
    date_str = date_str.replace("/", "-").replace(".", "-").strip()
    try:
        dt = datetime.strptime(date_str[:10], "%Y-%m-%d").replace(tzinfo=CST)
        return int(dt.timestamp())
    except ValueError:
        return 0


def _fetch_listing_page(page_id: str, page_no: int, referer: str) -> tuple[list[dict], int]:
    """Fetch one listing page via the jpaas API.

    Returns (items, total_count).
    Each item: {"url": ..., "title": ..., "date_str": ...}
    """
    params = {
        "parseType": "bulidstatic",
        "webId": WEB_ID,
        "tplSetId": TPL_SET_ID,
        "pageType": "column",
        "tagId": "内容区域",
        "editType": "null",
        "pageId": page_id,
    }
    if page_no > 1:
        params["paramJson"] = json.dumps(
            {"pageNo": page_no, "pageSize": ROWS_PER_PAGE}
        )

    qs = urllib.parse.urlencode(params)
    url = f"{API_URL}?{qs}"

    headers = {
        "Referer": BASE_URL + referer,
        "User-Agent": BROWSER_UA,
    }
    text = fetch(url, headers=headers)
    data = json.loads(text)

    html = data.get("data", {}).get("html", "")
    if not html:
        return [], 0

    # Parse items from HTML: each doc is in a <ul> with title link and date
    # Pattern: <li class="nav04Left02_content"><a href="..." title="...">...</a></li>
    #          <li class="nav04Left02_contenttime">YYYY-MM-DD</li>
    items = []
    for m in re.finditer(
        r'<li\s+class="nav04Left02_content">\s*<a\s+href="([^"]+)"[^>]*'
        r'title="([^"]+)"[^>]*>.*?</a>\s*</li>\s*'
        r'<li\s+class="nav04Left02_contenttime">([\d-]+)</li>',
        html,
        re.DOTALL,
    ):
        href, title, date_str = m.group(1), m.group(2).strip(), m.group(3)
        doc_url = href if href.startswith("http") else BASE_URL + href
        # Skip external links (gov.cn central, etc.)
        if "samr.gov.cn" not in doc_url and not href.startswith("/"):
            continue
        items.append({"url": doc_url, "title": title, "date_str": date_str})

    # Total count from pagination div
    total = 0
    count_m = re.search(r'count="(\d+)"', html)
    if count_m:
        total = int(count_m.group(1))

    return items, total


def _extract_meta(html: str) -> dict:
    """Extract metadata from article page <meta> tags."""
    meta = {}
    for name in ("ArticleTitle", "PubDate", "ContentSource", "Keywords",
                 "Description", "ColumnName"):
        m = re.search(
            rf'<meta\s+name=["\']?{name}["\']?\s+content=["\']([^"\']*)["\']',
            html, re.IGNORECASE,
        )
        if m:
            meta[name] = m.group(1).strip()
    return meta


def _extract_body(html: str) -> str:
    """Extract body text from <div class="Three_xilan_07 ...">."""
    # Find the content div -- may have additional classes like "article-pagenation"
    m = re.search(r'<div\s+class="Three_xilan_07[^"]*"[^>]*>', html)
    if not m:
        return ""

    start = m.end()
    chunk = html[start:start + 100000]

    # Find the end of the content area.
    # The content div is followed by share buttons, script tags, or closing divs.
    # Look for common end markers and pick the earliest one.
    end_pos = len(chunk)
    for marker in [
        '<div class="dw"',
        '<div class="share"',
        'class="gwdshare_t',
        '<script',
        'id="barrierfree_container_bottom"',
    ]:
        pos = chunk.find(marker)
        if pos > 0 and pos < end_pos:
            end_pos = pos

    content = chunk[:end_pos]

    # Clean HTML to plain text
    content = re.sub(r"<style[^>]*>.*?</style>", "", content, flags=re.DOTALL)
    content = re.sub(r"<br\s*/?\s*>", "\n", content)
    content = re.sub(r"<p[^>]*>", "\n", content)
    content = re.sub(r"</p>", "", content)
    content = re.sub(r"<div[^>]*>", "\n", content)
    content = re.sub(r"</div>", "", content)
    content = re.sub(r"<table[^>]*>", "\n", content)
    content = re.sub(r"</table>", "", content)
    content = re.sub(r"<tr[^>]*>", "\n", content)
    content = re.sub(r"<td[^>]*>", " ", content)
    text = re.sub(r"<[^>]+>", "", content)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n\s*\n", "\n", text)
    text = (
        text.replace("&nbsp;", " ")
        .replace("&#xa0;", " ")
        .replace("\u3000", " ")
        .replace("&lt;", "<")
        .replace("&gt;", ">")
        .replace("&amp;", "&")
        .replace("&ldquo;", "\u201c")
        .replace("&rdquo;", "\u201d")
        .replace("\u200b", "")  # zero-width space
        .strip()
    )
    return text if len(text) > 20 else ""


def _extract_doc_number(text: str) -> str:
    """Extract document number (文号) from body text.

    SAMR docs have numbers like: 国市监竞争〔2026〕3号, 市场监管总局令第XX号
    Look in the first 500 chars.
    """
    head = text[:500]
    # Standard bracket pattern: 国市监XX〔YYYY〕N号
    m = re.search(
        r"([\u4e00-\u9fff]+[\u3014\u3008\u300a\uff08\u2018\u301a〔]"
        r"(?:19|20)\d{2}"
        r"[\u3015\u3009\u300b\uff09\u2019\u301b〕]"
        r"\d+号)",
        head,
    )
    if m:
        return m.group(1)
    # 总局令 pattern
    m = re.search(r"(市场监管总局令第\d+号)", head)
    if m:
        return m.group(1)
    return ""


def _extract_attachments(html: str) -> list[dict]:
    """Extract attachment links from the article page.

    Attachments are typically in <a> tags with href pointing to
    /cms_files/ or ending in .pdf/.doc/.xls.
    """
    attachments = []
    # Look in the content area after Three_xilan_07
    idx = html.find("Three_xilan_07")
    if idx == -1:
        return attachments
    region = html[idx:idx + 100000]

    for a_match in re.finditer(
        r'<a\s+href="([^"]+)"[^>]*>([^<]+)</a>',
        region,
    ):
        href, name = a_match.group(1), a_match.group(2).strip()
        if not href or not name:
            continue
        # Only keep links to downloadable files
        if any(ext in href.lower() for ext in (".pdf", ".doc", ".docx", ".xls", ".xlsx", ".zip")):
            full_url = href if href.startswith("http") else BASE_URL + href
            attachments.append({"url": full_url, "name": name})

    return attachments


def crawl_section(conn, section_key: str, section: dict, fetch_bodies: bool = True):
    """Crawl a single section."""
    name = section["name"]
    page_id = section["page_id"]
    referer = section["referer"]
    log.info(f"--- Section: {name} ({section_key}) ---")

    # Fetch first page to get total count
    try:
        items, total = _fetch_listing_page(page_id, 1, referer)
    except Exception as e:
        log.error(f"Failed to fetch listing page 1: {e}")
        return 0

    if total == 0:
        total = len(items) * 10  # rough estimate
    total_pages = (total + ROWS_PER_PAGE - 1) // ROWS_PER_PAGE
    log.info(f"  {total} documents across {total_pages} pages")

    all_items = list(items)

    for page in range(2, total_pages + 1):
        try:
            page_items, _ = _fetch_listing_page(page_id, page, referer)
            all_items.extend(page_items)
        except Exception as e:
            log.warning(f"  Failed page {page}: {e}")
        time.sleep(REQUEST_DELAY)

        if page % 20 == 0:
            log.info(f"  Listing progress: page {page}/{total_pages}, {len(all_items)} items")

    log.info(f"  Found {len(all_items)} document links")

    if not fetch_bodies:
        for item in all_items:
            print(f"  {item['date_str']}  {item['url']}")
            print(f"             {item['title']}")
        return len(all_items)

    stored = 0
    bodies = 0
    for item in all_items:
        doc_url = item["url"]

        # Skip external URLs (state council links, etc.)
        if "samr.gov.cn" not in doc_url:
            continue

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
        publisher = "市场监管总局"
        keywords = ""
        date_published = item["date_str"]
        attachments = []

        try:
            doc_html = fetch(doc_url, headers={"User-Agent": BROWSER_UA})
            meta = _extract_meta(doc_html)
            body_text = _extract_body(doc_html)
            doc_number = _extract_doc_number(body_text)
            publisher = meta.get("ContentSource", publisher) or publisher
            keywords = meta.get("Keywords", "")
            if meta.get("PubDate"):
                date_published = meta["PubDate"][:10]
            attachments = _extract_attachments(doc_html)
            if doc_html:
                raw_html_path = save_raw_html(SITE_KEY, doc_id, doc_html)
                if body_text:
                    bodies += 1
        except Exception as e:
            log.warning(f"  Failed to fetch {doc_url}: {e}")
        time.sleep(REQUEST_DELAY)

        store_document(conn, SITE_KEY, {
            "id": doc_id,
            "title": item["title"],
            "document_number": doc_number,
            "publisher": publisher,
            "keywords": keywords,
            "date_written": _parse_date(date_published),
            "date_published": date_published,
            "body_text_cn": body_text,
            "url": doc_url,
            "classify_main_name": name,
            "raw_html_path": raw_html_path,
            "attachments_json": json.dumps(attachments, ensure_ascii=False) if attachments else "[]",
        })
        stored += 1

        if stored % 20 == 0:
            conn.commit()
            log.info(f"  Progress: {stored}/{len(all_items)} stored, {bodies} bodies")

    conn.commit()
    log.info(f"  Done: {stored} documents stored, {bodies} bodies fetched")
    return stored


def crawl_all(conn, sections: dict = None, fetch_bodies: bool = True):
    """Crawl all (or specified) SAMR sections."""
    if sections is None:
        sections = SECTIONS

    store_site(conn, SITE_KEY, SITE_CFG)
    total = 0

    for key, section in sections.items():
        total += crawl_section(conn, key, section, fetch_bodies)
        time.sleep(REQUEST_DELAY)

    log.info(f"=== SAMR total: {total} documents ===")


def main():
    parser = argparse.ArgumentParser(description="SAMR Policy & News Crawler")
    parser.add_argument(
        "--section",
        choices=list(SECTIONS.keys()),
        help="Crawl only this section",
    )
    parser.add_argument(
        "--stats", action="store_true", help="Show database stats"
    )
    parser.add_argument(
        "--list-only",
        action="store_true",
        help="List URLs without fetching bodies",
    )
    parser.add_argument(
        "--db",
        type=str,
        help="Path to SQLite database (default: documents.db)",
    )
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
