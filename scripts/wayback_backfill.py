#!/usr/bin/env python3
"""
Wayback Machine backfill for sites with no browsable archive.

Neither stdaily.com nor guancha.cn expose a historical archive we can
paginate through, so the daily crawler only captures a rolling recent
window. The Internet Archive's Wayback Machine has been snapshotting
both sites for years, and the CDX Server API exposes every archived
URL. We can therefore:

  1. Query CDX for every URL that looks like an article (prefix + pattern)
  2. Try fetching each URL **live first** — many Chinese news sites keep
     old content online even without a browsable index
  3. Fall back to the Wayback snapshot if the live URL is dead
  4. Parse with the existing crawler's title/body extraction functions
  5. Store into documents.db with the normal site_key

Usage:
    python3 scripts/wayback_backfill.py --site stdaily --from 2024 --to 2025
    python3 scripts/wayback_backfill.py --site guancha --from 2024 --to 2025 --limit 200
    python3 scripts/wayback_backfill.py --site stdaily --dry-run    # list URLs only

Wayback CDX is rate-limited (503s on heavy queries). This script uses
small year-sized batches with polite delays + exponential backoff.

Notes:
  - `collapse=urlkey` deduplicates across snapshots so each original URL
    appears only once.
  - We prefer live URLs because Wayback adds a toolbar + CSS injection
    that our regex-based body extractor has to strip around.
"""

import argparse
import json
import re
import sqlite3
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from crawlers.base import (
    REQUEST_DELAY,
    fetch,
    init_db,
    log,
    next_id,
    save_raw_html,
    store_document,
    store_site,
)
from crawlers import stdaily, guancha

BROWSER_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)

# CDX API is intentionally polite: one request at a time, no concurrency.
CDX_DELAY = 5         # seconds between CDX queries
CDX_TIMEOUT = 45
WAYBACK_TIMEOUT = 30

# Per-site configuration.
# Each site declares:
#   url_prefix:  Wayback CDX URL prefix (with `matchType=prefix`)
#   article_re:  regex matching article URLs (applied to the CDX "original" col)
#   crawler:     the crawler module to reuse for extraction + storage
#   clean_url:   optional callable to normalize a URL before DB storage
SITES = {
    "stdaily": {
        "url_prefix": "stdaily.com/web/",
        "article_re": re.compile(r"/web/[^\"'<>\s]+/content_\d+\.html"),
        "crawler": stdaily,
        "date_from_url": lambda u: re.search(r"/(\d{4}-\d{2})/(\d{2})/content_", u),
        "extract_title": stdaily._extract_title,
        "extract_body": stdaily._extract_body,
        "extract_meta": stdaily._extract_meta,
        "site_key": "stdaily",
        "publisher": "科技日报",
        "date_key": "date_published",
    },
    "guancha": {
        "url_prefix": "guancha.cn/",
        "article_re": re.compile(r"/[a-zA-Z_][a-zA-Z_0-9]*/\d{4}_\d{2}_\d{2}_\d+(?:_s)?\.shtml"),
        "crawler": guancha,
        "date_from_url": lambda u: re.search(r"/(\d{4})_(\d{2})_(\d{2})_\d+", u),
        "extract_title": guancha._extract_title,
        "extract_body": guancha._extract_body,
        "extract_meta": guancha._extract_meta,
        "site_key": "guancha",
        "publisher": "观察者网",
        "date_key": "date_published",
    },
}


def cdx_query(url_prefix: str, year: int, limit: int = 5000) -> list[str]:
    """Query CDX for article URLs within a year. Returns unique original URLs.

    Retries with exponential backoff on 503 (Wayback is rate-sensitive).
    """
    params = {
        "url": url_prefix,
        "matchType": "prefix",
        "output": "json",
        "from": f"{year}0101",
        "to": f"{year}1231",
        "filter": ["statuscode:200", "mimetype:text/html"],
        "collapse": "urlkey",
        "limit": str(limit),
    }
    # Build query string manually because urllib.parse.urlencode doesn't
    # handle multi-value keys correctly for CDX.
    qs = "&".join(
        f"{k}={urllib.parse.quote(str(v))}"
        for k, vals in [(k, v if isinstance(v, list) else [v]) for k, v in params.items()]
        for v in vals
    )
    url = f"https://web.archive.org/cdx/search/cdx?{qs}"

    for attempt in range(5):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": BROWSER_UA})
            with urllib.request.urlopen(req, timeout=CDX_TIMEOUT) as r:
                data = json.loads(r.read())
            if not data:
                return []
            # First row is the header: ["urlkey","timestamp","original",...]
            return [row[2] for row in data[1:]]
        except urllib.error.HTTPError as e:
            if e.code in (503, 502, 429):
                wait = (attempt + 1) * 10
                log.warning(f"  Wayback {e.code}, backing off {wait}s (attempt {attempt+1}/5)")
                time.sleep(wait)
            else:
                log.error(f"  CDX failed: {e}")
                return []
        except Exception as e:
            wait = (attempt + 1) * 5
            log.warning(f"  CDX error: {e}, retrying in {wait}s")
            time.sleep(wait)
    log.error(f"  Giving up on CDX query for {year}")
    return []


def fetch_wayback_snapshot(original_url: str, timestamp: str = "2024") -> str:
    """Fetch a URL via Wayback, stripping its toolbar injection.

    The Wayback snapshot URL is
      https://web.archive.org/web/{timestamp}if_/{original_url}
    The `if_` modifier asks Wayback to return the iframe-friendly version
    without the toolbar, which keeps the HTML much closer to the original.
    """
    wb_url = f"https://web.archive.org/web/{timestamp}if_/{original_url}"
    try:
        return fetch(wb_url, timeout=WAYBACK_TIMEOUT, headers={"User-Agent": BROWSER_UA})
    except Exception as e:
        log.warning(f"    Wayback fetch failed: {e}")
        return ""


def _live_has_usable_body(html: str, site: str) -> bool:
    """Return True if the live HTML contains an extractable article body.

    Used to decide whether to fall back to Wayback. For stdaily we detect
    two 'dead' patterns: the 15175-byte 404 page and small ~3KB stub pages
    whose <title> says '稿件详情' (Article Details) — both indicate the
    article has been removed from the live site even though HTTP is 200.
    """
    if not html:
        return False
    if site == "stdaily":
        if len(html) == stdaily.ERROR_PAGE_SIZE:
            return False
        if "稿件详情" in html[:500] and len(html) < 5000:
            return False
        return 'id="printContent"' in html
    if site == "guancha":
        # Paywall/redirect pages are handled separately in backfill()
        return 'class="content all-txt"' in html
    return True


def fetch_live_or_wayback(url: str, site: str = "stdaily") -> tuple[str, str]:
    """Try the live URL first, fall back to Wayback if live has no body.

    Returns (html, source) where source is 'live', 'wayback', or 'failed'.
    'failed' means both the live and Wayback versions were stubs or missing —
    the URL is effectively dead.
    """
    # Try live
    try:
        live_html = fetch(url, headers={"User-Agent": BROWSER_UA})
    except Exception:
        live_html = ""

    if _live_has_usable_body(live_html, site):
        return live_html, "live"

    # Fall back to Wayback
    wb_html = fetch_wayback_snapshot(url)
    if _live_has_usable_body(wb_html, site):
        return wb_html, "wayback"

    return "", "failed"


def backfill(site: str, year_from: int, year_to: int, limit: int,
             dry_run: bool, db_path: Path = None) -> int:
    """Run the Wayback backfill for one site across a year range."""
    if site not in SITES:
        raise ValueError(f"Unknown site: {site}. Choose from {list(SITES)}")
    cfg = SITES[site]
    crawler_mod = cfg["crawler"]

    # Discover URLs via CDX, year by year
    all_urls: list[str] = []
    seen: set[str] = set()
    for year in range(year_from, year_to + 1):
        log.info(f"CDX query: {site} {year}")
        rows = cdx_query(cfg["url_prefix"], year, limit=5000)
        # Filter by article pattern and deduplicate
        added = 0
        for u in rows:
            if not cfg["article_re"].search(u):
                continue
            # Normalize scheme — Wayback mixes http/https, canonicalize to https
            if u.startswith("http://"):
                u = "https://" + u[7:]
            if u not in seen:
                seen.add(u)
                all_urls.append(u)
                added += 1
        log.info(f"  {year}: {len(rows)} CDX rows → {added} new article URLs (total {len(all_urls)})")
        time.sleep(CDX_DELAY)
        if limit and len(all_urls) >= limit:
            all_urls = all_urls[:limit]
            log.info(f"  hit limit of {limit}, stopping discovery")
            break

    log.info(f"Discovered {len(all_urls)} unique article URLs")

    if dry_run:
        for u in all_urls[:50]:
            print(f"  {u}")
        if len(all_urls) > 50:
            print(f"  ... and {len(all_urls) - 50} more")
        return len(all_urls)

    # --- Fetch and store ---
    conn = init_db(db_path)
    store_site(conn, cfg["site_key"], crawler_mod.SITE_CFG)

    stored = 0
    skipped_existing = 0
    skipped_empty = 0
    from_live = 0
    from_wayback = 0
    errors = 0

    for i, url in enumerate(all_urls):
        # Skip if we already have this URL with a body
        existing = conn.execute(
            "SELECT id, body_text_cn FROM documents WHERE url = ?", (url,)
        ).fetchone()
        if existing and existing[1]:
            skipped_existing += 1
            continue

        html, source = fetch_live_or_wayback(url, site=site)
        if not html or source == "failed":
            errors += 1
            continue
        if source == "live":
            from_live += 1
        else:
            from_wayback += 1

        # Guancha: skip known redirect targets (paywall/Xinhua/CCTV)
        if site == "guancha":
            if any(m in html for m in guancha.SKIP_REDIRECT_MARKERS):
                skipped_empty += 1
                continue

        title = cfg["extract_title"](html)
        if not title:
            skipped_empty += 1
            continue

        body = cfg["extract_body"](html)
        meta = cfg["extract_meta"](html)

        # Derive date: prefer URL, fall back to meta
        if site == "guancha":
            m = cfg["date_from_url"](url)
            if m:
                date_str = f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
                date_ts = guancha._parse_date(m.group(1), m.group(2), m.group(3))
            else:
                date_str = (meta.get("date_published", "") or "")[:10]
                date_ts = 0
        else:
            m = cfg["date_from_url"](url)
            if m:
                date_str = f"{m.group(1)}-{m.group(2)}"
                date_ts = stdaily._parse_date(date_str)
            else:
                date_str = (meta.get("date_published", "") or "")[:10]
                date_ts = 0

        doc_id = existing[0] if existing else next_id(conn)
        raw_html_path = save_raw_html(cfg["site_key"], doc_id, html)

        doc = {
            "id": doc_id,
            "title": title,
            "publisher": meta.get("source") or cfg["publisher"],
            "keywords": "",
            "abstract": meta.get("abstract", ""),
            "date_written": date_ts,
            "date_published": date_str,
            "body_text_cn": body,
            "url": url,
            "classify_main_name": "媒体报道",
            "raw_html_path": raw_html_path,
        }
        # guancha stores the section in `relation`
        if site == "guancha":
            section_match = re.search(r"^https?://[^/]+/([^/]+)/", url)
            if section_match:
                section = section_match.group(1)
                doc["relation"] = section
                if section and section[0].isupper():
                    doc["classify_theme_name"] = section

        store_document(conn, cfg["site_key"], doc)
        stored += 1

        if stored % 20 == 0:
            conn.commit()
            log.info(
                f"  Progress: {stored} stored "
                f"(live={from_live}, wayback={from_wayback}), "
                f"{skipped_existing} already-had, {skipped_empty} skipped, "
                f"{errors} errors ({i+1}/{len(all_urls)})"
            )

        time.sleep(REQUEST_DELAY)

    conn.commit()
    log.info(
        f"=== {site} backfill: {stored} new "
        f"(live={from_live}, wayback={from_wayback}), "
        f"{skipped_existing} already-had, {skipped_empty} skipped, "
        f"{errors} errors ==="
    )
    conn.close()
    return stored


def main():
    parser = argparse.ArgumentParser(
        description="Wayback Machine backfill for stdaily and guancha"
    )
    parser.add_argument("--site", required=True, choices=sorted(SITES.keys()),
                        help="Site to backfill")
    parser.add_argument("--from", dest="year_from", type=int, default=2024,
                        help="Start year (inclusive, default 2024)")
    parser.add_argument("--to", dest="year_to", type=int, default=2025,
                        help="End year (inclusive, default 2025)")
    parser.add_argument("--limit", type=int, default=0,
                        help="Stop after this many URLs (0 = no limit)")
    parser.add_argument("--dry-run", action="store_true",
                        help="List URLs discovered, don't fetch/store")
    parser.add_argument("--db", type=str, help="Alternative DB path")
    args = parser.parse_args()

    if args.year_from > args.year_to:
        parser.error("--from must be <= --to")

    db_path = Path(args.db) if args.db else None
    backfill(args.site, args.year_from, args.year_to, args.limit,
             args.dry_run, db_path=db_path)


if __name__ == "__main__":
    main()
