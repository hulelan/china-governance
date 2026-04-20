"""
Extract text from PDF/DOC attachments for documents with stub body text.

Many Chinese government documents are published as PDF attachments with only
a one-line "click to view" page. This script:
1. Finds documents with short body text that reference attachments
2. Extracts attachment URLs from saved raw HTML (or live page for CAC)
3. Downloads the attachment and extracts text:
   - PDF: PyMuPDF (fitz)
   - DOC/DOCX: macOS textutil (falls back to skip on Linux)
4. Updates body_text_cn with the extracted text

Supports:
- gkmlpt sites: /attachment/ URLs in raw HTML
- CAC: /cms/pub/interact/downloadfile.jsp links
- Any site with direct PDF/DOC links in page HTML

Usage:
    python3 scripts/extract_pdf_text.py                  # Process all attachment-only docs
    python3 scripts/extract_pdf_text.py --site cac       # Only CAC
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

    # Pattern 3: CAC downloadfile.jsp (encrypted filepath param)
    # e.g. /cms/pub/interact/downloadfile.jsp?filepath=...&fText=...
    matches = re.findall(
        r'href=["\']?(/cms/pub/interact/downloadfile\.jsp\?[^"\'>\s]+)',
        html,
        re.IGNORECASE,
    )
    if matches:
        url = matches[0].replace("&amp;", "&")
        # Detect extension from fText param or Content-Disposition at download time
        # Default to "doc" since most CAC attachments are .doc
        return (url, "doc")

    # Pattern 4: Relative PDF/DOC links (NDRC uses ./P0xxxxx.pdf, SAMR uses /zj/...pdf)
    matches = re.findall(
        r'href=["\'](\./[^"\']+\.(pdf|doc|docx))["\']',
        html,
        re.IGNORECASE,
    )
    if matches:
        return matches[0]

    # Pattern 5: Absolute /path/*.pdf links (no hostname)
    matches = re.findall(
        r'href=["\'](/[^"\']+\.(pdf|doc|docx))["\']',
        html,
        re.IGNORECASE,
    )
    if matches:
        return matches[0]

    # Pattern 6: Any full URL PDF on the page (e.g. /wzfj/*.pdf)
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


def extract_text_from_doc(data: bytes) -> str:
    """Extract text from DOC/DOCX bytes using macOS textutil.

    Falls back to empty string on non-macOS systems.
    """
    import subprocess
    import platform

    if platform.system() != "Darwin":
        return ""

    # Detect format from magic bytes
    if data[:4] == b"%PDF":
        suffix = ".pdf"
    elif data[:2] == b"PK":
        suffix = ".docx"
    else:
        suffix = ".doc"

    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as f:
        f.write(data)
        tmp_path = f.name

    txt_path = tmp_path + ".txt"
    try:
        subprocess.run(
            ["textutil", "-convert", "txt", tmp_path, "-output", txt_path],
            capture_output=True,
            timeout=30,
        )
        if os.path.exists(txt_path):
            with open(txt_path, "r", encoding="utf-8", errors="replace") as f:
                text = f.read()
            os.unlink(txt_path)
        else:
            text = ""
    except Exception:
        text = ""
    finally:
        os.unlink(tmp_path)
        if os.path.exists(txt_path):
            os.unlink(txt_path)

    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n\s*\n", "\n", text)
    text = text.strip()
    return text if len(text) > 20 else ""


def download_attachment(url: str, base_url: str = "", timeout: int = 30) -> bytes | None:
    """Download an attachment from URL. Returns bytes or None on failure.

    Handles both absolute URLs and relative paths (prefixed with base_url).
    """
    if url.startswith("/"):
        url = base_url.rstrip("/") + url
    elif not url.startswith("http"):
        url = base_url.rstrip("/") + "/" + url

    try:
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/131.0.0.0 Safari/537.36"
                )
            },
        )
        resp = urllib.request.urlopen(req, timeout=timeout)
        return resp.read()
    except Exception:
        # For gkmlpt sites, try HTTP fallback
        if url.startswith("https://"):
            try:
                http_url = url.replace("https://", "http://")
                req = urllib.request.Request(
                    http_url,
                    headers={"User-Agent": "Mozilla/5.0 (compatible; PolicyCrawler/1.0)"},
                )
                resp = urllib.request.urlopen(req, timeout=timeout)
                return resp.read()
            except Exception:
                pass
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
    # CAC stubs can be up to ~400 chars, so use 500 for CAC, default for others
    body_threshold = args.max_body_len
    if args.site == "cac" and body_threshold <= 100:
        body_threshold = 500

    where = (
        "WHERE body_text_cn != '' AND LENGTH(body_text_cn) < ? "
        "AND (body_text_cn LIKE '%附件%' OR body_text_cn LIKE '%点击%' "
        "     OR body_text_cn LIKE '%下载%') "
    )
    params: list = [body_threshold]

    if args.site:
        where += " AND site_key = ?"
        params.append(args.site)

    # For CAC, we can also process docs without saved raw HTML
    # (we'll fetch the live page to find downloadfile.jsp links)
    if args.site != "cac":
        where += " AND raw_html_path != ''"

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
        # Get HTML: from saved file, or live fetch for CAC
        html = None
        if html_path and os.path.exists(html_path):
            with open(html_path, "r", encoding="utf-8", errors="replace") as f:
                html = f.read()
        elif site_key == "cac" and url:
            # Fetch live page to find downloadfile.jsp links
            try:
                req = urllib.request.Request(
                    url,
                    headers={
                        "User-Agent": (
                            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                            "AppleWebKit/537.36 (KHTML, like Gecko) "
                            "Chrome/131.0.0.0 Safari/537.36"
                        )
                    },
                )
                resp = urllib.request.urlopen(req, timeout=20)
                html = resp.read().decode("utf-8", errors="replace")
            except Exception as e:
                print(f"  [{site_key}] {doc_id}: live fetch failed: {e}")
                errors += 1
                continue

        if not html:
            skipped += 1
            continue

        result = find_attachment_url(html)
        if not result:
            skipped += 1
            continue

        attach_url, ext = result
        ext = ext.lower()

        # Determine base URL for relative paths
        from urllib.parse import urlparse, urljoin
        base_url = ""
        if site_key == "cac":
            base_url = "https://www.cac.gov.cn"
        elif url:
            p = urlparse(url)
            base_url = f"{p.scheme}://{p.netloc}"

        # For relative paths like ./P0xxx.pdf, resolve against the doc's own URL
        if attach_url.startswith("./") and url:
            attach_url = urljoin(url, attach_url)

        data = download_attachment(attach_url, base_url)
        if not data:
            errors += 1
            continue

        # Detect actual format from magic bytes (overrides extension guess)
        if data[:4] == b"%PDF":
            actual_ext = "pdf"
        elif data[:2] == b"PK":
            actual_ext = "docx"
        elif data[:8] == b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1":
            actual_ext = "doc"
        else:
            actual_ext = ext

        # Extract text based on format
        text = ""
        if actual_ext == "pdf":
            text = extract_text_from_pdf(data)
        elif actual_ext in ("doc", "docx"):
            text = extract_text_from_doc(data)

        if text:
            # Prepend the original stub text so we keep the intro paragraph
            combined = body.strip() + "\n\n" + text if body.strip() else text
            conn.execute(
                "UPDATE documents SET body_text_cn = ? WHERE id = ?",
                (combined, doc_id),
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
        time.sleep(0.5)  # Be polite

    conn.commit()
    conn.close()

    print(f"\nDone: {processed} processed")
    print(f"  {extracted} PDFs with text extracted")
    print(f"  {scanned} scanned PDFs (no text layer)")
    print(f"  {errors} download errors")
    print(f"  {skipped} skipped (no HTML or no attachment URL)")


if __name__ == "__main__":
    main()
