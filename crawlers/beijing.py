"""
Beijing Municipality (北京市) crawler.

Crawls policy documents from www.beijing.gov.cn. Beijing uses a custom CMS
with static HTML listing pages under the government information disclosure
(政府信息公开) section.

URL patterns:
  Listing:  /zhengce/zfwj/index.html (path-based pagination)
  Detail:   /zhengce/zfwj/YYYYMM/t{id}.html or /zhengce/zhengcefagui/{id}.html
  Body:     div.view-content or div.article or div#mainText
  Meta:     <meta> tags + structured table with 京政发, 京政办发, etc.

Sections crawled:
  - Municipal government rules (市政府规章)
  - Municipal government documents (市政府文件)
  - Municipal office documents (市政府办公厅文件)
  - Policy interpretations (政策解读)
  - Normative documents (规范性文件)

Usage:
    python -m crawlers.beijing                    # Crawl all sections
    python -m crawlers.beijing --section szfwj    # Crawl municipal gov docs only
    python -m crawlers.beijing --stats            # Show database stats
    python -m crawlers.beijing --list-only        # List without fetching bodies
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

SITE_KEY = "bj"
SITE_CFG = {
    "name": "Beijing Municipality",
    "base_url": "https://www.beijing.gov.cn",
    "admin_level": "provincial",
}

CST = timezone(timedelta(hours=8))

# Section key -> (section name, URL path)
# Beijing organizes policy docs under /zhengce/ paths.
SECTIONS = {
    "szfgz": ("市政府规章", "gongkai/zfxxgk/zc/gz"),                # Municipal rules (191 entries, table format)
    "szfwj": ("市政府文件", "zhengce/zfwj/zfwj2016/szfwj"),        # Municipal gov docs (~469 docs)
    "bgtwj": ("市政府办公厅文件", "zhengce/zfwj/zfwj2016/bgtwj"),  # Municipal office docs (~560 docs)
    "zcjd": ("政策解读", "zhengce/zcjd"),                           # Interpretations (confirmed working)
    "gfxwj": ("规范性文件", "zhengce/gfxwj"),                       # Normative documents (confirmed working)
}

_BASE_URL = "https://www.beijing.gov.cn"


def _section_url(section: str, page: int = 0) -> str:
    """Build listing page URL for a section.

    Beijing uses /{path}/index.html for page 0
    and /{path}/index_{page}.html for subsequent pages.
    Some sections may also use /{path}/?page=N query params.
    """
    _, path = SECTIONS[section]
    base = f"{_BASE_URL}/{path}/"
    if page == 0:
        return base + "index.html"
    return base + f"index_{page}.html"


def _get_total_pages(html: str) -> int:
    """Extract total page count from pagination.

    Beijing uses client-side pagination for most sections — the JS
    grabs all `.default_news li` and slices them into pages of 15.
    All data is in the first page HTML, so we return 1 for these.

    For sections with server-side pagination, we check for
    createPageHTML(), totalPage vars, or 共X页 indicators.
    """
    # Client-side pagination: all data in one page
    if re.search(r"var\s+\$list\s*=\s*\$\(['\"]\.default_news\s+li['\"]\)", html):
        return 1

    # createPageHTML has two forms:
    #   createPageHTML(totalPages, currentPage, ...) — 2-arg: first is pages
    #   createPageHTML(totalRecords, totalPages, currentPage, ...) — 3+ arg: second is pages
    m = re.search(r"createPageHTML\((\d+),\s*(\d+),\s*(\d+)", html)
    if m:
        # 3+ args: (totalRecords, totalPages, currentPage, ...)
        return int(m.group(2))
    m = re.search(r"createPageHTML\((\d+),", html)
    if m:
        return int(m.group(1))
    m = re.search(r"totalPage\s*[=:]\s*(\d+)", html)
    if m:
        return int(m.group(1))
    m = re.search(r"共\s*(\d+)\s*页", html)
    if m:
        return int(m.group(1))
    # Try page count from total records and page size
    total_m = re.search(r"totalRecord\s*[=:]\s*(\d+)", html)
    size_m = re.search(r"pageSize\s*[=:]\s*(\d+)", html)
    if total_m and size_m:
        total = int(total_m.group(1))
        size = int(size_m.group(1))
        if size > 0:
            return (total + size - 1) // size
    return 1


def _parse_listing(html: str, base_url: str) -> list[dict]:
    """Parse a listing page and extract document links, titles, dates.

    Beijing has three distinct HTML structures across sections:

    1. szfwj/bgtwj (.default_news with <b class="u_time">):
       <li><i class="flag">是</i>
         <a href="..." title="TITLE">TITLE</a>
         <span>京政发〔2025〕28号</span>
         <b class="u_time">2026-01-01</b></li>

    2. gfxwj (.default_news with <span>DATE</span>):
       <li><i class="flag">是</i>
         <a href="..." title="TITLE">TITLE</a>
         <span>2026-01-01</span></li>

    3. szfgz (p.c-bt-t card layout):
       <p class="c-bt-t"><a href="...">TITLE</a></p>
       <p class="c-bt-c">(2025年12月 第320号令 ...)</p>
    """
    items = []

    # First, try to extract the .default_news container to avoid
    # running expensive DOTALL regexes on the full page (~200KB+).
    news_html = html
    news_m = re.search(
        r'<ul[^>]*class="default_news"[^>]*>(.*?)</ul>',
        html, re.DOTALL,
    )
    if news_m:
        news_html = news_m.group(1)
        # Filter to items with flag "是" (skip SEO/test entries with empty flag)
        news_html = re.sub(
            r'<li[^>]*>\s*<i[^>]*class="flag"[^>]*>\s*</i>.*?</li>',
            '', news_html, flags=re.DOTALL,
        )

        # Sub-pattern A: date in <b class="u_time"> + doc number in <span>
        # (szfwj, bgtwj sections)
        if "u_time" in news_html:
            for m in re.finditer(
                r'<li[^>]*>.*?<a\s+href="([^"]+)"[^>]*title="([^"]*)"'
                r'[^>]*>.*?</a>(?:.*?<span[^>]*>([^<]*)</span>)?'
                r'.*?<b\s+class="u_time">(\d{4}-\d{2}-\d{2})</b>',
                news_html,
                re.DOTALL,
            ):
                href, title, doc_num, date_str = (
                    m.group(1), m.group(2), m.group(3) or "", m.group(4)
                )
                doc_url = urljoin(base_url, href)
                items.append({
                    "url": doc_url,
                    "title": unescape(title.strip()),
                    "date_str": date_str,
                    "document_number": doc_num.strip(),
                })
        else:
            # Sub-pattern B: date in <span> (gfxwj, zcjd sections)
            # <li>...<a href="URL" title="TITLE">...</a><span>DATE</span></li>
            for m in re.finditer(
                r'<li[^>]*>.*?<a\s+href="([^"]+)"[^>]*title="([^"]*)"'
                r'[^>]*>.*?</a>\s*<span>(\d{4}-\d{2}-\d{2})</span>',
                news_html,
                re.DOTALL,
            ):
                href, title, date_str = m.group(1), m.group(2), m.group(3)
                doc_url = urljoin(base_url, href)
                items.append({
                    "url": doc_url,
                    "title": unescape(title.strip()),
                    "date_str": date_str,
                })

    if items:
        return items

    # Pattern 2: zcjd-style list (date in <span>, no .default_news container)
    for m in re.finditer(
        r'<li[^>]*>.*?<a\s+href="([^"]+)"[^>]*title="([^"]*)"[^>]*>.*?</a>'
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

    # Pattern 3: Card layout (szfgz — municipal government rules)
    # <p class="c-bt-t"><a href="URL">TITLE</a></p>
    # <p class="c-bt-c">(YYYY年M月D日...第NNN号令...)</p>
    for m in re.finditer(
        r'<p[^>]*class="c-bt-t"[^>]*>\s*<a\s+href="([^"]+)"[^>]*>\s*'
        r'(.*?)\s*</a>\s*</p>\s*<p[^>]*class="c-bt-c"[^>]*>\s*(.*?)\s*</p>',
        html,
        re.DOTALL,
    ):
        href, title, meta_text = m.group(1), m.group(2), m.group(3)
        doc_url = urljoin(base_url, href)
        # Extract date from meta text: "2025年12月15日" or "YYYY-MM-DD"
        date_str = ""
        dm = re.search(r"(\d{4})年(\d{1,2})月(\d{1,2})日", meta_text)
        if dm:
            date_str = f"{dm.group(1)}-{int(dm.group(2)):02d}-{int(dm.group(3)):02d}"
        else:
            dm = re.search(r"(\d{4}[-/]\d{2}[-/]\d{2})", meta_text)
            if dm:
                date_str = dm.group(1).replace("/", "-")
        # Extract decree number: "第NNN号令"
        doc_number = ""
        nm = re.search(r"第\d+号令", meta_text)
        if nm:
            doc_number = nm.group(0)
        items.append({
            "url": doc_url,
            "title": unescape(title.strip()),
            "date_str": date_str,
            "document_number": doc_number,
        })

    if items:
        return items

    # Pattern 4: Table-based listings (fallback)
    for m in re.finditer(
        r'<tr[^>]*>.*?<a\s+href="([^"]+)"[^>]*>([^<]+)</a>'
        r'.*?(\d{4}[-/]\d{2}[-/]\d{2}).*?</tr>',
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
    """Extract metadata from detail page.

    Checks three sources:
    1. <meta> tags (standard gov.cn tags)
    2. Structured metadata table/list (发文字号, 发文机关, etc.)
    3. Beijing-specific header blocks
    """
    meta = {}

    # Source 1: <meta> tags
    for name in ("ArticleTitle", "PubDate", "ContentSource",
                 "ColumnName", "Keywords", "description"):
        m = re.search(
            rf'<meta\s+name="{name}"\s+content="([^"]*)"', html, re.IGNORECASE
        )
        if m:
            meta[name] = m.group(1).strip()

    # Source 2: Structured metadata blocks
    # Beijing uses either table rows or definition lists for metadata.
    # Table format: <th>发文字号</th><td>京政发〔2026〕1号</td>
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

    # Source 3: Definition-list format
    # <dt>发文字号：</dt><dd>京政发〔2026〕1号</dd>
    for m in re.finditer(
        r'<dt[^>]*>\s*([^<：]+)：?\s*</dt>\s*<dd[^>]*>\s*(.*?)\s*</dd>',
        html,
        re.DOTALL,
    ):
        label = m.group(1).strip()
        value = re.sub(r"<[^>]+>", "", m.group(2)).strip()
        if ("发文字号" in label or "文号" in label) and "document_number" not in meta:
            meta["document_number"] = value
        elif ("发文机关" in label) and "publisher" not in meta:
            meta["publisher"] = value
        elif ("成文日期" in label) and "date_written_str" not in meta:
            meta["date_written_str"] = value
        elif ("主题分类" in label) and "classify_theme_name" not in meta:
            meta["classify_theme_name"] = value
        elif ("索引号" in label) and "identifier" not in meta:
            meta["identifier"] = value

    return meta


def _extract_body(html: str) -> str:
    """Extract plain text body from document detail page.

    Tries multiple container selectors used across Beijing's templates:
    1. div#mainText (primary content container)
    2. div.view-content (view template)
    3. div.article (article template)
    4. div.TRS_Editor (TRS CMS content)
    5. div#UCAP-CONTENT (gov.cn standard widget)
    """
    content = ""
    for pattern in [
        r'<div[^>]*id=["\']mainText["\'][^>]*>(.*?)</div>\s*(?:<div[^>]*class="[^"]*page|<div[^>]*class="[^"]*attach|</div>)',
        r'<div[^>]*class="[^"]*\bview-content\b[^"]*"[^>]*>(.*?)</div>\s*(?:<div|</div>)',
        r'<div[^>]*class="[^"]*\barticle\b[^"]*"[^>]*>(.*?)</div>\s*(?:<div[^>]*class="[^"]*page|</div>)',
        r'<div[^>]*class="[^"]*\bTRS_Editor\b[^"]*"[^>]*>(.*?)</div>',
        r'<div[^>]*id=["\']UCAP-CONTENT["\'][^>]*>(.*?)</div>',
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

    Beijing titles may contain the doc number in parentheses:
    '关于...的通知（京政发〔2026〕1号）'
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
        doc_number = item.get("document_number", "") or _extract_doc_number(item["title"])
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
    """Crawl all (or specified) Beijing sections."""
    if sections is None:
        sections = {k: v[0] for k, v in SECTIONS.items()}

    store_site(conn, SITE_KEY, SITE_CFG)
    total = 0
    for section, name in sections.items():
        total += crawl_section(conn, section, name, fetch_bodies)
        time.sleep(REQUEST_DELAY)

    log.info(f"=== Beijing total: {total} documents ===")


def main():
    parser = argparse.ArgumentParser(
        description="Beijing Municipality Policy Crawler"
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
