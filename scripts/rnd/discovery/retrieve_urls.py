"""Retrieve arbitrary important documents by URL into the corpus.

For one-off "make sure we have this" docs from sources we don't crawl (MFA, CCTV,
CNR, The Paper, People's Daily app, Xinhua news.cn, …). Fetches each URL with
charset auto-detection (many CN sites are GB18030, not UTF-8), extracts title +
body, and stores under a domain-derived site_key. Writes/refreshes a coverage CSV.

Usage:
    python3 scripts/rnd/discovery/retrieve_urls.py URL [URL ...]
    python3 scripts/rnd/discovery/retrieve_urls.py --file urls.txt --csv docs/working/important_docs_coverage.csv
"""
import argparse, csv, re, sys, urllib.request
from html import unescape
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[3]))
from crawlers.base import init_db, next_id, save_raw_html, store_document, store_site  # noqa

UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"}
SITE_NAMES = {  # domain -> (site_key, display name, admin_level)
    "www.mfa.gov.cn": ("mfa", "Ministry of Foreign Affairs (外交部)", "central"),
    "news.cctv.com": ("cctv", "CCTV News (央视新闻)", "media"),
    "news.cnr.cn": ("cnr", "China National Radio (央广网)", "media"),
    "www.thepaper.cn": ("thepaper", "The Paper (澎湃新闻)", "media"),
    "www.peopleapp.com": ("peopleapp", "People's Daily App (人民日报客户端)", "media"),
    "www.news.cn": ("newscn", "Xinhua news.cn (新华社)", "media"),
}


def fetch_raw(url):
    raw = urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=25).read()
    m = re.search(rb'charset=["\']?([\w\-]+)', raw[:3000], re.I)
    enc = (m.group(1).decode("ascii", "ignore") if m else "utf-8").lower()
    if enc in ("gb2312", "gbk", "gb18030"):
        enc = "gb18030"
    return raw.decode(enc, "replace")


def extract_title(html):
    for pat in [r'<meta\s+property=["\']og:title["\']\s+content=["\']([^"\']+)["\']',
                r"<h1[^>]*>(.*?)</h1>", r"<title>([^<]+)</title>"]:
        m = re.search(pat, html, re.I | re.S)
        if m:
            t = unescape(re.sub(r"<[^>]+>", "", m.group(1)).strip())
            t = re.sub(r"\s*[_|]\s*[^_|]{0,20}(新闻|网|外交部|央视网|澎湃|新华|客户端)\s*$", "", t).strip()
            if len(t) > 3:
                return t
    return ""


def extract_body(html):
    paras = [unescape(re.sub(r"<[^>]+>", "", p)).replace("\xa0", " ").strip()
             for p in re.findall(r"<p[^>]*>(.*?)</p>", html, re.S)]
    body = "\n".join(t for t in paras if len(t) >= 10 and "ICP" not in t and "版权" not in t)
    if len(body) < 150:  # fallback: largest text container
        best = max((unescape(re.sub(r"<[^>]+>", " ", d)) for d in re.findall(r"<div[^>]*>(.*?)</div>", html, re.S)),
                   key=len, default="")
        best = re.sub(r"\s+", " ", best).strip()
        body = best if len(best) > len(body) else body
    return body.strip()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("urls", nargs="*")
    ap.add_argument("--file")
    ap.add_argument("--csv")
    args = ap.parse_args()
    urls = list(args.urls)
    if args.file:
        urls += [ln.strip() for ln in Path(args.file).read_text().splitlines() if ln.strip()]

    conn = init_db()
    rows = []
    for u in urls:
        dom = u.split("/")[2]
        site_key, site_name, level = SITE_NAMES.get(dom, (re.sub(r"\W", "", dom.split(".")[-2]), dom, "media"))
        store_site(conn, site_key, {"name": site_name, "base_url": f"https://{dom}", "admin_level": level})
        if conn.execute("SELECT 1 FROM documents WHERE url=?", (u,)).fetchone():
            r = conn.execute("SELECT title, LENGTH(body_text_cn) FROM documents WHERE url=?", (u,)).fetchone()
            rows.append([u, dom, site_key, "HELD", (r[0] or "")[:45], r[1] or 0]); continue
        try:
            html = fetch_raw(u)
            title, body = extract_title(html), extract_body(html)
            doc_id = next_id(conn)
            store_document(conn, site_key, {
                "id": doc_id, "title": title or u, "publisher": site_name,
                "date_published": (re.search(r"/(\d{4})(\d{2})(\d{2})_", u) or re.search(r"/(\d{4})/(\d{2})/(\d{2})/", u) or [None])
                and "-".join((re.search(r"/(\d{4})(\d{2})(\d{2})_", u) or re.search(r"/(\d{4})/(\d{2})/(\d{2})/", u)).groups()),
                "body_text_cn": body, "url": u, "classify_main_name": "重要文献",
                "raw_html_path": save_raw_html(site_key, doc_id, html),
            })
            conn.commit()
            rows.append([u, dom, site_key, "RETRIEVED", title[:45], len(body)])
        except Exception as e:
            rows.append([u, dom, site_key, "FAIL:" + type(e).__name__, "", 0])

    if args.csv:
        with open(args.csv, "w", newline="") as f:
            w = csv.writer(f); w.writerow(["url", "domain", "site_key", "status", "title", "body_len"]); w.writerows(rows)
    for r in rows:
        print(f"  {r[3]:12} {r[5]!s:>6}  {r[2]:9} {r[4]}")


if __name__ == "__main__":
    main()
