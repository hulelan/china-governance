"""Compute overlaps between CCP officials based on shared org/province + time.

Two officials "overlap" if they both worked in the same organization (or same
province) during overlapping time periods. The overlap duration is measured in
months.

Strategy:
- Group career records by normalized org key (or by province)
- For each group, compute all pairs with overlapping date ranges
- Store in officials.db `overlaps` table

Usage:
    python3 scripts/compute_overlaps.py              # Compute and save
    python3 scripts/compute_overlaps.py --dry-run    # Preview without saving
    python3 scripts/compute_overlaps.py --stats      # Show overlap stats
"""

import argparse
import sqlite3
import re
from collections import defaultdict
from itertools import combinations
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "officials.db"


SKIP_ORG_PATTERNS = [
    "加入中国共产党", "参加革命工作", "加入共青团", "出生", "生于",
    "学习", "毕业", "学位", "硕士", "博士", "研究生", "本科",
    "结婚", "去世", "逝世", "退休",
]


def normalize_org(org_text):
    """Reduce an org string to a stable key for grouping.

    Returns None for non-org strings (education, party joining, etc.)
    """
    if not org_text:
        return None

    text = org_text.strip()

    # Filter out non-org records
    if any(skip in text for skip in SKIP_ORG_PATTERNS):
        return None

    # Truncate at common position-marking words
    for marker in ["书记", "主任", "局长", "厅长", "部长", "委员", "代表",
                   "省长", "市长", "县长", "主席", "委员长", "总理", "副"]:
        idx = text.find(marker)
        if idx > 4:  # need at least 4 chars of org context
            text = text[:idx]
            break

    text = re.sub(r"[，,、；;\s]+$", "", text).strip()

    # Must contain a recognizable org indicator
    if not any(x in text for x in ["省", "市", "县", "区", "部", "委", "局", "院", "署", "办", "厅", "处", "国务院", "中央", "全国"]):
        return None

    return text if 4 <= len(text) <= 50 else None


def date_to_months(year, month):
    """Convert (year, month) to absolute months since year 0 for arithmetic."""
    if year is None:
        return None
    return year * 12 + (month or 6)  # default mid-year


def overlap_months(a_start, a_end, b_start, b_end):
    """Compute overlap in months between two date ranges.

    Each input is months-since-year-0 or None.
    If end is missing, assume position lasted 4 years (typical CCP term).
    """
    if a_start is None or b_start is None:
        return 0
    a_end = a_end if a_end is not None else a_start + 48  # 4 years default
    b_end = b_end if b_end is not None else b_start + 48

    start = max(a_start, b_start)
    end = min(a_end, b_end)
    return max(0, end - start)


def compute_overlaps(conn, dry_run=False):
    """Compute pairwise overlaps based on shared organization/province."""
    # Load all career records
    rows = conn.execute("""
        SELECT id, official_id, organization, province, start_year, start_month, end_year, end_month
        FROM career_records
        WHERE start_year IS NOT NULL
        ORDER BY official_id, start_year
    """).fetchall()

    print(f"Loaded {len(rows)} career records")

    # Group records by normalized org key
    org_groups = defaultdict(list)
    province_groups = defaultdict(list)

    for record_id, off_id, org, province, sy, sm, ey, em in rows:
        start = date_to_months(sy, sm)
        end = date_to_months(ey, em)
        if start is None:
            continue

        # By organization (more specific)
        org_key = normalize_org(org)
        if org_key:
            org_groups[org_key].append((off_id, start, end, sy, ey))

        # By province (broader, captures co-province even in different orgs)
        if province:
            province_groups[province].append((off_id, start, end, sy, ey))

    print(f"Grouped into {len(org_groups)} unique orgs and {len(province_groups)} provinces")

    # Compute overlaps within each org group
    overlaps_found = []  # (off_a, off_b, org, sy, ey, months)

    for org_key, members in org_groups.items():
        if len(members) < 2:
            continue
        for (a, b) in combinations(members, 2):
            off_a, a_start, a_end, a_sy, a_ey = a
            off_b, b_start, b_end, b_sy, b_ey = b
            if off_a == off_b:
                continue
            months = overlap_months(a_start, a_end, b_start, b_end)
            if months > 0:
                # Ensure a < b for dedup
                if off_a > off_b:
                    off_a, off_b = off_b, off_a
                overlap_start_year = max(a_sy, b_sy)
                # Use whichever end year is earlier, capping at start + 4 years if missing
                a_ey_safe = a_ey if a_ey is not None else (a_sy + 4)
                b_ey_safe = b_ey if b_ey is not None else (b_sy + 4)
                overlap_end_year = min(a_ey_safe, b_ey_safe)
                overlaps_found.append(
                    (off_a, off_b, org_key, None, overlap_start_year, overlap_end_year, months)
                )

    # Note: We deliberately skip province-only overlaps. Sharing "Beijing"
    # doesn't mean two people knew each other — they need to share a specific
    # organization for the overlap to be meaningful.

    print(f"Found {len(overlaps_found)} overlap records")

    if dry_run:
        # Show top 10 by duration
        overlaps_found.sort(key=lambda x: -x[6])
        print("\nTop 10 longest overlaps:")
        for off_a, off_b, org, prov, sy, ey, months in overlaps_found[:10]:
            name_a = conn.execute("SELECT name_cn FROM officials WHERE id=?", (off_a,)).fetchone()[0]
            name_b = conn.execute("SELECT name_cn FROM officials WHERE id=?", (off_b,)).fetchone()[0]
            loc = org or prov
            print(f"  {name_a} ↔ {name_b} | {loc} | {sy}-{ey} ({months} months)")
        return

    # Save to DB
    print("Saving to overlaps table...")
    conn.execute("DELETE FROM overlaps")
    for off_a, off_b, org, prov, sy, ey, months in overlaps_found:
        try:
            conn.execute(
                """INSERT OR IGNORE INTO overlaps
                   (official_a, official_b, organization, province,
                    overlap_start_year, overlap_end_year, overlap_months)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (off_a, off_b, org, prov, sy, ey, months),
            )
        except sqlite3.IntegrityError:
            pass
    conn.commit()
    print(f"Saved {conn.execute('SELECT COUNT(*) FROM overlaps').fetchone()[0]} overlap records")


def show_stats(conn):
    """Show overlap statistics."""
    total = conn.execute("SELECT COUNT(*) FROM overlaps").fetchone()[0]
    print(f"Total overlap records: {total}")

    by_loc = conn.execute("""
        SELECT COALESCE(organization, province) as loc, COUNT(*)
        FROM overlaps
        GROUP BY loc
        ORDER BY 2 DESC
        LIMIT 10
    """).fetchall()
    print("\nTop 10 locations by overlap count:")
    for loc, n in by_loc:
        print(f"  {loc}: {n}")

    print("\nTop 10 longest overlaps:")
    for row in conn.execute("""
        SELECT a.name_cn, b.name_cn,
               COALESCE(o.organization, o.province),
               o.overlap_start_year, o.overlap_end_year, o.overlap_months
        FROM overlaps o
        JOIN officials a ON a.id = o.official_a
        JOIN officials b ON b.id = o.official_b
        ORDER BY o.overlap_months DESC
        LIMIT 10
    """).fetchall():
        print(f"  {row[0]} ↔ {row[1]} | {row[2]} | {row[3]}-{row[4]} ({row[5]} months)")

    # Most-connected officials
    print("\nMost-connected officials (by overlap count):")
    for row in conn.execute("""
        SELECT name, cnt FROM (
            SELECT a.name_cn as name, COUNT(*) as cnt
            FROM overlaps o JOIN officials a ON a.id = o.official_a
            GROUP BY a.id
            UNION ALL
            SELECT b.name_cn as name, COUNT(*) as cnt
            FROM overlaps o JOIN officials b ON b.id = o.official_b
            GROUP BY b.id
        ) GROUP BY name ORDER BY SUM(cnt) DESC LIMIT 15
    """).fetchall():
        print(f"  {row[0]}: {row[1]}")


def main():
    parser = argparse.ArgumentParser(description="Compute CCP official career overlaps")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--stats", action="store_true")
    args = parser.parse_args()

    conn = sqlite3.connect(str(DB_PATH))
    if args.stats:
        show_stats(conn)
    else:
        compute_overlaps(conn, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
