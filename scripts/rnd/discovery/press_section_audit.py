#!/usr/bin/env python3
"""Press-release / press-conference audit of the central bodies we crawl.

For every central site a crawler declares (the list is read from the crawler code by
`scripts/build_section_registry.collect`, not typed here) this fetches the homepage
FROM WHERE IT RUNS, finds navigation links whose text names a press section
(新闻发布会 / 发布厅 / 发言人 / 吹风会 / 答记者问 ...), fetches each candidate and
byte-checks it: how many bytes, how many CJK characters, how many article-looking
links. HTTP 200 alone is not evidence on CN government hosts (200 + a 160-byte
redirect stub or a ~1 KB anti-bot shell are both common), so the verdict comes from
the bytes.

It then asks the read-only corpus whether we hold anything under that section's
path, and whether the crawler config mentions the path.

Run it ON THE DROPLET (its NYC IP is the crawl vantage); it writes nothing but the
CSV named by --out.

    python3 scripts/rnd/discovery/press_section_audit.py --out /tmp/press.csv
    python3 scripts/rnd/discovery/press_section_audit.py --site samr --site mofcom --out /tmp/p.csv
    python3 scripts/rnd/discovery/press_section_audit.py --dump-nav nea   # every nav link
"""
from __future__ import annotations

import argparse
import csv
import re
import sqlite3
import sys
import time
from pathlib import Path
from urllib.parse import urljoin, urlsplit

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from crawlers.base import fetch  # noqa: E402
import build_section_registry as reg  # noqa: E402

UA = {"User-Agent": ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
                     "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")}
PRESS_RE = re.compile(r"新闻发布会|发布会|发布厅|发言人|吹风会|答记者问|记者会|例行记者|新闻发布")
# Anchor texts that contain 发布 but are not press sections.
NOT_PRESS_RE = re.compile(r"政策发布|文件发布|信息发布|数据发布|标准发布|公告发布|发布时间|发布日期|发布机构")
A_RE = re.compile(r'<a\b[^>]*?href\s*=\s*["\']([^"\'#]+)["\'][^>]*>(.*?)</a>', re.S | re.I)
TAG_RE = re.compile(r"<[^>]+>")
CJK_RE = re.compile(r"[一-鿿]")
# An article link: a dated or id-shaped leaf, not a directory or an index page.
ART_RE = re.compile(
    r"(t\d{8}_\d+\.s?html?|art_[0-9a-f]{8,}\.html|content_\d+\.s?html?|c_\d+\.html?|/c\.html|"
    r"/\d{6,8}/[\w-]+\.s?html?|/art/\d{4}/[\w/]+\.html|\d{14,}\w*\.html|ARTI\w+\.s?html)", re.I)


def get(url: str) -> tuple[str, str]:
    """-> (html, error). Never raises."""
    try:
        return fetch(url, timeout=20, retries=1, headers=UA) or "", ""
    except Exception as exc:  # noqa: BLE001 - the error text IS the finding
        return "", f"{type(exc).__name__}: {exc}"[:120]


def anchors(html: str, base: str) -> list[tuple[str, str]]:
    out, seen = [], set()
    for href, inner in A_RE.findall(html):
        text = re.sub(r"\s+", "", TAG_RE.sub("", inner))
        m = re.search(r'title\s*=\s*["\']([^"\']+)', inner)
        if not text and m:
            text = m.group(1)
        if href.lower().startswith(("javascript", "mailto")):
            continue
        url = urljoin(base, href.strip())
        if (url, text) in seen:
            continue
        seen.add((url, text))
        out.append((url, text))
    return out


def verdict(html: str, err: str) -> tuple[str, int, int, int]:
    """-> (status, bytes, cjk, article_links)."""
    if err:
        return f"unreachable ({err})", 0, 0, 0
    b, cjk = len(html.encode("utf-8", "ignore")), len(CJK_RE.findall(html))
    arts = len({m.group(0) for m in ART_RE.finditer(html)})
    if b < 2000 or cjk < 50:
        return "stub (anti-bot shell or redirect)", b, cjk, arts
    if arts < 3:
        return "reachable, list is script-rendered or not a list", b, cjk, arts
    return "reachable", b, cjk, arts


def same_org(url: str, base_url: str) -> bool:
    def root(h):
        parts = h.lower().split(":")[0].split(".")
        return ".".join(parts[-3:]) if parts[-2:] == ["gov", "cn"] else ".".join(parts[-2:])
    return root(urlsplit(url).netloc) == root(urlsplit(base_url).netloc)


def held(conn, site_key: str, url: str) -> tuple[int, str]:
    """Documents we hold under the section's directory: (count, newest date_published)."""
    sp = urlsplit(url)
    _, pre = reg.norm_prefix(sp.path or "/")
    if pre == "/":
        return 0, ""
    n, newest = 0, ""
    for scheme in ("https", "http"):
        lo = f"{scheme}://{sp.netloc}{pre}"
        # range scan on the partial unique index: needs `url != ''` to be usable
        r = conn.execute("SELECT COUNT(*), MAX(substr(date_published,1,10)) FROM documents "
                         "WHERE url != '' AND url >= ? AND url < ?", (lo, lo + "￿")).fetchone()
        n += r[0] or 0
        newest = max(newest, r[1] or "")
    return n, newest


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=str(ROOT / "documents.db"))
    ap.add_argument("--site", action="append", help="repeatable; default = every central site")
    ap.add_argument("--out")
    ap.add_argument("--dump-nav", metavar="SITE", help="print every homepage link of one site and exit")
    ap.add_argument("--max-candidates", type=int, default=4)
    args = ap.parse_args()

    sites = reg.collect()
    sites.pop("__import_errors__", None)
    if args.dump_nav:
        s = sites[args.dump_nav]
        html, err = get(s["base_url"])
        print(s["base_url"], len(html), err)
        for url, text in anchors(html, s["base_url"]):
            if text and same_org(url, s["base_url"]):
                print(f"  {text[:24]:26} {url}")
        return 0

    keys = args.site or sorted(k for k, s in sites.items() if s["admin_level"] == "central")
    conn = sqlite3.connect(f"file:{args.db}?mode=ro", uri=True, timeout=60)
    conn.execute("PRAGMA busy_timeout=60000")
    rows = []
    for k in keys:
        s = sites[k]
        base = s["base_url"].rstrip("/") + "/"
        html, err = get(base)
        hstatus, hb, hcjk, _ = verdict(html, err)
        cfg_paths = " ".join(sec["config_path"] for sec in s["sections"])
        cands = []
        if not err:
            for url, text in anchors(html, base):
                if PRESS_RE.search(text) and not NOT_PRESS_RE.search(text) and same_org(url, base) \
                        and len(text) <= 16 and url.rstrip("/") != base.rstrip("/"):
                    if url not in [c[0] for c in cands]:
                        cands.append((url, text))
        if not cands:
            rows.append({"site_key": k, "name": s["name"], "module": s["module"], "homepage": base,
                         "homepage_status": f"{hstatus} [{hb}B/{hcjk}cjk]", "press_text": "",
                         "press_url": "", "press_status": "no press link on homepage" if not err else "",
                         "bytes": 0, "cjk": 0, "article_links": 0, "in_config": "", "held": 0,
                         "held_newest": "", "example": ""})
        for url, text in cands[:args.max_candidates]:
            time.sleep(1.0)
            ph, perr = get(url)
            st, b, cjk, arts = verdict(ph, perr)
            ex = ""
            for aurl, _t in anchors(ph, url):
                if ART_RE.search(aurl) and same_org(aurl, base):
                    ex = aurl
                    break
            n, newest = held(conn, k, url)
            _, pre = reg.norm_prefix(urlsplit(url).path or "/")
            in_cfg = "yes" if pre != "/" and pre.strip("/") in cfg_paths else "no"
            rows.append({"site_key": k, "name": s["name"], "module": s["module"], "homepage": base,
                         "homepage_status": f"{hstatus} [{hb}B/{hcjk}cjk]", "press_text": text,
                         "press_url": url, "press_status": st, "bytes": b, "cjk": cjk,
                         "article_links": arts, "in_config": in_cfg, "held": n,
                         "held_newest": newest, "example": ex})
        r = rows[-1]
        print(f"{k:12} home={hstatus[:22]:22} cands={len(cands):2} "
              f"{r['press_text'][:10]:10} {r['press_status'][:28]:28} arts={r['article_links']:3} "
              f"held={r['held']:5} {r['press_url']}", flush=True)
        time.sleep(1.0)
    if args.out and rows:
        with open(args.out, "w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
            w.writeheader()
            w.writerows(rows)
    return 0


if __name__ == "__main__":
    sys.exit(main())
