# govcms configs — 4 high-value Tier-B sources

Investigated 2026-09-04 from the droplet's NYC IP (`104.236.88.45`).
Source list: `docs/working/source-access-map.md` Tier B (Qinghai, Yunnan, Xinjiang, NEAC).

**All fetches were done from the droplet** (`ssh root@104.236.88.45 'curl -sL -A "Mozilla/5.0 ..." ...'`)
so reachability reflects the real crawl vantage, not a residential IP.

## TL;DR

| Source | Verdict | Dialect | Notes |
|---|---|---|---|
| 青海 Qinghai | ✅ crawlable | **NEW dialect (U) `qhsys`** | **HTTP only** — HTTPS is blackholed from the droplet |
| 云南 Yunnan | ⛔ **NOT crawlable** | — | Every `/zwgk/*` policy section is a **403 WAF shell**; belongs in Tier C (proxy-gated) |
| 新疆 Xinjiang | ✅ crawlable | (I) hexmon — **already in SITES** | Config exists but is mis-tagged `group="residential"`; now droplet-reachable → **untag it** |
| 民委 NEAC | ✅ crawlable | **NEW dialect (V) `cmon`** | central; TRS-WCM `/c<col>/<YYYYMM>/<num>.shtml` |

Two sites need **new URL dialects** added to `govcms.py` (specs below); one reuses an
existing dialect; one (Yunnan) cannot be crawled from the droplet at all.

---

## 1. 青海 Qinghai — ✅ crawlable (HTTP only), needs NEW dialect (U)

**Reachability:** `https://www.qinghai.gov.cn` is **blackholed** from the droplet
(`code=000`, 25 s timeout, all retries). `http://www.qinghai.gov.cn` returns **162 KB
real content** (`code=200`). So the base_url MUST be `http://` — `base.fetch()` then uses
the plain-HTTP path (`contexts=[None]`) and succeeds.

**Article-URL pattern (NEW):** `/zwgk/system/YYYY/MM/DD/<numeric-id>.shtml`
- e.g. `http://www.qinghai.gov.cn/zwgk/system/2026/09/04/030107864.shtml`
- Slash-separated, zero-padded date dirs + a **numeric** filename. This matches **no
  existing dialect**: R `schex` is `/YYYY/M/D/<32-hex>.shtml` (hex file, not numeric),
  Q `ymd8` is `/YYYYMMDD/<num>.html` (no slashes), O `datepath` uses dashes. → new dialect.

**Policy sections (reachable):** The dedicated 政策文件 tree `/xxgk/zcwj/` is **412 WAF-blocked**
(that whole `/xxgk/` subtree is fenced from the droplet). The reachable policy listings all
live under `/zwgk/` and every one yields `/zwgk/system/...` article links:
- `/zwgk/xwdt/tzgg/` — 通知公告 (official notices/announcements) — **primary policy section**
- `/zwgk/xwdt/qhyw/` — 青海要闻 (provincial gov news; secondary, mixed value)

(`/zwgk/zfgz/` 政府公报 is reachable but links out to a login-gated gazette host
`111.44.251.130` — not crawlable, excluded.)

**Config block:**
```python
    "qinghai": {
        # 青海省 — NEW dialect (U) qhsys: /zwgk/system/YYYY/MM/DD/<numeric-id>.shtml.
        # HTTP ONLY: https://www.qinghai.gov.cn is blackholed from the droplet's
        # datacenter IP (code 000); http:// returns 162 KB real content. The dedicated
        # 政策文件 tree /xxgk/zcwj/ is 412 WAF-fenced — the reachable policy listings are
        # the /zwgk/xwdt/ sections (tzgg 通知公告 = real 省政府/人大/政协 docs; qhyw 要闻).
        "name": "Qinghai (青海省)",
        "base_url": "http://www.qinghai.gov.cn", "admin_level": "provincial",
        "sections": ["/zwgk/xwdt/tzgg/", "/zwgk/xwdt/qhyw/"],
    },
```

**NEW dialect to add to `govcms.py`** (regex block near the other `_ART_*_RE`, and the
matching loop in `_list_articles`):
```python
#  (U) qhsys: …/system/YYYY/MM/DD/<numeric-id>.shtml  (青海省). Slash-separated,
#      zero-padded date dirs + a NUMERIC filename. Distinct from R schex (32-hex file),
#      Q ymd8 (no slashes) and O datepath (dashes). Anchored on /system/ so the loose
#      /YYYY/MM/DD/ can't false-match other sites' date paths.
_ART_QHSYS_RE = re.compile(
    r'<a\s+[^>]*href="([^"]*?/system/(\d{4})/(\d{2})/(\d{2})/\d+\.s?html?)"[^>]*>(.*?)</a>', re.S)
```
```python
    for m in _ART_QHSYS_RE.finditer(page_html):        # (U) qhsys: full date in path
        y, mo, d = m.group(2), m.group(3), m.group(4)
        matches.append((m, m.group(1), m.group(5), f"{y}-{mo}-{d}"))
```

**Validation (real article URLs + titles, from `/zwgk/xwdt/tzgg/index.html`, 75 KB):**
- `…/zwgk/system/2026/09/04/030107880.shtml` — 2026-09-04
- `…/zwgk/system/2026/07/11/030103544.shtml` — 2026-07-11
- `…/zwgk/system/2026/06/18/030102048.shtml` — 2026-06-18
- Titles (real provincial docs): 「青海省国防动员办公室关于试鸣防空警报的公告」,
  「青海省人大常委会关于对全省残疾人权益保障情况开展专题询问征集问题建议的公告（第12号）」,
  「中国人民政治协商会议第十三届青海省委员会常务委员会…决定」.

---

## 2. 云南 Yunnan — ⛔ NOT crawlable from the droplet (FLAG)

**Do not build a govcms config.** The source-access-map's "301 → 146 KB real" is a
**false positive** from the droplet vantage:
- `http://www.yn.gov.cn/` → 301 → `https://www.yn.gov.cn/` → the root path returns **404**
  (2.6 KB) and `/index.html` returns **403** (2.6 KB).
- **Every** policy section — `/zwgk/`, `/zwgk/zfxxgk/`, `/zfxxgk/`, `/zwgk/zcwj/`,
  `/zwgk/zcfg/`, `/ywdt/` — returns a styled **`403 Forbidden` WAF shell** (~2.63 KB),
  **even with full browser headers** (Accept / Accept-Language / Chrome UA). Server is
  `openresty` fronted by a CDN (`X-CCDN-REQ-ID`).

This is a datacenter-IP WAF geo-block. Yunnan belongs in **Tier C (proxy-gated)**, not
Tier B — recommend moving it in `source-access-map.md`. It is reachable only from a
residential-CN IP / browser vantage.

---

## 3. 新疆 Xinjiang — ✅ crawlable now; existing config just needs UN-tagging

**Reachability:** `https://www.xinjiang.gov.cn` returns **200 / 108 KB** from the droplet.
Both listing sections and article bodies fetch fine (article = 200 / 38 KB).

**Dialect:** (I) **hexmon** — article URLs are `/xinjiang/zfl/<YYYYMM>/<32-hex>.shtml`,
exactly the hexmon shape (`/<YYYYMM>/<32-hex>.shtml`). No new dialect needed.

**Important:** a `xinjiang` key **already exists in `SITES`** (govcms.py ~line 348) with the
correct sections and dialect, but it is tagged `group="residential"` (i.e. excluded from the
droplet nightly because it was assumed datacenter-blocked). It is **now droplet-reachable**,
so this is an **UPDATE, not a new key** — **drop the `group` tag** so it joins the nightly
`govcms` loop. (Do not add a second `xinjiang` key — that would collide.)

**Updated config block (remove `group="residential"`):**
```python
    "xinjiang": {  # 新疆 — hexmon dialect I (/xinjiang/zfl/<YYYYMM>/<32hex>.shtml).
        # Droplet-reachable as of 2026-09-04 (200/108 KB) → un-tagged from 'residential'
        # so it runs in the nightly govcms pass.
        "name": "Xinjiang (新疆维吾尔自治区)", "base_url": "https://www.xinjiang.gov.cn",
        "admin_level": "provincial",
        "sections": ["/xinjiang/zfl/zfxxgk_zhengce_list.shtml", "/xinjiang/zwgk/zw.shtml"],
    },
```

**Validation (real article URLs + titles, from `/xinjiang/zfl/zfxxgk_zhengce_list.shtml`, 40 KB):**
- `/xinjiang/zfl/202606/9c5d642833b447478986583672bbe2a7.shtml` — 2026-06
- `/xinjiang/zfl/202602/cfd7acf232d14b6eacb393719ee5c155.shtml` — 2026-02
- `/xinjiang/zfl/202512/ed82898b605b4906a7d753b25f1f6ffd.shtml` — 2025-12
- Titles (real 政府规章/规范性文件): 「新疆维吾尔自治区建设工程造价管理办法」,
  「新疆维吾尔自治区人民政府关于调整实施一批自治区级行政职权事项的决定」,
  「新疆维吾尔自治区行政裁量权基准制定和管理办法」.

---

## 4. 民委 NEAC (国家民委, State Ethnic Affairs Commission) — ✅ crawlable, needs NEW dialect (V)

**Reachability:** `https://www.neac.gov.cn` returns **200 / 171 KB**. All three policy
sections return 200 (~37 KB each); a sample article body = 200 / 139 KB.

**Article-URL pattern (NEW):** `/seac/c<col>/<YYYYMM>/<numeric-id>.shtml`
- e.g. `/seac/c103593/202601/1185934.shtml`
- Classic TRS-WCM layout: column dir `c<digits>` + `YYYYMM` month dir + a **numeric**
  filename. Matches **no existing dialect**: I `hexmon` needs a 32-hex filename (this is
  numeric); K `ccontent` is a literal `content.html`. → new dialect.
- List rows carry an explicit `YYYY-MM-DD` date (e.g. `2026-03-13`), so `_DATE_NEAR`
  overrides the coarse `YYYYMM-01` derived from the path.

**Policy sections (all 200, all yield the `cmon` article links):**
- `/seac/xxgk/zcfb/index.shtml` — 政策发布 (policy issuance) — **primary**
- `/seac/xxgk/zcjd/index.shtml` — 政策解读 (policy interpretation)
- `/seac/xxgk/tzgg/index.shtml` — 通知公告 (notices)

**Config block:**
```python
    "neac": {
        # 国家民委 (State Ethnic Affairs Commission) — NEW dialect (V) cmon:
        # /seac/c<col>/<YYYYMM>/<numeric-id>.shtml (TRS-WCM). 政策发布 + 政策解读 + 通知公告.
        # List rows carry YYYY-MM-DD → _DATE_NEAR wins over the path's YYYYMM-01.
        "name": "State Ethnic Affairs Commission (国家民委)",
        "base_url": "https://www.neac.gov.cn", "admin_level": "central",
        "sections": ["/seac/xxgk/zcfb/index.shtml", "/seac/xxgk/zcjd/index.shtml",
                     "/seac/xxgk/tzgg/index.shtml"],
    },
```

**NEW dialect to add to `govcms.py`:**
```python
#  (V) cmon: …/c<col>/<YYYYMM>/<numeric-id>.shtml  (国家民委 NEAC, TRS-WCM). Column dir
#      c<digits> + YYYYMM month dir + NUMERIC filename. Distinct from I hexmon (32-hex
#      file) and K ccontent (literal content.html). Date = YYYYMM → -01, but list rows
#      carry YYYY-MM-DD so _DATE_NEAR overrides. Add AFTER the existing dialects so those
#      win the de-dupe (spb/hexmon uses /cNNN/cNNN/YYYYMM/<32hex> — 32-hex file, no clash).
_ART_CMON_RE = re.compile(
    r'<a\s+[^>]*href="([^"]*?/c\d+/(\d{4})(\d{2})/\d+\.s?html?)"[^>]*>(.*?)</a>', re.S)
```
```python
    for m in _ART_CMON_RE.finditer(page_html):         # (V) cmon: YYYYMM dir → -01, row date wins
        ym4, mo = m.group(2), m.group(3)
        date_str = f"{ym4}-{mo}-01" if 1 <= int(mo) <= 12 else ""
        matches.append((m, m.group(1), m.group(4), date_str))
```

**Collision note:** `/c\d+/\d{6}/\d+\.shtml` is broad. Reviewed against crawled sites:
chinapeace uses `/cNNN/…/content_ID.shtml` (dialect C, `content_`/dashes), cnipa/ncha use
`/art/`, spb uses hexmon (`/cNNN/cNNN/YYYYMM/<32-hex>.shtml`, hex file). None collide with a
`/c<col>/<YYYYMM>/<numeric>.shtml`. Adding (V) after the existing loops keeps the de-dupe safe.

**Validation (real article URLs + titles, from `/seac/xxgk/zcfb/index.shtml`, 37 KB):**
- `/seac/c103593/202601/1185934.shtml` — row date 2026-01-08 — 「国家民委关于印发《全国民族团结进步示范区示范单位创建命名管理办法》的通知」
- `/seac/c103280/202503/1179105.shtml` — 「国家民委关于修改《国家民委科研项目管理办法》的决定」
- `/seac/c103593/202404/1172232.shtml` — 「国家民委关于废止部分规范性文件的通知」

---

## Merge checklist for the maintainer

1. **Add 2 new dialects** to `crawlers/govcms.py`: (U) `qhsys` (Qinghai) and (V) `cmon`
   (NEAC) — regex block + the `_list_articles` loop entry for each (specs above).
2. **Add 2 new SITES keys:** `qinghai` (HTTP base_url!) and `neac` (central).
3. **Update the existing `xinjiang` key:** remove `"group": "residential"` so it joins the
   nightly droplet loop (do NOT add a duplicate key).
4. **Skip Yunnan** — not crawlable from the droplet; move it to Tier C in the access map.
