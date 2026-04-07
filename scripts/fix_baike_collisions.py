#!/usr/bin/env python3
"""
Fix Frankenstein records in officials.db.

Background: `crawlers/baike.py` deduplicated Excel rows by `name_cn` alone,
silently dropping the second instance whenever two distinct people share
a Chinese name (31 such collisions in the source spreadsheet). The crawler
then fetched `baike.baidu.com/item/{name}` for each surviving row, but the
bare URL serves whichever entry Baidu Baike chose to feature — usually the
more famous/recent person, NOT the one whose metadata we kept.

Result: ~12 rows where the metadata (birth_year, home_province) is from
one person but the baike_html, career_text, and career_records belong to
a completely different person. The most visible example is 李强 (id=249),
whose row claims birth_year=1905 but stores the modern Premier Li Qiang's
career data (born 1959, served in Zhejiang from 1976).

This script:
  1. Identifies Frankenstein rows by comparing the row's birth_year to the
     plausible birth year derived from min(career_records.start_year) - 22.
  2. For each Frankenstein, picks the closest matching birth year from the
     Excel candidates for that name and updates birth_year + home_province
     in place. The career_records and overlaps remain valid because they
     describe the actual person we have data for.
  3. Reports anything ambiguous so the user can inspect manually.

This script does NOT add the missing twin rows (the people whose data we
never crawled because their name collided with someone else). That's a
separate, bigger task that requires Baidu Baike disambiguation handling.
"""

import argparse
import sqlite3
import sys
from collections import defaultdict
from pathlib import Path

import openpyxl

sys.path.insert(0, str(Path(__file__).parent.parent))
from crawlers.baike import EXCEL_PATH, DB_PATH


# Heuristic: a person's earliest career record is typically when they
# entered the workforce around age 18-25. We use 22 as the midpoint.
# A row is "Frankenstein" if the recorded birth_year is more than this
# many years off from the heuristic estimate.
TOLERANCE_YEARS = 20
TYPICAL_WORK_START_AGE = 22


def load_excel_collisions() -> dict[str, list[tuple[int, str]]]:
    """Return {name_cn: [(birth_year, home_province), ...]} for collision names."""
    wb = openpyxl.load_workbook(str(EXCEL_PATH), read_only=True)
    ws = wb["CC Members"]
    by_name: dict[str, set] = defaultdict(set)
    for i, row in enumerate(ws.iter_rows(values_only=True)):
        if i == 0:
            continue
        name_cn, birth_year, province = row[2], row[3], row[4]
        if name_cn and birth_year:
            by_name[name_cn].add((birth_year, province or ""))
    # Keep only collisions
    return {n: sorted(entries) for n, entries in by_name.items() if len(set(y for y, _ in entries)) > 1}


def estimate_birth_year(conn, official_id: int) -> int | None:
    """Return min(career.start_year) - typical work-start age, or None."""
    row = conn.execute(
        "SELECT MIN(start_year) FROM career_records WHERE official_id = ? AND start_year > 1900",
        (official_id,),
    ).fetchone()
    first_year = row[0] if row else None
    if not first_year:
        return None
    return first_year - TYPICAL_WORK_START_AGE


def closest_match(estimate: int, candidates: list[int]) -> int:
    return min(candidates, key=lambda y: abs(y - estimate))


def main():
    parser = argparse.ArgumentParser(description="Fix Frankenstein officials.db rows")
    parser.add_argument("--dry-run", action="store_true",
                        help="Show what would change without writing")
    args = parser.parse_args()

    collisions = load_excel_collisions()
    print(f"Loaded {len(collisions)} colliding name groups from Excel")

    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row

    fixed = 0
    skipped_no_careers = 0
    skipped_already_ok = 0
    ambiguous = []

    for name_cn, entries in sorted(collisions.items()):
        # All birth_year candidates from Excel for this name
        candidates = sorted(set(y for y, _ in entries))
        prov_by_year = {y: p for y, p in entries}

        rows = conn.execute(
            "SELECT id, birth_year, home_province FROM officials WHERE name_cn = ?",
            (name_cn,),
        ).fetchall()
        if not rows:
            continue

        for row in rows:
            oid = row["id"]
            db_born = row["birth_year"]

            estimate = estimate_birth_year(conn, oid)
            if estimate is None:
                skipped_no_careers += 1
                continue

            # If the recorded birth year is already plausible, leave it alone
            if abs(db_born - estimate) <= TOLERANCE_YEARS:
                skipped_already_ok += 1
                continue

            # Frankenstein detected — pick the closest collision candidate
            best = closest_match(estimate, candidates)
            best_prov = prov_by_year.get(best, "")

            # Sanity check: the pick should be much closer than the current value
            if abs(best - estimate) >= abs(db_born - estimate):
                ambiguous.append((name_cn, oid, db_born, estimate, candidates))
                continue

            print(f"FIX  id={oid:5d}  {name_cn:8s}  {db_born} → {best}  "
                  f"(est ~{estimate}, careers start {estimate + TYPICAL_WORK_START_AGE})  "
                  f"prov: {row['home_province']!r} → {best_prov!r}")
            if not args.dry_run:
                conn.execute(
                    "UPDATE officials SET birth_year = ?, home_province = ? WHERE id = ?",
                    (best, best_prov, oid),
                )
            fixed += 1

    if not args.dry_run:
        conn.commit()

    print()
    print(f"=== Summary ===")
    print(f"Fixed:                    {fixed}")
    print(f"Already-plausible rows:   {skipped_already_ok}")
    print(f"Skipped (no careers):     {skipped_no_careers}")
    print(f"Ambiguous (need manual):  {len(ambiguous)}")
    for name, oid, db_born, est, cands in ambiguous:
        print(f"  ⚠ {name} id={oid} db={db_born} est={est} candidates={cands}")

    if args.dry_run:
        print("\n(dry run — no changes written)")


if __name__ == "__main__":
    main()
