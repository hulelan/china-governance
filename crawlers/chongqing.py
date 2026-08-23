"""
Chongqing Municipality (重庆市) crawler.

Crawls policy documents from www.cq.gov.cn.  Chongqing uses a custom CMS with
static HTML listing pages under the government information disclosure section.

URL patterns:
  Listing:  /zwgk/zfxxgkml/szfwj/{section}/index.html  (page 0)
            /zwgk/zfxxgkml/szfwj/{section}/index_N.html (page N)
  Detail:   ./{YYYYMM}/t{YYYYMMDD}_{ID}.html
  Body:     div.trs_editor_view (TRS CMS)
  Meta:     <meta> tags (ArticleTitle, PubDate, ContentSource)

Sections crawled:
  - xzgfxwj/szfbgt: 市政府办公厅行政规范性文件  (Municipal Office normative docs)
  - xzgfxwj/szf:    市政府行政规范性文件        (Municipal Gov normative docs)
  - zfgz/zfgz:      政府规章 / 渝府令           (Government regulations)
  - fzhsxgz/fzhsxxzgfxwj: 废止和失效行政规范性文件 (Repealed/invalid normative
    docs — HISTORICAL BACKFILL, see note below)

Repealed-archive note (废止失效, section key "fzhsx"):
  When a normative doc is repealed it leaves the active xzgfxwj listings and is
  moved into this 586-record archive.  The archive listing is server-rendered
  with title + 发文字号 + 废止日期, but the row <a> tags carry NO href — detail
  URLs are only reachable through the site's ENCRYPTED-param search API
  (crypto-js / DECRYPT.js / ykb-request.js, the "encrypted-param dialect" of
  crawlers/trs.py) and the original detail pages have themselves been withdrawn
  (they 404).  So this section is captured as METADATA-ONLY records: title,
  document_number, repeal date (-> date_published) and is_abolished=1, with a
  stable synthetic URL (archive index + #发文字号) for dedup.  No body text is
  fetched.  This still recovers ~586 genuinely-missing OLD abolished docs as
  resolvable citation targets (matched by title / 文号).

Pagination:
  JS function createPage(totalPages, currentIndex, "index", "html").
  Page 0 -> index.html, page N -> index_N.html.  ~10 items per page.

Usage:
    python -m crawlers.chongqing                    # Crawl all sections
    python -m crawlers.chongqing --section szfbgt   # Crawl one section
    python -m crawlers.chongqing --stats            # Show database stats
    python -m crawlers.chongqing --list-only        # List without fetching bodies
"""

import argparse
import re
import time
from datetime import datetime, timedelta, timezone
from html import unescape
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

SITE_KEY = "cq"
SITE_CFG = {
    "name": "Chongqing Municipality",
    "base_url": "https://www.cq.gov.cn",
    "admin_level": "municipal",
}

CST = timezone(timedelta(hours=8))
_BASE_URL = "https://www.cq.gov.cn"

# Section key -> (display name, URL path relative to /zwgk/zfxxgkml/szfwj/, listing format)
# listing format: "xzgfxwj" (table with zcwjk-list) or "zfgz" (list with listpc-item)
SECTIONS = {
    "szfbgt": ("市政府办公厅行政规范性文件", "xzgfxwj/szfbgt", "xzgfxwj"),
    "szf":    ("市政府行政规范性文件",     "xzgfxwj/szf",    "xzgfxwj"),
    "zfgz":   ("政府规章（渝府令）",       "zfgz/zfgz",      "zfgz"),
    # Historical backfill: repealed/invalid normative docs (metadata-only, no body).
    "fzhsx":  ("废止和失效行政规范性文件", "fzhsxgz/fzhsxxzgfxwj", "fzhsx"),
}

# Section formats that yield metadata-only records (no fetchable detail page):
# the listing has title + 文号 + repeal date but no href, and the withdrawn
# detail pages 404.  Stored with a synthetic URL + is_abolished=1, no body.
NO_BODY_FORMATS = {"fzhsx"}


def _section_url(section_key: str, page: int = 0) -> str:
    """Build listing page URL for a section."""
    _, path, _ = SECTIONS[section_key]
    base = f"{_BASE_URL}/zwgk/zfxxgkml/szfwj/{path}/"
    if page == 0:
        return base + "index.html"
    return base + f"index_{page}.html"


def _get_total_pages(html: str) -> int:
    """Extract total page count from createPage() call.

    Chongqing uses: createPage(totalPages, currentIndex, "index", "html")
    """
    m = re.search(r"createPage\((\d+),\s*\d+,", html)
    if m:
        return int(m.group(1))
    return 1


def _parse_listing_xzgfxwj(html: str, base_url: str) -> list[dict]:
    """Parse listing for 行政规范性文件 sections (szfbgt, szf).

    Structure:
      <tr class="zcwjk-list-c ...">
        <td class="num">N</td>
        <td class="title">
          <a href="./YYYYMM/tYYYYMMDD_ID.html">
            <p class="tit">TITLE</p>
            <p class="info">
              <i class="kh">(</i>
              <span>发文字号：DOC_NUMBER</span>
              <span class="time">成文日期 ：YYYY-MM-DD</span>
              <i class="kh">)</i>
            </p>
          </a>
        </td>
        ...
      </tr>
    """
    items = []
    for m in re.finditer(
        r'<tr[^>]*class="zcwjk-list-c[^"]*"[^>]*>(.*?)</tr>',
        html,
        re.DOTALL,
    ):
        row = m.group(1)

        # Extract link
        href_m = re.search(r'<a[^>]*href="([^"]+)"', row)
        if not href_m:
            continue
        href = href_m.group(1)
        doc_url = urljoin(base_url, href)

        # Extract title
        title_m = re.search(r'<p\s+class="tit"[^>]*>(.*?)</p>', row, re.DOTALL)
        if not title_m:
            continue
        title = re.sub(r"<[^>]+>", "", title_m.group(1)).strip()

        # Extract document number (发文字号)
        doc_number = ""
        dn_m = re.search(r'发文字号[：:]\s*([^<]+)', row)
        if dn_m:
            doc_number = dn_m.group(1).strip()
            # Clean up any trailing whitespace or zero-width chars
            doc_number = re.sub(r'[\u200b\u200c\u200d\ufeff\s]+$', '', doc_number)

        # Extract date (成文日期)
        date_str = ""
        date_m = re.search(r'成文日期\s*[：:]\s*(\d{4}-\d{2}-\d{2})', row)
        if date_m:
            date_str = date_m.group(1)

        if title:
            items.append({
                "url": doc_url,
                "title": unescape(title),
                "date_str": date_str,
                "document_number": doc_number,
            })

    return items


def _parse_listing_zfgz(html: str, base_url: str) -> list[dict]:
    """Parse listing for 政府规章 section (渝府令).

    Structure:
      <a class="listpc-item" href="./YYYYMM/tYYYYMMDD_ID.html">
        <li class="pub-unit ... fbjg-val" title="市政府">市政府</li>
        <li class="file-title" title="TITLE">TITLE</li>
        <li class="file-code">渝府令〔YYYY〕NNN号</li>
        <li class="pub-time">YYYY-MM-DD</li>
      </a>
    """
    items = []
    for m in re.finditer(
        r'<a\s+class="listpc-item"[^>]*href="([^"]+)"[^>]*>(.*?)</a>',
        html,
        re.DOTALL,
    ):
        href, inner = m.group(1), m.group(2)
        doc_url = urljoin(base_url, href)

        # Extract title
        title_m = re.search(
            r'<li[^>]*class="file-title"[^>]*title="([^"]*)"', inner
        )
        if not title_m:
            title_m = re.search(
                r'<li[^>]*class="file-title"[^>]*>(.*?)</li>', inner, re.DOTALL
            )
            if not title_m:
                continue
            title = re.sub(r"<[^>]+>", "", title_m.group(1)).strip()
        else:
            title = title_m.group(1).strip()

        # Extract document number
        doc_number = ""
        dn_m = re.search(
            r'<li[^>]*class="file-code"[^>]*>(.*?)</li>', inner, re.DOTALL
        )
        if dn_m:
            doc_number = re.sub(r"<[^>]+>", "", dn_m.group(1)).strip()

        # Extract date
        date_str = ""
        date_m = re.search(
            r'<li[^>]*class="pub-time"[^>]*>(\d{4}-\d{2}-\d{2})</li>', inner
        )
        if date_m:
            date_str = date_m.group(1)

        # Extract publisher
        publisher = ""
        pub_m = re.search(
            r'<li[^>]*class="[^"]*fbjg-val[^"]*"[^>]*title="([^"]*)"', inner
        )
        if pub_m:
            publisher = pub_m.group(1).strip()

        if title:
            items.append({
                "url": doc_url,
                "title": unescape(title),
                "date_str": date_str,
                "document_number": doc_number,
                "publisher": publisher,
            })

    return items


def _parse_listing_fzhsx(html: str, base_url: str) -> list[dict]:
    """Parse the 废止和失效行政规范性文件 archive (metadata-only records).

    Same <tr class="zcwjk-list-c"> rows as the xzgfxwj sections, but the <a>
    tag has NO href (detail URLs live behind the encrypted search API, and the
    original pages 404), and the date shown is 废止日期 (repeal date) in
    YYYY年MM月DD日 form, e.g.:

      <tr class="zcwjk-list-c clearfix">
        <td class="num">1</td>
        <td class="title">
          <a>
            <p class="tit">TITLE</p>
            <p class="info">(<span>发文字号：渝府办发〔2016〕75号</span>
               <span class="time">废止日期 ：2026年02月03日</span>)</p>
          </a>
        </td>
      </tr>

    Because there is no real detail URL we synthesize a STABLE one from the
    archive index + a #发文字号 (or #title) fragment so the partial-unique url
    index makes re-runs idempotent and gives a plausible source link.
    """
    from urllib.parse import quote

    items = []
    for m in re.finditer(
        r'<tr[^>]*class="zcwjk-list-c[^"]*"[^>]*>(.*?)</tr>',
        html,
        re.DOTALL,
    ):
        row = m.group(1)

        title_m = re.search(r'<p\s+class="tit"[^>]*>(.*?)</p>', row, re.DOTALL)
        if not title_m:
            continue
        title = re.sub(r"<[^>]+>", "", title_m.group(1)).strip()
        if not title:
            continue

        doc_number = ""
        dn_m = re.search(r'发文字号[：:]\s*([^<]+)', row)
        if dn_m:
            doc_number = re.sub(
                r'[​‌‍﻿\s]+$', '', dn_m.group(1).strip()
            )

        # 废止日期 (repeal date) — accepts both YYYY年MM月DD日 and YYYY-MM-DD.
        repeal_date = ""
        rd_m = re.search(
            r'废止日期\s*[：:]\s*(\d{4}[-年]\d{1,2}[-月]\d{1,2}日?)', row
        )
        if rd_m:
            repeal_date = rd_m.group(1)

        # The archive gives no promulgation date, only the repeal date — but the
        # true era is reliably encoded in the 文号 (e.g. 渝府办发〔2016〕75号 ->
        # 2016).  Use that year for date_published so these sort into their real
        # era; keep the repeal date in `relation`.  Empty if no year found.
        promulgation = ""
        yr_m = re.search(r'[〔\[（(](\d{4})[〕\]）)]', doc_number)
        if yr_m:
            promulgation = yr_m.group(1)

        # Stable synthetic URL: archive index + #文号 (fall back to title).
        frag = doc_number or title
        synth_url = urljoin(base_url, "index.html") + "#" + quote(frag)

        items.append({
            "url": synth_url,
            "title": unescape(title),
            "date_str": promulgation,
            "document_number": doc_number,
            "is_abolished": 1,
            "repeal_date": repeal_date,
        })

    return items


def _parse_listing(html: str, base_url: str, fmt: str) -> list[dict]:
    """Dispatch to the correct listing parser."""
    if fmt == "zfgz":
        return _parse_listing_zfgz(html, base_url)
    if fmt == "fzhsx":
        return _parse_listing_fzhsx(html, base_url)
    return _parse_listing_xzgfxwj(html, base_url)


def _parse_date(date_str: str) -> int:
    """Convert date string to Unix timestamp at midnight CST."""
    date_str = (
        date_str.replace("/", "-")
        .replace("年", "-")
        .replace("月", "-")
        .replace("日", "")
    )
    try:
        dt = datetime.strptime(date_str.strip(), "%Y-%m-%d").replace(tzinfo=CST)
        return int(dt.timestamp())
    except ValueError:
        return 0


def _extract_meta(html: str) -> dict:
    """Extract metadata from detail page <meta> tags and body patterns."""
    meta = {}

    # Standard gov.cn <meta> tags
    for name in ("ArticleTitle", "PubDate", "ContentSource", "Keywords",
                 "Description", "ColumnName"):
        m = re.search(
            rf'<meta\s+name="{name}"\s+content="([^"]*)"', html, re.IGNORECASE
        )
        if m:
            meta[name] = m.group(1).strip()

    # Extract document number from body text (渝府发/渝府办发/渝府令 patterns)
    dn_m = re.search(r'(渝府[办令发规]*[〔\[]\d{4}[〕\]]\d+号)', html)
    if dn_m:
        meta["document_number"] = dn_m.group(1)

    # Look for publisher in body
    pub_m = re.search(r'(重庆市人民政府[办公厅]*)', html)
    if pub_m:
        meta["publisher"] = pub_m.group(1)

    return meta


def _extract_body(html: str) -> str:
    """Extract plain text body from document detail page.

    Chongqing uses div.trs_editor_view as the main content container,
    inside a div.content wrapper.
    """
    content = ""
    for pattern in [
        r'<div[^>]*class="[^"]*\btrs_editor_view\b[^"]*"[^>]*>(.*?)</div>\s*(?:\s*<script|</div>)',
        r'<div[^>]*class="[^"]*\bTRS_UEDITOR\b[^"]*"[^>]*>(.*?)</div>',
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
    conn, section_key: str, section_name: str, fetch_bodies: bool = True,
    max_pages: int = None,
):
    """Crawl all listing pages in a section and fetch document details.

    max_pages: cap the number of listing pages fetched (for bounded testing).
      None = all pages.
    """
    _, _, fmt = SECTIONS[section_key]
    # Repealed-archive rows have no fetchable detail page -> metadata-only.
    no_body = fmt in NO_BODY_FORMATS
    log.info(f"--- Section: {section_name} ({section_key}) ---")

    first_url = _section_url(section_key, 0)
    try:
        html = fetch(first_url)
    except Exception as e:
        log.error(f"Failed to fetch {first_url}: {e}")
        return 0

    total_pages = _get_total_pages(html)
    if max_pages is not None:
        total_pages = min(total_pages, max_pages)
    log.info(f"  {total_pages} listing pages" + (" (metadata-only)" if no_body else ""))

    # Parse first page
    all_items = _parse_listing(html, first_url, fmt)

    # Fetch remaining pages
    for page in range(1, total_pages):
        page_url = _section_url(section_key, page)
        try:
            page_html = fetch(page_url)
            items = _parse_listing(page_html, page_url, fmt)
            all_items.extend(items)
        except Exception as e:
            log.warning(f"  Failed page {page}: {e}")
        time.sleep(REQUEST_DELAY)

    log.info(f"  Found {len(all_items)} document links")

    stored = 0
    bodies = 0
    for item in all_items:
        doc_url = item["url"]

        # Skip if already stored with body text.  For metadata-only sections
        # (no body ever), skip if the record already exists at all so re-runs
        # are cheap and idempotent (the synthetic url is stable per 文号).
        existing = conn.execute(
            "SELECT id, body_text_cn FROM documents WHERE url = ? AND url != ''", (doc_url,)
        ).fetchone()
        if existing and (existing[1] or no_body):
            stored += 1
            continue

        doc_id = existing[0] if existing else next_id(conn)

        body_text = ""
        raw_html_path = ""
        doc_number = item.get("document_number", "")
        publisher = item.get("publisher", "")
        date_published = item.get("date_str", "")
        date_written = _parse_date(item.get("date_str", ""))

        if fetch_bodies and not no_body:
            try:
                doc_html = fetch(doc_url)
                meta = _extract_meta(doc_html)
                body_text = _extract_body(doc_html)

                # Merge metadata
                publisher = (
                    publisher
                    or meta.get("publisher", "")
                    or meta.get("ContentSource", "")
                )
                doc_number = meta.get("document_number", "") or doc_number

                if meta.get("PubDate"):
                    date_published = meta["PubDate"]

                if doc_html:
                    raw_html_path = save_raw_html(SITE_KEY, doc_id, doc_html)
                    bodies += 1
            except Exception as e:
                log.warning(f"  Failed to fetch {doc_url}: {e}")
            time.sleep(REQUEST_DELAY)

        doc_row = {
            "id": doc_id,
            "title": item["title"],
            "document_number": doc_number,
            "publisher": publisher,
            "date_written": date_written,
            "date_published": date_published,
            "body_text_cn": body_text,
            "url": doc_url,
            "classify_main_name": section_name,
            "raw_html_path": raw_html_path,
        }
        if no_body:
            # Repealed/invalid record: flag abolished, note the repeal date.
            doc_row["is_abolished"] = item.get("is_abolished", 1)
            rd = item.get("repeal_date", "")
            if rd:
                doc_row["relation"] = f"repealed;repeal_date={rd}"
        store_document(conn, SITE_KEY, doc_row)
        stored += 1

        if stored % 20 == 0:
            conn.commit()
            log.info(f"  Progress: {stored}/{len(all_items)} stored, {bodies} bodies")

    conn.commit()
    log.info(f"  Done: {stored} documents stored, {bodies} bodies fetched")
    return stored


def crawl_all(conn, sections: dict = None, fetch_bodies: bool = True,
              max_pages: int = None):
    """Crawl all (or specified) Chongqing sections."""
    if sections is None:
        sections = {k: v[0] for k, v in SECTIONS.items()}

    store_site(conn, SITE_KEY, SITE_CFG)
    total = 0
    for section_key, name in sections.items():
        total += crawl_section(conn, section_key, name, fetch_bodies, max_pages)
        time.sleep(REQUEST_DELAY)

    log.info(f"=== Chongqing total: {total} documents ===")


def main():
    parser = argparse.ArgumentParser(
        description="Chongqing Municipality Policy Crawler"
    )
    parser.add_argument(
        "--section",
        choices=list(SECTIONS.keys()),
        help="Crawl only this section",
    )
    parser.add_argument("--stats", action="store_true", help="Show database stats")
    parser.add_argument(
        "--list-only",
        action="store_true",
        help="List document URLs without fetching bodies",
    )
    parser.add_argument(
        "--db", type=str, help="Path to SQLite database (default: documents.db)",
    )
    parser.add_argument(
        "--max-pages", type=int, default=None,
        help="Cap listing pages per section (bounded testing)",
    )
    args = parser.parse_args()

    conn = init_db(Path(args.db) if args.db else None)

    if args.stats:
        show_stats(conn)
        conn.close()
        return

    sections = (
        {args.section: SECTIONS[args.section][0]} if args.section else None
    )
    crawl_all(conn, sections, fetch_bodies=not args.list_only,
              max_pages=args.max_pages)
    show_stats(conn)
    conn.close()


if __name__ == "__main__":
    main()
