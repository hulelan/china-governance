"""
Wuhan Municipality (武汉市) crawler.

Crawls policy documents from www.wuhan.gov.cn. Wuhan uses a standard government
CMS with JavaScript-rendered listing pages under the government information
disclosure (政府信息公开) section, plus an AI industry special topic portal.

URL patterns:
  Listing:  /zwgk/xxgk/zfwj/{section}/index.shtml (JS pagination)
  Detail:   /zwgk/xxgk/zfwj/{section}/YYYYMM/tYYYYMMDD_{id}.shtml
  Body:     div.trs_editor_view.TRS_UEDITOR or div.TRS_Editor
  Meta:     <li>label：value</li> structured list in div.sub

Sections crawled:
  Main policy documents (JS-rendered listings):
    - gfxwj: 规范性文件 (Normative documents, ~25 pages)
    - szfwj: 市政府文件 (Municipal government docs, ~38 pages)

  AI industry portal (HTML listings):
    - ai_zcwj:  政策文件 (AI policy documents)
    - ai_gzdt:  工作动态 (AI work dynamics)
    - ai_gzcg:  工作成果 (AI achievements)

Usage:
    python -m crawlers.wuhan                       # Crawl all sections
    python -m crawlers.wuhan --section gfxwj       # Normative docs only
    python -m crawlers.wuhan --section ai_gzdt     # AI work dynamics only
    python -m crawlers.wuhan --stats               # Show database stats
    python -m crawlers.wuhan --list-only           # List without fetching bodies
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

SITE_KEY = "wuhan"
SITE_CFG = {
    "name": "Wuhan Municipality",
    "base_url": "https://www.wuhan.gov.cn",
    "admin_level": "municipal",
}

CST = timezone(timedelta(hours=8))

_BASE_URL = "https://www.wuhan.gov.cn"

# Section key -> (section name, URL path, listing type)
# listing type: "js" = JavaScript document.writeln, "html" = plain <li><a> HTML
SECTIONS = {
    # Main policy document sections (JS-rendered listings)
    "gfxwj": ("规范性文件", "zwgk/xxgk/zfwj/gfxwj", "js"),
    "szfwj": ("市政府文件", "zwgk/xxgk/zfwj/szfwj", "js"),
    # AI industry portal sub-sections (HTML listings)
    "ai_zcwj": ("AI产业-政策文件", "ztzl/25zt/rgzncy/zcwj_94757", "html"),
    "ai_gzdt": ("AI产业-工作动态", "ztzl/25zt/rgzncy/gzdt_94760", "html"),
    "ai_gzcg": ("AI产业-工作成果", "ztzl/25zt/rgzncy/gzcg_94761", "html"),
}


def _listing_url(path: str, page: int = 0) -> str:
    """Build listing page URL.

    Page 0 -> index.shtml, Page N (N>0) -> index_N.shtml
    """
    base = f"{_BASE_URL}/{path}/"
    if page == 0:
        return base + "index.shtml"
    return base + f"index_{page}.shtml"


def _get_total_pages(html: str) -> int:
    """Extract total page count from createPageHTML(totalPages, currPage, ...).

    Wuhan uses: createPageHTML(25, 0, "index", "shtml")
    where first arg is total pages, second is current page (0-indexed).
    """
    m = re.search(
        r'createPageHTML\((\d+),\s*\d+,\s*"[^"]+",\s*"[^"]+"\)', html
    )
    if m:
        return int(m.group(1))
    return 1


def _parse_js_listing(html: str, base_url: str) -> list[dict]:
    """Parse a JS-rendered listing page (gfxwj, szfwj sections).

    Wuhan renders document entries via JavaScript:
        var url = "./202602/t20260214_2730572.shtml"
        var title = "...";
        var FILENUM = "武政规〔2026〕4号"
        document.writeln("<a href="+url+" ...>");
        ...
        document.writeln("2026-02-14 17:32");

    We extract url, title, FILENUM, and date from the JS source.
    """
    items = []

    # Extract urls (relative paths like ./YYYYMM/t...shtml)
    urls = re.findall(
        r'url\s*=\s*"(\./\d{6}/t\d{8}_\d+\.shtml)"', html
    )

    # Extract titles — the pattern is: title = "TITLE";  }
    # We match the last non-empty title assignment before the closing brace.
    titles = re.findall(
        r'title\s*=\s*"([^"]+?)";\s*\n\s*\}', html
    )

    # Extract document numbers
    filenums = re.findall(r'FILENUM\s*=\s*"([^"]*)"', html)

    # Extract dates (YYYY-MM-DD HH:MM format)
    dates = re.findall(
        r'writeln\("(\d{4}-\d{2}-\d{2})\s+\d{2}:\d{2}"\)', html
    )

    # All arrays should be the same length (one entry per document)
    count = min(len(urls), len(titles), len(filenums), len(dates))
    if count == 0:
        log.warning(
            f"  No JS entries found (urls={len(urls)}, titles={len(titles)}, "
            f"filenums={len(filenums)}, dates={len(dates)})"
        )
        return items

    for i in range(count):
        doc_url = urljoin(base_url, urls[i])
        filenum = filenums[i] if filenums[i] not in ("", "无") else ""
        items.append({
            "url": doc_url,
            "title": unescape(titles[i].strip()),
            "date_str": dates[i],
            "document_number": filenum,
        })

    return items


def _parse_html_listing(html: str, base_url: str) -> list[dict]:
    """Parse an HTML listing page (AI portal sub-sections).

    AI portal pages use plain HTML <li> elements:
        <li>
            <a href="./202602/t20260212_2729456.shtml"
               title="TITLE" target="_blank">TITLE</a>
            <span class="time">
                <script>var fileNum = ""; ...</script>
                2025年12月04日
            </span>
        </li>

    Some links use relative paths like ../../../../sy/whyw/... which we
    resolve against the base URL.
    """
    items = []
    seen_urls = set()

    # Match <li> blocks containing detail links with title attribute
    for m in re.finditer(
        r'<li[^>]*>\s*(?:<!--.*?-->)?\s*<a\s+href="([^"]+)"'
        r'\s+title="([^"]*)"[^>]*>.*?</a>\s*'
        r'<span\s+class="time"[^>]*>(.*?)</span>\s*</li>',
        html,
        re.DOTALL,
    ):
        href, title, time_block = m.group(1), m.group(2), m.group(3)
        if not title.strip():
            continue

        doc_url = urljoin(base_url, href.strip())
        if doc_url in seen_urls:
            continue
        seen_urls.add(doc_url)

        # Extract document number from JS in <span class="time">
        doc_number = ""
        fn_m = re.search(r'var\s+fileNum\s*=\s*"([^"]*)"', time_block)
        if fn_m and fn_m.group(1) not in ("", "无"):
            doc_number = fn_m.group(1)

        # Extract date — try YYYY年MM月DD日 first, then YYYY-MM-DD
        date_str = ""
        dm = re.search(r"(\d{4})年(\d{1,2})月(\d{1,2})日", time_block)
        if dm:
            date_str = (
                f"{dm.group(1)}-{int(dm.group(2)):02d}-{int(dm.group(3)):02d}"
            )
        else:
            dm = re.search(r"(\d{4}-\d{2}-\d{2})", time_block)
            if dm:
                date_str = dm.group(1)

        items.append({
            "url": doc_url,
            "title": unescape(title.strip()),
            "date_str": date_str,
            "document_number": doc_number,
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
        dt = datetime.strptime(date_str.strip(), "%Y-%m-%d").replace(
            tzinfo=CST
        )
        return int(dt.timestamp())
    except ValueError:
        return 0


def _extract_meta(html: str) -> dict:
    """Extract metadata from detail page.

    Wuhan uses structured <li> lists in div.sub:
        <li>索引号： K28044908/2026-04277</li>
        <li>发文机构： 武汉市人民政府</li>
        <li>发文字号： 武政规〔2026〕4号</li>
        <li>主题分类： 科技</li>
        <li>成文日期： 2026年02月13日</li>
        <li>发布日期： 2026年02月14日</li>
        <li>有效性： 有效</li>
    """
    meta = {}

    for m in re.finditer(
        r"<li>\s*([^：<]+)：\s*(.*?)\s*</li>", html, re.DOTALL
    ):
        label = m.group(1).strip()
        value = re.sub(r"<[^>]+>", "", m.group(2)).strip()
        if not value:
            continue

        if "发文字号" in label or "文号" in label:
            meta["document_number"] = value
        elif "发文机构" in label:
            meta["publisher"] = value
        elif "成文日期" in label:
            meta["date_written_str"] = value
        elif "发布日期" in label:
            meta["date_published_str"] = value
        elif "主题分类" in label:
            meta["classify_theme_name"] = value
        elif "索引号" in label:
            meta["identifier"] = value

    # Fallback: extract from <meta> tags
    for name in ("ArticleTitle", "PubDate", "ContentSource"):
        m = re.search(
            rf'<meta\s+name="{name}"\s+content="([^"]*)"',
            html,
            re.IGNORECASE,
        )
        if m and m.group(1).strip():
            meta.setdefault(name, m.group(1).strip())

    return meta


def _extract_body(html: str) -> str:
    """Extract plain text body from document detail page.

    Wuhan uses:
    1. div.trs_editor_view.TRS_UEDITOR (primary content container)
    2. div.TRS_Editor (fallback)
    3. div.article (broader fallback)
    """
    content = ""
    for pattern in [
        r'<div\s+class="trs_editor_view\s+TRS_UEDITOR[^"]*">(.*?)</div>\s*</div>\s*</div>\s*</div>',
        r'<div[^>]*class="[^"]*\bTRS_Editor\b[^"]*"[^>]*>(.*?)</div>',
        r'<div[^>]*class="[^"]*\barticle\b[^"]*"[^>]*>(.*?)</div>',
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
    """Extract document number from title if present.

    E.g. '关于...（武政规〔2026〕4号）' -> '武政规〔2026〕4号'
    """
    m = re.search(r"[（(]([^）)]*[〕][^）)]*号)[）)]", title)
    if m:
        return m.group(1)
    return ""


def crawl_section(
    conn, section: str, section_name: str, listing_type: str,
    fetch_bodies: bool = True,
):
    """Crawl all listing pages in a section and fetch document details."""
    _, path, _ = SECTIONS[section]
    log.info(f"--- Section: {section_name} ({section}) ---")

    first_url = _listing_url(path, 0)
    try:
        html = fetch(first_url)
    except Exception as e:
        log.error(f"Failed to fetch {first_url}: {e}")
        return 0

    total_pages = _get_total_pages(html)
    log.info(f"  {total_pages} listing pages")

    # Parse appropriate listing format
    parse_fn = _parse_js_listing if listing_type == "js" else _parse_html_listing
    all_items = parse_fn(html, first_url)

    # Fetch remaining pages
    for page in range(1, total_pages):
        page_url = _listing_url(path, page)
        try:
            page_html = fetch(page_url)
            items = parse_fn(page_html, page_url)
            all_items.extend(items)
        except Exception as e:
            log.warning(f"  Failed page {page}: {e}")
        time.sleep(REQUEST_DELAY)

    # Deduplicate by URL (AI portal pages sometimes list items twice)
    seen = set()
    deduped = []
    for item in all_items:
        if item["url"] not in seen:
            seen.add(item["url"])
            deduped.append(item)
    all_items = deduped

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
        doc_number = (
            item.get("document_number", "")
            or _extract_doc_number(item["title"])
        )
        publisher = ""
        date_published = item.get("date_str", "")
        date_written = _parse_date(item.get("date_str", ""))
        identifier = ""
        classify_theme = ""

        if fetch_bodies:
            try:
                doc_html = fetch(doc_url)
                meta = _extract_meta(doc_html)
                body_text = _extract_body(doc_html)

                # Merge metadata
                publisher = meta.get(
                    "publisher", meta.get("ContentSource", "")
                )
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
            log.info(
                f"  Progress: {stored}/{len(all_items)} stored, "
                f"{bodies} bodies"
            )

    conn.commit()
    log.info(f"  Done: {stored} documents stored, {bodies} bodies fetched")
    return stored


def crawl_all(conn, sections: dict = None, fetch_bodies: bool = True):
    """Crawl all (or specified) Wuhan sections."""
    if sections is None:
        sections = {k: (v[0], v[2]) for k, v in SECTIONS.items()}

    store_site(conn, SITE_KEY, SITE_CFG)
    total = 0
    for section, (name, listing_type) in sections.items():
        total += crawl_section(
            conn, section, name, listing_type, fetch_bodies
        )
        time.sleep(REQUEST_DELAY)

    log.info(f"=== Wuhan total: {total} documents ===")


def main():
    parser = argparse.ArgumentParser(
        description="Wuhan Municipality Policy Crawler"
    )
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
        help="List document URLs without fetching bodies",
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

    if args.section:
        name, _, listing_type = SECTIONS[args.section]
        sections = {args.section: (name, listing_type)}
    else:
        sections = None

    crawl_all(conn, sections, fetch_bodies=not args.list_only)
    show_stats(conn)
    conn.close()


if __name__ == "__main__":
    main()
