"""
Suzhou Municipality (苏州市) crawler.

Crawls policy documents from www.suzhou.gov.cn.  Suzhou uses an AJAX API
at /szinf/xxgk/interfacesWebZcwj/loadData that returns JSON with pagination.

API endpoint:
  POST /szinf/xxgk/interfacesWebZcwj/loadData?pageSize=15
  Body: pageIndex=N (&channel_id=UUID for section filter)

Response JSON:
  { "data": {
      "allRow": 5005,
      "totalPage": 334,
      "list": [
        { "TITLE": "...", "URL": "http://...", "C_WJBH": "doc number",
          "PUBLISHED_TIME_FORMAT": "YYYY-MM-DD", "C_FWRQ_FORMAT": "YYYY-MM-DD",
          "C_SYH": "index number", "CHANNEL_ID": "...",
          "MANUSCRIPT_ID": "UUID" }
      ]
    }
  }

Detail pages:
  Body:     div.article-content (id="zoomcon")
  Meta:     <meta name="ArticleTitle|PubDate|ContentSource">
            + dl/dd metadata block in div.xxgkml-content
              (索引号, 分类, 发布机构, 发文日期, 文号, 标题, 内容概述)

Sections (by channel_id):
  All:      all policy documents (no filter, ~5000 docs)
  zfwj:     市政府文件 (Municipal government docs)
  zfbgswj:  市政府办公室文件 (Municipal gov office docs)
  zfgz:     市政府规章 (Municipal regulations/令)
  rsxx:     人事信息 (Personnel information)
  szfqt:    市政府其他 (Other municipal gov docs)

Usage:
    python -m crawlers.suzhou                       # Crawl all docs
    python -m crawlers.suzhou --section zfwj        # Municipal gov docs only
    python -m crawlers.suzhou --stats               # Show database stats
    python -m crawlers.suzhou --list-only           # List without fetching bodies
    python -m crawlers.suzhou --db /tmp/suzhou.db   # Write to temp DB
"""

import argparse
import re
import time
import urllib.parse
import urllib.request
import json
from datetime import datetime, timedelta, timezone
from html import unescape
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

SITE_KEY = "suzhou"
SITE_CFG = {
    "name": "Suzhou Municipality",
    "base_url": "http://www.suzhou.gov.cn",
    "admin_level": "municipal",
}

CST = timezone(timedelta(hours=8))

_BASE_URL = "http://www.suzhou.gov.cn"
_API_URL = f"{_BASE_URL}/szinf/xxgk/interfacesWebZcwj/loadData"
_PAGE_SIZE = 15

# Section key -> (display name, channel_id or None for all)
SECTIONS = {
    "all":     ("全部政策文件", None),
    "zfwj":    ("市政府文件", "dc1a3f5691e541108d5a18bdd028949b"),
    "zfbgswj": ("市政府办公室文件", "32e8b8da70fe416898b0249a9fb113d8"),
    "zfgz":    ("市政府规章", "ac4d3260f9764f0f885f4636c756b9b7"),
    "rsxx":    ("人事信息", "a706a03e5c4d4628a9add3dbb30db8f9"),
    "szfqt":   ("市政府其他", "7def83c2f84a49df91b6f57f872ae150"),
}


def _fetch_api_page(page: int, channel_id: str = None) -> dict:
    """Fetch one page of documents from the Suzhou API.

    Returns the parsed JSON response data dict, or None on error.
    """
    params = {"pageSize": str(_PAGE_SIZE)}
    data = {"pageIndex": str(page)}
    if channel_id:
        data["channel_id"] = channel_id

    url = f"{_API_URL}?{urllib.parse.urlencode(params)}"
    post_data = urllib.parse.urlencode(data).encode("utf-8")

    hdrs = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Referer": f"{_BASE_URL}/szsrmzf/zfxxgkzl/xxgkml.shtml?para=zcwj",
        "Content-Type": "application/x-www-form-urlencoded",
    }
    req = urllib.request.Request(url, data=post_data, headers=hdrs)

    for attempt in range(3):
        try:
            resp = urllib.request.urlopen(req, timeout=20)
            text = resp.read().decode("utf-8", errors="replace")
            return json.loads(text)
        except Exception as e:
            if attempt < 2:
                wait = 2 ** attempt
                log.warning(f"  Retry {attempt+1}/3 for API page {page}: {e}")
                time.sleep(wait)
            else:
                log.error(f"  Failed API page {page}: {e}")
                return None


def _parse_date(date_str: str) -> int:
    """Convert date string to Unix timestamp at midnight CST."""
    date_str = (
        date_str.replace("/", "-")
        .replace("年", "-")
        .replace("月", "-")
        .replace("日", "")
    )
    try:
        dt = datetime.strptime(date_str.strip()[:10], "%Y-%m-%d").replace(
            tzinfo=CST
        )
        return int(dt.timestamp())
    except ValueError:
        return 0


def _extract_meta(html: str) -> dict:
    """Extract metadata from detail page.

    Sources:
    1. <meta> tags (ArticleTitle, PubDate, ContentSource)
    2. dl/dd metadata block in div.xxgkml-content
       (索引号, 分类, 发布机构, 发文日期, 文号, 标题, 内容概述)
    """
    meta = {}

    # Source 1: <meta> tags
    for name in ("ArticleTitle", "PubDate", "ContentSource", "Keywords"):
        m = re.search(
            rf'<meta\s+name="{name}"\s+content="([^"]*)"', html, re.IGNORECASE
        )
        if m:
            meta[name] = m.group(1).strip()

    # Source 2: xxgkml-content metadata block
    # Format:  <label><font>索 引 号：</font></label>
    #          <div class="display-block ...">VALUE</div>
    for m in re.finditer(
        r'<label>\s*<font>\s*([^<]+)\s*</font>\s*</label>\s*'
        r'<div[^>]*class="display-block[^"]*"[^>]*>\s*(.*?)\s*</div>',
        html,
        re.DOTALL,
    ):
        label = m.group(1).strip().rstrip("：:")
        # Clean up &ensp; entities, full-width spaces (\u3000), and whitespace
        label = re.sub(r"[&]\w+;", "", label)
        label = re.sub(r"[\s\u3000\u00a0]+", "", label).strip()
        value = re.sub(r"<[^>]+>", "", m.group(2)).strip()
        if not value:
            continue

        if "索引号" in label:
            meta["identifier"] = value
        elif "发布机构" in label:
            meta["publisher"] = value
        elif "发文日期" in label:
            meta["date_written_str"] = value
        elif "文号" in label:
            meta["document_number"] = value
        elif "时效" in label:
            meta["validity"] = value
        elif "分类" in label:
            # Multiple spans: 二级主题, 一级主题, channel, 体裁
            themes = re.findall(r'<font>([^<]+)</font>', m.group(2))
            if themes:
                meta["classify_theme_name"] = " / ".join(themes)
        elif "内容概述" in label:
            meta["abstract"] = value

    return meta


def _extract_body(html: str) -> str:
    """Extract plain text body from document detail page.

    Suzhou uses div.article-content (id="zoomcon") as the main content
    container, wrapped in a <UCAPCONTENT> tag.
    """
    content = ""
    for pattern in [
        r'<div[^>]*class="article-content"[^>]*>(.*?)</div>\s*(?:<div[^>]*class="article-auxi|</div>)',
        r'<div[^>]*id="zoomcon"[^>]*>(.*?)</div>',
        r'<UCAPCONTENT>(.*?)</UCAPCONTENT>',
        r'<div[^>]*class="[^"]*\bcontent\b[^"]*"[^>]*>(.*?)</div>',
    ]:
        m = re.search(pattern, html, re.DOTALL)
        if m:
            content = m.group(1)
            break

    if not content:
        return ""

    # Replace <br> and </p> with newlines
    content = re.sub(r"<br\s*/?\s*>", "\n", content)
    content = re.sub(r"</p>", "\n", content)
    # Strip HTML tags
    text = re.sub(r"<[^>]+>", "", content)
    # Clean whitespace
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n\s*\n", "\n", text)
    text = text.strip()
    # Unescape HTML entities
    text = unescape(text)
    text = text.replace("\xa0", " ")

    if len(text) > 20:
        return text
    return ""


def crawl_section(
    conn,
    section_key: str,
    section_name: str,
    channel_id: str = None,
    fetch_bodies: bool = True,
):
    """Crawl all pages for a section using the Suzhou API."""
    log.info(f"--- Section: {section_name} ({section_key}) ---")

    # Fetch first page to get total count
    resp = _fetch_api_page(1, channel_id)
    if not resp or not resp.get("data"):
        log.error(f"  Failed to fetch first API page")
        return 0

    total_rows = resp["data"].get("allRow", 0)
    total_pages = resp["data"].get("totalPage", 1)
    log.info(f"  Total: {total_rows} documents across {total_pages} pages")

    all_items = resp["data"].get("list", [])

    # Fetch remaining pages
    for page in range(2, total_pages + 1):
        resp = _fetch_api_page(page, channel_id)
        if not resp or not resp.get("data"):
            log.warning(f"  Failed page {page}/{total_pages}")
            continue
        page_items = resp["data"].get("list", [])
        if not page_items:
            log.info(f"  Empty page {page} — stopping")
            break
        all_items.extend(page_items)

        if page % 20 == 0:
            log.info(f"  Listing progress: {page}/{total_pages} pages, {len(all_items)} items")
        time.sleep(REQUEST_DELAY)

    # Deduplicate by URL
    seen = set()
    deduped = []
    for item in all_items:
        url = item.get("URL", "")
        if url and url not in seen:
            seen.add(url)
            deduped.append(item)
    all_items = deduped
    log.info(f"  Found {len(all_items)} unique document links")

    stored = 0
    bodies = 0
    for item in all_items:
        doc_url = item.get("URL", "")
        if not doc_url:
            continue

        # Ensure URL is absolute
        if doc_url.startswith("/"):
            doc_url = _BASE_URL + doc_url

        # Skip if already stored with body text
        existing = conn.execute(
            "SELECT id, body_text_cn FROM documents WHERE url = ?", (doc_url,)
        ).fetchone()
        if existing and existing[1]:
            stored += 1
            continue

        doc_id = existing[0] if existing else next_id(conn)

        # Extract fields from API response
        title = item.get("TITLE", "").strip()
        if not title:
            continue

        doc_number = item.get("C_WJBH", "").strip()
        identifier = item.get("C_SYH", "").strip()
        date_published = item.get("PUBLISHED_TIME_FORMAT", "")[:10]
        date_written_str = item.get("C_FWRQ_FORMAT", "")[:10]
        date_written = _parse_date(date_written_str) if date_written_str else _parse_date(date_published)

        body_text = ""
        raw_html_path = ""
        publisher = ""
        abstract = ""
        classify_theme = ""

        if fetch_bodies:
            try:
                doc_html = fetch(doc_url, headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                })
                meta = _extract_meta(doc_html)
                body_text = _extract_body(doc_html)

                # Merge metadata
                publisher = meta.get("publisher", meta.get("ContentSource", ""))
                doc_number = meta.get("document_number", "") or doc_number
                identifier = meta.get("identifier", "") or identifier
                classify_theme = meta.get("classify_theme_name", "")
                abstract = meta.get("abstract", "")

                if meta.get("date_written_str"):
                    date_written = _parse_date(meta["date_written_str"])
                if meta.get("PubDate"):
                    date_published = meta["PubDate"].split()[0]

                if doc_html:
                    raw_html_path = save_raw_html(SITE_KEY, doc_id, doc_html)
                    bodies += 1
            except Exception as e:
                log.warning(f"  Failed to fetch {doc_url}: {e}")
            time.sleep(REQUEST_DELAY)

        store_document(conn, SITE_KEY, {
            "id": doc_id,
            "title": title,
            "document_number": doc_number,
            "identifier": identifier,
            "publisher": publisher,
            "date_written": date_written,
            "date_published": date_published,
            "abstract": abstract,
            "body_text_cn": body_text,
            "url": doc_url,
            "classify_main_name": section_name,
            "classify_theme_name": classify_theme,
            "raw_html_path": raw_html_path,
        })
        stored += 1

        if stored % 20 == 0:
            conn.commit()
            log.info(
                f"  Progress: {stored}/{len(all_items)} stored, "
                f"{bodies} bodies"
            )

    conn.commit()
    log.info(f"  Done: {stored} documents stored, {bodies} bodies fetched")
    return stored


def crawl_all(conn, sections: dict = None, fetch_bodies: bool = True):
    """Crawl all (or specified) Suzhou sections."""
    if sections is None:
        # Default: crawl "all" (no channel filter) to get everything
        sections = {"all": (SECTIONS["all"][0], SECTIONS["all"][1])}

    store_site(conn, SITE_KEY, SITE_CFG)
    total = 0
    for section_key, (name, channel_id) in sections.items():
        total += crawl_section(
            conn, section_key, name, channel_id, fetch_bodies
        )
        time.sleep(REQUEST_DELAY)

    log.info(f"=== Suzhou total: {total} documents ===")


def main():
    parser = argparse.ArgumentParser(
        description="Suzhou Municipality Policy Crawler"
    )
    parser.add_argument(
        "--section",
        choices=list(SECTIONS.keys()),
        help="Crawl only this section (default: all)",
    )
    parser.add_argument(
        "--stats", action="store_true", help="Show database stats"
    )
    parser.add_argument(
        "--list-only",
        action="store_true",
        help="List document URLs without fetching bodies",
    )
    parser.add_argument(
        "--db",
        type=str,
        help="Path to SQLite database (default: documents.db)",
    )
    args = parser.parse_args()

    conn = init_db(Path(args.db) if args.db else None)

    if args.stats:
        show_stats(conn)
        conn.close()
        return

    if args.section:
        name, channel_id = SECTIONS[args.section]
        sections = {args.section: (name, channel_id)}
    else:
        sections = None

    crawl_all(conn, sections, fetch_bodies=not args.list_only)
    show_stats(conn)
    conn.close()


if __name__ == "__main__":
    main()
