"""
Hangzhou Municipality (杭州市) crawler.

Crawls policy documents from www.hangzhou.gov.cn.  Hangzhou runs on JCMS
(same platform as Zhejiang province), with listings rendered by the JCMS API:

    /api-gateway/jpaas-publish-server/front/page/build/unit

The API uses "bulidstatic" pre-rendering.  From overseas IPs, page navigation
is unreliable (all pages return page 1), but the initial page for each column
does return items.  Sections with count > rows will only capture page 1 items
(see known limitation below).

URL patterns:
  Column:   /col/col{COLUMN_ID}/index.html
  JCMS API: /api-gateway/jpaas-publish-server/front/page/build/unit
            ?parseType=bulidstatic&webId=149&tplSetId=LWYUCb5AkzKrVm7WODRpT
            &pageType=column&tagId={TAG_ID}&pageId={COLUMN_ID}
            &rows=15&pageNo=1
  Detail:   /art/YYYY/M/D/art_{COL}_{NUM}.html
            /col/col{COL}/art/YYYY/art_{UUID}.html
  Body:     div.zc_article_con (regulations), div#zoom, div.TRS_Editor
  Meta:     <meta name="ArticleTitle|PubDate|ContentSource">

Listing HTML patterns (from JCMS API response):
  Department files:   <li><a title="TITLE" href="URL">...</a><b>DATE</b></li>
  Regulations:        <td><a title="TITLE" href="URL">...</a></td>
                      (dates in span.zc_list_con, e.g. "2025年11月20日...第354号公布")
  Personnel:          <li><a title="TITLE" href="URL">...</a><b>DATE</b></li>

Sections crawled:
  zfgz:    政府规章 (Government regulations, ~15 items)
  bmwj:    部门文件 (Department documents, 432 items — page 1 only from US)
  rsrm:    人事任免 (Personnel appointments, 117 items — page 1 only)

Known limitation:
  The JCMS "bulidstatic" API ignores pageNo from overseas.  For sections with
  count > rows (15), only page 1 items are captured.  Full pagination needs a
  Chinese IP.  The regulations section has <=15 items so all are captured.

Usage:
    python -m crawlers.hangzhou                        # Crawl all sections
    python -m crawlers.hangzhou --section zfgz         # Government regulations
    python -m crawlers.hangzhou --section bmwj         # Department documents
    python -m crawlers.hangzhou --stats                # Show database stats
    python -m crawlers.hangzhou --list-only            # List without bodies
    python -m crawlers.hangzhou --db /tmp/hangzhou.db  # Write to temp DB
"""

import argparse
import re
import json
import time
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from html import unescape
from pathlib import Path
from urllib.parse import urljoin

from crawlers.base import (
    REQUEST_DELAY,
    allow_ipv6,
    fetch,
    init_db,
    log,
    next_id,
    save_raw_html,
    show_stats,
    store_document,
    store_site,
)

# Hangzhou is in Zhejiang; some resources may need IPv6
allow_ipv6("hangzhou.gov.cn")

SITE_KEY = "hangzhou"
SITE_CFG = {
    "name": "Hangzhou Municipality",
    "base_url": "https://www.hangzhou.gov.cn",
    "admin_level": "municipal",
}

CST = timezone(timedelta(hours=8))

_BASE_URL = "https://www.hangzhou.gov.cn"
_API_URL = f"{_BASE_URL}/api-gateway/jpaas-publish-server/front/page/build/unit"
_WEB_ID = "149"
_TPL_SET_ID = "LWYUCb5AkzKrVm7WODRpT"

# Section key -> (display name, column_id, tag_id, parse_type)
# parse_type: "li" = <li><a>TITLE</a><b>DATE</b></li>
#             "table" = regulations table layout
SECTIONS = {
    "zfgz": ("政府规章", "1229610717", "规章库列表", "table"),
    "bmwj": ("部门文件", "1229063389", "当前栏目列表a", "li"),
    "rsrm": ("人事任免", "1229063417", "当前栏目列表a", "li"),
}


def _fetch_jcms_page(column_id: str, tag_id: str, page_no: int = 1,
                     rows: int = 15) -> str:
    """Fetch one page of listings from the JCMS API.

    Returns the HTML fragment from the response, or empty string on error.
    """
    params = {
        "parseType": "bulidstatic",
        "webId": _WEB_ID,
        "tplSetId": _TPL_SET_ID,
        "pageType": "column",
        "tagId": tag_id,
        "pageId": column_id,
        "rows": str(rows),
        "pageNo": str(page_no),
    }
    url = _API_URL + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    })

    for attempt in range(3):
        try:
            resp = urllib.request.urlopen(req, timeout=20)
            text = resp.read().decode("utf-8", errors="replace")
            data = json.loads(text)
            if data.get("success") and "html" in data.get("data", {}):
                return data["data"]["html"]
            return ""
        except Exception as e:
            if attempt < 2:
                wait = 2 ** attempt
                log.warning(f"  Retry {attempt+1}/3 for JCMS page {page_no}: {e}")
                time.sleep(wait)
            else:
                log.error(f"  Failed JCMS page {page_no}: {e}")
                return ""


def _parse_listing_li(html: str) -> list[dict]:
    """Parse listing items in <li> format (department files, personnel).

    Pattern:
      <li>
        <a title="TITLE" target="_blank" href="URL">TITLE</a>
        <b>YYYY-MM-DD</b>
      </li>
    """
    items = []
    for m in re.finditer(
        r'<li[^>]*>\s*<a[^>]*title="([^"]*)"[^>]*href="([^"]*)"[^>]*>'
        r'.*?</a>\s*<b>(\d{4}-\d{2}-\d{2})</b>',
        html,
        re.DOTALL,
    ):
        title, href, date_str = m.group(1).strip(), m.group(2).strip(), m.group(3)
        if not title:
            continue
        doc_url = _resolve_url(href)
        items.append({
            "url": doc_url,
            "title": _clean_title(title),
            "date_str": date_str,
        })
    return items


def _parse_listing_table(html: str) -> list[dict]:
    """Parse listing items in table format (regulations).

    Pattern:
      <td>
        <a ... title="TITLE" href="URL" ...>TITLE</a>
        <br/>
        <span class="zc_list_con">
          YYYY年M月D日杭州市人民政府令第NNN号公布 ...
        </span>
      </td>
    """
    items = []
    for m in re.finditer(
        r'<a[^>]*href="([^"]*)"[^>]*title="([^"]*)"[^>]*>.*?</a>\s*'
        r'(?:<br\s*/?>)?\s*<span[^>]*class="zc_list_con"[^>]*>\s*(.*?)\s*</span>',
        html,
        re.DOTALL,
    ):
        href, title, desc = m.group(1).strip(), m.group(2).strip(), m.group(3).strip()
        if not title:
            continue

        doc_url = _resolve_url(href)

        # Extract date from description: "2025年11月20日..."
        date_str = ""
        dm = re.search(r"(\d{4})年(\d{1,2})月(\d{1,2})日", desc)
        if dm:
            date_str = f"{dm.group(1)}-{int(dm.group(2)):02d}-{int(dm.group(3)):02d}"

        # Extract document number from description: "第354号"
        doc_number = ""
        dn_m = re.search(r"第(\d+)号", desc)
        if dn_m:
            doc_number = f"杭州市人民政府令第{dn_m.group(1)}号"

        items.append({
            "url": doc_url,
            "title": _clean_title(title),
            "date_str": date_str,
            "document_number": doc_number,
        })
    return items


def _resolve_url(href: str) -> str:
    """Resolve a relative URL against the Hangzhou base."""
    href = href.strip()
    if href.startswith("//"):
        return "https:" + href
    if href.startswith("http"):
        return href
    return urljoin(_BASE_URL + "/", href.lstrip("/"))


def _clean_title(title: str) -> str:
    """Clean a document title: unescape entities, collapse whitespace."""
    title = unescape(title.strip())
    title = re.sub(r"\s+", " ", title)
    return title


def _get_pagination_count(html: str) -> int:
    """Extract total item count from JCMS pagination metadata.

    Looks for: count="432" in the pagination table.
    """
    m = re.search(r'count="(\d+)"', html)
    if m:
        return int(m.group(1))
    return 0


def _parse_date(date_str: str) -> int:
    """Convert date string to Unix timestamp at midnight CST."""
    date_str = (
        date_str.replace("/", "-")
        .replace("年", "-")
        .replace("月", "-")
        .replace("日", "")
    )
    try:
        dt = datetime.strptime(date_str.strip()[:10], "%Y-%m-%d").replace(
            tzinfo=CST
        )
        return int(dt.timestamp())
    except ValueError:
        return 0


def _extract_meta(html: str) -> dict:
    """Extract metadata from detail page.

    Sources:
    1. <meta> tags (ArticleTitle, PubDate, ContentSource, Keywords)
    2. xxgk metadata table if present
    """
    meta = {}

    # Source 1: <meta> tags
    for name in ("ArticleTitle", "PubDate", "ContentSource",
                 "ColumnName", "Keywords"):
        m = re.search(
            rf'<meta\s+name="{name}"\s+content="([^"]*)"', html, re.IGNORECASE
        )
        if m:
            meta[name] = m.group(1).strip()

    # Source 2: metadata from xxgk table rows or label patterns
    for m in re.finditer(
        r'<td[^>]*>\s*([^<]*(?:索引号|发文字号|文号|发文机关|发布机构|'
        r'成文日期|发布日期|主题分类|有效性)[^<]*)\s*</td>\s*<td[^>]*>\s*(.*?)\s*</td>',
        html,
        re.DOTALL,
    ):
        label = m.group(1).strip().rstrip("：:")
        value = re.sub(r"<[^>]+>", "", m.group(2)).strip()
        if not value:
            continue
        if "索引号" in label:
            meta["identifier"] = value
        elif "发文字号" in label or "文号" in label:
            meta["document_number"] = value
        elif "发文机关" in label or "发布机构" in label:
            meta["publisher"] = value
        elif "成文日期" in label:
            meta["date_written_str"] = value
        elif "发布日期" in label:
            meta["date_published_str"] = value
        elif "主题分类" in label:
            meta["classify_theme_name"] = value

    # Also try label/div patterns (some Hangzhou pages)
    for m in re.finditer(
        r'<label>\s*<font>\s*([^<]+)\s*</font>\s*</label>\s*'
        r'<div[^>]*class="display-block[^"]*"[^>]*>\s*(.*?)\s*</div>',
        html,
        re.DOTALL,
    ):
        label = re.sub(r"[&]\w+;", "", m.group(1)).strip().rstrip("：:")
        value = re.sub(r"<[^>]+>", "", m.group(2)).strip()
        if not value:
            continue
        if "索引号" in label:
            meta["identifier"] = value
        elif "发布机构" in label or "发文机关" in label:
            meta["publisher"] = value
        elif "文号" in label:
            meta["document_number"] = value
        elif "发文日期" in label or "成文日期" in label:
            meta["date_written_str"] = value

    return meta


def _extract_div_content(html: str, attr_idx: int) -> str:
    """Extract all content from a <div> tag, handling nested divs.

    attr_idx should point to a position inside the opening <div> tag
    (e.g. the start of 'class="..."').  This function finds the matching
    closing </div> by tracking div nesting depth.
    """
    # Find the > that closes the opening tag
    gt = html.find(">", attr_idx)
    if gt == -1:
        return ""
    start = gt + 1

    # Track nesting depth to find the matching </div>
    depth = 1
    pos = start
    while depth > 0 and pos < len(html):
        next_open = html.find("<div", pos)
        next_close = html.find("</div>", pos)

        if next_close == -1:
            break

        if next_open != -1 and next_open < next_close:
            depth += 1
            pos = next_open + 4
        else:
            depth -= 1
            if depth == 0:
                return html[start:next_close]
            pos = next_close + 6

    return ""


def _extract_body(html: str) -> str:
    """Extract plain text body from a document detail page.

    Tries containers in order:
    1. div.zc_article_con (Hangzhou regulations layout)
    2. div#zoom / div#zoomcon
    3. div.TRS_Editor / div.trs_editor_view
    4. div.article-content
    """
    content = ""

    # Try string-based extraction for zc_article_con first.
    # This div contains nested divs (zc_artice_tit, zc_artice_tit1),
    # so we need to find the matching closing tag by tracking depth.
    idx = html.find('class="zc_article_con"')
    if idx == -1:
        idx = html.find("class='zc_article_con'")
    if idx >= 0:
        content = _extract_div_content(html, idx)

    if not content:
        # Try id="zoomcon" or id="zoom" — also may have nested divs
        for id_name in ("zoomcon", "zoom"):
            idx = html.find(f'id="{id_name}"')
            if idx == -1:
                idx = html.find(f"id='{id_name}'")
            if idx >= 0:
                content = _extract_div_content(html, idx)
                if content:
                    break

    if not content:
        # Regex fallback for other containers
        for pattern in [
            r'<div[^>]*class="[^"]*\bTRS_Editor\b[^"]*"[^>]*>(.*?)</div>',
            r'<div[^>]*class="[^"]*\btrs_editor_view\b[^"]*"[^>]*>(.*?)</div>',
            r'<div[^>]*class="[^"]*\barticle-content\b[^"]*"[^>]*>(.*?)</div>',
            r'<div[^>]*class="[^"]*\bcontent\b[^"]*"[^>]*>(.*?)</div>',
        ]:
            m = re.search(pattern, html, re.DOTALL)
            if m:
                content = m.group(1)
                break

    if not content:
        return ""

    # Convert HTML to plain text
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
    """Extract document number from title parentheses if present."""
    m = re.search(r"[（(]([^）)]*[〕][^）)]*号)[）)]", title)
    if m:
        return m.group(1)
    return ""


def crawl_section(
    conn,
    section_key: str,
    section_name: str,
    column_id: str,
    tag_id: str,
    parse_type: str,
    fetch_bodies: bool = True,
):
    """Crawl a single section via the JCMS API."""
    log.info(f"--- Section: {section_name} ({section_key}) ---")

    # Fetch page 1
    html = _fetch_jcms_page(column_id, tag_id, page_no=1)
    if not html:
        log.error(f"  JCMS API returned empty response")
        return 0

    # Parse items from page 1
    if parse_type == "table":
        all_items = _parse_listing_table(html)
    else:
        all_items = _parse_listing_li(html)

    # Check pagination count
    total_count = _get_pagination_count(html)
    if total_count > 0:
        log.info(
            f"  Total in section: {total_count}, "
            f"captured page 1: {len(all_items)} items"
        )
        if total_count > len(all_items):
            # Try fetching page 2 to see if pagination works
            html2 = _fetch_jcms_page(column_id, tag_id, page_no=2)
            if html2:
                if parse_type == "table":
                    p2_items = _parse_listing_table(html2)
                else:
                    p2_items = _parse_listing_li(html2)
                # Check if page 2 has different items
                p1_urls = {i["url"] for i in all_items}
                new_items = [i for i in p2_items if i["url"] not in p1_urls]
                if new_items:
                    all_items.extend(new_items)
                    log.info(f"  Page 2: {len(new_items)} new items")
                    # Continue fetching pages
                    total_pages = (total_count + 14) // 15
                    for page_no in range(3, total_pages + 1):
                        time.sleep(REQUEST_DELAY)
                        page_html = _fetch_jcms_page(
                            column_id, tag_id, page_no=page_no
                        )
                        if not page_html:
                            break
                        if parse_type == "table":
                            page_items = _parse_listing_table(page_html)
                        else:
                            page_items = _parse_listing_li(page_html)
                        existing_urls = {i["url"] for i in all_items}
                        new_page = [
                            i for i in page_items
                            if i["url"] not in existing_urls
                        ]
                        if not new_page:
                            log.info(
                                f"  Page {page_no} returned duplicates — "
                                f"stopping pagination"
                            )
                            break
                        all_items.extend(new_page)
                        if page_no % 10 == 0:
                            log.info(
                                f"  Listing progress: page {page_no}/"
                                f"{total_pages}, {len(all_items)} items"
                            )
                else:
                    log.info(
                        f"  NOTE: Pagination returns duplicate page — only "
                        f"page 1 accessible from this IP "
                        f"({total_count - len(all_items)} items on later pages)"
                    )
            time.sleep(REQUEST_DELAY)
    else:
        log.info(f"  Found {len(all_items)} items (no pagination)")

    log.info(f"  Found {len(all_items)} document links total")

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
        doc_number = item.get("document_number", "") or _extract_doc_number(
            item["title"]
        )
        publisher = ""
        date_published = item.get("date_str", "")
        date_written = _parse_date(item.get("date_str", ""))
        identifier = ""
        classify_theme = ""

        if fetch_bodies:
            try:
                doc_html = fetch(doc_url, headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                })
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
                    date_published = meta["PubDate"].split()[0]
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
    """Crawl all (or specified) Hangzhou sections."""
    if sections is None:
        sections = {
            k: (v[0], v[1], v[2], v[3]) for k, v in SECTIONS.items()
        }

    store_site(conn, SITE_KEY, SITE_CFG)
    total = 0
    for section_key, (name, col_id, tag_id, parse_type) in sections.items():
        total += crawl_section(
            conn, section_key, name, col_id, tag_id, parse_type,
            fetch_bodies=fetch_bodies,
        )
        time.sleep(REQUEST_DELAY)

    log.info(f"=== Hangzhou total: {total} documents ===")


def main():
    parser = argparse.ArgumentParser(
        description="Hangzhou Municipality Policy Crawler"
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
        name, col_id, tag_id, parse_type = SECTIONS[args.section]
        sections = {args.section: (name, col_id, tag_id, parse_type)}
    else:
        sections = None

    crawl_all(conn, sections, fetch_bodies=not args.list_only)
    show_stats(conn)
    conn.close()


if __name__ == "__main__":
    main()
