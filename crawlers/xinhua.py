"""
Xinhua News Agency (新华社/新华网) crawler.

Crawls articles from www.news.cn via their public JSON datasource API.
Each section page has a Vue.js "superEdit4" frontend that loads article
metadata from static JSON files.  The JSON feeds return up to 1000 articles
with title, date, keywords, author, and source — but no body text.
Body text is fetched from individual article pages (HTML).

Sections:
    tech          — 科技 (technology, AI, digital economy)
    fortune       — 财经 (finance/economy)
    politics_docs — 中央文件发布 (central government documents)
    politics_read — 中央文件解读 (central document analysis/interpretation)

Usage:
    python -m crawlers.xinhua                        # Crawl all sections
    python -m crawlers.xinhua --section tech         # Tech section only
    python -m crawlers.xinhua --section fortune      # Economy section only
    python -m crawlers.xinhua --stats                # Show database stats
    python -m crawlers.xinhua --list-only            # List article URLs
    python -m crawlers.xinhua --db alt.db            # Alternate database
"""

import argparse
import re
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path

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

SITE_KEY = "xinhua"
SITE_CFG = {
    "name": "Xinhua News Agency (新华社/新华网)",
    "base_url": "https://www.news.cn",
    "admin_level": "media",
}

CST = timezone(timedelta(hours=8))
BROWSER_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)

# Each section maps to a JSON datasource endpoint.
# path_prefix is used to build the JSON URL: https://www.news.cn/{path_prefix}/ds_{datasource_id}.json
SECTIONS = {
    "tech": {
        "name": "科技 (Technology)",
        "path_prefix": "tech",
        "datasource_id": "fd79514d92f34849bc8baef7ce3d5aae",
    },
    "fortune": {
        "name": "财经 (Economy/Finance)",
        "path_prefix": "fortune",
        "datasource_id": "b53aac3e4e6342f699a9e2acdd0ee8fd",
    },
    "politics_docs": {
        "name": "中央文件发布 (Central Documents)",
        "path_prefix": "politics/zywj",
        "datasource_id": "fa4d1c1ddde34b3eb63719d67879d727",
    },
    "politics_read": {
        "name": "中央文件解读 (Document Analysis)",
        "path_prefix": "politics/zywj",
        "datasource_id": "751e4d15841642e5b6b636377247b397",
    },
}


def _parse_date(date_str: str) -> int:
    """Convert 'YYYY-MM-DD HH:MM:SS' to Unix timestamp (midnight CST)."""
    if not date_str:
        return 0
    try:
        dt = datetime.strptime(date_str.strip()[:10], "%Y-%m-%d").replace(tzinfo=CST)
        return int(dt.timestamp())
    except ValueError:
        return 0


def _build_full_url(publish_url: str) -> str:
    """Convert a publishUrl (relative or absolute) to a full URL."""
    publish_url = publish_url.strip()
    if publish_url.startswith("http"):
        return publish_url
    if publish_url.startswith("/"):
        return f"https://www.news.cn{publish_url}"
    return ""


def _fetch_listing(section_key: str) -> list[dict]:
    """Fetch the JSON datasource for a section and return article metadata."""
    sec = SECTIONS[section_key]
    json_url = (
        f"https://www.news.cn/{sec['path_prefix']}/"
        f"ds_{sec['datasource_id']}.json"
    )
    log.info(f"  Fetching listing: {json_url}")

    try:
        data = fetch_json(json_url, headers={"User-Agent": BROWSER_UA})
    except Exception as e:
        log.error(f"  Failed to fetch listing for {section_key}: {e}")
        return []

    raw_items = data.get("datasource", [])
    articles = []

    for item in raw_items:
        title = item.get("title", "") or item.get("showTitle", "")
        # Skip items where the title is HTML (link-wrapped) — these are
        # from an older datasource format and lack clean metadata.
        if "<" in title:
            title = re.sub(r"<[^>]+>", "", title).strip()
            if not title:
                continue

        publish_url = item.get("publishUrl", "")
        full_url = _build_full_url(publish_url)
        if not full_url:
            continue
        # Accept both new-style /c.html and old-style /c_NNNNN.htm URLs
        if "/c.html" not in full_url and "/c_" not in full_url:
            continue

        articles.append({
            "url": full_url,
            "title": title,
            "publish_time": item.get("publishTime", ""),
            "keywords": item.get("keywords", ""),
            "author": item.get("author", ""),
            "source": item.get("sourceText", ""),
            "summary": item.get("summary", ""),
            "content_id": item.get("contentId", ""),
            "section": section_key,
        })

    return articles


def _extract_body(html: str) -> str:
    """Extract body text from a Xinhua article page.

    The article body is inside <span id="detailContent"> or
    <div id="detail">.
    """
    # Primary: <span id="detailContent">...</span> (new-style /c.html pages)
    start = html.find('id="detailContent"')
    if start == -1:
        # Fallback: <div id="detail"> (new-style variant)
        start = html.find('id="detail"')
    if start == -1:
        # Fallback: <div class="content clearfix"> (old-style .htm pages)
        start = html.find('class="content clearfix"')
    if start == -1:
        return ""

    # Find the opening tag's closing >
    gt = html.find(">", start)
    if gt == -1:
        return ""

    content_start = gt + 1

    # Find end: look for common markers that follow the article body
    end_pos = len(html)
    for marker in [
        '</span><!--',            # end of detailContent
        '<div class="editor',     # editor attribution
        '<div id="sdgc"',         # related articles sidebar
        '<div class="mfooter',    # mobile footer
        '<div class="pageShare',  # share bar below article
        '<!--责任编辑',             # editor comment
        '<div class="main-right', # right sidebar
        '<div class="columBox',   # old-style related articles
        '<div class="share',      # old-style share bar
        '<div id="fllow',         # old-style follow section
    ]:
        pos = html.find(marker, content_start)
        if pos != -1 and pos < end_pos:
            end_pos = pos

    content = html[content_start:end_pos]

    # Strip HTML to plain text
    content = re.sub(r"<br\s*/?\s*>", "\n", content)
    content = re.sub(r"<p[^>]*>", "\n", content)
    content = re.sub(r"</p>", "", content)
    content = re.sub(r"<div[^>]*>", "\n", content)
    content = re.sub(r"</div>", "", content)
    content = re.sub(r"<img[^>]*>", "", content)
    content = re.sub(r"<style[^>]*>.*?</style>", "", content, flags=re.DOTALL)
    content = re.sub(r"<script[^>]*>.*?</script>", "", content, flags=re.DOTALL)
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
    # Strip trailing editorial boilerplate
    for cutoff in ["【纠错】", "【责任编辑", "阅读下一篇"]:
        idx = text.find(cutoff)
        if idx > 0:
            text = text[:idx].strip()
    return text if len(text) > 30 else ""


def _extract_meta_from_html(html: str) -> dict:
    """Extract title, date, source from article page HTML as fallback."""
    meta = {}

    # Title: <span class="title">...</span>
    m = re.search(r'<span class="title">([^<]+)</span>', html)
    if m:
        meta["title"] = m.group(1).strip()

    # Title fallback: <title> tag
    if "title" not in meta:
        m = re.search(r"<title>([^<]+)</title>", html)
        if m:
            title = m.group(1).strip()
            # Xinhua titles often end with "_新华网" — strip that
            title = re.sub(r"[_\-]新华网$", "", title).strip()
            if title:
                meta["title"] = title

    # Date: from header-time div — <span class="year"><em>2026</em></span>
    #        <span class="day"><em>03</em>/<em>25</em></span>
    #        <span class="time">09:38:30</span>
    m_year = re.search(r'class="year"[^>]*><em>(\d{4})</em>', html)
    m_day = re.search(r'class="day"[^>]*><em>(\d{2})</em>/<em>(\d{2})</em>', html)
    m_time = re.search(r'class="time"[^>]*>(\d{2}:\d{2}:\d{2})', html)
    if m_year and m_day:
        date_str = f"{m_year.group(1)}-{m_day.group(1)}-{m_day.group(2)}"
        if m_time:
            date_str += f" {m_time.group(1)}"
        meta["date_published"] = date_str

    # Date fallback: mobile header "2026-03-25 09:38:30"
    if "date_published" not in meta:
        m = re.search(r'class="info"[^>]*>\s*(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})', html)
        if m:
            meta["date_published"] = m.group(1).strip()

    # Source: <div class="source">来源：经济日报</div>
    m = re.search(r'class="source"[^>]*>来源[：:]\s*([^<]+)', html)
    if m:
        meta["source"] = m.group(1).strip()

    return meta


def crawl(conn, sections: list[str] = None, list_only: bool = False):
    """Crawl Xinhua articles from the specified sections."""
    store_site(conn, SITE_KEY, SITE_CFG)

    if sections is None:
        sections = list(SECTIONS.keys())

    total_stored = 0
    total_skipped = 0

    for section_key in sections:
        if section_key not in SECTIONS:
            log.warning(f"Unknown section: {section_key}")
            continue

        sec = SECTIONS[section_key]
        log.info(f"=== Section: {sec['name']} ({section_key}) ===")

        articles = _fetch_listing(section_key)
        log.info(f"  Found {len(articles)} articles in listing")

        if list_only:
            for a in articles:
                print(f"  [{a['publish_time'][:10]}] {a['title'][:60]}  {a['url']}")
            continue

        stored = 0
        skipped = 0

        for i, article in enumerate(articles):
            url = article["url"]

            # Skip if already crawled with body text
            existing = conn.execute(
                "SELECT id, body_text_cn FROM documents WHERE url = ?", (url,)
            ).fetchone()
            if existing and existing[1]:
                skipped += 1
                continue

            # Fetch article page for body text
            try:
                article_html = fetch(url, headers={"User-Agent": BROWSER_UA})
            except Exception as e:
                log.warning(f"  Failed to fetch {url}: {e}")
                continue

            body_text = _extract_body(article_html)
            html_meta = _extract_meta_from_html(article_html)

            # Use JSON metadata as primary, HTML as fallback
            title = article["title"] or html_meta.get("title", "")
            if not title:
                log.warning(f"  No title for {url}, skipping")
                continue

            date_str = article["publish_time"][:10] or html_meta.get("date_published", "")[:10]
            source = article["source"] or html_meta.get("source", "新华网")

            doc_id = existing[0] if existing else next_id(conn)
            raw_html_path = save_raw_html(SITE_KEY, doc_id, article_html)

            store_document(conn, SITE_KEY, {
                "id": doc_id,
                "title": title,
                "publisher": source,
                "keywords": article.get("keywords", ""),
                "abstract": article.get("summary", ""),
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
                    f"  Progress: {stored} stored, {skipped} skipped "
                    f"({i+1}/{len(articles)})"
                )

            time.sleep(REQUEST_DELAY)

        conn.commit()
        log.info(
            f"  {sec['name']}: {stored} new, {skipped} skipped, "
            f"{len(articles)} in listing"
        )
        total_stored += stored
        total_skipped += skipped

    log.info(
        f"=== Xinhua total: {total_stored} new, {total_skipped} skipped ==="
    )
    return total_stored


def main():
    parser = argparse.ArgumentParser(description="Xinhua News Agency Crawler")
    parser.add_argument("--stats", action="store_true", help="Show database stats")
    parser.add_argument(
        "--list-only", action="store_true",
        help="List article URLs without fetching body text",
    )
    parser.add_argument(
        "--section", type=str,
        help=f"Crawl a specific section: {', '.join(SECTIONS.keys())}",
    )
    parser.add_argument(
        "--db", type=str,
        help="Path to SQLite database (default: documents.db)",
    )
    args = parser.parse_args()

    conn = init_db(Path(args.db) if args.db else None)

    if args.stats:
        show_stats(conn)
        conn.close()
        return

    sections = [args.section] if args.section else None
    crawl(conn, sections=sections, list_only=args.list_only)
    show_stats(conn)
    conn.close()


if __name__ == "__main__":
    main()
