#!/usr/bin/env python3
"""Probe ONE candidate section before adding it to a crawler. Writes nothing.

"Add a section" is only safe when the listing really lists articles AND the articles
really yield bodies from the crawl vantage, and HTTP 200 proves neither. This fetches
the listing with the same code path `crawlers.govcms` uses (`_list_articles`,
`_extract_body`), then fetches the newest few articles and reports body lengths, and
says how many of the listed URLs the corpus already holds.

    # run on the droplet; --db is opened read-only
    python3 scripts/rnd/discovery/probe_section.py https://www.mfa.gov.cn/fyrbt_673021/
    python3 scripts/rnd/discovery/probe_section.py URL [URL ...] --bodies 3 --db documents.db
"""
from __future__ import annotations

import argparse
import re
import sqlite3
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from crawlers import govcms  # noqa: E402
from crawlers.base import fetch  # noqa: E402

UA = {"User-Agent": ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
                     "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")}
CJK = re.compile(r"[一-鿿]")


def probe(url: str, conn, n_bodies: int) -> dict:
    out = {"url": url, "bytes": 0, "cjk": 0, "listed": 0, "held": 0, "newest": "", "bodies": [], "error": ""}
    try:
        html = fetch(url, timeout=25, retries=1, headers=UA) or ""
    except Exception as exc:  # noqa: BLE001
        out["error"] = f"{type(exc).__name__}: {exc}"[:140]
        return out
    out["bytes"], out["cjk"] = len(html.encode("utf-8", "ignore")), len(CJK.findall(html))
    arts = govcms._list_articles(html, url)
    out["listed"] = len(arts)
    dated = sorted((a for a in arts if a.get("date")), key=lambda a: a["date"], reverse=True)
    out["newest"] = dated[0]["date"] if dated else ""
    if conn is not None:
        for a in arts:
            u = a["url"]
            alt = u.replace("https://", "http://") if u.startswith("https://") else u.replace("http://", "https://")
            if conn.execute("SELECT 1 FROM documents WHERE url != '' AND url IN (?, ?)", (u, alt)).fetchone():
                out["held"] += 1
    for a in (dated or arts)[:n_bodies]:
        time.sleep(1.0)
        try:
            body = govcms._extract_body(fetch(a["url"], timeout=25, retries=1, headers=UA) or "")
            out["bodies"].append((a.get("date", ""), len(body), a.get("title", "")[:36], a["url"]))
        except Exception as exc:  # noqa: BLE001
            out["bodies"].append((a.get("date", ""), -1, f"ERR {type(exc).__name__}", a["url"]))
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("urls", nargs="+")
    ap.add_argument("--db", default=str(ROOT / "documents.db"))
    ap.add_argument("--bodies", type=int, default=3)
    args = ap.parse_args()
    conn = None
    if Path(args.db).exists():
        conn = sqlite3.connect(f"file:{args.db}?mode=ro", uri=True, timeout=60)
        conn.execute("PRAGMA busy_timeout=60000")
    for url in args.urls:
        r = probe(url, conn, args.bodies)
        print(f"{r['url']}\n  bytes={r['bytes']} cjk={r['cjk']} listed={r['listed']} "
              f"held={r['held']} newest={r['newest'] or '-'} {r['error']}", flush=True)
        for d, n, title, u in r["bodies"]:
            print(f"    {d or '-':10} body={n:6}  {title}  {u}")
        time.sleep(1.0)
    return 0


if __name__ == "__main__":
    sys.exit(main())
