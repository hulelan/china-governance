"""
Shenzhen Government Gazette (深圳市人民政府公报) crawler.

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

Gotchas:
  * HTTPS from Python urllib fails with `SSL BAD_ECPOINT` on this host; every
    request is forced to http://. URLs are STORED as published (https://…),
    which is how the 35 pre-existing rows are stored, and dedup compares both
    schemes.
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

SITE_KEY = "sz_gazette"
SITE_CFG = {
    "name": "Shenzhen Government Gazette (深圳市人民政府公报)",
    "base_url": "http://www.sz.gov.cn/zfgb",
    "admin_level": "municipal",
}

HOST = "http://www.sz.gov.cn"          # http only — see module docstring
ROOT_COLUMN = 101619                   # 政府公报
SKIP_COLUMNS = {101639}                # 政策解读 (explainers)
DEFAULT_DELAY = 1.0
HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"),
    "Referer": "https://www.sz.gov.cn/zfgb/",
}


# --- fetch helpers ---------------------------------------------------------

def _to_http(url: str) -> str:
    return re.sub(r"^https://", "http://", url or "")


def _get_json(path: str, timeout: int = 30) -> dict | None:
    """GET a /postmeta/... JSON path over http; None on any failure."""
    url = HOST + path
    try:
        return json.loads(fetch(url, timeout=timeout, headers=HEADERS))
    except Exception as e:
        log.warning(f"  JSON fetch failed {url}: {e}")
        return None


def column_json(col_id: int) -> dict | None:
    return _get_json(f"/postmeta/i/{col_id}.json")


def post_json(post_id: int) -> dict | None:
    return _get_json(f"/postmeta/p/{post_id // 1_000_000}/{post_id // 1_000}/{post_id}.json")


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


def article_to_doc(art: dict, issue: dict) -> dict:
    """Map one gazette listing article onto the documents schema."""
    ext = {}
    try:
        ext = json.loads(art.get("json_ext") or "{}") or {}
    except Exception:
        ext = {}
    if isinstance(ext, list):
        ext = {}
    docnum = (art.get("EXT_zh") or ext.get("EXT_zh") or "").strip()
    issuer = (art.get("EXT_fwdw") or ext.get("EXT_fwdw") or art.get("source") or "").strip()
    section = (art.get("EXT_sort") or ext.get("EXT_sort") or "").strip()
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
        "classify_main_name": "政府公报",
        "classify_genre_name": section,
        "keywords": issue.get("name", ""),   # e.g. 2006年第49期（总第519期）
        "url": (art.get("url") or "").strip(),
        "post_url": (art.get("url") or "").strip(),
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


def _store_category(conn, col: dict, parent_id: int):
    conn.execute(
        "INSERT OR IGNORE INTO categories (id, site_key, name, parent_id, post_count) "
        "VALUES (?, ?, ?, ?, ?)",
        (int(col["id"]), SITE_KEY, (col.get("name") or "").strip(), parent_id,
         int(col.get("publish_count") or 0)))


def fetch_body(post_id: int) -> tuple[str, str, list]:
    """Fetch one post JSON → (body_text, content_html, attachments)."""
    p = post_json(post_id)
    if not p:
        return "", "", []
    content = p.get("content") or ""
    att = p.get("attachment") or []
    return html_to_text(content), content, att if isinstance(att, list) else []


# --- crawl -----------------------------------------------------------------

def crawl(conn, years: set[int] | None = None, fetch_bodies: bool = True,
          limit: int = 0, delay: float = DEFAULT_DELAY) -> dict:
    """Walk root → years → issues → articles; store new docs (never overwrite)."""
    store_site(conn, SITE_KEY, SITE_CFG, sid="755001")
    stats = {"issues": 0, "listed": 0, "new": 0, "bodies": 0, "skipped": 0}

    root = column_json(ROOT_COLUMN)
    if not root:
        log.error("Gazette root column unreachable — aborting")
        return stats
    year_cols = [c for c in root.get("children") or []
                 if int(c.get("id") or 0) not in SKIP_COLUMNS]
    if years is not None:
        year_cols = [c for c in year_cols if _year_of(c) in years]
    log.info(f"=== Shenzhen gazette: {len(year_cols)} year column(s) "
             f"({'all' if years is None else sorted(years)}) ===")

    for ycol in year_cols:
        _store_category(conn, ycol, ROOT_COLUMN)
        time.sleep(delay)
        ydata = column_json(int(ycol["id"]))
        if not ydata:
            continue
        issues = ydata.get("children") or []
        log.info(f"  {ycol.get('name')}: {len(issues)} issues")

        for issue in issues:
            _store_category(conn, issue, int(ycol["id"]))
            time.sleep(delay)
            idata = column_json(int(issue["id"]))
            if not idata:
                continue
            stats["issues"] += 1
            for art in idata.get("articles") or []:
                if not art.get("id") or not art.get("url"):
                    continue
                stats["listed"] += 1
                doc = article_to_doc(art, issue)
                held = _existing_id(conn, doc["id"], doc["url"])
                if held:
                    stats["skipped"] += 1
                    continue

                if fetch_bodies:
                    time.sleep(delay)
                    body, content_html, att = fetch_body(doc["id"])
                    doc["body_text_cn"] = body
                    doc["attachments_json"] = json.dumps(att, ensure_ascii=False)
                    if content_html:
                        doc["raw_html_path"] = save_raw_html(SITE_KEY, doc["id"], content_html)
                    if body:
                        stats["bodies"] += 1

                store_document(conn, SITE_KEY, doc)
                stats["new"] += 1
                if stats["new"] % 50 == 0:
                    conn.commit()
                    log.info(f"    progress: {stats}")
                if limit and stats["new"] >= limit:
                    conn.commit()
                    log.info(f"=== Gazette: hit --limit {limit}: {stats} ===")
                    return stats
        conn.commit()

    conn.commit()
    log.info(f"=== Gazette done: {stats} ===")
    return stats


def backfill_bodies(conn, limit: int = 0, delay: float = DEFAULT_DELAY) -> int:
    """Fetch bodies for sz_gazette docs listed with --list-only."""
    rows = conn.execute(
        "SELECT id FROM documents WHERE site_key = ? AND body_text_cn = '' ORDER BY id",
        (SITE_KEY,)).fetchall()
    log.info(f"=== Gazette body backfill: {len(rows)} docs without body ===")
    done = 0
    for (doc_id,) in rows:
        body, content_html, att = fetch_body(doc_id)
        time.sleep(delay)
        if not body:
            continue
        raw = save_raw_html(SITE_KEY, doc_id, content_html) if content_html else ""
        conn.execute(
            "UPDATE documents SET body_text_cn = ?, attachments_json = ?, "
            "raw_html_path = CASE WHEN ? != '' THEN ? ELSE raw_html_path END, "
            "crawl_timestamp = ? WHERE id = ?",
            (body, json.dumps(att, ensure_ascii=False), raw, raw,
             datetime.now(timezone.utc).isoformat(), doc_id))
        done += 1
        if done % 50 == 0:
            conn.commit()
            log.info(f"  {done}/{len(rows)} bodies")
        if limit and done >= limit:
            break
    conn.commit()
    log.info(f"=== Gazette body backfill done: {done} bodies ===")
    return done


def main():
    ap = argparse.ArgumentParser(description="Shenzhen Government Gazette (政府公报) crawler")
    ap.add_argument("--year", help="Years to walk: '2006,2023' or '2000-2010' (default: all)")
    ap.add_argument("--list-only", action="store_true",
                    help="Store listing metadata (incl. 文号) without fetching bodies")
    ap.add_argument("--backfill-bodies", action="store_true",
                    help="Fetch bodies for already-listed sz_gazette docs")
    ap.add_argument("--limit", type=int, default=0, help="Stop after N new docs (0 = no cap)")
    ap.add_argument("--delay", type=float, default=DEFAULT_DELAY,
                    help=f"Seconds between requests (default {DEFAULT_DELAY})")
    ap.add_argument("--stats", action="store_true", help="Show database stats")
    ap.add_argument("--db", help="SQLite path (default documents.db; use a scratch DB for tests)")
    args = ap.parse_args()

    conn = init_db(Path(args.db)) if args.db else init_db()
    try:
        if args.stats:
            show_stats(conn)
        elif args.backfill_bodies:
            backfill_bodies(conn, limit=args.limit, delay=args.delay)
        else:
            crawl(conn, years=parse_years(args.year), fetch_bodies=not args.list_only,
                  limit=args.limit, delay=args.delay)
            n, nb = conn.execute(
                "SELECT COUNT(*), SUM(body_text_cn != '') FROM documents WHERE site_key = ?",
                (SITE_KEY,)).fetchone()
            print(f"\n{SITE_KEY}: {n} documents, {nb or 0} with body")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
