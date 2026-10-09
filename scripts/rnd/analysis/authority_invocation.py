#!/usr/bin/env python3
"""Whose authority do documents invoke? -- the answerable form of "Aligning
Agendas" (JCPS 2026), which topic-models 71,460 leader activity releases we do
not hold.

The Party hierarchy is nearly absent from this corpus as an ISSUER (104
provincial party-committee documents vs 19,015 government ones) because
政府信息公开 obliges administrative organs, not the Party. But it is highly
visible as INVOKED authority, so that is what this measures: per year and per
admin level, the share of documents whose text names each channel.

Prints the RAW series and the FIXED-SITE PANEL series side by side on purpose.
The raw one is untrustworthy -- municipal document counts run 1,257 (2008) ->
11,280 (2025) as newly-crawled sites arrive, and the raw series shows a 2025
collapse that the panel shows is composition.

INDEX TRAP (see docs/research/rmb-coverage.md §4): `doc_search` is a trigram
index and needs >=3 characters, so a 2-character name like 李强 returns a clean
0 from it and 1,614 from `doc_search_seg`. Terms are routed by length here, and
the routing is printed so it cannot be silently wrong.

Read-only. Writeup: docs/research/authority-invocation.md

    python3 scripts/rnd/analysis/authority_invocation.py
    python3 scripts/rnd/analysis/authority_invocation.py --terms 习近平,党中央,李强
    python3 scripts/rnd/analysis/authority_invocation.py --min-per-year 50
"""
import argparse
import sqlite3
import sys
from collections import defaultdict
from pathlib import Path

_P = Path(__file__).resolve().parents
ROOT = _P[3] if len(_P) > 3 else Path.cwd()

DEFAULT_TERMS = "习近平,党中央,总书记,国务院总理"
LEVELS = ("central", "provincial", "municipal")

# Index routing lives in one place now (scripts/rnd/analysis/fts.py). This file
# had its own copy, which is exactly how the trap got written a sixth time in a
# query elsewhere: the right logic existed but was not reachable.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from fts import TRIGRAM_MIN, term_ids  # noqa: E402,F401


def table(label, tot, hit, terms, years, min_per_year):
    print(f"--- {label} ---")
    head = "".join(f"{t+'%':>11}" for t in terms)
    print(f"  {'yr':<6}{'docs':>8}{head}")
    for yr in years:
        n = tot.get(yr, 0)
        if n < min_per_year:
            continue
        cells = "".join(f"{100.0*hit.get((yr,t),0)/n:>11.1f}" for t in terms)
        print(f"  {yr:<6}{n:>8,}{cells}")
    print()


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--db", default=str(ROOT / "documents.db"))
    ap.add_argument("--terms", default=DEFAULT_TERMS,
                    help=f"comma-separated (default: {DEFAULT_TERMS})")
    ap.add_argument("--min-per-year", type=int, default=50,
                    help="suppress a year-level cell below this many documents")
    ap.add_argument("--panel-min", type=int, default=30,
                    help="a panel site needs this many bodied docs in EVERY panel year")
    ap.add_argument("--from-year", type=int, default=2012)
    ap.add_argument("--to-year", type=int, default=2025)
    args = ap.parse_args()

    terms = [t.strip() for t in args.terms.split(",") if t.strip()]
    conn = sqlite3.connect(f"file:{args.db}?mode=ro", uri=True)
    conn.execute("PRAGMA cache_size=-40000")

    sets = {}
    print("term -> index (a 2-char term in the trigram index returns a silent 0):")
    for t in terms:
        sets[t], idx = term_ids(conn, t)
        print(f"  {t:<16}{idx:<16}{len(sets[t]):>8,}")
    print()

    rows = conn.execute(f"""
        SELECT d.id, d.site_key, CAST(substr(d.date_published,1,4) AS INT), i.admin_level_doc
        FROM documents d JOIN doc_identity i ON i.doc_id = d.id
        WHERE d.date_published != '' AND d.body_text_cn != ''
          AND i.admin_level_doc IN ({','.join('?' * len(LEVELS))})
    """, LEVELS).fetchall()
    print(f"bodied, dated, levelled documents: {len(rows):,}")

    years = list(range(args.from_year, args.to_year + 1))
    panel_years = [y for y in years if y <= 2024]     # 2025 may be partial
    cnt = defaultdict(int)
    for _, sk, yr, _ in rows:
        if yr in panel_years:
            cnt[(sk, yr)] += 1
    panel = {sk for sk in {s for s, _ in cnt}
             if all(cnt.get((sk, y), 0) >= args.panel_min for y in panel_years)}
    print(f"fixed panel ({len(panel)} sites, >={args.panel_min}/yr in "
          f"{panel_years[0]}-{panel_years[-1]}): {' '.join(sorted(panel))}\n")

    for scope, keep in (("RAW (all sites)", None), ("FIXED PANEL", panel)):
        print(f"================ {scope} ================")
        tot = defaultdict(int); hit = defaultdict(int)
        for did, sk, yr, lvl in rows:
            if yr not in years or (keep is not None and sk not in keep):
                continue
            tot[(lvl, yr)] += 1
            for t in terms:
                if did in sets[t]:
                    hit[(lvl, yr, t)] += 1
        for lvl in LEVELS:
            t_ = {y: tot.get((lvl, y), 0) for y in years}
            h_ = {(y, t): hit.get((lvl, y, t), 0) for y in years for t in terms}
            if max(t_.values(), default=0) < args.min_per_year:
                print(f"--- {lvl}: too thin ({max(t_.values(), default=0)}/yr) ---\n")
                continue
            table(lvl, t_, h_, terms, years, args.min_per_year)


if __name__ == "__main__":
    main()
