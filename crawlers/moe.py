"""
Ministry of Education (教育部) crawler.

Crawls policy documents from www.moe.gov.cn. Uses MOE's WAS (Web Application
Server) search system for paginated listings, with rich metadata extraction
from individual document pages.

Key sections:
  - S&T Department (科学技术与信息化司, A16): AI+Education policies, informatics
  - Policy & Regulations (政策法规司): Laws, normative documents
  - Development Planning (发展规划司): Five-year plans, strategic planning
  - Ministry Orders (部令): Formal regulatory orders
  - Normative Documents (规范性文件): Binding policy documents

The WAS system provides a unified search endpoint:
  /was5/web/search?channelid={ID}&page={N}
Each channelid corresponds to a department or document category.

Document pages have rich <meta> tags (ArticleTitle, publishdate, ContentSource)
plus a #moe-policy-table with 信息索引, 发文字号, 发文机构 etc.

Usage:
    python -m crawlers.moe                    # Crawl all sections
    python -m crawlers.moe --section a16      # S&T Department only
    python -m crawlers.moe --section orders   # Ministry orders only
    python -m crawlers.moe --stats            # Show database stats
    python -m crawlers.moe --list-only        # List URLs without fetching bodies
    python -m crawlers.moe --limit 50         # First 50 docs per section
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

SITE_KEY = "moe"
SITE_CFG = {
    "name": "Ministry of Education (教育部)",
    "base_url": "https://www.moe.gov.cn",
    "admin_level": "central",
}

BASE_URL = "http://www.moe.gov.cn"
CST = timezone(timedelta(hours=8))

# WAS search channel IDs — each corresponds to a section/department
SECTIONS = {
    "a16": {
        "name": "科学技术与信息化司",
        "channelid": 236238,
        "note": "AI+Education Action Plan, informatics policy",
    },
    "policy_law": {
        "name": "政策法规司",
        "channelid": 237424,
        "note": "Laws, regulations, legal opinions",
    },
    "normative": {
        "name": "规范性文件",
        "channelid": 267907,
        "note": "Binding normative documents",
    },
    "orders": {
        "name": "部令",
        "channelid": 280494,
        "note": "Formal ministry orders (highest authority)",
    },
    "planning": {
        "name": "发展规划司",
        "channelid": 288139,
        "note": "Strategic planning, five-year plans",
    },
    "higher_ed": {
        "name": "高等教育司",
        "channelid": 289115,
        "note": "University policy, academic programs",
    },
    "ministry_docs": {
        "name": "部文",
        "channelid": 289046,
        "note": "Ministry-level formal documents",
    },
}

WAS_PAGE_SIZE = 15  # MOE WAS returns 15 items per page


def _parse_date(date_str: str) -> int:
    """Convert date string to Unix timestamp at midnight CST."""
    if not date_str:
        return 0
    date_str = date_str.replace("/", "-").strip()
    try:
        dt = datetime.strptime(date_str[:10], "%Y-%m-%d").replace(tzinfo=CST)
        return int(dt.timestamp())
    except ValueError:
        return 0


def _parse_was_listing(html: str) -> list[dict]:
    """Parse WAS search results page.

    Format: <li><a href="URL">TITLE</a><span>DATE</span></li>
    The WAS system returns absolute URLs.
    """
    items = []
    # Pattern: <li> with <a href="...">title</a> and <span>date</span>
    for m in re.finditer(
        r'<li[^>]*>\s*<a\s+href="([^"]+)"[^>]*>([^<]+)</a>\s*<span>(\d{4}-\d{2}-\d{2})</span>',
        html,
    ):
        url, title, date_str = m.group(1), m.group(2), m.group(3)
        # Normalize URL
        if url.startswith("/"):
            url = BASE_URL + url
        items.append({
            "url": url,
            "title": title.strip(),
            "date_str": date_str,
        })
    return items


def _parse_static_listing(html: str, base_url: str) -> list[dict]:
    """Parse static listing pages (jyb_xxgk sections).

    Format: <li><a href="./YYYYMM/t..." title="FULL">SHORT</a><span>DATE</span></li>
    """
    items = []
    for m in re.finditer(
        r'<li[^>]*>\s*<a\s+href="([^"]+)"[^>]*?(?:title="([^"]*)")?[^>]*>([^<]+)</a>'
        r'\s*<span>(\d{4}-\d{2}-\d{2})</span>',
        html,
    ):
        href, full_title, short_title, date_str = (
            m.group(1), m.group(2), m.group(3), m.group(4)
        )
        url = urljoin(base_url, href)
        title = full_title if full_title else short_title
        items.append({
            "url": url,
            "title": title.strip(),
            "date_str": date_str,
        })
    return items


def _get_was_page_count(html: str) -> int:
    """Extract total page count from WAS listing JS."""
    m = re.search(r"countPage\s*=\s*(\d+)", html)
    if m:
        return int(m.group(1))
    # Fallback: calculate from recordCount
    m = re.search(r"recordCount\s*=\s*(\d+)", html)
    if m:
        total = int(m.group(1))
        return (total + WAS_PAGE_SIZE - 1) // WAS_PAGE_SIZE
    return 1


def _extract_body(html: str) -> str:
    """Extract body text from MOE document page.

    Primary: div#downloadContent (policy documents)
    Fallback: div.moe_content (news/articles)
    """
    # Try #downloadContent first (policy docs)
    start = html.find('id="downloadContent"')
    if start == -1:
        # Fallback: class="moe_content"
        start = html.find('class="moe_content"')
    if start == -1:
        # Another fallback: TRS_Editor
        start = html.find('class="TRS_Editor"')
    if start == -1:
        return ""

    gt = html.find(">", start)
    if gt == -1:
        return ""
    content_start = gt + 1

    # Find end boundary
    end_pos = -1
    for marker in ['<div class="moe-detail-shuxing"', '<dl class="relnews"',
                   '<div class="editer_share"', '<div class="moe_footer"',
                   '<!-- footer', '<script']:
        pos = html.find(marker, content_start)
        if pos != -1 and (end_pos == -1 or pos < end_pos):
            end_pos = pos

    if end_pos == -1:
        end_pos = content_start + 80000

    content = html[content_start:end_pos]
    if not content.strip():
        return ""

    # Strip HTML tags, normalize whitespace
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
    """Extract metadata from <meta> tags on document pages."""
    meta = {}
    for name in ("ArticleTitle", "PubDate", "publishdate", "ContentSource",
                 "source", "ColumnName", "contentid", "author"):
        m = re.search(
            rf'<meta\s+name=["\']?{name}["\']?\s+content=["\']([^"\']*)["\']',
            html, re.IGNORECASE,
        )
        if m:
            meta[name] = m.group(1).strip()
    return meta


def _extract_policy_table(html: str) -> dict:
    """Extract data from the #moe-policy-table.

    Fields: 发文机构, 发文字号, 信息索引, 信息类别, 生成日期
    """
    info = {}
    table_start = html.find('id="moe-policy-table"')
    if table_start == -1:
        return info

    table_end = html.find("</table>", table_start)
    if table_end == -1:
        table_end = table_start + 5000
    table_html = html[table_start:table_end]

    # Extract key-value pairs from table cells
    # Format: <td class="policy-item-title">KEY：</td>\n<td class="policy-item-cont">VALUE</td>
    for key in ("发文机构", "发文字号", "信息索引", "信息类别", "生成日期", "信息名称"):
        m = re.search(
            rf'{key}[：:]\s*</td>\s*<td[^>]*>\s*([^<]+)',
            table_html,
            re.DOTALL,
        )
        if not m:
            # Alternative: within same cell
            m = re.search(rf'{key}[：:]\s*([^<\n]+)', table_html)
        if m:
            info[key] = m.group(1).strip()

    return info


def _extract_doc_number(body_text: str, policy_table: dict) -> str:
    """Extract document number (文号) from policy table or body text."""
    # Prefer policy table
    if policy_table.get("发文字号"):
        return policy_table["发文字号"]

    # Fallback: regex on body text
    head = body_text[:500]
    m = re.search(
        r"([\u4e00-\u9fff]+[\u3014\u3008\u300a\uff08\u2018\u301a〔]"
        r"(?:19|20)\d{2}"
        r"[\u3015\u3009\u300b\uff09\u2019\u301b〕]"
        r"\d+号)",
        head,
    )
    return m.group(1) if m else ""


def crawl_section(conn, section_key: str, section: dict,
                  fetch_bodies: bool = True, limit: int = 0):
    """Crawl a single WAS section."""
    name = section["name"]
    channelid = section["channelid"]
    log.info(f"--- Section: {name} ({section_key}, channelid={channelid}) ---")

    # Fetch first page to get pagination info
    was_url = f"{BASE_URL}/was5/web/search?channelid={channelid}&page=1"
    try:
        html = fetch(was_url)
    except Exception as e:
        log.error(f"Failed to fetch {was_url}: {e}")
        return 0

    total_pages = _get_was_page_count(html)
    log.info(f"  {total_pages} pages of results")

    all_items = _parse_was_listing(html)

    # Fetch remaining pages
    for page in range(2, total_pages + 1):
        if limit and len(all_items) >= limit:
            break
        page_url = f"{BASE_URL}/was5/web/search?channelid={channelid}&page={page}"
        try:
            page_html = fetch(page_url)
            all_items.extend(_parse_was_listing(page_html))
        except Exception as e:
            log.warning(f"  Failed page {page}: {e}")
        time.sleep(REQUEST_DELAY)

    if limit:
        all_items = all_items[:limit]

    log.info(f"  Found {len(all_items)} document links")

    stored = 0
    bodies = 0
    skipped = 0
    for item in all_items:
        doc_url = item["url"]
        existing = conn.execute(
            "SELECT id, body_text_cn FROM documents WHERE url = ? AND url != ''",
            (doc_url,),
        ).fetchone()
        if existing and existing[1]:
            skipped += 1
            continue

        doc_id = existing[0] if existing else next_id(conn)
        body_text = ""
        raw_html_path = ""
        doc_number = ""
        publisher = "教育部"
        date_published = item["date_str"]
        category = name

        if fetch_bodies:
            try:
                doc_html = fetch(doc_url)
                meta = _extract_meta(doc_html)
                policy_table = _extract_policy_table(doc_html)
                body_text = _extract_body(doc_html)
                doc_number = _extract_doc_number(body_text, policy_table)

                # Use richer metadata when available
                publisher = (
                    policy_table.get("发文机构")
                    or meta.get("ContentSource")
                    or meta.get("source")
                    or publisher
                )
                if meta.get("publishdate"):
                    date_published = meta["publishdate"][:10]
                elif meta.get("PubDate"):
                    date_published = meta["PubDate"][:10]
                if policy_table.get("信息类别"):
                    category = policy_table["信息类别"]

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
            "classify_main_name": category,
            "raw_html_path": raw_html_path,
            "keywords": "",
        })
        stored += 1

        if stored % 20 == 0:
            conn.commit()
            log.info(f"  Progress: {stored}/{len(all_items)} stored, {bodies} bodies, {skipped} skipped")

    conn.commit()
    log.info(f"  Done: {stored} stored, {bodies} bodies, {skipped} already existed")
    return stored


def crawl_all(conn, sections: dict = None, fetch_bodies: bool = True, limit: int = 0):
    """Crawl all (or specified) MOE sections."""
    if sections is None:
        sections = SECTIONS

    store_site(conn, SITE_KEY, SITE_CFG)
    total = 0
    for key, section in sections.items():
        total += crawl_section(conn, key, section, fetch_bodies, limit)
        time.sleep(REQUEST_DELAY)

    log.info(f"=== MOE total: {total} documents ===")
    return total


def main():
    parser = argparse.ArgumentParser(description="MOE (Ministry of Education) Crawler")
    parser.add_argument("--section", choices=list(SECTIONS.keys()),
                        help="Crawl only this section")
    parser.add_argument("--stats", action="store_true", help="Show database stats")
    parser.add_argument("--list-only", action="store_true",
                        help="List URLs without fetching bodies")
    parser.add_argument("--limit", type=int, default=0,
                        help="Max documents per section (0=all)")
    parser.add_argument("--db", type=str,
                        help="Path to SQLite database (default: documents.db)")
    args = parser.parse_args()

    conn = init_db(Path(args.db) if args.db else None)

    if args.stats:
        show_stats(conn)
        conn.close()
        return

    sections = {args.section: SECTIONS[args.section]} if args.section else None
    crawl_all(conn, sections, fetch_bodies=not args.list_only, limit=args.limit)
    show_stats(conn)
    conn.close()


if __name__ == "__main__":
    main()
