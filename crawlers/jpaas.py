"""
Generic jpaas (jpage) crawler — multi-site.

Many Chinese gov portals run the jpaas CMS whose listings page via
`/module/web/jpage/dataproxy.jsp?...&columnid=C&unitid=U&webid=W`. Unlike a
hardcoded per-site crawler, this one AUTO-DISCOVERS a site's config the way
crawlers.gkmlpt.discover_site does for Guangdong:

  homepage -> /col/colN/ links (+ anchor text) -> pick the policy-document columns
  -> fetch one column page -> the embedded dataproxy.jsp call carries unitid+webid.

So adding a jpaas site is just a SITES entry (base_url); everything else discovers.
Confirmed jpaas: Jiangsu (provincial + depts), Shandong, and likely more provinces
(see docs/working/coverage-tracker.md). Parsing/body extraction is reused from
crawlers.jiangsu (same jpaas HTML).

Usage:
    python -m crawlers.jpaas --list-sites
    python -m crawlers.jpaas --site js_czt          # Jiangsu Finance Dept
    python -m crawlers.jpaas --site js_czt --discover-only   # show discovered config
"""
import argparse
import re
import time
from urllib.parse import urljoin

from crawlers.base import (
    REQUEST_DELAY, fetch, init_db, log, next_id, save_raw_html,
    show_stats, store_document, store_site,
)
# Reuse the jpaas HTML parsing already written for Jiangsu (same CMS format).
from crawlers.jiangsu import (
    _parse_listing, _extract_meta, _extract_body, _parse_date, _extract_doc_number,
)

BROWSER_UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")
PAGE_SIZE = 20

# Columns whose anchor text marks them as policy-document listings.
POLICY_KW = ("政策文件", "规范性文件", "政府文件", "办公厅文件", "规章", "政策解读",
             "通知公告", "政府信息公开", "法规", "政策法规", "文件", "公报")

SITES = {
    # Jiangsu provincial departments (jpaas; provincial portal handled by crawlers.jiangsu)
    "js_czt": {"name": "Jiangsu Finance Dept (江苏财政厅)", "base_url": "https://czt.jiangsu.gov.cn", "admin_level": "provincial"},
    "js_fzggw": {"name": "Jiangsu DRC (江苏发改委)", "base_url": "https://fzggw.jiangsu.gov.cn", "admin_level": "provincial"},
    "js_gxt": {"name": "Jiangsu Industry & IT (江苏工信厅)", "base_url": "https://gxt.jiangsu.gov.cn", "admin_level": "provincial"},
    "js_jtyst": {"name": "Jiangsu Transport (江苏交通厅)", "base_url": "https://jtyst.jiangsu.gov.cn", "admin_level": "provincial"},
    # Shandong provincial portal (jpaas)
    "shandong": {"name": "Shandong Province (山东省)", "base_url": "http://www.shandong.gov.cn", "admin_level": "provincial"},  # https fails SSL handshake; http works
    # NOTE: 国家医保局 (nhsa) and 广电总局 (nrta) look jpaas (their homepages show /col/
    # links) but paginate via ENCRYPTED-param dataproxy and embed the listing as a TRS
    # <recordset>; they are crawled by crawlers.trs, not here.
}


def _get(url, referer=None):
    return fetch(url, headers={"User-Agent": BROWSER_UA, "Referer": referer or url})


def discover(base_url: str) -> dict:
    """Auto-discover a jpaas site's (unitid, webid, policy columns).

    Returns {"unitid","webid","columns":[(col_id,name),...]} or raises.
    """
    home = _get(base_url)
    col_ids = list(dict.fromkeys(re.findall(r"/col/col(\d+)/", home)))
    if not col_ids:
        raise RuntimeError("no /col/ columns on homepage")

    unitid = webid = None
    cols = []
    for cid in col_ids[:40]:
        try:
            cp = _get(urljoin(base_url, f"/col/col{cid}/index.html"), referer=base_url)
        except Exception:
            continue
        if not unitid:  # unitid/webid are per-site; grab once from a dataproxy call
            m = re.search(r"webid=(\d+)[^\"']*?unitid=(\d+)", cp)
            if m:
                webid, unitid = m.group(1), m.group(2)
        nm = re.search(r'<meta\s+name="ColumnName"\s+content="([^"]*)"', cp, re.I)
        name = (nm.group(1).strip() if nm else "")
        if name and any(kw in name for kw in POLICY_KW):
            cols.append((cid, name))
    if not unitid:
        raise RuntimeError("could not extract unitid/webid from column pages")
    if not cols:
        raise RuntimeError("no policy columns identified by ColumnName")
    return {"unitid": unitid, "webid": webid, "columns": cols}


def _jpage_url(base_url, col_id, unitid, webid, page):
    start = page * PAGE_SIZE + 1
    return (f"{base_url}/module/web/jpage/dataproxy.jsp?startrecord={start}"
            f"&endrecord={(page + 1) * PAGE_SIZE}&perpage={PAGE_SIZE}"
            f"&columnid={col_id}&unitid={unitid}&webid={webid}")


def crawl_site(conn, site_key, cfg, fetch_bodies=True, max_empty=2):
    base = cfg["base_url"].rstrip("/")
    store_site(conn, site_key, cfg)
    info = discover(base)
    log.info(f"[{site_key}] discovered unitid={info['unitid']} webid={info['webid']} "
             f"{len(info['columns'])} policy columns")
    stored = 0
    for col_id, col_name in info["columns"]:
        log.info(f"  column {col_id} ({col_name})")
        empty = 0
        for page in range(0, 200):
            url = (f"{base}/col/col{col_id}/index.html" if page == 0
                   else _jpage_url(base, col_id, info["unitid"], info["webid"], page))
            try:
                html = _get(url, referer=base)
            except Exception as e:
                log.warning(f"    page {page}: {e}"); break
            items = _parse_listing(html, base)
            new = 0
            for it in items:
                if conn.execute("SELECT 1 FROM documents WHERE url=? AND url != ''", (it["url"],)).fetchone():
                    continue
                new += 1
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
                    "document_number": meta.get("document_number") or _extract_doc_number(it["title"]),
                    "publisher": meta.get("publisher", ""),
                    "date_published": it.get("date_str", ""),
                    "date_written": _parse_date(meta.get("date_written_str", "")),
                    "body_text_cn": body, "url": it["url"],
                    "classify_theme_name": meta.get("classify_theme_name", ""),
                    "classify_main_name": col_name, "raw_html_path": raw,
                })
                stored += 1
            if new == 0:
                empty += 1
                if empty >= max_empty:
                    break
            else:
                empty = 0
            conn.commit()
            time.sleep(REQUEST_DELAY)
    log.info(f"[{site_key}] done: {stored} new docs")
    return stored


def main():
    ap = argparse.ArgumentParser(description="Generic jpaas (jpage) multi-site crawler")
    ap.add_argument("--site", help="site key from SITES")
    ap.add_argument("--list-sites", action="store_true")
    ap.add_argument("--discover-only", action="store_true", help="show discovered config, don't crawl")
    ap.add_argument("--list-only", action="store_true", help="crawl metadata, skip bodies")
    ap.add_argument("--db")
    args = ap.parse_args()

    if args.list_sites:
        for k, c in SITES.items():
            print(f"  {k:14} {c['name']}  {c['base_url']}")
        return
    if not args.site or args.site not in SITES:
        print("Specify --site KEY (see --list-sites)"); return

    if args.discover_only:
        import json
        print(json.dumps(discover(SITES[args.site]["base_url"].rstrip("/")), ensure_ascii=False, indent=2))
        return

    conn = init_db(args.db) if args.db else init_db()
    crawl_site(conn, args.site, SITES[args.site], fetch_bodies=not args.list_only)
    show_stats(conn)
    conn.close()


if __name__ == "__main__":
    main()
