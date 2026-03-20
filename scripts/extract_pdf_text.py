"""
Extract text from PDF/DOC attachments for documents with stub body text.

Many Chinese government documents are published as PDF attachments with only
a one-line "click to view" page. This script:
1. Finds documents with short body text that reference attachments
2. Extracts attachment URLs from saved raw HTML
3. Downloads the PDF and extracts text using PyMuPDF (fitz)
4. Updates body_text_cn with the extracted text

Usage:
    python3 scripts/extract_pdf_text.py                  # Process all attachment-only docs
    python3 scripts/extract_pdf_text.py --site gd        # Only Guangdong province
    python3 scripts/extract_pdf_text.py --limit 50       # Process first 50
    python3 scripts/extract_pdf_text.py --dry-run        # Show what would be processed
    python3 scripts/extract_pdf_text.py --db alt.db      # Use alternate database
"""

import argparse
import os
import re
import sqlite3
import sys
import tempfile
import time
import urllib.request

import fitz  # PyMuPDF


def find_attachment_url(html: str) -> tuple[str, str] | None:
    """Extract the first PDF/DOC attachment URL from raw HTML.

    Looks for attachment file URLs in gkmlpt content JSON and HTML.
    Returns (url, extension) or None.
    """
    # Pattern 1: /attachment/ URLs with any document extension
    matches = re.findall(
        r'(https?://[^\s"\\]*?/attachment/[^\s"\\]*?\.(pdf|doc|docx))',
        html,
        re.IGNORECASE,
    )
    if matches:
        return matches[0]

    # Pattern 2: nfw-cms-attachment class with escaped unicode quotes
    matches = re.findall(
        r'nfw-cms-attachment.*?href=\\u0022(.*?\.(pdf|doc|docx))\\u0022',
        html,
        re.IGNORECASE,
    )
    if matches:
        url = matches[0][0].replace("\\u0026", "&").replace("\\/", "/")
        return (url, matches[0][1])

    # Pattern 3: Any PDF URL on the page (e.g. /wzfj/*.pdf)
    matches = re.findall(
        r'(https?://[^\s"\\]*?\.(pdf))',
        html,
        re.IGNORECASE,
    )
    if matches:
        return matches[0]

    return None


def extract_text_from_pdf(data: bytes) -> str:
    """Extract text from PDF bytes using PyMuPDF.

    Returns extracted text, or empty string if the PDF is scanned/image-only.
    """
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
        f.write(data)
        tmp_path = f.name

    try:
        doc = fitz.open(tmp_path)
        text = ""
        for page in doc:
            text += page.get_text()
        doc.close()
    finally:
        os.unlink(tmp_path)

    # Clean up whitespace
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n\s*\n", "\n", text)
    text = text.strip()
    text = text.replace("\xa0", " ")

    if len(text) > 20:
        return text
    return ""


def download_pdf(url: str, timeout: int = 30) -> bytes | None:
    """Download a PDF from URL. Returns bytes or None on failure."""
    try:
        # Try HTTP first (gkmlpt sites often block HTTPS)
        url = url.replace("https://", "http://")
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "Mozilla/5.0 (compatible; PolicyCrawler/1.0)"},
        )
        resp = urllib.request.urlopen(req, timeout=timeout)
        return resp.read()
    except Exception:
        return None


def main():
    parser = argparse.ArgumentParser(
        description="Extract text from PDF attachments for stub-body documents"
    )
    parser.add_argument("--site", type=str, help="Only process this site_key")
    parser.add_argument(
        "--limit", type=int, default=0, help="Max documents to process (0=all)"
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Show what would be processed"
    )
    parser.add_argument(
        "--db", type=str, default="documents.db", help="Database path"
    )
    parser.add_argument(
        "--max-body-len",
        type=int,
        default=100,
        help="Max body_text_cn length to consider as stub (default: 100)",
    )
    args = parser.parse_args()

    conn = sqlite3.connect(args.db)
    conn.execute("PRAGMA busy_timeout = 30000")

    # Find attachment-only documents
    where = (
        "WHERE body_text_cn != '' AND LENGTH(body_text_cn) < ? "
        "AND (body_text_cn LIKE '%附件%' OR body_text_cn LIKE '%点击%' "
        "     OR body_text_cn LIKE '%下载%') "
        "AND raw_html_path != ''"
    )
    params: list = [args.max_body_len]

    if args.site:
        where += " AND site_key = ?"
        params.append(args.site)

    limit_clause = f" LIMIT {args.limit}" if args.limit else ""

    rows = conn.execute(
        f"SELECT id, raw_html_path, body_text_cn, url, site_key "
        f"FROM documents {where}{limit_clause}",
        params,
    ).fetchall()

    print(f"Found {len(rows)} attachment-only documents to process")

    if args.dry_run:
        for doc_id, html_path, body, url, site_key in rows[:20]:
            exists = "Y" if os.path.exists(html_path) else "N"
            print(f"  [{site_key}] {doc_id}: html={exists} | {body[:50]}")
        if len(rows) > 20:
            print(f"  ... and {len(rows) - 20} more")
        return

    processed = 0
    extracted = 0
    scanned = 0
    errors = 0
    skipped = 0

    for doc_id, html_path, body, url, site_key in rows:
        if not os.path.exists(html_path):
            skipped += 1
            continue

        with open(html_path, "r", encoding="utf-8", errors="replace") as f:
            html = f.read()

        result = find_attachment_url(html)
        if not result:
            skipped += 1
            continue

        attach_url, ext = result
        ext = ext.lower()

        # Only handle PDFs for now (DOC/DOCX need python-docx)
        if ext not in ("pdf",):
            skipped += 1
            continue

        data = download_pdf(attach_url)
        if not data:
            errors += 1
            continue

        text = extract_text_from_pdf(data)
        if text:
            conn.execute(
                "UPDATE documents SET body_text_cn = ? WHERE id = ?",
                (text, doc_id),
            )
            extracted += 1
            if extracted % 10 == 0:
                conn.commit()
                print(
                    f"  Progress: {processed}/{len(rows)} processed, "
                    f"{extracted} extracted, {scanned} scanned, {errors} errors"
                )
        else:
            scanned += 1

        processed += 1
        time.sleep(0.3)  # Be polite

    conn.commit()
    conn.close()

    print(f"\nDone: {processed} processed")
    print(f"  {extracted} PDFs with text extracted")
    print(f"  {scanned} scanned PDFs (no text layer)")
    print(f"  {errors} download errors")
    print(f"  {skipped} skipped (no HTML or no attachment URL)")


if __name__ == "__main__":
    main()
