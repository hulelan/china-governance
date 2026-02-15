# China Government Publications Crawler — Project Specification

---

## 1. Motivation

Chinese governance operates through a structure where policy priorities are set centrally but implemented locally. The State Council and central ministries issue directives, plans, and speeches; provincial, municipal, and district governments then interpret, adapt, and execute these within their jurisdictions. This process generates a massive volume of public documents — policy announcements, implementation plans, meeting summaries, inspection reports, financial disclosures, public consultations — published on official government websites.

Despite being publicly accessible, this material is largely invisible to the outside world. The documents are in Chinese, spread across thousands of independent websites with no cross-site indexing, not systematically captured by any search engine, and lack any analytical layer. As a result, even basic questions about Chinese governance remain unanswered at scale. A Chinese bureaucrat would have intuitive knowledge of how this system operates — which documents matter, how implementation chains work, what the typical cadence of policy propagation looks like. The rest of the world does not.

The specific analytical gaps this project addresses:

- **Policy signal propagation.** When the State Council issues a directive, which local governments pick it up, how quickly, and with what local modifications? Which central documents are most frequently cited locally?
- **Implementation mechanics.** What does the actual chain of implementation look like? How does a central "opinion" (意见) become a local "implementation plan" (实施方案) and then a departmental "work plan" (工作计划)?
- **Local innovation.** What policy measures emerge at local levels that aren't directed from above? Where does experimentation happen?
- **Governance patterns.** What do meeting frequencies, attendee lists, inspection visits, and reporting cadences reveal about how governance actually works, beyond the formal org chart?
- **Cross-regional variation.** How does the same central mandate get interpreted differently across provinces and cities?

Building a searchable, translated, tagged corpus of these publications would demystify Chinese policymaking, surface transferable policy ideas, and enable systematic study of the world's largest bureaucracy.

There is an important scope constraint: a large and growing share of government communication flows through WeChat official accounts (政务微信公众号), which are walled gardens — no public URLs, content locked inside Tencent's ecosystem, active anti-scraping. This project limits itself to content published on official government websites, which is at least nominally on the open web.

---

## 2. Goals

### 2.1 Final Goal

A searchable, tagged, translated corpus of Chinese government publications across all administrative levels — central, provincial, prefectural, and district — enabling comparative analysis of policy propagation, implementation variation, and governance patterns.

At full scale, this means coverage of the State Council and major central ministries, ~31 provincial-level divisions, ~333 prefecture-level cities, and selectively important district/county governments. Probably several thousand websites total.

### 2.2 Intermediate MVP

**Scope:** Shenzhen municipal government — the main portal plus a representative sample of department and district sites.

Shenzhen was chosen for two reasons: it was the starting point of investigation (the initial example URL was a Shenzhen mayoral activity page), and — critically — its site architecture turned out to use a standardized platform (gkmlpt) deployed across all departments and districts in the city, and potentially across Guangdong province. This means a Shenzhen MVP doubles as a validation that the approach generalizes.

**What MVP proves:**

- That the full pipeline works end-to-end: crawl → extract → translate → tag → store → analyze
- That a single parser handles the gkmlpt platform across heterogeneous departments and districts
- That structured metadata (document numbers, dates, publishing organs, keywords) is reliably extractable
- That LLM-based translation and tagging produces analytically useful output
- That cross-referencing between documents (central directives cited in local documents) is feasible

**What MVP produces:**

- Tens of thousands of documents from Shenzhen (roughly 2020–present), from the main portal + 3–4 department sites + 2 district sites
- Structured database with metadata, full Chinese text, English translation, and topic tags
- At least one concrete analytical output — e.g., "Which State Council documents were most cited by Shenzhen departments in 2024?"

**What MVP does not attempt:**

- Coverage beyond Shenzhen
- WeChat content
- Historical completeness (pre-2020)
- Real-time monitoring or incremental crawling (batch is sufficient)

---

## 3. What Needs to Be Built

### 3.1 Architecture Overview

The system is a five-stage pipeline:

```
[1. Site Registry]     → Master list of target URLs, CMS type, access notes
        ↓
[2. Listing Discovery] → Enumerate all document URLs within each site
        ↓
[3. Content Extraction]→ Fetch individual pages, parse metadata + body text
        ↓
[4. Structured Storage]→ PostgreSQL for structured data, filesystem for raw HTML
        ↓
[5. LLM Processing]    → Translation, topic tagging, entity extraction, cross-references
```

Each stage has distinct technical considerations. Several were investigated in depth during our sessions; others remain open. Below, each stage is discussed with what we investigated, what we found, what we decided, and what remains unknown.

---

### 3.2 Stage 1: Site Registry — What Sites Exist?

#### The consideration

Before crawling anything, we need a master list of every website to target. "Shenzhen government website" turned out to be a much larger surface area than a single domain.

#### What we investigated

We explored the scope of Shenzhen's government web presence through web searches, examining the Guangdong search portal's department filter (search.gd.gov.cn), following subdomain links found in search results, and directly fetching district government homepages.

#### What we found

"Shenzhen government" is not one site but a constellation of approximately 48 independent websites:

- **1 main portal:** www.sz.gov.cn (also accessible as www.shenzhen.gov.cn)
- **~37 municipal department sites**, each on its own subdomain of sz.gov.cn. Confirmed examples include fgw.sz.gov.cn (Development & Reform), stic.sz.gov.cn (S&T Innovation), gxj.sz.gov.cn (Industry & IT), sf.sz.gov.cn (Justice Bureau), szfb.sz.gov.cn (Finance), hrss.sz.gov.cn (Human Resources), pnr.sz.gov.cn (Planning & Natural Resources), zjj.sz.gov.cn (Housing & Construction), gzw.sz.gov.cn (State-Owned Assets), jr.sz.gov.cn (Financial Supervision), cgj.sz.gov.cn (Urban Management), zxqyj.sz.gov.cn (SME Service), szjj.sz.gov.cn (Traffic Police), fao.sz.gov.cn (Foreign Affairs), zzb.sz.gov.cn (Organization Department), tzb.sz.gov.cn (United Front Work).
- **11 district/zone sites**, each on its own domain. Confirmed: www.szft.gov.cn (Futian), www.yantian.gov.cn (Yantian), www.szns.gov.cn (Nanshan), www.szpsq.gov.cn (Pingshan), www.szgm.gov.cn (Guangming). Inferred but not verified: Luohu, Bao'an, Longgang, Longhua, Dapeng New District, Shenzhen-Shanwei Cooperation Zone.
- **Other platforms:** opendata.sz.gov.cn (Open Data API, requires appKey), wsbs.sz.gov.cn (Government Services portal).

Of the ~48 sites, about 17 were confirmed by direct access or search results. The remainder are inferred from the department list on the Guangdong search portal.

#### What we decided

The MVP should target the main portal + 3–4 department sites + 2 district sites. This validates that the crawler generalizes across the constellation without requiring the complete inventory upfront. The full inventory can be compiled as a parallel task by scraping the official "department website navigation" page (部门网站导航) on the main portal, or from the legally mandated annual website work report (政府网站年度工作报表) each site publishes.

#### What remains uninvestigated

- Exact subdomains for ~20 departments (inferred but not confirmed)
- Whether all departments actually host their own sites vs. being subsections of the main portal
- The machine-readability of the annual website report — if it contains a clean list of URLs, the full registry is trivial to compile

---

### 3.3 Stage 2: Listing Discovery — What Documents Exist Within Each Site?

This is the most architecturally consequential stage. It answers: "given a site, enumerate all its document URLs" — the step before fetching any actual content.

#### What we investigated

We examined URL patterns across multiple Shenzhen sites. We fetched gkmlpt index pages and content pages via HTTP to understand their rendering architecture. We analyzed the URL structure across departments, districts, and time periods.

#### What we found

**Two distinct CMS patterns exist across the constellation:**

**Pattern A — Main portal (sz.gov.cn).** URLs follow `/cn/xxgk/zfxxgj/{section}/{subsection}/content/mpost_{id}.html`. The path encodes a navigation hierarchy: xxgk (信息公开) → zfxxgj (政府信息公开) → section → subsection → content. The `mpost_` prefix has sequential numeric IDs — we observed IDs from ~1.6M to ~12.3M, though with unknown gap density. This pattern is specific to the main portal.

**Pattern B — gkmlpt platform (dominant across departments and districts).** URLs follow `/{department_prefix}/gkmlpt/content/{major_version}/{folder_id}/post_{post_id}.html`. This is the 公开目录平台 (Government Information Disclosure Platform), a standardized system deployed across essentially all Shenzhen departments and districts. We confirmed its presence on Pingshan district, Nanshan district, Guangming district, Yantian district, and multiple department sites (Housing & Construction, Industry & IT, Traffic Police, the main portal's own statistics department). Critically, we also confirmed the same platform on Guangzhou's Conghua district (conghua.gov.cn), establishing that this is a Guangdong province-level standard — likely built by 数字广东 (Digital Guangdong, a Tencent-affiliated contractor).

**The gkmlpt platform has a split rendering architecture,** which is the key technical finding. We discovered this by fetching both the index page and a content page from Pingshan's gkmlpt:

- **Index/listing pages** (e.g., `/gkmlpt/index`) are JavaScript single-page applications built with Vue.js. The HTML returned by the server contains only a shell — header, search bar, footer — with zero document listings in the source. All content is loaded dynamically via AJAX calls to an underlying API. The search interface supports filtering by title or full text, sorting by time or relevance, and filtering by document status.
- **Individual content pages** (e.g., `/gkmlpt/content/9/9103/post_9103540.html`) are fully server-rendered HTML with the complete document text and metadata in the source.

**URL structure details:** The `department_prefix` in gkmlpt URLs corresponds to abbreviated pinyin of the department name. For Pingshan district, examples include: psjtgdjsbgs (Transportation & Construction), psfzhgjj (Development & Reform), psrlzyj (Human Resources), pskjcxfws (S&T Innovation), psozhzx (Government Data). Older pages sometimes omit the prefix: `/gkmlpt/content/9/9033/post_9033443.html`.

**The `major_version` number increments roughly annually:** version 9 → 2021, version 10 → 2022, version 11 → 2024, version 12 → 2025. Post IDs are globally sequential across the entire gkmlpt system: ~9M range in 2021 → ~12M range in 2025.

#### What we decided

There are two viable approaches for listing discovery on gkmlpt sites:

- **Preferred: Reverse-engineer the gkmlpt JSON API.** Since the index page is a Vue.js SPA that fetches data via AJAX, there is necessarily a backend API that returns paginated document listings in structured form (almost certainly JSON). Once this endpoint is identified, we can paginate through the entire document inventory with simple HTTP requests — no browser automation at all. This is faster, more reliable, and cheaper than headless browsing.
- **Fallback: Use Playwright to render the SPA.** If the API turns out to use encrypted parameters, authentication tokens, or other protections, we use headless browser automation to navigate the listing pages, trigger pagination, and scrape the rendered DOM.

For the main portal's `mpost_` pattern, listing discovery may require crawling category index pages, or brute-force sequential ID enumeration (request every ID, handle 404s). This strategy depends on gap density, which hasn't been measured.

#### What remains uninvestigated — and why this is the single highest-priority unknown

**The gkmlpt API endpoint structure has not been identified.** This is the single most consequential remaining unknown because it determines the entire crawler architecture: if the API is a clean, paginated JSON endpoint (which is the most likely scenario for a Vue.js SPA), listing discovery becomes trivially simple HTTP pagination and Playwright is not needed at all. If the API is protected, we need Playwright for listing pages.

Identifying this API requires inspecting browser DevTools while interacting with a gkmlpt index page — watching the Network tab for XHR/Fetch requests when pagination or search is triggered. This can be automated: a Playwright script navigates to the page, listens on `page.on('request')` and `page.on('response')`, triggers clicks, and logs every API call with its URL, parameters, and response body. This is approximately 40 lines of code and can be done by a coding agent with network access.

Also uninvestigated: the main portal's listing mechanism (we couldn't fetch sz.gov.cn pages even via HTTP due to different server behavior from district sites), and whether sequential ID enumeration is viable (depends on gap density).

---

### 3.4 Stage 3: Content Extraction — Parsing Individual Documents

#### The consideration

Once we have a list of document URLs, we need to fetch each page and parse it into structured fields: metadata and body text.

#### What we investigated

We successfully fetched a complete gkmlpt content page from Pingshan district over plain HTTP and examined its full HTML structure.

#### What we found

gkmlpt content pages have a **standardized metadata table** with consistent field names. The eight fields are:

| Field | Chinese Label | Example |
|-------|-------------|---------|
| Index Number | 索引号 | `114403006955506492/2021-00426` |
| Category | 分类 | (varies) |
| Publishing Organ | 发布机构 | `深圳市坪山区人民政府` |
| Date Written | 成文日期 | `2021-09-02` |
| Title | 名称 | (full document title) |
| Document Number | 文号 | (formal identifier; sometimes empty) |
| Publication Date | 发布日期 | `2021-09-03` |
| Keywords | 主题词 | `工作总结` |

The body text follows the metadata table as standard HTML paragraphs. The page also includes functional UI elements (print button, font size controls, social sharing) that are easy to ignore during extraction.

The department prefix in the URL path provides an additional organizational signal (which department published the document) that should be stored as metadata.

**Content types observed** across Shenzhen sites include: 通知公告 (notices/announcements — the bulk of content), 政策法规 (policies/regulations), 领导活动 (leader activities), 工作动态 (work updates), 征集调查 (public consultations), 政策解读 (policy interpretations), 资金信息 (financial/funding information), 规划计划 (plans), 统计数据 (statistical data), 政府公报 (government gazette), and 在线访谈 (online interviews/Q&A).

#### What we decided

A single parser handles all gkmlpt content pages. The parser extracts metadata from the table by matching Chinese field labels, and body text from the content div. This requires only HTTP + HTML parsing (Scrapy or requests + BeautifulSoup). No JavaScript rendering is needed for content pages.

Because gkmlpt is a Guangdong province-wide standard, this parser should generalize not only across Shenzhen departments but also to other Guangdong cities with minimal modification.

#### What remains uninvestigated

- **Attachment prevalence.** Many policy documents are published as PDF or Word file attachments rather than inline HTML. We don't know what fraction of gkmlpt pages contain attachments. A sample of 50–100 random content pages would answer this and determine whether a PDF extraction pipeline is needed from day one.
- **Main portal HTML structure.** We were unable to fetch any `mpost_` pages from sz.gov.cn, so the main portal's metadata format is unknown. It may match gkmlpt, or may need a separate parser.
- **Document number (文号) format patterns.** These are critical for cross-referencing — e.g., "深府〔2024〕15号" identifies Shenzhen municipal government document #15 of 2024. Building the cross-reference extractor requires cataloging the actual format patterns from real documents.
- **How central documents are cited in local documents.** The Cambridge Quarterly paper found cross-references to be a powerful analytical tool, but the specific textual patterns in Shenzhen documents haven't been examined.

---

### 3.5 Stage 4: Structured Storage

#### The consideration

Raw HTML needs to be archived (for re-parsing if extraction logic improves), and extracted data needs a queryable schema.

#### What we investigated

This was discussed architecturally but not prototyped.

#### Tentative decisions

- **Raw HTML archive:** Filesystem or S3-equivalent, organized by domain and crawl date.
- **Structured data:** PostgreSQL with fields for at minimum: source URL, domain, administrative level, department, document title, document number (文号), date written, date published, publishing organ, keywords, category, body text (Chinese), body text (English), topic tags, referenced document numbers, crawl timestamp.
- **Scale estimate:** For the MVP (Shenzhen, 2020–present, gkmlpt sections only), expect tens of thousands of documents. At ~5–20KB per document, raw storage is under 1GB. PostgreSQL handles this trivially.

#### What remains uninvestigated

- Exact schema design, indexing strategy, foreign keys for cross-references
- Full-text search approach: PostgreSQL's tsvector, or a dedicated engine (Elasticsearch, Meilisearch)
- Deduplication for documents appearing on multiple sites

---

### 3.6 Stage 5: LLM Processing

#### The consideration

Translation (Chinese → English), topic classification, entity extraction (people, organizations, policies), and document cross-referencing.

#### What we investigated

Discussed architecturally; no prompts prototyped or costs estimated.

#### Tentative decisions

- Batch processing after content extraction (not inline with crawling)
- Translation, tagging, and entity extraction combined into a single LLM call per document to reduce costs
- Topic taxonomy should align with existing academic work where possible: UCSD's 13 S&T themes, CAPC-CG's five-color policy communication taxonomy
- Claude or GPT-4 class models for translation quality; potentially smaller models for pure tagging at scale

#### What remains uninvestigated

- Per-document token cost and total budget at MVP scale
- Prompt engineering for translation accuracy, topic tag consistency, entity extraction recall
- Whether Chinese NLP tools (Jieba, LAC) should complement LLM processing for specific tasks
- The actual topic taxonomy: what categories are analytically useful for the stated research questions

---

### 3.7 Cross-Cutting: SSL/TLS Access

#### The consideration

The first action in the entire project — fetching the original example URL — failed with an SSL error: `[SSL: BAD_ECPOINT] bad ecpoint`. If we can't fetch pages at all, nothing else matters.

#### What we investigated

We systematically tested HTTPS and HTTP access across multiple Shenzhen government domains: the main portal (sz.gov.cn), Guangming district (szgm.gov.cn), Nanshan district (szns.gov.cn), and Pingshan district (szpsq.gov.cn).

#### What we found

The `BAD_ECPOINT` error affects HTTPS connections to every tested Shenzhen government site. The servers use an SSL/TLS configuration with elliptic curve parameters incompatible with the OpenSSL version underlying standard Python libraries.

However, **plain HTTP works.** We successfully fetched complete HTML pages from `http://www.szpsq.gov.cn` — both gkmlpt index pages and individual content pages. The sites accept HTTP without redirecting to HTTPS.

#### What we decided

The crawler defaults to HTTP for all `*.sz.gov.cn` and district sites. This eliminates the SSL blocker entirely for the MVP. Two optional improvements for later: a China-based VPS (Alibaba or Tencent Cloud) may resolve HTTPS via different TLS library versions or network path, and custom cipher suite configuration in Python's `ssl` module may accommodate the server's elliptic curve preferences. Neither is needed for MVP — HTTP over public government documents carries no practical risk.

---

### 3.8 Cross-Cutting: JavaScript Rendering Requirements

#### The consideration

Whether the crawler needs a headless browser (Playwright) or can use simple HTTP requests determines complexity, speed, and infrastructure cost.

#### What we found

The picture is nuanced — different page types have different rendering requirements:

| Page Type | Rendering | Scraping Tool |
|-----------|-----------|---------------|
| gkmlpt index/listing pages | JavaScript SPA (Vue.js) | Playwright, or reverse-engineered API (preferred) |
| gkmlpt content/detail pages | Server-rendered HTML | Simple HTTP (Scrapy/requests) |
| Main portal listing pages | Unknown | Not yet testable |
| Main portal content pages | Likely server-rendered | Not yet testable |

The critical implication: if the gkmlpt JSON API can be reverse-engineered (see Stage 2), Playwright may not be needed at all. Content pages are definitely server-rendered, and API-based listing discovery would bypass the SPA entirely. This is why the API discovery task is highest priority — it determines the entire tool chain.

---

### 3.9 Cross-Cutting: Existing Work and Precedent

#### The consideration

Others may have already solved parts of this problem.

#### What we found

**UC San Diego China Policy Document Navigator** (portals.igcc.sdsc.edu). Developed by IGCC and the China Data Lab at UCSD's 21st Century China Center. Contains tens of thousands of science & technology policy documents across national, provincial, and prefectural levels. Offers keyword search in Chinese and English, date filtering, issuing department and province filters, topic modeling across 13 themes, and visual dashboards. Metadata is exportable; full-text available by request. Hosted at UCSD Supercomputer Center. This is the closest existing project to our goals, but limited to S&T policy specifically. Their crawling and extraction methodology is directly relevant.

**"Mitigating Missingness in Analysing Chinese Policy" (Cambridge Quarterly).** Researchers scraped 80+ government portals via their 政务公开 sections. Key findings: they used policy cross-references (documents citing other documents) as a primary analytical tool — exactly the analysis we want to enable. They found that some sites have implemented retrieval restrictions (the MFA limits search results to 1,000). They noted missingness is a real problem — not all documents that exist are publicly posted. They compared scraped data to PKULaw (a commercial legal database) and found ~1–5% discrepancies.

**CAPC-CG Corpus** (arXiv 2510.08986). Central government documents 1949–2023, containing 3.3 million paragraph units annotated with a five-color taxonomy of policy communication clarity. Fleiss's kappa of 0.86 for inter-annotator agreement.

**Other relevant datasets:** A Multi-level Supportive Policy Dataset for China's Resource-Based Cities (2003–2023), a Chinese Agricultural Policy Corpus (1982–2023), and various provincial/sectoral collections.

#### What we decided

We are not building from zero. The UCSD group in particular has likely solved many of the same technical problems. Reaching out for methodology sharing or collaboration is worth pursuing — their S&T focus is narrower than our ambition, but the crawling/extraction infrastructure should be transferable. The Cambridge paper validates that cross-reference analysis is analytically powerful, reinforcing the priority of document number (文号) extraction.

---

### 3.10 Cross-Cutting: Legal Considerations

#### What we investigated

We encountered a Zhihu discussion referencing the Chinese legal framework for web scraping of government sites.

#### What we found

Government information disclosure (政府信息公开) is a legal mandate — these documents are published specifically for public access. The 2019 draft Data Security Management Measures specify that automated access should not exceed one-third of a site's daily traffic and must cease if the site operator requests it. Personal information protection rules are irrelevant here (government policy documents, not personal data). The primary legal risks — personal data collection, circumventing access controls, causing service disruption — don't apply to polite crawling of publicly disclosed government documents.

#### What we decided

Minimal legal risk. The crawler should be polite (reasonable delays, respect for robots.txt where it exists), use an identifiable user-agent string, and avoid overloading any single server.

---

### 3.11 Cross-Cutting: Scalability Beyond Shenzhen

#### What we found

The gkmlpt platform is not Shenzhen-specific — we confirmed the identical platform on Guangzhou's Conghua district (conghua.gov.cn). This is a Guangdong province-level standard, probably built by Digital Guangdong (数字广东). Once the gkmlpt parser works for Shenzhen, it generalizes to other Guangdong cities with minimal modification.

Beyond Guangdong, the 2017 State Council Government Website Development Guidelines (政府网站发展指引) mandated consolidation and standardization across all government websites. This means the number of distinct CMS templates nationally is probably in the range of 5–15, not hundreds. Each new template requires a custom parser, but the cost of coverage scales sub-linearly.

---

## 4. Remaining Actions Before Implementation

These are ordered by priority and labeled by whether they require human action or can be automated.

**Action 1 — Discover gkmlpt API endpoints (automatable, highest priority).** Write a Playwright script that navigates to `http://www.szpsq.gov.cn/psozhzx/gkmlpt/index`, intercepts all network requests via `page.on('request')` / `page.on('response')`, triggers pagination and search interactions, and logs every API endpoint URL with parameters and response bodies. ~40 lines of code. Determines whether Playwright is needed at all for production crawling. Can be done by a coding agent with network access.

**Action 2 — Verify subdomain inventory (automatable).** Navigate to sz.gov.cn's department links page or annual website report, extract all department/district website URLs. Confirms or corrects the inferred list.

**Action 3 — Inspect main portal content pages (automatable).** Fetch sample `mpost_` URLs from sz.gov.cn via HTTP. Determine whether the metadata format matches gkmlpt or requires a separate parser.

**Action 4 — Sample attachment prevalence (automatable).** Fetch 50–100 random gkmlpt content pages, count how many contain PDF/DOC attachment links vs. inline HTML. Determines whether PDF extraction is needed for MVP.

**Action 5 — Register for Open Data API (requires human).** Account creation on opendata.sz.gov.cn likely involves CAPTCHA and phone verification. Once an appKey is obtained, everything downstream (testing endpoints, evaluating coverage) is automatable. This is optional — the Open Data API may provide a cleaner path to some documents but isn't the primary crawling strategy.

---

## 5. Key Technical Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| MVP scope | Shenzhen constellation | Proves generalization across heterogeneous sites within one city |
| Primary crawl target | gkmlpt platform sections | Standardized across departments/districts; single parser; province-wide standard |
| Network protocol | HTTP (not HTTPS) | HTTPS fails with BAD_ECPOINT across all Shenzhen sites; HTTP works |
| Listing discovery | API reverse-engineering (preferred) | gkmlpt index is a Vue.js SPA — backend API must exist |
| Listing discovery fallback | Playwright headless browser | If API is protected or uses encrypted parameters |
| Content extraction | Scrapy or requests + BeautifulSoup | Content pages are server-rendered HTML; no JS needed |
| Storage | PostgreSQL + filesystem for raw HTML | Modest scale at MVP (tens of thousands of documents) |
| LLM processing | Batch, decoupled from crawling | Separates crawling throughput from API costs/rate limits |
| Deployment | China-based VPS recommended | May resolve SSL; avoids GFW latency. Not blocking — HTTP works from anywhere |

---

## 6. Risk Register

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| gkmlpt API is authenticated or uses encrypted parameters | Low | High — forces Playwright for all listing discovery | Most Chinese gov platforms use open APIs; authentication contradicts the accessibility mandate these platforms exist to fulfill |
| Rate limiting blocks the crawler | Medium | Medium — slows but doesn't prevent collection | Polite delays (2–3s between requests), rotating across subdomains, off-peak crawling |
| Content is primarily PDF attachments rather than inline HTML | Medium | Medium — requires OCR/PDF extraction pipeline | Action 4 (attachment sampling) resolves this before architecture is committed |
| Main portal uses a different CMS than gkmlpt | High (likely) | Low — requires one additional parser | Main portal is a single site; a dedicated parser is manageable |
| Government blocks access from outside China | Medium | High for non-China deployment | China-based VPS solves this; HTTP access already confirmed working from outside |
| Site structure changes mid-crawl | Low | Low | Store raw HTML for re-parsing; version-pin parsers |
| UCSD project already covers our scope | Low | Positive — potential collaboration | Their S&T focus is narrower; our scope is broader |