# Verified Coverage Gaps — Investigation & Proposed Fixes

**Date:** 2026-09-14 · **Author:** investigation pass (read-only) · **Scope:** 3 confirmed gaps.
**Vantages tested:** droplet NYC IP (`104.236.88.45`) and Mac residential — noted per gap.
**This is a diagnosis doc only.** No crawler/script/web code was edited. Patches below are
sketches for a human to apply. All DB numbers read live from the droplet `documents.db`.

---

## Gap 1 — GD provincial dept subdomains have ~0% body text (3,640 docs)

Site keys: `gdedu gdjt gdcom gdct gdee gdmz gdstc gdczt gdnr gdzjst gdii gdny`
(configured in `crawlers/gkmlpt.py` `SITES`, `admin_level='provincial'`, base_urls like
`https://gdee.gd.gov.cn`, `https://edu.gd.gov.cn`, `https://gdstc.gd.gov.cn`, …).

### Diagnosis (what I observed)

- Body coverage per site is essentially zero: `gdee` 1/300, `gdct` 3/300, `gdii` 1/296,
  the other nine **0** each. Total **34 / 3,640** rows have any `body_text_cn`.
- Raw-HTML coverage is also ~0: only **34 / 3,640** rows have a non-empty `raw_html_path`
  (e.g. `raw_html/gdee/` holds just 3 files). So for 99% of these docs the article page
  was **never fetched or saved** — the row is a list-only record (title + URL from the
  `search.gd.gov.cn` / category API).
- Stored URLs are standard gkmlpt content pages, e.g.
  `https://gdee.gd.gov.cn/gkmlpt/content/4/4923/post_4923279.html`.
- **Reachability (both vantages):** the article page returns **HTTP 200, ~41 KB of real
  HTML** from the droplet **and** from the Mac. This is **not** an IP/WAF block — the
  pages are fully fetchable from the NYC droplet.
- I pulled one live page and inspected the template: the body is **not** in the
  `_CONFIG.DETAIL.content` JSON blob that `extract_body_text()` keys on (that regex
  matches **nothing** here). The visible body lives in a server-rendered
  `<div class="article-content">…</div>` block (validated extract = 816 chars of clean
  text; a `发布日期：2026-07-10` date is present in the page).

### Root cause

Two compounding issues, both in `crawlers/gkmlpt.py`:

1. **`extract_body_text()` has no container for the GD-dept template.** It handles only
   (a) the `"content":"…"` JSON blob (standard gkmlpt city sites), (b) Nanshan
   `tyxxy_main`, (c) Shenzhen `news_cont_d_wrap`. The `gd.gov.cn` provincial-dept
   subdomains use a different CMS whose body is `<div class="article-content">`, so
   extraction returns `""` even when the page is fetched.
2. **Bodies were never backfilled for these sites.** Because 99% of rows have empty
   `raw_html_path`, the article pages weren't fetched at ingest — these look like rows
   added from the listing API without the per-doc body fetch (`fetch_document_body`)
   ever running. So even after fixing (1), a re-fetch pass is required.

### Proposed fix

**(a) Add the GD-dept container to `extract_body_text()`** (insert before the final
`return ""`):

```python
    # Fallback: Guangdong provincial-dept subdomains (gdee/gdedu/gdstc/gdii/…
    # *.gd.gov.cn). Server-rendered template — body in <div class="article-content">,
    # NO _CONFIG.DETAIL.content JSON blob.
    m = re.search(
        r'<div\s+class="article-content"[^>]*>(.*?)</div>\s*'
        r'<div\s+class="(?:tab__slot|footer-warp|jiucuo)',
        html, re.DOTALL)
    if not m:
        m = re.search(r'<div\s+class="article-content"[^>]*>(.*?)</div>\s*</div>',
                      html, re.DOTALL)
    if m:
        text = re.sub(r"<[^>]+>", " ", m.group(1))
        text = re.sub(r"\s+", " ", text).strip()
        if len(text) > 20:
            return text
```

**(b) Re-fetch bodies** — the gkmlpt `--backfill-bodies` path already targets
`body_text_cn=''` rows whose URL contains `/gkmlpt/content/…post_` (which these do) and
calls `extract_body_text` + saves raw HTML:

```bash
# on the droplet, after applying patch (a):
python3 -m crawlers.gkmlpt --backfill-bodies      # covers all body-less gkmlpt-URL docs
```

(If `--backfill-bodies` isn't site-scopable and you want to bound it, run it and it will
pick up the 3,606 dept rows plus any other body-less gkmlpt rows; pages are reachable
from the droplet so no residential vantage is needed.)

### Effort

**RE-CRAWL (re-fetch).** Not a pure re-extract — raw HTML was not saved for 99% of rows,
so the fix is: 1-line-family container patch + a `--backfill-bodies` pass that fetches
~3,606 article pages from the droplet (~1–2 h at the crawler's delay). No proxy needed.

---

## Gap 2 — ipc_court (SPC IP Tribunal) is 99% body-less, 0% dated (389 docs)

`crawlers/ipc_court.py`, site `ipc.court.gov.cn`.

### Diagnosis

- Coverage: **389 docs, 2 with body, 0 with `date_published`.**
- **All 389 rows have `raw_html_path` set** and the files exist and are real
  (e.g. `raw_html/ipc_court/900134172.html` = 40 KB). Vantage is irrelevant here — the
  fix reads saved HTML, no network.
- The two target docs are already present with saved raw HTML, bodies empty:
  - `view-6033.html` → id `900134172`, 《…关于依法审理涉人工智能纠纷案件的意见》
  - `view-6039.html` → id `900134176`, its 理解与适用.
- Inspecting the saved HTML, the real structure is:
  ```
  <div class="detail">
    <h2>TITLE</h2>
    <div class="message">
      <span>发布时间：2026-09-08 09:35:01</span>
      <span>来源：最高人民法院新闻局</span>
    </div>
    <div class="detail_video">…</div>
    <div class="detail_image">…</div>
    <div class="txt"> …ARTICLE BODY… </div>
  </div>
  ```

### Root cause

`_extract_article()` looks for the body in `<article>` or `class="article"`, and for the
date near `class="article"`. **Neither exists** in this template — the body is
`<div class="txt">` inside `<div class="detail">`, and the date/source are in
`<div class="message">` as `发布时间：` / `来源：`. So body extraction falls through to
`""` and no date is ever found.

### Proposed fix (patch sketch for `crawlers/ipc_court.py::_extract_article`)

```python
    # Date + source live in <div class="message"> (发布时间：/来源：)
    m = re.search(r'发布时间[：:]\s*(\d{4}-\d{2}-\d{2})', html)
    if m:
        meta["date_published"] = m.group(1)
    m = re.search(r'来源[：:]\s*([^<\s]+)', html)
    if m:
        meta["source"] = m.group(1).strip()

    # Body: <div class="txt"> inside <div class="detail">; fall back to the
    # whole <div class="detail"> block if the txt div isn't found.
    body = ""
    for pattern in [r'<div class="txt">(.*?)</div>\s*</div>',
                    r'<div class="detail">(.*?)</div>\s*</div>\s*</div>']:
        m = re.search(pattern, html, re.DOTALL)
        if m:
            content = m.group(1)
            content = re.sub(r"<br\s*/?\s*>", "\n", content)
            content = re.sub(r"</p>|</div>", "\n", content)
            content = re.sub(r"<[^>]+>", "", content)
            text = re.sub(r"[ \t]+", " ", content)
            text = re.sub(r"\n\s*\n+", "\n", text)
            text = (text.replace("&nbsp;", " ").replace("　", " ")
                        .replace("&amp;", "&").strip())
            if len(text) > 50:
                body = text
                break
    meta["body_text_cn"] = body
```

**Validated** against the two saved files: 900134172 → date `2026-09-08`, src
`最高人民法院新闻局`, body **10,445 chars**; 12723225 → date `2018-12-14`, src
`最高人民法院知识产权法庭`, body 267 chars. (Caveat: `<div class="txt">…</div></div>`
can truncate on documents whose body contains nested `<div>`s; the `detail`-block
fallback catches those, but spot-check a handful after the run.)

Because all 389 rows already have `raw_html_path`, the cheapest application is a
**re-extract over saved HTML** (read each `raw_html_path`, run the new
`_extract_article`, `UPDATE body_text_cn/date_published/date_written`) rather than a
re-crawl. Re-running the crawler also works (it re-fetches body-less rows) but is slower
and hits the live site. A tiny re-extract loop (pattern already used by
`scripts/backfill_from_html.py`) is preferable.

### Effort

**RE-EXTRACT** (no network; 389/389 raw HTML saved). ~seconds. Optionally also fix the
`crawl()` date-write path so future crawls store the date (`_parse_date` already exists;
just feed it `meta["date_published"]`).

---

## Gap 3 — 中国网信 (CAC magazine) signed essays

Target example: 《全面筑牢人工智能安全屏障 推动人工智能健康有序发展》 (a 署名文章, authored by
陈一新, 国家安全部部长).

### Diagnosis

- **Not in the corpus.** No cac.gov.cn row matches the essay title (the one
  `title LIKE '%中国网信%'` hit is a magazine-promo notice, not the essay).
- **The magazine's electronic edition is a WeChat mini-program, not a web page.** The
  cac.gov.cn announcement page (`/2024-01/24/c_1707761934036060.htm`) only tells readers
  to scan a QR code / open the "中国网信" WeChat mini-program to read issues, 本期目录 and
  署名文章. There is **no browsable web index of the magazine's articles** on cac.gov.cn.
- **CAC is already crawled** by a bespoke crawler `crawlers/cac.py` (NOT govcms). It uses
  the `/cms/JsonList` POST API keyed by `channelCode`, and article URLs are the standard
  CAC/news.cn dialect `/{YYYY-MM}/{DD}/c_<id>.htm` — **not** a govcms `t-date` / `/art/`
  / `content_N` shape. So the premise "add a govcms SITES entry" does not apply; a govcms
  dialect is neither needed nor a fit here.
- The open-web home of the 网信政务 channels is `/wxzw/A0937index_1.htm` (200, 40 KB from
  the droplet). Sub-channels and their codes (all droplet-reachable, HTTP 200):
  - `wxfb` 网信发布 `A093702` `/wxzw/wxfb/A093702index_1.htm` — **already crawled**
  - `zcfg` 政策法规 `A093703` — already crawled
  - `wxzf` 网信执法 `A093704` — already crawled
  - `bgfb` 报告发布 `A093706` — already crawled
  - `gdgz` 高端观察 `A093709` `/wxzw/gdgz/A093709index_1.htm` — **NOT crawled**
  - `dfwx` 地方网信 `A093710` `/wxzw/dfwx/A093710index_1.htm` — **NOT crawled**
- I checked `gdgz` (高端观察, the likeliest home for leader/theory pieces): reachable, but
  its listing is mixed news (WIC press conferences, foundation meetings, the magazine
  subscription promo) — **not** a clean 署名文章 stream. The specific 陈一新 essay does not
  appear on cac.gov.cn's crawlable web at all; it surfaces only on third-party mirrors
  (gm7.org, secrss.com's "中国网信杂志" author feed).

### Root cause

The 中国网信 magazine proper is **mini-program-gated (Tier E)** — its full 署名文章 corpus
is not published as browsable web articles on cac.gov.cn. What *does* reach the open web
is captured under the `/wxzw/` channels, most of which the existing `cac` crawler already
ingests; the gap for signed/observation essays is that the `gdgz` (高端观察) and `dfwx`
channels aren't in `cac.py`'s `SECTIONS`, and even those don't fully mirror the magazine.

### Proposed fix

This is **not** a govcms job. Two independent actions:

**(a) Cheap, in-pipeline — widen the existing `cac` crawler** to the un-crawled open-web
channels (adds observation/regional essays; will *not* capture WeChat-exclusive pieces).
Add to `crawlers/cac.py` `SECTIONS`:

```python
    "gdgz": {
        "name": "高端观察",
        "channel_code": "A093709",
        "listing_path": "/wxzw/gdgz/A093709index_1.htm",
    },
    "dfwx": {                      # optional — regional, news-heavy
        "name": "地方网信",
        "channel_code": "A093710",
        "listing_path": "/wxzw/dfwx/A093710index_1.htm",
    },
```

No new dialect: article URLs are the CAC `/YYYY-MM/DD/c_<id>.htm` pattern the crawler
already parses; the `/cms/JsonList` API just needs the new `channelCode`s.

**(b) The magazine itself is a NEW SOURCE, Tier E.** To get the WeChat-exclusive
署名文章 (e.g. the 陈一新 AI-security essay) there is no regex-crawlable path. Options,
in rough order of effort: ingest from a mirror that republishes the magazine
(`secrss.com/articles?author=中国网信杂志` carries the 署名文章 feed), or a bespoke
WeChat-mini-program capture. Classify as **Tier E / mini-program-gated**; out of scope
for the govcms/t-date approach. Recommend logging it in `source-access-map.md` under
Tier E alongside 福建政策文件库.

### Effort

- (a) **Config add** to an existing crawler (`cac.py`) — trivial, in-pipeline, no new
  dialect. Captures open-web observation essays only.
- (b) **New source** (mini-program mirror ingestion) for the magazine's exclusive
  署名文章 — a separate, heavier project; the specific target essay is only obtainable
  this way (or via a third-party mirror), since it is not on cac.gov.cn's crawlable web.
```

