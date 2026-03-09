"""Show coverage by admin level and site."""
import sqlite3

conn = sqlite3.connect("documents.db")

rows = conn.execute("""
    SELECT s.admin_level, s.name, s.site_key,
           COUNT(*) as total,
           SUM(CASE WHEN d.body_text_cn IS NOT NULL AND d.body_text_cn != '' THEN 1 ELSE 0 END) as with_body
    FROM documents d
    JOIN sites s ON s.site_key = d.site_key
    GROUP BY s.admin_level, s.name, s.site_key
    ORDER BY s.admin_level, total DESC
""").fetchall()

current_level = None
for level, name, sk, total, body in rows:
    if level != current_level:
        current_level = level
        print(f"\n{'='*60}")
        print(f"  {level or 'unknown'} level")
        print(f"{'='*60}")
    pct = 100 * body / total if total > 0 else 0
    bar = '#' * int(pct / 5) + '.' * (20 - int(pct / 5))
    print(f"  {name:35s} {body:5d}/{total:5d} ({pct:4.0f}%) [{bar}]")

# Summary
print(f"\n{'='*60}")
total_all = conn.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
body_all = conn.execute("SELECT COUNT(*) FROM documents WHERE body_text_cn IS NOT NULL AND body_text_cn != ''").fetchone()[0]
print(f"  TOTAL: {body_all}/{total_all} ({100*body_all/total_all:.1f}%)")

# What's NOT crawled yet
print(f"\n  NOT YET CRAWLED:")
print(f"    - Guangdong Province (gd.gov.cn) — configured, never crawled")
print(f"    - Guangzhou, Zhuhai, Huizhou, Jiangmen — configured, never crawled")
