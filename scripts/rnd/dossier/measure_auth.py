"""Per-authority corpus facts for the dossier annotations.

Normalises the title the way the resolver does NOT (folding the zero-width
space), so all copies of one statute are counted together regardless of which
one the resolver picked as representative.
"""
import json, sqlite3

TITLES = {
    "cybersec":  "中华人民共和国网络安全法",
    "pipl":      "中华人民共和国个人信息保护法",
    "dsl":       "中华人民共和国数据安全法",
    "antifraud": "中华人民共和国反电信网络诈骗法",
    "telecom":   "中华人民共和国电信条例",
    "rwjg":      "电信设备进网管理办法",
}

conn = sqlite3.connect("file:documents.db?mode=ro", uri=True)
out = {}
hdr = "%-10s %6s %6s %8s %8s  %s" % (
    "key", "copies", "w/body", "best_ch", "inbound", "resolver representative")
print(hdr)
print("-" * len(hdr))
for key, title in TITLES.items():
    rows = conn.execute(
        'SELECT id, site_key, LENGTH(body_text_cn) FROM documents '
        'WHERE REPLACE(REPLACE(title, char(8203), ""), " ", "") = ?', (title,)
    ).fetchall()
    ids = [r[0] for r in rows]
    n, wb = len(rows), sum(1 for r in rows if r[2])
    best = max([r[2] for r in rows] or [0])
    inb = 0
    rep = None
    if ids:
        ph = ",".join("?" * len(ids))
        inb = conn.execute(
            f"SELECT COUNT(DISTINCT source_id) FROM citations WHERE target_id IN ({ph})",
            ids).fetchone()[0]
        rep = conn.execute(
            f"SELECT target_id, COUNT(*) FROM citations WHERE target_id IN ({ph}) "
            "GROUP BY target_id ORDER BY 2 DESC LIMIT 1", ids).fetchone()
    repinfo, repid, repchars, repsite, repedges = "", None, None, None, None
    if rep:
        repid, repedges = rep
        repsite, repchars = conn.execute(
            "SELECT site_key, LENGTH(body_text_cn) FROM documents WHERE id=?",
            (repid,)).fetchone()
        repinfo = f"{repid} {repsite} {repchars}ch across {repedges} edges"
    print("%-10s %6d %6d %8d %8d  %s" % (key, n, wb, best, inb, repinfo))
    out[key] = {"copies": n, "with_body": wb, "best_chars": best,
                "inbound": inb, "rep_id": repid, "rep_site": repsite,
                "rep_chars": repchars, "rep_edges": repedges,
                "all": [{"id": r[0], "site": r[1], "chars": r[2]} for r in rows]}

json.dump(out, open("/tmp/dossier_facts.json", "w"), ensure_ascii=False, indent=1)
print("\nWROTE /tmp/dossier_facts.json")
