"""
Shenzhen non-gkmlpt content crawler.

Crawls investment news, government notices, and department content from
sz.gov.cn, fgw.sz.gov.cn, and lg.gov.cn — sections that are NOT on the
gkmlpt platform. Uses curl for fetching (sz.gov.cn has TLS issues with
Python's SSL library).

Usage:
    python -m crawlers.sz_invest                     # Crawl all sections
    python -m crawlers.sz_invest --section tzdt      # Crawl only 投资动态
    python -m crawlers.sz_invest --stats             # Show database stats
    python -m crawlers.sz_invest --list-only         # List URLs without fetching bodies
"""

import argparse
import re
import subprocess
import time

from crawlers.base import (
    REQUEST_DELAY,
    init_db,
    log,
    next_id,
    save_raw_html,
    show_stats,
    store_document,
    store_site,
)

SITE_KEY = "sz_invest"
SITE_CFG = {
    "name": "Shenzhen Portal (non-gkmlpt)",
    "base_url": "https://www.sz.gov.cn",
    "admin_level": "municipal",
}

# Each section defines: base_url, path, list parser type, body selector
SECTIONS = {
    # --- sz.gov.cn: investment portal ---
    "tzdt": {
        "name": "投资动态",
        "base_url": "https://www.sz.gov.cn",
        "path": "/cn/zjsz/fwts_1_3/tzdt_1/",
        "list_type": "sz",        # <li> with span.number, span.tit
        "body_selector": "news_cont_d_wrap",
    },
    # --- sz.gov.cn: government info disclosure ---
    "tzgg": {
        "name": "通知公告",
        "base_url": "https://www.sz.gov.cn",
        "path": "/cn/xxgk/zfxxgj/tzgg/",
        "list_type": "sz",
        "body_selector": "news_cont_d_wrap",
    },
    "zwdt": {
        "name": "政务动态",
        "base_url": "https://www.sz.gov.cn",
        "path": "/cn/xxgk/zfxxgj/zwdt/",
        "list_type": "sz",
        "body_selector": "news_cont_d_wrap",
    },
    # --- fgw.sz.gov.cn: DRC special topics ---
    "fgw_xwdt": {
        "name": "发改委新闻动态",
        "base_url": "https://fgw.sz.gov.cn",
        "path": "/ztzl/qtztzl/szscjmyjjfzzhfwpt/xwdt/",
        "list_type": "fgw",       # <a> with span.zyzp-text, span.zyzp-time
        "body_selector": "articleBox",
    },
    # --- lg.gov.cn: Longgang AI/robotics department ---
    "lg_ai": {
        "name": "龙岗AI与机器人动态",
        "base_url": "https://www.lg.gov.cn",
        "path": "/bmzz/rgznjqrs/xxgk/qt/gzdt/",
        "list_type": "lg",        # standard <li> with <a> and <span> date
        "body_selector": "content_article",
    },
}


def _fetch(url: str, timeout: int = 20, retries: int = 3) -> str:
    """Fetch via curl — .gov.cn sites have TLS issues with Python's SSL."""
    for attempt in range(retries):
        try:
            result = subprocess.run(
                ["curl", "-sk", "--max-time", str(timeout), url],
                capture_output=True, text=True, timeout=timeout + 5,
            )
            if result.returncode == 0 and len(result.stdout) > 100:
                return result.stdout
            if attempt < retries - 1:
                log.warning(f"  Retry {attempt+1}/{retries} for {url}: curl rc={result.returncode}")
                time.sleep(2 ** attempt)
            else:
                raise RuntimeError(f"curl failed for {url}: rc={result.returncode}")
        except subprocess.TimeoutExpired:
            if attempt < retries - 1:
                log.warning(f"  Retry {attempt+1}/{retries} for {url}: timeout")
                time.sleep(2 ** attempt)
            else:
                raise RuntimeError(f"curl timeout for {url}")


def _section_url(base_url: str, path: str, page: int = 0) -> str:
    base = f"{base_url}{path}"
    if page == 0:
        return base + "index.html"
    return base + f"index_{page}.html"


def _get_total_pages(html: str) -> int:
    m = re.search(r"createPageHTML\((\d+),", html)
    if m:
        return int(m.group(1))
    pages = re.findall(r'index_(\d+)\.html', html)
    if pages:
        return max(int(p) for p in pages)
    return 1


# ---------------------------------------------------------------------------
# Listing parsers (one per list_type)
# ---------------------------------------------------------------------------

def _parse_sz(html: str) -> list[dict]:
    """sz.gov.cn: <li> with span.number + span.tit + span date.

    Handles two date formats: YYYY-MM-DD and YYYY年MM月DD日.
    """
    items = []
    for m in re.finditer(
        r'<li[^>]*>\s*'
        r'<span\s+class="number">[^<]*</span>\s*'
        r'<span\s+class="tit">\s*<a\s+href="([^"]+)"\s+title="([^"]*)"[^>]*>[^<]*</a>\s*</span>\s*'
        r'<span>(\d{4}[-年]\d{2}[-月]\d{2}日?)</span>\s*'
        r'</li>',
        html, re.DOTALL,
    ):
        url, title, raw_date = m.group(1), m.group(2).strip(), m.group(3)
        # Normalize date: 2026年03月25日 → 2026-03-25
        date_str = raw_date.replace("年", "-").replace("月", "-").rstrip("日")
        items.append({"url": url, "title": title, "date_str": date_str})
    return items


def _parse_fgw(html: str) -> list[dict]:
    """fgw.sz.gov.cn: <a> with span.zyzp-text + span.zyzp-time."""
    items = []
    for m in re.finditer(
        r'<a\s+href="([^"]*content/post_\d+\.html)"[^>]*title="([^"]*)"[^>]*>\s*'
        r'<span\s+class="zyzp-text">[^<]*</span>\s*'
        r'<span\s+class="zyzp-time">(\d{4}-\d{2}-\d{2})</span>',
        html, re.DOTALL,
    ):
        items.append({"url": m.group(1), "title": m.group(2).strip(), "date_str": m.group(3)})
    return items


def _parse_lg(html: str) -> list[dict]:
    """lg.gov.cn: <li> with <a href title> and <span> date."""
    items = []
    for m in re.finditer(
        r'<li[^>]*>\s*<a\s+href="([^"]*content/post_\d+\.html)"\s+title="([^"]*)"[^>]*>'
        r'.*?<span[^>]*>(\d{4}-\d{2}-\d{2})</span>\s*</li>',
        html, re.DOTALL,
    ):
        items.append({"url": m.group(1), "title": m.group(2).strip(), "date_str": m.group(3)})
    return items


PARSERS = {"sz": _parse_sz, "fgw": _parse_fgw, "lg": _parse_lg}


# ---------------------------------------------------------------------------
# Body extraction
# ---------------------------------------------------------------------------

def _extract_body(html: str, selector: str) -> str:
    """Extract body text using the specified CSS class."""
    m = re.search(
        rf'<div\s+class="[^"]*{re.escape(selector)}[^"]*"[^>]*>(.*?)</div>\s*(?:<div|</div>)',
        html, re.DOTALL,
    )
    if not m:
        return ""
    content = m.group(1)
    content = re.sub(r'<br\s*/?\s*>', '\n', content)
    content = re.sub(r'<p[^>]*>', '\n', content)
    content = re.sub(r'<[^>]+>', '', content)
    content = re.sub(r'[ \t]+', ' ', content)
    content = re.sub(r'\n\s*\n', '\n', content)
    content = content.replace("&nbsp;", " ").replace("&lt;", "<")
    content = content.replace("&gt;", ">").replace("&amp;", "&")
    content = content.strip()
    return content if len(content) > 20 else ""


def _extract_meta(html: str) -> dict:
    meta = {}
    m = re.search(r'来源[：:]\s*([^<\n]+)', html)
    if m:
        meta["publisher"] = m.group(1).strip()
    m = re.search(r'<meta\s+name="PubDate"\s+content="([^"]*)"', html)
    if m:
        meta["date"] = m.group(1).strip()
    return meta


# ---------------------------------------------------------------------------
# Crawl logic
# ---------------------------------------------------------------------------

def crawl_section(conn, section_key: str, section_cfg: dict, fetch_bodies: bool = True):
    base_url = section_cfg["base_url"]
    path = section_cfg["path"]
    name = section_cfg["name"]
    parse_fn = PARSERS[section_cfg["list_type"]]
    body_sel = section_cfg["body_selector"]

    log.info(f"--- Section: {name} ({section_key}) ---")

    first_url = _section_url(base_url, path, 0)
    try:
        html = _fetch(first_url)
    except Exception as e:
        log.error(f"Failed to fetch {first_url}: {e}")
        return 0

    total_pages = _get_total_pages(html)
    log.info(f"  {total_pages} listing pages")

    all_items = parse_fn(html)

    for page in range(1, total_pages):
        page_url = _section_url(base_url, path, page)
        try:
            page_html = _fetch(page_url)
            all_items.extend(parse_fn(page_html))
        except Exception as e:
            log.warning(f"  Failed page {page}: {e}")
        time.sleep(REQUEST_DELAY)

    log.info(f"  Found {len(all_items)} article links")

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
        publisher = ""
        date_published = item["date_str"]

        if fetch_bodies:
            try:
                doc_html = _fetch(doc_url)
                body_text = _extract_body(doc_html, body_sel)
                meta = _extract_meta(doc_html)
                publisher = meta.get("publisher", "")
                if meta.get("date"):
                    date_published = meta["date"]
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
            "document_number": "",
            "publisher": publisher,
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
    log.info(f"  Done: {stored} documents, {bodies} bodies")
    return stored


def crawl_all(conn, sections: dict = None, fetch_bodies: bool = True):
    if sections is None:
        sections = SECTIONS
    store_site(conn, SITE_KEY, SITE_CFG)
    total = 0
    for key, cfg in sections.items():
        total += crawl_section(conn, key, cfg, fetch_bodies)
        time.sleep(REQUEST_DELAY)
    log.info(f"=== {SITE_KEY} total: {total} documents ===")


def main():
    parser = argparse.ArgumentParser(description="Shenzhen Non-gkmlpt Content Crawler")
    parser.add_argument("--section", choices=list(SECTIONS.keys()),
                        help="Crawl only this section")
    parser.add_argument("--stats", action="store_true", help="Show database stats")
    parser.add_argument("--list-only", action="store_true",
                        help="List URLs without fetching bodies")
    args = parser.parse_args()

    conn = init_db()

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
