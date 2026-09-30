"""
Central-ministry MIRROR crawler (via the State Council policy-document library).

Four central ministries' OWN websites are blackholed from the New York droplet
(datacenter-IP / geo blocks): 住房和城乡建设部 (MOHURD), 民政部 (MCA),
自然资源部 (MNR), 国家卫生健康委 (NHC). Their documents are, however, mirrored
in the reachable State Council 政策文件库 (policy document library), which exposes
a JSON search API that works FROM THE DROPLET (NYC).

This is "Fix 3" of docs/research/access-vantage-brief.md.

Route
-----
Reuses the same endpoint gov.py's `crawl_library` uses:
    https://sousuo.www.gov.cn/search-gov/data
      ?t=zhengcelibrary_bm   (部门文件 — central-ministry docs)
      &bmfl=<发文机关>        (department filter — the key added here)
      &p=<page>&n=<size>&sortType=1  (newest-first)
The `bmfl` facet returned by the API is gov.cn's own issuing-agency
classification; filtering on it yields the ministry's OWN (incl. co-issued)
documents rather than mere mentions. Each item's `url` is a normal gov.cn
content page whose body/metadata are parsed by gov.py's extractors (reused
here — no body-extraction logic is reinvented).

Each ministry is stored under its own site_key (mohurd/mca/mnr/nhc) so /browse
and coverage attribute the docs to the ministry. Dedup is by URL: a doc already
held with body text (e.g. it drifted through the rolling gov feed, or another
ministry co-issued it and crawled it first) is skipped.

Usage:
    python -m crawlers.govmirror --list-sites
    python -m crawlers.govmirror                 # all 4 ministries, 2023+ (bounded)
    python -m crawlers.govmirror --site mohurd   # one ministry
    python -m crawlers.govmirror --since-year 2020 --deep   # deeper backfill
    python -m crawlers.govmirror --stats
"""

import argparse
import re
import time
import urllib.parse
import urllib.request

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
from crawlers.gov import (
    _extract_body,
    _extract_metadata_table,
    _extract_meta,
    _extract_source,
    _extract_title,
    _ms_to_date,
)

SEARCH_API = "https://sousuo.www.gov.cn/search-gov/data"
CATEGORY_T = "zhengcelibrary_bm"  # 部门文件 — central ministry documents

# site_key -> {name, bmfl (exact 发文机关 string as it appears in the API facet)}
MINISTRIES = {
    "mohurd": {"name": "住房和城乡建设部 (MOHURD)", "bmfl": "住房和城乡建设部"},
    "mca":    {"name": "民政部 (MCA)",              "bmfl": "民政部"},
    "mnr":    {"name": "自然资源部 (MNR)",          "bmfl": "自然资源部"},
    "nhc":    {"name": "国家卫生健康委 (NHC)",       "bmfl": "国家卫生健康委"},
}

BASE_URL = "https://www.gov.cn"
_UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")


def _search_page(bmfl: str, page: int, n: int = 50) -> dict | None:
    """Fetch one page of the policy-library search API filtered by 发文机关."""
    params = {
        "t": CATEGORY_T, "q": "", "timetype": "timezd", "mintime": "", "maxtime": "",
        "sort": "", "sortType": "1", "searchfield": "", "pcodeJiguan": "", "childtype": "",
        "subchildtype": "", "tsbq": "", "pubtimeyear": "", "pubtimeqarter": "",
        "pcodeYear": "", "pcodeNum": "", "filetype": "", "p": str(page), "n": str(n),
        "inpro": "", "bmfl": bmfl, "dup": "", "orpro": "",
    }
    url = SEARCH_API + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={
        "User-Agent": _UA,
        "Referer": "https://sousuo.www.gov.cn/zcwjk/policyDocumentLibrary",
        "Accept": "application/json, text/plain, */*",
    })
    import json as _json
    for attempt in range(3):
        try:
            raw = urllib.request.urlopen(req, timeout=45).read().decode("utf-8", "replace")
            return _json.loads(raw)
        except Exception as e:  # noqa: BLE001
            if attempt < 2:
                time.sleep(3 * (attempt + 1))
            else:
                log.warning(f"  search page {page} (bmfl={bmfl}) failed: {e}")
                return None


def _year_of(ms) -> int:
    d = _ms_to_date(ms)  # 'YYYY-MM-DD' or ''
    try:
        return int(d[:4])
    except (ValueError, IndexError):
        return 0


def crawl_ministry(conn, site_key: str, since_year: int = 2023, n: int = 50,
                   deep: bool = False, limit: int = 0, fetch_bodies: bool = True) -> int:
    """Crawl one ministry's docs from the policy library, newest-first.

    Stops when items predate `since_year` (unless `deep`), or after `limit`
    stored docs, or after 2 consecutive all-held pages (incremental catch-up).
    """
    cfg = MINISTRIES[site_key]
    bmfl = cfg["bmfl"]
    store_site(conn, site_key, {
        "name": cfg["name"], "base_url": BASE_URL, "admin_level": "central",
    })

    first = _search_page(bmfl, 1, n)
    if not first or "searchVO" not in first:
        log.warning(f"[{site_key}] no data, skipping")
        return 0
    sv = first["searchVO"]
    total, total_pages = sv.get("totalCount", 0), sv.get("totalpage", 0)
    log.info(f"[{site_key}={bmfl}] {total} docs / {total_pages} pages "
             f"(since {since_year if not deep else 'ALL'}, n={n})")

    stored = 0
    bodies = 0
    consecutive_all_seen = 0
    for p in range(1, total_pages + 1):
        page = first if p == 1 else _search_page(bmfl, p, n)
        items = (page or {}).get("searchVO", {}).get("listVO") or []
        if not items:
            break

        new_on_page = 0
        hit_old = False
        for it in items:
            url = it.get("url", "")
            if not url:
                continue
            yr = _year_of(it.get("pubtime"))
            if not deep and yr and yr < since_year:
                hit_old = True
                continue  # newest-first, but keep scanning the page for stragglers

            existing = conn.execute(
                "SELECT id, body_text_cn FROM documents WHERE url = ? AND url != ''", (url,)
            ).fetchone()
            if existing and existing[1]:
                continue  # already held with body
            new_on_page += 1

            doc_id = existing[0] if existing else next_id(conn)
            pcode = (it.get("pcode") or it.get("wenhao") or it.get("fwzh") or "").strip()
            title = re.sub(r"<[^>]+>", "", it.get("title", "")).strip()
            publisher = it.get("puborg", "") or bmfl
            date_published = _ms_to_date(it.get("pubtime"))

            body_text, raw_html_path, doc_number = "", "", pcode
            classify_theme, identifier = "", ""
            if fetch_bodies:
                try:
                    doc_html = fetch(url)
                    table_info = _extract_metadata_table(doc_html)
                    doc_number = table_info.get("document_number", "") or pcode
                    publisher = table_info.get("publisher", "") or publisher
                    identifier = table_info.get("identifier", "")
                    classify_theme = table_info.get("classify_theme_name", "")
                    if table_info.get("title"):
                        title = table_info["title"]
                    elif not title or len(title) < 5:
                        title = _extract_title(doc_html) or title
                    if not publisher:
                        publisher = _extract_source(doc_html)
                    body_text = _extract_body(doc_html)
                    if body_text:
                        bodies += 1
                    if doc_html:
                        raw_html_path = save_raw_html(site_key, doc_id, doc_html)
                except Exception as e:  # noqa: BLE001
                    log.warning(f"  body fetch failed {url}: {e}")
                time.sleep(REQUEST_DELAY)

            store_document(conn, site_key, {
                "id": doc_id,
                "title": title,
                "document_number": doc_number,
                "identifier": identifier,
                "publisher": publisher,
                "date_published": date_published,
                "body_text_cn": body_text,
                "url": url,
                "classify_theme_name": classify_theme,
                "classify_main_name": "政策文件",
                "raw_html_path": raw_html_path,
            })
            stored += 1
            if limit and stored >= limit:
                conn.commit()
                log.info(f"[{site_key}] hit limit {limit} ({stored} stored, {bodies} bodies)")
                return stored

        if p % 5 == 0:
            conn.commit()
            log.info(f"  [{site_key}] page {p}/{total_pages}: {stored} stored, {bodies} bodies")

        # early exits
        if not deep and hit_old and new_on_page == 0:
            log.info(f"  [{site_key}] reached pre-{since_year} docs — stopping")
            break
        if new_on_page == 0:
            consecutive_all_seen += 1
            if consecutive_all_seen >= 2:
                log.info(f"  [{site_key}] 2 consecutive all-held pages — stopping (incremental)")
                break
        else:
            consecutive_all_seen = 0
        time.sleep(REQUEST_DELAY)

    conn.commit()
    log.info(f"=== [{site_key}] {stored} stored, {bodies} bodies ===")
    return stored


def main():
    ap = argparse.ArgumentParser(description="Central-ministry mirror crawler (gov.cn policy library)")
    ap.add_argument("--site", help="One ministry site_key: " + ", ".join(MINISTRIES))
    ap.add_argument("--since-year", type=int, default=2023,
                    help="Only crawl docs published in/after this year (default 2023)")
    ap.add_argument("--deep", action="store_true", help="Walk all pages (full history)")
    ap.add_argument("--limit", type=int, default=0, help="Stop after N stored docs PER ministry")
    ap.add_argument("--list-only", action="store_true", help="Store metadata only, no body fetch")
    ap.add_argument("--list-sites", action="store_true", help="List ministries and exit")
    ap.add_argument("--stats", action="store_true", help="Show DB stats and exit")
    ap.add_argument("--db", type=str, help="Path to SQLite DB (default documents.db)")
    args = ap.parse_args()

    if args.list_sites:
        for k, v in MINISTRIES.items():
            print(f"  {k:8s} {v['name']}  (bmfl={v['bmfl']})")
        return

    conn = init_db(args.db) if args.db else init_db()
    if args.stats:
        show_stats(conn)
        conn.close()
        return

    sites = [args.site] if args.site else list(MINISTRIES)
    total = 0
    for sk in sites:
        if sk not in MINISTRIES:
            log.warning(f"unknown site '{sk}', skipping")
            continue
        total += crawl_ministry(
            conn, sk, since_year=args.since_year, deep=args.deep,
            limit=args.limit, fetch_bodies=not args.list_only,
        )
    log.info(f"=== govmirror total: {total} documents stored ===")
    conn.close()


if __name__ == "__main__":
    main()
