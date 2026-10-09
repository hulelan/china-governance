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
import json
import os
import re
import sqlite3
import sys
import tempfile
import time
import urllib.request

import fitz  # PyMuPDF


ATTACH_EXTS = (".pdf", ".doc", ".docx", ".xls", ".xlsx")


def attachment_url_from_json(attachments_json: str) -> tuple[str, str] | None:
    """-> (absolute url, ext) from `documents.attachments_json`, or None.

    Why this exists (measured 2026-10-09): this script finds attachment URLs by
    PARSING SAVED RAW HTML, and the raw-HTML mirror begins 2026-06-08 (the droplet
    migration) — so for anything crawled earlier the HTML is simply not on disk and
    the document was skipped forever. 7,802 documents have a body under 400 chars
    saying 详见附件 / 文件下载链接, 6,731 of them carry `attachments_json`, 6,013 name a
    PDF, and ZERO had been enriched. The url was in the database the whole time,
    alongside `name`, `mime` and `size`.

    The stored url is absolute and often `https://`, which fails on most Shenzhen
    hosts with `SSL: BAD_ECPOINT` (an OpenSSL elliptic-curve parse error — these
    hosts serve certificates OpenSSL cannot handle, very likely SM2). That is already
    handled downstream: `download_attachment` retries `https` -> `http`, and forcing
    http succeeded on 8 of 8 probes with valid %PDF- magic.
    """
    if not attachments_json or attachments_json in ("[]", "null"):
        return None
    try:
        arr = json.loads(attachments_json)
    except Exception:
        return None
    items = arr if isinstance(arr, list) else [arr]
    # Prefer a PDF; fall back to any office format we can read.
    for wanted in (".pdf",), ATTACH_EXTS:
        for it in items:
            if not isinstance(it, dict):
                continue
            u = (it.get("url") or "").strip()
            if not u:
                continue
            low = u.lower()
            for ext in wanted:
                if low.endswith(ext) or ext in low:
                    return u, ext
    return None


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
        # An encrypted or malformed PDF must be a ROW-level outcome, not a run-level
        # one. Measured 2026-10-09: a single `ValueError: document closed or encrypted`
        # propagated out of here and killed a 6,013-document run after 1,544 had been
        # enriched — the per-10 incremental commits are the only reason that work
        # survived. A loop that pays network time per row cannot let one bad input abort
        # the rest.
        text = ""
        try:
            doc = fitz.open(tmp_path)
        except Exception as e:                      # noqa: BLE001
            print(f"    unreadable PDF ({type(e).__name__}: {e}); skipping")
            return ""
        try:
            if getattr(doc, "needs_pass", False) or getattr(doc, "is_encrypted", False):
                # Try the empty password, which opens many "protected" gov PDFs.
                if not doc.authenticate(""):
                    print("    encrypted PDF (no empty-password access); skipping")
                    return ""
            for page in doc:
                try:
                    text += page.get_text()
                except Exception as e:              # noqa: BLE001
                    # One damaged page should not lose the rest of the document.
                    print(f"    page unreadable ({type(e).__name__}); continuing")
        except Exception as e:                      # noqa: BLE001
            print(f"    PDF read failed ({type(e).__name__}: {e}); keeping partial text")
        finally:
            try:
                doc.close()
            except Exception:                       # noqa: BLE001
                pass
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


# A host that accepts a TCP connection but never answers costs the FULL timeout on
# every document it owns. Measured 2026-10-09: a run sat 27 minutes with 23 s of CPU,
# one ESTAB socket and ZERO database writes — roughly 54 documents at 30 s each, all
# timing out on one peer. Because the work list is ordered by id, one host's documents
# are contiguous, so a run can spend hours inside a single dead host. At that rate 5,084
# documents would need ~42 h and collide with the nightly.
HOST_FAIL_LIMIT = 8


class HostBreaker:
    """Stop fetching from a host after HOST_FAIL_LIMIT consecutive failures.

    Consecutive, not cumulative: a host that fails 8 in a row is down, whereas a host
    with 8 scattered failures among successes is merely serving some bad files. Any
    success resets the count, so a slow-but-working host is never tripped.
    """

    def __init__(self, limit=HOST_FAIL_LIMIT):
        self.limit = limit
        self.consecutive = {}
        self.tripped = set()

    @staticmethod
    def host_of(url):
        from urllib.parse import urlparse
        try:
            return (urlparse(url).netloc or "").lower()
        except Exception:                           # noqa: BLE001
            return ""

    def is_open(self, url):
        return self.host_of(url) in self.tripped

    def record(self, url, ok):
        h = self.host_of(url)
        if not h:
            return
        if ok:
            self.consecutive[h] = 0
            return
        n = self.consecutive.get(h, 0) + 1
        self.consecutive[h] = n
        if n >= self.limit:
            self.tripped.add(h)

    def report(self):
        return sorted(self.tripped)


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
        f"SELECT id, raw_html_path, body_text_cn, url, site_key, "
        f"COALESCE(attachments_json, '') "
        f"FROM documents {where}{limit_clause}",
        params,
    ).fetchall()

    print(f"Found {len(rows)} attachment-only documents to process")

    if args.dry_run:
        for doc_id, html_path, body, url, site_key, att_json in rows[:20]:
            exists = "Y" if html_path and os.path.exists(html_path) else "N"
            from_json = attachment_url_from_json(att_json)
            print(f"  [{site_key}] {doc_id}: html={exists} "
                  f"json_url={'Y' if from_json else 'N'} | {body[:44]}")
        if len(rows) > 20:
            print(f"  ... and {len(rows) - 20} more")
        return

    breaker = HostBreaker()
    processed = 0
    extracted = 0
    scanned = 0
    errors = 0
    skipped = 0

    for doc_id, html_path, body, url, site_key, att_json in rows:
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

        # The HTML may be absent (the raw_html mirror begins 2026-06-08) or may
        # carry no link; `attachments_json` holds the url either way.
        result = find_attachment_url(html) if html else None
        if not result:
            result = attachment_url_from_json(att_json)
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

        if breaker.is_open(attach_url):
            # This host has failed HOST_FAIL_LIMIT times in a row; do not pay another
            # full timeout for it. See HostBreaker.
            skipped += 1
            processed += 1
        # Unconditional: the progress line used to live inside `if text:`, so a
        # run that extracted nothing printed nothing and looked hung. Measured
        # 2026-10-09: 27 minutes, 23 s CPU, one ESTAB socket, zero output.
        if processed % 25 == 0:
            print(f"  Progress: {processed}/{len(rows)} processed, {extracted} "
                  f"extracted, {scanned} scanned, {errors} errors, "
                  f"{skipped} skipped" +
                  (f" | hosts tripped: {', '.join(breaker.report())}"
                   if breaker.report() else ""))
            continue

        data = download_attachment(attach_url, base_url)
        breaker.record(attach_url, bool(data))
        if not data:
            errors += 1
            processed += 1
            if processed % 25 == 0:
                print(f"  Progress: {processed}/{len(rows)} processed, {extracted} "
                      f"extracted, {scanned} scanned, {errors} errors, "
                      f"{skipped} skipped" +
                      (f" | hosts tripped: {', '.join(breaker.report())}"
                       if breaker.report() else ""))
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

        # Extract text based on format. Wrapped because the run MUST survive one
        # unreadable attachment (see extract_text_from_pdf): a crash here costs every
        # row not yet reached, and they were each paid for with a network fetch.
        text = ""
        try:
            if actual_ext == "pdf":
                text = extract_text_from_pdf(data)
            elif actual_ext in ("doc", "docx"):
                text = extract_text_from_doc(data)
        except Exception as e:                      # noqa: BLE001
            print(f"  [{site_key}] {doc_id}: extract failed "
                  f"({type(e).__name__}: {e}); skipping")
            errors += 1
            continue

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
