#!/usr/bin/env python3
"""
Probe Chinese provincial government websites for gkmlpt endpoints.

Tests /gkmlpt/index for each province/city, checking for "SID:" and
"_CONFIG" in the response body to confirm the gkmlpt platform (which is
known to be a Guangdong-specific system). Also tries common alternative
paths (/zwgk/index, /xxgk/index) to discover other information disclosure
platforms.
"""

import json
import re
import requests
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed

TIMEOUT = 10

PROVINCES = {
    "Fujian": "http://www.fujian.gov.cn",
    "Hainan": "http://www.hainan.gov.cn",
    "Sichuan": "http://www.sc.gov.cn",
    "Yunnan": "http://www.yn.gov.cn",
    "Guizhou": "http://www.guizhou.gov.cn",
    "Hubei": "http://www.hubei.gov.cn",
    "Hunan": "http://www.hunan.gov.cn",
    "Jiangxi": "http://www.jiangxi.gov.cn",
    "Anhui": "http://www.ah.gov.cn",
    "Henan": "http://www.henan.gov.cn",
    "Hebei": "http://www.hebei.gov.cn",
    "Shanxi": "http://www.shanxi.gov.cn",
    "Liaoning": "http://www.ln.gov.cn",
    "Jilin": "http://www.jl.gov.cn",
    "Heilongjiang": "http://www.hlj.gov.cn",
    "Guangxi": "http://www.gxzf.gov.cn",
    "Inner Mongolia": "http://www.nmg.gov.cn",
    "Tibet": "http://www.xizang.gov.cn",
    "Xinjiang": "http://www.xinjiang.gov.cn",
    "Gansu": "http://www.gansu.gov.cn",
    "Qinghai": "http://www.qinghai.gov.cn",
    "Ningxia": "http://www.nx.gov.cn",
}

CITIES = {
    "Zhejiang": "http://www.zj.gov.cn",
    "Jiangsu": "http://www.jiangsu.gov.cn",
    "Shanghai": "http://www.shanghai.gov.cn",
    "Beijing": "http://www.beijing.gov.cn",
    "Chongqing": "http://www.cq.gov.cn",
    "Tianjin": "http://www.tj.gov.cn",
}

PRIMARY_PATH = "/gkmlpt/index"
ALT_PATHS = ["/zwgk/index", "/xxgk/index"]

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
}

# Soft-404 indicators (page says "not found" despite HTTP 200)
SOFT_404_PATTERNS = [
    "找不到", "页面不存在", "not found", "Not Found", "404",
    "无法找到", "访问的页面", "page not found",
]


def extract_sid(text: str) -> str | None:
    """Extract SID value from _CONFIG block in page source."""
    m = re.search(r'SID:\s*["\']([^"\']+)["\']', text)
    return m.group(1) if m else None


def extract_tree_count(text: str) -> int | None:
    """Try to extract the number of top-level categories from TREE JSON."""
    m = re.search(r"var\s+TREE\s*=\s*(\[.*?\])\s*;", text, re.DOTALL)
    if not m:
        return None
    try:
        tree = json.loads(m.group(1))
        return len(tree)
    except (json.JSONDecodeError, TypeError):
        return None


def is_soft_404(text: str) -> bool:
    """Detect soft-404 pages that return HTTP 200 but show error content."""
    lower = text[:2000].lower()
    body_len = len(text.strip())
    # Very short pages with 404 indicators
    if body_len < 1000:
        for pattern in SOFT_404_PATTERNS:
            if pattern.lower() in lower:
                return True
    return False


def probe_url(url: str) -> dict:
    """Fetch a URL and return a detailed result dict."""
    result = {"url": url, "status": None, "error": None, "final_url": None,
              "has_sid": False, "sid": None, "has_config": False,
              "tree_count": None, "soft_404": False, "snippet": "",
              "body_size": 0}
    try:
        resp = requests.get(
            url, timeout=TIMEOUT, headers=HEADERS, allow_redirects=True,
            verify=False,
        )
        body = resp.text
        result["status"] = resp.status_code
        result["final_url"] = resp.url
        result["body_size"] = len(body)
        result["snippet"] = body[:300].replace("\n", " ").strip()

        # gkmlpt detection
        sid = extract_sid(body)
        if sid:
            result["has_sid"] = True
            result["sid"] = sid
        if "_CONFIG" in body:
            result["has_config"] = True
        tree_count = extract_tree_count(body)
        if tree_count is not None:
            result["tree_count"] = tree_count

        # Soft-404 detection
        if resp.status_code == 200 and is_soft_404(body):
            result["soft_404"] = True

    except requests.exceptions.Timeout:
        result["error"] = "TIMEOUT"
    except requests.exceptions.ConnectionError as e:
        reason = str(e)
        if "Name or service not known" in reason or "getaddrinfo" in reason:
            result["error"] = "DNS_FAILED"
        elif "Connection refused" in reason:
            result["error"] = "CONN_REFUSED"
        elif "Connection reset" in reason:
            result["error"] = "CONN_RESET"
        else:
            result["error"] = f"CONN_ERROR: {reason[:80]}"
    except requests.exceptions.SSLError as e:
        result["error"] = f"SSL_ERROR: {str(e)[:80]}"
    except Exception as e:
        result["error"] = f"ERROR: {str(e)[:80]}"
    return result


def is_real_success(r: dict) -> bool:
    """Check if a probe result represents a real (non-soft-404) success."""
    return (r["status"] is not None
            and r["status"] < 400
            and not r["soft_404"])


def probe_site(name: str, base_url: str) -> dict:
    """Probe a single site: try gkmlpt first, then alternatives."""
    result = {
        "name": name,
        "base_url": base_url,
        "gkmlpt": None,
        "alternatives": [],
    }

    # Try primary gkmlpt path
    url = base_url.rstrip("/") + PRIMARY_PATH
    gk = probe_url(url)
    result["gkmlpt"] = gk

    # Always try alternatives to discover other platforms
    for alt_path in ALT_PATHS:
        alt_url = base_url.rstrip("/") + alt_path
        alt_result = probe_url(alt_url)
        alt_result["path"] = alt_path
        result["alternatives"].append(alt_result)

    return result


def main():
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    all_sites = {}
    all_sites.update(PROVINCES)
    all_sites.update(CITIES)

    print(f"Probing {len(all_sites)} sites for gkmlpt endpoints...")
    print(f"Primary path: {PRIMARY_PATH}")
    print(f"Alternative paths: {', '.join(ALT_PATHS)}")
    print(f"Timeout: {TIMEOUT}s per request")
    print("=" * 80)

    results = []
    with ThreadPoolExecutor(max_workers=6) as executor:
        futures = {
            executor.submit(probe_site, name, url): name
            for name, url in all_sites.items()
        }
        for future in as_completed(futures):
            name = futures[future]
            try:
                r = future.result()
                results.append(r)
                gk = r["gkmlpt"]
                if gk["has_sid"]:
                    marker = f"GKMLPT CONFIRMED (SID={gk['sid']})"
                elif gk["soft_404"]:
                    marker = "soft-404 (page not found)"
                elif gk["error"]:
                    marker = gk["error"]
                elif gk["status"] and gk["status"] >= 400:
                    marker = f"HTTP {gk['status']}"
                elif gk["status"] and gk["status"] < 400:
                    marker = f"HTTP {gk['status']} (no SID, {gk['body_size']} bytes)"
                else:
                    marker = "unknown"
                print(f"  {name:20s} /gkmlpt/index -> {marker}")
            except Exception as e:
                print(f"  {name:20s} -> EXCEPTION: {e}")

    results.sort(key=lambda r: r["name"])

    # === SUMMARY ===
    print("\n" + "=" * 80)
    print("RESULTS")
    print("=" * 80)

    is_province = lambda name: name in PROVINCES

    # Categorize gkmlpt results
    gkmlpt_confirmed = [r for r in results if r["gkmlpt"]["has_sid"]]
    gkmlpt_soft_404 = [r for r in results
                       if r["gkmlpt"]["status"] == 200 and r["gkmlpt"]["soft_404"]]

    print(f"\n--- GKMLPT CONFIRMED (SID found) [{len(gkmlpt_confirmed)}] ---")
    if gkmlpt_confirmed:
        for r in gkmlpt_confirmed:
            gk = r["gkmlpt"]
            label = "Province" if is_province(r["name"]) else "City/Muni"
            extras = [f"SID={gk['sid']}"]
            if gk["has_config"]:
                extras.append("has _CONFIG")
            if gk["tree_count"] is not None:
                extras.append(f"{gk['tree_count']} categories")
            print(f"  [{label}] {r['name']:20s} {', '.join(extras)}")
            print(f"    URL: {gk['url']} -> {gk['final_url']}")
    else:
        print("  (none)")

    print(f"\n--- GKMLPT NOT FOUND [{len(results) - len(gkmlpt_confirmed)}] ---")
    for r in results:
        if r["gkmlpt"]["has_sid"]:
            continue
        gk = r["gkmlpt"]
        label = "Province" if is_province(r["name"]) else "City/Muni"
        if gk["error"]:
            reason = gk["error"]
        elif gk["soft_404"]:
            reason = f"HTTP {gk['status']} (soft-404, page says not found)"
        elif gk["status"] and gk["status"] >= 400:
            reason = f"HTTP {gk['status']}"
        elif gk["status"]:
            reason = f"HTTP {gk['status']} but no SID/_CONFIG ({gk['body_size']} bytes)"
        else:
            reason = "no response"
        print(f"  [{label}] {r['name']:20s} {reason}")

    # Alternative paths summary
    print(f"\n--- ALTERNATIVE PATHS (reachable, non-404) ---")
    alt_hits = []
    for r in results:
        for alt in r["alternatives"]:
            if is_real_success(alt):
                alt_hits.append((r["name"], alt))
    if alt_hits:
        for name, alt in sorted(alt_hits, key=lambda x: x[0]):
            label = "Province" if is_province(name) else "City/Muni"
            sid_note = f" ** SID={alt['sid']} **" if alt["has_sid"] else ""
            print(f"  [{label}] {name:20s} HTTP {alt['status']} at {alt['path']}{sid_note}")
            print(f"    Final URL: {alt['final_url']}")
            print(f"    Size: {alt['body_size']} bytes")
    else:
        print("  (none with real content)")

    # Also show alt paths that returned something (even non-200)
    print(f"\n--- ALTERNATIVE PATHS (all responses) ---")
    for r in results:
        line_parts = []
        for alt in r["alternatives"]:
            if alt["error"]:
                line_parts.append(f"{alt['path']}: {alt['error']}")
            elif alt["soft_404"]:
                line_parts.append(f"{alt['path']}: soft-404")
            else:
                line_parts.append(f"{alt['path']}: HTTP {alt['status']} ({alt['body_size']}b)")
        print(f"  {r['name']:20s} {' | '.join(line_parts)}")

    # Final tally
    print(f"\n{'=' * 80}")
    print(f"CONCLUSION: {len(gkmlpt_confirmed)}/{len(results)} sites have "
          f"confirmed gkmlpt endpoints")
    if not gkmlpt_confirmed:
        print("\nAs expected from prior research (docs/references/gkmlpt-platform-survey.md),")
        print("gkmlpt is a Guangdong-specific platform. None of these non-Guangdong")
        print("provinces/cities use it. Each province runs its own CMS for information")
        print("disclosure and would require a custom crawler adapter.")
    print(f"{'=' * 80}")


if __name__ == "__main__":
    main()
