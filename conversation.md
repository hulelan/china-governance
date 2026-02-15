Lelan: 

The project that I want to do is to collect, organize, and analyze all of the government websites for China. This includes the central government and various provincial and city and local governments. The reason that I want to do this is there is a lot of material that they publish in terms of announcements. And since most governmental policy is actually implemented on the local level, even though priorities are set on the central level, it is really helpful to know, for example, well, it is really helpful to know what local governments are doing, why they're doing this, what they think is happening, and how they are doing certain things. So for example, it is helpful to know what sorts of documents or speeches from the central government are most frequently referenced on local governments. It's helpful to know what kinds of meetings are happening where, and like we don't even have a good understanding of how these things happen in the political governance that occurs. Like this is all knowledge that I'm sure a Chinese bureaucrat knows, but the world doesn't. And I think this is, I'm very curious, and I'm curious to understand, and I also think this will demystify China to a certain extent to the outside world to know how policy is actually done. I also think there probably are some good policy decisions and ideas there. And I will show you an example of an article that I would be interested in documenting. The primary challenges here are that these pages are not indexed to my knowledge, and I don't understand, I don't know how to pull like all of the available pages in a website. I think that's the primary challenge, like how do we crawl all of these websites effectively? Like I can, we can start with a list of cities or a list of even like domains, but even within a domain, how do we know which, what pages these are is the primary challenge. And once we get them, I think actually organizing them will be relatively simple because we can use large language models to translate, to tag, to pull out the relevant keywords and some documents, etc. But I am really worried about the prospect of pulling down all these documents since the, like the walled garden is part of the problem. Like most of these documents are in WeChat, and so we're only limiting ourselves to ones that are available on websites. But even then, I want to figure out how we can do this. I would like you to help me do this, which includes helping us make sure that we have a crystal goal, that we know what we want, what the final goal is, what the intermediary MVP version of it is, what the technical challenges are, and then we can start from there and figure out how to do things like crawl the website.

https://www.sz.gov.cn/cn/xxgk/zfxxgj/sldzc/szfld/lwp/jqhd/content/mpost_12193340.html


Claude: 
Let me start by looking at the example page you shared to understand the type of content we're working with.This is a fantastic project. The example URL is revealing — let me break down what I can see and then work through the project systematically.

## What the Example Tells Us

The URL you shared is from Shenzhen's government portal (sz.gov.cn), and the path structure is highly informative:

`/cn/xxgk/zfxxgj/sldzc/szfld/lwp/jqhd/content/mpost_12193340.html`

This decodes to: 信息公开 (information disclosure) → 政府信息公开 → 市领导 (city leaders) → 卢文鹏 (specific leader) → 近期活动 (recent activities). The nearby page I found (mpost_12193338) is Mayor Qin Weizhong speaking at the 2025 Global AI Terminal Exhibition, referencing Xi Jinping's remarks on AI, and announcing Shenzhen's "AI+" action plan. This is exactly the kind of content where you can trace how central directives (Xi's AI remarks) get operationalized into local policy (Shenzhen's specific industrial strategy).

The `mpost_` ID pattern and the hierarchical URL structure suggest a standardized CMS — which is actually a crucial insight for crawling.

---

## Let me help structure this project clearly.

### The Crystal Goal

**Ultimate goal:** A searchable, tagged, translated corpus of Chinese government publications across all administrative levels, enabling analysis of how central policy priorities propagate through the bureaucratic hierarchy — what gets emphasized where, what local variation looks like, what implementation actually entails.

**The analytical questions this enables:**
- Which central documents/speeches are most frequently cited at local levels? (Policy signal propagation)
- What is the lag time between a central directive and local implementation documents?
- What local policy innovations appear that aren't directed from above?
- What do meeting patterns, attendee lists, and inspection visits reveal about governance priorities?
- What variation exists across provinces/cities in how the same central mandate gets interpreted?

### MVP vs. Full Vision

**MVP (Phase 1):** Pick 5–10 cities at different tiers (e.g., Shenzhen, Chengdu, Hefei, a county-level city) plus the State Council (gov.cn). Crawl their main government portals. Build the pipeline: crawl → extract → translate → tag → store. Prove the concept works and produces interesting analysis on a small scale.

**Phase 2:** Expand to all provincial capitals + major cities (~50 sites). Standardize the taxonomy. Build comparative analysis tools.

**Phase 3:** Comprehensive coverage of prefecture-level cities (~333) and key county-level governments. This is where you hit the long tail.

---

## Technical Challenges — In Order of Difficulty

### 1. Discovery: What sites exist?

This is actually more solved than you might think.

**The good news:** In 2017, the State Council issued 《政府网站发展指引》(Government Website Development Guidelines), which mandated consolidation and standardization. There's a national government website census. The key resource is the **全国政府网站基本信息数据库** — a registry of all government websites that the General Office of the State Council maintains. Portions of this have been published.

Practically, the domain structure is predictable:
- Central: `www.gov.cn`, ministry sites like `www.mof.gov.cn`
- Provincial: pattern like `www.zj.gov.cn` (Zhejiang), `www.gd.gov.cn` (Guangdong)
- Prefecture cities: `www.sz.gov.cn` (Shenzhen), `www.chengdu.gov.cn`
- Counties/districts often live as subdomains or subpaths of their parent city

A reasonable first step is to compile the master domain list from existing sources — Wikipedia's list of Chinese administrative divisions cross-referenced with known domain patterns, plus the government's own directory.

### 2. Crawling: How do we get all pages within a site?

This is the core technical challenge. Several approaches, in order of sophistication:

**a) Sitemap discovery.** Many government sites publish `sitemap.xml`. Check `robots.txt` and `/sitemap.xml` first. When these exist, they give you the full URL inventory for free.

**b) Hierarchical navigation crawling.** The URL structure you showed reveals a tree: 信息公开 → subcategories → content pages. Most Chinese government sites have a relatively standard navigation structure mandated by the 2017 guidelines. You can crawl the top-level category pages, extract pagination links, and follow them down. The `mpost_` pattern with sequential IDs suggests you could even enumerate by incrementing IDs, though there will be gaps.

**c) Full recursive crawling.** Standard web spider approach — start from the homepage, follow all internal links, respect `robots.txt` (or don't, depending on your ethical stance — these are public government documents). Tools: Scrapy (Python) is the standard. For JavaScript-rendered pages, you'd need a headless browser (Playwright/Puppeteer), though most government sites are server-rendered HTML.

**d) The "government information disclosure" (政府信息公开) section** is typically the richest and most structured part of these sites. Many have their own index/search interfaces. Some have APIs. Targeting this section specifically is higher-value than crawling the entire site.

### 3. Anti-Bot and Access Issues

Chinese government sites generally aren't heavily protected against scraping — they're public information disclosure platforms. But you'll encounter:
- Rate limiting (solve with polite delays, rotating IPs)
- SSL/TLS quirks (as we saw — the sz.gov.cn fetch failed on an SSL issue)
- Occasional CAPTCHAs
- Some content behind search interfaces that don't expose URLs directly
- The Great Firewall can make access from outside China slower/unreliable — ideally you'd run crawlers on a Chinese VPS (Alibaba Cloud, Tencent Cloud)

### 4. Content Extraction and Standardization

Once you have the HTML, you need to extract:
- Title, date, publishing authority, document number (文号)
- Body text
- References to other documents (this is gold for your propagation analysis)
- Attachments (PDFs, Word docs — many policy documents are uploaded as attachments)

The good news: the CMS standardization means extraction patterns will be reusable across many sites. The bad news: there are still probably 5–10 distinct CMS templates across the ecosystem, each needing its own parser.

### 5. The WeChat Problem

You flagged this correctly. A huge amount of government communication now happens via official WeChat public accounts (政务微信公众号). These are essentially walled — no public URLs, content behind WeChat's app, and Tencent actively blocks scraping. Some workarounds:
- Some WeChat articles get mirrored to the official websites (partial overlap)
- Services like Sogou WeChat Search (`weixin.sogou.com`) index some public account articles
- There are third-party monitoring services (新榜, 清博) that track government WeChat accounts
- This is genuinely a harder problem and might need to be Phase 4 / a separate sub-project

---

## Proposed Architecture

```
1. Domain Registry (master list of gov sites + metadata)
        ↓
2. Crawler (Scrapy + Playwright for JS-heavy sites)
        ↓
3. Raw HTML Storage (S3 or equivalent, with metadata)
        ↓
4. Content Extraction Pipeline (per-CMS-template parsers)
        ↓
5. Structured Data Store (PostgreSQL or similar)
   - title, date, source_authority, admin_level, 
   - document_number, body_text, referenced_documents,
   - attachments, URL, crawl_date
        ↓
6. LLM Processing Layer
   - Translation (EN)
   - Topic tagging / classification
   - Entity extraction (people, orgs, policies referenced)
   - Document cross-referencing
        ↓
7. Analysis / Search Interface
```

---

## Where I'd Start

The immediate next step is to do a concrete proof-of-concept on **one site** — Shenzhen (sz.gov.cn) is ideal since you already have it. Specifically:

1. Enumerate the 政府信息公开 section structure
2. Build a crawler that can pull all content pages
3. Extract structured data from ~100 pages
4. Run LLM tagging/translation on those
5. See what patterns emerge

Want to start there? I can help you write the crawler code, beginning with mapping out sz.gov.cn's structure — checking for sitemaps, analyzing their URL patterns, and building a Scrapy spider. We can do the first reconnaissance steps right now.

Lelan: 
This sounds good. Let's hold our goal in this conversation to be to collect all the information required to have a reliable and accurate and reasonable execution plan to actually build out the MVP for Shenzhen if we were to give this to a team of coding agents. So ideally, at the very, very end, we have collected all this information and tried and validated our hypotheses, and there are no remaining obvious questions that we still need to answer, and then we have a final document. Like, don't worry about creating this now, I'm just telling you about the goal that elucidates exactly what the team of agents needs to do. So, for now, let's work through a list of things that we need to know and begin to resolve them

Claude: 
Good. Let me lay out the open questions we need to resolve before this plan is hand-off ready, roughly in dependency order (later items depend on earlier ones).

**Block 1: Site Reconnaissance (sz.gov.cn)**
1. What is the full scope of the site? Is it just `www.sz.gov.cn` or is there a constellation of department subdomains (like the `szfb.sz.gov.cn`, `pnr.sz.gov.cn` we already saw in search results)?
2. Does the site have a sitemap.xml? What does robots.txt say?
3. What is the URL structure / CMS pattern? Is the `mpost_` ID sequential? Are there other content patterns?
4. Is content server-rendered HTML or does it require JavaScript execution?
5. How many total pages/documents are we estimating? Order of magnitude matters for infrastructure decisions.
6. What content types exist (policy docs, meeting summaries, leader activities, notices, etc.) and what's the HTML structure for each?

**Block 2: Access & Crawling Feasibility**
7. Can we reliably fetch pages from outside China, or do we need a China-based VPS?
8. Rate limiting behavior — how aggressive can we be?
9. Are there attached files (PDFs, DOCs) and how prevalent are they?
10. Are there search/list endpoints that give us document inventories more efficiently than recursive crawling?

**Block 3: Data Model & Extraction**
11. What metadata is reliably present in the HTML? (date, author, document number, category)
12. What does the cross-referencing structure look like? How are central documents cited?
13. What taxonomy/tagging scheme do we want?

**Block 4: Infrastructure & LLM Pipeline**
14. Storage format and estimated size
15. LLM model selection, cost estimation for translation + tagging at scale
16. How to handle incremental updates (re-crawling for new content)

Let's start with Block 1 since everything else flows from it. I'll try to fetch the site structure now — checking for sitemaps, exploring the domain constellation, and analyzing the URL patterns. Let me do several of these in parallel.OK, I've gathered substantial intelligence. Let me synthesize what we now know and what remains uncertain, question by question.

---

## Block 1 Findings: Site Reconnaissance

### Q1: Scope — It's Not One Site, It's a Constellation

This is the single most important finding. "Shenzhen's government website" is actually **dozens of independent sites** on distinct subdomains. What I've confirmed so far:

**Main portal:** `www.sz.gov.cn` — the municipal government gateway

**Municipal department sites** (each has its own subdomain):
- `fgw.sz.gov.cn` — Development & Reform Commission
- `stic.sz.gov.cn` — Science & Technology Innovation Bureau
- `hrss.sz.gov.cn` — Human Resources & Social Security
- `szfb.sz.gov.cn` — Finance Bureau
- `sf.sz.gov.cn` — Justice Bureau
- `gxj.sz.gov.cn` — Industry & Information Technology
- `pnr.sz.gov.cn` — Planning & Natural Resources
- `zjj.sz.gov.cn` — Housing & Construction
- `gzw.sz.gov.cn` — State-owned Assets (SASAC)
- `jr.sz.gov.cn` — Local Financial Supervision
- `zxqyj.sz.gov.cn` — SME Service Bureau
- `szjj.sz.gov.cn` — Traffic Police
- `tzb.sz.gov.cn` — United Front Work Department
- `zzb.sz.gov.cn` — Organization Department

**District government sites** (Shenzhen has 9 districts + 1 special zone):
- `www.szft.gov.cn` — Futian
- `www.yantian.gov.cn` — Yantian
- `www.szns.gov.cn` — Nanshan
- `www.szpsq.gov.cn` — Pingshan
- `www.szgm.gov.cn` — Guangming

Plus Luohu, Bao'an, Longgang, Longhua, Dapeng New District, and Shenzhen-Shanwei Cooperation Zone.

**Other platforms:**
- `opendata.sz.gov.cn` — Open Data platform (has a proper API with appKey authentication)
- `wsbs.sz.gov.cn` — Government services portal

**Implication for MVP scoping:** We need to decide whether the MVP targets just the main portal, or the main portal + a sample of department sites + a sample of district sites. I'd argue we need at least the main portal + 3–4 department sites + 2 district sites to validate that the approach generalizes across the constellation.

### Q2: Sitemap & Robots.txt

I was unable to fetch `robots.txt` or `sitemap.xml` from sz.gov.cn due to an SSL/TLS error (`BAD_ECPOINT`). This is itself an important finding — the site uses an unusual SSL configuration that breaks standard TLS libraries. This will need to be handled in the crawler (likely by configuring custom SSL ciphers or using a less strict TLS client). **This is a verified technical obstacle that needs a specific solution in the spec.**

### Q3: URL Structure & CMS Patterns

Two distinct content management patterns are visible:

**Pattern A — Main portal content:** URLs like `/cn/xxgk/zfxxgj/sldzc/szfld/lwp/jqhd/content/mpost_12193340.html`
- The `mpost_` prefix with sequential numeric IDs (I've seen IDs ranging from ~1,600,000 to ~12,300,000)
- The path encodes the navigation hierarchy: `xxgk` (信息公开) → `zfxxgj` (政府信息公开) → section → subsection → `content/mpost_ID.html`

**Pattern B — The `gkmlpt` platform:** URLs like `/gkmlpt/content/10/10934/post_10934309.html`
- This is a **standardized government information disclosure platform** (公开目录平台) deployed across nearly all Shenzhen departments and districts
- The URL structure is: `/{department_prefix}/gkmlpt/content/{major_version}/{folder_id}/post_{post_id}.html`
- This platform appears on `zjj.sz.gov.cn/gkmlpt/`, `gxj.sz.gov.cn/gkmlpt/`, `szjj.sz.gov.cn/gkmlpt/`, and all district sites

The `gkmlpt` standardization is extremely valuable — it means a single parser can potentially work across many sites. **This is the highest-priority crawl target.**

### Q5: Scale Estimation

Based on the `mpost_` IDs ranging up to ~12.3 million on the main portal, and accounting for gaps, we're probably looking at **hundreds of thousands to low millions** of content pages across the entire constellation. The Fukuda district site (szft.gov.cn) shows documents going back to 1996. For the MVP, limiting to recent years (say 2020-present) or to the 政府信息公开 sections specifically would bring this to a more manageable range — probably tens of thousands of documents.

### Q6: Content Types Observed

From what I can see across the search results, the main content types include:
- **通知公告** (Notices/announcements) — the bulk of content
- **政策法规** (Policies/regulations)
- **领导活动** (Leader activities) — your original example
- **工作动态** (Work updates)
- **征集调查** (Public consultations/opinion solicitation)
- **政策解读** (Policy interpretations)
- **资金信息** (Financial/funding information)
- **规划计划** (Plans)
- **统计数据** (Statistical data)
- **政府公报** (Government gazette)
- **在线访谈** (Online interviews/Q&A sessions)

---

## Critical Discovery: Existing Related Projects

This is something you should know before building from scratch:

**1. UC San Diego's China Policy Document Navigator** ([portals.igcc.sdsc.edu](https://portals.igcc.sdsc.edu))
- Developed by IGCC and the China Data Lab at UCSD's 21st Century China Center
- Contains tens of thousands of S&T-related policy documents across national, provincial, and prefectural levels
- Has search by keyword (Chinese & English), date range, issuing department, province
- Topic modeling across 13 themes, visual dashboards
- Allows metadata export; full-text access by request
- **Limitation:** Focused on science & technology policy specifically, not the full breadth of government publications. But their data collection methodology could be very informative.

**2. A Cambridge paper ("Mitigating Missingness in Analysing Chinese Policy")** scraped from 80+ government portals using the 政务公开 sections. Key methodological findings from that paper:
- They used policy cross-references (documents citing other documents) as an analytical tool — exactly your stated interest
- They found that some government sites have started implementing retrieval restrictions (e.g., MFA limits search results to 1,000)
- They noted missingness is a real problem — not all documents that exist are publicly posted
- They compared their scraped data to PKULaw (a commercial database) and found ~1-5% differences

**3. CAPC-CG Corpus** (arXiv 2510.08986) — Central government documents 1949-2023, 3.3 million paragraph units, annotated with policy communication taxonomy

**Implication:** You are not building in a vacuum. The UCSD group in particular has likely already solved many of the technical challenges. It would be worth reaching out to them, both to learn from their approach and to potentially collaborate or build on their infrastructure. Their focus on S&T is narrower than your ambition, but the crawling/extraction pipeline would be very similar.

---

## Remaining Open Questions for Next Steps

Here's what we still need to resolve:

1. **SSL workaround:** We need to confirm that a custom TLS configuration (e.g., using `requests` with modified cipher suites, or `curl` with `--insecure`) can actually fetch pages from sz.gov.cn. This is a blocker — if we can't fetch, nothing else matters.

2. **The `gkmlpt` platform internals:** Does it have a built-in search/listing API or pagination endpoint? If so, we can enumerate all documents programmatically without recursive crawling. We need someone to inspect the platform's JavaScript to find the underlying data endpoints.

3. **Complete subdomain inventory:** We need the full list of department and district sites. The page at `sz.gov.cn/szsrmzfxxgk/dfbmptlj/index.html` appears to have this but we couldn't fetch it.

4. **JavaScript rendering requirements:** Are the listing/index pages server-rendered HTML or do they require JS execution? This determines whether we use Scrapy alone or need Playwright.

5. **Rate limiting behavior:** We need empirical testing — how fast can we request before getting blocked?

6. **China-based access:** Given the SSL issues fetching from outside, we should confirm whether a China-based VPS (Alibaba Cloud/Tencent Cloud) resolves the problem.

7. **Attachment prevalence:** Many policy documents are uploaded as PDF/DOC attachments. We need to understand how common this is and whether we need a PDF extraction pipeline from day one.

What would you like to tackle next? I'd suggest we try to resolve the SSL access issue first (question 1), since it's a gating technical question. If you can try accessing `sz.gov.cn` from a browser and share what you see in the page source, that would also help enormously with understanding the HTML structure and whether the `gkmlpt` platform has API endpoints we can use.

Lelan: 
Let's keep validating next steps.

Claude: 
Good — we had identified 7 prioritized open questions. Let me work through what we can resolve right now. I'll tackle three in parallel: the **gkmlpt platform internals** (can we find API documentation or JS endpoints?), the **complete subdomain inventory**, and the **SSL workaround** specifics.Important — Pingshan's HTTP endpoint worked. Let me now look for the API endpoints the gkmlpt platform uses to load its document listings.Excellent — that's a massive finding. Let me now try to discover the API the gkmlpt index page uses by checking similar platforms.Now I have enough to compile comprehensive findings. Let me write up the updated spec.Here's what moved today. Three findings reshape the architecture:

**SSL blocker is gone.** HTTP (not HTTPS) works across all Shenzhen gov sites tested. The `BAD_ECPOINT` error only affects TLS — plain HTTP returns full pages. This removes the primary technical blocker.

**gkmlpt has a split architecture.** The listing/index pages are Vue.js SPAs — no document data in the HTML, everything loaded via AJAX. But individual content pages are server-rendered with full text and a standardized metadata table (索引号, 发布机构, 成文日期, 名称, 文号, 发布日期, 主题词). This means the crawler needs two modes: an API-based or Playwright-based listing discovery layer, and a simple HTTP scraper for content extraction.

**The metadata structure is standardized and parseable.** I fetched a full content page from Pingshan's gkmlpt. The metadata table has consistent field names across departments, making extraction a single parser rather than per-site custom work. Post IDs are globally sequential (~9M in 2021, ~12M in 2025), with major version numbers incrementing roughly annually.

**The single highest-value next step** is 5 minutes of browser DevTools inspection: open any gkmlpt index page, watch the Network tab for XHR requests as you paginate, and capture the underlying JSON API endpoint. If there's a clean paginated API (likely, given it's a Vue SPA), we skip Playwright entirely and can enumerate all documents with simple HTTP requests. That's the difference between a complex crawler and a straightforward one.


# Shenzhen Gov Crawler — Validation Session Findings

## Resolved Questions

### 1. SSL Workaround — RESOLVED ✅

**Finding:** The `BAD_ECPOINT` SSL error affects HTTPS connections across the entire Shenzhen gov constellation — confirmed on `sz.gov.cn`, `szgm.gov.cn` (Guangming), `szns.gov.cn` (Nanshan), and `szpsq.gov.cn` (Pingshan).

**Workaround confirmed:** HTTP (not HTTPS) connections work. Successfully fetched full page content from `http://www.szpsq.gov.cn/psozhzx/gkmlpt/index` and `http://www.szpsq.gov.cn/gkmlpt/content/9/9103/post_9103540.html`.

**Spec implication:** Crawler should default to HTTP for all `*.sz.gov.cn` and Shenzhen district sites. Optionally attempt HTTPS with custom cipher suites as fallback. China-based VPS may still resolve the HTTPS issue (untested), but HTTP works now and removes this as a blocker.

---

### 2. gkmlpt Platform Architecture — MAJOR FINDINGS ✅

The gkmlpt (公开目录平台 / Government Information Disclosure Platform) has a **split rendering architecture**:

**Index/listing pages = JavaScript SPA** (critical implication)
- The HTML returned for `/gkmlpt/index` contains only a shell: header, search bar, footer
- No document listings in HTML — all content loaded dynamically via AJAX
- Uses Vue.js (based on asset paths: `/gkmlpt/gkml/pc/images/`)
- Has advanced search: by title/full text, time/relevance sort, file status (current/expired)
- **Implication:** Cannot use simple HTTP scraping for listings. Need either:
  - (a) Playwright/Selenium to render JS and extract listings, OR
  - (b) Reverse-engineer the underlying API endpoints (preferred — faster, more reliable)
  - API discovery requires inspecting browser DevTools Network tab on a live session

**Content/detail pages = Server-rendered HTML** (good news)
- Individual document pages (`/gkmlpt/content/{version}/{folder}/post_{id}.html`) return full HTML with all content
- Full text body is in the HTML
- Structured metadata table is standardized with these fields:

| Field | Chinese | Example |
|-------|---------|---------|
| Index Number | 索引号 | `114403006955506492/2021-00426` |
| Category | 分类 | (varies) |
| Publishing Org | 发布机构 | `深圳市坪山区人民政府` |
| Date Written | 成文日期 | `2021-09-02` |
| Title | 名称 | (document title) |
| Document Number | 文号 | (formal document ID, sometimes empty) |
| Publication Date | 发布日期 | `2021-09-03` |
| Keywords | 主题词 | `工作总结` |

- **Implication:** Scrapy (no Playwright) sufficient for individual page extraction. Metadata parsing is straightforward CSS/XPath.

---

### 3. URL Pattern Analysis — Refined ✅

From Pingshan district content pages, confirmed URL structure:

```
/{department_prefix}/gkmlpt/content/{major_version}/{folder_id}/post_{post_id}.html
```

**Department prefix patterns (Pingshan examples):**
- `psjtgdjsbgs` — 交通公共基础设施建设管理部门 (Transport infrastructure)
- `psfzhgjj` — 发展和改革局 (Development & Reform)
- `psrlzyj` — 人力资源局 (Human Resources)
- `pspspsjdbsc` — 坪山街道办事处 (Pingshan Subdistrict)
- `pssjj` — 审计局 (Audit Bureau)
- `pstztgfws` — 投资推广服务 (Investment Promotion)
- `psowxzbwblyj` — 文化广电旅游体育局 (Culture & Tourism)
- `pskjcxfws` — 科技创新服务 (S&T Innovation)
- `psozhzx` — 政务服务和数据管理局 (Government Services & Data)

Older pages omit department prefix: `/gkmlpt/content/9/9033/post_9033443.html`

**Version/year mapping (approximate):**
- Major version 9 → 2021
- Major version 10 → 2022
- Major version 11 → 2024
- Major version 12 → 2025

**post_id is globally sequential** — IDs in ~9M range (2021) through ~12M range (2025).

---

### 4. Complete Subdomain Inventory — COMPILED ✅

Source: Shenzhen search portal (search.gd.gov.cn) department filter + direct observation.

**Municipal Departments (~37 sites):**

| # | Department | Known Subdomain | Confirmed |
|---|-----------|----------------|-----------|
| 1 | 发展改革委 | fgw.sz.gov.cn | ✅ |
| 2 | 教育局 | szeb.sz.gov.cn | (inferred) |
| 3 | 科技创新局 | stic.sz.gov.cn | ✅ |
| 4 | 工业和信息化局 | gxj.sz.gov.cn | ✅ |
| 5 | 公安局 | ga.sz.gov.cn | (inferred) |
| 6 | 民政局 | mzj.sz.gov.cn | (inferred) |
| 7 | 司法局 | sf.sz.gov.cn | ✅ |
| 8 | 财政局 | szfb.sz.gov.cn | ✅ |
| 9 | 人力资源保障局 | hrss.sz.gov.cn | ✅ |
| 10 | 规划和自然资源局 | pnr.sz.gov.cn | ✅ |
| 11 | 生态环境局 | meeb.sz.gov.cn | (inferred) |
| 12 | 住房建设局 | zjj.sz.gov.cn | ✅ |
| 13 | 交通运输局 | jtys.sz.gov.cn | (inferred) |
| 14 | 水务局 | swj.sz.gov.cn | (inferred) |
| 15 | 商务局/投资促进局 | commerce.sz.gov.cn | (inferred) |
| 16 | 文化广电旅游体育局 | wtl.sz.gov.cn | (inferred) |
| 17 | 卫生健康委 | wjw.sz.gov.cn | (inferred) |
| 18 | 退役军人事务局 | (unknown) | |
| 19 | 应急管理局 | (unknown) | |
| 20 | 审计局 | (unknown) | |
| 21 | 国资委 | gzw.sz.gov.cn | ✅ |
| 22 | 市场监管局 | amr.sz.gov.cn | (inferred) |
| 23 | 政务和数据局 | (unknown) | |
| 24 | 统计局 | tjj.sz.gov.cn | (inferred) |
| 25 | 医保局 | (unknown) | |
| 26 | 城管和综合执法局 | cgj.sz.gov.cn | ✅ |
| 27 | 口岸办 | (unknown) | |
| 28 | 乡村振兴和协作交流局 | (unknown) | |
| 29 | 信访局 | (unknown) | |
| 30 | 中小企业服务局 | zxqyj.sz.gov.cn | ✅ |
| 31 | 公安局交通管理局 | szjj.sz.gov.cn | ✅ |
| 32 | 前海管理局 | qh.sz.gov.cn | (inferred) |
| 33 | 发展研究中心 | (unknown) | |
| 34 | 机关事务管理局 | (unknown) | |
| 35 | 建筑工务署 | (unknown) | |
| 36 | 气象局 | weather.sz.gov.cn | (inferred) |
| 37 | 河套发展署 | (unknown) | |
| — | 外事办 | fao.sz.gov.cn | ✅ |
| — | 金融监管局 | jr.sz.gov.cn | ✅ |
| — | 组织部 | zzb.sz.gov.cn | ✅ |
| — | 统战部 | tzb.sz.gov.cn | ✅ |

**Districts (11 sites):**

| # | District | Domain | Confirmed |
|---|----------|--------|-----------|
| 1 | 福田区 | www.szft.gov.cn | ✅ |
| 2 | 罗湖区 | www.szlh.gov.cn | (inferred) |
| 3 | 盐田区 | www.yantian.gov.cn | ✅ |
| 4 | 南山区 | www.szns.gov.cn | ✅ |
| 5 | 宝安区 | www.baoan.gov.cn | (inferred) |
| 6 | 龙岗区 | www.lg.gov.cn | (inferred) |
| 7 | 龙华区 | www.szlhq.gov.cn | (inferred) |
| 8 | 坪山区 | www.szpsq.gov.cn | ✅ |
| 9 | 光明区 | www.szgm.gov.cn | ✅ |
| 10 | 大鹏新区 | www.dpxq.gov.cn | (inferred) |
| 11 | 深汕特别合作区 | (unknown) | |

**Total: ~48 sites.** Of these, ~17 subdomains confirmed by direct observation.

**Action needed:** Scrape the "政府网站年度工作报表" page (linked from main portal footer) or the department links page to get the full verified list with exact URLs.

---

### 5. gkmlpt Is Province-Wide Standard — CONFIRMED ✅

The gkmlpt platform is not Shenzhen-specific. Confirmed on Guangzhou Conghua district (`www.conghua.gov.cn/gzchscjg/gkmlpt/mindex`). This is a Guangdong province-level standardized platform, likely built by 数字广东 (Digital Guangdong, a Tencent-affiliated government IT contractor).

**Implication for scaling beyond Shenzhen:** Once the gkmlpt parser works for Shenzhen, it should generalize to other Guangdong cities with minimal modification.

---

### 6. JavaScript Rendering Requirements — PARTIALLY RESOLVED

| Page Type | Rendering | Tool Needed |
|-----------|-----------|-------------|
| gkmlpt index/listings | JS SPA (Vue.js) | Playwright OR API reverse-engineering |
| gkmlpt content pages | Server-rendered HTML | Scrapy / requests |
| Main portal (sz.gov.cn) listings | Unknown (couldn't fetch) | TBD |
| Main portal content pages | Likely server-rendered | TBD |

**Recommendation:** Prioritize API reverse-engineering for gkmlpt listings. If someone opens browser DevTools Network tab on a gkmlpt index page and filters for XHR/Fetch requests, the underlying JSON API endpoints should be visible. This is the single highest-value investigative task remaining.

---

## Updated Open Questions

### Still Blocking (Priority Order)

1. **gkmlpt API endpoints** — Need browser DevTools inspection of gkmlpt index page to find the JSON API that powers document listings. This determines whether we need Playwright at all.

2. **Verify inferred subdomains** — ~20 department subdomains are inferred, not confirmed. Need the official department links page or annual website report.

3. **Main portal (sz.gov.cn) HTML structure** — Haven't been able to inspect main portal content pages. The mpost_ URL pattern needs verification of HTML structure and metadata format.

### Not Blocking But Important

4. **Rate limiting** — Requires empirical testing once crawler prototype exists.

5. **Attachment prevalence** — Sample 50-100 documents to estimate PDF/DOC ratio.

6. **Document number (文号) format** — Needed for cross-reference extraction. Need to catalog format patterns from actual documents.

7. **Open Data API (opendata.sz.gov.cn)** — Evaluate whether this covers any content types we need. Requires obtaining appKey.

---

## Revised MVP Architecture

Based on findings, the crawler has two distinct operational modes:

### Mode A: Listing Discovery (find document URLs)
- **Preferred:** Reverse-engineer gkmlpt JSON API → paginate through all documents
- **Fallback:** Playwright renders gkmlpt index pages → extract links
- **Output:** Queue of `post_{id}.html` URLs per department/district

### Mode B: Content Extraction (parse individual documents)
- **Method:** Simple HTTP GET (Scrapy or requests) over HTTP (not HTTPS)
- **Extract:** Metadata table (索引号, 发布机构, 成文日期, 名称, 文号, 发布日期, 主题词) + full text body + any attachment URLs
- **Parser:** Single parser works across all gkmlpt implementations

### Pipeline:
```
[Listing Discovery] → [URL Queue] → [Content Extraction] → [Structured Storage]
                                                                    ↓
                                                         [Translation + Tagging]
```

---

## Recommended Next Actions (for you)

1. **Browser inspection of gkmlpt API** (5 min, highest value)
   - Open http://www.szpsq.gov.cn/psozhzx/gkmlpt/index in Chrome
   - Open DevTools → Network tab → filter XHR/Fetch
   - Click through pagination or search
   - Copy the API URL patterns and sample responses

2. **Verify subdomains** (5 min)
   - Visit sz.gov.cn → look for "部门网站" or "网站导航" link
   - Or search for "深圳市政府网站年度工作报表" which lists all sites

3. **Check main portal content page** (2 min)
   - Visit any mpost_ URL on sz.gov.cn, view source
   - Confirm metadata table structure matches gkmlpt pattern

4. **Register for Open Data API** (10 min, optional)
   - Visit opendata.sz.gov.cn
   - Register and get appKey
   - Test whether policy document content is available via API

Lelan: 
Are these steps something that a coding agent could do?

Claude: 
Yes, mostly. Here's the breakdown:

**Fully automatable (Playwright script):**

**1. gkmlpt API discovery.** This is the canonical use case for Playwright's `page.on('request')` / `page.on('response')` interceptors. The agent navigates to the gkmlpt index page, listens for XHR/Fetch requests, triggers pagination clicks, and logs every API call with its URL pattern, query parameters, and response body. No human eyeballs needed — the output is a list of endpoint URLs and sample JSON payloads. This is actually *better* done by a script than by hand, because it captures exact request headers, cookies, and parameter structures.

**2. Subdomain verification.** Navigate to `sz.gov.cn`, find the department links page (政府部门网站导航), extract all `<a href>` values. If the links page is JS-rendered, Playwright handles it; if server-rendered, plain `requests` suffices. The "政府网站年度工作报表" is typically a static page or downloadable document listing every site URL.

**3. Main portal content page structure.** Fetch any `mpost_` URL via HTTP, parse the HTML, extract the metadata table structure and field names. Pure HTTP + BeautifulSoup.

**Requires human action:**

**4. Open Data API registration.** Account creation on `opendata.sz.gov.cn` likely involves CAPTCHA, phone number verification, or institutional affiliation. A coding agent can't do this. However, once you have the appKey, everything downstream (testing endpoints, paginating results) is fully automatable.

**The practical question** is where the agent runs. My sandbox here has egress disabled, so I can't execute these directly. But the spec for a coding agent is straightforward — want me to write the Playwright discovery script so you can either run it locally or hand it to a coding agent on a machine with network access? The API discovery script in particular is maybe 40 lines and would resolve the single biggest remaining unknown.

Lelan: 
Could you synthesize our whole conversation into a document organized with the following: 

Motivation:

Goals: 
-Final goal
-Intermediate MVP

What needs to be built / architecture and why. Here explain all the different considerations, and for the items you investigated, explain what you did, what you found, and what you decided as a result. For the items you haven't investigated, mark them as such and explain why they matter.

Claude: spec.md