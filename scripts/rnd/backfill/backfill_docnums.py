"""Backfill document_number from the leading 文号 in body text.

Several crawlers (shanghai, ...) store documents WITHOUT extracting their 文号,
so the docs sit in the corpus with an empty document_number — and citations that
reference them by 文号 (e.g. 沪府发〔2009〕29号) can't resolve, even though we HOLD
the document. This is a metadata gap, not a coverage gap.

Government documents put their own 文号 in a header line at the very top of the
body (before/after the title). This script extracts that leading 文号 and fills
document_number, so a citations rebuild then resolves the (already-held) targets.

Precision: we only take a 文号 found in the first `--header` chars (the masthead
region), never one buried deep in the body (which would be a *citation*, not the
doc's own number). Prefix restricted per-site to that jurisdiction's issuer.

Usage:
    python3 scripts/rnd/backfill/backfill_docnums.py --site sh --dry-run
    python3 scripts/rnd/backfill/backfill_docnums.py --site sh
"""
import argparse
import re
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[3]))
from analyze import normalize_formal_ref  # noqa: E402

DB = Path(__file__).parents[3] / "documents.db"

# Jurisdiction guard: only accept a leading 文号 whose issuer prefix matches the
# site's OWN jurisdiction. A cross-jurisdiction leading number means the doc is a
# forward/citation of someone else's doc ("转发…的通知") — extracting it would set
# a FALSE document_number and corrupt citation resolution. Prefixes are the
# regex-anchored issuer stems for each site's own documents.
SITE_PREFIX = {
    "sh": "沪",            # Shanghai 沪府发/沪府办发/沪府...
    "js": "苏",            # Jiangsu 苏政发/苏政办发
    "suzhou": "苏",        # Suzhou 苏府/苏州...
    "bj": "京",            # Beijing 京政发/京政办发
    "zhongshan": "中府",   # Zhongshan municipal (中府/中府办); avoids central 中发/中办
    "zhuhai": "珠",        # Zhuhai 珠府...
    "gd": "粤",            # Guangdong province 粤府/粤办...
    "mof": "财",           # Ministry of Finance 财*
    "ndrc": "发改",        # NDRC 发改*
    "gov": "国",           # State Council 国发/国办/国函
    "mofcom": "商",        # MOFCOM 商*
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--site", required=True,
                    help="site_key (must have a jurisdiction prefix), or 'all' for every mapped site")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--header", type=int, default=140,
                    help="chars from body start to search for the doc's own 文号")
    args = ap.parse_args()

    sites = list(SITE_PREFIX) if args.site == "all" else [args.site]
    conn = sqlite3.connect(DB, timeout=60)
    conn.execute("PRAGMA busy_timeout=60000")  # tolerate a concurrent nightly writer
    grand = 0
    for site in sites:
        prefix = SITE_PREFIX.get(site)
        if not prefix:
            print(f"SKIP '{site}': no jurisdiction prefix defined")
            continue
        pat = re.compile(prefix + r"[一-鿿]{0,7}〔(?:19|20)\d{2}〕\d+号")
        rows = conn.execute(
            "SELECT id, body_text_cn FROM documents "
            "WHERE site_key = ? AND (document_number = '' OR document_number IS NULL) "
            "AND body_text_cn IS NOT NULL AND body_text_cn != ''",
            (site,),
        ).fetchall()

        updated, samples = 0, []
        for doc_id, body in rows:
            m = pat.search((body or "")[: args.header])
            if not m:
                continue
            ref = normalize_formal_ref(m.group(0))
            if not ref:
                continue
            if not args.dry_run:
                conn.execute("UPDATE documents SET document_number = ? WHERE id = ?", (ref, doc_id))
            if len(samples) < 6:
                samples.append((doc_id, ref))
            updated += 1

        grand += updated
        print(f"{'[DRY] ' if args.dry_run else ''}{site} ({prefix}): "
              f"{'would update ' if args.dry_run else 'updated '}{updated}/{len(rows)}")
        for did, ref in samples:
            print(f"    {did}: {ref}")

    if not args.dry_run:
        conn.commit()
    print(f"{'[DRY-RUN] ' if args.dry_run else ''}TOTAL: {grand}")


if __name__ == "__main__":
    main()


if __name__ == "__main__":
    main()
