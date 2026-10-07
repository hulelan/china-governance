"""Validate the source-type ontology against a live documents.db.

Confirms every site_key in the corpus resolves to exactly one ontology leaf and
reports HOW each was placed:

    explicit  — listed in data/source_ontology.yaml (exact key or prefix)
    fallback  — placed by web/services/ontology.py's deterministic fallback
                from the `sites` table's admin_level / govcms SITES group
                (the designed path for new crawlers; informational)
    unmapped  — neither layer could place it -> 'other'  (FAILS)

Also prints per-branch document counts and the news / non-news split used by
the "exclude news" filter.

    python3 scripts/validate_ontology.py                 # uses SQLITE_PATH or documents.db
    python3 scripts/validate_ontology.py --db /path/to/documents.db
    python3 scripts/validate_ontology.py --show-fallback # list every fallback-placed key
"""
import argparse
import os
import sqlite3
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from web.services import ontology  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=os.environ.get("SQLITE_PATH", "documents.db"))
    ap.add_argument("--show-fallback", action="store_true",
                    help="list every fallback-placed site_key with its leaf")
    args = ap.parse_args()

    conn = sqlite3.connect(f"file:{args.db}?mode=ro", uri=True)
    rows = conn.execute(
        "SELECT s.site_key, s.admin_level, COUNT(d.id) FROM sites s "
        "LEFT JOIN documents d ON d.site_key = s.site_key GROUP BY s.site_key"
    ).fetchall()
    sites = [{"site_key": r[0], "admin_level": r[1]} for r in rows]
    levels = {r[0]: r[1] for r in rows}
    doc_counts = {r[0]: r[2] for r in rows}
    site_keys = [r[0] for r in rows]

    result = ontology.validate(sites)
    fb = result["fallback"]
    unmapped = result["unmapped"]

    print(f"Total site_keys:                 {result['total']}")
    print(f"Mapped explicitly (yaml):        {len(result['explicit'])}")
    print(f"Mapped by fallback (admin_level):{len(fb):>4}   "
          f"({sum(doc_counts[k] for k in fb):,} docs)")
    if fb:
        by_leaf = defaultdict(list)
        for sk, leaf in fb.items():
            by_leaf[leaf].append(sk)
        for leaf, keys in sorted(by_leaf.items(), key=lambda kv: -len(kv[1])):
            docs = sum(doc_counts[k] for k in keys)
            lv = Counter(levels[k] for k in keys).most_common(1)[0][0]
            print(f"    {leaf:28s} {len(keys):>4} sites {docs:>8,} docs  (admin_level={lv})")
            if args.show_fallback:
                print("        " + ", ".join(sorted(keys)))
    print(f"Unmapped (-> other, FAIL):       {len(unmapped):>4}   "
          f"({sum(doc_counts[k] for k in unmapped):,} docs)")
    for sk in sorted(unmapped):
        print(f"    {sk:20s} admin_level={levels[sk]!r:14} {doc_counts[sk]:>7,} docs")

    # Per-branch doc counts (explicit + prefix + fallback).
    print("\nDocument counts by top-level branch:")
    for top in ontology.tree():
        tot = sum(cnt for sk, cnt in doc_counts.items()
                  if ontology.is_under(sk, top["id"], levels[sk]))
        print(f"  {top['id']:12s} {top['label_en']:34s} {tot:>8,}")

    total_docs = sum(doc_counts.values())
    news_docs = sum(cnt for sk, cnt in doc_counts.items()
                    if ontology.is_under(sk, "media", levels[sk]))
    non_news = total_docs - news_docs
    non_news_sites = ontology.sites_excluding("media", all_site_keys=sites)
    print(f"\nTotal docs:      {total_docs:,}")
    print(f"News docs:       {news_docs:,}")
    print(f"Non-news docs:   {non_news:,}")
    print(f"Non-news sites:  {len(non_news_sites)} / {len(site_keys)}")

    ok = len(unmapped) == 0
    print("\nVALIDATION:", "PASS" if ok else "FAIL")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
