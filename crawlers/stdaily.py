"""
Science & Technology Daily (科技日报 / stdaily.com) crawler.

stdaily is the official newspaper of the Ministry of Science and Technology
(MOST) — effectively a central-government publication about tech/innovation
policy, AI, and industrial R&D. We treat it as admin_level='central' even
though it looks like a newspaper, because its voice is MOST's voice.

Discovery surfaces:
    sitemap.xml    — rolling ~200 most-recent URLs (last ~4 days)
    homepage /     — ~120 article links, mostly from gdxw/gjxw/ztxw sections

URL pattern:
    /web/{section}/{YYYY-MM}/{DD}/content_{id}.html

  where section is one of:
    gdxw    — 国内新闻 (domestic)
    gjxw    — 国际新闻 (international)
    ztxw    — 专题新闻 (special topics)
    cjgxdj  — 创新高地 (innovation highland, a standing feature)
    (or empty — main daily newspaper edition)

Limitation: there is no browsable historical archive and no pagination. The
only "deep" mode we can offer is to also scan the homepage in addition to the
sitemap. True multi-year backfill would require an external source (Wayback
Machine, search engines) and is not implemented.

Body extraction: article body lives inside <div id="printContent">.

Usage:
    python -m crawlers.stdaily                  # MVP: sitemap only (~200 articles)
    python -m crawlers.stdaily --deep           # Deep: sitemap + homepage
    python -m crawlers.stdaily --stats          # Show database stats
    python -m crawlers.stdaily --list-only      # List URLs without fetching
    python -m crawlers.stdaily --db alt.db      # Write to alternate database
"""

import argparse
import re
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path

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

SITE_KEY = "stdaily"
SITE_CFG = {
    "name": "Science & Technology Daily (科技日报)",
    "base_url": "https://www.stdaily.com",
    "admin_level": "central",
}

SITEMAP_URL = "https://www.stdaily.com/sitemap.xml"
HOMEPAGE_URL = "https://www.stdaily.com/"

CST = timezone(timedelta(hours=8))
BROWSER_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)

# Matches both /web/{section}/.../content_{id}.html and /web/.../content_{id}.html
ARTICLE_URL_PATTERN = re.compile(
    r"https?://www\.stdaily\.com(/web/[^\"'<>\s]+/content_\d+\.html)"
)
ARTICLE_PATH_PATTERN = re.compile(r"/web/[^\"'<>\s]+/content_\d+\.html")

# 404 pages on stdaily are exactly 15175 bytes — use as a sentinel
ERROR_PAGE_SIZE = 15175

# Skip the English-language section — it's small and off-corpus
SKIP_SECTIONS = {"English"}


def _parse_date(date_str: str) -> int:
    """Convert 'YYYY-MM-DD' to Unix timestamp (midnight CST)."""
    if not date_str:
        return 0
    try:
        dt = datetime.strptime(date_str[:10], "%Y-%m-%d").replace(tzinfo=CST)
        return int(dt.timestamp())
    except ValueError:
        return 0


def _date_from_url(url: str) -> str:
    """Extract YYYY-MM-DD from a stdaily article URL."""
    m = re.search(r"/(\d{4}-\d{2})/(\d{2})/content_", url)
    if m:
        return f"{m.group(1)}-{m.group(2)}"
    return ""


def _section_from_url(url: str) -> str:
    """Extract the section key (e.g. 'gdxw') from a stdaily URL, or '' for main paper."""
    m = re.search(r"/web/([^/]+)/\d{4}-\d{2}/", url)
    if m:
        return m.group(1)
    return ""


def _discover_from_sitemap() -> list[str]:
    """Fetch sitemap.xml and return the list of article URLs."""
    log.info(f"Fetching sitemap: {SITEMAP_URL}")
    try:
        xml = fetch(SITEMAP_URL, headers={"User-Agent": BROWSER_UA})
    except Exception as e:
        log.error(f"  Failed to fetch sitemap: {e}")
        return []
    urls = re.findall(r"<loc>([^<]+)</loc>", xml)
    # Keep only article URLs (sitemap may include section indexes etc.)
    urls = [u for u in urls if ARTICLE_URL_PATTERN.match(u)]
    # Filter out skipped sections
    urls = [u for u in urls if _section_from_url(u) not in SKIP_SECTIONS]
    log.info(f"  Sitemap yielded {len(urls)} article URLs")
    return urls


def _discover_from_homepage() -> list[str]:
    """Fetch homepage and extract article URLs."""
    log.info(f"Fetching homepage: {HOMEPAGE_URL}")
    try:
        html = fetch(HOMEPAGE_URL, headers={"User-Agent": BROWSER_UA})
    except Exception as e:
        log.error(f"  Failed to fetch homepage: {e}")
        return []
    paths = set(ARTICLE_PATH_PATTERN.findall(html))
    urls = [f"https://www.stdaily.com{p}" for p in paths
            if _section_from_url(f"https://www.stdaily.com{p}") not in SKIP_SECTIONS]
    log.info(f"  Homepage yielded {len(urls)} article URLs")
    return urls


def _clean_text(text: str) -> str:
    """Decode common HTML entities and normalize whitespace."""
    return (
        text.replace("&nbsp;", " ")
        .replace("\u3000", " ")
        .replace("&amp;", "&")
        .replace("&lt;", "<")
        .replace("&gt;", ">")
        .replace("&quot;", '"')
        .replace("&#160;", " ")
        .strip()
    )


def _extract_title(html: str) -> str:
    """Get article title. stdaily puts it in <title> and various h1/h2 tags."""
    # Prefer <h1 class="articel_title"> or similar
    m = re.search(r'<h[12][^>]*class="[^"]*(?:title|article)[^"]*"[^>]*>\s*([^<]+)\s*</h', html)
    if m:
        title = _clean_text(m.group(1))
        if title:
            return title
    # Fall back to <title>, stripping site suffixes
    m = re.search(r"<title>\s*([^<]+?)\s*</title>", html)
    if m:
        title = _clean_text(m.group(1))
        for suffix in ["-科技日报", "_科技日报", "| 科技日报", "- 科技日报"]:
            if title.endswith(suffix):
                title = title[: -len(suffix)].strip()
        return title
    return ""


def _extract_body(html: str) -> str:
    """Extract body text from <div id='printContent'>."""
    start = html.find('id="printContent"')
    if start == -1:
        return ""
    gt = html.find(">", start)
    if gt == -1:
        return ""
    content_start = gt + 1

    end_pos = len(html)
    for marker in [
        "</div><!--printContent end-->",
        '<div id="commentDiv"',
        '<div class="mbjs_con_author"',
        '<div class="info_right"',
        '<div class="article_bottom"',
        '<div class="page_bottom"',
        '<div id="goodcover"',
        '<!-- 编辑: ',
        "【责任编辑",
        "【纠错",
    ]:
        pos = html.find(marker, content_start)
        if pos != -1 and pos < end_pos:
            end_pos = pos

    content = html[content_start:end_pos]

    # Strip HTML
    content = re.sub(r"<br\s*/?\s*>", "\n", content)
    content = re.sub(r"<p[^>]*>", "\n", content)
    content = re.sub(r"</p>", "", content)
    content = re.sub(r"<div[^>]*>", "\n", content)
    content = re.sub(r"</div>", "", content)
    content = re.sub(r"<img[^>]*>", "", content)
    content = re.sub(r"<script[^>]*>.*?</script>", "", content, flags=re.DOTALL)
    content = re.sub(r"<style[^>]*>.*?</style>", "", content, flags=re.DOTALL)
    text = re.sub(r"<[^>]+>", "", content)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n\s*\n", "\n", text)
    text = (
        text.replace("&nbsp;", " ")
        .replace("\u3000", " ")
        .replace("&lt;", "<")
        .replace("&gt;", ">")
        .replace("&amp;", "&")
        .replace("&quot;", '"')
        .strip()
    )
    for cutoff in ["【纠错】", "【责任编辑", "阅读下一篇", "责任编辑："]:
        idx = text.find(cutoff)
        if idx > 0:
            text = text[:idx].strip()
    return text if len(text) > 30 else ""


def _extract_meta(html: str) -> dict:
    """Extract publish time, author/source from stdaily article HTML."""
    meta = {}
    # Typical format: "2026-03-17 07:35:27" inside an info/date div
    m = re.search(r'(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})', html)
    if m:
        meta["date_published"] = m.group(1)
    # Source: "来源：科技日报" or "作者：..."
    m = re.search(r"来源[：:]\s*([^<\s]{2,30})", html)
    if m:
        meta["source"] = m.group(1).strip()
    m = re.search(r"作者[：:]\s*([^<\s]{2,30})", html)
    if m:
        meta["author"] = m.group(1).strip()
    return meta


def crawl(conn, deep: bool = False, list_only: bool = False) -> int:
    """Crawl stdaily articles.

    Args:
        deep: if True, discover from both sitemap AND homepage (more unique URLs)
        list_only: if True, print URLs without fetching body
    """
    store_site(conn, SITE_KEY, SITE_CFG)

    # --- Discovery ---
    seen = set()
    urls: list[str] = []

    sitemap_urls = _discover_from_sitemap()
    for u in sitemap_urls:
        if u not in seen:
            seen.add(u)
            urls.append(u)

    if deep:
        home_urls = _discover_from_homepage()
        for u in home_urls:
            if u not in seen:
                seen.add(u)
                urls.append(u)

    log.info(f"Total unique URLs: {len(urls)}")

    if list_only:
        for u in urls:
            print(f"  [{_section_from_url(u) or 'main':8s}] {_date_from_url(u)} {u}")
        return len(urls)

    # --- Fetch + store ---
    stored = 0
    skipped = 0
    errors = 0
    for i, url in enumerate(urls):
        existing = conn.execute(
            "SELECT id, body_text_cn FROM documents WHERE url = ?", (url,)
        ).fetchone()
        if existing and existing[1]:
            skipped += 1
            continue

        try:
            html = fetch(url, headers={"User-Agent": BROWSER_UA})
        except Exception as e:
            log.warning(f"  Failed to fetch {url}: {e}")
            errors += 1
            continue

        # stdaily returns a 15175-byte 404 page for dead links with 200 status
        if len(html) == ERROR_PAGE_SIZE or 'id="printContent"' not in html:
            log.debug(f"  Dead link (no printContent): {url}")
            errors += 1
            continue

        title = _extract_title(html)
        if not title:
            log.warning(f"  No title for {url}, skipping")
            errors += 1
            continue

        body_text = _extract_body(html)
        meta = _extract_meta(html)
        date_str = meta.get("date_published", "")[:10]

        doc_id = existing[0] if existing else next_id(conn)
        raw_html_path = save_raw_html(SITE_KEY, doc_id, html)

        store_document(conn, SITE_KEY, {
            "id": doc_id,
            "title": title,
            "publisher": meta.get("source") or "科技日报",
            "keywords": "",
            "abstract": "",
            "date_written": _parse_date(date_str),
            "date_published": date_str,
            "body_text_cn": body_text,
            "url": url,
            "classify_main_name": "媒体报道",
            "raw_html_path": raw_html_path,
        })
        stored += 1

        if stored % 20 == 0:
            conn.commit()
            log.info(
                f"  Progress: {stored} stored, {skipped} skipped, {errors} errors "
                f"({i+1}/{len(urls)})"
            )

        time.sleep(REQUEST_DELAY)

    conn.commit()
    log.info(
        f"=== stdaily: {stored} new, {skipped} skipped, {errors} errors, "
        f"{len(urls)} discovered ==="
    )
    return stored


def main():
    parser = argparse.ArgumentParser(description="Science & Technology Daily Crawler")
    parser.add_argument("--stats", action="store_true", help="Show database stats")
    parser.add_argument("--deep", action="store_true",
                        help="Discover from both sitemap and homepage (~more unique URLs)")
    parser.add_argument("--list-only", action="store_true",
                        help="List article URLs without fetching body text")
    parser.add_argument("--db", type=str,
                        help="Path to SQLite database (default: documents.db)")
    args = parser.parse_args()

    conn = init_db(Path(args.db) if args.db else None)

    if args.stats:
        show_stats(conn)
        conn.close()
        return

    crawl(conn, deep=args.deep, list_only=args.list_only)
    show_stats(conn)
    conn.close()


if __name__ == "__main__":
    main()
