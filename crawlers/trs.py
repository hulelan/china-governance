"""
Generic TRS WCM crawler — multi-site.

Many central .gov.cn portals run TRS WCM, whose column pages embed the article
list directly in `/col/colN/index.html` as a `<recordset>` of `<record>` CDATA
blocks (each carrying the /art/ link, title, 文号, and 发布日期). This is a
DIFFERENT dialect from crawlers.jpaas: jpaas paginates via a plain-ID
`dataproxy.jsp?columnid=104&unitid=6` call, whereas these TRS sites paginate via
a `<nextgroup>` dataproxy URL with ENCRYPTED columnid/unitid blobs. That's why
the jpaas crawler discovers the columns but lists 0 docs on these sites.

We reuse:
  - crawlers.jpaas.discover      -> finds policy columns (same /col/ homepage)
  - crawlers.jiangsu._extract_*  -> body/meta extraction from /art/ pages

Confirmed TRS-recordset sites: 国家医保局 (nhsa), 广电总局 (nrta). Many of the
"col-based" central/city portals in docs/working/coverage.csv share this format
(see coverage-tracker.md).

Coverage note: page 0 of each column carries ~45 recent records. Deep pagination
via the encrypted <nextgroup> URL is unreliable (often returns an empty 54-byte
body), so --deep is best-effort; the default single-page pass captures the recent
policy window, which is the highest-value slice.

Usage:
    python -m crawlers.trs --list-sites
    python -m crawlers.trs --site nhsa
    python -m crawlers.trs --site nhsa --discover-only
    python -m crawlers.trs --site nhsa --deep      # attempt nextgroup pagination
"""
import argparse
import html as H
import re
import time
from urllib.parse import urljoin

from crawlers.base import (
    REQUEST_DELAY, fetch, init_db, log, next_id, save_raw_html,
    show_stats, store_document, store_site,
)
from crawlers.jiangsu import _extract_meta, _extract_body, _parse_date, _extract_doc_number
from crawlers.jpaas import discover, _get

SITES = {
    "nhsa": {"name": "National Healthcare Security Admin (国家医保局)", "base_url": "https://www.nhsa.gov.cn", "admin_level": "central"},
    "nrta": {"name": "Radio & Television Admin (广电总局)", "base_url": "https://www.nrta.gov.cn", "admin_level": "central"},
}

_REC_RE = re.compile(r"<record><!\[CDATA\[(.*?)\]\]></record>", re.S)
_A_RE = re.compile(r'<a\s+href="([^"]+)"[^>]*title="([^"]*)"')
_SPAN_RE = re.compile(r"<span[^>]*>(.*?)</span>", re.S)
_DATE_RE = re.compile(r"(\d{4}-\d{2}-\d{2})(?!\d)")      # exclude 索引号 like 2026-02-00018
_IDXNO_RE = re.compile(r"\d{4}-\d{2}-\d{5}")
_NEXT_RE = re.compile(r'<nextgroup><!\[CDATA\[.*?href="([^"]+dataproxy\.jsp[^"]+)"', re.S)


def _parse_records(page: str, base: str) -> list:
    """Extract (url, title, 文号, date) tuples from a TRS <recordset> page."""
    out = []
    for rec in _REC_RE.findall(page):
        a = _A_RE.search(rec)
        if not a:
            continue
        title = H.unescape(a.group(2)).strip()
        if not title:
            continue
        url = urljoin(base, H.unescape(a.group(1)))
        dates = _DATE_RE.findall(rec)          # 发布日期 is the last date span
        date = dates[-1] if dates else ""
        docnum = ""
        for sp in _SPAN_RE.findall(rec):
            t = re.sub(r"<[^>]+>", "", sp).strip()
            if ("〔" in t or t.endswith("号")) and not _IDXNO_RE.match(t):
                docnum = H.unescape(t)
                break
        out.append({"url": url, "title": title, "date_str": date, "docnum": docnum})
    return out


def _next_url(page: str, base: str, page_no: int) -> str | None:
    """Build the next page's dataproxy URL from the <nextgroup> block."""
    m = _NEXT_RE.search(page)
    if not m:
        return None
    return re.sub(r"page=\d+", f"page={page_no}", urljoin(base, H.unescape(m.group(1))))


def crawl_site(conn, site_key, cfg, fetch_bodies=True, deep=False, max_pages=40):
    base = cfg["base_url"].rstrip("/")
    store_site(conn, site_key, cfg)
    info = discover(base)
    log.info(f"[{site_key}] discovered {len(info['columns'])} policy columns")
    stored = 0
    for col_id, col_name in info["columns"]:
        log.info(f"  column {col_id} ({col_name})")
        url = f"{base}/col/col{col_id}/index.html"
        page_no = 0
        while url:
            try:
                page = _get(url, referer=base)
            except Exception as e:
                log.warning(f"    page {page_no}: {e}")
                break
            recs = _parse_records(page, base)
            if not recs:
                break
            all_held, new = True, 0
            for it in recs:
                if conn.execute("SELECT 1 FROM documents WHERE url=?", (it["url"],)).fetchone():
                    continue
                all_held, new = False, new + 1
                doc_id = next_id(conn)
                body, raw, meta = "", "", {}
                if fetch_bodies:
                    try:
                        dh = fetch(it["url"])
                        meta = _extract_meta(dh)
                        body = _extract_body(dh)
                        raw = save_raw_html(site_key, doc_id, dh)
                    except Exception as e:
                        log.warning(f"    body {it['url']}: {e}")
                    time.sleep(REQUEST_DELAY)
                store_document(conn, site_key, {
                    "id": doc_id, "title": it["title"],
                    "document_number": it["docnum"] or meta.get("document_number") or _extract_doc_number(it["title"]),
                    "publisher": meta.get("publisher", ""),
                    "date_published": it["date_str"],
                    "date_written": _parse_date(meta.get("date_written_str", "")),
                    "body_text_cn": body, "url": it["url"],
                    "classify_theme_name": meta.get("classify_theme_name", ""),
                    "classify_main_name": col_name, "raw_html_path": raw,
                })
                stored += 1
            conn.commit()
            # Default: page 0 only (recent window). --deep attempts nextgroup pagination.
            if not deep or page_no >= max_pages or all_held:
                break
            url = _next_url(page, base, page_no + 1)
            page_no += 1
            time.sleep(REQUEST_DELAY)
    log.info(f"[{site_key}] done: {stored} new docs")
    return stored


def main():
    ap = argparse.ArgumentParser(description="Generic TRS WCM (recordset) multi-site crawler")
    ap.add_argument("--site", help="site key from SITES")
    ap.add_argument("--list-sites", action="store_true")
    ap.add_argument("--discover-only", action="store_true")
    ap.add_argument("--list-only", action="store_true", help="crawl metadata, skip bodies")
    ap.add_argument("--deep", action="store_true", help="attempt <nextgroup> pagination past page 0")
    ap.add_argument("--db")
    args = ap.parse_args()

    if args.list_sites:
        for k, c in SITES.items():
            print(f"  {k:14} {c['name']}  {c['base_url']}")
        return
    if not args.site or args.site not in SITES:
        print("Specify --site KEY (see --list-sites)")
        return

    cfg = SITES[args.site]
    if args.discover_only:
        import json
        print(json.dumps(discover(cfg["base_url"].rstrip("/")), ensure_ascii=False, indent=2))
        return

    conn = init_db(args.db) if args.db else init_db()
    crawl_site(conn, args.site, cfg, fetch_bodies=not args.list_only, deep=args.deep)
    show_stats(conn)


if __name__ == "__main__":
    main()
