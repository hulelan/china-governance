"""Compare a deterministic regex-based reference extractor to DeepSeek's
references_json on the same set of documents.

Goal: figure out whether a regex pass is "good enough" to extract policy
references on the 170k+ documents that don't have references_json yet,
or whether we need to spend money/time running DeepSeek classification on
the long tail.

Methodology:
  - Pick N docs (default 50) where references_json is non-empty.
  - For each: run regex on body_text_cn, parse references_json.
  - Compute set overlap. Print per-doc + aggregate stats.

Regex patterns covered:
  1. 《XXX》 — anything in Chinese book quotes (most cited refs use this).
  2. 国发〔2020〕14号 / 国办发〔2019〕47号 — formal central document numbers.
  3. 〔2020〕XX号 / [2020]XX号 — generic formal document numbers.

Usage:
    python3 scripts/compare_references_regex_vs_deepseek.py
    python3 scripts/compare_references_regex_vs_deepseek.py --sample 100
"""

from __future__ import annotations

import argparse
import json
import re
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parents[3] / "documents.db"

# ─── Regex patterns ──────────────────────────────────────────────────────────

# 1. Book-quote refs (the most common form in Chinese policy docs)
#    Matches 《X》 where X has at least 2 chars (filters out empty quotes)
RE_BOOK_QUOTE = re.compile(r"《([^》《\n]{2,80})》")

# 2. Formal central-government document numbers, e.g.:
#    国发〔2020〕14号    国办发〔2019〕47号    教高函〔2018〕5号
#    Note Chinese uses 〔〕 brackets, but [] also appears in some docs.
RE_FORMAL_DOC = re.compile(
    r"([一-龥]{1,8}[发字函通][\d一-龥]{0,4}?[〔\[]\d{4}[〕\]]\d+号)"
)

# 3. Year+number-only fallback: 〔2020〕14号 without an issuer prefix
RE_FORMAL_BARE = re.compile(r"[〔\[](\d{4})[〕\]](\d+)号")


def normalize_ref(ref: str) -> str:
    """Canonicalize a reference for set comparison.

    DeepSeek sometimes returns refs WITH 《》 brackets, sometimes without.
    We strip them so the comparison is fair.
    """
    r = ref.strip()
    if r.startswith("《") and r.endswith("》"):
        r = r[1:-1]
    return r.strip()


def regex_extract(body: str) -> list[str]:
    """Return deduplicated list of references found in the body."""
    if not body:
        return []
    refs: list[str] = []
    seen: set[str] = set()

    for m in RE_BOOK_QUOTE.finditer(body):
        r = m.group(1).strip()
        if r and r not in seen:
            seen.add(r)
            refs.append(r)

    for m in RE_FORMAL_DOC.finditer(body):
        r = m.group(1).strip()
        if r and r not in seen:
            seen.add(r)
            refs.append(r)

    return refs


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--sample", type=int, default=50,
                   help="number of docs to compare (default 50)")
    p.add_argument("--show-details", type=int, default=10,
                   help="docs to print full diff for (default 10)")
    args = p.parse_args()

    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute("""
        SELECT id, site_key, title, references_json, body_text_cn
        FROM documents
        WHERE references_json IS NOT NULL
          AND references_json != '' AND references_json != '[]'
          AND body_text_cn IS NOT NULL AND LENGTH(body_text_cn) > 200
        ORDER BY RANDOM()
        LIMIT ?
    """, (args.sample,)).fetchall()

    if not rows:
        print("No docs with references_json + body text found.")
        return

    print(f"Comparing {len(rows)} docs: DeepSeek refs vs regex refs\n")
    print("=" * 100)

    total_ds = 0
    total_regex = 0
    total_overlap = 0
    total_ds_only = 0
    total_regex_only = 0
    overlap_ratios: list[float] = []

    for i, (doc_id, site, title, refs_json, body) in enumerate(rows, 1):
        try:
            ds_raw = json.loads(refs_json)
            ds_refs = {normalize_ref(r) for r in ds_raw if isinstance(r, str)}
        except (json.JSONDecodeError, TypeError):
            continue

        rx_refs = {normalize_ref(r) for r in regex_extract(body)}

        overlap = ds_refs & rx_refs
        ds_only = ds_refs - rx_refs
        rx_only = rx_refs - ds_refs
        union = ds_refs | rx_refs

        total_ds += len(ds_refs)
        total_regex += len(rx_refs)
        total_overlap += len(overlap)
        total_ds_only += len(ds_only)
        total_regex_only += len(rx_only)
        if union:
            overlap_ratios.append(len(overlap) / len(union))

        if i <= args.show_details:
            print(f"\n[{i:>2}] {site}  doc_id={doc_id}")
            print(f"  Title    │ {title[:80]}")
            print(f"  DeepSeek │ {len(ds_refs)} refs: "
                  f"{sorted(list(ds_refs))[:5]}{'...' if len(ds_refs) > 5 else ''}")
            print(f"  Regex    │ {len(rx_refs)} refs: "
                  f"{sorted(list(rx_refs))[:5]}{'...' if len(rx_refs) > 5 else ''}")
            print(f"  Overlap  │ {len(overlap)} "
                  f"({100*len(overlap)/len(union):.0f}% of union)")
            if ds_only and len(ds_only) <= 3:
                print(f"  DS-only  │ {sorted(list(ds_only))}")
            if rx_only and len(rx_only) <= 3:
                print(f"  RX-only  │ {sorted(list(rx_only))}")

    # ─── Aggregate report ──────────────────────────────────────────
    print("\n" + "=" * 100)
    print(f"AGGREGATE OVER {len(rows)} DOCS:")
    print(f"  DeepSeek total refs:       {total_ds:>5}")
    print(f"  Regex total refs:          {total_regex:>5}")
    print(f"  Overlap:                   {total_overlap:>5}  "
          f"({100*total_overlap/max(total_ds, 1):.1f}% of DeepSeek, "
          f"{100*total_overlap/max(total_regex, 1):.1f}% of regex)")
    print(f"  Only DeepSeek found:       {total_ds_only:>5}  "
          f"(refs regex missed)")
    print(f"  Only regex found:          {total_regex_only:>5}  "
          f"(refs DeepSeek didn't extract — might be noise OR misses)")
    if overlap_ratios:
        avg = sum(overlap_ratios) / len(overlap_ratios)
        print(f"  Avg per-doc Jaccard:       {100*avg:.1f}%  "
              f"(higher = regex covers what DeepSeek does)")

    print("\nVerdict:")
    if overlap_ratios:
        avg = sum(overlap_ratios) / len(overlap_ratios)
        ds_recall = total_overlap / max(total_ds, 1)
        if ds_recall >= 0.8:
            print("  ✓ Regex catches ≥80% of DeepSeek's refs. Probably safe to "
                  "scale regex to the long tail.")
        elif ds_recall >= 0.5:
            print("  ⚠ Regex catches 50-80%. Useful as a baseline but DeepSeek "
                  "still wins on edge cases (informal program names, partial "
                  "quotes). Hybrid recommended.")
        else:
            print("  ✗ Regex misses most of what DeepSeek finds. DeepSeek-only "
                  "if quality matters.")


if __name__ == "__main__":
    main()
