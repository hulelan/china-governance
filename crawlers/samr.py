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

Known quirk: connection resets from US IPs on some pages. The retry loop
usually recovers, but prefer the droplet (NYC) for a full crawl.

Sections crawled:
  - zjwj:  总局文件 (Bureau documents / policy releases, ~2,000 docs)
  - zcjd:  政策解读 (Policy interpretations, ~470 docs)
  - xw_zj: 新闻-总局 (Bureau news, ~3,600 docs)
  - xw_sj: 新闻-司局 (Division news, ~900 docs)
  - xw_df: 新闻-地方 (Local/regional news, ~8,000 docs)
  - xw_mtjj: 媒体聚焦
  - xwfbt: 新闻发布厅 (press conferences / 专题新闻发布会; added 2026-11-25)
  - ggjgs_tzgg, bzjss_zqyj: two 司局 columns (广告监管司 通知公告, 标准技术司 征求意见).
    Every 司局 has its own columns; these two are the ones a reader asked for, not
    the full set (see docs/working/press-conference-coverage.md).

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
    # Added 2026-11-25 (section-coverage audit). page_id is the <meta name="ColId">
    # of each section's index.html, the same way the six above were found.
    "xwfbt": {
        "name": "新闻发布厅",
        "page_id": "5fb1ceb699444ed2a679754ec3cc020d",
        "referer": "/xw/xwfbt/index.html",
    },
    "ggjgs_tzgg": {
        "name": "广告监管司-通知公告",
        "page_id": "2ae297a1236648ef93d95b6f9838fc1d",
        "tag_id": "ajax分页",
        "referer": "/ggjgs/tzgg/index.html",
    },
    "bzjss_zqyj": {
        "name": "标准技术司-征求意见",
        "page_id": "c556a93c7baf431dada20ec9fdca5cb1",
        "tag_id": "ajax分页",
        "referer": "/bzjss/zqyj/index.html",
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


# The two listing templates the site serves. (A) is the main column template
# (tagId "内容区域", 20 rows); (B) is the 司局 sub-site template (tagId "ajax分页",
# 10 rows). Both carry the pager's total in count="N".
DEFAULT_TAG_ID = "内容区域"
_ITEM_PATTERNS = (
    # (A) <li class="nav04Left02_content"><a href title>..</a></li>
    #     <li class="nav04Left02_contenttime">YYYY-MM-DD</li>
    re.compile(
        r'<li\s+class="nav04Left02_content">\s*<a\s+href="([^"]+)"[^>]*'
        r'title="([^"]+)"[^>]*>.*?</a>\s*</li>\s*'
        r'<li\s+class="nav04Left02_contenttime">([\d-]+)</li>',
        re.DOTALL,
    ),
    # (B) <a href title>..</a> <div class="contentRight01time">YYYY-MM-DD</div>
    re.compile(
        r'<a\s+href="([^"]+)"[^>]*title="([^"]+)"[^>]*>.*?</a>\s*'
        r'<div\s+class="contentRight01time">([\d-]+)</div>',
        re.DOTALL,
    ),
)


def _clean_title(title: str) -> str:
    """title="" attributes are hard-wrapped by the CMS; a line break inside a
    Chinese title is layout, not content."""
    return re.sub(r"\s*[\r\n]+\s*", "", title).strip()


def _parse_listing_html(html: str) -> tuple[list[dict], int]:
    """Parse the HTML fragment the listing API returns -> (items, total_count).

    Pure (no network) so tests can pin both templates.
    """
    items = []
    for pat in _ITEM_PATTERNS:
        for m in pat.finditer(html):
            href, title, date_str = m.group(1), _clean_title(m.group(2)), m.group(3)
            doc_url = href if href.startswith("http") else BASE_URL + href
            # Skip external links (gov.cn central, etc.)
            if "samr.gov.cn" not in doc_url and not href.startswith("/"):
                continue
            items.append({"url": doc_url, "title": title, "date_str": date_str})
        if items:
            break

    total = 0
    count_m = re.search(r'count="(\d+)"', html)
    if count_m:
        total = int(count_m.group(1))
    return items, total


def _fetch_listing_page(page_id: str, page_no: int, referer: str,
                        tag_id: str = DEFAULT_TAG_ID,
                        page_size: int = ROWS_PER_PAGE) -> tuple[list[dict], int]:
    """Fetch one listing page via the jpaas API.

    Returns (items, total_count).
    Each item: {"url": ..., "title": ..., "date_str": ...}
    """
    params = {
        "parseType": "bulidstatic",
        "webId": WEB_ID,
        "tplSetId": TPL_SET_ID,
        "pageType": "column",
        "tagId": tag_id,
        "editType": "null",
        "pageId": page_id,
    }
    if page_no > 1:
        params["paramJson"] = json.dumps(
            {"pageNo": page_no, "pageSize": page_size}
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
    return _parse_listing_html(html)


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


_BODY_DIV_RE = re.compile(r'<div\s+class="(?:Three|zt)_xilan_07[^"]*"[^>]*>')


def _extract_body(html: str) -> str:
    """Extract body text from <div class="Three_xilan_07 ..."> (main site) or
    <div class="zt_xilan_07"> (the 司局 sub-site article template)."""
    # Find the content div -- may have additional classes like "article-pagenation".
    # Without the zt_ alternative the 司局 columns stored 1 body in 26 (2026-11-25).
    m = _BODY_DIV_RE.search(html)
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
    bm = _BODY_DIV_RE.search(html)
    idx = bm.start() if bm else -1
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
    tag_id = section.get("tag_id", DEFAULT_TAG_ID)
    log.info(f"--- Section: {name} ({section_key}) ---")

    # Fetch first page to get total count
    try:
        items, total = _fetch_listing_page(page_id, 1, referer, tag_id)
    except Exception as e:
        log.error(f"Failed to fetch listing page 1: {e}")
        return 0

    if total == 0:
        total = len(items) * 10  # rough estimate
    # Page size is whatever page 1 actually returned (20 on the main template,
    # 10 on the 司局 one); assuming 20 would walk only half of a 10-row section.
    page_size = len(items) if 0 < len(items) < ROWS_PER_PAGE and total > len(items) else ROWS_PER_PAGE
    total_pages = (total + page_size - 1) // page_size
    log.info(f"  {total} documents across {total_pages} pages")

    all_items = list(items)

    # Incremental: stop once a full page is all already held (reverse-chron →
    # older held). This also avoids re-walking down to the dead 2023 URLs that
    # 404. SAMR_DEEP=1 forces a full walk.
    import os
    deep = os.environ.get("SAMR_DEEP") == "1"

    def _held(u):
        return bool(u) and conn.execute(
            "SELECT 1 FROM documents WHERE url = ? AND url != ''", (u,)).fetchone() is not None

    keep_walking = deep or (bool(all_items) and not all(_held(i["url"]) for i in all_items))
    for page in range(2, total_pages + 1):
        if not keep_walking:
            log.info(f"  page {page-1} all already held — stopping walk (older held)")
            break
        try:
            page_items, _ = _fetch_listing_page(page_id, page, referer, tag_id, page_size)
            all_items.extend(page_items)
            if not deep and page_items and all(_held(i["url"]) for i in page_items):
                keep_walking = False
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
            "SELECT id FROM documents WHERE url = ? AND url != ''", (doc_url,)
        ).fetchone()
        if existing:  # skip ANY held doc, incl. body-less/404'd ones — don't re-fetch
            stored += 1
            continue

        doc_id = next_id(conn)
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
