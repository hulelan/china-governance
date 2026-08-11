#!/usr/bin/env python3
"""Build the master coverage ledger: every institution + its status.
Seeds from the DB dump of held sites, then appends the not-yet-held verdicts.
Re-runnable; the not-held list is maintained here as the campaign progresses."""
import csv
from pathlib import Path

REPO = Path("/Users/lelan/Desktop/claude_code/china-governance")
HAVE = Path("/tmp/have.csv")
OUT = REPO / "docs/working/coverage-ledger.csv"

COLS = ["level", "institution", "site_key", "docs", "status", "method", "limitation"]

rows = []
# --- HELD (from the live DB) ---
with open(HAVE, encoding="utf-8") as f:
    for r in csv.reader(f):
        if len(r) < 4:
            continue
        level, site_key, name, docs = r[0], r[1], r[2], r[3]
        rows.append({"level": level, "institution": name, "site_key": site_key,
                     "docs": docs, "status": "have", "method": "crawler",
                     "limitation": ""})

# --- NOT YET HELD (rounds 1–2 investigation verdicts) ---
# status: blocked (WAF/IP-fence — needs residential/headless), spa (client-rendered),
# api (crackable via a bespoke JSON API), pending (under investigation this round).
not_held = [
    # (level, institution, site_key, status, method, limitation)
    ("central", "国务院发展研究中心 DRC", "drc", "spa", "-", "easyui AJAX datagrid; no server-rendered list"),
    ("central", "国家药监局 NMPA", "nmpa", "blocked", "-", "Aliyun $_ts JS anti-bot WAF"),
    ("central", "国家卫健委 NHC", "nhc", "blocked", "-", "412 JS-cookie WAF (rotating token)"),
    ("central", "公安部 MPS", "mps", "blocked", "-", "Jiasule __jsl_clearance JS challenge"),
    ("central", "民政部 MCA", "mca", "blocked", "-", "DNS SERVFAIL from droplet; domain unresolved"),
    ("central", "人社部 MOHRSS", "mohrss", "blocked", "-", "Tencent EdgeOne JS cookie challenge"),
    ("central", "住建部 MOHURD", "mohurd", "blocked", "-", "intermittent WAF + JS-rendered doc list"),
    ("central", "海关总署 GAC", "gac", "blocked", "-", "policy-section 412 WAF (homepage reachable)"),
    ("central", "中国信通院 CAICT", "caict", "blocked", "-", "every path 404-fenced to datacenter IP (HIGH VALUE)"),
    ("media",   "机器之心 Jiqizhixin", "jiqizhixin", "blocked", "-", "data-service interstitial to datacenter IPs"),
    ("media",   "虎嗅 Huxiu", "huxiu", "api", "api-crawl", "SSR /article/{aid}.html + JSON articleList API; buildable now"),
    ("research", "北京智源 BAAI", "baai", "spa", "-", "client-rendered shell"),
    ("research", "上海人工智能实验室 Shanghai AI Lab", "shlab", "spa", "-", "client-rendered shell"),
    ("central", "国家金融监督管理总局 NFRA", "nfra", "spa", "-", "SPA shell (215B)"),
    # Round 2 not-held:
    ("central", "中国政府采购网 CCGP", "ccgp", "deferred", "govcms-A", "crawlable but high-volume low-value tender notices — deferred by choice"),
    ("central", "国家疾控局 NDCPA/CDC", "ndcpa", "spa", "-", "jQuery zwgk.js JSON-rendered list"),
    ("central", "国家烟草专卖局 STMA", "stma", "blocked", "-", "WAF blackholes datacenter IP (site is dialect L, residential would work)"),
    ("central", "国家铁路局 NRA", "nra", "blocked", "-", "IPv6 CDN misroutes datacenter IP; alt portal Yundun WAF"),
    # Round 3 not-held:
    ("central", "国家标准委 SAC", "sac", "spa", "-", "JS-SPA list + JS-rendered article bodies"),
    ("central", "国家信访局 GJXFJ", "gjxfj", "spa", "-", "wPaginate.js JS-templated list (item.publishUrl)"),
    ("central", "中央党校/行政学院 CCPS", "ccps", "blocked", "-", "Tencent Cloud WAF 403 to datacenter IP"),
    ("provincial", "河南省 Henan", "henan", "blocked", "-", "Wangsu/PS-ATL CDN WAF 403 to datacenter IP"),
    ("provincial", "安徽省 Anhui", "anhui", "blocked", "-", "WZWS WAF 403 reason:GeoBL (Hefei AI/quantum hub — HIGH VALUE)"),
    ("provincial", "河北省 Hebei", "hebei", "blocked", "-", "network blackhole (SYN dropped) to datacenter IP"),
    ("provincial", "山西省 Shanxi", "shanxi", "blocked", "-", "network blackhole (SYN dropped)"),
    ("provincial", "江西省 Jiangxi", "jiangxi", "blocked", "-", "network blackhole (SYN dropped)"),
    ("provincial", "广西 Guangxi", "guangxi", "blocked", "-", "network blackhole (SYN dropped)"),
    ("provincial", "陕西省 Shaanxi", "shaanxi", "blocked", "-", "IPv6-only, no IPv4 route from droplet (Xi'an semiconductor hub)"),
    ("provincial", "贵州省 Guizhou", "guizhou", "blocked", "-", "IPv6-only, no IPv4 route (big-data hub)"),
    ("provincial", "云南省 Yunnan", "yunnan", "blocked", "-", "list metadata reachable (dialect A) but article bodies WAF-403 — residential needed"),
]
# NOTE: safe + nfsra are crawled (in DB as 'have') but their article-body container is
# not yet recognized (near-empty bodies) — body-extraction TODO, tracked in structure-gaps.md.
for level, inst, sk, status, method, lim in not_held:
    rows.append({"level": level, "institution": inst, "site_key": sk, "docs": "0",
                 "status": status, "method": method, "limitation": lim})

OUT.parent.mkdir(parents=True, exist_ok=True)
with open(OUT, "w", encoding="utf-8", newline="") as f:
    f.write("# Master coverage ledger — every Chinese-gov institution we know of + its status.\n")
    f.write("# status: have | api | spa | blocked | pending. Grown each crawler round.\n")
    w = csv.DictWriter(f, fieldnames=COLS)
    w.writeheader()
    for row in rows:
        w.writerow(row)

held = sum(1 for r in rows if r["status"] == "have")
print(f"ledger: {len(rows)} institutions ({held} have, {len(rows)-held} not-yet-held) -> {OUT}")
for s in ("have", "api", "spa", "blocked"):
    print(f"  {s}: {sum(1 for r in rows if r['status']==s)}")
