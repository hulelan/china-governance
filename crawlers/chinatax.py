"""
国家税务总局 (State Taxation Administration) crawler — the 政策法规库 (fgk).

fgk.chinatax.gov.cn is a heavily-defended JS app; this crawler decodes its three
layers:

 1. **C3VK cookie challenge** — every dynamic URL first returns a ~380 B JS shell
    that sets `document.cookie = "C3VK=<token>; path=/; max-age=300"` and reloads.
    Re-requesting with that cookie yields the real page. The cookie is domain-wide
    for 5 min, so `_Session` solves once and reuses it (re-solving only when a
    shell reappears) — halving requests over a ~10k-doc crawl.
 2. **layui shell** — the category list page (`/zcfgk/cNNN/listflfg.html`) renders
    its rows client-side; the useful bit is a `channelId = <32-hex UUID>` var (the
    URL's `cNNN` is a decoy).
 3. **JSON list API** — `POST https://www.chinatax.gov.cn/getFileListByCodeId`
    with `{codeId:'', channelId:<uuid>, page, size}` returns
    `results.data.results[]` (title, url, publishedTimeStr) + `total`.

Article bodies live on the fgk subdomain (the API's `url` points at www, which
404s) in a `class="article"` container.

Categories are the `listflfg*` list pages (法律/行政法规/部门规章/规范性文件/
税收政策), ~9,900 docs total. The API returns newest-first, so incremental runs
early-exit a category once a full page is all-held.

Usage:
    python -m crawlers.chinatax                 # all categories, incremental
    python -m crawlers.chinatax --max-docs 500  # bounded backfill chunk
    python -m crawlers.chinatax --list-only     # metadata only, skip bodies
"""
import argparse
import html as H
import json
import re
import ssl
import time
import urllib.parse
import urllib.request

from crawlers.base import (
    fetch, init_db, log, next_id, save_raw_html,
    show_stats, store_document, store_site,
)

SITE_KEY = "chinatax"
CFG = {"name": "State Taxation Administration (国家税务总局)",
       "base_url": "https://fgk.chinatax.gov.cn", "admin_level": "central"}
FGK = "https://fgk.chinatax.gov.cn"
API = "https://www.chinatax.gov.cn/getFileListByCodeId"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")
_CTX = ssl.create_default_context()
_CTX.check_hostname = False
_CTX.verify_mode = ssl.CERT_NONE
try:
    _CTX.set_ciphers("DEFAULT@SECLEVEL=1")
except ssl.SSLError:
    pass

# Document categories (list pages carrying a channelId + a getFileListByCodeId feed).
CATEGORY_PATHS = [
    "/zcfgk/c100006/listflfg.html",     # 税收法规规章 (~5000)
    "/zcfgk/c102416/listflfg.html",     # (~1500)
    "/zcfgk/c100012/listflfg.html",     # (~1900)
    "/zcfgk/c102424/listflfg.html",     # (~800)
    "/zcfgk/c100013/listflfg.html",     # 其他文件 (~480)
    "/zcfgk/c100009/listflfg_fg.html",  # 行政法规 (~75)
    "/zcfgk/c100010/listflfg_fg.html",  # (~65)
    "/zcfgk/c102440/listflfg.html",     # (~35)
]

_C3VK_RE = re.compile(r"C3VK=([a-z0-9]+)")
_CHANNEL_RE = re.compile(r"channelId\s*=\s*[\"']?([a-f0-9]{32})")
_DOCNUM_RE = re.compile(r"([一-鿿]{2,12}〔\d{4}〕\d+号|国税发〔\d{4}〕\d+号|财税〔\d{4}〕\d+号)")


class _Session:
    """Fetches through the C3VK challenge, caching the domain-wide cookie.

    The cookie is max-age=300; we refresh it proactively (every 240 s) so body
    fetches don't each pay a re-challenge round trip once it expires, and the API
    (which doesn't return a shell) doesn't silently fail on an expired cookie.
    """

    def __init__(self):
        self.cookie = ""
        self.cookie_at = 0.0

    def _fresh(self):
        return self.cookie and (time.time() - self.cookie_at) < 240

    def get(self, url, tries=3):
        body = ""
        for _ in range(tries):
            hdr = {"User-Agent": UA, "Referer": FGK + "/"}
            if self.cookie:
                hdr["Cookie"] = self.cookie
            body = fetch(url, headers=hdr)
            m = _C3VK_RE.search(body)
            if m and len(body) < 1500:          # a challenge shell, not real content
                self.cookie = "C3VK=" + m.group(1)
                self.cookie_at = time.time()
                continue
            return body
        return body

    def ensure_cookie(self):
        if not self._fresh():
            self.get(FGK + "/")               # re-solves + stamps cookie_at

    def api(self, channel_id, page, size=30):
        self.ensure_cookie()
        data = urllib.parse.urlencode(
            {"codeId": "", "channelId": channel_id, "page": page, "size": size}).encode()
        hdr = {"User-Agent": UA, "Content-Type": "application/x-www-form-urlencoded",
               "Referer": FGK + "/", "Origin": FGK}
        if self.cookie:
            hdr["Cookie"] = self.cookie
        req = urllib.request.Request(API, data=data, headers=hdr, method="POST")
        raw = urllib.request.urlopen(req, timeout=25, context=_CTX).read()
        return json.loads(raw)["results"]["data"]


def _fgk_url(api_url):
    # API returns a www.chinatax.gov.cn URL (404s); the article lives on fgk.
    return re.sub(r"^https?://[^/]+", FGK, api_url)


def _body_of(html):
    i = html.find('class="article')
    if i < 0:
        i = html.find('class="content')
    region = html[i:i + 80_000] if i >= 0 else html
    region = re.split(r'(相关(?:附件|链接|文件)|class="[^"]*(?:foot|share|xglj))', region, 1)[0]
    ps = [H.unescape(re.sub(r"<[^>]+>", "", p)).strip()
          for p in re.findall(r"<p[^>]*>(.*?)</p>", region, re.S)]
    return "\n".join(p for p in ps if len(p) >= 8)


def crawl(conn, fetch_bodies=True, max_docs=None):
    store_site(conn, SITE_KEY, CFG)
    sess = _Session()
    stored = 0
    for path in CATEGORY_PATHS:
        if max_docs and stored >= max_docs:
            break
        lp = sess.get(FGK + path)
        cm = _CHANNEL_RE.search(lp)
        if not cm:
            log.warning(f"[{SITE_KEY}] no channelId for {path}")
            continue
        channel = cm.group(1)
        try:
            first = sess.api(channel, 1, 1)
        except Exception as e:
            log.warning(f"[{SITE_KEY}] api {path}: {e}")
            continue
        total = first.get("total", 0)
        log.info(f"[{SITE_KEY}] {path} channel={channel[:10]} total={total}")
        page, done = 1, False
        while not done:
            try:
                d = sess.api(channel, page, 30)
            except Exception as e:
                log.warning(f"  api page {page}: {e}")
                break
            rows = d.get("results", [])
            if not rows:
                break
            all_held = True
            for it in rows:
                url = _fgk_url(it.get("url", ""))
                if not url or "content" not in url:
                    continue
                if conn.execute("SELECT 1 FROM documents WHERE url=?", (url,)).fetchone():
                    continue
                all_held = False
                title = H.unescape(it.get("title", "")).strip()
                date_pub = (it.get("publishedTimeStr", "") or "")[:10]
                doc_id = next_id(conn)
                body, raw, nm = "", "", None
                if fetch_bodies:
                    try:
                        art = sess.get(url)
                        body = _body_of(art)
                        nm = _DOCNUM_RE.search(body[:400]) or _DOCNUM_RE.search(title)
                        raw = save_raw_html(SITE_KEY, doc_id, art)
                    except Exception as e:
                        log.warning(f"  body {url}: {e}")
                    time.sleep(0.3)
                store_document(conn, SITE_KEY, {
                    "id": doc_id, "title": title,
                    "document_number": nm.group(1) if nm else "",
                    "date_published": date_pub,
                    "body_text_cn": body, "url": url,
                    "classify_main_name": it.get("channelName", "税收政策"),
                    "raw_html_path": raw, "admin_level": "central",
                })
                stored += 1
                if max_docs and stored >= max_docs:
                    done = True
                    break
            conn.commit()
            # Incremental: a full page all-held means we've reached known docs.
            if all_held and len(rows) == 30:
                break
            page += 1
            if page > (total // 30 + 2):
                break
    log.info(f"[{SITE_KEY}] done: {stored} new docs")
    return stored


def main():
    ap = argparse.ArgumentParser(description="国家税务总局 (STA) 政策法规库 crawler")
    ap.add_argument("--list-only", action="store_true", help="metadata only, skip bodies")
    ap.add_argument("--max-docs", type=int, help="cap docs this run (bounded backfill)")
    ap.add_argument("--db")
    args = ap.parse_args()
    conn = init_db(args.db) if args.db else init_db()
    crawl(conn, fetch_bodies=not args.list_only, max_docs=args.max_docs)
    show_stats(conn)


if __name__ == "__main__":
    main()
