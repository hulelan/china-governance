"""
National Laws Database (国家法律法规数据库) crawler.

Crawls laws, regulations, and judicial interpretations from flk.npc.gov.cn.
This is the official free legal information platform maintained by the NPC,
containing the full text of all national laws, State Council administrative
regulations, local regulations, and judicial interpretations.

These are the foundational legal texts that policy documents reference — our
corpus has 159k unresolved citations pointing to laws we don't have. This
crawler fills that gap.

API: Spring Boot (RuoYi) backend with JSON POST endpoints.
  - /law-search/search/list   — paginated search (29k+ laws)
  - /law-search/search/flfgDetails — full text for one law

Categories (flfgCodeId):
  100: 宪法 (Constitution)
  102: 法律 (Laws)
  210: 行政法规 (Administrative Regulations)
  222: 地方法规 (Local Regulations)
  320: 高法司法解释 (Supreme Court Interpretations)
  330: 高检司法解释 (Supreme Procuratorate Interpretations)

Usage:
    python -m crawlers.npc                    # Crawl all laws
    python -m crawlers.npc --stats            # Show database stats
    python -m crawlers.npc --list-only        # List without fetching bodies
    python -m crawlers.npc --limit 100        # First 100 only
    python -m crawlers.npc --search 人工智能   # Search for AI-related laws
"""

import argparse
import json
import re
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone, timedelta
from pathlib import Path

from crawlers.base import (
    REQUEST_DELAY,
    init_db,
    log,
    next_id,
    show_stats,
    store_document,
    store_site,
)

SITE_KEY = "npc"
SITE_CFG = {
    "name": "National Laws Database (国家法律法规数据库)",
    "base_url": "https://flk.npc.gov.cn",
    "admin_level": "central",
}

BASE_URL = "https://flk.npc.gov.cn"
CST = timezone(timedelta(hours=8))

BROWSER_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)

# Category map from enumData API
CATEGORIES = {
    100: "宪法",
    102: "法律",
    180: "法律解释",
    190: "有关法律问题和重大问题的决定",
    195: "修正案",
    200: "修改、废止的决定（法律）",
    210: "行政法规",
    215: "修改、废止的决定（行政法规）",
    220: "监察法规",
    222: "地方法规",
    305: "法规性决定",
    310: "修改、废止的决定（地方法规）",
    320: "高法司法解释",
    330: "高检司法解释",
    340: "联合发布司法解释",
    350: "修改、废止的决定（司法解释）",
}


def _parse_date(date_str: str) -> int:
    """Convert date string (YYYY-MM-DD) to Unix timestamp."""
    if not date_str:
        return 0
    try:
        dt = datetime.strptime(date_str[:10], "%Y-%m-%d").replace(tzinfo=CST)
        return int(dt.timestamp())
    except ValueError:
        return 0


def _api_post(path: str, data: dict, timeout: int = 30) -> dict | None:
    """POST JSON to the flk.npc.gov.cn API."""
    url = BASE_URL + path
    payload = json.dumps(data).encode("utf-8")
    headers = {
        "User-Agent": BROWSER_UA,
        "Content-Type": "application/json;charset=UTF-8",
        "Accept": "application/json, text/plain, */*",
        "Origin": BASE_URL,
        "Referer": BASE_URL + "/",
    }

    for attempt in range(3):
        try:
            req = urllib.request.Request(url, data=payload, headers=headers)
            resp = urllib.request.urlopen(req, timeout=timeout)
            text = resp.read().decode("utf-8", errors="replace")
            result = json.loads(text)
            if result.get("code") == 200:
                return result
            else:
                log.warning(f"  API error: code={result.get('code')} msg={result.get('msg','')[:80]}")
                return None
        except (urllib.error.HTTPError, urllib.error.URLError, OSError, json.JSONDecodeError) as e:
            if attempt < 2:
                wait = 3 * (attempt + 1)
                log.warning(f"  Retry {attempt+1}/3 for {path}: {e}")
                time.sleep(wait)
            else:
                log.error(f"  Failed {path} after 3 retries: {e}")
                return None

    return None


PAGE_SIZE = 50  # Max rows per API call


def _search_page(page_num: int = 1, search_content: str = "") -> dict | None:
    """Fetch one page of search results."""
    body = {
        "searchType": 2,
        "sxx": [],
        "gbrqYear": [],
        "flfgCodeId": [],
        "zdjgCodeId": [],
        "searchContent": search_content,
        "searchRange": 1,
        "pageNum": page_num,
        "pageSize": PAGE_SIZE,
    }
    return _api_post("/law-search/search/list", body, timeout=45)


def _fetch_detail(law_id: str) -> dict | None:
    """Fetch detail metadata for a single law (GET endpoint).

    Note: Full law text is in DOCX files on an internal CDN
    (flkoss.obs-bj2-internal.cucloud.cn) only reachable from within
    China. The detail endpoint provides metadata + related-doc links
    but not the body text. Body text backfill requires Chinese IP access.
    """
    url = f"{BASE_URL}/law-search/search/flfgDetails?bbbs={law_id}"
    headers = {
        "User-Agent": BROWSER_UA,
        "Accept": "application/json, text/plain, */*",
        "Referer": f"{BASE_URL}/detail?id={law_id}",
    }
    for attempt in range(3):
        try:
            req = urllib.request.Request(url, headers=headers)
            resp = urllib.request.urlopen(req, timeout=45)
            text = resp.read().decode("utf-8", errors="replace")
            result = json.loads(text)
            if result.get("code") == 200:
                return result
            return None
        except Exception as e:
            if attempt < 2:
                time.sleep(3 * (attempt + 1))
            else:
                return None
    return None


def _clean_html(html_text: str) -> str:
    """Strip HTML tags from law body text."""
    if not html_text:
        return ""
    text = re.sub(r"<br\s*/?\s*>", "\n", html_text)
    text = re.sub(r"<p[^>]*>", "\n", text)
    text = re.sub(r"</p>", "", text)
    text = re.sub(r"<[^>]+>", "", text)
    text = text.replace("&nbsp;", " ").replace("&lt;", "<").replace("&gt;", ">").replace("&amp;", "&")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n\s*\n", "\n", text)
    return text.strip()


def crawl(conn, search_content: str = "", limit: int = 0, fetch_bodies: bool = True):
    """Crawl laws from the national database.

    Paginates through the search API (pageNum/pageSize). Body text is
    stored as empty since the DOCX files are on an internal CDN only
    accessible from China. The metadata alone (29k titles + publishers +
    dates + categories) enables citation resolution against our 159k
    unresolved citation references.
    """
    store_site(conn, SITE_KEY, SITE_CFG)

    # First page to get total count
    log.info("Fetching first page...")
    result = _search_page(page_num=1, search_content=search_content)
    if not result:
        log.error("Failed to fetch search results")
        return 0

    total = result.get("total", 0)
    total_pages = (total + PAGE_SIZE - 1) // PAGE_SIZE
    log.info(f"Total laws: {total} ({total_pages} pages of {PAGE_SIZE})")

    rows = result.get("rows", [])
    if not rows:
        log.warning("No results returned")
        return 0

    stored = 0
    skipped = 0
    page_num = 1

    while True:
        for item in rows:
            if limit and stored >= limit:
                break

            law_id = item.get("bbbs", "")
            title = item.get("title", "").strip()
            if not title or not law_id:
                continue

            doc_url = f"https://flk.npc.gov.cn/detail?id={law_id}"

            existing = conn.execute(
                "SELECT id FROM documents WHERE url = ?", (doc_url,)
            ).fetchone()
            if existing:
                skipped += 1
                continue

            doc_id = next_id(conn)

            gbrq = item.get("gbrq", "")   # 公布日期
            sxrq = item.get("sxrq", "")   # 施行日期
            flfg_code = item.get("flfgCodeId", 0)
            category = CATEGORIES.get(flfg_code, item.get("flxz", ""))
            publisher = item.get("zdjgName", "")

            store_document(conn, SITE_KEY, {
                "id": doc_id,
                "title": title,
                "publisher": publisher,
                "date_written": _parse_date(gbrq),
                "date_published": gbrq,
                "body_text_cn": "",  # Body requires Chinese IP access
                "url": doc_url,
                "classify_main_name": category,
                "raw_html_path": "",
                "keywords": f"effective:{sxrq}" if sxrq else "",
            })
            stored += 1

        if limit and stored >= limit:
            break

        # Next page
        page_num += 1
        if page_num > total_pages:
            break

        if page_num % 10 == 0:
            conn.commit()
            log.info(f"  Page {page_num}/{total_pages}: {stored} stored, {skipped} skipped")

        result = _search_page(page_num=page_num, search_content=search_content)
        if not result:
            log.warning(f"  Failed to fetch page {page_num}, stopping")
            break

        rows = result.get("rows", [])
        if not rows:
            log.info(f"  No more results on page {page_num}, stopping")
            break

        time.sleep(REQUEST_DELAY)

    conn.commit()
    log.info(f"Done: {stored} laws stored, {skipped} already existed (of {total} total)")
    return stored


def main():
    parser = argparse.ArgumentParser(description="National Laws Database Crawler")
    parser.add_argument("--stats", action="store_true", help="Show database stats")
    parser.add_argument("--list-only", action="store_true",
                        help="List laws without fetching body text")
    parser.add_argument("--limit", type=int, default=0,
                        help="Max number of laws to store (0=all)")
    parser.add_argument("--search", type=str, default="",
                        help="Search term to filter laws")
    parser.add_argument("--db", type=str,
                        help="Path to SQLite database (default: documents.db)")
    args = parser.parse_args()

    conn = init_db(Path(args.db) if args.db else None)

    if args.stats:
        show_stats(conn)
        conn.close()
        return

    crawl(conn, search_content=args.search, limit=args.limit,
          fetch_bodies=not args.list_only)
    show_stats(conn)
    conn.close()


if __name__ == "__main__":
    main()
