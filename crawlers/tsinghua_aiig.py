"""
Tsinghua AIIG (清华大学人工智能国际治理研究院) crawler.

Crawls research publications from the Institute for AI International Governance
at Tsinghua University. Sections: annual reports, research reports, monographs,
academic papers, and international governance watch (weekly digest).

The site uses a standard university CMS (Visual SiteBuilder) with paginated
HTML listing pages. ~180 items total, 100% AI governance content.

Usage:
    python -m crawlers.tsinghua_aiig                    # Crawl all sections
    python -m crawlers.tsinghua_aiig --section xslw     # One section only
    python -m crawlers.tsinghua_aiig --list-only        # List URLs without fetching
    python -m crawlers.tsinghua_aiig --stats            # Show database stats
    python -m crawlers.tsinghua_aiig --db alt.db        # Write to alternate database
"""

import argparse
import re
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path
from urllib.parse import urljoin

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

SITE_KEY = "tsinghua_aiig"
SITE_CFG = {
    "name": "Tsinghua AIIG (清华大学人工智能国际治理研究院)",
    "base_url": "https://aiig.tsinghua.edu.cn",
    "admin_level": "research",
}

BASE_URL = "https://aiig.tsinghua.edu.cn"
CST = timezone(timedelta(hours=8))
BROWSER_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)

# Sections to crawl.  key -> (Chinese name, listing path, col_id)
# col_id is the numeric folder in /info/COL_ID/DOC_ID.htm — used only for
# filtering hrefs on listing pages so we don't pick up nav links.
SECTIONS = {
    "ndbg":   ("年度报告 (Annual Reports)",      "/yjcg/ndbg.htm",   "1024"),
    "yjbg":   ("研究报告 (Research Reports)",     "/yjcg/yjbg.htm",   "1025"),
    "zzwx":   ("专著文献 (Monographs)",           "/yjcg/zzwx.htm",   "1745"),
    "xslw":   ("学术论文 (Academic Papers)",       "/yjcg/xslw.htm",   "1368"),
    "gjzlgc": ("国际治理观察 (Intl Governance Watch)", "/yjcg/gjzlgc.htm", None),
}


def _parse_date(date_str: str) -> int:
    """Convert 'YYYY年MM月' or 'YYYY.MM.DD' or 'YYYY-MM-DD' to Unix timestamp."""
    if not date_str:
        return 0
    date_str = date_str.strip()
    # "2026年03月" format
    m = re.match(r"(\d{4})年(\d{1,2})月?(?:(\d{1,2})日?)?", date_str)
    if m:
        y, mo = int(m.group(1)), int(m.group(2))
        d = int(m.group(3)) if m.group(3) else 1
        try:
            dt = datetime(y, mo, d, tzinfo=CST)
            return int(dt.timestamp())
        except ValueError:
            return 0
    # "2026.03.23" format (gjzlgc dates)
    m = re.match(r"(\d{4})\.(\d{1,2})\.(\d{1,2})", date_str)
    if m:
        try:
            dt = datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)), tzinfo=CST)
            return int(dt.timestamp())
        except ValueError:
            return 0
    # ISO "YYYY-MM-DD"
    m = re.match(r"(\d{4})-(\d{1,2})-(\d{1,2})", date_str)
    if m:
        try:
            dt = datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)), tzinfo=CST)
            return int(dt.timestamp())
        except ValueError:
            return 0
    return 0


def _date_str_normalize(date_str: str) -> str:
    """Normalize date to YYYY-MM-DD for storage in date_published."""
    if not date_str:
        return ""
    date_str = date_str.strip()
    m = re.match(r"(\d{4})年(\d{1,2})月?(?:(\d{1,2})日?)?", date_str)
    if m:
        y, mo = m.group(1), m.group(2).zfill(2)
        d = m.group(3).zfill(2) if m.group(3) else "01"
        return f"{y}-{mo}-{d}"
    m = re.match(r"(\d{4})\.(\d{1,2})\.(\d{1,2})", date_str)
    if m:
        return f"{m.group(1)}-{m.group(2).zfill(2)}-{m.group(3).zfill(2)}"
    m = re.match(r"(\d{4})-(\d{1,2})-(\d{1,2})", date_str)
    if m:
        return f"{m.group(1)}-{m.group(2).zfill(2)}-{m.group(3).zfill(2)}"
    return ""


def _get_total_and_pages(html: str, items_per_page: int = 3) -> tuple[int, int]:
    """Extract total item count and calculate total pages from pagination div.

    Pagination format: 共N条  with page links.  The CMS shows 3 items per page.
    The page number display may use '...' and not show all page numbers, so we
    compute total_pages from total items / items_per_page.
    """
    m = re.search(r'共(\d+)条', html)
    total = int(m.group(1)) if m else 0
    if total == 0:
        return 0, 1
    total_pages = max(1, (total + items_per_page - 1) // items_per_page)
    return total, total_pages


def _discover_listing_items(html: str, section_key: str, page_url: str) -> list[dict]:
    """Extract article items from a listing page.

    Returns list of dicts with: url, title, excerpt, date (for gjzlgc).
    """
    col_id = SECTIONS[section_key][2]
    items = []

    if section_key == "gjzlgc":
        # gjzlgc has a different layout: <li> with <a href="..."> containing
        # <h5> title, <p> excerpt, <h6><span> date.  Links may be external (WeChat).
        # Restrict to the main content area to avoid nav links.
        content_start = html.find('class="n_titu"')
        if content_start == -1:
            content_start = html.find('class="n_news"')
        if content_start == -1:
            content_start = 0
        content_end = html.find('pb_sys_common', content_start)
        if content_end == -1:
            content_end = html.find('n_footer', content_start)
        if content_end == -1:
            content_end = len(html)
        content_html = html[content_start:content_end]

        for m in re.finditer(
            r'<li>\s*<a\s+href="([^"]*)"[^>]*title="([^"]*)"',
            content_html,
        ):
            href, title = m.group(1), m.group(2)
            if not title or not href:
                continue
            # Look for date in the <h6> after this match
            snippet = content_html[m.start():m.start() + 3000]
            date_m = re.search(r'class="img2">(\d{4}\.\d{2}\.\d{2})', snippet)
            date_str = date_m.group(1) if date_m else ""
            # Excerpt
            excerpt_m = re.search(r'<p>(.*?)</p>', snippet, re.DOTALL)
            excerpt = ""
            if excerpt_m:
                excerpt = re.sub(r'<[^>]+>', '', excerpt_m.group(1)).strip()

            # Resolve URL
            if href.startswith("http"):
                url = href
            else:
                url = urljoin(page_url, href)
            items.append({
                "url": url,
                "title": title.strip(),
                "excerpt": excerpt,
                "date": date_str,
            })
    else:
        # Standard sections: <li><a href="../info/COL_ID/DOC_ID.htm" title="...">
        for m in re.finditer(
            r'<a\s+href="([^"]*?/info/\d+/\d+\.htm)"[^>]*title="([^"]*)"',
            html,
        ):
            href, title = m.group(1), m.group(2)
            if not title:
                continue
            url = urljoin(page_url, href)
            # Excerpt from <p> tag right after
            snippet = html[m.start():m.start() + 2000]
            excerpt_m = re.search(r'<p>(.*?)</p>', snippet, re.DOTALL)
            excerpt = ""
            if excerpt_m:
                excerpt = re.sub(r'<[^>]+>', '', excerpt_m.group(1)).strip()
            items.append({
                "url": url,
                "title": title.strip(),
                "excerpt": excerpt,
                "date": "",
            })

    return items


def _build_page_urls(section_key: str, total_pages: int) -> list[str]:
    """Build URLs for all pagination pages of a section.

    Page 1 = the base listing URL (e.g. /yjcg/xslw.htm)
    Page 2 = /yjcg/xslw/(total_pages - 1).htm
    Page 3 = /yjcg/xslw/(total_pages - 2).htm
    ...
    Page N = /yjcg/xslw/1.htm
    """
    base_path = SECTIONS[section_key][1]
    slug = section_key
    urls = [BASE_URL + base_path]  # page 1
    for page_num in range(2, total_pages + 1):
        # Page 2 => (total_pages - 1).htm, page 3 => (total_pages - 2).htm, etc.
        file_num = total_pages - page_num + 1
        urls.append(f"{BASE_URL}/yjcg/{slug}/{file_num}.htm")
    return urls


def _extract_article(html: str) -> dict:
    """Extract metadata and body text from an article detail page."""
    meta = {}

    # Title from <div class="title"><h3><span>...</span></h3>
    m = re.search(r'<div\s+class="title">\s*<h3><span>(.*?)</span></h3>', html, re.DOTALL)
    if m:
        meta["title"] = re.sub(r'<[^>]+>', '', m.group(1)).strip()

    # Author from 作者：...
    m = re.search(r'作者：([^<]*)', html)
    if m:
        author = m.group(1).strip()
        if author:
            meta["author"] = author

    # Date from 发表日期：...
    m = re.search(r'发表日期：([^<]*)', html)
    if m:
        meta["date_raw"] = m.group(1).strip()

    # Description from <META Name="description" Content="...">
    # There may be multiple description meta tags; find the non-empty one.
    for m in re.finditer(r'<META\s+Name="description"\s+Content="([^"]*)"', html, re.IGNORECASE):
        desc = m.group(1).strip()
        if len(desc) > 10:
            meta["abstract"] = desc
            break

    # Body text from <div id="vsb_content">
    start = html.find('id="vsb_content"')
    if start != -1:
        gt = html.find(">", start)
        if gt != -1:
            content_start = gt + 1
            # Find end of vsb_content div — look for closing markers
            end_pos = len(html)
            for marker in ['id="div_vote_id"', '<section id="ar_fot"',
                           '<!-- 附件 -->', '<UL style="list-style-type:none',
                           '<!--============================主体 结束']:
                pos = html.find(marker, content_start)
                if pos != -1 and pos < end_pos:
                    end_pos = pos
            content = html[content_start:end_pos]
            text = _html_to_text(content)
            if len(text) > 30:
                meta["body_text_cn"] = text

    # Attachments — PDF links
    attachments = []
    for m in re.finditer(
        r'<a\s+href="(/system/_content/download\.jsp[^"]*)"[^>]*>(.*?)</a>',
        html, re.DOTALL,
    ):
        att_url = BASE_URL + m.group(1)
        att_name = re.sub(r'<[^>]+>', '', m.group(2)).strip()
        if att_name:
            attachments.append({"url": att_url, "name": att_name})

    if attachments:
        import json
        meta["attachments_json"] = json.dumps(attachments, ensure_ascii=False)

    return meta


def _html_to_text(html_content: str) -> str:
    """Convert HTML fragment to plain text."""
    text = html_content
    # Remove script/style blocks
    text = re.sub(r'<script[^>]*>.*?</script>', '', text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.DOTALL | re.IGNORECASE)
    # Block elements to newlines
    text = re.sub(r'<br\s*/?\s*>', '\n', text)
    text = re.sub(r'<p[^>]*>', '\n', text)
    text = re.sub(r'</p>', '', text)
    text = re.sub(r'<div[^>]*>', '\n', text)
    text = re.sub(r'</div>', '', text)
    text = re.sub(r'<h\d[^>]*>', '\n', text)
    text = re.sub(r'</h\d>', '\n', text)
    # Remove images
    text = re.sub(r'<img[^>]*>', '', text)
    # Remove all remaining tags
    text = re.sub(r'<[^>]+>', '', text)
    # Decode entities
    text = (
        text.replace("&nbsp;", " ")
        .replace("\u3000", " ")
        .replace("&lt;", "<")
        .replace("&gt;", ">")
        .replace("&amp;", "&")
        .replace("&quot;", '"')
    )
    # Collapse whitespace
    text = re.sub(r'[ \t]+', ' ', text)
    text = re.sub(r'\n\s*\n', '\n', text)
    return text.strip()


def crawl(conn, section_filter: str = None, list_only: bool = False):
    """Crawl Tsinghua AIIG publications."""
    store_site(conn, SITE_KEY, SITE_CFG)

    sections_to_crawl = {}
    if section_filter:
        if section_filter not in SECTIONS:
            log.error(f"Unknown section '{section_filter}'. "
                      f"Available: {', '.join(SECTIONS.keys())}")
            return 0
        sections_to_crawl[section_filter] = SECTIONS[section_filter]
    else:
        sections_to_crawl = SECTIONS

    total_stored = 0
    total_skipped = 0

    for section_key, (section_name, listing_path, col_id) in sections_to_crawl.items():
        log.info(f"--- Section: {section_name} ---")

        # Fetch first listing page
        first_url = BASE_URL + listing_path
        try:
            first_html = fetch(first_url, headers={"User-Agent": BROWSER_UA})
        except Exception as e:
            log.error(f"  Failed to fetch listing page {first_url}: {e}")
            continue

        total_items, total_pages = _get_total_and_pages(first_html)
        log.info(f"  {total_items} items across {total_pages} pages")

        # Collect all items across pages
        all_items = _discover_listing_items(first_html, section_key, first_url)
        log.info(f"  Page 1: {len(all_items)} items")

        if total_pages > 1:
            page_urls = _build_page_urls(section_key, total_pages)
            for page_idx, page_url in enumerate(page_urls[1:], start=2):
                time.sleep(REQUEST_DELAY)
                try:
                    page_html = fetch(page_url, headers={"User-Agent": BROWSER_UA})
                except Exception as e:
                    log.warning(f"  Failed to fetch page {page_idx}: {e}")
                    continue
                page_items = _discover_listing_items(page_html, section_key, page_url)
                log.info(f"  Page {page_idx}: {len(page_items)} items")
                all_items.extend(page_items)

        # Deduplicate by URL
        seen_urls = set()
        unique_items = []
        for item in all_items:
            if item["url"] not in seen_urls:
                seen_urls.add(item["url"])
                unique_items.append(item)
        all_items = unique_items

        log.info(f"  Total unique items: {len(all_items)}")

        if list_only:
            for item in all_items:
                print(f"  [{section_key}] {item['title'][:60]}  {item['url']}")
            total_stored += len(all_items)
            continue

        stored = 0
        skipped = 0

        for i, item in enumerate(all_items):
            url = item["url"]

            # Skip if already crawled with body text
            existing = conn.execute(
                "SELECT id, body_text_cn FROM documents WHERE url = ?", (url,)
            ).fetchone()
            if existing and existing[1]:
                skipped += 1
                continue

            # For gjzlgc items linking to WeChat: store listing metadata only
            # (we can't easily scrape mp.weixin.qq.com)
            if "mp.weixin.qq.com" in url:
                doc_id = existing[0] if existing else next_id(conn)
                date_pub = _date_str_normalize(item.get("date", ""))
                store_document(conn, SITE_KEY, {
                    "id": doc_id,
                    "title": item["title"],
                    "publisher": "清华大学人工智能国际治理研究院",
                    "abstract": item.get("excerpt", ""),
                    "date_written": _parse_date(item.get("date", "")),
                    "date_published": date_pub,
                    "body_text_cn": item.get("excerpt", ""),
                    "url": url,
                    "classify_genre_name": section_name,
                })
                stored += 1
                continue

            # Fetch detail page
            time.sleep(REQUEST_DELAY)
            try:
                detail_html = fetch(url, headers={"User-Agent": BROWSER_UA})
            except Exception as e:
                log.warning(f"  Failed to fetch {url}: {e}")
                continue

            meta = _extract_article(detail_html)
            title = meta.get("title") or item["title"]
            if not title:
                log.warning(f"  No title for {url}, skipping")
                continue

            doc_id = existing[0] if existing else next_id(conn)
            date_raw = meta.get("date_raw", "")
            date_pub = _date_str_normalize(date_raw)

            raw_html_path = save_raw_html(SITE_KEY, doc_id, detail_html)

            store_document(conn, SITE_KEY, {
                "id": doc_id,
                "title": title,
                "publisher": meta.get("author", "清华大学人工智能国际治理研究院"),
                "abstract": meta.get("abstract", item.get("excerpt", "")),
                "date_written": _parse_date(date_raw),
                "date_published": date_pub,
                "body_text_cn": meta.get("body_text_cn", ""),
                "url": url,
                "classify_genre_name": section_name,
                "attachments_json": meta.get("attachments_json", "[]"),
                "raw_html_path": raw_html_path,
            })
            stored += 1

            if stored % 10 == 0:
                conn.commit()
                log.info(f"  Progress: {stored} stored, {skipped} skipped "
                         f"({i+1}/{len(all_items)})")

        conn.commit()
        log.info(f"  {section_name}: {stored} new, {skipped} skipped")
        total_stored += stored
        total_skipped += skipped

    log.info(f"=== Tsinghua AIIG: {total_stored} new, {total_skipped} skipped ===")
    return total_stored


def main():
    parser = argparse.ArgumentParser(
        description="Tsinghua AIIG (清华大学人工智能国际治理研究院) Crawler"
    )
    parser.add_argument("--stats", action="store_true", help="Show database stats")
    parser.add_argument("--list-only", action="store_true",
                        help="List article URLs without fetching")
    parser.add_argument("--section", type=str,
                        choices=list(SECTIONS.keys()),
                        help="Crawl only one section")
    parser.add_argument("--db", type=str,
                        help="Path to SQLite database (default: documents.db)")
    args = parser.parse_args()

    conn = init_db(Path(args.db) if args.db else None)

    if args.stats:
        show_stats(conn)
        conn.close()
        return

    crawl(conn, section_filter=args.section, list_only=args.list_only)
    show_stats(conn)
    conn.close()


if __name__ == "__main__":
    main()
