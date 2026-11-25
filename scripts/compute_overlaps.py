"""Compute overlaps between CCP officials: same body, overlapping tenure.

`career_records.organization` is a canonical key written by
`crawlers/baike_career.py` (北京市委, 北京市政府, 清华大学, 中央组织部 …), one row per
held post, so two officials overlap when they hold a row with the SAME key over
intersecting months. A multi-post entry ("中央政治局委员，北京市委书记") therefore
pairs its holder with colleagues in each body, not only the first one named.

Rules
- Each official's rows in one body are merged into a union of month intervals
  first, so three consecutive rows (2017.05-2017.06, 2017.06-2018.01,
  2018.01-2022.10) give ONE overlap row per colleague, not three.
- Year-only dates sit mid-year (month 6); a same-year entry counts 6 months.
- A post with no end (end_year NULL: "2022.10-", "至今", or a last narrative
  "1975年1月，当选…") runs to the crawl date if it began within 5 years of it,
  i.e. it is plausibly current. Otherwise the end is simply unknown (the page of
  a long-retired official often stops on such a line) and it counts 2 years.
- Rows of one official in one body that are at most 2 months apart are one tenure.
- An overlap shorter than 6 months is kept only when both sides carry month-
  precise dates. With year-only or unknown-end dates a short overlap is usually
  a predecessor and successor touching (王安顺 left 北京市政府 2016.10, 蔡奇's
  "2016-2017年" row sits at mid-2016), not two people serving together.
- Mass bodies are not a workplace. Membership of 中央委员会 / 全国人大 / 全国政协 /
  a military service as a whole pairs hundreds of people who never worked
  together, so those keys count only for their leadership posts.

Usage:
    python3 scripts/compute_overlaps.py --db COPY.db            # compute and save
    python3 scripts/compute_overlaps.py --db COPY.db --dry-run  # preview
    python3 scripts/compute_overlaps.py --stats                 # overlap stats
"""

import argparse
import re
import sqlite3
from collections import defaultdict
from itertools import combinations
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "officials.db"

OPEN_ENDED_CAP_MONTHS = 60       # a post begun within this of the crawl is "current"
UNKNOWN_END_MONTHS = 24          # otherwise the end is unknown: assume two years
MERGE_GAP_MONTHS = 2
MIN_FUZZY_OVERLAP = 6
MIN_KEY_LEN = 3

# body -> titles that count. A body listed here pairs only its leadership.
_LEAD = r"主席|委员长|秘书长|书记|主任|司令|政治委员|政委|参谋长|部长|院长|校长"
MASS_BODIES = {
    "中央委员会": None,                       # never: every official here is a member
    "全国人大": _LEAD,
    "全国人大常委会": _LEAD,
    "全国政协": _LEAD,
    "中央顾问委员会": _LEAD,
    "中央纪委": _LEAD + r"|常委",
    "陆军": _LEAD, "空军": _LEAD, "海军": _LEAD, "火箭军": _LEAD, "第二炮兵": _LEAD, "武警": _LEAD,
    "武警部队": _LEAD, "八路军": _LEAD, "新四军": _LEAD, "红军": _LEAD, "志愿军": _LEAD,
    "中国人民志愿军": _LEAD, "中国工农红军": _LEAD, "工农红军": _LEAD,
    "中国科学院": _LEAD, "中国工程院": _LEAD, "共青团中央": _LEAD,
}


def counts_for_overlap(org, position):
    """False for a row that is membership of a mass body rather than a shared workplace."""
    if not org or len(org) < MIN_KEY_LEN:
        return False
    if org in MASS_BODIES:
        pat = MASS_BODIES[org]
        return bool(pat and re.search(pat, position or ""))
    return True


def to_interval(sy, sm, ey, em, as_of):
    """(start, end, fuzzy) in months since year 0, end exclusive; None if unusable.

    fuzzy = an endpoint is year-only or the end is unknown.
    """
    if sy is None:
        return None
    start = sy * 12 + (sm or 6)
    fuzzy = sm is None
    if ey is None:
        fuzzy = True
        if start + OPEN_ENDED_CAP_MONTHS >= as_of:
            end = as_of
        else:
            end = start + UNKNOWN_END_MONTHS
    else:
        end = ey * 12 + (em or 6)
        fuzzy = fuzzy or em is None
        if end <= start and ey == sy and (sm is None or em is None):
            end = start + 6            # "2017-2017年": some part of that year
    if end <= start:
        end = start + 1
    return start, end, fuzzy


def merge(intervals):
    out = []
    for s, e, fuzzy in sorted(intervals):
        if out and s <= out[-1][1] + MERGE_GAP_MONTHS:
            out[-1][1] = max(out[-1][1], e)
            out[-1][2] = out[-1][2] or fuzzy
        else:
            out.append([s, e, fuzzy])
    return out


def intersect(a, b):
    """Intersections of two merged interval lists."""
    out, i, j = [], 0, 0
    while i < len(a) and j < len(b):
        s, e = max(a[i][0], b[j][0]), min(a[i][1], b[j][1])
        if e > s and (e - s >= MIN_FUZZY_OVERLAP or not (a[i][2] or b[j][2])):
            out.append((s, e))
        if a[i][1] < b[j][1]:
            i += 1
        else:
            j += 1
    return out


def _year(months):
    """Calendar year of a month index built as year*12 + month (month 1-12)."""
    return (months - 1) // 12


def crawl_as_of(conn):
    row = conn.execute("SELECT MAX(crawl_timestamp) FROM officials").fetchone()
    ts = row[0] if row and row[0] else None
    m = re.match(r"(\d{4})-(\d{2})", ts or "")
    return int(m.group(1)) * 12 + int(m.group(2)) if m else 2026 * 12 + 4


def find_overlaps(rows, as_of):
    """rows: (official_id, organization, position, province, sy, sm, ey, em).

    Returns [(off_a, off_b, organization, province, start_year, end_year, months)],
    off_a < off_b, one row per contiguous shared period in one body.
    """
    by_org = defaultdict(lambda: defaultdict(list))
    prov = defaultdict(set)
    for off_id, org, pos, province, sy, sm, ey, em in rows:
        if not counts_for_overlap(org, pos):
            continue
        iv = to_interval(sy, sm, ey, em, as_of)
        if iv is None:
            continue
        by_org[org][off_id].append(iv)
        prov[org].add(province)

    found = []
    for org, members in by_org.items():
        if len(members) < 2:
            continue
        merged = {off: merge(ivs) for off, ivs in members.items()}
        province = next(iter(prov[org])) if len(prov[org]) == 1 else None
        for a, b in combinations(sorted(merged), 2):
            for s, e in intersect(merged[a], merged[b]):
                found.append((a, b, org, province, _year(s), _year(e), e - s))
    return found


def compute_overlaps(conn, dry_run=False):
    rows = conn.execute("""
        SELECT official_id, organization, position, province,
               start_year, start_month, end_year, end_month
        FROM career_records
        WHERE start_year IS NOT NULL
    """).fetchall()
    print(f"Loaded {len(rows)} career records")
    found = find_overlaps(rows, crawl_as_of(conn))
    print(f"Found {len(found)} overlap records")

    if dry_run:
        names = dict(conn.execute("SELECT id, name_cn FROM officials"))
        print("\nTop 10 longest overlaps:")
        for a, b, org, _prov, sy, ey, months in sorted(found, key=lambda x: -x[6])[:10]:
            print(f"  {names[a]} ↔ {names[b]} | {org} | {sy}-{ey} ({months} months)")
        return found

    print("Saving to overlaps table...")
    conn.execute("DELETE FROM overlaps")
    conn.executemany(
        """INSERT OR IGNORE INTO overlaps
           (official_a, official_b, organization, province,
            overlap_start_year, overlap_end_year, overlap_months)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        found,
    )
    conn.commit()
    print(f"Saved {conn.execute('SELECT COUNT(*) FROM overlaps').fetchone()[0]} overlap records")
    return found


def show_stats(conn):
    """Show overlap statistics."""
    total = conn.execute("SELECT COUNT(*) FROM overlaps").fetchone()[0]
    print(f"Total overlap records: {total}")
    connected = conn.execute(
        "SELECT COUNT(*) FROM (SELECT official_a AS o FROM overlaps UNION SELECT official_b FROM overlaps)"
    ).fetchone()[0]
    officials = conn.execute("SELECT COUNT(*) FROM officials").fetchone()[0]
    print(f"Officials with at least one overlap: {connected} of {officials}")

    print("\nTop 10 bodies by overlap count:")
    for loc, n in conn.execute("""
        SELECT COALESCE(organization, province) AS loc, COUNT(*)
        FROM overlaps GROUP BY loc ORDER BY 2 DESC LIMIT 10
    """):
        print(f"  {loc}: {n}")

    print("\nTop 10 longest overlaps:")
    for row in conn.execute("""
        SELECT a.name_cn, b.name_cn, COALESCE(o.organization, o.province),
               o.overlap_start_year, o.overlap_end_year, o.overlap_months
        FROM overlaps o
        JOIN officials a ON a.id = o.official_a
        JOIN officials b ON b.id = o.official_b
        ORDER BY o.overlap_months DESC LIMIT 10
    """):
        print(f"  {row[0]} ↔ {row[1]} | {row[2]} | {row[3]}-{row[4]} ({row[5]} months)")


def main():
    parser = argparse.ArgumentParser(description="Compute CCP official career overlaps")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--stats", action="store_true")
    parser.add_argument("--db", help="officials.db to work on (default: repo officials.db). "
                                     "Rebuild a COPY, never the file the web app is reading.")
    args = parser.parse_args()

    conn = sqlite3.connect(str(args.db or DB_PATH))
    conn.execute("PRAGMA busy_timeout=30000")
    if args.stats:
        show_stats(conn)
    else:
        compute_overlaps(conn, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
