# Jiangsu second prefecture: which city reaches Suzhou depth

**Date:** 2026-10-07. **Status:** discovery only, read-only. Nothing applied.
**Question:** `fidelity-jiangsu.md` §8.7 says B1 is discharged only when a second Jiangsu
prefecture is crawled to Suzhou depth (Suzhou = 4,918 municipal + 5 district sites, ~370 docs).
Candidates probed: 无锡, 南通, 常州, 扬州, 镇江, and the districts of 无锡, 南通, 常州.

**Vantage:** the droplet (NYC). All probes ran at ≤1 req/s with `nice -n 19`, `timeout ≤300`,
byte-checked (a 200 with a <1 KB stub or a 7.7 KB WAF shell counts as not reachable).
Raw outputs: `/root/scratch_20261007/js2_*.txt` on the droplet. Probe scripts: `probe.py`,
`listprobe.py`, `depth.py`, `bodyprobe.py`, `js2_totals*.py` in the same directory.

**Answer in one line:** 无锡. Its municipal archive is static and Suzhou-sized (~4,600 rows to
the 1990s). Its five districts and two county-level cities answer a plain POST JSON API with no
cookie or browser. 南通 is WAF-closed from NYC. 常州 is JS-rendered at every tier with
attachment-only bodies. 扬州 and 镇江 do not answer.

---

## 1. City portals

| City | URL | Reachable from NYC | What came back | Verdict |
|---|---|---|---|---|
| 无锡 | `https://www.wuxi.gov.cn/` | yes | 200, 144 KB, static nav to `zfxxgk/szfxxgkml/fgwjjjd/*` | **candidate** |
| 南通 | `https://www.nantong.gov.cn/` | no | 403, 7,737 B shell `拒绝执行 \| 网站云防护系统`; same on `/ntszf/zfwj/zfwj.html` and `/robots.txt`; `http://` times out | closed (cloud WAF, IP-gated) |
| 常州 | `https://www.changzhou.gov.cn/` | yes | 200, 97 KB, static nav; every policy list is XHR | JS at every tier |
| 扬州 | `https://www.yangzhou.gov.cn/` | no | 403, 290 B | closed |
| 镇江 | `https://www.zhenjiang.gov.cn/` | no | connect timeout 25 s | closed |

Already in the corpus: `wuxi` 130 rows (2015 to 2026, 4 of them nav-noise titles such as
联系我们), page 0 of three sections only. `nantong` and `changzhou` are `city2` placeholder
entries with `sections: ["/"]` and hold no rows.

---

## 2. 无锡 municipal (`www.wuxi.gov.cn`)

Dialect: docymd (X), `/doc/YYYY/MM/DD/<id>.shtml`. Lists are server-rendered, 24 rows per page,
`index.shtml` then `index_N.shtml`. No Hanweb datacall. Dates are the URL path date and
`meta_date` agrees (`2025-12-31`, `2026-09-16`), so there is no Suzhou-style crawl-stamping.

All section roots sit under `/zfxxgk/szfxxgkml/fgwjjjd/`. Depth was measured by galloping
and bisecting `index_N.shtml` (≤15 requests per section).

| Section | Path (under `fgwjjjd/`) | Static | Pages | Est. rows | Earliest year |
|---|---|---|---|---|---|
| 市政府文件 | `zfwj/szfwj/` | yes | 21 | ~490 | 1998 |
| 市政府办公室文件 | `zfwj/szfbgswj/` | yes | 25 | ~590 | 2005 |
| 行政规范性文件 | `zfwj/gfxwj/` | yes | 14 | ~325 | 1993 |
| 政府规章 | `zfwj/zfgz/` | yes | 4 | ~85 | 1995 |
| 部门文件 (规范性) | `zfwj/bmgfxwj/` | yes | 100 (last page full; may be a CMS cap) | ~2,400 | 2015 |
| 政策解读 | `zfwj/zcjd/` | yes | 21 | ~490 | 2010 |
| 文件修改废止 | `zfwj/wjxgfz/` | yes | 3 | ~70 | 2013 |
| 现代产业政策 | `zfwj/xdcyzc/` | yes | 7 | ~160 | 2009 |
| 市委文件 | `dwwj/swwj/` | yes | 3 | ~55 | 2015 |
| 政府文件 landing | `zfwj/` | yes | 1 (74 rows, aggregate) | 0 new | 2015 |
| 地方性法规 | `dfxfg/` | no | 16 B stub | 0 | n/a |

Estimated municipal total: **~4,650 rows** (about 2,250 without 部门文件). Suzhou holds 4,918.
The 1993 to 2010 tail is real: `gfxwj/index_14.shtml` lists 12 rows from 2002 and earlier.

Body on 3 samples (repo `fetch()` + `govcms._extract_body`): 3 of 3 OK.
`doc/2025/12/31/4710967` 2,866 chars; `doc/2026/09/16/4831861` 4,144 chars;
`doc/2026/09/07/4833600` (a 市政府 doc mirrored on wnd) 2,946 chars. Both date extractors
return the path date. A pre-2005 body was not sampled.

Why the existing entry stops at 130: `govcms._pages()` picks `.shtml` pagination only when
page 0 contains a t-date link (`t\d{8}_\d+\.shtml`). 无锡 page 0 has only `/doc/YYYY/MM/DD/`
links, so `--deep` requests `index_1.html`, gets a 548 B 404, and stops. The fix is a
one-line widening of that test (or a per-site `page_ext` key) plus a per-site `max_pages`
(default 30; `bmgfxwj` needs ≥100). That is a paging fix, not a dialect.

---

## 3. 无锡 districts and county-level cities

All seven run the same intertid CMS as the city. Section roots mirror the city's
(`.../sqzfxxgkml/fgwjjjd/{qzfwj,qzfbgswj,qgfxwj|qjfggz,zcjd}/index.shtml`). The difference is
the list: `index.shtml` is an empty shell whose rows come from one POST:

```
POST /info_open/search
pageIndex=1&pageSize=20&siteId=<site>&channelIds=<chan>&searchType=1&order=writeTime
→ {"data": {"totalElements": N, "totalPages": P, "page": 1, "size": 20,
            "data": [{"title", "writeTimeString", "url": "/doc/YYYY/MM/DD/<id>.shtml", ...}]}}
```

No cookie, no referer check, no challenge. `siteId` and the channel id are literals in the
page (`getSearchList(1,20,"184","37764",1,"writeTime",...)` or `var id = "37764"`). Article
URLs are the docymd shape, so body and date reuse the city path. Totals below are
`totalElements` from the API; the earliest year is the last page's last row.

| Unit | Host | Reachable | siteId | 区政府文件 | 区政府办文件 | 规范性文件 | 政策解读 | Total | Earliest | Body |
|---|---|---|---|---|---|---|---|---|---|---|
| 梁溪区 | `www.wxlx.gov.cn` | yes (http) | 184 | 57 (chan 37764) | 82 (37765) | 9 (37767) | 61 (37770) | **209** | 2016 | OK, 468 chars |
| 锡山区 | `www.jsxishan.gov.cn` | yes (http) | 182 | 142 (36714) | 167 (36715) | 19 政务公开工作文件 (36717) | 122 (36721) | **450** | 2012 | OK, 4,305 chars (2012 doc) |
| 惠山区 | `www.huishan.gov.cn` | yes | 183 | 5 (37178) | 17 (37179) | 6 (37177) | 19 (37184) | **47** | 2011 | not sampled |
| 滨湖区 | `www.wxbh.gov.cn` | yes (http) | 174 | 22 (34086) | 30 (34087) | none listed | 31 (34092) | **83** | 2017 | OK, 995 chars |
| 新吴区 (高新区) | `www.wnd.gov.cn` | yes (http; https times out) | 181 | 5 (35404) | 30 (35405) | 672 (35407) | 388 (35410) | **1,095** | 2015 | OK, 2,946 chars |
| 无锡经开区 | `wxjkq.wuxi.gov.cn` | yes | 197 | has `fgwjjjd/` | | | | not counted | | |
| 江阴市 | `www.jiangyin.gov.cn` | yes | 4 | ~400 (20 static pages) | ~400 (20 pages) | ~40 (2 pages) | ~40 (2 pages) | **~880** | 2012 | not sampled |
| 宜兴市 | `www.yixing.gov.cn` | yes | 2 | JS | JS | 36 static (2 pages) | JS | ≥36 | 2018 | not sampled |

Notes.
- 新吴区's 672 规范性文件 and 388 解读 are mostly bureau-level and include 市政府 mirrors
  (`关于促进邮政业高质量发展的实施意见` is addressed 各市（县）、区人民政府). Expect
  `doc_identity` to mark many as mirrors.
- The wrong hostnames fail DNS from NYC (`liangxi`, `xishan`, `binhu`); the right ones come
  from the city's 市（县）区信息公开目录 page.
- 江阴 is a hybrid. `index.shtml` is the API shell (`getSearchList(1,20,4,allchildid,...)`,
  channel 19068 for 市政府文件), but `index_2.shtml` to `index_20.shtml` are static with 20
  real rows each, and `index_1.shtml` 404s. A static `--deep` walk starting at `index_2`
  recovers everything except the newest ~20 per section. Its ids live in opaque path segments
  (`szfwj_17a82c54pe6vn_15kfqfh1hwj5d`), which is fine for a literal `sections` list.
- 宜兴 uses the same API (`qx_wbj_getSearchList(1,20,2,chanIdStr,...)` in `/yxwww/js/qx_xxgk.js`)
  but the channel string is built in JS, so its ids were not read. Its static 规范性文件 list
  (2 pages) works today.

District tier estimate: **~1,880 rows** across the five districts, plus **~880** for 江阴 and a
floor of 36 for 宜兴. Suzhou's district tier is ~370 rows.

---

## 4. 常州 (for the record)

Municipal (`www.changzhou.gov.cn`). The portal is static, but every policy list is a JS
shell: 政府文件 `/gi_class/szbg?classtype=1` (53 KB, 0 article links), 文字解读
`/ns_class/zwgk_10_18` (33 KB, 0 links, `page=` selector drawn by script), 按文号
`/ns_class/wjbh?wenhao=常政发` (9 KB, `result.total / result.totalpage` filled by XHR). The
endpoint is not in the page HTML; it sits in an external script. Article pages `/gi_news/<id>`
render, but the body is a 150-char cover note (`现将...印发给你们`) with the instrument in an
attachment (`下载本信息公开文件`). Body on 3 samples: 3 of 3 extract, 148 to 155 chars each.
Suzhou-depth here means an XHR reverse-engineer plus attachment extraction.

Districts. 天宁 `www.cztn.gov.cn`, 新北 `www.cznd.gov.cn`, 武进 `www.wj.gov.cn`, 金坛
`www.jintan.gov.cn`, 溧阳 `www.liyang.gov.cn` are reachable and share a `/class/<8 letters>`
CMS; each list page is a 9 to 11 KB shell with 0 article links (武进's is 73 KB and also 0).
钟楼 `www.czzl.gov.cn` fails DNS. All JS.

## 5. 南通 (for the record)

Portal: cloud-WAF 403 shell on every path tried. Districts: 崇川 `www.chongchuan.gov.cn`,
海门 `www.haimen.gov.cn`, 如皋 `www.rugao.gov.cn`, 海安 `www.haian.gov.cn` return the identical
7,737 B shell; 通州 `www.tongzhou.gov.cn` fails the TLS handshake; 如东 `www.rudong.gov.cn` and
启东 `www.qidong.gov.cn` time out. Nothing in 南通 answers a datacenter IP. This matches the
`source-access-map.md` "anti-bot BLOCKED" bucket (成都/南通/白银/阜阳). A residential or HK
vantage (`hk-vps-runbook.md`) is the only route.

---

## 6. Recommendation

**Crawl 无锡.** It is the only candidate whose municipal archive is static, dated from the
URL, and Suzhou-sized without new dialect work. Its district tier is five times Suzhou's and
needs exactly one new list mode.

Expected rows by tier (estimates from page counts and API totals, before dedup):

| Tier | Rows | Of which new |
|---|---|---|
| Municipal 市政府 / 办公室 / 规范性 / 规章 / 解读 / 市委 (8 sections) | ~2,250 | ~2,120 |
| Municipal 部门文件 (`bmgfxwj`, bureau 规范性文件) | ~2,400 | ~2,400 |
| Districts (梁溪 / 锡山 / 惠山 / 滨湖 / 新吴) | ~1,880 | ~1,880 |
| County-level cities (江阴 static tail; 宜兴 static 规范性) | ~900 | ~900 |
| **Total** | **~7,400** | **~7,300** |

Work needed, in order of return:
1. **Paging fix in `govcms._pages()`** (not a dialect). Widen the `.shtml` test to accept
   `/doc/\d{4}/\d{2}/\d{2}/\d+\.shtml` on page 0, or honor a per-site `page_ext` key. Add a
   per-site `max_pages` (or a `--max-pages` flag; today `crawl_site(max_pages=30)` is
   hardcoded). This alone takes the municipal tier from 130 to ~4,600.
2. **One new list mode, "intertid search" (call it dialect AC).** A section entry that names
   `siteId`, `channelIds`, and the POST path; the walker pages `pageIndex` to `totalPages`
   and hands each row's `url` to the existing docymd body path. Needed for the five districts
   and for page 1 of 江阴. ~40 lines; the API has no gate.
3. Optional: 江阴 static tail (no code, just sections starting at `index_2.shtml` once step 1
   lands) and 宜兴 static 规范性文件 (no code).

Remainder that is user-gated: 南通 (WAF; needs a residential vantage), 扬州 and 镇江
(no response from NYC), 宜兴's JS lists (channel string built in JS; a browser read or a
one-time human look at the network panel resolves it), and 常州 at every tier (XHR endpoint
plus attachment bodies). None of these affects the B1 question once 无锡 is in.

Caveats. The 部门文件 count assumes 100 pages × 24; if the CMS caps the walk at 100 the real
archive is deeper, not shallower. The 2,400 bureau rows will skew `lead_issuer` toward 无锡
bureaus; `doc_identity` handles that, but a 市政府-only comparison with Suzhou should filter
on `instrument_role` or issuer. 新吴区's 1,095 includes 市政府 mirrors.

---

## 7. `govcms.SITES` entries (proposed, not applied)

Municipal. Replaces the current 3-section `wuxi` entry. The `page_ext` and `max_pages` keys
do not exist yet (step 1 above); until they do, `--deep` stops at page 0.

```python
    # 无锡市 — docymd (X) /doc/YYYY/MM/DD/<id>.shtml, static 24-row lists, index_N.shtml.
    # Probed 2026-10-07 (jiangsu-second-prefecture.md): ~4,600 rows to 1993. page_ext
    # must be .shtml (page 0 has no t-date link, so the auto-detect picks .html → 404).
    # bmgfxwj is 100 pages; the others are ≤25. dfxfg/ is a 16-byte stub; skip it.
    "wuxi": {"name": "无锡市", "base_url": "https://www.wuxi.gov.cn", "admin_level": "municipal",
        "group": "city3", "page_ext": ".shtml", "max_pages": 110,
        "sections": ["/zfxxgk/szfxxgkml/fgwjjjd/zfwj/szfwj/index.shtml",      # 市政府文件 (21p, 1998–)
                     "/zfxxgk/szfxxgkml/fgwjjjd/zfwj/szfbgswj/index.shtml",   # 市政府办公室文件 (25p, 2005–)
                     "/zfxxgk/szfxxgkml/fgwjjjd/zfwj/gfxwj/index.shtml",      # 行政规范性文件 (14p, 1993–)
                     "/zfxxgk/szfxxgkml/fgwjjjd/zfwj/zfgz/index.shtml",       # 政府规章 (4p, 1995–)
                     "/zfxxgk/szfxxgkml/fgwjjjd/zfwj/bmgfxwj/index.shtml",    # 部门文件 (100p, 2015–)
                     "/zfxxgk/szfxxgkml/fgwjjjd/zfwj/zcjd/index.shtml",       # 政策解读 (21p, 2010–)
                     "/zfxxgk/szfxxgkml/fgwjjjd/zfwj/wjxgfz/index.shtml",     # 文件修改废止 (3p)
                     "/zfxxgk/szfxxgkml/fgwjjjd/zfwj/xdcyzc/index.shtml",     # 现代产业政策 (7p, 2009–)
                     "/zfxxgk/szfxxgkml/fgwjjjd/dwwj/swwj/index.shtml"]},     # 市委文件 (3p)
```

Districts. These need the intertid search mode (step 2). The `api_search` key is the proposed
shape; the walker POSTs `/info_open/search` with `siteId`, each `channelIds`, `pageSize=20`,
`searchType=1`, `order=writeTime`, and iterates `pageIndex` to `data.totalPages`.

```python
    # 无锡 districts — intertid CMS, JS list shells backed by POST /info_open/search
    # (no cookie, no gate). Articles are docymd /doc/YYYY/MM/DD/<id>.shtml. Probed 2026-10-07.
    # http:// hosts: https times out on wnd and is unneeded elsewhere. Channel ids per section:
    # 区政府文件 / 区政府办文件 / 规范性文件 / 政策解读.
    "wxd_liangxi": {"name": "Wuxi Liangxi District (无锡梁溪区)", "base_url": "http://www.wxlx.gov.cn",
        "admin_level": "district", "group": "dept",
        "api_search": {"path": "/info_open/search", "siteId": 184,
                       "channelIds": [37764, 37765, 37767, 37770]}},               # 209 rows, 2016–
    "wxd_xishan": {"name": "Wuxi Xishan District (无锡锡山区)", "base_url": "http://www.jsxishan.gov.cn",
        "admin_level": "district", "group": "dept",
        "api_search": {"path": "/info_open/search", "siteId": 182,
                       "channelIds": [36714, 36715, 36717, 36721]}},               # 450 rows, 2012–
    "wxd_huishan": {"name": "Wuxi Huishan District (无锡惠山区)", "base_url": "https://www.huishan.gov.cn",
        "admin_level": "district", "group": "dept",
        "api_search": {"path": "/info_open/search", "siteId": 183,
                       "channelIds": [37178, 37179, 37177, 37184]}},               # 47 rows, 2011–
    "wxd_binhu": {"name": "Wuxi Binhu District (无锡滨湖区)", "base_url": "http://www.wxbh.gov.cn",
        "admin_level": "district", "group": "dept",
        "api_search": {"path": "/info_open/search", "siteId": 174,
                       "channelIds": [34086, 34087, 34092]}},                      # 83 rows, 2017–
    "wxd_xinwu": {"name": "Wuxi Xinwu District / High-tech Zone (无锡新吴区)", "base_url": "http://www.wnd.gov.cn",
        "admin_level": "district", "group": "dept",
        "api_search": {"path": "/info_open/search", "siteId": 181,
                       "channelIds": [35404, 35405, 35407, 35410]}},               # 1,095 rows, 2015–
    # 江阴市 — same CMS. Page 1 is the API shell (siteId 4; 市政府文件 channel 19068, 办公室
    # 19082, 规范性 19067, 解读 19100); index_2..index_20.shtml are STATIC 20-row pages and
    # index_1.shtml 404s. Static walk from index_2 misses only the newest ~20 per section.
    "wxd_jiangyin": {"name": "Jiangyin (无锡江阴市)", "base_url": "https://www.jiangyin.gov.cn",
        "admin_level": "district", "group": "dept", "page_ext": ".shtml", "max_pages": 25,
        "sections": ["/xxgk/zfxxgkml_17a82c54pe6vn_arjk73731zj4/fgwjjjd_17a82c54pe6vn_1sasuptbh4wxw/szfwj_17a82c54pe6vn_15kfqfh1hwj5d/index_2.shtml",
                     "/xxgk/zfxxgkml_17a82c54pe6vn_arjk73731zj4/fgwjjjd_17a82c54pe6vn_1sasuptbh4wxw/szfbgswj_17a82c54pe6vn_1febak8zsqyd0/index_2.shtml",
                     "/xxgk/zfxxgkml_17a82c54pe6vn_arjk73731zj4/fgwjjjd_17a82c54pe6vn_1sasuptbh4wxw/zfgfxwj_17a82c54pe6vn_1e49jf7z1bvda/index_2.shtml",
                     "/xxgk/zfxxgkml_17a82c54pe6vn_arjk73731zj4/fgwjjjd_17a82c54pe6vn_1sasuptbh4wxw/zcjd_17a82c54pe6vn_1dt3k1x3yugp3/index_2.shtml"]},
    # 宜兴市 — only 规范性文件 is static (2 pages); 市政府文件/办公室/解读 are the same API
    # with the channel string built in JS (not read). Static part only.
    "wxd_yixing": {"name": "Yixing (无锡宜兴市)", "base_url": "https://www.yixing.gov.cn",
        "admin_level": "district", "group": "dept", "page_ext": ".shtml",
        "sections": ["/zgyx/zfxxgk/szfxxgkml/fgwjjjd/gfxwj/index.shtml"]},       # 36 rows, 2018–
```

Note on `index_2.shtml` as a section root: `_pages()` Scheme B appends `index_N` to the
section directory starting at N=1, so a root of `.../index_2.shtml` needs the walker to start
from the given page number (or list the pages explicitly). Confirm before relying on it.

---

## 8. Crawl sequence for a writer agent (after the nightly lock clears)

All on the droplet, in a separate DB, then merged. `--deep` is required for the municipal tier.

```bash
cd /root/china-governance && ls /tmp/china-governance-daily-sync.lock.d 2>/dev/null && echo "LOCKED, wait"

# 0. Code first (Mac): widen the .shtml paging test / add page_ext + max_pages, add the
#    intertid search mode, apply the SITES entries above, run tests, commit, push, then
#    `git pull` on the droplet (tree must be clean; verify HEAD moved).

# 1. Sanity, no writes:
python3 -m crawlers.govcms --site wuxi --discover
python3 -m crawlers.govcms --site wuxi --list-only --deep --db /root/scratch_20261007/js2_probe.db

# 2. Municipal, separate DB (~4,600 bodies at 1 req/s ≈ 1.5 h):
nohup python3 -m crawlers.govcms --site wuxi --deep --db documents_wuxi.db > logs/wuxi_$(date +%Y%m%d).log 2>&1 &

# 3. Districts + county cities, same DB, after step 2 finishes:
for s in wxd_liangxi wxd_xishan wxd_huishan wxd_binhu wxd_xinwu wxd_jiangyin wxd_yixing; do
  python3 -m crawlers.govcms --site $s --deep --db documents_wuxi.db
done

# 4. Merge, then the nightly handles bodies, scores, identity, citations, search index:
python3 scripts/merge_db.py documents_wuxi.db
python3 scripts/validate_cascades.py        # after the next nightly; JS 82d check is Suzhou-dependent

# 5. Re-run the Jiangsu replication (fidelity-jiangsu.md §4.3 size-predicts-relay) with
#    site_key IN ('suzhou','wuxi') and the wxd_/szd_ district tiers.
```

If the nightly's `--group city3 --deep --workers 4` picks up the new `wuxi` entry before the
merge, that is also fine; the entries are idempotent on `url`.

---

## 9. Honesty

- Row counts are page counts × rows per page for static sections and `totalElements` for the
  API. Neither was deduplicated against the 130 rows already stored or across mirrors.
- 部门文件 last page was found at exactly 100 with a full 24 rows. The CMS may cap the walk; the
  archive could be deeper.
- Bodies were sampled on 2 municipal and 4 district articles, all 2012 or later. The 1993 to
  2005 tail was listed, not fetched.
- 惠山, 江阴, 宜兴 bodies were not sampled. They share the CMS and the `/doc/` shape with the
  sampled sites.
- 宜兴's API channel ids and 经开区's totals were not read. Both are small.
- The previous agent's probe job (`pgrep -af scratch_20261007`, a 南通 district probe) may
  still have been running during this pass; its output was not used. None of this pass's
  probes were left running.
