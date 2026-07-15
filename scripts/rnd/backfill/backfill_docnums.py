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

# Generic leading 文号: an issuer abbreviation (1-8 Han chars) + 〔YYYY〕N号.
# Precision comes from position: we only look at the masthead region (first
# --header chars), where a gov doc prints its OWN number — a citation would be
# deeper in the body. normalize_formal_ref() strips any lead-in that leaked in.
GENERIC = re.compile(r"[一-鿿]{1,8}〔(?:19|20)\d{2}〕\d+号")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--site", required=True, help="site_key, or 'all' for every site")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--header", type=int, default=140,
                    help="chars from body start to search for the doc's own 文号")
    args = ap.parse_args()

    conn = sqlite3.connect(DB)
    if args.site == "all":
        where, params = "1=1", ()
    else:
        where, params = "site_key = ?", (args.site,)
    rows = conn.execute(
        f"SELECT id, body_text_cn FROM documents "
        f"WHERE {where} AND (document_number = '' OR document_number IS NULL) "
        f"AND body_text_cn IS NOT NULL AND body_text_cn != ''",
        params,
    ).fetchall()

    updated, samples = 0, []
    for doc_id, body in rows:
        m = GENERIC.search((body or "")[: args.header])
        if not m:
            continue
        ref = normalize_formal_ref(m.group(0))
        if not ref:
            continue
        if not args.dry_run:
            conn.execute("UPDATE documents SET document_number = ? WHERE id = ?", (ref, doc_id))
        if len(samples) < 20:
            samples.append((doc_id, ref))
        updated += 1

    if not args.dry_run:
        conn.commit()
    print(f"{'[DRY-RUN] would update' if args.dry_run else 'Updated'} {updated} "
          f"of {len(rows)} empty-docnum '{args.site}' docs")
    for did, ref in samples:
        print(f"  {did}: {ref}")


if __name__ == "__main__":
    main()


if __name__ == "__main__":
    main()
