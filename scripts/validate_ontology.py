"""Validate the source-type ontology against a live documents.db.

Confirms every site_key in the corpus resolves to exactly one ontology leaf
(nothing silently falls into 'other'), and prints per-node document counts plus
the news / non-news split used by the "exclude news" filter.

    python3 scripts/validate_ontology.py                 # uses SQLITE_PATH or documents.db
    python3 scripts/validate_ontology.py --db /path/to/documents.db
"""
import argparse
import os
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from web.services import ontology  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=os.environ.get("SQLITE_PATH", "documents.db"))
    args = ap.parse_args()

    conn = sqlite3.connect(f"file:{args.db}?mode=ro", uri=True)
    rows = conn.execute(
        "SELECT s.site_key, COUNT(d.id) FROM sites s "
        "LEFT JOIN documents d ON d.site_key = s.site_key GROUP BY s.site_key"
    ).fetchall()
    site_keys = [r[0] for r in rows]
    doc_counts = {r[0]: r[1] for r in rows}

    result = ontology.validate(site_keys)

    print(f"Total site_keys: {result['total']}")
    print(f"Unmapped (-> other, unintended): {len(result['unmapped'])}")
    if result["unmapped"]:
        print("  " + ", ".join(sorted(result["unmapped"])))

    # Per-branch doc counts.
    print("\nDocument counts by top-level branch:")
    branch_docs = {}
    leaf_docs = {}
    for sk, cnt in doc_counts.items():
        leaf = ontology.site_to_type(sk)
        leaf_docs[leaf] = leaf_docs.get(leaf, 0) + cnt
    for top in ontology.tree():
        tot = sum(doc_counts.get(sk, 0) for sk in ontology.type_to_sites(top["id"]))
        # include prefix-matched
        tot = sum(cnt for sk, cnt in doc_counts.items()
                  if ontology.is_under(sk, top["id"]))
        branch_docs[top["id"]] = tot
        print(f"  {top['id']:12s} {top['label_en']:34s} {tot:>8,}")

    total_docs = sum(doc_counts.values())
    news_docs = sum(cnt for sk, cnt in doc_counts.items()
                    if ontology.is_under(sk, "media"))
    non_news = total_docs - news_docs
    non_news_sites = ontology.sites_excluding("media", all_site_keys=site_keys)
    print(f"\nTotal docs:      {total_docs:,}")
    print(f"News docs:       {news_docs:,}")
    print(f"Non-news docs:   {non_news:,}")
    print(f"Non-news sites:  {len(non_news_sites)} / {len(site_keys)}")

    ok = len(result["unmapped"]) == 0
    print("\nVALIDATION:", "PASS" if ok else "FAIL")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
