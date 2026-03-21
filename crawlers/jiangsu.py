"""
Jiangsu Province (江苏省) crawler.

Crawls policy documents from www.jiangsu.gov.cn. Jiangsu uses a custom CMS
with static HTML listing pages under the government information disclosure
and policy document sections.

URL patterns:
  Listing:  /art/jszfxxgk/{section}/index.html (path-based pagination)
  Detail:   /art/YYYY/M/D/art_{cat_id}_{art_id}.html
  Body:     div.article-body or div.con_text or div#zoom
  Meta:     <meta> tags + structured info table

Sections crawled:
  - Provincial government rules (省政府规章)
  - Provincial government documents (省政府文件)
  - Normative documents (省政府规范性文件)
  - Provincial office documents (省政府办公厅文件)
  - Policy interpretations (政策解读)

Usage:
    python -m crawlers.jiangsu                    # Crawl all sections
    python -m crawlers.jiangsu --section gfxwj    # Crawl normative documents only
    python -m crawlers.jiangsu --stats            # Show database stats
    python -m crawlers.jiangsu --list-only        # List without fetching bodies
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

SITE_KEY = "js"
SITE_CFG = {
    "name": "Jiangsu Province",
    "base_url": "https://www.jiangsu.gov.cn",
    "admin_level": "provincial",
}

CST = timezone(timedelta(hours=8))

# Section key -> (section name, column ID for jpage API)
# Jiangsu uses jpage jQuery plugin with dataproxy.jsp for AJAX pagination.
# Column IDs discovered via recon of www.jiangsu.gov.cn.
SECTIONS = {
    "zcwj": ("最新文件", "84242"),         # Latest files (~5184 docs)
    "zcjd": ("政策解读", "84725"),          # Policy interpretations
    "xxgk": ("政府信息公开", "84239"),      # Government info disclosure
    "szfgb": ("省政府公报", "81677"),       # Provincial government gazette
}

_BASE_URL = "https://www.jiangsu.gov.cn"
_JPAGE_URL = f"{_BASE_URL}/module/web/jpage/dataproxy.jsp"
_PAGE_SIZE = 20  # jpage default perPage


def _section_url(section: str, page: int = 0) -> str:
    """Build listing page URL for a section.

    Page 0 returns the main column page (server-rendered first page).
    Subsequent pages are fetched via jpage dataproxy.jsp API.
    """
    _, col_id = SECTIONS[section]
    if page == 0:
        return f"{_BASE_URL}/col/col{col_id}/index.html"
    # jpage uses 1-based page numbers in the API
    return (
        f"{_JPAGE_URL}?startrecord={(page * _PAGE_SIZE) + 1}"
        f"&endrecord={(page + 1) * _PAGE_SIZE}"
        f"&perpage={_PAGE_SIZE}&columnid={col_id}&unitid=356383&webid=1"
    )


def _get_total_pages(html: str) -> int:
    """Extract total page count from jpage configuration.

    Jiangsu uses jpage plugin: totalRecord:N, perPage:M
    """
    total_m = re.search(r"totalRecord[\"']?\s*[:=]\s*[\"']?(\d+)", html)
    if total_m:
        total = int(total_m.group(1))
        return (total + _PAGE_SIZE - 1) // _PAGE_SIZE
    # Fallback patterns
    m = re.search(r"createPageHTML\((\d+),", html)
    if m:
        return int(m.group(1))
    m = re.search(r"共\s*(\d+)\s*页", html)
    if m:
        return int(m.group(1))
    return 1


def _extract_jpage_records(xml: str) -> str:
    """Extract HTML content from jpage XML CDATA responses.

    jpage dataproxy.jsp returns XML like:
      <datastore><recordset>
        <record><![CDATA[<li>...</li>]]></record>
      </recordset></datastore>

    Extracts and concatenates all CDATA content into a single HTML string.
    """
    records = re.findall(r'<!\[CDATA\[(.*?)\]\]>', xml, re.DOTALL)
    if records:
        return "\n".join(records)
    return xml


def _parse_listing(html: str, base_url: str) -> list[dict]:
    """Parse a listing page and extract document links, titles, dates.

    Jiangsu uses <ul class="RcontUl"> with:
      <li class="clearfix">
        <a href="URL" title="TITLE">TEXT</a>
        <span class="time">YYYY-MM-DD</span>
        <span class="jds">...</span>
      </li>

    In jpage API responses, dates may have whitespace/newlines:
      <span class="time">
          2026-
          01-
          23
      </span>
    """
    items = []

    # If this is jpage XML, extract CDATA content first
    if "<datastore>" in html or "<recordset>" in html:
        html = _extract_jpage_records(html)

    # Pattern 1: <li> with title attribute, date in <span class="time">
    # Don't require </li> at end — there's a <span class="jds"> block after the date.
    # Allow whitespace in date values (jpage API splits dates across lines).
    for m in re.finditer(
        r'<li[^>]*>\s*<a\s+href="([^"]+)"[^>]*title="([^"]*)"[^>]*>.*?</a>'
        r'.*?<span[^>]*class="time"[^>]*>\s*'
        r'(\d{4})\s*[-/]\s*(\d{2})\s*[-/]\s*(\d{2})\s*</span>',
        html,
        re.DOTALL,
    ):
        href, title = m.group(1), m.group(2)
        date_str = f"{m.group(3)}-{m.group(4)}-{m.group(5)}"
        doc_url = urljoin(base_url, href)
        items.append({
            "url": doc_url,
            "title": unescape(title.strip()),
            "date_str": date_str,
        })

    if items:
        return items

    # Pattern 2: <li> without title attribute, date in any <span>
    for m in re.finditer(
        r'<li[^>]*>\s*<a\s+href="([^"]+)"[^>]*>([^<]+)</a>'
        r'.*?<span[^>]*>\s*(\d{4})\s*[-/]\s*(\d{2})\s*[-/]\s*(\d{2})\s*</span>',
        html,
        re.DOTALL,
    ):
        href, title = m.group(1), m.group(2)
        date_str = f"{m.group(3)}-{m.group(4)}-{m.group(5)}"
        doc_url = urljoin(base_url, href)
        items.append({
            "url": doc_url,
            "title": unescape(title.strip()),
            "date_str": date_str,
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
    """Extract metadata from detail page."""
    meta = {}

    # <meta> tags
    for name in ("ArticleTitle", "PubDate", "ContentSource",
                 "ColumnName", "Keywords"):
        m = re.search(
            rf'<meta\s+name="{name}"\s+content="([^"]*)"', html, re.IGNORECASE
        )
        if m:
            meta[name] = m.group(1).strip()

    # Structured metadata table
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

    return meta


def _extract_body(html: str) -> str:
    """Extract plain text body from document detail page.

    Tries multiple container selectors:
    1. div.article-body (Jiangsu primary)
    2. div.con_text (alternate layout)
    3. div#zoom (common gov.cn)
    4. div.TRS_Editor (TRS CMS)
    """
    content = ""
    # Jiangsu uses div.artile_zw (note typo) as the main content container.
    # It contains scripts, styles, a metadata table, and the body text.
    for pattern in [
        r'<div[^>]*class="[^"]*\bartile_zw\b[^"]*"[^>]*>(.*?)</div>\s*(?:<div[^>]*class="[^"]*\bfenxiang\b|<div[^>]*class="[^"]*\bright\b)',
        r'<div[^>]*class="[^"]*\barticle\b[^"]*"[^>]*>(.*?)</div>\s*</div>',
        r'<div[^>]*id=["\']zoom["\'][^>]*>(.*?)</div>',
        r'<div[^>]*class="[^"]*\bTRS_Editor\b[^"]*"[^>]*>(.*?)</div>',
    ]:
        m = re.search(pattern, html, re.DOTALL)
        if m:
            content = m.group(1)
            break

    if not content:
        return ""

    # Strip scripts, styles, and metadata table before extracting text
    content = re.sub(r"<script[^>]*>.*?</script>", "", content, flags=re.DOTALL)
    content = re.sub(r"<style[^>]*>.*?</style>", "", content, flags=re.DOTALL)
    content = re.sub(r"<table[^>]*class=\"xxgk_table\".*?</table>", "", content, flags=re.DOTALL)
    content = re.sub(r"<br\s*/?\s*>", "\n", content)
    content = re.sub(r"</p>", "\n", content)
    text = re.sub(r"<[^>]+>", "", content)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n\s*\n", "\n", text)
    text = text.strip()
    text = unescape(text)
    text = text.replace("\xa0", " ")

    if len(text) > 20:
        return text
    return ""


def _extract_doc_number(title: str) -> str:
    """Extract document number from title (苏政发〔YYYY〕N号)."""
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

    all_items = _parse_listing(html, first_url)

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
        date_published = item["date_str"]
        date_written = _parse_date(item["date_str"])
        identifier = ""
        classify_theme = ""

        if fetch_bodies:
            try:
                doc_html = fetch(doc_url)
                meta = _extract_meta(doc_html)
                body_text = _extract_body(doc_html)

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
    """Crawl all (or specified) Jiangsu sections."""
    if sections is None:
        sections = {k: v[0] for k, v in SECTIONS.items()}

    store_site(conn, SITE_KEY, SITE_CFG)
    total = 0
    for section, name in sections.items():
        total += crawl_section(conn, section, name, fetch_bodies)
        time.sleep(REQUEST_DELAY)

    log.info(f"=== Jiangsu total: {total} documents ===")


def main():
    parser = argparse.ArgumentParser(description="Jiangsu Province Policy Crawler")
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
