# AI Policy Vertical: What to Crawl from Central to Local

*Conducted 2026-02-22. Maps every layer of government needed to trace AI policy from State Council to district level, with crawlability assessment for each.*

## The Full Chain

```
Central (国家级)     ← NEW: need to crawl
  State Council (国务院)         — gov.cn
  MIIT (工信部)                  — miit.gov.cn
  MOST (科技部)                  — most.gov.cn
  CAC/网信办                     — cac.gov.cn
  NDRC (发改委)                  — ndrc.gov.cn

Provincial (省级)    ← NEW: confirmed gkmlpt, zero code changes
  Guangdong Province (广东省)    — www.gd.gov.cn (SID: 2)

Municipal (市级)     ← DONE
  Shenzhen (深圳)               — 20 sites, 45,130 docs
  Guangzhou (广州)               — www.gz.gov.cn (SID: 200001), ready to crawl

District (区级)      ← DONE
  Pingshan, Longhua, Guangming, etc. — already in corpus
```

**The gap is the top layer.** Provincial and below are all gkmlpt — free expansion. Central government is five different platforms, each requiring its own crawler.

---

## Central Government Sites: Crawlability Assessment

### 1. NDRC (发改委) — EASIEST

| | |
|---|---|
| **URL** | `https://www.ndrc.gov.cn` |
| **CMS** | Static HTML + JS modules |
| **AI relevance** | Industrial policy, investment guidance funds, "new infrastructure" directives |
| **Difficulty** | Easy-moderate |

**How to crawl:**
- Policy listings at `/xxgk/zcfb/tz/index.html` through `index_19.html` (20 pages)
- Total pages revealed by `createPageHTML(N, 0, "index", "html")` in inline `<script>`
- Document URLs: `./YYYYMM/tYYYYMMDD_NNNNNNN.html` — predictable, static HTML
- No User-Agent blocking. WAF present but doesn't interfere.
- Also has 解读 (interpretations) linked alongside policies

**Key sections for AI:**
- `/xxgk/zcfb/tz/` — Notices (通知)
- `/xxgk/zcfb/` — Policy documents main listing
- `/fzggw/jgsj/` — Department listings (find high-tech / digital economy department)

### 2. State Council (国务院) — MODERATE-EASY

| | |
|---|---|
| **URL** | `https://www.gov.cn` |
| **CMS** | TRS CMS (static HTML, server-generated) |
| **AI relevance** | Top-level directives, "State Council opinions" that all lower levels must implement |
| **Difficulty** | Moderate-easy |

**How to crawl:**
- `/zhengce/` has direct `<a href>` links to policy pages
- Policy URL pattern: `/zhengce/content/YYYYMM/content_NNNNNNN.htm`
- Has sitemaps at `/baidu.xml`, `/google.xml` (though may be stale)
- Has a Vue.js policy library SPA at `sousuo.www.gov.cn/zcwjk/policyDocumentLibrary` — harder to access directly but not needed for basic crawling
- No User-Agent blocking. Permissive robots.txt.

**Key sections for AI:**
- `/zhengce/` — All policies
- `/zhengce/xxgk/gjgzk/` — National work library (国家工作库)

### 3. MOST (科技部) — MODERATE

| | |
|---|---|
| **URL** | `https://www.most.gov.cn` |
| **CMS** | Custom static site generator |
| **AI relevance** | Science and technology plans, AI research funding, national labs, tech ethics |
| **Difficulty** | Moderate |

**How to crawl:**
- Information disclosure at `/xxgk/xinxifenlei/fdzdgknr/`
- Category-based sidebar navigation, crawl each section
- Document URLs: `./fgzc/TYPE/TYPEYYYY/YYYYMM/tYYYYMMDD_NNNNNN.html`
- Pagination via JS widget — config in inline script: `pagination_script_config = { pageNumber: '0', total: '1' }`
- No User-Agent blocking. No robots.txt (allow all).

**Key sections for AI:**
- `/xxgk/xinxifenlei/fdzdgknr/fgzc/gfxwj/` — Normative documents (规范性文件)
- `/xxgk/xinxifenlei/fdzdgknr/fgzc/bmgz/` — Department regulations (部门规章)

### 4. CAC/网信办 — MODERATE-HARD

| | |
|---|---|
| **URL** | `https://www.cac.gov.cn` |
| **CMS** | Legacy Java CMS (JSP-based search) |
| **AI relevance** | AI governance regulations, algorithm recommendations, deepfake rules, data security |
| **Difficulty** | Moderate-hard |

**How to crawl:**
- Sections use coded index pages: `wxzw/zcfg/A093703index_1.htm` (政策法规)
- URL codes (`A0937XX`) not predictable — must discover by crawling navigation links
- Pagination via `_N.htm` suffix, but some page 2+ return 404 (inconsistent)
- No User-Agent blocking. Permissive robots.txt.

**Key sections for AI:**
- `/wxzw/zcfg/` — Policies and regulations
- `/wxzw/A0937index_1.htm` — Cyberspace governance (网信政务)

**Note:** CAC is arguably the most important central body for AI regulation specifically (they wrote the algorithm recommendation rules, generative AI rules, deepfake rules). Worth the extra effort.

### 5. MIIT (工信部) — HARDEST

| | |
|---|---|
| **URL** | `https://www.miit.gov.cn` |
| **CMS** | Hanweb CMS + Kong API Gateway + JSL CDN |
| **AI relevance** | AI industry standards, compute infrastructure, chip policy, telecom/data |
| **Difficulty** | Hard |

**How to crawl:**
- **Returns 403 without browser User-Agent** — must spoof `Mozilla/5.0...`
- Policy search at `/search/wjfb.html` uses Hanweb `search-front-server` backend
- Search API exists but blocks direct access — content is JS-rendered
- Would likely need headless browser (Playwright) or careful request header replay
- robots.txt itself returns 403

**Key sections for AI:**
- `/zwgk/zcwj/wjfb/` — Policy document releases (redirects to search page)
- `/jgsj/` — Department tree (find AI/high-tech relevant departments)

---

## Effort Estimate: Full AI Policy Vertical

| Layer | Sites | Effort | Status |
|-------|-------|--------|--------|
| **District** | Shenzhen districts (6) | Done | 45,130 docs in corpus |
| **Municipal** | Shenzhen departments (14) | Done | Already crawled |
| **Municipal** | Guangzhou | 1 hour | Add to SITES, run crawler |
| **Provincial** | Guangdong Province | 1 hour | Add to SITES (SID: 2), run crawler |
| **Central — NDRC** | ndrc.gov.cn | 1 day | Static HTML, predictable pagination |
| **Central — State Council** | gov.cn | 1-2 days | Static HTML + sitemap, large volume |
| **Central — MOST** | most.gov.cn | 1-2 days | Category-based navigation, JS pagination |
| **Central — CAC** | cac.gov.cn | 2-3 days | Inconsistent pagination, coded URLs |
| **Central — MIIT** | miit.gov.cn | 3-5 days | WAF, JS rendering, headless browser likely needed |

**Total for a complete vertical: ~2 weeks of crawler development.**

The provincial and municipal layers are essentially free (gkmlpt). The central layer is where all the new work is.

### What was actually built (2026-03-15)

The expansion diverged from this plan. Instead of MOST/CAC/MIIT, we built:
- **MOF** (`crawlers/mof.py`) — Ministry of Finance, 919 docs, 912 bodies. Covers fiscal policy, government guidance funds, VC regulation.
- **MEE** (`crawlers/mee.py`) — Ministry of Ecology & Environment, 563 docs, 494 bodies. Covers environmental regulation, carbon policy.
- **16 Guangdong cities** added to gkmlpt — Zhongshan, Shantou, Shaoguan, Heyuan, Shanwei, Yangjiang, Zhanjiang, Chaozhou, Jieyang, Yunfu, etc.
- **3 more Shenzhen districts** — Yantian, Longgang, Dapeng.

Total corpus: **103,470 docs, 91% body text**. MOST, CAC, and MIIT remain unbuilt.

---

## Recommended Build Order

1. **Guangdong Province + Guangzhou** — add to SITES dict, run existing crawler. Completes the provincial layer for free. Do this first because it immediately enables vertical analysis using documents already in the corpus.

2. **NDRC** — easiest central site. Write `crawlers/ndrc.py`. The NDRC issues broad industrial policy directives that Guangdong Province then localizes — this one connection alone demonstrates the vertical chain.

3. **State Council** — highest authority. Write `crawlers/gov.py`. State Council "opinions" (国务院意见) are the documents that trigger the entire cascade. Even a partial crawl of `/zhengce/` is valuable.

4. **CAC** — most AI-specific. Write `crawlers/cac.py`. The CAC's algorithm/AI regulations are the documents that Shenzhen's stic (S&T Innovation Bureau) and other departments implement locally.

5. **MOST** — research/funding side of AI. Write `crawlers/most.py`.

6. **MIIT** — only if needed. Hardest to crawl, and much of MIIT's AI-relevant content overlaps with NDRC and CAC.

---

## Architecture Note

The current `crawler.py` is a gkmlpt-specific adapter. For multi-platform crawling, the cleanest approach:

```
crawlers/
├── gkmlpt.py       # Current crawler.py (Guangdong platform)
├── ndrc.py          # NDRC static HTML crawler
├── gov.py           # State Council crawler
├── cac.py           # CAC crawler
├── most.py          # MOST crawler
└── base.py          # Shared: fetch(), store_document(), save_raw_html()
```

All crawlers write to the same `documents.db` using the same schema. The `site_key` field distinguishes sources. The web app, analysis tools, and search all work unchanged — they don't care where documents came from.

---

## What This Enables

With a complete vertical, you could answer questions like:

- **Policy cascade timing:** When the State Council issues an AI opinion, how many days until Guangdong Province issues implementation guidelines? How many more days until Shenzhen issues specific rules?
- **Implementation divergence:** Does Shenzhen's interpretation of "AI ethics" match what the CAC actually wrote? Where do local implementations add or omit provisions?
- **Cross-reference density:** Which central documents get cited most by local governments? Which get ignored?
- **Regulatory competition:** Do Guangzhou and Shenzhen implement the same provincial AI directive differently?

This is exactly the "experimentation under hierarchy" analysis that David Yang (Harvard) and Sebastian Heilmann built careers studying — but with a live, continuously-updated database instead of a one-time manual collection.
