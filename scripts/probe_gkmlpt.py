"""
Probe Guangdong city government websites for active gkmlpt endpoints.

Checks each URL for a working gkmlpt platform by looking for SID and _CONFIG
in the response, and extracts top-level category count from TREE if present.
"""

import json
import re
import sys

import requests

TIMEOUT = 10

BROWSER_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/131.0.0.0 Safari/537.36"
)

TARGETS = {
    # --- Guangdong prefecture-level cities (not already in SITES) ---
    "Dongguan": "http://www.dg.gov.cn/gkmlpt/index",
    "Foshan": "http://www.foshan.gov.cn/gkmlpt/index",
    "Zhongshan": "http://www.zs.gov.cn/gkmlpt/index",
    "Shantou": "http://www.shantou.gov.cn/gkmlpt/index",
    "Zhaoqing": "http://www.zhaoqing.gov.cn/gkmlpt/index",
    "Shaoguan": "http://www.sg.gov.cn/gkmlpt/index",
    "Heyuan": "http://www.heyuan.gov.cn/gkmlpt/index",
    "Meizhou": "http://www.meizhou.gov.cn/gkmlpt/index",
    "Shanwei": "http://www.shanwei.gov.cn/gkmlpt/index",
    "Yangjiang": "http://www.yangjiang.gov.cn/gkmlpt/index",
    "Zhanjiang": "http://www.zhanjiang.gov.cn/gkmlpt/index",
    "Maoming": "http://www.maoming.gov.cn/gkmlpt/index",
    "Qingyuan": "http://www.qingyuan.gov.cn/gkmlpt/index",
    "Chaozhou": "http://www.chaozhou.gov.cn/gkmlpt/index",
    "Jieyang": "http://www.jieyang.gov.cn/gkmlpt/index",
    "Yunfu": "http://www.yunfu.gov.cn/gkmlpt/index",
    # --- Missing Shenzhen districts ---
    "Bao'an": "http://www.baoan.gov.cn/gkmlpt/index",
    "Yantian": "http://www.yantian.gov.cn/gkmlpt/index",
    "Longgang": "http://www.lg.gov.cn/gkmlpt/index",
    "Dapeng": "http://www.dpxq.gov.cn/gkmlpt/index",
}


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


def extract_sid(text: str) -> str | None:
    """Extract SID value from page source."""
    m = re.search(r'SID:\s*["\']([^"\']+)["\']', text)
    return m.group(1) if m else None


def probe(name: str, url: str) -> dict:
    """Probe a single URL and return result dict."""
    result = {"name": name, "url": url, "ok": False}
    try:
        resp = requests.get(
            url,
            timeout=TIMEOUT,
            headers={"User-Agent": BROWSER_UA},
            allow_redirects=True,
        )
        result["status"] = resp.status_code
        text = resp.text
        result["size"] = len(text)

        # Check for SID (primary indicator of gkmlpt)
        sid = extract_sid(text)
        if sid:
            result["ok"] = True
            result["sid"] = sid

        # Check for _CONFIG
        if "_CONFIG" in text:
            result["has_config"] = True

        # Try to get tree category count
        tree_count = extract_tree_count(text)
        if tree_count is not None:
            result["tree_categories"] = tree_count

    except requests.exceptions.ConnectTimeout:
        result["error"] = "connection timeout"
    except requests.exceptions.ConnectionError as e:
        reason = str(e)
        if "Name or service not known" in reason or "getaddrinfo" in reason:
            result["error"] = "DNS resolution failed"
        elif "Connection refused" in reason:
            result["error"] = "connection refused"
        elif "Connection reset" in reason:
            result["error"] = "connection reset"
        else:
            result["error"] = f"connection error: {reason[:120]}"
    except requests.exceptions.ReadTimeout:
        result["error"] = "read timeout"
    except requests.exceptions.TooManyRedirects:
        result["error"] = "too many redirects"
    except requests.exceptions.RequestException as e:
        result["error"] = f"request error: {str(e)[:120]}"

    return result


def main():
    print(f"Probing {len(TARGETS)} gkmlpt endpoints...\n")
    print(f"{'City':<14} {'Status':<8} {'Result':<50}")
    print("-" * 72)

    results = []
    for name, url in TARGETS.items():
        r = probe(name, url)
        results.append(r)

        if r["ok"]:
            extras = []
            if r.get("sid"):
                extras.append(f"SID={r['sid']}")
            if r.get("tree_categories") is not None:
                extras.append(f"{r['tree_categories']} categories")
            if r.get("has_config"):
                extras.append("has _CONFIG")
            detail = ", ".join(extras)
            print(f"{name:<14} {'OK':<8} {detail}")
        elif "error" in r:
            print(f"{name:<14} {'FAIL':<8} {r['error']}")
        else:
            status = r.get("status", "?")
            size = r.get("size", 0)
            print(f"{name:<14} {str(status):<8} no SID found (body {size} bytes)")

    # Summary
    working = [r for r in results if r["ok"]]
    failed = [r for r in results if not r["ok"]]
    print(f"\n{'=' * 72}")
    print(f"SUMMARY: {len(working)}/{len(results)} endpoints have active gkmlpt")
    if working:
        print(f"\n  Working ({len(working)}):")
        for r in working:
            cats = f", {r['tree_categories']} categories" if r.get("tree_categories") is not None else ""
            print(f"    {r['name']:<14} {r['url']}{cats}")
    if failed:
        print(f"\n  Not working ({len(failed)}):")
        for r in failed:
            reason = r.get("error", f"HTTP {r.get('status', '?')}, no SID")
            print(f"    {r['name']:<14} {reason}")


if __name__ == "__main__":
    main()
