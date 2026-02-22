"""Compute SHA-256 hashes of raw HTML files and store in database."""
import hashlib
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "documents.db"
RAW_HTML_DIR = Path(__file__).parent.parent / "raw_html"

def compute_hashes():
    conn = sqlite3.connect(str(DB_PATH))
    updated = 0

    for site_dir in RAW_HTML_DIR.iterdir():
        if not site_dir.is_dir():
            continue
        for html_file in site_dir.glob("*.html"):
            doc_id = html_file.stem
            try:
                doc_id = int(doc_id)
            except ValueError:
                continue
            content = html_file.read_bytes()
            sha256 = hashlib.sha256(content).hexdigest()
            conn.execute(
                "UPDATE documents SET raw_html_sha256 = ? WHERE id = ?",
                (sha256, doc_id),
            )
            updated += 1
            if updated % 500 == 0:
                conn.commit()
                print(f"  Hashed {updated} files...")

    conn.commit()
    conn.close()
    print(f"Computed hashes for {updated} raw HTML files")

if __name__ == "__main__":
    compute_hashes()
