# China Governance Crawler — Execution Plan

## MVP Goal

A working end-to-end pipeline for Shenzhen that crawls government documents from the gkmlpt platform, extracts structured metadata + body text, translates to English, tags by topic, and produces at least one concrete analytical output — e.g., *"Which State Council documents were most cited by Shenzhen departments in 2024?"*

**Scope:** Main portal + 3–4 department sites + 2 district sites, documents from 2020–present. Tens of thousands of documents total.

---

## Dependency Chain

```
Goal 1 (Recon) → Goal 2 (Listing) → Goal 3 (Extraction) → Goal 4 (Storage) → Goal 5 (LLM) → Goal 6 (Analysis)
                                      ↑ parallel design ↑     ↑ parallel design ↑
```

Goals 3 and 4 can be designed in parallel once Goal 1 resolves key unknowns. Goal 5 prompt design can also begin in parallel.

**Single gating task:** Goal 1's API discovery — determines the entire architecture of Goal 2.

---

## Goal 1: Reconnaissance — Resolve Remaining Unknowns

### Status: NOT STARTED

### Tasks

1. **Discover gkmlpt API endpoints** (HIGHEST PRIORITY)
   - Write a Playwright script (~40 lines) that navigates to a gkmlpt index page (e.g., `http://www.szpsq.gov.cn/psozhzx/gkmlpt/index`)
   - Intercept all XHR/Fetch requests via `page.on('request')` / `page.on('response')`
   - Trigger pagination and search interactions
   - Log every API endpoint URL with parameters and response bodies

2. **Verify subdomain inventory**
   - Scrape the department navigation page on sz.gov.cn
   - Or find the annual website report (政府网站年度工作报表)
   - Produce a verified list of all ~48 Shenzhen gov subdomains

3. **Inspect main portal content pages**
   - Fetch sample `mpost_` URLs from sz.gov.cn via HTTP
   - Determine if metadata format matches gkmlpt or requires a separate parser

4. **Sample attachment prevalence**
   - Fetch 50–100 random gkmlpt content pages
   - Count how many contain PDF/DOC attachment links vs. inline HTML only
   - Determines whether PDF extraction is day-one work

### Done When

- [ ] We have the gkmlpt API endpoint URL, its pagination parameters, and a sample JSON response
- [ ] We have a verified list of all Shenzhen gov subdomains
- [ ] We know whether the main portal needs a separate parser
- [ ] We have a percentage for attachment prevalence

---

## Goal 2: Listing Discovery — Enumerate All Document URLs

### Status: NOT STARTED (blocked by Goal 1)

### Tasks

1. **If API found in Goal 1:** Build an HTTP-based paginator that calls the gkmlpt JSON API and collects all `post_{id}.html` URLs per department/district
2. **If API is protected:** Build a Playwright-based scraper that renders the Vue.js SPA and extracts listings
3. **For the main portal:** Build a separate listing crawler (category page crawling or sequential ID enumeration depending on Goal 1 findings)

### Done When

- [ ] Running listing discovery against one department produces a complete list of document URLs
- [ ] URL count roughly matches expected range based on post ID analysis (~9M in 2021 to ~12M in 2025)
- [ ] Same code works across at least 3 different department prefixes without modification

---

## Goal 3: Content Extraction — Parse Individual Documents

### Status: NOT STARTED (can begin design in parallel after Goal 1)

### Tasks

1. Build a parser (requests + BeautifulSoup or Scrapy) that fetches a gkmlpt content page over HTTP and extracts:
   - 8 standardized metadata fields: 索引号, 分类, 发布机构, 成文日期, 名称, 文号, 发布日期, 主题词
   - Body text
   - Attachment URLs
2. Handle edge cases: empty 文号, older URLs without department prefix, varied content types
3. If attachment prevalence >20%, build PDF text extraction

### Done When

- [ ] Parser correctly extracts all 8 metadata fields from 50+ pages across 3+ departments/districts with zero field misses
- [ ] Body text extraction is clean (no UI chrome, print buttons, social sharing markup)
- [ ] If needed, PDF text extraction works

---

## Goal 4: Storage — Structured Database + Raw Archive

### Status: NOT STARTED (can begin design in parallel after Goal 1)

### Tasks

1. Design PostgreSQL schema:
   - source_url, domain, admin_level, department, title, document_number (文号)
   - date_written, date_published, publishing_organ, keywords, category
   - body_text_cn, body_text_en, topic_tags, referenced_documents, crawl_timestamp
2. Set up filesystem archive for raw HTML (organized by domain/crawl date)
3. Build ingestion pipeline: parser output → database

### Done When

- [ ] Ingest 1,000+ documents and query by department, date range, keyword
- [ ] No duplicate documents in the database
- [ ] Raw HTML recoverable for any document

---

## Goal 5: LLM Processing — Translation, Tagging, Cross-References

### Status: NOT STARTED (prompt design can begin in parallel)

### Tasks

1. Design a single LLM prompt per document that returns:
   - English translation
   - Topic tags (aligned with UCSD's 13 S&T themes or similar taxonomy)
   - Extracted entities (people, organizations, policies)
   - Referenced document numbers (文号)
2. Batch-process all stored documents (decoupled from crawling)
3. Estimate cost: tokens per document × document count × price per token

### Done When

- [ ] Translation quality spot-checked on 20+ documents by a Chinese reader
- [ ] Topic tags are consistent across similar documents
- [ ] Cross-reference extraction correctly identifies 文号 patterns (e.g., "深府〔2024〕15号")

---

## Goal 6: First Analytical Output — Prove the Thesis

### Status: NOT STARTED (blocked by Goals 1–5)

### Tasks

1. Query the corpus: *Which State Council / central government documents were most frequently cited by Shenzhen departments in 2024?*
2. Visualize the result (table or chart: top-cited central documents with citation counts by department)

### Done When

- [ ] Output is concrete, interpretable, and novel to a China policy researcher
- [ ] Cross-references trace back to verifiable central government documents
- [ ] Result demonstrates something genuinely difficult to know without this system

---

## Key Technical Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| MVP scope | Shenzhen constellation | Proves generalization across heterogeneous sites |
| Primary crawl target | gkmlpt platform sections | Standardized; single parser; province-wide standard |
| Network protocol | HTTP (not HTTPS) | HTTPS fails with BAD_ECPOINT; HTTP works |
| Listing discovery | API reverse-engineering (preferred) | gkmlpt index is Vue.js SPA — backend API must exist |
| Listing fallback | Playwright headless browser | If API is protected |
| Content extraction | requests + BeautifulSoup or Scrapy | Content pages are server-rendered; no JS needed |
| Storage | PostgreSQL + filesystem | Modest scale at MVP |
| LLM processing | Batch, decoupled from crawling | Separates throughput from API costs |
| Deployment | China-based VPS recommended | Not blocking — HTTP works from anywhere |
