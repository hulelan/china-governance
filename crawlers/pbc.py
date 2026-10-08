"""
中国人民银行 (People's Bank of China) crawler — 条法司 regulations + normative docs.

PBOC's list pages don't put dates next to anchors on the ARTICLE page, which stumps
generic scrapers; the trick is that each recent article's URL node-id is a
**timestamp**, e.g. `/tiaofasi/144941/144957/2026052217462526593/index.html`
→ 2026-05-22. Legacy articles (pre-~2025) instead carry a SHORT numeric CMS
node-id (`/144957/3591404/index.html`), which is not a timestamp at all — so the
authoritative date is the `<span class="hui12">YYYY-MM-DD</span>` the LIST page
prints beside each anchor, and the node-id timestamp is only the fallback.
(This matters: a 19-digit node-id is the CMS *creation* stamp and can differ from
the published date — 2026012314163359926 is listed as 2026-01-26.)

PAGINATION (the reason this crawler used to hold only 31 docs — 2026-10-08).
The pager is an "easysite/eportal" article-list portlet. It is NOT the common
`index_N.html` dialect (those 404 here) and it prints no `共N页`/`createPageHTML`.
Page 1 instead carries its own pager, self-describing, in two places:

    <a onclick="queryArticleByCondition(this,'/tiaofasi/144941/144957/21892-2.html')"
       tagname="/tiaofasi/144941/144957/21892-2.html">下一页</a>
    <input name="article_paging_list_hidden" moduleid="21892" totalpage="6">

so page N>1 is a PLAIN GET of `{section}/{prefix}-{N}.html`. The `prefix` must be
READ from those tagnames, never reconstructed from `moduleid`: 144957's module id
is numeric (`21892` → `21892-2.html`) but 3581332's is a 32-char uuid of which the
path uses only the first 8 chars (`3b3662a6db7145c0...` → `3b3662a6-2.html`).
Page `totalpage+1` returns a real 404, so the walk also stops cleanly on its own.

Covers the two document subsections of 条法司 (Legal Affairs Dept). Measured by a
full `--probe` walk on 2026-10-08: 541 documents, 1993-01-14 .. 2026-09-11.
  - 3581332 规范性文件 (normative documents) — 430 of 430 records, 22 pages, from 1997-07-19
  - 144957  部门规章 (PBOC orders / 令)      — 111 of 113 records,  6 pages, from 1993-01-14
The 2 rows 144957 counts but this crawler does not take are cross-posts whose hrefs
point into ANOTHER section (`goutongjiaoliu/113456/113469/…`); `_rows` is deliberately
scoped to the section it is walking, so they belong to that section's crawl, not this
one. (The 法律/行政法规 subsections link out to external law texts; 工作信息/简介/意见征集
are nav.) Adding a section is one SECTIONS entry.

BODIES ARE MOSTLY PDFs. 360 of the 541 documents — effectively everything before
~2020 — publish as a PDF attachment whose only on-page trace is the link's filename.
See `_body_of` for why that needed labelling rather than being left as-is.

NOT the same CMS as SAFE (国家外汇管理局): safe.gov.cn serves
`/safe/YYYY/MMDD/<id>.html` article URLs under a `共28页` + `pagesInput` JS pager
with none of the easysite markers, so it needs its own crawler. Probed 2026-10-08.

Usage:
    python -m crawlers.pbc                  # full walk, bodies
    python -m crawlers.pbc --probe          # enumerate the lists, write NOTHING
    python -m crawlers.pbc --list-only      # store metadata only, no bodies
    python -m crawlers.pbc --max-pages 3    # bound the walk
"""
import argparse
import html as H
import json
import re
import sys
import time
import urllib.error

from crawlers.base import (
    REQUEST_DELAY, WriteRetryStats, commit_with_retry, fetch, init_db, log,
    next_id, save_raw_html, show_stats, store_document, store_site,
)

SITE_KEY = "pbc"
CFG = {"name": "People's Bank of China (中国人民银行)",
       "base_url": "http://www.pbc.gov.cn", "admin_level": "central"}
BASE = "http://www.pbc.gov.cn"
UA = {"User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                     "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"),
      "Referer": "http://www.pbc.gov.cn/"}

# (section path under the site root, human label)
SECTIONS = [
    ("tiaofasi/144941/3581332", "规范性文件"),
    ("tiaofasi/144941/144957", "部门规章"),
]

# Both sections are < 25 pages; the bound is a runaway guard, not a scope limit.
DEFAULT_MAX_PAGES = 40

# A node-id is a timestamp only when it is long enough to BE one (YYYYMMDD…).
# Deliberately a floor on the RAW id, and only used as a fallback — the 7-digit
# legacy ids are real documents, and the old `\d{15,}` row regex silently
# refused every one of them (that floor was the 31-doc bug, half of it).
_TS_ID_MIN = 14

_ATT_RE = re.compile(r'href=["\']((?:/[^"\']+)\.(?:pdf|doc|docx|xls|xlsx|zip))["\']', re.I)

_DOCNUM_RE = re.compile(r"(中国人民银行(?:公告|令)〔\d{4}〕第?\d+号|银发〔\d{4}〕\d+号|[一-鿿]{2,10}〔\d{4}〕\d+号)")


def _get(url):
    return fetch(url, headers=UA)


def _pager(list_html, section):
    """(page-url prefix, total_pages) read off the list page's own pager.

    Returns (None, 1) when the page carries no pager (single-page section).
    """
    if not list_html:
        return None, 1
    tags = re.findall(
        rf'tagname=["\'](?:{re.escape(BASE)})?/{re.escape(section)}/([\w]+)-(\d+)\.html["\']',
        list_html)
    if not tags:
        return None, 1
    # The pager links all share one prefix; take the most common in case of noise.
    prefixes = {}
    for pre, _n in tags:
        prefixes[pre] = prefixes.get(pre, 0) + 1
    prefix = max(prefixes, key=lambda p: prefixes[p])
    seen_max = max(int(n) for pre, n in tags if pre == prefix)
    m = re.search(r'article_paging_list_hidden"[^>]*totalpage="(\d+)"', list_html)
    total = int(m.group(1)) if m else seen_max
    return prefix, max(total, 1)


def _page_url(section, prefix, page):
    """Page 1 is the section index; later pages are the portlet's paging files."""
    if page <= 1 or not prefix:
        return f"{BASE}/{section}/index.html"
    return f"{BASE}/{section}/{prefix}-{page}.html"


def _rows(list_html, section):
    """(node_id, title, list_date) for each article on a section list page.

    `list_date` is '' when the row prints no date — the row is still yielded, so a
    template change can never silently drop documents (it shows up as a dateless
    count in the log instead).
    """
    anchor = re.compile(
        rf'<a\s+href=["\'](?:{re.escape(BASE)})?/{re.escape(section)}/(\d{{4,}})/index\.html["\']'
        rf'([^>]*)>(.*?)</a>', re.S)
    out, seen = [], set()
    for m in anchor.finditer(list_html):
        nid, attrs, inner = m.group(1), m.group(2), m.group(3)
        if nid in seen:
            continue
        tm = re.search(r'title=["\']([^"\']*)["\']', attrs)
        title = tm.group(1) if tm else re.sub(r"<[^>]+>", "", inner)
        title = H.unescape(title).strip()
        if len(title) < 4:
            continue
        # The date sits in the same <td>, just after the anchor. Read a FIXED
        # window rather than requiring a terminator: a regex that must match a
        # following "<a " would drop the last row of a page outright.
        tail = list_html[m.end():m.end() + 200]
        dm = re.search(r'<span[^>]*class="hui12"[^>]*>\s*(\d{4}-\d{2}-\d{2})\s*</span>', tail)
        seen.add(nid)
        out.append((nid, title, dm.group(1) if dm else ""))
    return out


def _date_for(nid, list_date):
    """The list page's printed date wins; a long node-id is the timestamp fallback."""
    if list_date:
        return list_date
    if len(nid) >= _TS_ID_MIN and nid[:4].isdigit():
        return f"{nid[:4]}-{nid[4:6]}-{nid[6:8]}"
    return ""


def _walk(section, max_pages):
    """Enumerate (node_id, title, date) across the section's pages, newest first."""
    rows, seen = [], set()
    prefix, total = None, 1
    page = 1
    while page <= max_pages and page <= total:
        url = _page_url(section, prefix, page)
        try:
            lp = _get(url)
        except urllib.error.HTTPError as e:
            if e.code in (404, 410):
                log.info(f"[{SITE_KEY}]   page {page}: {e.code} — end of section")
            else:
                log.warning(f"[{SITE_KEY}]   page {page} ({url}): {e}")
            break
        except Exception as e:
            log.warning(f"[{SITE_KEY}]   page {page} ({url}): {e}")
            break
        if page == 1:
            prefix, total = _pager(lp, section)
            log.info(f"[{SITE_KEY}]   pager: prefix={prefix} totalpage={total}")
        page_rows = [r for r in _rows(lp, section) if r[0] not in seen]
        if not page_rows:
            log.info(f"[{SITE_KEY}]   page {page}: no new rows — stopping")
            break
        for r in page_rows:
            seen.add(r[0])
        rows.extend(page_rows)
        page += 1
        if page <= total:
            time.sleep(REQUEST_DELAY)
    return rows


def _attachments(html):
    """Absolute URLs of the files linked inside the article's `id="zoom"` region."""
    i = html.find('id="zoom"')
    region = html[i:i + 80_000] if i >= 0 else html
    out, seen = [], set()
    for href in _ATT_RE.findall(region):
        if href in seen:
            continue
        seen.add(href)
        out.append(BASE + href)
    return out


def _body_of(html):
    i = html.find('id="zoom"')
    if i < 0:
        return ""
    region = html[i:i + 80_000]
    ps = [H.unescape(re.sub(r"<[^>]+>", "", p)).strip()
          for p in re.findall(r"<p[^>]*>(.*?)</p>", region, re.S)]
    body = "\n".join(p for p in ps if len(p) >= 2)
    if len(body) < 30:   # some PBOC bodies aren't in <p>; fall back to stripped text
        txt = re.sub(r"<script.*?</script>", " ", html[i:i + 80_000], flags=re.S)
        txt = H.unescape(re.sub(r"<[^>]+>", " ", txt))
        body = re.sub(r"\s{2,}", "\n", txt).strip()
    # PBOC publishes most pre-2020 documents as a PDF whose ONLY on-page trace is
    # the link's filename — and the filename is the title, so the extracted "body"
    # reads like real prose (360 of the 541 docs, measured 2026-10-08). That is the
    # worst case of CLAUDE.md's marker-table shape twice over: it counts as "already
    # stored WITH a body" so no backfill ever revisits it, and it carries none of the
    # 附件/点击/下载 markers `scripts/extract_pdf_text.py` selects on, so the PDF
    # pipeline cannot see it either. Label it so both can.
    if len(body) < 200 and "附件" not in body and _ATT_RE.search(region):
        body = "附件：" + body
    return body


def crawl(conn, fetch_bodies=True, max_pages=DEFAULT_MAX_PAGES):
    store_site(conn, SITE_KEY, CFG)
    stats = WriteRetryStats()
    stored = 0
    for section, label in SECTIONS:
        rows = _walk(section, max_pages)
        undated = sum(1 for _n, _t, d in rows if not d)
        log.info(f"[{SITE_KEY}] {label} ({section}): {len(rows)} docs listed"
                 f"{f' ({undated} with no list date)' if undated else ''}")
        pending = 0
        for nid, title, list_date in rows:
            url = f"{BASE}/{section}/{nid}/index.html"
            if conn.execute("SELECT 1 FROM documents WHERE url=? AND url != ''", (url,)).fetchone():
                continue
            date_pub = _date_for(nid, list_date)
            doc_id = next_id(conn)
            body, raw, atts = "", "", []
            if fetch_bodies:
                try:
                    art = _get(url)
                    body = _body_of(art)
                    atts = _attachments(art)
                    raw = save_raw_html(SITE_KEY, doc_id, art)
                except Exception as e:
                    log.warning(f"  body {url}: {e}")
                time.sleep(REQUEST_DELAY)
            nm = _DOCNUM_RE.search(title) or _DOCNUM_RE.search(body[:200])
            store_document(conn, SITE_KEY, {
                "id": doc_id, "title": title,
                "document_number": nm.group(1) if nm else "",
                "date_published": date_pub,
                "body_text_cn": body, "url": url,
                "attachments_json": json.dumps(atts, ensure_ascii=False),
                "classify_main_name": label, "raw_html_path": raw,
                "admin_level": "central",
            })
            stored += 1
            pending += 1
            # Commit incrementally: these rows cost network time, so don't hold the
            # write lock across hundreds of fetches (CLAUDE.md, SQLite concurrency).
            if pending >= 20:
                if commit_with_retry(conn, what=f"{SITE_KEY} {label}"):
                    pending = 0
                else:
                    stats.skipped += 1
        if pending and not commit_with_retry(conn, what=f"{SITE_KEY} {label} final"):
            stats.skipped += 1
    log.info(f"[{SITE_KEY}] done: {stored} new docs")
    if stats.skipped:
        log.error(f"[{SITE_KEY}] {stats.skipped} commit(s) failed — rows may be lost")
    return stored, stats


def main():
    ap = argparse.ArgumentParser(description="中国人民银行 (PBOC) crawler")
    ap.add_argument("--list-only", action="store_true",
                    help="store metadata only (no article fetches)")
    ap.add_argument("--probe", action="store_true",
                    help="enumerate the section lists and report; write NOTHING")
    ap.add_argument("--max-pages", type=int, default=DEFAULT_MAX_PAGES,
                    help=f"pages per section (default {DEFAULT_MAX_PAGES})")
    ap.add_argument("--db")
    args = ap.parse_args()

    if args.probe:
        total, oldest, newest = 0, "", ""
        for section, label in SECTIONS:
            rows = _walk(section, args.max_pages)
            dates = sorted(d for d in (_date_for(n, ld) for n, _t, ld in rows) if d)
            total += len(rows)
            if dates:
                oldest = min(oldest or dates[0], dates[0])
                newest = max(newest, dates[-1])
            log.info(f"[{SITE_KEY}] PROBE {label}: {len(rows)} docs, "
                     f"{dates[0] if dates else '?'} .. {dates[-1] if dates else '?'}")
        log.info(f"[{SITE_KEY}] PROBE total: {total} docs, {oldest} .. {newest}")
        return

    conn = init_db(args.db) if args.db else init_db()
    _stored, stats = crawl(conn, fetch_bodies=not args.list_only,
                           max_pages=args.max_pages)
    show_stats(conn)
    if stats.skipped:
        sys.exit(1)


if __name__ == "__main__":
    main()
