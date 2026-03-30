"""
Ministry of Commerce (商务部 / MOFCOM) crawler.

Two data sources:
  1. Main site (www.mofcom.gov.cn/zwgk/zcfb/) — 2,200+ policy releases
     Uses an API that returns rendered HTML: /api-gateway/jpaas-publish-server/front/page/build/unit
     Article detail pages have meta tags (ArticleTitle, PubDate, ContentSource, Keywords)
     and body in <div class="art-con"> or <div ergodic="article" class="art-con">.

  2. Export control subdomain (exportcontrol.mofcom.gov.cn) — dedicated portal
     JSON API: /edi_ecms_web_front/front/column/getColumnList (paginated news)
     JSON API: /edi_ecms_web_front/front/column/getColumnListZcfgGn (domestic policy catalog)
     Article detail pages have inline HTML body in <div class="bd"> after JS variables.

Sections:
  Main site:
    zcfb      — 政策发布 (policy releases, ~2,300 docs)

  Export control subdomain:
    ec_gndt   — 国内动态 (domestic export control news, columnID=1, ~320 docs)
    ec_gjdt   — 国际动态 (international export control news, columnID=2, ~230 docs)
    ec_zcfg   — 政策法规 (export control laws/regulations, domestic catalog)
    ec_gfgd   — 各方观点 (expert perspectives, columnID=16, ~80 docs)
    ec_cjwt   — 常见问题 (FAQ, columnID=17, ~25 docs)

Usage:
    python -m crawlers.mofcom                        # Crawl all sections
    python -m crawlers.mofcom --section ec_gndt      # Export control domestic news only
    python -m crawlers.mofcom --section zcfb         # Main site policy releases only
    python -m crawlers.mofcom --stats                # Show database stats
    python -m crawlers.mofcom --list-only            # List URLs without fetching bodies
    python -m crawlers.mofcom --db documents_new.db  # Write to separate DB
"""

import argparse
import json
import re
import time
import urllib.parse
import urllib.request
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
    USER_AGENT,
)

SITE_KEY = "mofcom"
SITE_CFG = {
    "name": "Ministry of Commerce",
    "base_url": "https://www.mofcom.gov.cn",
    "admin_level": "central",
}

CST = timezone(timedelta(hours=8))

EC_BASE = "http://exportcontrol.mofcom.gov.cn"

# --- Sections ---

SECTIONS = {
    # Main site
    "zcfb": {
        "name": "政策发布",
        "source": "main",
    },
    # Export control subdomain — paginated news via getColumnList API
    "ec_gndt": {
        "name": "出口管制-国内动态",
        "source": "ec_list",
        "column_id": 1,
    },
    "ec_gjdt": {
        "name": "出口管制-国际动态",
        "source": "ec_list",
        "column_id": 2,
    },
    "ec_gfgd": {
        "name": "出口管制-各方观点",
        "source": "ec_list",
        "column_id": 16,
    },
    "ec_cjwt": {
        "name": "出口管制-常见问题",
        "source": "ec_list",
        "column_id": 17,
    },
    # Export control — policy/regulation catalog (single API call, not paginated)
    "ec_zcfg": {
        "name": "出口管制-政策法规",
        "source": "ec_zcfg",
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
        dt = datetime.strptime(date_str[:10], "%Y-%m-%d").replace(tzinfo=CST)
        return int(dt.timestamp())
    except ValueError:
        return 0


def _extract_doc_number(title: str) -> str:
    """Extract 文号 from title if present (e.g., 商务部公告2026年第11号)."""
    # Pattern: 商务部公告YYYY年第N号
    m = re.search(r"(商务部(?:公告|令)\d{4}年第\d+号)", title)
    if m:
        return m.group(1)
    # Standard bracket pattern
    m = re.search(r"[（(]([^）)]*[〕\]][^）)]*号)[）)]", title)
    if m:
        return m.group(1)
    return ""


# ====================================================================
# Main site (www.mofcom.gov.cn) — API-based listing + HTML detail pages
# ====================================================================

MAIN_API_URL = (
    "https://www.mofcom.gov.cn/api-gateway/jpaas-publish-server"
    "/front/page/build/unit"
)
MAIN_API_PARAMS = {
    "parseType": "bulidstatic",
    "webId": "8f43c7ad3afc411fb56f281724b73708",
    "tplSetId": "52551ea0e2c14bca8c84792f7aa37ead",
    "pageType": "column",
    "tagId": "分页列表",
    "editType": "null",
    "pageId": "fc8bdff48fa345a48b651c1285b70b8f",
}
MAIN_ROWS_PER_PAGE = 15
MAIN_BASE = "https://www.mofcom.gov.cn"


def _fetch_main_listing(page_no: int) -> tuple[list[dict], int]:
    """Fetch one page from the main MOFCOM policy listing API.

    Returns (items, total_count).
    Each item: {"url": ..., "title": ..., "date_str": ...}
    """
    params = dict(MAIN_API_PARAMS)
    if page_no > 1:
        params["paramJson"] = json.dumps(
            {"pageNo": page_no, "pageSize": MAIN_ROWS_PER_PAGE}
        )
    qs = urllib.parse.urlencode(params)
    url = f"{MAIN_API_URL}?{qs}"

    headers = {
        "Referer": "https://www.mofcom.gov.cn/zwgk/zcfb/",
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
    }
    text = fetch(url, headers=headers)
    data = json.loads(text)
    html = data.get("data", {}).get("html", "")

    items = []
    for m in re.finditer(
        r'<a\s+href="([^"]+)"[^>]*title="([^"]+)"[^>]*>.*?</a>\s*<span>\[(\d{4}-\d{2}-\d{2})\]</span>',
        html,
        re.DOTALL,
    ):
        href, title, date_str = m.group(1), m.group(2), m.group(3)
        doc_url = href if href.startswith("http") else MAIN_BASE + href
        items.append({"url": doc_url, "title": title.strip(), "date_str": date_str})

    total = 0
    count_m = re.search(r'count="(\d+)"', html)
    if count_m:
        total = int(count_m.group(1))

    return items, total


def _extract_main_body(html: str) -> str:
    """Extract body text from a main MOFCOM article page.

    Body is in <div ergodic="article" class="art-con ..."> or <div class="art-con">.
    """
    # Try ergodic="article" first (most common)
    m = re.search(
        r'<div\s+ergodic="article"\s+class="art-con[^"]*">(.*?)</div>\s*(?:<section|<div\s+class="article-tool)',
        html,
        re.DOTALL,
    )
    if not m:
        # Fallback: art-con div
        m = re.search(
            r'<div\s+class="art-con[^"]*">\s*(?:<div\s+class="art-con-gonggao">)?\s*(.*?)</div>',
            html,
            re.DOTALL,
        )
    if not m:
        return ""

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
        .replace("&#xa0;", " ")
        .replace("\u3000", " ")
        .replace("&lt;", "<")
        .replace("&gt;", ">")
        .replace("&amp;", "&")
        .strip()
    )
    return text if len(text) > 20 else ""


def _extract_main_meta(html: str) -> dict:
    """Extract metadata from main MOFCOM article meta tags."""
    meta = {}
    for name in (
        "ArticleTitle", "PubDate", "ContentSource", "Keywords",
        "Description", "ColumnName",
    ):
        m = re.search(
            rf'<meta\s+name="{name}"\s+content="([^"]*)"',
            html,
            re.IGNORECASE,
        )
        if m:
            meta[name] = m.group(1).strip()
    return meta


def crawl_main_section(conn, fetch_bodies: bool = True):
    """Crawl the main MOFCOM policy release listing."""
    log.info("--- Section: 政策发布 (zcfb, main site) ---")

    # First page to get total count
    try:
        items, total = _fetch_main_listing(1)
    except Exception as e:
        log.error(f"Failed to fetch main listing page 1: {e}")
        return 0

    if total == 0:
        total = len(items) * 10  # estimate
    total_pages = (total + MAIN_ROWS_PER_PAGE - 1) // MAIN_ROWS_PER_PAGE
    log.info(f"  {total} documents across {total_pages} pages")

    all_items = list(items)

    for page in range(2, total_pages + 1):
        try:
            page_items, _ = _fetch_main_listing(page)
            all_items.extend(page_items)
        except Exception as e:
            log.warning(f"  Failed page {page}: {e}")
        time.sleep(REQUEST_DELAY)

        if page % 20 == 0:
            log.info(f"  Listing progress: page {page}/{total_pages}, {len(all_items)} items")

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
        publisher = "商务部"
        keywords = ""
        date_published = item["date_str"]

        if fetch_bodies:
            try:
                doc_html = fetch(doc_url, headers={
                    "User-Agent": (
                        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                        "AppleWebKit/537.36"
                    ),
                })
                meta = _extract_main_meta(doc_html)
                body_text = _extract_main_body(doc_html)
                publisher = meta.get("ContentSource", publisher)
                keywords = meta.get("Keywords", "")
                if meta.get("PubDate"):
                    date_published = meta["PubDate"][:10]
                doc_number = doc_number or _extract_doc_number(
                    meta.get("ArticleTitle", "")
                )
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
            "keywords": keywords,
            "date_written": _parse_date(date_published),
            "date_published": date_published,
            "body_text_cn": body_text,
            "url": doc_url,
            "classify_main_name": "政策发布",
            "raw_html_path": raw_html_path,
        })
        stored += 1

        if stored % 20 == 0:
            conn.commit()
            log.info(f"  Progress: {stored}/{len(all_items)} stored, {bodies} bodies")

    conn.commit()
    log.info(f"  Done: {stored} documents stored, {bodies} bodies fetched")
    return stored


# ====================================================================
# Export control subdomain — JSON API
# ====================================================================

EC_LIST_API = EC_BASE + "/edi_ecms_web_front/front/column/getColumnList"
EC_ZCFG_GN_API = EC_BASE + "/edi_ecms_web_front/front/column/getColumnListZcfgGn"


def _fetch_ec_list_page(column_id: int, page_num: int) -> tuple[list[dict], int, int]:
    """Fetch one page from the export control article list API.

    Returns (items, total, max_page_num).
    Each item: {"url": ..., "title": ..., "date_str": ..., "source": ...}
    """
    data = urllib.parse.urlencode({
        "pageNumber": page_num,
        "columnID": column_id,
        "title": "",
    }).encode("utf-8")

    req = urllib.request.Request(
        EC_LIST_API,
        data=data,
        headers={
            "User-Agent": USER_AGENT,
            "Content-Type": "application/x-www-form-urlencoded",
        },
    )

    for attempt in range(3):
        try:
            resp = urllib.request.urlopen(req, timeout=20)
            text = resp.read().decode("utf-8", errors="replace")
            result = json.loads(text)
            break
        except Exception as e:
            if attempt < 2:
                time.sleep(2 ** attempt)
                log.warning(f"  Retry {attempt+1}/3 for EC list API col={column_id} p={page_num}: {e}")
            else:
                raise

    page_info = result.get("pageInfo", {})
    total = page_info.get("total", 0)
    max_page = page_info.get("maxPageNum", 1)
    rows = page_info.get("rows", [])

    items = []
    for row in rows:
        url = row.get("url", "")
        if url and not url.startswith("http"):
            url = EC_BASE + url
        pub_time = row.get("publishTimeStr", "")
        date_str = pub_time[:10] if pub_time else ""
        items.append({
            "url": url,
            "title": row.get("title", "").strip(),
            "date_str": date_str,
            "source": row.get("source", "").strip(),
        })

    return items, total, max_page


def _extract_ec_body(html: str) -> str:
    """Extract body text from an export control article detail page.

    Content is inline HTML inside <div class="bd"> after the <script> block.
    """
    # Find the <div class="bd"> content section
    bd_start = html.find('class="bd"')
    if bd_start == -1:
        return ""
    gt = html.find(">", bd_start)
    if gt == -1:
        return ""
    content_start = gt + 1

    # Find end: the disclaimer or next major section
    end_pos = -1
    for marker in ['class="u-disclaimer-box"', 'class="u-art-box-footer"',
                    '<div class="ft"', "<!-- /"]:
        pos = html.find(marker, content_start)
        if pos != -1 and (end_pos == -1 or pos < end_pos):
            end_pos = pos

    if end_pos == -1:
        end_pos = content_start + 50000

    content = html[content_start:end_pos]
    if not content.strip():
        return ""

    # Remove the inline <script> block
    content = re.sub(r"<script[^>]*>.*?</script>", "", content, flags=re.DOTALL)

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
        .replace("&#xa0;", " ")
        .replace("\u3000", " ")
        .replace("&lt;", "<")
        .replace("&gt;", ">")
        .replace("&amp;", "&")
        .strip()
    )
    return text if len(text) > 20 else ""


def _extract_ec_meta(html: str) -> dict:
    """Extract JS variable metadata from export control article page."""
    meta = {}
    for var_name in ("title", "source", "publishTime", "articleId", "siteId",
                     "subTitle", "articleType", "infoType"):
        m = re.search(
            rf"var\s+{var_name}\s*=\s*'([^']*)'",
            html,
        )
        if m:
            meta[var_name] = m.group(1).strip()
    return meta


def crawl_ec_list_section(conn, section_key: str, section: dict,
                          fetch_bodies: bool = True):
    """Crawl an export control paginated list section (news, FAQ, etc.)."""
    name = section["name"]
    column_id = section["column_id"]
    log.info(f"--- Section: {name} ({section_key}, columnID={column_id}) ---")

    try:
        items, total, max_page = _fetch_ec_list_page(column_id, 1)
    except Exception as e:
        log.error(f"Failed to fetch EC list col={column_id} page 1: {e}")
        return 0

    log.info(f"  {total} articles across {max_page} pages")

    all_items = list(items)
    for page in range(2, max_page + 1):
        try:
            page_items, _, _ = _fetch_ec_list_page(column_id, page)
            all_items.extend(page_items)
        except Exception as e:
            log.warning(f"  Failed page {page}: {e}")
        time.sleep(REQUEST_DELAY)

    log.info(f"  Found {len(all_items)} article links")

    stored = 0
    bodies = 0
    for item in all_items:
        doc_url = item["url"]
        if not doc_url:
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
        publisher = item.get("source") or "商务部"
        date_published = item["date_str"]

        if fetch_bodies:
            try:
                doc_html = fetch(doc_url)
                meta = _extract_ec_meta(doc_html)
                body_text = _extract_ec_body(doc_html)
                publisher = meta.get("source", publisher)
                if meta.get("publishTime"):
                    date_published = meta["publishTime"][:10]
                if doc_html:
                    raw_html_path = save_raw_html(SITE_KEY, doc_id, doc_html)
                    bodies += 1
            except Exception as e:
                log.warning(f"  Failed to fetch {doc_url}: {e}")
            time.sleep(REQUEST_DELAY)

        store_document(conn, SITE_KEY, {
            "id": doc_id,
            "title": item["title"],
            "document_number": _extract_doc_number(item["title"]),
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


def crawl_ec_zcfg_section(conn, fetch_bodies: bool = True):
    """Crawl the export control policy/regulation catalog.

    Uses the getColumnListZcfgGn API which returns all domestic policies
    organized by sub-category (laws, regulations, normative docs, control lists).
    """
    name = "出口管制-政策法规"
    log.info(f"--- Section: {name} (ec_zcfg) ---")

    # Fetch domestic policy catalog
    data = urllib.parse.urlencode({"parentId": 11}).encode("utf-8")
    req = urllib.request.Request(
        EC_ZCFG_GN_API,
        data=data,
        headers={
            "User-Agent": USER_AGENT,
            "Content-Type": "application/x-www-form-urlencoded",
        },
    )

    try:
        resp = urllib.request.urlopen(req, timeout=20)
        text = resp.read().decode("utf-8", errors="replace")
        result = json.loads(text)
    except Exception as e:
        log.error(f"Failed to fetch EC zcfg catalog: {e}")
        return 0

    # Parse nested structure: gnInfoLists -> [{ name, datas: [{title, url, ...}] }]
    all_items = []
    for category in result.get("gnInfoLists", []):
        cat_name = category.get("name", "")
        for article in category.get("datas", []):
            url = article.get("url", "")
            if url and not url.startswith("http"):
                url = EC_BASE + url
            pub_time = article.get("publishTimeStr", "")
            date_str = pub_time[:10] if pub_time else ""
            all_items.append({
                "url": url,
                "title": article.get("title", "").strip(),
                "date_str": date_str,
                "sub_category": cat_name,
                "sub_title": (article.get("subTitle") or "").strip(),
            })

    # Also fetch sanction list items if present
    for item in result.get("sanctionList", []):
        # These are just category headers, not individual documents
        pass

    log.info(f"  Found {len(all_items)} policy/regulation documents")

    stored = 0
    bodies = 0
    for item in all_items:
        doc_url = item["url"]
        if not doc_url:
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
        publisher = "商务部"
        date_published = item["date_str"]

        if fetch_bodies:
            try:
                doc_html = fetch(doc_url)
                meta = _extract_ec_meta(doc_html)
                body_text = _extract_ec_body(doc_html)
                publisher = meta.get("source", publisher)
                if meta.get("publishTime"):
                    date_published = meta["publishTime"][:10]
                if doc_html:
                    raw_html_path = save_raw_html(SITE_KEY, doc_id, doc_html)
                    bodies += 1
            except Exception as e:
                log.warning(f"  Failed to fetch {doc_url}: {e}")
            time.sleep(REQUEST_DELAY)

        store_document(conn, SITE_KEY, {
            "id": doc_id,
            "title": item["title"],
            "document_number": _extract_doc_number(item["title"]),
            "publisher": publisher,
            "date_written": _parse_date(date_published),
            "date_published": date_published,
            "body_text_cn": body_text,
            "url": doc_url,
            "classify_main_name": name,
            "classify_genre_name": item.get("sub_category", ""),
            "raw_html_path": raw_html_path,
        })
        stored += 1

        if stored % 10 == 0:
            conn.commit()
            log.info(f"  Progress: {stored}/{len(all_items)} stored, {bodies} bodies")

    conn.commit()
    log.info(f"  Done: {stored} documents stored, {bodies} bodies fetched")
    return stored


# ====================================================================
# Orchestration
# ====================================================================

def crawl_all(conn, sections: dict = None, fetch_bodies: bool = True):
    """Crawl all (or specified) MOFCOM sections."""
    if sections is None:
        sections = SECTIONS

    store_site(conn, SITE_KEY, SITE_CFG)
    total = 0

    for key, section in sections.items():
        source = section["source"]
        if source == "main":
            total += crawl_main_section(conn, fetch_bodies)
        elif source == "ec_list":
            total += crawl_ec_list_section(conn, key, section, fetch_bodies)
        elif source == "ec_zcfg":
            total += crawl_ec_zcfg_section(conn, fetch_bodies)
        time.sleep(REQUEST_DELAY)

    log.info(f"=== MOFCOM total: {total} documents ===")


def main():
    parser = argparse.ArgumentParser(description="MOFCOM / Export Control Crawler")
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
