"""Build docs/working/coverage.csv — the coverage registry.

Enumerates the government apparatus (central bodies + all provinces + provincial
capitals + major cities) and merges with sites we already crawl (from documents.db),
probing each for reachability + CMS. Columns:
  level, name, jurisdiction, domain, cms, http, status, site_key, docs
"""
import csv, re, sqlite3, sys, urllib.request, urllib.error
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parents[3]))
from crawlers.gkmlpt import discover_site  # noqa

ROOT = Path(__file__).parents[3]
DB = ROOT / "documents.db"
OUT = ROOT / "docs" / "working" / "coverage.csv"
UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"}

# --- Central government apparatus: name, domain, our-site_key-if-crawled, category ---
CENTRAL = [
    ("国务院 State Council", "gov.cn", "gov", "state-council"),
    ("外交部 MFA", "mfa.gov.cn", "mfa", "ministry"),
    ("国家发改委 NDRC", "ndrc.gov.cn", "ndrc", "ministry"),
    ("教育部 MOE", "moe.gov.cn", "moe", "ministry"),
    ("科技部 MOST", "most.gov.cn", "most", "ministry"),
    ("工信部 MIIT", "miit.gov.cn", "miit", "ministry"),
    ("公安部 MPS", "mps.gov.cn", "", "ministry"),
    ("民政部 MCA", "mca.gov.cn", "", "ministry"),
    ("司法部 MOJ", "moj.gov.cn", "", "ministry"),
    ("财政部 MOF", "mof.gov.cn", "mof", "ministry"),
    ("人社部 MOHRSS", "mohrss.gov.cn", "", "ministry"),
    ("自然资源部 MNR", "mnr.gov.cn", "", "ministry"),
    ("生态环境部 MEE", "mee.gov.cn", "mee", "ministry"),
    ("住建部 MOHURD", "mohurd.gov.cn", "", "ministry"),
    ("交通运输部 MOT", "mot.gov.cn", "", "ministry"),
    ("水利部 MWR", "mwr.gov.cn", "", "ministry"),
    ("农业农村部 MARA", "moa.gov.cn", "", "ministry"),
    ("商务部 MOFCOM", "mofcom.gov.cn", "mofcom", "ministry"),
    ("文旅部 MCT", "mct.gov.cn", "", "ministry"),
    ("卫健委 NHC", "nhc.gov.cn", "", "ministry"),
    ("应急管理部 MEM", "mem.gov.cn", "", "ministry"),
    ("退役军人部 MVA", "mva.gov.cn", "", "ministry"),
    ("央行 PBOC", "pbc.gov.cn", "pbc", "ministry"),
    ("审计署 CNAO", "audit.gov.cn", "", "ministry"),
    # State Council direct agencies / administrations
    ("海关总署 GACC", "customs.gov.cn", "", "agency"),
    ("税务总局 STA", "chinatax.gov.cn", "chinatax", "agency"),
    ("市场监管总局 SAMR", "samr.gov.cn", "samr", "agency"),
    ("金融监管总局 NFRA", "nfra.gov.cn", "", "agency"),
    ("证监会 CSRC", "csrc.gov.cn", "csrc", "agency"),
    ("统计局 NBS", "stats.gov.cn", "", "agency"),
    ("知识产权局 CNIPA", "cnipa.gov.cn", "", "agency"),
    ("医保局 NHSA", "nhsa.gov.cn", "nhsa", "agency"),
    ("国家网信办 CAC", "cac.gov.cn", "cac", "agency"),
    ("国家数据局 NDA", "nda.gov.cn", "nda", "agency"),
    ("国家能源局 NEA", "nea.gov.cn", "", "agency"),
    ("广电总局 NRTA", "nrta.gov.cn", "nrta", "agency"),
    ("药监局 NMPA", "nmpa.gov.cn", "", "agency"),
    ("林草局 NFGA", "forestry.gov.cn", "", "agency"),
    ("移民局 NIA", "nia.gov.cn", "", "agency"),
    ("体育总局 GAS", "sport.gov.cn", "", "agency"),
    # power organs / judiciary / CPC
    ("全国人大 NPC", "npc.gov.cn", "npc", "power-organ"),
    ("全国政协 CPPCC", "cppcc.gov.cn", "", "power-organ"),
    ("最高法 SPC", "court.gov.cn", "ipc_court", "judiciary"),
    ("最高检 SPP", "spp.gov.cn", "spp", "judiciary"),
    ("中央政法委", "chinapeace.gov.cn", "", "cpc"),
    ("共产党员网(中组部) 12371", "12371.cn", "", "cpc"),
]

PROVINCES = [
    ("北京", "beijing.gov.cn", "municipality", "bj"), ("天津", "tj.gov.cn", "municipality", ""),
    ("上海", "shanghai.gov.cn", "municipality", "sh"), ("重庆", "cq.gov.cn", "municipality", "cq"),
    ("河北", "hebei.gov.cn", "province", ""), ("山西", "shanxi.gov.cn", "province", ""),
    ("内蒙古", "nmg.gov.cn", "province", ""), ("辽宁", "ln.gov.cn", "province", ""),
    ("吉林", "jl.gov.cn", "province", ""), ("黑龙江", "hlj.gov.cn", "province", "hlj"),
    ("江苏", "jiangsu.gov.cn", "province", "js"), ("浙江", "zj.gov.cn", "province", "zj"),
    ("安徽", "ah.gov.cn", "province", ""), ("福建", "fujian.gov.cn", "province", ""),
    ("江西", "jiangxi.gov.cn", "province", ""), ("山东", "shandong.gov.cn", "province", ""),
    ("河南", "henan.gov.cn", "province", ""), ("湖北", "hubei.gov.cn", "province", ""),
    ("湖南", "hunan.gov.cn", "province", ""), ("广东", "gd.gov.cn", "province", "gd"),
    ("广西", "gxzf.gov.cn", "province", ""), ("海南", "hainan.gov.cn", "province", ""),
    ("四川", "sc.gov.cn", "province", ""), ("贵州", "guizhou.gov.cn", "province", ""),
    ("云南", "yn.gov.cn", "province", ""), ("西藏", "xizang.gov.cn", "province", ""),
    ("陕西", "shaanxi.gov.cn", "province", ""), ("甘肃", "gansu.gov.cn", "province", ""),
    ("青海", "qh.gov.cn", "province", ""), ("宁夏", "nx.gov.cn", "province", ""),
    ("新疆", "xinjiang.gov.cn", "province", ""),
]
# provincial capitals + major cities (best-effort domains). city already-crawled via other-crawled merge.
CITIES = [
    ("石家庄", "sjz.gov.cn"), ("太原", "taiyuan.gov.cn"), ("呼和浩特", "huhhot.gov.cn"),
    ("沈阳", "shenyang.gov.cn"), ("长春", "changchun.gov.cn"), ("南京", "nanjing.gov.cn"),
    ("杭州", "hangzhou.gov.cn"), ("合肥", "hefei.gov.cn"), ("福州", "fuzhou.gov.cn"),
    ("南昌", "nc.gov.cn"), ("济南", "jinan.gov.cn"), ("郑州", "zhengzhou.gov.cn"),
    ("武汉", "wuhan.gov.cn"), ("长沙", "changsha.gov.cn"), ("南宁", "nanning.gov.cn"),
    ("海口", "haikou.gov.cn"), ("成都", "chengdu.gov.cn"), ("贵阳", "guiyang.gov.cn"),
    ("昆明", "km.gov.cn"), ("拉萨", "lasa.gov.cn"), ("西安", "xa.gov.cn"),
    ("兰州", "lanzhou.gov.cn"), ("西宁", "xining.gov.cn"), ("银川", "yinchuan.gov.cn"),
    ("乌鲁木齐", "urumqi.gov.cn"),
    # major non-capital cities
    ("青岛", "qingdao.gov.cn"), ("大连", "dl.gov.cn"), ("宁波", "ningbo.gov.cn"),
    ("厦门", "xm.gov.cn"), ("无锡", "wuxi.gov.cn"), ("温州", "wenzhou.gov.cn"),
]


def probe(domain):
    """Fast probe: fetch homepage, detect CMS; only call discover_site for gkmlpt."""
    last = "000"
    for scheme in ("https://www.", "https://", "http://www.", "http://"):
        url = scheme + domain
        try:
            r = urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=12)
            html = r.read().decode("utf-8", "replace")
            if "gkmlpt" in html:
                try:
                    sid, _ = discover_site(url, headers=UA)
                    return str(r.status), f"gkmlpt(SID={sid})"
                except Exception:
                    return str(r.status), "gkmlpt?"
            cms = ("jpaas" if ("dataproxy.jsp" in html or ("/art/" in html and "jpaas" in html))
                   else "col/" if re.search(r"/col/col\d+", html) else "?")
            return str(r.status), cms
        except urllib.error.HTTPError as e:
            last = str(e.code)
        except Exception:
            last = "000"
    return last, ""


def status_for(http, cms, have):
    if have:
        return "CRAWLED"
    if http == "200" and cms and cms != "?":
        return "BUILDABLE"
    if http == "200":
        return "REACHABLE-UNKNOWN-CMS"
    if http in ("403", "412", "406"):
        return "ANTI-BOT"
    return "BLOCKED"


def main():
    con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    docs = dict(con.execute("SELECT site_key, COUNT(*) FROM documents GROUP BY site_key").fetchall())
    rows, listed = [], set()

    for name, dom, have, cat in CENTRAL:
        http, cms = ("-", "-") if have else probe(dom)
        rows.append([f"central:{cat}", name, "中央", dom, cms, http, status_for(http, cms, have), have, docs.get(have, "")])
        if have:
            listed.add(have)
    for name, dom, level, have in PROVINCES:
        http, cms = ("-", "-") if have else probe(dom)
        rows.append([level, name, name, dom, cms, http, status_for(http, cms, have), have, docs.get(have, "")])
        if have:
            listed.add(have)
    for name, dom in CITIES:
        http, cms = probe(dom)
        rows.append(["prefecture-city", name, name, dom, cms, http, status_for(http, cms, ""), "", ""])
    # GD provincial departments we added (gkmlpt)
    from crawlers.gkmlpt import SITES as GK
    for key, cfg in GK.items():
        if key.startswith("gd") and key not in ("gd", "gz"):
            rows.append(["provincial-dept", cfg["name"], "广东", re.sub(r"https?://", "", cfg["base_url"]),
                         "gkmlpt", "200", "CRAWLED" if docs.get(key) else "BUILDABLE", key, docs.get(key, "")])
            listed.add(key)
    # any other crawled site_key not already listed
    for key, n in sorted(docs.items(), key=lambda x: -x[1]):
        if key not in listed:
            rows.append(["other-crawled", key, "", "", "", "-", "CRAWLED", key, n])

    with open(OUT, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["level", "name", "jurisdiction", "domain", "cms", "http", "status", "site_key", "docs"])
        w.writerows(rows)
    from collections import Counter
    print(f"wrote {len(rows)} rows")
    print("by status:", dict(Counter(r[6] for r in rows)))
    print("central only:", dict(Counter(r[6] for r in rows if r[0].startswith("central"))))


if __name__ == "__main__":
    main()
