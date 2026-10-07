"""
Re-extract body text from saved raw HTML for documents with missing bodies.

This is a quick win for sites where body extraction failed on first crawl
(e.g., MOST changed their CMS template, or a container selector was added to
an extractor later — "the GD-dept container fix" pattern). No network requests
needed — reads from raw_html/ directory.

Routing (2026-10-07, corpus-lessons A7): each site is sent to the SAME
extractor its crawler uses — single-site modules via SITE_KEY, multi-site
dicts (govcms.SITES, gkmlpt.SITES) by key — then falls through to
crawlers.govcms._extract_body (the richest shared container list) and finally
the local generic. Before this, every govcms-tier site hit only the local
generic, which knew none of their containers.

Guard: a body is only written when the stored one is NULL/empty or SHORTER
than the new text — never replaces a longer body (the UPDATE carries the
predicate, so it holds even if the candidate query is widened).

Usage:
    python3 scripts/backfill_from_html.py                   # All sites
    python3 scripts/backfill_from_html.py --site most       # One site
    python3 scripts/backfill_from_html.py --sites spc,jl_jyt
    python3 scripts/backfill_from_html.py --dry-run         # Preview (counts only)
"""

import argparse
import importlib
import re
import sqlite3
import sys
import time
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))
DB_PATH = ROOT / "documents.db"
RAW_HTML_DIR = ROOT / "raw_html"

# Single-site crawler modules exposing _extract_body(html). site_key -> module.
EXTRACTORS = {
    "most": "crawlers.most",
    "ndrc": "crawlers.ndrc",
    "nda": "crawlers.nda",
    "mee": "crawlers.mee",
    "samr": "crawlers.samr",
    "mofcom": "crawlers.mofcom",
    "cac": "crawlers.cac",
    "sic": "crawlers.sic",
    "miit": "crawlers.miit",
    "mof": "crawlers.mof",
    "moe": "crawlers.moe",
    "gov": "crawlers.gov",
    "spp": "crawlers.spp",
    "beijing": "crawlers.beijing",
    "shanghai": "crawlers.shanghai",
    "jiangsu": "crawlers.jiangsu",
    "chongqing": "crawlers.chongqing",
    "wuhan": "crawlers.wuhan",
    "suzhou": "crawlers.suzhou",
    "hangzhou": "crawlers.hangzhou",
    "xinhua": "crawlers.xinhua",
    "people": "crawlers.people",
}

# Generic extractor for gkmlpt-based sites (Guangdong). Unioned with gkmlpt.SITES at runtime.
GKMLPT_SITES = {
    "heyuan", "zhongshan", "zhuhai", "gd", "szdp", "gz", "shanwei",
    "jiangmen", "yunfu", "huizhou", "szlg", "szlhq", "szgm", "szlh",
    "szns", "szft", "szpsq", "sz", "ga", "mzj", "hrss", "swj", "jtys",
    "zjj", "stic", "sf", "szeb", "yjgl", "wjw", "fgw", "audit", "jieyang",
    "yangjiang", "shaoguan", "shantou",
}

_MOD_CACHE = {}


def _mod(name: str):
    if name not in _MOD_CACHE:
        try:
            _MOD_CACHE[name] = importlib.import_module(name)
        except Exception as e:  # noqa: BLE001 — a broken crawler import must not stop the pass
            print(f"  ! cannot import {name}: {e}")
            _MOD_CACHE[name] = None
    return _MOD_CACHE[name]


def _site_router() -> dict:
    """site_key -> callable(html)->str for the multi-site crawlers."""
    router = {}
    govcms = _mod("crawlers.govcms")
    if govcms:
        for key in govcms.SITES:
            router[key] = govcms._extract_body
    gkmlpt = _mod("crawlers.gkmlpt")
    gk_keys = set(GKMLPT_SITES) | (set(gkmlpt.SITES) if gkmlpt else set())
    for key in gk_keys:
        router[key] = _gkmlpt_extract_body
    for key, modname in EXTRACTORS.items():
        m = _mod(modname)
        if m and hasattr(m, "_extract_body"):
            router[key] = m._extract_body
    return router


def _generic_extract_body(html: str) -> str:
    """Generic body extractor — tries multiple common CMS patterns."""
    html = re.sub(r"<(script|style)\b.*?</\1\s*>", "", html, flags=re.S | re.I)
    # NOTE: no bare "article" — it matched wrapper classes (bt-article-y, detail-article)
    # and returned the whole article box incl. metadata table/footer as "body".
    for class_name in [
        "trs_editor_view", "TRS_Editor", "TRS_UEDITOR",
        "articleDetailsText", "text wide",
        "xxgk-detail-content", "content-article",
    ]:
        m = re.search(rf'class="[^"]*{re.escape(class_name)}[^"]*"', html)
        if not m:
            if f'id="{class_name}"' in html:
                m = re.search(rf'id="{re.escape(class_name)}"', html)
        if not m:
            continue
        start = html.find(">", m.start()) + 1
        end = len(html)
        for marker in ['<meta name="ContentEnd"', 'class="filelist"',
                       'class="share', 'class="relation', 'class="footer',
                       '<script', '<!-- end content', '<!-- footer']:
            pos = html.find(marker, start)
            if pos != -1 and pos < end:
                end = pos
        content = html[start:end]
        content = re.sub(r"<br\s*/?\s*>", "\n", content)
        content = re.sub(r"<p[^>]*>", "\n", content)
        content = re.sub(r"</p>", "", content)
        content = re.sub(r"<div[^>]*>", "\n", content)
        content = re.sub(r"</div>", "", content)
        content = re.sub(r"<img[^>]*>", "", content)
        text = re.sub(r"<[^>]+>", "", content)
        text = re.sub(r"[ \t]+", " ", text)
        text = re.sub(r"\n\s*\n", "\n", text)
        text = (
            text.replace("&nbsp;", " ")
            .replace("　", " ")
            .replace("&lt;", "<")
            .replace("&gt;", ">")
            .replace("&amp;", "&")
            .replace("&ldquo;", "“")
            .replace("&rdquo;", "”")
            .strip()
        )
        if len(text) > 50:
            return text
    return ""


def _gkmlpt_extract_body(html: str) -> str:
    """Extract body from gkmlpt-style pages (JSON content field or HTML)."""
    gk = _mod("crawlers.gkmlpt")
    if gk:
        try:
            t = gk.extract_body_text(html)
            if t and len(t) > 50:
                return t
        except Exception:  # noqa: BLE001
            pass
    import json
    m = re.search(r'"content"\s*:\s*"((?:[^"\\]|\\.)*)"', html)
    if m:
        try:
            content = json.loads(f'"{m.group(1)}"')
            text = re.sub(r"<[^>]+>", "", content)
            text = re.sub(r"&nbsp;", " ", text)
            text = re.sub(r"\s+", " ", text).strip()
            if len(text) > 50:
                return text
        except (json.JSONDecodeError, ValueError):
            pass
    return _generic_extract_body(html)


def extract_for_site(site_key: str, html: str, router: dict) -> str:
    """Site extractor → govcms shared containers (bounded, tested) → local generic
    ONLY for sites with no crawler extractor at all. The generic used to run after
    every site extractor too; on attachment-only pages it then "found" a wrapper
    div and wrote the page chrome as body (cq_gaj/js_jtyst, 2026-10-07)."""
    chain = []
    if site_key in router:
        chain.append(router[site_key])
    govcms = _mod("crawlers.govcms")
    if govcms and (site_key not in router or router[site_key] is not govcms._extract_body):
        chain.append(govcms._extract_body)
    if site_key not in router:
        chain.append(_generic_extract_body)
    for fn in chain:
        try:
            body = fn(html)
        except Exception:  # noqa: BLE001 — one extractor crashing must not lose the doc
            body = ""
        if body and len(body) > 50:
            return body
    return ""


def _why_failed(html: str) -> str:
    """Best-effort reason a page yielded no body (for the report, not for logic)."""
    if len(html) < 3000:
        return "stub(<3k, anti-bot/redirect shell)"
    core = re.sub(r"<(script|style)\b.*?</\1\s*>", "", html, flags=re.S | re.I)
    if re.search(r'\.(pdf|docx?|xlsx?|rar|zip)["\')]', core, re.I):
        return "attachment-only (pdf/doc/xls/rar)"
    if re.search(r"<video|\.mp4|ckplayer", core, re.I):
        return "video page"
    if "<img" in core:
        return "image-only (一图读懂/scan)"
    return "no recognisable body (JS-rendered or unknown container)"


def _site_pct(conn, site_key: str):
    n, b = conn.execute(
        """SELECT COUNT(*), SUM(CASE WHEN body_text_cn IS NOT NULL AND LENGTH(body_text_cn)>20
                  THEN 1 ELSE 0 END) FROM documents WHERE site_key=?""", (site_key,)).fetchone()
    return n or 0, b or 0


def backfill(sites=None, dry_run: bool = False, limit: int = 0):
    conn = sqlite3.connect(str(DB_PATH), timeout=30)
    conn.execute("PRAGMA busy_timeout=30000")
    conn.execute("PRAGMA journal_mode=WAL")

    query = """
        SELECT id, site_key, raw_html_path
        FROM documents
        WHERE (body_text_cn IS NULL OR LENGTH(body_text_cn) <= 20)
          AND raw_html_path IS NOT NULL AND raw_html_path != ''
    """
    params = []
    if sites:
        query += f" AND site_key IN ({','.join('?' * len(sites))})"
        params.extend(sites)
    query += " ORDER BY site_key, id"
    if limit:
        query += f" LIMIT {int(limit)}"

    rows = conn.execute(query, params).fetchall()
    print(f"Found {len(rows)} documents with raw HTML but no body text")

    if dry_run:
        for site, count in Counter(r[1] for r in rows).most_common():
            print(f"  {site}: {count}")
        conn.close()
        return

    router = _site_router()
    before = {s: _site_pct(conn, s) for s in sorted({r[1] for r in rows})}

    updated = 0
    failed = 0
    by_site = Counter()
    reasons = Counter()
    t0 = time.time()

    for i, (doc_id, site_key, raw_path) in enumerate(rows, 1):
        html_file = ROOT / raw_path
        if not html_file.exists():
            failed += 1
            reasons[f"{site_key}|file missing"] += 1
            continue
        html = html_file.read_text(errors="replace")
        body = extract_for_site(site_key, html, router)
        if body:
            # Never overwrite a non-empty body with a shorter one.
            cur = conn.execute(
                """UPDATE documents SET body_text_cn = ?
                   WHERE id = ? AND (body_text_cn IS NULL OR LENGTH(body_text_cn) < LENGTH(?))""",
                (body, doc_id, body))
            if cur.rowcount:
                updated += 1
                by_site[site_key] += 1
            if updated % 200 == 0:
                conn.commit()
        else:
            failed += 1
            reasons[f"{site_key}|{_why_failed(html)}"] += 1
        if i % 2000 == 0:
            conn.commit()
            conn.execute("PRAGMA wal_checkpoint(PASSIVE)")
            print(f"  …{i}/{len(rows)} scanned, {updated} updated ({time.time() - t0:.0f}s)")

    conn.commit()
    conn.execute("PRAGMA wal_checkpoint(PASSIVE)")

    print(f"\nDone: {updated} bodies extracted, {failed} failed ({time.time() - t0:.0f}s)")
    print(f"\n{'site':12s} {'docs':>6s} {'body% before':>12s} {'body% after':>11s} {'+bodies':>8s}")
    for s in before:
        n, b0 = before[s]
        _, b1 = _site_pct(conn, s)
        print(f"{s:12s} {n:6d} {100.0 * b0 / n if n else 0:11.1f}% {100.0 * b1 / n if n else 0:10.1f}% {by_site.get(s, 0):8d}")
    if reasons:
        print("\nStill bodiless (site|reason → count):")
        for k, c in reasons.most_common():
            print(f"  {k}: {c}")
    conn.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Re-extract body text from saved raw HTML")
    parser.add_argument("--site", help="Only process this site")
    parser.add_argument("--sites", help="Comma-separated site_keys")
    parser.add_argument("--limit", type=int, default=0, help="Stop after N candidate rows")
    parser.add_argument("--dry-run", action="store_true", help="Preview without updating")
    args = parser.parse_args()
    site_list = []
    if args.site:
        site_list.append(args.site)
    if args.sites:
        site_list.extend(s.strip() for s in args.sites.split(",") if s.strip())
    backfill(sites=site_list or None, dry_run=args.dry_run, limit=args.limit)
