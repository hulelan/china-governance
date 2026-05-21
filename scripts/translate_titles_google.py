"""Batch-translate untranslated document titles using deep-translator
(Google's free web endpoint). Writes results to documents.title_en.

Resumable: filters to rows where title_en IS NULL OR title_en = ''.
Parallel: ThreadPoolExecutor (default 8 workers — Google free endpoint
tolerates this without rate-limit pain in practice).

Defenses:
  - Skip rows with no Chinese characters (already English or malformed).
  - Skip rows where >30% of characters are '?' (corrupted encoding).
  - On exception, leave title_en empty and continue. The row will be
    retried on the next run.

Usage:
    python3 scripts/translate_titles_google.py --dry-run --limit 20
    python3 scripts/translate_titles_google.py --workers 8 --limit 1000
    python3 scripts/translate_titles_google.py                        # full run
"""

from __future__ import annotations

import argparse
import sqlite3
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from deep_translator import GoogleTranslator
from deep_translator.exceptions import (
    RequestError, TranslationNotFound, NotValidPayload,
)

DB_PATH = Path(__file__).parent.parent / "documents.db"


def has_chinese(s: str) -> bool:
    return any("一" <= c <= "鿿" for c in s)


def looks_corrupted(s: str) -> bool:
    """True if the title is mostly '?' characters (Mojibake) or empty."""
    if not s or not s.strip():
        return True
    q = s.count("?")
    return q > len(s) * 0.3


def translate_one(doc_id: int, title: str) -> tuple[int, str | None, str]:
    """Returns (doc_id, english_translation_or_None, skip_reason).

    skip_reason is one of: "ok", "corrupted", "no_chinese", "api_error",
    "empty_response". Lets the caller log distinct failure modes.
    """
    if looks_corrupted(title):
        return doc_id, None, "corrupted"
    if not has_chinese(title):
        return doc_id, None, "no_chinese"

    # Retry up to 3x with exponential backoff on transient API errors
    last_err = None
    for attempt in range(3):
        try:
            out = GoogleTranslator(source="zh-CN", target="en").translate(title)
            if not out or not out.strip():
                return doc_id, None, "empty_response"
            return doc_id, out.strip(), "ok"
        except (RequestError, TranslationNotFound, NotValidPayload) as e:
            last_err = e
            time.sleep(0.5 * (2 ** attempt))   # 0.5s, 1s, 2s
        except Exception as e:                  # noqa: BLE001
            last_err = e
            time.sleep(0.5 * (2 ** attempt))
    return doc_id, None, "api_error"


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--workers", type=int, default=8,
                   help="parallel threads (default 8)")
    p.add_argument("--limit", type=int, default=0,
                   help="stop after N titles (0 = no limit)")
    p.add_argument("--commit-every", type=int, default=100,
                   help="SQLite commit every N updates (default 100)")
    p.add_argument("--dry-run", action="store_true",
                   help="translate but do not write")
    p.add_argument("--site", default="",
                   help="only translate one site_key (for testing)")
    args = p.parse_args()

    conn = sqlite3.connect(DB_PATH, timeout=60)
    conn.execute("PRAGMA busy_timeout=60000")
    conn.execute("PRAGMA journal_mode=WAL")

    where = "(title_en IS NULL OR title_en = '') AND title IS NOT NULL AND title != ''"
    params: list = []
    if args.site:
        where += " AND site_key = ?"
        params.append(args.site)
    sql = f"SELECT id, title FROM documents WHERE {where} ORDER BY id"
    if args.limit:
        sql += f" LIMIT {args.limit}"

    cur = conn.execute(sql, params)
    todo = cur.fetchall()
    total = len(todo)
    if not todo:
        print("Nothing to translate. ✓")
        return

    print(f"Translating {total:,} titles using {args.workers} workers"
          f"{' (DRY RUN)' if args.dry_run else ''}…")
    t0 = time.time()

    done = 0
    written = 0
    skip_counts = {"corrupted": 0, "no_chinese": 0, "api_error": 0, "empty_response": 0}
    pending: list[tuple[str, int]] = []   # (translation, doc_id) buffer

    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        futures = [ex.submit(translate_one, d, t) for d, t in todo]
        for fut in as_completed(futures):
            doc_id, en, reason = fut.result()
            done += 1
            if en is None:
                skip_counts[reason] = skip_counts.get(reason, 0) + 1
            else:
                pending.append((en, doc_id))
                written += 1

            # Flush periodically so progress is durable
            if not args.dry_run and len(pending) >= args.commit_every:
                conn.executemany(
                    "UPDATE documents SET title_en = ? WHERE id = ?", pending)
                conn.commit()
                pending.clear()

            if done % 200 == 0 or done == total:
                rate = done / (time.time() - t0)
                eta = (total - done) / rate if rate else 0
                skip_total = sum(skip_counts.values())
                print(f"  {done:>6,}/{total:,}  "
                      f"({100 * done / total:5.1f}%)  "
                      f"written={written:,}  skipped={skip_total:,} "
                      f"(api={skip_counts['api_error']} "
                      f"non-zh={skip_counts['no_chinese']} "
                      f"corrupt={skip_counts['corrupted']})  "
                      f"{rate:.1f}/s  ETA {eta/60:.1f} min",
                      file=sys.stderr, flush=True)

    if pending and not args.dry_run:
        conn.executemany(
            "UPDATE documents SET title_en = ? WHERE id = ?", pending)
        conn.commit()

    elapsed = time.time() - t0
    skip_total = sum(skip_counts.values())
    print(f"\nDone in {elapsed/60:.1f} min. "
          f"Written {written:,} translations, skipped {skip_total:,}: "
          f"api_error={skip_counts['api_error']}, "
          f"no_chinese={skip_counts['no_chinese']}, "
          f"corrupted={skip_counts['corrupted']}, "
          f"empty_response={skip_counts['empty_response']}.")


if __name__ == "__main__":
    main()
