"""Translate AI policy chain documents to English via Claude API.

Requires: pip install anthropic
Requires: ANTHROPIC_API_KEY environment variable

Usage:
    python3 scripts/translate_chain.py                # Translate all untranslated AI docs
    python3 scripts/translate_chain.py --dry-run      # Show what would be translated
    python3 scripts/translate_chain.py --doc-id 12345 # Translate a single document
"""

import argparse
import json
import logging
import os
import sqlite3
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from crawler import DB_PATH

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are a professional translator specializing in Chinese government documents.
Translate the following Chinese government document into clear, professional English.

Rules:
- Preserve document numbers (文号) untranslated, e.g., 深龙华府办规〔2024〕20号
- Use consistent English names for government bodies:
  - 龙华区 → Longhua District
  - 南山区 → Nanshan District
  - 坪山区 → Pingshan District
  - 科技创新局 → S&T Innovation Bureau
  - 发展和改革委员会 → Development & Reform Commission
  - 人力资源和社会保障局 → Human Resources & Social Security Bureau
- Translate policy/plan names consistently
- For terms without clean English equivalents, provide the Chinese in parentheses
- Output ONLY the translation, no commentary"""

# Documents to prioritize: formal policy docs and key chain documents
PRIORITY_QUERY = """
SELECT id, title, body_text_cn, document_number, site_key
FROM documents
WHERE (title LIKE '%人工智能%' OR keywords LIKE '%人工智能%' OR abstract LIKE '%人工智能%')
  AND body_text_cn IS NOT NULL AND LENGTH(body_text_cn) > 20
  AND (body_text_en IS NULL OR body_text_en = '')
ORDER BY
    (document_number IS NOT NULL AND document_number <> '') DESC,
    LENGTH(body_text_cn) DESC
"""


def translate_document(client, title: str, body: str) -> tuple[str, str]:
    """Translate a document's title and body. Returns (title_en, body_en)."""
    # Translate title
    title_resp = client.messages.create(
        model="claude-sonnet-4-5-20250929",
        max_tokens=200,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": f"Translate this document title:\n{title}"}],
    )
    title_en = title_resp.content[0].text.strip()

    # Translate body (may be long, use haiku for cost efficiency on very long docs)
    model = "claude-sonnet-4-5-20250929" if len(body) < 3000 else "claude-sonnet-4-5-20250929"
    body_resp = client.messages.create(
        model=model,
        max_tokens=8000,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": f"Translate this government document:\n\n{body}"}],
    )
    body_en = body_resp.content[0].text.strip()

    return title_en, body_en


def main():
    parser = argparse.ArgumentParser(description="Translate AI chain documents")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--doc-id", type=int, help="Translate a single document")
    parser.add_argument("--limit", type=int, default=10, help="Max documents to translate")
    args = parser.parse_args()

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key and not args.dry_run:
        print("Error: ANTHROPIC_API_KEY environment variable required")
        print("  export ANTHROPIC_API_KEY=sk-ant-...")
        sys.exit(1)

    conn = sqlite3.connect(DB_PATH)

    if args.doc_id:
        rows = conn.execute(
            "SELECT id, title, body_text_cn, document_number, site_key FROM documents WHERE id = ?",
            (args.doc_id,),
        ).fetchall()
    else:
        rows = conn.execute(PRIORITY_QUERY).fetchall()

    rows = rows[:args.limit]
    log.info(f"Found {len(rows)} documents to translate")

    if args.dry_run:
        for doc_id, title, body, doc_num, site_key in rows:
            chars = len(body) if body else 0
            marker = f" [{doc_num}]" if doc_num else ""
            print(f"  {doc_id} ({site_key}){marker} {chars} chars — {title[:60]}")
        # Estimate cost
        total_chars = sum(len(r[2]) for r in rows if r[2])
        est_tokens = total_chars  # rough: 1 char ≈ 1 token for Chinese
        est_cost = est_tokens * 3 / 1_000_000  # Sonnet input price ~$3/MTok
        print(f"\nEstimated: ~{total_chars:,} chars, ~${est_cost:.2f} input cost")
        return

    import anthropic
    client = anthropic.Anthropic(api_key=api_key)

    success = 0
    for i, (doc_id, title, body, doc_num, site_key) in enumerate(rows):
        marker = f" [{doc_num}]" if doc_num else ""
        log.info(f"[{i+1}/{len(rows)}] Translating {doc_id}{marker} — {title[:50]}")

        try:
            title_en, body_en = translate_document(client, title, body)
            conn.execute(
                "UPDATE documents SET body_text_en = ? WHERE id = ?",
                (body_en, doc_id),
            )
            conn.commit()
            success += 1
            log.info(f"  OK — {len(body_en)} chars English")
        except Exception as e:
            log.error(f"  FAILED: {e}")

        time.sleep(0.5)

    log.info(f"Done: {success}/{len(rows)} translated")
    conn.close()


if __name__ == "__main__":
    main()
