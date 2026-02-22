# China Governance Crawler — Execution Plan

## MVP Goal

A working end-to-end pipeline for Shenzhen that crawls government documents from the gkmlpt platform, extracts structured metadata + body text, translates to English, tags by topic, and produces at least one concrete analytical output — e.g., *"Which State Council documents were most cited by Shenzhen departments in 2024?"*

**Scope:** Main portal + 13 department sites + 6 district sites, documents from 2015–present. Tens of thousands of documents total.

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

### Status: COMPLETE ✅

### Tasks

1. **Discover gkmlpt API endpoints** ✅ DONE
   - API: `/gkmlpt/api/all/{category_id}?page={page_num}&sid={site_id}`
   - Returns rich JSON: 30+ fields per document including title, 文号, publisher, keywords, dates, attachments, classification, abstract
   - 100 items per page. Categories provide post_count for total.
   - Discovered by analyzing Vue.js bundle source code (Playwright failed due to slow page loads from outside China)

2. **Verify subdomain inventory** ✅ DONE
   - Scanned 30 known Shenzhen gov domains for /gkmlpt/index endpoints
   - Found 16 working gkmlpt sites beyond the original 6 (20 total)
   - 12 municipal departments + 1 main portal + 6 districts + 1 public security bureau

3. **Inspect main portal content pages** ✅ DONE
   - Main portal content uses NFCMS CMS (different from gkmlpt)
   - BUT main portal ALSO has /gkmlpt/index with working API (SID=755001, 4,176 docs)
   - So the API path works for the main portal too

4. **Sample attachment prevalence** ✅ DONE
   - ~10% of documents have attachments (PDF, DOCX)
   - Attachment URLs are included in the API response (no HTML parsing needed)

### Done When

- [x] We have the gkmlpt API endpoint URL, its pagination parameters, and a sample JSON response
- [x] We have a verified list of all Shenzhen gov subdomains with gkmlpt
- [x] We know whether the main portal needs a separate parser
- [x] We have a percentage for attachment prevalence

---

## Goal 2: Listing Discovery — Enumerate All Document URLs

### Status: COMPLETE ✅

Built into `crawler.py`. The API paginator (`crawl_category()`) calls `/gkmlpt/api/all/{cat_id}?page=N&sid=S`, paginates through all pages (100 items/page), and collects full article metadata. Works identically across all gkmlpt sites.

### Done When

- [x] Running listing discovery against one department produces a complete list of document URLs
- [x] URL count matches post_count from API (verified on Pingshan: 1,636 unique docs)
- [x] Same code works across 20 sites without modification

---

## Goal 3: Content Extraction — Parse Individual Documents

### Status: COMPLETE ✅

Metadata comes from the API (30+ fields per document, richer than HTML parsing). Body text extracted from `_CONFIG.DETAIL.content` in each content page's HTML. Built into `crawler.py` as `extract_body_text()` and `fetch_document_body()`.

### Done When

- [x] All metadata fields extracted from API (30+ fields including 索引号, 文号, publisher, keywords, dates, classification, attachments)
- [x] Body text extraction produces clean Chinese text (tested on 3+ pages across different departments)
- [x] Attachment URLs included in API response (no HTML parsing needed); ~10% prevalence, PDF extraction deferred

---

## Goal 4: Storage — Structured Database + Raw Archive

### Status: COMPLETE ✅

Using SQLite (not PostgreSQL — simpler for MVP, trivially handles the scale). Schema in `crawler.py` `init_db()`. Raw HTML saved to `raw_html/{site_key}/{doc_id}.html`.

**Current corpus: 45,130 documents across 20 sites. 1,456+ with body text (backfill running). 4,255 with 文号.**

### Done When

- [x] Ingest 1,000+ documents and query by department, date range, keyword (45,130 docs ingested)
- [x] No duplicate documents (ON CONFLICT DO UPDATE handles deduplication by doc ID)
- [x] Raw HTML recoverable for any document (saved to filesystem)

---

## Goal 5: LLM Processing — Translation, Tagging, Cross-References

### Status: PARTIALLY ADDRESSED

Cross-reference extraction (文号 pattern matching) is already working WITHOUT an LLM — implemented via regex in `analyze.py`. Translation and topic tagging still need an LLM API key.

### Tasks

1. ~~Extract referenced document numbers (文号)~~ ✅ Done with regex
2. Design a single LLM prompt per document that returns:
   - English translation
   - Topic tags (aligned with UCSD's 13 S&T themes or similar taxonomy)
   - Extracted entities (people, organizations, policies)
3. Batch-process all stored documents (decoupled from crawling)
4. Estimate cost: tokens per document × document count × price per token

### Done When

- [ ] Translation quality spot-checked on 20+ documents by a Chinese reader
- [ ] Topic tags are consistent across similar documents
- [x] Cross-reference extraction correctly identifies 文号 patterns (e.g., "深府〔2024〕15号")

---

## Goal 6: First Analytical Output — Prove the Thesis

### Status: STRONG RESULTS ✅

Built `analyze.py` with cross-reference analysis, citation network, category breakdown, and timeline. Results from 1,456 documents with body text across 6 sites:

- **38% of documents** contain cross-references to other government documents
- **1,535 total cross-references** extracted
- **Top cited:** 国发〔2012〕52号 (28 citations — State Council administrative reform)
- **Citation hierarchy:** 37.5% municipal, 25.7% central, 12.6% provincial, 9.8% district
- **Cross-site citations visible:** 国发〔2015〕3号 cited by 3 different sites
- **Ministry-to-district propagation:** Ministry of Housing docs cited by both Guangming + Pingshan districts

### Done When

- [x] Output is concrete, interpretable, and novel (cross-reference hierarchy already visible)
- [x] Cross-references trace back to verifiable central government documents (State Council doc numbers confirmed)
- [x] Result demonstrates something genuinely difficult to know without this system (policy propagation from central → local visible)
- [x] Citation network analysis shows which departments cite which levels of government

---

## Key Technical Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| MVP scope | Shenzhen constellation (20 sites) | Proves generalization across heterogeneous sites |
| Primary crawl target | gkmlpt platform sections | Standardized; single parser; province-wide standard |
| Network protocol | HTTP (not HTTPS) | HTTPS fails with BAD_ECPOINT; HTTP works |
| Listing discovery | API reverse-engineering | gkmlpt index is Vue.js SPA — API in JS bundle |
| Content extraction | urllib + regex | Content pages are server-rendered; no JS needed |
| Storage | SQLite + filesystem | Simpler than PostgreSQL; handles 45K docs trivially |
| Cross-references | Regex (not LLM) | 文号 format is predictable; regex is fast and free |
| LLM processing | Batch, decoupled from crawling | Separates throughput from API costs |
| Deployment | Works from anywhere | HTTP access confirmed from US |
