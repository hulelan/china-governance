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

import openpyxl
import requests
from bs4 import BeautifulSoup

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


def init_db():
    """Create tables if they don't exist."""
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=30000")
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS officials (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name_en TEXT,
            name_cn TEXT UNIQUE,
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
    """Load CC members from Excel into officials table (skip existing)."""
    wb = openpyxl.load_workbook(str(EXCEL_PATH), read_only=True)

    # Collect CC membership info
    ws = wb["CC Members"]
    member_info = {}  # name_cn -> {congresses, is_pb, is_psc, ...}
    for i, row in enumerate(ws.iter_rows(values_only=True)):
        if i == 0:
            continue
        congress, name_en, name_cn, birth_year, province = row[0], row[1], row[2], row[3], row[4]
        is_pb, is_psc = row[6], row[7]
        if not name_cn:
            continue
        if name_cn not in member_info:
            member_info[name_cn] = {
                "name_en": name_en,
                "birth_year": birth_year,
                "province": province,
                "congresses": [],
                "is_pb": False,
                "is_psc": False,
            }
        member_info[name_cn]["congresses"].append(congress)
        if is_pb == "Y":
            member_info[name_cn]["is_pb"] = True
        if is_psc == "Y":
            member_info[name_cn]["is_psc"] = True

    # Insert into DB
    inserted = 0
    for name_cn, info in member_info.items():
        try:
            conn.execute(
                """INSERT OR IGNORE INTO officials
                   (name_en, name_cn, birth_year, home_province, cc_congresses, is_politburo, is_psc)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (info["name_en"], name_cn, info["birth_year"], info["province"],
                 json.dumps(info["congresses"]), int(info["is_pb"]), int(info["is_psc"])),
            )
            if conn.execute("SELECT changes()").fetchone()[0] > 0:
                inserted += 1
        except sqlite3.IntegrityError:
            pass
    conn.commit()
    log.info(f"Loaded {inserted} new officials from Excel ({len(member_info)} total unique)")
    return len(member_info)


def fetch_baike_page(name_cn, birth_year=None):
    """Fetch a Baidu Baike page for a person. Returns (url, html, career_text) or None."""
    encoded = urllib.parse.quote(name_cn)
    url = f"https://baike.baidu.com/item/{encoded}"

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


def _extract_career_text(soup):
    """Extract career/biography section from Baidu Baike page.

    Baidu Baike renders article content client-side, but the text is still
    in the HTML. We extract all text and look for structured career lines
    in the format: YYYY.MM-YYYY.MM position  or  YYYY年M月 position
    """
    # Remove script and style elements
    for tag in soup(["script", "style"]):
        tag.decompose()

    full_text = soup.get_text("\n", strip=True)
    lines = full_text.split("\n")

    # Look for structured career lines (YYYY.MM-YYYY.MM or YYYY年M月)
    career_lines = []
    career_pattern = re.compile(r"^\d{4}[\.\-年]")

    for line in lines:
        line = line.strip()
        if not line:
            continue
        # Match career timeline format: 1975.09-1978.12 or 1975年9月
        if career_pattern.match(line) and len(line) > 15:
            # Skip birth/education-only lines that are too short
            career_lines.append(line)

    if career_lines:
        return "\n".join(career_lines)

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

# Patterns for extracting career records from Chinese biographical text
# Format 1: YYYY.MM-YYYY.MM position (Baike style A)
CAREER_PATTERN_DOT = re.compile(
    r"(\d{4})\.(\d{1,2})-(\d{4})\.(\d{1,2})\s+(.+)"
)
# Format 2: YYYY-YYYY年 position (Baike style B — top leaders)
CAREER_PATTERN_RANGE = re.compile(
    r"(\d{4})-(\d{4})年\s+(.+)"
)
# Format 3: YYYY年M月 position (older narrative style)
CAREER_PATTERN_CN = re.compile(
    r"(\d{4})年(?:(\d{1,2})月)?[，,、\s—-]*"
    r"(?:任|担任|兼任|调任|转任|升任|当选|出任|改任|晋升|被任命|受命|就任|授予|选举|聘为|提拔|调入|进入|赴|到|在)?"
    r"\s*(.+?)(?=[。；;$\n]|(?=\d{4}年))"
)

# Province/city detection
PROVINCES = {
    "北京": "Beijing", "天津": "Tianjin", "上海": "Shanghai", "重庆": "Chongqing",
    "河北": "Hebei", "山西": "Shanxi", "辽宁": "Liaoning", "吉林": "Jilin",
    "黑龙江": "Heilongjiang", "江苏": "Jiangsu", "浙江": "Zhejiang", "安徽": "Anhui",
    "福建": "Fujian", "江西": "Jiangxi", "山东": "Shandong", "河南": "Henan",
    "湖北": "Hubei", "湖南": "Hunan", "广东": "Guangdong", "海南": "Hainan",
    "四川": "Sichuan", "贵州": "Guizhou", "云南": "Yunnan", "陕西": "Shaanxi",
    "甘肃": "Gansu", "青海": "Qinghai", "台湾": "Taiwan",
    "内蒙古": "Inner Mongolia", "广西": "Guangxi", "西藏": "Tibet",
    "宁夏": "Ningxia", "新疆": "Xinjiang",
}

CENTRAL_ORGS = [
    "国务院", "中央", "全国人大", "全国政协", "中共中央", "中纪委", "中央纪委",
    "中央军委", "国家", "最高人民法院", "最高人民检察院",
    "中国人民银行", "外交部", "国防部", "财政部", "商务部", "工信部",
    "教育部", "科技部", "公安部", "民政部", "司法部", "人社部",
    "自然资源部", "生态环境部", "住建部", "交通运输部", "水利部",
    "农业农村部", "文旅部", "卫健委", "退役军人事务部", "应急管理部",
    "审计署", "国资委", "市场监管总局", "发改委", "统计局",
]


def _detect_province(text):
    """Detect province from position text."""
    for cn, en in PROVINCES.items():
        if cn in text:
            return cn
    return None


def _detect_admin_level(text, province):
    """Detect admin level from position text."""
    if any(org in text for org in CENTRAL_ORGS):
        return "central"
    if province and ("省" in text or "自治区" in text or province + "市" in text for p in ["北京", "天津", "上海", "重庆"] if p == province):
        return "provincial"
    if "市" in text and "区" not in text:
        return "municipal"
    if "区" in text or "县" in text:
        return "district"
    if province:
        return "provincial"
    return "unknown"


def parse_career_text(career_text):
    """Parse career text into structured records.

    Handles two formats:
    - YYYY.MM-YYYY.MM position (most common on modern Baike pages)
    - YYYY年M月 position (older style)

    Returns list of dicts with position, organization, province, etc.
    """
    if not career_text:
        return []

    records = []

    for line in career_text.split("\n"):
        line = line.strip()
        if not line:
            continue

        # Skip education/parenthetical lines
        if line.startswith("（") or line.startswith("("):
            continue

        start_year = start_month = end_year = end_month = None
        position_text = ""

        # Format 1: YYYY.MM-YYYY.MM position
        m = CAREER_PATTERN_DOT.match(line)
        if m:
            start_year, start_month = int(m.group(1)), int(m.group(2))
            end_year, end_month = int(m.group(3)), int(m.group(4))
            position_text = m.group(5).strip()
        else:
            # Format 2: YYYY-YYYY年 position (top leaders)
            m2 = CAREER_PATTERN_RANGE.match(line)
            if m2:
                start_year = int(m2.group(1))
                end_year = int(m2.group(2))
                position_text = m2.group(3).strip()
            else:
                # Format 3: YYYY年M月 position (narrative)
                m3 = CAREER_PATTERN_CN.match(line)
                if m3:
                    start_year = int(m3.group(1))
                    start_month = int(m3.group(2)) if m3.group(2) else None
                    position_text = m3.group(3).strip()

        if not position_text or not start_year:
            continue
        if len(position_text) < 2 or len(position_text) > 200:
            continue
        # Skip birth/education entries
        if any(skip in position_text for skip in ["出生", "生于", "入学", "学习", "专业", "毕业", "学位", "结婚"]):
            continue

        province = _detect_province(position_text)
        admin_level = _detect_admin_level(position_text, province)

        # Try to split organization from position title
        org = ""
        pos = position_text
        org_match = re.match(
            r"(.+?(?:省|市|区|县|部|委|局|院|署|办|厅|处|总|公司|集团|银行|大学|学院|工厂|军区|政府))"
            r"\s*(.+)", position_text
        )
        if org_match and len(org_match.group(2)) > 1:
            org = org_match.group(1)
            pos = org_match.group(2)

        records.append({
            "position": pos,
            "organization": org or position_text,
            "province": province,
            "admin_level": admin_level,
            "start_year": start_year,
            "start_month": start_month,
            "end_year": end_year,
            "end_month": end_month,
            "raw_text": line,
        })

    # For format 2 (no end dates): infer from next record
    for i in range(len(records) - 1):
        if records[i]["end_year"] is None:
            records[i]["end_year"] = records[i + 1]["start_year"]
            records[i]["end_month"] = records[i + 1]["start_month"]

    return records


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
    args = parser.parse_args()

    conn = init_db()

    # Always load/update from Excel
    load_members_from_excel(conn)

    if args.stats:
        show_stats(conn)
        return

    if args.parse:
        parse_all_officials(conn, dry_run=args.dry_run)
        return

    crawl_officials(conn, limit=args.limit)


if __name__ == "__main__":
    main()
