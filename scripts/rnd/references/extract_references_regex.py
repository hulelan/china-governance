"""Deterministic reference extractor for Chinese policy documents.

Runs over every document with body text but no references_json yet, extracts
formal references using regex patterns, and writes them to references_json
along with versioning metadata (references_source = 'regex_v1',
references_extracted_at = ISO date).

Existing DeepSeek-sourced references are NOT overwritten — the WHERE clause
filters them out.

Patterns:
  1. 《XXX》         Chinese book-quote brackets (most refs use this form)
  2. 国发〔2020〕14号  Formal central document numbers (issuer + year + serial)
  3. 〔2020〕14号     Bare document numbers without issuer prefix

A stop-list filters out single-word noise inside 《》 brackets — generic
headers like "管理办法" or "通知" which appear in passing but aren't real refs.

Usage:
    python3 scripts/extract_references_regex.py --dry-run --limit 50
    python3 scripts/extract_references_regex.py                    # full run
"""

from __future__ import annotations

import argparse
import json
import re
import sqlite3
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

DB_PATH = Path(__file__).parents[3] / "documents.db"

# ─── Regex patterns ──────────────────────────────────────────────────────────

RE_BOOK_QUOTE = re.compile(r"《([^》《\n]{3,80})》")
RE_FORMAL_DOC = re.compile(
    r"([一-龥]{1,8}[发字函通][\d一-龥]{0,4}?[〔\[]\d{4}[〕\]]\d+号)"
)
RE_FORMAL_BARE = re.compile(r"([一-龥]{0,8}[〔\[]\d{4}[〕\]]\d+号)")

# Stop-list: generic headers that show up inside 《》 in passing but aren't
# actual references. Compared against the *full extracted string*, not
# substrings — so 《XX省XX管理办法》 still passes (it contains but isn't
# equal to "管理办法").
STOP_WORDS = {
    "管理办法", "实施办法", "实施细则", "细则",
    "通知", "决定", "意见", "规定", "条例", "办法",
    "方案", "公告", "通告", "章程", "制度", "法", "规", "令",
    "规划", "纲要", "标准", "规范", "草案", "文件", "政策",
    "措施", "规则", "条款", "若干意见", "若干规定", "若干办法",
    "实施意见", "工作方案", "工作要点", "工作意见", "暂行办法",
    "暂行规定", "试行办法", "试行规定", "征求意见稿",
}


def extract_refs(body: str) -> list[str]:
    """Return ordered, deduplicated list of refs from body text."""
    if not body:
        return []
    refs: list[str] = []
    seen: set[str] = set()

    for m in RE_BOOK_QUOTE.finditer(body):
        r = m.group(1).strip()
        if r in STOP_WORDS or len(r) < 3:
            continue
        if r and r not in seen:
            seen.add(r)
            refs.append(r)

    for m in RE_FORMAL_DOC.finditer(body):
        r = m.group(1).strip()
        if r and r not in seen:
            seen.add(r)
            refs.append(r)

    for m in RE_FORMAL_BARE.finditer(body):
        r = m.group(1).strip()
        if r and r not in seen:
            seen.add(r)
            refs.append(r)

    return refs


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--limit", type=int, default=0,
                   help="stop after N docs (0 = no limit)")
    p.add_argument("--commit-every", type=int, default=500,
                   help="SQLite commit every N updates (default 500)")
    p.add_argument("--dry-run", action="store_true",
                   help="extract but do not write")
    p.add_argument("--site", default="",
                   help="only process one site_key (for testing)")
    args = p.parse_args()

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    source_tag = "regex_v1"

    conn = sqlite3.connect(DB_PATH, timeout=60)
    conn.execute("PRAGMA busy_timeout=60000")
    conn.execute("PRAGMA journal_mode=WAL")

    # Skip docs that already have refs from any source
    where = (
        "(references_source IS NULL OR references_source = '') "
        "AND body_text_cn IS NOT NULL AND LENGTH(body_text_cn) > 100"
    )
    params: list = []
    if args.site:
        where += " AND site_key = ?"
        params.append(args.site)

    cur = conn.execute(
        f"SELECT COUNT(*) FROM documents WHERE {where}", params)
    total = cur.fetchone()[0]
    if args.limit and args.limit < total:
        total = args.limit

    if total == 0:
        print("No docs to process. ✓")
        return

    print(f"Extracting refs from {total:,} docs"
          f"{' (DRY RUN)' if args.dry_run else ''} as source={source_tag}")
    t0 = time.time()

    sql = (
        f"SELECT id, body_text_cn FROM documents WHERE {where} ORDER BY id"
    )
    if args.limit:
        sql += f" LIMIT {args.limit}"

    cur = conn.execute(sql, params)

    done = 0
    with_refs = 0
    empty = 0
    pending: list[tuple[str, str, str, int]] = []  # (refs_json, src, at, id)

    for doc_id, body in cur:
        refs = extract_refs(body)
        if refs:
            with_refs += 1
        else:
            empty += 1
        pending.append((json.dumps(refs, ensure_ascii=False),
                        source_tag, now, doc_id))
        done += 1

        if not args.dry_run and len(pending) >= args.commit_every:
            conn.executemany(
                "UPDATE documents SET "
                "references_json = ?, references_source = ?, "
                "references_extracted_at = ? WHERE id = ?",
                pending)
            conn.commit()
            pending.clear()

        if done % 5000 == 0 or done == total:
            rate = done / (time.time() - t0)
            eta = (total - done) / rate if rate else 0
            print(f"  {done:>6,}/{total:,} "
                  f"({100*done/total:5.1f}%)  "
                  f"with_refs={with_refs:,}  empty={empty:,}  "
                  f"{rate:.0f}/s  ETA {eta/60:.1f} min",
                  file=sys.stderr, flush=True)

        if args.limit and done >= args.limit:
            break

    if pending and not args.dry_run:
        conn.executemany(
            "UPDATE documents SET "
            "references_json = ?, references_source = ?, "
            "references_extracted_at = ? WHERE id = ?",
            pending)
        conn.commit()

    elapsed = time.time() - t0
    pct_with = 100 * with_refs / max(done, 1)
    print(f"\nDone in {elapsed/60:.1f} min. "
          f"Scanned {done:,} docs: {with_refs:,} have refs ({pct_with:.1f}%), "
          f"{empty:,} have no refs.")


if __name__ == "__main__":
    main()
