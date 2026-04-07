"""
Guancha / Observer Network (观察者网 / guancha.cn) crawler.

Guancha is an influential semi-independent Chinese news/commentary site based
in Shanghai. Its content sits outside official state media but is ideologically
aligned with a nationalist/developmentalist reading of Chinese policy. We
include it for research value: it shows how tech/economic/foreign policy gets
framed *outside* the government's own voice, and what narratives circulate
among policy-engaged Chinese readers.

Discovery surfaces:
    homepage /                              — ~185 article links (all sections mixed)
    /{section}                              — in-section listings for each channel
    columnist pages (e.g. /GuanJinRong)     — author-page articles

URL patterns:
    Desktop: https://www.guancha.cn/{section}/{YYYY}_{MM}_{DD}_{id}.shtml
    Mobile:  https://m.guancha.cn/{section}/{YYYY}_{MM}_{DD}_{id}.shtml

Section pages with real content (discovered empirically):
    politics, economy, internation, qiche, kegongliliang, xinzhiguanchasuo,
    xinqiang

Some section slugs (society, military, zhongguo) fall back to the homepage —
meaning those channels don't have standalone listing pages. We skip those.

Columnist pages are included per user request for research on whether named
authors get referenced/cited differently than staff-written pieces. Each
columnist has a slug like /GuanJinRong, /ZhaoGang, /TuZhuXi etc. — we
discover them from the homepage and follow them in --deep mode.

Limitation: no pagination on section pages, no public archive. The "deep"
mode simply fetches more listing pages per run; true historical backfill is
not available without an external source.

Body extraction: <div class="content all-txt"> on desktop pages.

Usage:
    python -m crawlers.guancha                  # MVP: homepage only (~185 articles)
    python -m crawlers.guancha --deep           # Deep: homepage + all sections + columnists
    python -m crawlers.guancha --stats          # Show database stats
    python -m crawlers.guancha --list-only      # List URLs without fetching
    python -m crawlers.guancha --db alt.db      # Write to alternate database
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

SITE_KEY = "guancha"
SITE_CFG = {
    "name": "Guancha / Observer Network (观察者网)",
    "base_url": "https://www.guancha.cn",
    "admin_level": "media",
}

HOMEPAGE_URL = "https://www.guancha.cn/"

CST = timezone(timedelta(hours=8))
BROWSER_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)

# Sections that have real listing pages (confirmed empirically).
SECTION_PAGES = [
    "politics", "economy", "internation", "qiche",
    "kegongliliang", "xinzhiguanchasuo", "xinqiang",
]

# Homepage size is ~350KB — any non-section URL that returns this is a
# fallback to the homepage (nginx catch-all), so we skip those.
HOMEPAGE_SIZE_MIN = 340000

# URL pattern for guancha articles on both desktop and mobile.
# Example: /economy/2024_07_11_741115.shtml
#          /GuanJinRong/2017_07_27_420211.shtml
ARTICLE_PATH_PATTERN = re.compile(
    r"/([a-zA-Z_][a-zA-Z_0-9]*)/(\d{4})_(\d{2})_(\d{2})_(\d+)(?:_s)?\.shtml"
)

# Exclude non-article slugs that look like article paths.
EXCLUDE_SLUGS = {"Search", "df888"}

# Guancha articles with these markers have no readable body — the
# `<div class="content all-txt">` container is present but empty and the
# page contains a JS redirect to one of these external targets.
#
# We STORE these as title-only rows (not skip) so the corpus retains a
# record that the article existed, with the redirect target encoded in
# `classify_genre_name` for later filtering and analysis. The body stays
# empty as a flag.
#
# An empirical survey found 82% of empty-body guancha pages are paywalled
# member content. The remaining ~18% redirect to Xinhua or CCTV.
REDIRECT_MARKERS = {
    "user.guancha.cn/main/content": "paywall_member",   # paid 观察员 content
    "h.xinhuaxmt.com/vh512/share":  "redirect_xinhua",  # Xinhua SPA mirror
    "news.cctv.com/tiantianxuexi":  "redirect_cctv",    # CCTV 天天学习 program
}


def _detect_redirect(html: str) -> str:
    """Return the redirect-type label if this page is a known empty-body
    redirect target, else empty string."""
    for marker, label in REDIRECT_MARKERS.items():
        if marker in html:
            return label
    return ""


def _parse_date(y: str, m: str, d: str) -> int:
    """Convert Y/M/D strings to Unix timestamp (midnight CST)."""
    try:
        dt = datetime(int(y), int(m), int(d), tzinfo=CST)
        return int(dt.timestamp())
    except ValueError:
        return 0


def _extract_article_links(html: str) -> list[tuple[str, str]]:
    """Return list of (section, url) tuples from any guancha HTML listing."""
    seen = set()
    out = []
    for m in ARTICLE_PATH_PATTERN.finditer(html):
        section, y, mo, d, aid = m.groups()
        if section in EXCLUDE_SLUGS:
            continue
        path = f"/{section}/{y}_{mo}_{d}_{aid}.shtml"
        url = f"https://www.guancha.cn{path}"
        if url in seen:
            continue
        seen.add(url)
        out.append((section, url))
    return out


def _fetch_listing(url: str, label: str) -> list[tuple[str, str]]:
    """Fetch one listing page and return (section, url) tuples."""
    log.info(f"  Fetching {label}: {url}")
    try:
        html = fetch(url, headers={"User-Agent": BROWSER_UA})
    except Exception as e:
        log.warning(f"    Failed: {e}")
        return []
    # Guancha returns the homepage as a fallback for unknown URLs; detect that.
    if url != HOMEPAGE_URL and len(html) >= HOMEPAGE_SIZE_MIN:
        log.debug(f"    {url} fell back to homepage, skipping")
        return []
    return _extract_article_links(html)


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
    """Extract article title from guancha HTML.

    Guancha has two page templates:
      1. Normal (economy, internation, columnists): title in the <title> tag.
      2. Political speeches (some politics pages): a double-<html> document
         where the first shell is empty ('<title></title>') and the real
         title appears in an <h3> immediately before <div class="content all-txt">.

    We try <title> first (picking the first *non-empty* one in case there are
    multiple), then fall back to the last h1/h2/h3/h4 before the body
    container.
    """
    # 1. Non-empty <title> tag
    for m in re.finditer(r"<title>\s*([^<]+?)\s*</title>", html):
        t = _clean_text(m.group(1))
        if t:
            for suffix in ["-观察者网", "_观察者网", "- 观察者网"]:
                if t.endswith(suffix):
                    t = t[: -len(suffix)].strip()
            return t

    # 2. Heading just before the body container (politics speech template)
    body_pos = html.find('class="content all-txt"')
    if body_pos == -1:
        body_pos = len(html)
    head_window = html[max(0, body_pos - 2000):body_pos]
    headings = re.findall(r"<(h[1-6])[^>]*>\s*([^<]{3,200})\s*</\1>", head_window)
    if headings:
        # Take the last (closest to body)
        tag, text = headings[-1]
        text = _clean_text(text)
        if text:
            return text

    return ""


def _extract_body(html: str) -> str:
    """Extract body text from <div class='content all-txt'>."""
    # Primary desktop container
    start = html.find('class="content all-txt"')
    if start == -1:
        # Mobile variant: <div class="g_content">
        start = html.find('class="g_content"')
    if start == -1:
        return ""
    gt = html.find(">", start)
    if gt == -1:
        return ""
    content_start = gt + 1

    end_pos = len(html)
    for marker in [
        '<div class="content-bottom-ad',
        '<div class="article-other',
        '<div class="kuaixun-new-content',
        '<div class="g_comment',
        '<div class="g_reader',
        '<div class="g_footer',
        '<div class="g_openApp',
        '<div id="comment',
        '<!-- 内容结束',
        "责任编辑：",
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
    for cutoff in ["责任编辑", "本文系观察者网独家稿件", "关键字 ："]:
        idx = text.find(cutoff)
        if idx > 0:
            text = text[:idx].strip()
    return text if len(text) > 30 else ""


def _extract_meta(html: str) -> dict:
    """Extract publish time, source/author from guancha article HTML."""
    meta = {}
    # Publish date: "2026-04-07 10:19:56"
    m = re.search(r"(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}(?::\d{2})?)", html)
    if m:
        meta["date_published"] = m.group(1)
    # Source: "来源：财联社" / "来源：新华社"
    m = re.search(r"来源[：:]\s*([^<\s]{2,30})", html)
    if m:
        meta["source"] = m.group(1).strip()
    # Author: "作者｜XXX" or "文｜XXX"
    m = re.search(r'<meta\s+name="author"\s+content="([^"]+)"', html)
    if m:
        meta["author"] = m.group(1).strip()
    # Abstract from meta description
    m = re.search(r'<meta\s+name="description"\s+content="([^"]{10,})"', html)
    if m:
        meta["abstract"] = m.group(1).strip()
    return meta


def _discover_columnist_sections(homepage_html: str) -> list[str]:
    """Find columnist slugs referenced on the homepage.

    Columnist slugs are CamelCase Pinyin (e.g. GuanJinRong, ZhaoGang, TuZhuXi)
    vs news sections which are lowercase (politics, economy). We identify them
    by finding any section slug from _extract_article_links that starts with
    an uppercase letter.
    """
    links = _extract_article_links(homepage_html)
    sections = set(s for s, _ in links if s and s[0].isupper())
    return sorted(sections)


def crawl(conn, deep: bool = False, list_only: bool = False) -> int:
    """Crawl guancha articles.

    Args:
        deep: if True, also fetch each section listing page and every columnist
              page discovered on the homepage
        list_only: if True, print URLs without fetching bodies
    """
    store_site(conn, SITE_KEY, SITE_CFG)

    seen = set()
    all_links: list[tuple[str, str]] = []

    # 1. Homepage (always)
    log.info("=== Guancha: discovering articles ===")
    try:
        homepage_html = fetch(HOMEPAGE_URL, headers={"User-Agent": BROWSER_UA})
    except Exception as e:
        log.error(f"Failed to fetch homepage: {e}")
        return 0

    for section, url in _extract_article_links(homepage_html):
        if url not in seen:
            seen.add(url)
            all_links.append((section, url))
    log.info(f"  Homepage: {len(all_links)} unique articles")

    # 2. Deep mode: section pages + columnist pages
    if deep:
        # Section listing pages (more in-section articles per page)
        for section in SECTION_PAGES:
            section_url = f"https://www.guancha.cn/{section}"
            for s, url in _fetch_listing(section_url, f"section /{section}"):
                if url not in seen:
                    seen.add(url)
                    all_links.append((s, url))
            time.sleep(REQUEST_DELAY)

        # Columnist pages discovered from homepage
        columnists = _discover_columnist_sections(homepage_html)
        log.info(f"  Found {len(columnists)} columnists on homepage: {columnists[:10]}")
        for slug in columnists:
            col_url = f"https://www.guancha.cn/{slug}"
            for s, url in _fetch_listing(col_url, f"columnist /{slug}"):
                if url not in seen:
                    seen.add(url)
                    all_links.append((s, url))
            time.sleep(REQUEST_DELAY)

    log.info(f"Total unique URLs discovered: {len(all_links)}")

    if list_only:
        for section, url in all_links:
            m = ARTICLE_PATH_PATTERN.search(url)
            date_str = f"{m.group(2)}-{m.group(3)}-{m.group(4)}" if m else ""
            print(f"  [{section:20s}] {date_str} {url}")
        return len(all_links)

    # 3. Fetch + store each article
    stored = 0
    skipped = 0
    errors = 0
    redirect_count = 0
    for i, (section, url) in enumerate(all_links):
        # Skip only if we already have body OR a known redirect label —
        # rerunning the crawler should not re-fetch a known dead link.
        existing = conn.execute(
            "SELECT id, body_text_cn, classify_genre_name FROM documents WHERE url = ?",
            (url,),
        ).fetchone()
        if existing and (existing[1] or existing[2]):
            skipped += 1
            continue

        try:
            html = fetch(url, headers={"User-Agent": BROWSER_UA})
        except Exception as e:
            log.warning(f"  Failed to fetch {url}: {e}")
            errors += 1
            continue

        # Detect known redirect targets. We STORE these as title-only rows
        # tagged with the redirect label so the corpus remembers they
        # existed and we can filter on classify_genre_name later.
        redirect_label = _detect_redirect(html)
        if redirect_label:
            redirect_count += 1

        title = _extract_title(html)
        if not title:
            log.warning(f"  No title for {url}, skipping")
            errors += 1
            continue

        body_text = _extract_body(html)
        meta = _extract_meta(html)

        # Derive date from URL as primary source (always reliable)
        m = ARTICLE_PATH_PATTERN.search(url)
        if m:
            date_str = f"{m.group(2)}-{m.group(3)}-{m.group(4)}"
            date_ts = _parse_date(m.group(2), m.group(3), m.group(4))
        else:
            date_str = meta.get("date_published", "")[:10]
            date_ts = 0

        doc_id = existing[0] if existing else next_id(conn)
        raw_html_path = save_raw_html(SITE_KEY, doc_id, html)

        # Author: for columnist sections (CamelCase slug), the section IS the author
        is_columnist = bool(section and section[0].isupper())
        author = meta.get("author") or (section if is_columnist else "")

        store_document(conn, SITE_KEY, {
            "id": doc_id,
            "title": title,
            "publisher": meta.get("source") or "观察者网",
            "keywords": "",
            "abstract": meta.get("abstract", ""),
            "date_written": date_ts,
            "date_published": date_str,
            "body_text_cn": body_text,
            "url": url,
            # Store section as relation for later filtering/analysis.
            # Columnist sections start uppercase so they're distinguishable.
            "relation": section,
            # Author goes into classify_theme_name for columnist research later.
            "classify_theme_name": author,
            # If this article is a known external redirect (paywall, Xinhua,
            # CCTV), tag it here so we can filter the empty-body rows by reason.
            "classify_genre_name": redirect_label,
            "classify_main_name": "媒体报道",
            "raw_html_path": raw_html_path,
        })
        stored += 1

        if stored % 20 == 0:
            conn.commit()
            log.info(
                f"  Progress: {stored} stored, {skipped} skipped, "
                f"{redirect_count} redirects (title-only), {errors} errors "
                f"({i+1}/{len(all_links)})"
            )

        time.sleep(REQUEST_DELAY)

    conn.commit()
    log.info(
        f"=== guancha: {stored} new ({redirect_count} title-only redirects), "
        f"{skipped} skipped (already crawled), {errors} errors, "
        f"{len(all_links)} discovered ==="
    )
    return stored


def main():
    parser = argparse.ArgumentParser(description="Guancha / Observer Network Crawler")
    parser.add_argument("--stats", action="store_true", help="Show database stats")
    parser.add_argument("--deep", action="store_true",
                        help="Also fetch each section page + all homepage columnists")
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
