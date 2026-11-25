#!/usr/bin/env python3
"""Prime the web app's publish-keyed cache right after the nightly restart.

Run by daily_sync.sh Phase 3, after `touch .publish_stamp` and the restart. Every
page cached in web/services/pubcache.py is computed ONCE here and written to the
shared on-disk cache, so both uvicorn workers serve it warm and no human pays the
cold cost (measured 2026-11-25: /dashboard 13s, /chain 8s, /lens 9s, /collections/oil
5.6s on a first hit). One request per URL is enough because the cache is shared
across workers; the old curl loop could only warm whichever worker answered.

    python3 scripts/warm_web_cache.py                       # localhost:8001
    python3 scripts/warm_web_cache.py --base http://127.0.0.1:8011
    python3 scripts/warm_web_cache.py --list                # print the URLs only

Exit status is 0 unless the app never came up, so a slow page cannot fail the
nightly; each URL's status and time is printed for the log.
"""
import argparse
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def warm_urls() -> list:
    """The pages a visitor reaches by clicking: the nav, every /chain topic tab,
    and every suggested /lens topic. Derived from the app's own constants so a new
    chain topic or lens suggestion is warmed without editing this list."""
    from web.services.chain import TOPIC_KEYWORDS
    from web.services.lens import LENS_SUGGESTIONS
    urls = ["/", "/dashboard", "/tracker", "/discourse", "/collections/oil",
            "/browse", "/browse?site=gov", "/structure", "/network",
            "/api/v1/network?min_degree=3", "/api/v1/stats", "/officials",
            "/research", "/annotations", "/lens"]
    urls += [f"/chain/{t}" for t in TOPIC_KEYWORDS]
    urls += ["/lens?q=" + urllib.parse.quote(q) for q in LENS_SUGGESTIONS]
    return urls


def fetch(url: str, timeout: float):
    t0 = time.time()
    try:
        with urllib.request.urlopen(url, timeout=timeout) as r:
            n = len(r.read())
            return r.status, n, time.time() - t0
    except urllib.error.HTTPError as e:
        return e.code, 0, time.time() - t0
    except Exception as e:   # timeout, refused
        return type(e).__name__, 0, time.time() - t0


def wait_up(base: str, seconds: float) -> bool:
    deadline = time.time() + seconds
    while time.time() < deadline:
        status, _, _ = fetch(base + "/api/v1/stats", timeout=10)
        if status == 200:
            return True
        time.sleep(1)
    return False


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--base", default="http://localhost:8001")
    ap.add_argument("--timeout", type=float, default=180.0, help="per-URL timeout (s)")
    ap.add_argument("--wait", type=float, default=60.0, help="seconds to wait for the app")
    ap.add_argument("--list", action="store_true")
    a = ap.parse_args()

    urls = warm_urls()
    if a.list:
        print("\n".join(urls))
        return 0
    if not wait_up(a.base, a.wait):
        print(f"warm_web_cache: app at {a.base} did not come up in {a.wait:.0f}s")
        return 1
    t_all = time.time()
    bad = 0
    for u in urls:
        status, n, dt = fetch(a.base + u, a.timeout)
        bad += status != 200
        print(f"  {dt:6.2f}s  {status}  {n:>9,}B  {urllib.parse.unquote(u)}", flush=True)
    print(f"warm_web_cache: {len(urls)} urls, {bad} not-200, {time.time()-t_all:.1f}s total")
    return 0


if __name__ == "__main__":
    sys.exit(main())
