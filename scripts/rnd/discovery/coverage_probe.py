"""Probe every mainland province-level portal: reachability + CMS. Emits a TSV
registry line per jurisdiction for the coverage tracker. Re-runnable."""
import sys, re, urllib.request, socket
sys.path.insert(0, "/root/china-governance")
from crawlers.gkmlpt import discover_site

UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
      "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"}

# name, portal host, do-we-crawl-it (site_key or '')
PROVINCES = [
    ("北京","beijing.gov.cn","bj"),("天津","tj.gov.cn",""),("河北","hebei.gov.cn",""),
    ("山西","shanxi.gov.cn",""),("内蒙古","nmg.gov.cn",""),("辽宁","ln.gov.cn",""),
    ("吉林","jl.gov.cn",""),("黑龙江","hlj.gov.cn","hlj"),("上海","shanghai.gov.cn","sh"),
    ("江苏","jiangsu.gov.cn","js"),("浙江","zj.gov.cn","zj"),("安徽","ah.gov.cn",""),
    ("福建","fujian.gov.cn",""),("江西","jiangxi.gov.cn",""),("山东","shandong.gov.cn",""),
    ("河南","henan.gov.cn",""),("湖北","hubei.gov.cn",""),("湖南","hunan.gov.cn",""),
    ("广东","gd.gov.cn","gd"),("广西","gxzf.gov.cn",""),("海南","hainan.gov.cn",""),
    ("重庆","cq.gov.cn","cq"),("四川","sc.gov.cn",""),("贵州","guizhou.gov.cn",""),
    ("云南","yn.gov.cn",""),("西藏","xizang.gov.cn",""),("陕西","shaanxi.gov.cn",""),
    ("甘肃","gansu.gov.cn",""),("青海","qh.gov.cn",""),("宁夏","nx.gov.cn",""),
    ("新疆","xinjiang.gov.cn",""),
]

def probe(host):
    status, cms = "000", ""
    for scheme in ("https://www.","http://www.","https://","http://"):
        url = scheme + host
        req = urllib.request.Request(url, headers=UA)
        try:
            r = urllib.request.urlopen(req, timeout=12)
            html = r.read().decode("utf-8","replace")
            status = str(r.status)
            if "gkmlpt" in html: cms="gkmlpt"
            elif "dataproxy.jsp" in html or ("/art/" in html and "jpaas" in html): cms="jpaas"
            elif re.search(r"/col/col\d+", html): cms="col/?"
            else: cms="?"
            try:
                sid,_ = discover_site(url, headers=UA); cms=f"gkmlpt(SID={sid})"
            except Exception: pass
            return status, cms
        except urllib.error.HTTPError as e:
            status = str(e.code)  # 403/412 = anti-bot, keep trying other schemes
        except Exception:
            pass
    return status, cms

print("name\thost\thave\thttp\tcms\tverdict")
for name, host, have in PROVINCES:
    if have:
        print(f"{name}\t{host}\t{have}\t-\t-\tCRAWLED"); continue
    st, cms = probe(host)
    verdict = ("crawlable" if cms and cms!="?" and st=="200" else
               "reachable-unknown-cms" if st=="200" else
               "anti-bot("+st+")" if st in ("403","412","406") else
               "BLOCKED")
    print(f"{name}\t{host}\t\t{st}\t{cms}\t{verdict}")
