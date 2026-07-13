"""
State Council (国务院) crawler.

Crawls policy documents from www.gov.cn. Uses the static JSON feed at
/zhengce/zuixin/ZUIXINZHENGCE.json as the primary listing source, then
fetches individual document pages for body text and structured metadata.

Two document templates exist:
  - Template A: /zhengce/content/YYYYMM/content_NNN.htm (formal State Council docs)
    Has structured metadata table with 发文字号, 发文机关, 主题分类, etc.
  - Template B: /zhengce/YYYYMM/content_NNN.htm (general policy articles)
    Has h1#ti title, div.pages-date, but no metadata table.
  Both share #UCAP-CONTENT for body text and <meta> tags in <head>.

Usage:
    python -m crawlers.gov                  # Crawl all documents from JSON feed
    python -m crawlers.gov --stats          # Show database stats
    python -m crawlers.gov --list-only      # List document URLs without fetching bodies
"""

import argparse
import json
import re
import time
import urllib.parse
import urllib.request
from datetime import datetime

from crawlers.base import (
    REQUEST_DELAY,
    fetch,
    fetch_json,
    init_db,
    log,
    next_id,
    save_raw_html,
    show_stats,
    store_document,
    store_site,
)

SITE_KEY = "gov"
SITE_CFG = {
    "name": "State Council",
    "base_url": "https://www.gov.cn",
    "admin_level": "central",
}

# The "latest policies" rolling feed — recent docs only, NO history.
JSON_FEED_URL = "https://www.gov.cn/zhengce/zuixin/ZUIXINZHENGCE.json"

# ---------------------------------------------------------------------------
# Historical archive: the State Council Policy Document Library (政策文件库).
# The rolling JSON feed above only covers recent docs, so old 国发/国办/国函
# documents (cited thousands of times but aged out of the feed) were never
# captured. This paginated search API is the full archive.
#
# API (reverse-engineered from the zcwjk SPA's app.js, 2026-07):
#   https://sousuo.www.gov.cn/search-gov/data?t=<category>&p=<page>&n=<size>&...
# Each category `t` returns searchVO.listVO[] with title / url / pcode (文号) /
# puborg / pubtime, plus searchVO.totalCount + totalpage. The `url` is a normal
# gov.cn content page the body/metadata extractors below already parse, and
# `pcode` gives the 文号 up front (so citations resolve even before body fetch).
# ---------------------------------------------------------------------------
LIBRARY_API = "https://sousuo.www.gov.cn/search-gov/data"
LIBRARY_CATEGORIES = {
    "gw": "zhengcelibrary_gw",   # 国务院公文 — State Council formal docs (~6.2k)
    "bm": "zhengcelibrary_bm",   # 部门文件 — central ministry docs (~12.7k)
}


def _library_page(category_t: str, page: int, n: int = 50) -> dict | None:
    """Fetch one page of the policy-document-library search API."""
    params = {
        "t": category_t, "q": "", "timetype": "timezd", "mintime": "", "maxtime": "",
        "sort": "", "sortType": "1", "searchfield": "", "pcodeJiguan": "", "childtype": "",
        "subchildtype": "", "tsbq": "", "pubtimeyear": "", "pubtimeqarter": "",
        "pcodeYear": "", "pcodeNum": "", "filetype": "", "p": str(page), "n": str(n),
        "inpro": "", "bmfl": "", "dup": "", "orpro": "",
    }
    url = LIBRARY_API + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={
        "User-Agent": ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
                       "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"),
        "Referer": "https://sousuo.www.gov.cn/zcwjk/policyDocumentLibrary",
        "Accept": "application/json, text/plain, */*",
    })
    for attempt in range(3):
        try:
            raw = urllib.request.urlopen(req, timeout=45).read().decode("utf-8", "replace")
            return json.loads(raw)
        except Exception as e:
            if attempt < 2:
                time.sleep(3 * (attempt + 1))
            else:
                log.warning(f"  library page {page} ({category_t}) failed: {e}")
                return None


def _ms_to_date(ms) -> str:
    """Convert a millisecond epoch (pubtime/ptime) to 'YYYY-MM-DD'."""
    try:
        return datetime.fromtimestamp(int(ms) / 1000).strftime("%Y-%m-%d")
    except (ValueError, TypeError, OSError):
        return ""


def crawl_library(conn, categories=("gw",), n: int = 50, deep: bool = False,
                  limit: int = 0, fetch_bodies: bool = True):
    """Crawl the historical policy-document library (archival backfill).

    Sorted newest-first. `deep=True` walks every page (initial full backfill);
    otherwise it stops after 2 consecutive pages of already-held docs (cheap
    incremental catch-up). `pcode` (文号) is stored as document_number up front,
    so citations resolve even when a body fetch fails.
    """
    store_site(conn, SITE_KEY, SITE_CFG)
    total_stored = 0

    for cat in categories:
        cat_t = LIBRARY_CATEGORIES.get(cat, cat)
        first = _library_page(cat_t, 1, n)
        if not first or "searchVO" not in first:
            log.warning(f"Library [{cat}]: no data, skipping")
            continue
        sv = first["searchVO"]
        total, total_pages = sv.get("totalCount", 0), sv.get("totalpage", 0)
        log.info(f"Library [{cat}={cat_t}]: {total} docs across {total_pages} pages (n={n})")

        consecutive_all_seen = 0
        for p in range(1, total_pages + 1):
            page = first if p == 1 else _library_page(cat_t, p, n)
            items = (page or {}).get("searchVO", {}).get("listVO") or []
            if not items:
                log.info(f"  page {p}: empty — stopping")
                break

            new_on_page = 0
            for it in items:
                url = it.get("url", "")
                if not url:
                    continue
                existing = conn.execute(
                    "SELECT id, body_text_cn FROM documents WHERE url = ?", (url,)
                ).fetchone()
                if existing and existing[1]:
                    continue  # already have body — skip
                new_on_page += 1

                doc_id = existing[0] if existing else next_id(conn)
                pcode = (it.get("pcode") or it.get("wenhao") or it.get("fwzh") or "").strip()
                title = re.sub(r"<[^>]+>", "", it.get("title", "")).strip()
                publisher = it.get("puborg", "")
                date_published = _ms_to_date(it.get("pubtime"))

                body_text, raw_html_path = "", ""
                doc_number = pcode
                if fetch_bodies:
                    try:
                        doc_html = fetch(url)
                        table_info = _extract_metadata_table(doc_html)
                        doc_number = table_info.get("document_number", "") or pcode
                        publisher = table_info.get("publisher", "") or publisher
                        if table_info.get("title"):
                            title = table_info["title"]
                        body_text = _extract_body(doc_html)
                        if doc_html:
                            raw_html_path = save_raw_html(SITE_KEY, doc_id, doc_html)
                    except Exception as e:
                        log.warning(f"  body fetch failed {url}: {e}")
                    time.sleep(REQUEST_DELAY)

                store_document(conn, SITE_KEY, {
                    "id": doc_id,
                    "title": title,
                    "document_number": doc_number,
                    "publisher": publisher,
                    "date_published": date_published,
                    "body_text_cn": body_text,
                    "url": url,
                    "classify_main_name": "政策文件",
                    "raw_html_path": raw_html_path,
                })
                total_stored += 1
                if limit and total_stored >= limit:
                    conn.commit()
                    log.info(f"Library crawl: hit limit {limit} ({total_stored} stored)")
                    return total_stored

            if p % 10 == 0:
                conn.commit()
                log.info(f"  page {p}/{total_pages}: {total_stored} stored")

            # Incremental early-exit (skip during a deep full backfill)
            if not deep:
                if new_on_page == 0:
                    consecutive_all_seen += 1
                    if consecutive_all_seen >= 2:
                        log.info(f"  2 consecutive all-held pages — stopping (incremental)")
                        break
                else:
                    consecutive_all_seen = 0
            time.sleep(REQUEST_DELAY)

        conn.commit()

    log.info(f"=== Library crawl total: {total_stored} documents stored ===")
    return total_stored


def _extract_meta(html: str) -> dict:
    """Extract structured metadata from <meta> tags."""
    meta = {}
    for name in ("manuscriptId", "firstpublishedtime", "lastmodifiedtime",
                 "keywords", "description", "author", "lanmu", "catalog"):
        m = re.search(rf'<meta\s+name=["\']?{name}["\']?\s+content=["\']([^"\']*)["\']', html, re.IGNORECASE)
        if m:
            meta[name] = m.group(1).strip()
    return meta


def _extract_metadata_table(html: str) -> dict:
    """Extract structured fields from the metadata table (Template A only).

    Parses the table with 索引号, 发文机关, 发文字号, etc.
    """
    info = {}
    # Match table rows: <td><b>LABEL：</b></td><td>VALUE</td>
    for m in re.finditer(
        r'<td[^>]*><b>([^<]+)：?\s*</b></td>\s*<td[^>]*>(.*?)</td>',
        html, re.DOTALL,
    ):
        label = m.group(1).replace('\u3000', '').strip()
        value = re.sub(r'<[^>]+>', '', m.group(2)).strip()
        if label == '发文字号':
            info['document_number'] = value
        elif label == '发文机关':
            info['publisher'] = value
        elif label == '成文日期':
            info['date_written_str'] = value
        elif label == '发布日期':
            info['date_published_str'] = value
        elif label == '主题分类':
            info['classify_theme_name'] = value
        elif label in ('标题', '标\u3000\u3000题'):
            info['title'] = value
        elif label == '索引号' or '索' in label:
            info['identifier'] = value
    return info


def _extract_title(html: str) -> str:
    """Extract title from h1#ti or <title> tag."""
    # Template B: <h1 id="ti">
    m = re.search(r'<h1[^>]*id=["\']ti["\'][^>]*>(.*?)</h1>', html, re.DOTALL)
    if m:
        return re.sub(r'<[^>]+>', '', m.group(1)).strip()
    # Fallback: <title>
    m = re.search(r'<title>(.*?)</title>', html)
    if m:
        title = m.group(1).strip()
        # Remove suffix like "_水利_中国政府网"
        title = re.sub(r'_[^_]+_中国政府网$', '', title)
        return title
    return ""


def _extract_source(html: str) -> str:
    """Extract source from Template B's div.pages-date > span.font."""
    m = re.search(r'<span\s+class="font[^"]*">来源：([^<]+)</span>', html)
    if m:
        return m.group(1).strip()
    return ""


def _extract_body(html: str) -> str:
    """Extract body text from #UCAP-CONTENT."""
    m = re.search(r'id=["\']UCAP-CONTENT["\'][^>]*>(.*?)</div>\s*(?:</div>|</table>)',
                  html, re.DOTALL)
    if not m:
        return ""
    content = m.group(1)
    # Replace <br> and <p> boundaries with newlines
    content = re.sub(r'<br\s*/?\s*>', '\n', content)
    content = re.sub(r'</p>', '\n', content)
    # Strip HTML tags
    text = re.sub(r'<[^>]+>', '', content)
    # Clean whitespace
    text = re.sub(r'[ \t]+', ' ', text)
    text = re.sub(r'\n\s*\n', '\n', text)
    text = text.strip()
    # Unescape HTML entities
    text = text.replace("&nbsp;", " ").replace("&lt;", "<")
    text = text.replace("&gt;", ">").replace("&amp;", "&")
    if len(text) > 20:
        return text
    return ""


def fetch_document_list() -> list[dict]:
    """Fetch the JSON feed and return document entries."""
    log.info(f"Fetching document list from {JSON_FEED_URL}")
    data = fetch_json(JSON_FEED_URL)
    log.info(f"  Found {len(data)} documents in JSON feed")
    return data


def crawl_all(conn, fetch_bodies: bool = True):
    """Crawl all documents from the JSON feed."""
    store_site(conn, SITE_KEY, SITE_CFG)

    entries = fetch_document_list()
    stored = 0
    bodies = 0

    for entry in entries:
        doc_url = entry.get("URL", "")
        title = entry.get("TITLE", "")
        date_published = entry.get("DOCRELPUBTIME", "")

        if not doc_url or not title:
            continue

        # Check if already stored with body text
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
        publisher = ""
        identifier = ""
        classify_theme = ""
        keywords = ""

        if fetch_bodies:
            try:
                doc_html = fetch(doc_url)

                # Extract from <meta> tags
                meta = _extract_meta(doc_html)
                keywords = meta.get("keywords", "")
                if meta.get("firstpublishedtime"):
                    date_published = meta["firstpublishedtime"].replace("-", "-")

                # Try Template A metadata table
                table_info = _extract_metadata_table(doc_html)
                doc_number = table_info.get("document_number", "")
                publisher = table_info.get("publisher", "")
                identifier = table_info.get("identifier", "")
                classify_theme = table_info.get("classify_theme_name", "")
                if table_info.get("title"):
                    title = table_info["title"]

                # Template B fallback for publisher
                if not publisher:
                    publisher = _extract_source(doc_html)

                # Title fallback
                if not title or len(title) < 5:
                    extracted_title = _extract_title(doc_html)
                    if extracted_title:
                        title = extracted_title

                # Body text
                body_text = _extract_body(doc_html)

                if doc_html:
                    raw_html_path = save_raw_html(SITE_KEY, doc_id, doc_html)
                    bodies += 1
            except Exception as e:
                log.warning(f"  Failed to fetch {doc_url}: {e}")
            time.sleep(REQUEST_DELAY)

        store_document(conn, SITE_KEY, {
            "id": doc_id,
            "title": title,
            "document_number": doc_number,
            "identifier": identifier,
            "publisher": publisher,
            "keywords": keywords,
            "date_published": date_published,
            "body_text_cn": body_text,
            "url": doc_url,
            "classify_theme_name": classify_theme,
            "classify_main_name": "政策文件",
            "raw_html_path": raw_html_path,
        })
        stored += 1

        if stored % 20 == 0:
            conn.commit()
            log.info(f"  Progress: {stored}/{len(entries)} stored, {bodies} bodies")

    conn.commit()
    log.info(f"=== State Council total: {stored} documents, {bodies} bodies ===")


def main():
    parser = argparse.ArgumentParser(description="State Council Policy Crawler")
    parser.add_argument("--stats", action="store_true", help="Show database stats")
    parser.add_argument("--list-only", action="store_true",
                        help="List document URLs without fetching bodies")
    parser.add_argument("--library", action="store_true",
                        help="Crawl the historical policy-document library (archival backfill) "
                             "instead of the rolling 'latest' feed")
    parser.add_argument("--categories", default="gw",
                        help="Comma-separated library categories: gw (国务院公文), bm (部门文件). "
                             "Default: gw")
    parser.add_argument("--deep", action="store_true",
                        help="With --library: walk EVERY page (full backfill). Without it, the "
                             "library crawl stops after 2 all-held pages (incremental).")
    parser.add_argument("--limit", type=int, default=0,
                        help="With --library: stop after N stored docs (0 = no cap)")
    parser.add_argument("--db", type=str, help="Path to SQLite database (default: documents.db)")
    args = parser.parse_args()

    conn = init_db(args.db) if args.db else init_db()

    if args.stats:
        show_stats(conn)
        conn.close()
        return

    if args.library:
        cats = [c.strip() for c in args.categories.split(",") if c.strip()]
        crawl_library(conn, categories=cats, deep=args.deep, limit=args.limit,
                      fetch_bodies=not args.list_only)
    else:
        crawl_all(conn, fetch_bodies=not args.list_only)
    show_stats(conn)
    conn.close()


if __name__ == "__main__":
    main()
