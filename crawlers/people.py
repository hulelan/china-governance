"""
People's Daily (人民日报) crawler.

Crawls editorial and commentary articles from opinion.people.com.cn,
the official CPC newspaper's opinion section. These editorials signal
policy direction before formal documents are issued.

The opinion section is organized into named columns (栏目), each with
a paginated HTML listing page. Articles have rich meta tags and
structured body content.

Sections (ordered by political significance):
    shelun        — 社论 (Editorials — highest-level CPC policy signals)
    benbao        — 本报评论员 (Staff Commentator — formal editorial line)
    renzhongping  — 任仲平 (Major signed commentaries — major policy)
    renping       — 任平 (Signed commentaries)
    zhongyin      — 仲音 (Signed commentaries)
    renmin_luntan — 人民论坛 (People's Forum — governance/ideology)
    renmin_shiping— 人民时评 (People's Commentary — current affairs)
    renmin_guandian— 人民观点 (People's Perspectives — analytical)
    pinglun_guancha— 评论员观察 (Commentator Watch)
    jinritang     — 今日谈 (Today's Talk — short daily editorials)
    wanghai_lou   — 望海楼 (Wanghai Tower — international commentary)
    renmin_ruiping— 人民锐评 (Sharp Commentary — rapid response)
    xianchangpinglun— 现场评论 (On-scene Commentary)
    jinshe_ping   — 金社平 (Economic commentary)
    huanyu_ping   — 寰宇平 (Global commentary)
    zhongsheng    — 钟声 (International affairs commentary)
    heyin         — 和音 (Harmony Voice — diplomacy commentary)

Usage:
    python -m crawlers.people                              # Crawl all sections
    python -m crawlers.people --section shelun             # Editorials only
    python -m crawlers.people --section renmin_ruiping     # Sharp commentary
    python -m crawlers.people --stats                      # Show database stats
    python -m crawlers.people --list-only                  # List URLs only
    python -m crawlers.people --db /tmp/people.db          # Alternate database
    python -m crawlers.people --pages 3                    # Max pages per section
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

SITE_KEY = "people"
SITE_CFG = {
    "name": "People's Daily (人民日报)",
    "base_url": "http://opinion.people.com.cn",
    "admin_level": "media",
}

CST = timezone(timedelta(hours=8))
BROWSER_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)

# Each section maps to a listing page path under opinion.people.com.cn.
# The path is appended to the base: http://opinion.people.com.cn/GB/{path}/index.html
# Pagination: index.html (page 1), index2.html (page 2), etc.
SECTIONS = {
    "shelun": {
        "name": "社论 (Editorials)",
        "path": "8213/49160/49179",
    },
    "benbao": {
        "name": "本报评论员 (Staff Commentator)",
        "path": "8213/49160/49217",
    },
    "renzhongping": {
        "name": "任仲平 (Major Signed Commentary)",
        "path": "8213/49160/49205",
    },
    "renping": {
        "name": "任平 (Signed Commentary)",
        "path": "8213/49160/457595",
    },
    "zhongyin": {
        "name": "仲音 (Signed Commentary)",
        "path": "8213/49160/457596",
    },
    "renmin_luntan": {
        "name": "人民论坛 (People's Forum)",
        "path": "8213/49160/49220",
    },
    "renmin_shiping": {
        "name": "人民时评 (People's Commentary)",
        "path": "8213/49160/49219",
    },
    "renmin_guandian": {
        "name": "人民观点 (People's Perspectives)",
        "path": "8213/49160/385787",
    },
    "pinglun_guancha": {
        "name": "评论员观察 (Commentator Watch)",
        "path": "8213/49160/457597",
    },
    "jinritang": {
        "name": "今日谈 (Today's Talk)",
        "path": "8213/49160/49221",
    },
    "wanghai_lou": {
        "name": "望海楼 (Wanghai Tower — International)",
        "path": "8213/49160/54773",
    },
    "renmin_ruiping": {
        "name": "人民锐评 (Sharp Commentary)",
        "path": "436867",
    },
    "xianchangpinglun": {
        "name": "现场评论 (On-scene Commentary)",
        "path": "8213/49160/457598",
    },
    "jinshe_ping": {
        "name": "金社平 (Economic Commentary)",
        "path": "8213/49160/461999",
    },
    "huanyu_ping": {
        "name": "寰宇平 (Global Commentary)",
        "path": "8213/49160/461964",
    },
    "zhongsheng": {
        "name": "钟声 (International Affairs Commentary)",
        "path": "8213/49160/461972",
    },
    "heyin": {
        "name": "和音 (Harmony Voice — Diplomacy)",
        "path": "8213/49160/461963",
    },
}

DEFAULT_MAX_PAGES = 5  # ~100 articles per section (20 per page)


def _parse_date(date_str: str) -> int:
    """Convert 'YYYY-MM-DD' to Unix timestamp at midnight CST."""
    if not date_str:
        return 0
    try:
        dt = datetime.strptime(date_str.strip()[:10], "%Y-%m-%d").replace(tzinfo=CST)
        return int(dt.timestamp())
    except ValueError:
        return 0


def _build_full_url(href: str) -> str:
    """Convert a relative href to a full URL on people.com.cn."""
    href = href.strip()
    if href.startswith("http"):
        return href
    if href.startswith("/"):
        return f"http://opinion.people.com.cn{href}"
    return ""


def _fetch_listing(section_key: str, max_pages: int = DEFAULT_MAX_PAGES) -> list[dict]:
    """Fetch paginated listing pages for a section, return article metadata.

    Each listing page contains ~20 article links in <li> tags:
        <li><a href='/n1/2026/0313/c461529-40680977.html'>title</a>
            <i class=gray> 2026-03-13 </i></li>
    """
    sec = SECTIONS[section_key]
    base_path = f"http://opinion.people.com.cn/GB/{sec['path']}"
    articles = []
    seen_urls = set()

    for page_num in range(1, max_pages + 1):
        if page_num == 1:
            page_url = f"{base_path}/index.html"
        else:
            page_url = f"{base_path}/index{page_num}.html"

        log.info(f"  Fetching listing page {page_num}: {page_url}")

        try:
            html = fetch(page_url, headers={"User-Agent": BROWSER_UA})
        except Exception as e:
            if page_num == 1:
                log.error(f"  Failed to fetch first page for {section_key}: {e}")
            else:
                log.info(f"  Page {page_num} not available (end of pagination)")
            break

        # Extract articles from <li> tags
        # Pattern: <li...><a href='/n1/YYYY/MMDD/cNNNNNN-NNNNNNN.html' target="_blank">title</a> ... YYYY-MM-DD ...
        page_articles = []
        for m in re.finditer(
            r"<li[^>]*>\s*<a\s+href='(/n1/[^']+)'\s+target=\"_blank\">\s*"
            r"(.*?)\s*</a>\s*(.*?)</li>",
            html,
            re.DOTALL,
        ):
            href = m.group(1)
            title = re.sub(r"<[^>]+>", "", m.group(2)).strip()
            rest = m.group(3)

            # Extract date from rest (e.g. <i class=gray> 2026-03-13 </i>)
            date_match = re.search(r"(\d{4}-\d{2}-\d{2})", rest)
            date_str = date_match.group(1) if date_match else ""

            full_url = _build_full_url(href)
            if not full_url or not title:
                continue
            if full_url in seen_urls:
                continue
            seen_urls.add(full_url)

            page_articles.append({
                "url": full_url,
                "title": title,
                "date": date_str,
                "section": section_key,
            })

        if not page_articles:
            log.info(f"  Page {page_num}: no articles found, stopping pagination")
            break

        articles.extend(page_articles)
        log.info(f"  Page {page_num}: {len(page_articles)} articles")

        # Check if there's a next page link
        next_page = f"index{page_num + 1}.html"
        if next_page not in html and page_num > 1:
            break

        time.sleep(REQUEST_DELAY)

    return articles


def _extract_body(html: str) -> str:
    """Extract body text from a People's Daily article page.

    Two templates exist:
      - New template: body inside <div id="rm_txt_zw">...</div>
      - Old template: body inside <div id="p_content">...</div>
    """
    start = html.find('id="rm_txt_zw"')
    if start == -1:
        # Old template: <div id="p_content">
        start = html.find('id="p_content"')
    if start == -1:
        # Fallback: try rm_txt_con
        start = html.find('class="rm_txt_con')
    if start == -1:
        return ""

    # Find the opening tag's closing >
    gt = html.find(">", start)
    if gt == -1:
        return ""

    content_start = gt + 1

    # Find end: look for common markers after the body
    end_pos = len(html)
    for marker in [
        '<div class="edit cf">',      # editor attribution (责编) — new template
        '<div class="edit"',           # editor attribution — old template
        '<div class="zdfy',            # translation section
        '<div class="box_pic"></div>\n\t\t\t\t</div>',  # end of rm_txt_zw
        '<p class="paper_num">',       # share section
        '<div class="rm_relevant',     # related articles
        '<div class="share-wrap',      # share section — old template
        '<!--copyright-->',
        '<div class="rm_ranking',      # ranking sidebar
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
    content = re.sub(r"<center>.*?</center>", "", content, flags=re.DOTALL)
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
    for cutoff in ["【纠错】", "（责编：", "（责任编辑", "分享让更多人看到"]:
        idx = text.find(cutoff)
        if idx > 0:
            text = text[:idx].strip()
    return text if len(text) > 30 else ""


def _extract_meta_from_html(html: str) -> dict:
    """Extract article metadata from HTML meta tags and page structure."""
    meta = {}

    # Title from <h1>
    m = re.search(r"<h1>([^<]+)</h1>", html)
    if m:
        meta["title"] = m.group(1).strip()

    # Publish date from meta tag
    m = re.search(r'name="publishdate"\s+content="([^"]+)"', html)
    if m:
        meta["date_published"] = m.group(1).strip()

    # Source from meta tag
    m = re.search(r'name="source"\s+content="([^"]+)"', html)
    if m:
        source_raw = m.group(1).strip()
        # Clean up: "来源：人民网-观点频道 原创稿" -> "人民网-观点频道"
        source = re.sub(r"^来源[：:]\s*", "", source_raw)
        source = re.sub(r"\s*原创稿$", "", source)
        meta["source"] = source

    # Content ID from meta tag (useful for dedup)
    m = re.search(r'name="contentid"\s+content="([^"]+)"', html)
    if m:
        meta["content_id"] = m.group(1).strip()

    # Description/abstract from meta tag
    m = re.search(r'name="description"\s+content="([^"]+)"', html)
    if m:
        desc = m.group(1).strip()
        if len(desc) > 10:
            meta["abstract"] = desc

    # Author from <div class="author cf">
    m = re.search(r'class="author[^"]*">\s*([^<]+)', html)
    if m:
        author = m.group(1).strip()
        if author and author != "2055":  # Skip numeric editor IDs
            meta["author"] = author

    # Keywords
    m = re.search(r'name="keywords"\s+content="([^"]+)"', html)
    if m:
        kw = m.group(1).strip()
        if kw:
            meta["keywords"] = kw

    return meta


def crawl(conn, sections: list[str] = None, list_only: bool = False,
          max_pages: int = DEFAULT_MAX_PAGES):
    """Crawl People's Daily editorial articles from the specified sections."""
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

        articles = _fetch_listing(section_key, max_pages=max_pages)
        log.info(f"  Found {len(articles)} articles in listing")

        if list_only:
            for a in articles:
                print(f"  [{a['date']}] {a['title'][:70]}  {a['url']}")
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

            # Fetch article page for body text and metadata
            try:
                article_html = fetch(url, headers={"User-Agent": BROWSER_UA})
            except Exception as e:
                log.warning(f"  Failed to fetch {url}: {e}")
                continue

            body_text = _extract_body(article_html)
            html_meta = _extract_meta_from_html(article_html)

            # Use listing metadata as primary, HTML meta as fallback
            title = article["title"] or html_meta.get("title", "")
            if not title:
                log.warning(f"  No title for {url}, skipping")
                continue

            date_str = html_meta.get("date_published", article["date"])[:10]
            source = html_meta.get("source", "人民日报")
            author = html_meta.get("author", "")

            # Build publisher string
            publisher = "人民日报"
            if author:
                publisher = f"人民日报 ({author})"

            doc_id = existing[0] if existing else next_id(conn)
            raw_html_path = save_raw_html(SITE_KEY, doc_id, article_html)

            store_document(conn, SITE_KEY, {
                "id": doc_id,
                "title": title,
                "publisher": publisher,
                "keywords": html_meta.get("keywords", ""),
                "abstract": html_meta.get("abstract", ""),
                "date_written": _parse_date(date_str),
                "date_published": date_str,
                "body_text_cn": body_text,
                "url": url,
                "classify_main_name": "媒体报道",
                "classify_genre_name": sec["name"].split("(")[0].strip(),
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
        f"=== People's Daily total: {total_stored} new, "
        f"{total_skipped} skipped ==="
    )
    return total_stored


def main():
    parser = argparse.ArgumentParser(
        description="People's Daily (人民日报) Crawler"
    )
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
    parser.add_argument(
        "--pages", type=int, default=DEFAULT_MAX_PAGES,
        help=f"Max listing pages per section (default: {DEFAULT_MAX_PAGES})",
    )
    args = parser.parse_args()

    conn = init_db(Path(args.db) if args.db else None)

    if args.stats:
        show_stats(conn)
        conn.close()
        return

    sections = [args.section] if args.section else None
    crawl(conn, sections=sections, list_only=args.list_only,
          max_pages=args.pages)
    show_stats(conn)
    conn.close()


if __name__ == "__main__":
    main()
