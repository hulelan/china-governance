"""Baidu Baike crawler for CPC Central Committee members.

Fetches biographical pages from baike.baidu.com and stores raw HTML +
extracted career text in officials.db.

Usage:
    python3 -m crawlers.baike                    # Crawl all uncrawled members
    python3 -m crawlers.baike --limit 10         # Crawl 10 members
    python3 -m crawlers.baike --stats            # Show crawl progress
    python3 -m crawlers.baike --parse            # Parse career records from crawled pages
    python3 -m crawlers.baike --parse --dry-run  # Preview parsing
"""

import argparse
import json
import logging
import re
import sqlite3
import time
import urllib.parse
from pathlib import Path

from crawlers.baike_career import parse_career_text  # noqa: F401  (re-exported)

# openpyxl / requests / bs4 are imported where they are used, so `--parse` and
# `--stats` run on a machine that has only the standard library.

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s", datefmt="%H:%M:%S")
log = logging.getLogger(__name__)

DB_PATH = Path(__file__).parent.parent / "officials.db"
EXCEL_PATH = Path.home() / "Downloads" / "CPC_Elite_Leadership_Database.xlsx"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
}

# Rate limit: polite crawling
REQUEST_DELAY = 2.0  # seconds between requests


def init_db(db_path=None):
    """Create tables if they don't exist."""
    conn = sqlite3.connect(str(db_path or DB_PATH))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=30000")
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS officials (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name_en TEXT,
            name_cn TEXT,
            birth_year INTEGER,
            home_province TEXT,
            cc_congresses TEXT,
            is_politburo INTEGER DEFAULT 0,
            is_psc INTEGER DEFAULT 0,
            baike_url TEXT,
            baike_html TEXT,
            baike_career_text TEXT,
            crawl_status TEXT DEFAULT 'pending',
            crawl_timestamp TEXT,
            parse_status TEXT DEFAULT 'pending'
        );
        -- Two distinct people can share a Chinese name (李强, 王宁, 刘伟,
        -- ...). The Excel source had 31 such collisions. Uniqueness must
        -- be on (name_cn, birth_year), not name_cn alone. The original
        -- DB shipped with `name_cn UNIQUE` and `INSERT OR IGNORE` silently
        -- dropped the second twin in each collision; see
        -- scripts/fix_baike_collisions.py for the historical repair.
        CREATE UNIQUE INDEX IF NOT EXISTS idx_officials_name_birth
            ON officials(name_cn, birth_year);

        CREATE TABLE IF NOT EXISTS career_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            official_id INTEGER NOT NULL,
            position TEXT,
            organization TEXT,
            province TEXT,
            admin_level TEXT,
            start_year INTEGER,
            start_month INTEGER,
            end_year INTEGER,
            end_month INTEGER,
            raw_text TEXT,
            FOREIGN KEY (official_id) REFERENCES officials(id)
        );

        CREATE TABLE IF NOT EXISTS overlaps (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            official_a INTEGER NOT NULL,
            official_b INTEGER NOT NULL,
            organization TEXT,
            province TEXT,
            overlap_start_year INTEGER,
            overlap_end_year INTEGER,
            overlap_months INTEGER,
            FOREIGN KEY (official_a) REFERENCES officials(id),
            FOREIGN KEY (official_b) REFERENCES officials(id),
            UNIQUE(official_a, official_b, organization, overlap_start_year)
        );

        CREATE INDEX IF NOT EXISTS idx_career_official ON career_records(official_id);
        CREATE INDEX IF NOT EXISTS idx_career_org ON career_records(organization);
        CREATE INDEX IF NOT EXISTS idx_career_province ON career_records(province);
        CREATE INDEX IF NOT EXISTS idx_overlaps_a ON overlaps(official_a);
        CREATE INDEX IF NOT EXISTS idx_overlaps_b ON overlaps(official_b);
    """)
    conn.commit()
    return conn


def load_members_from_excel(conn):
    """Load CC members from Excel into officials table (skip existing).

    Two CC members can share a Chinese name (the Excel had 31 collisions).
    We dedupe by `(name_cn, birth_year)` so both twins survive — keyed by
    name alone would silently drop one of them, which is how we ended up
    with the wrong 李强 in the original DB load.
    """
    import openpyxl
    wb = openpyxl.load_workbook(str(EXCEL_PATH), read_only=True)

    # Collect CC membership info, keyed by (name_cn, birth_year)
    ws = wb["CC Members"]
    member_info: dict[tuple, dict] = {}
    for i, row in enumerate(ws.iter_rows(values_only=True)):
        if i == 0:
            continue
        congress, name_en, name_cn, birth_year, province = row[0], row[1], row[2], row[3], row[4]
        is_pb, is_psc = row[6], row[7]
        if not name_cn:
            continue
        key = (name_cn, birth_year)
        if key not in member_info:
            member_info[key] = {
                "name_en": name_en,
                "name_cn": name_cn,
                "birth_year": birth_year,
                "province": province,
                "congresses": [],
                "is_pb": False,
                "is_psc": False,
            }
        member_info[key]["congresses"].append(congress)
        if is_pb == "Y":
            member_info[key]["is_pb"] = True
        if is_psc == "Y":
            member_info[key]["is_psc"] = True

    # Insert into DB
    inserted = 0
    for info in member_info.values():
        try:
            conn.execute(
                """INSERT OR IGNORE INTO officials
                   (name_en, name_cn, birth_year, home_province, cc_congresses, is_politburo, is_psc)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (info["name_en"], info["name_cn"], info["birth_year"], info["province"],
                 json.dumps(info["congresses"]), int(info["is_pb"]), int(info["is_psc"])),
            )
            if conn.execute("SELECT changes()").fetchone()[0] > 0:
                inserted += 1
        except sqlite3.IntegrityError:
            pass
    conn.commit()
    log.info(f"Loaded {inserted} new officials from Excel ({len(member_info)} unique by (name, birth))")
    return len(member_info)


def fetch_baike_page(name_cn, birth_year=None):
    """Fetch a Baidu Baike page for a person. Returns (url, html, career_text) or None."""
    encoded = urllib.parse.quote(name_cn)
    url = f"https://baike.baidu.com/item/{encoded}"

    import requests
    from bs4 import BeautifulSoup
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15, allow_redirects=True)
        if resp.status_code != 200:
            return None

        html = resp.text
        soup = BeautifulSoup(html, "html.parser")

        # Extract career/biography text
        career_text = _extract_career_text(soup)

        # Disambiguate: if birth year is given, check if page matches
        if birth_year and career_text:
            if str(birth_year) not in html[:5000]:
                # Try disambiguation page
                log.debug(f"Birth year {birth_year} not found for {name_cn}, might be wrong person")

        return url, html, career_text

    except Exception as e:
        log.warning(f"Failed to fetch {name_cn}: {e}")
        return None


_CAREER_LINE = re.compile(r"^\d{4}\s*[\.\-年—–－~～至/]|^\d{4}\s+\S")


def _paragraph_lines(soup):
    """One string per Baike paragraph, inline spans JOINED.

    Baike wraps every hyperlink and every run of plain text in its own <span>, so
    `get_text("\n")` cut career lines at each link: "2011-2014 外交部新闻司司" /
    "长、外交部发言人", or a bare "1963.09——1968.08，" whose post was a link and was
    lost. Reading paragraph by paragraph keeps the line whole. Footnote markers
    ([3]) and picture captions are dropped.
    """
    lines = []
    for para in soup.find_all(attrs={"data-tag": "paragraph"}):
        for junk in para.find_all(
                lambda t: t.name in ("sup", "svg", "img")
                or any(c.startswith(("supWrap", "lemmaPicture")) for c in (t.get("class") or []))):
            junk.decompose()
        for br in para.find_all("br"):
            br.replace_with("\n")
        for part in para.get_text("").split("\n"):
            part = re.sub(r"[ \t\xa0]+", " ", part).strip()
            if part:
                lines.append(part)
    return lines


def _extract_career_text(soup):
    """Extract career/biography section from Baidu Baike page.

    Career lines are those starting with a year: 1975.09-1978.12 …, 1975年9月 …,
    1982 － 1988 ….
    """
    # Remove script and style elements
    for tag in soup(["script", "style"]):
        tag.decompose()

    para_lines = _paragraph_lines(soup)
    full_text = soup.get_text("\n", strip=True)
    lines = para_lines or full_text.split("\n")

    career_lines = []
    for line in lines:
        line = line.strip()
        if line and _CAREER_LINE.match(line) and len(line) > (9 if para_lines else 15):
            career_lines.append(line)

    if career_lines:
        return "\n".join(career_lines)

    lines = full_text.split("\n")
    # Fallback: look for any lines with career keywords
    keyword_lines = []
    for line in lines:
        if any(kw in line for kw in ["书记", "市长", "省长", "部长", "主任", "副"]) and len(line) > 20:
            keyword_lines.append(line)

    if keyword_lines:
        return "\n".join(keyword_lines[:50])

    # Last resort: return the meta description
    meta = soup.find("meta", attrs={"name": "description"})
    if meta and meta.get("content"):
        return meta["content"]

    return ""


def reextract_career_text(conn, dry_run=False):
    """Rebuild baike_career_text from the STORED baike_html (no network).

    Only replaces a text when the new one has at least as many dated lines, so a
    page on an older template that the paragraph reader cannot see keeps what it had.
    """
    from bs4 import BeautifulSoup
    rows = conn.execute(
        "SELECT id, name_cn, baike_html, baike_career_text FROM officials "
        "WHERE crawl_status='done' AND baike_html IS NOT NULL AND baike_html != ''"
    ).fetchall()
    changed = kept = 0
    for official_id, name_cn, html, old in rows:
        new = _extract_career_text(BeautifulSoup(html, "html.parser"))
        n_old = sum(1 for ln in (old or "").split("\n") if _CAREER_LINE.match(ln))
        n_new = sum(1 for ln in new.split("\n") if _CAREER_LINE.match(ln))
        if not new or new == old or (n_new == 0 and n_old > 0):
            kept += 1
            continue
        changed += 1
        if not dry_run:
            conn.execute("UPDATE officials SET baike_career_text=? WHERE id=?", (new, official_id))
    if not dry_run:
        conn.commit()
    log.info(f"Re-extracted career text: {changed} changed, {kept} kept, of {len(rows)}")
    return changed


def crawl_officials(conn, limit=None):
    """Crawl Baidu Baike pages for officials with status='pending'."""
    cursor = conn.execute(
        "SELECT id, name_cn, birth_year FROM officials WHERE crawl_status = 'pending' ORDER BY is_psc DESC, is_politburo DESC, id"
    )
    rows = cursor.fetchall()

    if limit:
        rows = rows[:limit]

    log.info(f"Crawling {len(rows)} officials from Baidu Baike...")
    success = 0
    failed = 0

    for i, (official_id, name_cn, birth_year) in enumerate(rows):
        result = fetch_baike_page(name_cn, birth_year)

        if result:
            url, html, career_text = result
            conn.execute(
                """UPDATE officials SET baike_url=?, baike_html=?, baike_career_text=?,
                   crawl_status='done', crawl_timestamp=datetime('now')
                   WHERE id=?""",
                (url, html, career_text, official_id),
            )
            success += 1
            career_preview = (career_text or "")[:80].replace("\n", " ")
            log.info(f"[{i+1}/{len(rows)}] {name_cn} — {career_preview}...")
        else:
            conn.execute(
                "UPDATE officials SET crawl_status='failed', crawl_timestamp=datetime('now') WHERE id=?",
                (official_id,),
            )
            failed += 1
            log.warning(f"[{i+1}/{len(rows)}] {name_cn} — FAILED")

        conn.commit()
        time.sleep(REQUEST_DELAY)

    log.info(f"Done: {success} success, {failed} failed")


# --- Step 2: Programmatic career parsing ---
# The parser lives in crawlers/baike_career.py (stdlib only, unit-tested in
# tests/test_baike_career.py). One row per held post body; see its docstring.


def parse_all_officials(conn, dry_run=False):
    """Parse career text for all crawled officials."""
    cursor = conn.execute(
        "SELECT id, name_cn, baike_career_text FROM officials WHERE crawl_status='done' AND baike_career_text IS NOT NULL"
    )
    rows = cursor.fetchall()
    log.info(f"Parsing career records for {len(rows)} officials...")

    total_records = 0
    for official_id, name_cn, career_text in rows:
        records = parse_career_text(career_text)
        total_records += len(records)

        if dry_run:
            if records:
                log.info(f"{name_cn}: {len(records)} records")
                for r in records[:3]:
                    log.info(f"  {r['raw_text']} → {r['organization']} | {r['province']} | {r['admin_level']}")
            continue

        # Delete old records and insert new
        conn.execute("DELETE FROM career_records WHERE official_id=?", (official_id,))
        for r in records:
            conn.execute(
                """INSERT INTO career_records
                   (official_id, position, organization, province, admin_level,
                    start_year, start_month, end_year, end_month, raw_text)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (official_id, r["position"], r["organization"], r["province"],
                 r["admin_level"], r["start_year"], r["start_month"],
                 r["end_year"], r["end_month"], r["raw_text"]),
            )
        conn.execute("UPDATE officials SET parse_status='done' WHERE id=?", (official_id,))
    if not dry_run:
        conn.commit()

    log.info(f"Total: {total_records} career records from {len(rows)} officials")


def show_stats(conn):
    """Show crawl and parse progress."""
    total = conn.execute("SELECT COUNT(*) FROM officials").fetchone()[0]
    crawled = conn.execute("SELECT COUNT(*) FROM officials WHERE crawl_status='done'").fetchone()[0]
    failed = conn.execute("SELECT COUNT(*) FROM officials WHERE crawl_status='failed'").fetchone()[0]
    pending = conn.execute("SELECT COUNT(*) FROM officials WHERE crawl_status='pending'").fetchone()[0]
    parsed = conn.execute("SELECT COUNT(*) FROM officials WHERE parse_status='done'").fetchone()[0]
    records = conn.execute("SELECT COUNT(*) FROM career_records").fetchone()[0]
    pb = conn.execute("SELECT COUNT(*) FROM officials WHERE is_politburo=1").fetchone()[0]
    psc = conn.execute("SELECT COUNT(*) FROM officials WHERE is_psc=1").fetchone()[0]

    print(f"Officials: {total} total ({pb} Politburo, {psc} PSC)")
    print(f"Crawled:   {crawled} done, {failed} failed, {pending} pending")
    print(f"Parsed:    {parsed} officials → {records} career records")


def main():
    parser = argparse.ArgumentParser(description="Baidu Baike CPC official crawler")
    parser.add_argument("--limit", type=int, help="Max officials to crawl")
    parser.add_argument("--stats", action="store_true", help="Show progress stats")
    parser.add_argument("--parse", action="store_true", help="Parse career records from crawled pages")
    parser.add_argument("--dry-run", action="store_true", help="Preview parsing without saving")
    parser.add_argument("--reextract", action="store_true",
                        help="Rebuild baike_career_text from the stored baike_html (no network)")
    parser.add_argument("--db", help="officials.db to work on (default: repo officials.db). "
                                     "Re-parse a COPY, never the file the web app is reading.")
    args = parser.parse_args()

    # Re-parsing needs no seed list (the Excel file exists only on the Mac) and
    # must not touch the schema of the file it was pointed at.
    offline = args.stats or args.parse or args.reextract
    if offline:
        conn = sqlite3.connect(str(args.db or DB_PATH))
        conn.execute("PRAGMA busy_timeout=30000")
    else:
        conn = init_db(args.db)
    if not offline:
        if not EXCEL_PATH.exists():
            parser.error(f"seed list not found: {EXCEL_PATH}")
        load_members_from_excel(conn)

    if args.stats:
        show_stats(conn)
        return

    if args.reextract:
        reextract_career_text(conn, dry_run=args.dry_run)
        if not args.parse:
            return

    if args.parse:
        parse_all_officials(conn, dry_run=args.dry_run)
        return

    crawl_officials(conn, limit=args.limit)


if __name__ == "__main__":
    main()
