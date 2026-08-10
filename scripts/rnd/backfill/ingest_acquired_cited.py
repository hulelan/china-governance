#!/usr/bin/env python3
"""Ingest hand-acquired high-cited documents (missing from the corpus) into documents.db.

These are landmark national/provincial docs that hundreds of other docs cite by
title/文号 but that no crawler had captured (e.g. the 915-cite 城市、镇控制性详细规划
编制审批办法). Fetched to JSONL by a retrieval subagent from authoritative *.gov.cn.

Once inserted, TitleMatcher indexes their titles + document_numbers, so the next
extract_citations pass resolves the previously-dangling references to them.

Idempotent: skips any row whose URL already exists. Run in a quiet window (no
crawl / no score pass writing) to avoid a second writer.

    python3 scripts/rnd/backfill/ingest_acquired_cited.py --jsonl /tmp/missing_docs_fetched.jsonl
    python3 scripts/rnd/backfill/ingest_acquired_cited.py --dry-run
"""
import argparse
import json
import sqlite3
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

REPO = Path(__file__).parents[3]


def site_for(url: str) -> str:
    """Map a source host to an EXISTING sites.site_key so the doc inherits the
    right admin_level + shows up in that ministry's browse."""
    host = (urlparse(url).hostname or "").lower()
    if host.endswith("gd.gov.cn"):          # gd.gov.cn, hrss.gd.gov.cn
        return "gd"
    if "yangshan" in host:                  # a GD municipal portal (predecessor plan)
        return "gd"
    if "chinatax" in host:
        return "chinatax"
    if host.endswith("moe.gov.cn"):
        return "moe"
    # gov.cn (国务院公报), mem.gov.cn (应急管理部 hosting a State Council plan) -> State Council
    return "gov"


def to_epoch(date_str: str):
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%Y.%m.%d", "%Y年%m月%d日"):
        try:
            return int(datetime.strptime(date_str.strip(), fmt).replace(tzinfo=timezone.utc).timestamp())
        except (ValueError, AttributeError):
            continue
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--jsonl", default="/tmp/missing_docs_fetched.jsonl")
    ap.add_argument("--db", default=str(REPO / "documents.db"))
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    rows = []
    with open(args.jsonl, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))

    conn = sqlite3.connect(args.db)
    conn.execute("PRAGMA busy_timeout=30000;")
    cur = conn.cursor()
    next_id = cur.execute("SELECT COALESCE(MAX(id), 0) + 1 FROM documents").fetchone()[0]
    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    inserted = skipped = empty = 0
    for r in rows:
        url = (r.get("source_url") or "").strip()
        body = r.get("body_text") or ""
        title = (r.get("title") or "").strip()
        if not body.strip() or not title:
            empty += 1
            print(f"  SKIP empty  : {title[:40]!r} (rank {r.get('rank')})")
            continue
        exists = cur.execute("SELECT id FROM documents WHERE url = ? AND url != ''", (url,)).fetchone()
        if exists:
            skipped += 1
            print(f"  SKIP dup    : {title[:40]!r} -> id {exists[0]}")
            continue
        sk = site_for(url)
        epoch = to_epoch(r.get("date") or "")
        if args.dry_run:
            print(f"  WOULD INSERT: id {next_id} [{sk}] {title[:44]!r} ({len(body)} chars, #{r.get('document_number')})")
        else:
            cur.execute(
                """INSERT INTO documents
                   (id, site_key, title, document_number, publisher, date_published,
                    display_publish_time, body_text_cn, url, relation, crawl_timestamp)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                (next_id, sk, title, (r.get("document_number") or "").strip() or None,
                 (r.get("issuer") or "").strip() or None, (r.get("date") or "").strip() or None,
                 epoch, body, url, "acquired=cited_ref;fetched=2026-08-10", now_iso),
            )
            print(f"  INSERT      : id {next_id} [{sk}] {title[:44]!r} ({len(body)} chars)")
        next_id += 1
        inserted += 1

    if not args.dry_run:
        conn.commit()
    conn.close()
    print(f"\n{'DRY-RUN ' if args.dry_run else ''}inserted={inserted} skipped_dup={skipped} skipped_empty={empty}")


if __name__ == "__main__":
    main()
