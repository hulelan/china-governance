#!/usr/bin/env python3
"""
Discover Chinese government websites publishing AI/technology policy content
that we don't already crawl.

Checks known provincial and municipal gov.cn domains for:
  1. Reachability (homepage HTTP status)
  2. AI/tech policy content (searches common disclosure paths for key terms)
  3. Estimated document counts (via listing page parsing)

Usage:
    python3 scripts/discover_sources.py              # Full scan with deep probing
    python3 scripts/discover_sources.py --quick       # Reachability check only
    python3 scripts/discover_sources.py --json        # Output results as JSON
    python3 scripts/discover_sources.py --timeout 15  # Custom timeout (seconds)
"""

import argparse
import json
import re
import socket
import ssl
import sys
import time
import urllib.request
import urllib.error
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from urllib.parse import urljoin, urlparse

# ---------------------------------------------------------------------------
# Already-crawled domains — extracted from crawlers/*.py
# Any domain whose suffix matches one of these is considered "already covered."
# ---------------------------------------------------------------------------
ALREADY_CRAWLED_DOMAINS = {
    # Central ministries
    "www.gov.cn",
    "www.ndrc.gov.cn",
    "www.mof.gov.cn",
    "www.mee.gov.cn",
    "www.miit.gov.cn",
    "www.cac.gov.cn",
    "www.most.gov.cn",
    "www.mofcom.gov.cn",
    "exportcontrol.mofcom.gov.cn",
    "www.samr.gov.cn",
    "www.nda.gov.cn",
    # Shenzhen municipal + departments + districts (gkmlpt)
    "www.sz.gov.cn",
    "zjj.sz.gov.cn",
    "stic.sz.gov.cn",
    "fgw.sz.gov.cn",
    "hrss.sz.gov.cn",
    "mzj.sz.gov.cn",
    "sf.sz.gov.cn",
    "jtys.sz.gov.cn",
    "swj.sz.gov.cn",
    "wjw.sz.gov.cn",
    "szeb.sz.gov.cn",
    "yjgl.sz.gov.cn",
    "audit.sz.gov.cn",
    "ga.sz.gov.cn",
    # Shenzhen districts
    "www.szpsq.gov.cn",
    "www.szgm.gov.cn",
    "www.szns.gov.cn",
    "www.szft.gov.cn",
    "www.szlh.gov.cn",
    "www.szlhq.gov.cn",
    "www.yantian.gov.cn",
    "www.lg.gov.cn",
    "www.dpxq.gov.cn",
    "www.baoan.gov.cn",
    # Guangdong province + cities (gkmlpt)
    "www.gd.gov.cn",
    "www.gz.gov.cn",
    "www.zhuhai.gov.cn",
    "www.huizhou.gov.cn",
    "www.jiangmen.gov.cn",
    "www.zs.gov.cn",
    "www.shantou.gov.cn",
    "www.zhaoqing.gov.cn",
    "www.sg.gov.cn",
    "www.heyuan.gov.cn",
    "www.shanwei.gov.cn",
    "www.yangjiang.gov.cn",
    "www.zhanjiang.gov.cn",
    "www.chaozhou.gov.cn",
    "www.jieyang.gov.cn",
    "www.yunfu.gov.cn",
    "www.dg.gov.cn",
    "www.foshan.gov.cn",
    # Provincial crawlers
    "www.beijing.gov.cn",
    "www.shanghai.gov.cn",
    "www.jiangsu.gov.cn",
    "www.zj.gov.cn",
    "www.cq.gov.cn",
    "www.wuhan.gov.cn",
    # Non-gov
    "36kr.com",
    "news.ifeng.com",
    "www.163.com",
    "www.news.cn",
    "aiig.tsinghua.edu.cn",
}

# ---------------------------------------------------------------------------
# Search terms for AI/technology policy
# ---------------------------------------------------------------------------
AI_SEARCH_TERMS = [
    "人工智能",      # artificial intelligence
    "算力",          # computing power
    "大模型",        # large language models
    "数据要素",      # data elements
    "智能制造",      # smart manufacturing
    "数字经济",      # digital economy
]

# ---------------------------------------------------------------------------
# Candidate sites to check — provinces we don't yet crawl
# ---------------------------------------------------------------------------
CANDIDATE_PROVINCES = {
    "Sichuan":       {"domain": "www.sc.gov.cn",      "name": "四川省"},
    "Tianjin":       {"domain": "www.tj.gov.cn",       "name": "天津市"},
    "Hubei":         {"domain": "www.hubei.gov.cn",    "name": "湖北省"},
    "Liaoning":      {"domain": "www.ln.gov.cn",       "name": "辽宁省"},
    "Shandong":      {"domain": "www.shandong.gov.cn", "name": "山东省"},
    "Henan":         {"domain": "www.henan.gov.cn",    "name": "河南省"},
    "Hebei":         {"domain": "www.hb.gov.cn",       "name": "河北省"},
    "Ningxia":       {"domain": "www.nx.gov.cn",       "name": "宁夏"},
    "Xinjiang":      {"domain": "www.xj.gov.cn",       "name": "新疆"},
    "Guangxi":       {"domain": "www.gx.gov.cn",       "name": "广西"},
    "Yunnan":        {"domain": "www.yn.gov.cn",       "name": "云南省"},
    # NOTE: Guizhou uses www.guizhou.gov.cn; www.gz.gov.cn is Guangzhou (already crawled)
    "Guizhou":       {"domain": "www.guizhou.gov.cn",  "name": "贵州省"},
    "Jilin":         {"domain": "www.jl.gov.cn",       "name": "吉林省"},
    "Heilongjiang":  {"domain": "www.hlj.gov.cn",      "name": "黑龙江省"},
    "Inner Mongolia": {"domain": "www.nmg.gov.cn",     "name": "内蒙古"},
    "Tibet":         {"domain": "www.xizang.gov.cn",   "name": "西藏"},
    "Qinghai":       {"domain": "www.qh.gov.cn",       "name": "青海省"},
    "Gansu":         {"domain": "www.gs.gov.cn",       "name": "甘肃省"},
    "Hainan":        {"domain": "www.hainan.gov.cn",   "name": "海南省"},
    "Fujian":        {"domain": "www.fj.gov.cn",       "name": "福建省"},
    "Jiangxi":       {"domain": "www.jx.gov.cn",       "name": "江西省"},
    "Shanxi":        {"domain": "www.sx.gov.cn",       "name": "山西省"},
    "Shaanxi":       {"domain": "www.sn.gov.cn",       "name": "陕西省"},
    "Hunan":         {"domain": "www.hunan.gov.cn",    "name": "湖南省"},
    "Anhui":         {"domain": "www.ah.gov.cn",       "name": "安徽省"},
}

CANDIDATE_CITIES = {
    "Chengdu":   {"domain": "www.chengdu.gov.cn",  "name": "成都市"},
    "Hangzhou":  {"domain": "www.hangzhou.gov.cn",  "name": "杭州市"},
    "Nanjing":   {"domain": "www.nanjing.gov.cn",   "name": "南京市"},
    "Xi'an":     {"domain": "www.xa.gov.cn",        "name": "西安市"},
    "Changsha":  {"domain": "www.changsha.gov.cn",  "name": "长沙市"},
    "Jinan":     {"domain": "www.jinan.gov.cn",     "name": "济南市"},
    "Hefei":     {"domain": "www.hefei.gov.cn",     "name": "合肥市"},
    "Fuzhou":    {"domain": "www.fuzhou.gov.cn",    "name": "福州市"},
    "Kunming":   {"domain": "www.km.gov.cn",        "name": "昆明市"},
    "Wuxi":      {"domain": "www.wuxi.gov.cn",      "name": "无锡市"},
    "Suzhou":    {"domain": "www.suzhou.gov.cn",     "name": "苏州市"},
    "Dalian":    {"domain": "www.dl.gov.cn",         "name": "大连市"},
    "Qingdao":   {"domain": "www.qingdao.gov.cn",   "name": "青岛市"},
    "Xiamen":    {"domain": "www.xm.gov.cn",        "name": "厦门市"},
    "Ningbo":    {"domain": "www.ningbo.gov.cn",     "name": "宁波市"},
    "Zhengzhou": {"domain": "www.zhengzhou.gov.cn",  "name": "郑州市"},
}

# Also check key ministry-level bodies we might be missing
CANDIDATE_MINISTRIES = {
    "SASAC":         {"domain": "www.sasac.gov.cn",    "name": "国资委"},
    "MOE":           {"domain": "www.moe.gov.cn",      "name": "教育部"},
    "PBOC":          {"domain": "www.pbc.gov.cn",      "name": "央行"},
    "CSRC":          {"domain": "www.csrc.gov.cn",     "name": "证监会"},
    "MPS":           {"domain": "www.mps.gov.cn",      "name": "公安部"},
    "NBS":           {"domain": "www.stats.gov.cn",    "name": "统计局"},
    "CNIPA":         {"domain": "www.cnipa.gov.cn",    "name": "知识产权局"},
    "CAS":           {"domain": "www.cas.cn",          "name": "中科院"},
    "CBIRC":         {"domain": "www.cbirc.gov.cn",    "name": "金融监管总局"},
    "MOHURD":        {"domain": "www.mohurd.gov.cn",   "name": "住建部"},
    "MNR":           {"domain": "www.mnr.gov.cn",      "name": "自然资源部"},
}

# Common paths to try for policy/disclosure pages
POLICY_PATHS = [
    "/zwgk/",          # government affairs disclosure
    "/zcfb/",          # policy releases
    "/xxgk/",          # information disclosure
    "/zwgk/zcfb/",     # policy releases under disclosure
    "/zwgk/zfxxgkml/", # government info disclosure catalog
    "/gkmlpt/index",   # gkmlpt platform (Guangdong)
    "/",               # homepage
]

# Paths likely to contain AI/tech policy content
AI_CONTENT_PATHS = [
    "/zwgk/zcfb/",
    "/xxgk/",
    "/zwgk/",
    "/jmzc/",          # beneficial policies
    "/tzgg/",          # notices
    "/zcjd/",          # policy interpretation
]

# ---------------------------------------------------------------------------
# HTTP helpers
# ---------------------------------------------------------------------------
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
}

# Create an SSL context that doesn't verify certs (many .gov.cn sites have issues)
_SSL_CTX = ssl.create_default_context()
_SSL_CTX.check_hostname = False
_SSL_CTX.verify_mode = ssl.CERT_NONE


def fetch_url(url: str, timeout: int = 10) -> dict:
    """Fetch a URL and return status info. Never raises."""
    result = {
        "url": url,
        "status": None,
        "error": None,
        "final_url": None,
        "body_size": 0,
        "body_snippet": "",
        "content_type": "",
    }
    try:
        req = urllib.request.Request(url, headers=HEADERS)
        handler = urllib.request.HTTPSHandler(context=_SSL_CTX)
        opener = urllib.request.build_opener(handler)
        resp = opener.open(req, timeout=timeout)
        body = resp.read(200_000)  # Read max 200KB
        text = body.decode("utf-8", errors="replace")
        result["status"] = resp.status
        result["final_url"] = resp.url
        result["body_size"] = len(text)
        result["body_snippet"] = text[:500].replace("\n", " ").strip()
        result["content_type"] = resp.headers.get("Content-Type", "")
        result["_body"] = text  # Keep full body for analysis
    except urllib.error.HTTPError as e:
        result["status"] = e.code
        result["error"] = f"HTTP {e.code}"
    except urllib.error.URLError as e:
        reason = str(e.reason) if hasattr(e, "reason") else str(e)
        if "Name or service not known" in reason or "getaddrinfo" in reason or "nodename" in reason:
            result["error"] = "DNS_FAILED"
        elif "Connection refused" in reason:
            result["error"] = "CONN_REFUSED"
        elif "Connection reset" in reason or "reset by peer" in reason:
            result["error"] = "CONN_RESET"
        elif "timed out" in reason or "timeout" in reason.lower():
            result["error"] = "TIMEOUT"
        elif "SSL" in reason or "ssl" in reason or "certificate" in reason.lower():
            result["error"] = f"SSL_ERROR"
        else:
            result["error"] = f"URL_ERROR: {reason[:100]}"
    except socket.timeout:
        result["error"] = "TIMEOUT"
    except OSError as e:
        result["error"] = f"OS_ERROR: {str(e)[:100]}"
    except Exception as e:
        result["error"] = f"ERROR: {str(e)[:100]}"
    return result


# ---------------------------------------------------------------------------
# Analysis helpers
# ---------------------------------------------------------------------------
SOFT_404_PATTERNS = [
    "找不到", "页面不存在", "not found", "Not Found", "404",
    "无法找到", "访问的页面不存在", "page not found", "错误页面",
]


def is_soft_404(body: str) -> bool:
    """Detect soft-404 pages that return HTTP 200 but are error pages."""
    if not body:
        return False
    lower = body[:3000].lower()
    body_len = len(body.strip())
    if body_len < 2000:
        for pattern in SOFT_404_PATTERNS:
            if pattern.lower() in lower:
                return True
    return False


def count_ai_term_hits(body: str) -> dict:
    """Count occurrences of AI/tech terms in page body."""
    hits = {}
    for term in AI_SEARCH_TERMS:
        count = body.count(term)
        if count > 0:
            hits[term] = count
    return hits


def estimate_doc_links(body: str) -> int:
    """Estimate number of document links on a page (heuristic)."""
    # Count links that look like document pages
    patterns = [
        r'href="[^"]*\.html?"',
        r'href="[^"]*\.shtml"',
        r'href="[^"]*content_\d+',
        r'href="[^"]*article/',
        r'href="[^"]*zwgk/[^"]*"',
        r'<a[^>]+title="[^"]+"',
    ]
    total = 0
    for pat in patterns:
        total += len(re.findall(pat, body))
    return total


def detect_gkmlpt(body: str) -> bool:
    """Check if page is a gkmlpt platform."""
    return bool(re.search(r'SID:\s*["\']', body)) or "gkmlpt" in body.lower()


def detect_cms_type(body: str) -> str:
    """Try to identify the CMS/platform type."""
    lower = body.lower()
    if detect_gkmlpt(body):
        return "gkmlpt"
    if "jpage" in lower or "dataproxy.jsp" in lower:
        return "jpage"
    if "trs" in lower or "TRS" in body:
        return "TRS"
    if "ucap" in lower:
        return "UCAP"
    if "wp-content" in lower:
        return "WordPress"
    if "e-government" in lower or "egov" in lower:
        return "eGov"
    return "unknown"


# ---------------------------------------------------------------------------
# Core probe logic
# ---------------------------------------------------------------------------
def probe_site(name: str, info: dict, level: str, timeout: int = 10,
               deep: bool = True) -> dict:
    """Probe a single candidate site. Returns a result dict."""
    domain = info["domain"]
    cn_name = info["name"]
    # Try both HTTPS and HTTP
    base_urls = [f"https://{domain}", f"http://{domain}"]

    result = {
        "name": name,
        "cn_name": cn_name,
        "domain": domain,
        "level": level,
        "reachable": False,
        "base_url": None,
        "status": None,
        "error": None,
        "already_crawled": domain in ALREADY_CRAWLED_DOMAINS,
        "has_gkmlpt": False,
        "cms_type": "unknown",
        "ai_term_hits": {},
        "ai_term_total": 0,
        "ai_pages_found": [],
        "estimated_doc_links": 0,
        "policy_paths_found": [],
        "notes": [],
    }

    if result["already_crawled"]:
        result["notes"].append("ALREADY CRAWLED")
        return result

    # Step 1: Test reachability
    homepage = None
    for base in base_urls:
        resp = fetch_url(base, timeout=timeout)
        if resp["status"] and resp["status"] < 400 and not is_soft_404(resp.get("_body", "")):
            homepage = resp
            result["reachable"] = True
            result["base_url"] = base
            result["status"] = resp["status"]
            body = resp.get("_body", "")
            result["cms_type"] = detect_cms_type(body)
            if detect_gkmlpt(body):
                result["has_gkmlpt"] = True

            # Check for AI terms on homepage
            hits = count_ai_term_hits(body)
            if hits:
                result["ai_term_hits"] = hits
                result["ai_term_total"] = sum(hits.values())

            break
        elif resp["error"]:
            result["error"] = resp["error"]
        elif resp["status"]:
            result["status"] = resp["status"]
            result["error"] = f"HTTP {resp['status']}"

    if not result["reachable"]:
        return result

    if not deep:
        return result

    # Step 2: Check common policy paths
    base = result["base_url"]
    for path in POLICY_PATHS:
        if path == "/":
            continue  # Already checked homepage
        url = base.rstrip("/") + path
        resp = fetch_url(url, timeout=timeout)
        body = resp.get("_body", "")
        if resp["status"] and resp["status"] < 400 and not is_soft_404(body):
            path_info = {
                "path": path,
                "status": resp["status"],
                "doc_links": estimate_doc_links(body),
            }
            if detect_gkmlpt(body):
                result["has_gkmlpt"] = True
                path_info["gkmlpt"] = True
            result["policy_paths_found"].append(path_info)
        time.sleep(0.3)  # Be polite

    # Step 3: Search for AI content on policy pages
    for path in AI_CONTENT_PATHS:
        url = base.rstrip("/") + path
        resp = fetch_url(url, timeout=timeout)
        body = resp.get("_body", "")
        if resp["status"] and resp["status"] < 400 and body:
            hits = count_ai_term_hits(body)
            if hits:
                page_info = {
                    "url": url,
                    "path": path,
                    "term_hits": hits,
                    "total_hits": sum(hits.values()),
                    "doc_links": estimate_doc_links(body),
                }
                result["ai_pages_found"].append(page_info)
                # Merge term hits
                for term, count in hits.items():
                    result["ai_term_hits"][term] = (
                        result["ai_term_hits"].get(term, 0) + count
                    )
                result["ai_term_total"] = sum(result["ai_term_hits"].values())
        time.sleep(0.3)

    # Step 4: Try a site-specific search for 人工智能 if site has a search endpoint
    # Common search URL patterns on gov.cn sites
    search_paths = [
        f"/search/search_rsa.shtml?searchWord=人工智能",
        f"/col/col1229240698/index.html",  # common jpage search
    ]
    for spath in search_paths:
        url = base.rstrip("/") + spath
        resp = fetch_url(url, timeout=timeout)
        body = resp.get("_body", "")
        if resp["status"] and resp["status"] < 400 and body and len(body) > 1000:
            hits = count_ai_term_hits(body)
            if hits:
                links = estimate_doc_links(body)
                result["notes"].append(
                    f"Search endpoint found at {spath} ({links} links, "
                    f"{sum(hits.values())} AI term hits)"
                )
        time.sleep(0.3)

    # Estimate total doc links from policy pages
    result["estimated_doc_links"] = max(
        [p.get("doc_links", 0) for p in result["policy_paths_found"]] or [0]
    )

    return result


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------
def print_report(results: list, quick: bool = False):
    """Print a human-readable report of discovery results."""
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"\n{'=' * 80}")
    print(f"  AI/Tech Policy Source Discovery Report")
    print(f"  Generated: {now}")
    print(f"  Sites checked: {len(results)}")
    print(f"  Mode: {'quick (reachability only)' if quick else 'full (deep scan)'}")
    print(f"{'=' * 80}")

    # Partition results
    already = [r for r in results if r["already_crawled"]]
    reachable = [r for r in results if r["reachable"] and not r["already_crawled"]]
    unreachable = [r for r in results if not r["reachable"] and not r["already_crawled"]]

    # Sort reachable by AI relevance
    reachable.sort(key=lambda r: r["ai_term_total"], reverse=True)

    # --- HIGH VALUE: Reachable + AI content found ---
    ai_sites = [r for r in reachable if r["ai_term_total"] > 0]
    non_ai_sites = [r for r in reachable if r["ai_term_total"] == 0]

    print(f"\n--- REACHABLE + AI CONTENT FOUND [{len(ai_sites)}] ---")
    print(f"    (Ranked by AI term frequency)\n")
    if ai_sites:
        for i, r in enumerate(ai_sites, 1):
            level_tag = f"[{r['level']:8s}]"
            terms = ", ".join(f"{t}({c})" for t, c in
                              sorted(r["ai_term_hits"].items(),
                                     key=lambda x: x[1], reverse=True)[:4])
            print(f"  {i:2d}. {level_tag} {r['name']:20s} ({r['cn_name']})")
            print(f"      Domain:     {r['domain']}")
            print(f"      Status:     HTTP {r['status']}")
            print(f"      AI terms:   {r['ai_term_total']} hits -- {terms}")
            if r["has_gkmlpt"]:
                print(f"      Platform:   gkmlpt (reusable crawler!)")
            elif r["cms_type"] != "unknown":
                print(f"      Platform:   {r['cms_type']}")
            if r["policy_paths_found"]:
                paths_str = ", ".join(
                    f"{p['path']}({p['doc_links']} links)"
                    for p in r["policy_paths_found"][:4]
                )
                print(f"      Paths:      {paths_str}")
            if r["ai_pages_found"]:
                for p in r["ai_pages_found"][:2]:
                    print(f"      AI page:    {p['url']}")
                    print(f"                  {p['total_hits']} hits, "
                          f"~{p['doc_links']} doc links")
            if r["estimated_doc_links"] > 0:
                print(f"      Est. links: ~{r['estimated_doc_links']} on best page")
            for note in r["notes"]:
                print(f"      Note:       {note}")
            print()
    else:
        print("    (none)\n")

    # --- REACHABLE, NO AI CONTENT ---
    print(f"--- REACHABLE, NO AI CONTENT DETECTED [{len(non_ai_sites)}] ---")
    if non_ai_sites:
        for r in non_ai_sites:
            level_tag = f"[{r['level']:8s}]"
            paths = ", ".join(p["path"] for p in r["policy_paths_found"][:3])
            cms = f" ({r['cms_type']})" if r["cms_type"] != "unknown" else ""
            gkmlpt = " ** GKMLPT **" if r["has_gkmlpt"] else ""
            print(f"  {level_tag} {r['name']:20s} {r['domain']:30s} "
                  f"HTTP {r['status']}{cms}{gkmlpt}")
            if paths:
                print(f"           Policy paths: {paths}")
    else:
        print("    (none)")
    print()

    # --- UNREACHABLE ---
    print(f"--- UNREACHABLE [{len(unreachable)}] ---")
    if unreachable:
        for r in unreachable:
            level_tag = f"[{r['level']:8s}]"
            err = r["error"] or f"HTTP {r['status']}"
            print(f"  {level_tag} {r['name']:20s} {r['domain']:30s} {err}")
    else:
        print("    (none)")
    print()

    # --- ALREADY CRAWLED ---
    if already:
        print(f"--- ALREADY CRAWLED (skipped) [{len(already)}] ---")
        for r in already:
            print(f"  {r['domain']}")
        print()

    # --- SUMMARY TABLE ---
    print(f"{'=' * 80}")
    print(f"  PRIORITY RANKING: Top candidates for new crawlers")
    print(f"{'=' * 80}\n")

    if ai_sites:
        print(f"  {'#':>3s}  {'Site':25s} {'Level':10s} {'AI Hits':>8s} "
              f"{'Platform':10s} {'Domain':30s}")
        print(f"  {'---':>3s}  {'----':25s} {'-----':10s} {'-------':>8s} "
              f"{'--------':10s} {'------':30s}")
        for i, r in enumerate(ai_sites[:20], 1):
            cms = r["cms_type"]
            if r["has_gkmlpt"]:
                cms = "gkmlpt"
            print(f"  {i:3d}  {r['name']:25s} {r['level']:10s} "
                  f"{r['ai_term_total']:8d} {cms:10s} {r['domain']:30s}")
    else:
        print("  No sites with detected AI content. Try --full mode or check manually.")

    print(f"\n{'=' * 80}")
    reachable_count = len(reachable)
    total_checked = len(results) - len(already)
    print(f"  Total checked: {total_checked}")
    print(f"  Reachable:     {reachable_count} ({reachable_count*100//max(total_checked,1)}%)")
    print(f"  AI content:    {len(ai_sites)}")
    print(f"  Unreachable:   {len(unreachable)}")
    print(f"  Already ours:  {len(already)} (skipped)")
    print(f"{'=' * 80}\n")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(
        description="Discover Chinese gov websites with AI/tech policy content."
    )
    parser.add_argument("--quick", action="store_true",
                        help="Quick mode: reachability check only, no deep scan")
    parser.add_argument("--json", action="store_true",
                        help="Output results as JSON")
    parser.add_argument("--timeout", type=int, default=12,
                        help="HTTP timeout in seconds (default: 12)")
    parser.add_argument("--workers", type=int, default=6,
                        help="Parallel workers (default: 6)")
    parser.add_argument("--provinces-only", action="store_true",
                        help="Only check provincial sites")
    parser.add_argument("--cities-only", action="store_true",
                        help="Only check municipal sites")
    parser.add_argument("--ministries-only", action="store_true",
                        help="Only check ministry sites")
    parser.add_argument("--save", action="store_true",
                        help="Save JSON results to logs/discover_YYYYMMDD.json")
    args = parser.parse_args()

    # Build candidate list
    candidates = []
    if not args.cities_only and not args.ministries_only:
        for name, info in CANDIDATE_PROVINCES.items():
            candidates.append((name, info, "province"))
    if not args.provinces_only and not args.ministries_only:
        for name, info in CANDIDATE_CITIES.items():
            candidates.append((name, info, "municipal"))
    if not args.provinces_only and not args.cities_only:
        for name, info in CANDIDATE_MINISTRIES.items():
            candidates.append((name, info, "central"))

    deep = not args.quick
    mode = "quick" if args.quick else "full"
    total = len(candidates)
    skippable = sum(1 for _, info, _ in candidates
                    if info["domain"] in ALREADY_CRAWLED_DOMAINS)

    # When --json, send progress to stderr so stdout is clean JSON
    progress_out = sys.stderr if args.json else sys.stdout

    print(f"AI/Tech Policy Source Discovery", file=progress_out)
    print(f"Mode: {mode} | Timeout: {args.timeout}s | Workers: {args.workers}",
          file=progress_out)
    print(f"Candidates: {total} ({total - skippable} new, {skippable} already crawled)",
          file=progress_out)
    print(f"Search terms: {', '.join(AI_SEARCH_TERMS)}", file=progress_out)
    if deep:
        print(f"Deep scan: checking {len(POLICY_PATHS)} policy paths + "
              f"{len(AI_CONTENT_PATHS)} content paths per site", file=progress_out)
    print(file=progress_out)

    results = []
    completed = 0

    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = {}
        for name, info, level in candidates:
            future = executor.submit(
                probe_site, name, info, level,
                timeout=args.timeout, deep=deep
            )
            futures[future] = (name, info, level)

        for future in as_completed(futures):
            name, info, level = futures[future]
            completed += 1
            try:
                result = future.result()
                results.append(result)

                # Progress indicator
                status_char = "."
                if result["already_crawled"]:
                    status_char = "s"  # skipped
                elif not result["reachable"]:
                    status_char = "x"
                elif result["ai_term_total"] > 0:
                    status_char = "*"
                elif result["reachable"]:
                    status_char = "+"

                # Print inline progress
                detail = ""
                if result["already_crawled"]:
                    detail = "skipped (already crawled)"
                elif not result["reachable"]:
                    detail = result["error"] or "unreachable"
                elif result["ai_term_total"] > 0:
                    detail = f"AI content! ({result['ai_term_total']} hits)"
                else:
                    detail = f"reachable, no AI terms found"

                progress_out.write(
                    f"\r  [{completed:3d}/{total}] {status_char} "
                    f"{name:20s} {info['domain']:30s} {detail}\n"
                )
                progress_out.flush()

            except Exception as e:
                progress_out.write(
                    f"\r  [{completed:3d}/{total}] ! "
                    f"{name:20s} EXCEPTION: {e}\n"
                )

    # Sort for report: AI hits descending, then reachable, then unreachable
    results.sort(key=lambda r: (
        -r["ai_term_total"],
        -int(r["reachable"]),
        r["name"],
    ))

    # Strip internal _body fields for output
    clean = []
    for r in results:
        cr = {k: v for k, v in r.items() if not k.startswith("_")}
        for page in cr.get("ai_pages_found", []):
            page.pop("_body", None)
        clean.append(cr)

    if args.json:
        print(json.dumps(clean, ensure_ascii=False, indent=2))
    else:
        print_report(results, quick=args.quick)

    if args.save:
        from pathlib import Path
        log_dir = Path(__file__).parent.parent / "logs"
        log_dir.mkdir(exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_path = log_dir / f"discover_{ts}.json"
        with open(log_path, "w", encoding="utf-8") as f:
            json.dump({
                "timestamp": datetime.now().isoformat(),
                "mode": mode,
                "sites_checked": total,
                "results": clean,
            }, f, ensure_ascii=False, indent=2)
        print(f"Results saved to {log_path}")


if __name__ == "__main__":
    main()
