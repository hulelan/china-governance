"""
NFCMS JSON walker — Shenzhen Government Gazette (深圳市人民政府公报) + the other
Shenzhen-platform (NFCMS) sections that publish the same static JSON.

The gazette (www.sz.gov.cn/zfgb/, 1989–present) is the legal publication of
record for 市政府规章 and 市政府/市府办 规范性文件. It is a DIFFERENT section of
the same NFCMS platform the gkmlpt `sz` crawler reads (site 755001), so the
gkmlpt category feeds never list it: before this crawler the corpus held ~35
`/zfgb/` URLs, found incidentally via `gkmlpt --search`. The A6 queue audit
(docs/working/a6-recoverable-head.md) found 10/11 probed "missing" Shenzhen
instruments here — including two CLAUDE.md had recorded as delisted
(深圳市行政听证办法 2006, 深财规〔2023〕3号).

Dialect — the whole archive is walkable through the platform's static JSON:
  /postmeta/i/101619.json           root column → `children` = 39 year columns
  /postmeta/i/<year_col>.json       → `children` = issue columns (总第N期)
  /postmeta/i/<issue_col>.json      → `articles[]`: id, title, url, date,
                                      EXT_zh (文号), EXT_fwdw (issuer),
                                      EXT_sort (gazette section)
  /postmeta/p/<id//1e6>/<id//1e3>/<id>.json  → full post: `content` (HTML),
                                      `attachment`, `keywords`
So listing is 1 + 39 + ~1,450 requests (one per issue) and bodies are one JSON
GET per article (no HTML parsing). The `政策解读` pseudo-year column (101639)
is skipped — explainers, not instruments.

Other NFCMS sections (`NFCMS_SITES`, select with --site):
  * `szdp_gfxwj` — 大鹏新区 规范性文件库 (www.dpxq.gov.cn/ztzl/gfxwjk/, site
    755038, root column 150493). A flat column: the root JSON itself carries all
    ~42 `articles` (levels=0, no year/issue tiers) with `EXT_sx` (有效/无效)
    and `EXT_type` (政府规章/其他) — stored in `relation` as
    `status=<sx>;type=<type>` (prefixed `repealed;` when 无效, the token
    chongqing uses for its 废止失效 archive). The listing has NO 文号 field, so
    the 文号 is read from the body's promulgation line (深鹏办规〔2023〕9号) once
    the post is fetched. Docs land under the EXISTING gkmlpt site_key `szdp`
    (Dapeng district) so they join its district rows — the site row is only
    created if absent, never rewritten.

Gotchas:
  * HTTPS from Python urllib fails with `SSL BAD_ECPOINT` on the sz.gov.cn host;
    every request is forced to http:// (same for dpxq.gov.cn, for uniformity).
    URLs are STORED as published (https://…), which is how the 35 pre-existing
    rows are stored, and dedup compares both schemes.
  * Article ids are platform post ids (the same id space gkmlpt uses as
    documents.id). The pre-existing `/zfgb/` rows under `sz` were stored under
    DIFFERENT ids (search-backfill ids), so dedup is by URL first, then id.
    Existing rows are never overwritten.
  * Year column `pub_point`s are irregular (2012 → zfgb/2012_1, 1991 → zfgb/1901,
    1990 → zfgb/1900); --year filters on the column NAME, not the path.
  * One host, many requests: default delay is 1.0s (not REQUEST_DELAY=0.5).

Usage:
    python -m crawlers.sz_gazette --list-only                 # all years, metadata only
    python -m crawlers.sz_gazette --year 2006,2023 --list-only
    python -m crawlers.sz_gazette --year 2000-2010            # with bodies
    python -m crawlers.sz_gazette --backfill-bodies           # bodies for listed docs
    python -m crawlers.sz_gazette --db /path/scratch.db ...   # separate-DB workflow
    python -m crawlers.sz_gazette --site szdp_gfxwj --list-only   # Dapeng 规范性文件库
    python -m crawlers.sz_gazette --site szdp_gfxwj --backfill-bodies
"""

import argparse
import json
import re
import sqlite3
import time
from datetime import datetime, timezone
from pathlib import Path

from crawlers.base import (
    fetch,
    init_db,
    log,
    save_raw_html,
    show_stats,
    store_document,
    store_site,
)

DEFAULT_DELAY = 1.0
_UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")

# One entry per NFCMS section. `levels` = how many column tiers sit between the
# root and the article-bearing columns (gazette: root→year→issue = 2; a flat
# 文件库 whose root JSON lists the articles itself = 0). `own_site` = this
# crawler owns the `sites` row (store_site every run) vs. joins an existing
# site_key (row created only if missing). `url_filter` scopes --backfill-bodies
# to this section's posts when the site_key is shared with another crawler.
NFCMS_SITES = {
    "sz_gazette": {
        "site_key": "sz_gazette",
        "site_cfg": {
            "name": "Shenzhen Government Gazette (深圳市人民政府公报)",
            "base_url": "http://www.sz.gov.cn/zfgb",
            "admin_level": "municipal",
        },
        "own_site": True,
        "sid": "755001",
        "host": "http://www.sz.gov.cn",       # http only — see module docstring
        "referer": "https://www.sz.gov.cn/zfgb/",
        "root": 101619,                       # 政府公报
        "skip_columns": {101639},             # 政策解读 (explainers)
        "levels": 2,
        "classify_main_name": "政府公报",
        "label": "Shenzhen gazette",
        "docnum_from_body": False,
        "url_filter": "",
    },
    "szdp_gfxwj": {
        "site_key": "szdp",                   # EXISTING gkmlpt site (Dapeng New District)
        "site_cfg": {
            "name": "Dapeng New District",
            "base_url": "http://www.dpxq.gov.cn",
            "admin_level": "district",
        },
        "own_site": False,
        "sid": "755038",
        "host": "http://www.dpxq.gov.cn",
        "referer": "https://www.dpxq.gov.cn/ztzl/gfxwjk/",
        "root": 150493,                       # 规范性文件库
        "skip_columns": set(),
        "levels": 0,
        "classify_main_name": "规范性文件库",
        "label": "Dapeng 规范性文件库",
        "docnum_from_body": True,
        "url_filter": "/ztzl/gfxwjk/",
    },
}
DEFAULT_SITE = "sz_gazette"

# Back-compat module constants (the gazette values).
SITE_KEY = NFCMS_SITES[DEFAULT_SITE]["site_key"]
SITE_CFG = NFCMS_SITES[DEFAULT_SITE]["site_cfg"]
HOST = NFCMS_SITES[DEFAULT_SITE]["host"]
ROOT_COLUMN = NFCMS_SITES[DEFAULT_SITE]["root"]
SKIP_COLUMNS = NFCMS_SITES[DEFAULT_SITE]["skip_columns"]

# A document's OWN 文号 appears in one of two places near the top of its body:
#   (a) the promulgation line of a codified text:
#       （2023年12月26日深鹏办规〔2023〕9号公布 根据2025年…修订）
#   (b) a standalone 文号 line under the title of a notice: 深鹏办规〔2023〕9号
# Anything else (e.g. 根据《…若干措施》（深办发〔2018〕25号）) is a CITATION of
# another instrument, so the scan is line-anchored, not a free search.
_DOCNUM = r"[一-龥]{2,10}\s*[〔\[【（(]\s*\d{4}\s*[〕\]】）)]\s*第?\d{1,4}\s*号"
_DOCNUM_LINE_RE = re.compile(rf"^\s*({_DOCNUM})\s*$")
_PROMULGATION_RE = re.compile(
    rf"^\s*[（(]\s*\d{{4}}年\d{{1,2}}月\d{{1,2}}日\s*({_DOCNUM})\s*(公布|发布|印发|通过|公布施行)")


def _headers(cfg: dict) -> dict:
    return {"User-Agent": _UA, "Referer": cfg["referer"]}


# --- fetch helpers ---------------------------------------------------------

def _to_http(url: str) -> str:
    return re.sub(r"^https://", "http://", url or "")


def _get_json(path: str, cfg: dict, timeout: int = 30) -> dict | None:
    """GET a /postmeta/... JSON path over http; None on any failure."""
    url = cfg["host"] + path
    try:
        return json.loads(fetch(url, timeout=timeout, headers=_headers(cfg)))
    except Exception as e:
        log.warning(f"  JSON fetch failed {url}: {e}")
        return None


def column_json(col_id: int, cfg: dict) -> dict | None:
    return _get_json(f"/postmeta/i/{col_id}.json", cfg)


def post_json(post_id: int, cfg: dict) -> dict | None:
    return _get_json(f"/postmeta/p/{post_id // 1_000_000}/{post_id // 1_000}/{post_id}.json", cfg)


# --- parsing ---------------------------------------------------------------

def html_to_text(content: str) -> str:
    """Flatten the post `content` HTML to text (same cleanup as gkmlpt bodies)."""
    if not content:
        return ""
    content = re.sub(r"<style[^>]*>.*?</style>", " ", content, flags=re.DOTALL | re.IGNORECASE)
    content = re.sub(r"<script[^>]*>.*?</script>", " ", content, flags=re.DOTALL | re.IGNORECASE)
    content = re.sub(r"<br\s*/?>|</p>|</div>|</tr>", "\n", content, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", "", content)
    text = text.replace("&nbsp;", " ").replace("&lt;", "<").replace("&gt;", ">")
    text = text.replace("&amp;", "&").replace("&quot;", '"').replace("　", " ")
    text = re.sub(r"[ \t\r]+", " ", text)
    text = re.sub(r"\n\s*\n+", "\n", text).strip()
    return text if len(text) > 20 else ""


def docnum_from_body(body: str) -> str:
    """The document's own 文号 from the head of its body (first 12 lines): a
    promulgation line or a standalone 文号 line — never a cited 文号."""
    for line in (body or "").split("\n")[:12]:
        m = _PROMULGATION_RE.match(line) or _DOCNUM_LINE_RE.match(line)
        if m:
            return re.sub(r"\s+", "", m.group(1))
    return ""


def _year_of(column: dict) -> int | None:
    m = re.search(r"(\d{4})年", column.get("name") or "")
    return int(m.group(1)) if m else None


def parse_years(spec: str | None) -> set[int] | None:
    """'2006,2023' | '2000-2010' | mixed → set of years; None = all."""
    if not spec:
        return None
    years: set[int] = set()
    for part in spec.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            a, b = part.split("-", 1)
            years.update(range(int(a), int(b) + 1))
        else:
            years.add(int(part))
    return years


def status_relation(art: dict, ext: dict) -> str:
    """`relation` from the NFCMS validity fields (EXT_sx 有效/无效, EXT_type).
    Empty when the listing carries neither (the gazette)."""
    sx = (art.get("EXT_sx") or ext.get("EXT_sx") or "").strip()
    typ = (art.get("EXT_type") or ext.get("EXT_type") or "").strip()
    if not sx and not typ:
        return ""
    parts = []
    if sx == "无效":
        parts.append("repealed")
    if sx:
        parts.append(f"status={sx}")
    if typ:
        parts.append(f"type={typ}")
    return ";".join(parts)


def article_to_doc(art: dict, issue: dict, cfg: dict | None = None) -> dict:
    """Map one NFCMS listing article onto the documents schema."""
    cfg = cfg or NFCMS_SITES[DEFAULT_SITE]
    ext = {}
    try:
        ext = json.loads(art.get("json_ext") or "{}") or {}
    except Exception:
        ext = {}
    if isinstance(ext, list):
        ext = {}
    docnum = (art.get("EXT_zh") or ext.get("EXT_zh") or "").strip()
    issuer = (art.get("EXT_fwdw") or ext.get("EXT_fwdw") or art.get("source") or "").strip()
    section = (art.get("EXT_sort") or ext.get("EXT_sort") or
               art.get("EXT_type") or ext.get("EXT_type") or "").strip()
    title = re.sub(r"<[^>]+>", "", art.get("title") or "").replace("<br/>", " ").strip()
    return {
        "id": int(art["id"]),
        "title": title,
        "document_number": docnum,
        "publisher": issuer,
        "date_published": (art.get("date") or "").strip(),
        "display_publish_time": int(art.get("visible_publish_time") or 0),
        "abstract": (art.get("abstract") or "").strip(),
        "category_id": int(issue.get("id") or 0),
        "classify_main_name": cfg["classify_main_name"],
        "classify_genre_name": section,
        "keywords": issue.get("name", ""),   # e.g. 2006年第49期（总第519期）
        "url": (art.get("url") or "").strip(),
        "post_url": (art.get("url") or "").strip(),
        "relation": status_relation(art, ext),
    }


# --- storage ---------------------------------------------------------------

def _existing_id(conn, doc_id: int, url: str):
    """Return (existing_id, has_body) if this post is already held (by URL in
    either scheme — the partial index needs `url != ''` — or by id)."""
    http_u, https_u = _to_http(url), re.sub(r"^http://", "https://", url)
    row = conn.execute(
        "SELECT id, body_text_cn != '' FROM documents "
        "WHERE url IN (?, ?) AND url != '' LIMIT 1", (http_u, https_u)).fetchone()
    if row:
        return row
    return conn.execute(
        "SELECT id, body_text_cn != '' FROM documents WHERE id = ?", (doc_id,)).fetchone()


def _store_category(conn, col: dict, parent_id: int, site_key: str):
    conn.execute(
        "INSERT OR IGNORE INTO categories (id, site_key, name, parent_id, post_count) "
        "VALUES (?, ?, ?, ?, ?)",
        (int(col["id"]), site_key, (col.get("name") or "").strip(), parent_id,
         int(col.get("publish_count") or 0)))


def _ensure_site(conn, cfg: dict):
    """Own site → upsert every run; shared site_key → create only if absent
    (never rewrite another crawler's sid/tree_json)."""
    if cfg["own_site"] or not conn.execute(
            "SELECT 1 FROM sites WHERE site_key = ?", (cfg["site_key"],)).fetchone():
        store_site(conn, cfg["site_key"], cfg["site_cfg"], sid=cfg["sid"])


def fetch_body(post_id: int, cfg: dict | None = None) -> tuple[str, str, list]:
    """Fetch one post JSON → (body_text, content_html, attachments)."""
    p = post_json(post_id, cfg or NFCMS_SITES[DEFAULT_SITE])
    if not p:
        return "", "", []
    content = p.get("content") or ""
    att = p.get("attachment") or []
    return html_to_text(content), content, att if isinstance(att, list) else []


# --- crawl -----------------------------------------------------------------

def crawl(conn, years: set[int] | None = None, fetch_bodies: bool = True,
          limit: int = 0, delay: float = DEFAULT_DELAY, site: str = DEFAULT_SITE) -> dict:
    """Walk root → (years → issues →) articles; store new docs (never overwrite)."""
    cfg = NFCMS_SITES[site]
    site_key = cfg["site_key"]
    _ensure_site(conn, cfg)
    stats = {"issues": 0, "listed": 0, "new": 0, "bodies": 0, "skipped": 0}

    root = column_json(cfg["root"], cfg)
    if not root:
        log.error(f"{cfg['label']} root column unreachable — aborting")
        return stats

    class _Done(Exception):
        pass

    def store_articles(idata: dict, issue: dict):
        for art in idata.get("articles") or []:
            if not art.get("id") or not art.get("url"):
                continue
            stats["listed"] += 1
            doc = article_to_doc(art, issue, cfg)
            held = _existing_id(conn, doc["id"], doc["url"])
            if held:
                stats["skipped"] += 1
                continue

            if fetch_bodies:
                time.sleep(delay)
                body, content_html, att = fetch_body(doc["id"], cfg)
                doc["body_text_cn"] = body
                doc["attachments_json"] = json.dumps(att, ensure_ascii=False)
                if content_html:
                    doc["raw_html_path"] = save_raw_html(site_key, doc["id"], content_html)
                if body:
                    stats["bodies"] += 1
                if cfg["docnum_from_body"] and not doc["document_number"]:
                    doc["document_number"] = docnum_from_body(body)

            store_document(conn, site_key, doc)
            stats["new"] += 1
            if stats["new"] % 50 == 0:
                conn.commit()
                log.info(f"    progress: {stats}")
            if limit and stats["new"] >= limit:
                conn.commit()
                log.info(f"=== {cfg['label']}: hit --limit {limit}: {stats} ===")
                raise _Done()

    try:
        if cfg["levels"] == 0:
            # Flat column: the root JSON lists the articles itself.
            log.info(f"=== {cfg['label']}: flat column {cfg['root']} ===")
            stats["issues"] += 1
            store_articles(root, root.get("category") or {"id": cfg["root"]})
        else:
            year_cols = [c for c in root.get("children") or []
                         if int(c.get("id") or 0) not in cfg["skip_columns"]]
            if years is not None:
                year_cols = [c for c in year_cols if _year_of(c) in years]
            log.info(f"=== {cfg['label']}: {len(year_cols)} year column(s) "
                     f"({'all' if years is None else sorted(years)}) ===")

            for ycol in year_cols:
                _store_category(conn, ycol, cfg["root"], site_key)
                time.sleep(delay)
                ydata = column_json(int(ycol["id"]), cfg)
                if not ydata:
                    continue
                issues = ydata.get("children") or []
                log.info(f"  {ycol.get('name')}: {len(issues)} issues")

                for issue in issues:
                    _store_category(conn, issue, int(ycol["id"]), site_key)
                    time.sleep(delay)
                    idata = column_json(int(issue["id"]), cfg)
                    if not idata:
                        continue
                    stats["issues"] += 1
                    store_articles(idata, issue)
                conn.commit()
    except _Done:
        return stats

    conn.commit()
    log.info(f"=== {cfg['label']} done: {stats} ===")
    return stats


def backfill_bodies(conn, limit: int = 0, delay: float = DEFAULT_DELAY,
                    site: str = DEFAULT_SITE) -> int:
    """Fetch bodies for docs listed with --list-only."""
    cfg = NFCMS_SITES[site]
    site_key = cfg["site_key"]
    sql = "SELECT id FROM documents WHERE site_key = ? AND body_text_cn = ''"
    params: list = [site_key]
    if cfg["url_filter"]:
        sql += " AND url LIKE ? AND url != ''"
        params.append(f"%{cfg['url_filter']}%")
    rows = conn.execute(sql + " ORDER BY id", params).fetchall()
    log.info(f"=== {cfg['label']} body backfill: {len(rows)} docs without body ===")
    done = 0
    for (doc_id,) in rows:
        body, content_html, att = fetch_body(doc_id, cfg)
        time.sleep(delay)
        if not body:
            continue
        raw = save_raw_html(site_key, doc_id, content_html) if content_html else ""
        docnum = docnum_from_body(body) if cfg["docnum_from_body"] else ""
        conn.execute(
            "UPDATE documents SET body_text_cn = ?, attachments_json = ?, "
            "raw_html_path = CASE WHEN ? != '' THEN ? ELSE raw_html_path END, "
            "document_number = CASE WHEN document_number = '' THEN ? ELSE document_number END, "
            "crawl_timestamp = ? WHERE id = ?",
            (body, json.dumps(att, ensure_ascii=False), raw, raw, docnum,
             datetime.now(timezone.utc).isoformat(), doc_id))
        done += 1
        if done % 50 == 0:
            conn.commit()
            log.info(f"  {done}/{len(rows)} bodies")
        if limit and done >= limit:
            break
    conn.commit()
    log.info(f"=== {cfg['label']} body backfill done: {done} bodies ===")
    return done


def main():
    ap = argparse.ArgumentParser(description="NFCMS JSON crawler: Shenzhen 政府公报 + Dapeng 规范性文件库")
    ap.add_argument("--site", default=DEFAULT_SITE, choices=sorted(NFCMS_SITES),
                    help=f"NFCMS section to walk (default {DEFAULT_SITE})")
    ap.add_argument("--year", help="Years to walk: '2006,2023' or '2000-2010' (default: all; gazette only)")
    ap.add_argument("--list-only", action="store_true",
                    help="Store listing metadata (incl. 文号) without fetching bodies")
    ap.add_argument("--backfill-bodies", action="store_true",
                    help="Fetch bodies for already-listed docs of this section")
    ap.add_argument("--limit", type=int, default=0, help="Stop after N new docs (0 = no cap)")
    ap.add_argument("--delay", type=float, default=DEFAULT_DELAY,
                    help=f"Seconds between requests (default {DEFAULT_DELAY})")
    ap.add_argument("--stats", action="store_true", help="Show database stats")
    ap.add_argument("--db", help="SQLite path (default documents.db; use a scratch DB for tests)")
    args = ap.parse_args()
    site_key = NFCMS_SITES[args.site]["site_key"]

    conn = init_db(Path(args.db)) if args.db else init_db()
    try:
        if args.stats:
            show_stats(conn)
        elif args.backfill_bodies:
            backfill_bodies(conn, limit=args.limit, delay=args.delay, site=args.site)
        else:
            crawl(conn, years=parse_years(args.year), fetch_bodies=not args.list_only,
                  limit=args.limit, delay=args.delay, site=args.site)
            n, nb = conn.execute(
                "SELECT COUNT(*), SUM(body_text_cn != '') FROM documents WHERE site_key = ?",
                (site_key,)).fetchone()
            print(f"\n{site_key}: {n} documents, {nb or 0} with body")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
