"""
Re-extract body text from saved raw HTML for documents with missing bodies.

This is a quick win for sites where body extraction failed on first crawl
(e.g., MOST changed their CMS template). No network requests needed — reads
from raw_html/ directory.

Usage:
    python3 scripts/backfill_from_html.py              # All sites
    python3 scripts/backfill_from_html.py --site most  # One site
    python3 scripts/backfill_from_html.py --dry-run    # Preview
"""

import argparse
import importlib
import os
import re
import sqlite3
import sys
import time
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "documents.db"
RAW_HTML_DIR = Path(__file__).parent.parent / "raw_html"

# Map site_key -> module with _extract_body function
EXTRACTORS = {
    "most": "crawlers.most",
    "ndrc": "crawlers.ndrc",
    "nda": "crawlers.nda",
    "mee": "crawlers.mee",
    "samr": "crawlers.samr",
    "mofcom": "crawlers.mofcom",
    "cac": "crawlers.cac",
    "sic": "crawlers.sic",
}

# Generic extractor for gkmlpt-based sites
GKMLPT_SITES = {
    "heyuan", "zhongshan", "zhuhai", "gd", "szdp", "gz", "shanwei",
    "jiangmen", "yunfu", "huizhou", "szlg", "szlhq", "szgm", "szlh",
    "szns", "szft", "szpsq", "sz", "ga", "mzj", "hrss", "swj", "jtys",
    "zjj", "stic", "sf", "szeb", "yjgl", "wjw", "fgw", "audit", "jieyang",
    "yangjiang", "shaoguan", "shantou",
}


def _generic_extract_body(html: str) -> str:
    """Generic body extractor — tries multiple common CMS patterns."""
    for class_name in [
        "trs_editor_view", "TRS_Editor", "TRS_UEDITOR",
        "article", "articleDetailsText", "text wide",
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
            .replace("\u3000", " ")
            .replace("&lt;", "<")
            .replace("&gt;", ">")
            .replace("&amp;", "&")
            .replace("&ldquo;", "\u201c")
            .replace("&rdquo;", "\u201d")
            .strip()
        )
        if len(text) > 50:
            return text
    return ""


def _gkmlpt_extract_body(html: str) -> str:
    """Extract body from gkmlpt-style pages (JSON content field or HTML)."""
    import json
    # gkmlpt stores content in JSON — look for "content" field
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


def backfill(site_filter: str = None, dry_run: bool = False):
    conn = sqlite3.connect(str(DB_PATH))

    # Find docs with raw HTML but no body text
    query = """
        SELECT id, site_key, raw_html_path, title
        FROM documents
        WHERE (body_text_cn IS NULL OR LENGTH(body_text_cn) <= 20)
          AND raw_html_path IS NOT NULL AND raw_html_path != ''
    """
    params = []
    if site_filter:
        query += " AND site_key = ?"
        params.append(site_filter)
    query += " ORDER BY site_key, id"

    rows = conn.execute(query, params).fetchall()
    print(f"Found {len(rows)} documents with raw HTML but no body text")

    if dry_run:
        from collections import Counter
        site_counts = Counter(r[1] for r in rows)
        for site, count in site_counts.most_common():
            print(f"  {site}: {count}")
        conn.close()
        return

    updated = 0
    failed = 0
    by_site = {}

    for doc_id, site_key, raw_path, title in rows:
        html_file = Path(__file__).parent.parent / raw_path
        if not html_file.exists():
            failed += 1
            continue

        html = html_file.read_text(errors="replace")

        # Choose extractor
        if site_key in EXTRACTORS:
            try:
                mod = importlib.import_module(EXTRACTORS[site_key])
                body = mod._extract_body(html)
            except Exception:
                body = _generic_extract_body(html)
        elif site_key in GKMLPT_SITES:
            body = _gkmlpt_extract_body(html)
        else:
            body = _generic_extract_body(html)

        if body and len(body) > 50:
            conn.execute(
                "UPDATE documents SET body_text_cn = ? WHERE id = ?",
                (body, doc_id)
            )
            updated += 1
            by_site[site_key] = by_site.get(site_key, 0) + 1
            if updated % 50 == 0:
                conn.commit()
                print(f"  Updated {updated}...")
        else:
            failed += 1

    conn.commit()
    conn.close()

    print(f"\nDone: {updated} bodies extracted, {failed} failed")
    for site, count in sorted(by_site.items(), key=lambda x: -x[1]):
        print(f"  {site}: +{count}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Re-extract body text from saved raw HTML")
    parser.add_argument("--site", help="Only process this site")
    parser.add_argument("--dry-run", action="store_true", help="Preview without updating")
    args = parser.parse_args()
    backfill(site_filter=args.site, dry_run=args.dry_run)
