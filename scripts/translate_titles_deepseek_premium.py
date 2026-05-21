"""Premium title translation pass using DeepSeek, targeting high-value docs.

Run AFTER `translate_titles_google.py` so every doc has a Google translation
as a fallback. This script OVERWRITES title_en with DeepSeek's translation
for the top-N docs ranked by (ai_relevance + citation_rank), where idiomatic
English matters most.

Defenses (against LLM hallucination on corrupted inputs):
  - Skip rows where the ZH title has >30% '?' characters (Mojibake).
  - Skip rows with no Chinese characters (already English or empty).
  - If DeepSeek returns >2.5× the source length, treat as suspicious and
    keep the existing translation.

Usage:
    python3 scripts/translate_titles_deepseek_premium.py --dry-run --limit 5
    python3 scripts/translate_titles_deepseek_premium.py --top 5000

Env: DEEPSEEK_API_KEY in .env (auto-loaded).
"""

from __future__ import annotations

import argparse
import os
import sqlite3
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

# Load .env so DEEPSEEK_API_KEY is available
ENV_PATH = Path(__file__).parent.parent / ".env"
if ENV_PATH.exists():
    for line in ENV_PATH.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"'))

from openai import OpenAI                        # noqa: E402

DB_PATH = Path(__file__).parent.parent / "documents.db"

PROMPT_SYSTEM = (
    "You translate Chinese government document titles to English. "
    "Output ONLY the English translation, no quotes, no commentary. "
    "Preserve official terminology and proper nouns. Keep it concise."
)


def has_chinese(s: str) -> bool:
    return any("一" <= c <= "鿿" for c in s)


def looks_corrupted(s: str) -> bool:
    if not s or not s.strip():
        return True
    return s.count("?") > len(s) * 0.3


_client = None
def _ds() -> OpenAI:
    global _client
    if _client is None:
        key = os.environ.get("DEEPSEEK_API_KEY", "")
        if not key:
            print("Error: DEEPSEEK_API_KEY not set in env or .env", file=sys.stderr)
            sys.exit(1)
        _client = OpenAI(api_key=key, base_url="https://api.deepseek.com")
    return _client


def translate_one(doc_id: int, title: str) -> tuple[int, str | None]:
    if looks_corrupted(title) or not has_chinese(title):
        return doc_id, None
    try:
        resp = _ds().chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": PROMPT_SYSTEM},
                {"role": "user", "content": title},
            ],
            max_tokens=200,
            temperature=0.0,
            timeout=30,
        )
        out = (resp.choices[0].message.content or "").strip()
        if not out:
            return doc_id, None
        # Hallucination defense: if output is much longer than the Chinese
        # input × an English-expansion factor, treat as suspicious.
        if len(out) > len(title) * 6:
            return doc_id, None
        return doc_id, out
    except Exception:                            # noqa: BLE001
        return doc_id, None


def select_top_docs(conn: sqlite3.Connection, top_n: int) -> list[tuple[int, str]]:
    """Return [(id, title)] of top-N docs by ai_relevance + citation_rank.

    These are the docs people are most likely to skim, so they get the
    higher-quality translation.
    """
    return conn.execute("""
        SELECT id, title FROM documents
        WHERE title IS NOT NULL AND title != ''
          AND (ai_relevance > 0 OR citation_rank > 0)
        ORDER BY (COALESCE(ai_relevance, 0) * 2 + COALESCE(citation_rank, 0) * 0.05) DESC
        LIMIT ?
    """, (top_n,)).fetchall()


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--top", type=int, default=5000,
                   help="how many top-ranked docs to re-translate (default 5000)")
    p.add_argument("--workers", type=int, default=2,
                   help="concurrency (default 2 — DeepSeek silently rate-limits above this)")
    p.add_argument("--limit", type=int, default=0,
                   help="cap total work (0 = no cap, just use --top)")
    p.add_argument("--commit-every", type=int, default=50,
                   help="SQLite commit every N updates")
    p.add_argument("--dry-run", action="store_true",
                   help="translate but do not write")
    args = p.parse_args()

    conn = sqlite3.connect(DB_PATH, timeout=60)
    conn.execute("PRAGMA busy_timeout=60000")
    conn.execute("PRAGMA journal_mode=WAL")

    rows = select_top_docs(conn, args.top)
    if args.limit:
        rows = rows[:args.limit]
    total = len(rows)
    print(f"Premium-translating top {total:,} high-value docs"
          f" with DeepSeek (concurrency={args.workers})"
          f"{' [DRY RUN]' if args.dry_run else ''}…")

    t0 = time.time()
    done = 0
    written = 0
    skipped = 0
    pending: list[tuple[str, int]] = []

    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        futures = [ex.submit(translate_one, d, t) for d, t in rows]
        for fut in as_completed(futures):
            doc_id, en = fut.result()
            done += 1
            if en is None:
                skipped += 1
            else:
                pending.append((en, doc_id))
                written += 1

            if not args.dry_run and len(pending) >= args.commit_every:
                conn.executemany(
                    "UPDATE documents SET title_en = ? WHERE id = ?", pending)
                conn.commit()
                pending.clear()

            if done % 50 == 0 or done == total:
                rate = done / (time.time() - t0)
                eta = (total - done) / rate if rate else 0
                print(f"  {done:>5,}/{total:,}  "
                      f"({100*done/total:5.1f}%)  written={written:,}  "
                      f"skipped={skipped:,}  {rate:.2f}/s  "
                      f"ETA {eta/60:.1f} min",
                      file=sys.stderr, flush=True)

    if pending and not args.dry_run:
        conn.executemany(
            "UPDATE documents SET title_en = ? WHERE id = ?", pending)
        conn.commit()

    elapsed = time.time() - t0
    print(f"\nDone in {elapsed/60:.1f} min. "
          f"Written {written:,}, skipped {skipped:,}.")


if __name__ == "__main__":
    main()
