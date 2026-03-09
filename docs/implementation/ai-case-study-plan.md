# AI Policy Case Study — Implementation Plan

## Context

We're building the first end-to-end policy chain as a proof of concept for ROADMAP MVP 1. The case study: **What is Shenzhen actually doing about AI?**

### What we found in the corpus (updated after Steps 1-2)

- **113 documents** related to AI across 16 departments/districts
- **87 now have body text** (76%, up from 2% before backfill)
- **57 named policy citations** (《》 brackets) + **11 formal 文号 citations** extracted
- **40 unique referenced policy documents** identified across all admin levels
- **Key finding:** Most AI policy citations use named references, not formal 文号 numbers. The municipal-level AI plans are NOT in our corpus — they're referenced from district documents but published elsewhere.
- **Longhua district** is the standout: 30 AI documents, three generations of formal policy (2021, 2024 measures + 2024 action plan), all referencing the municipal AI strategy

### The policy chain we can already partially see

```
Central:  State Council "AI+" action opinions (国办发, referenced in news articles)
    ↓
Municipal:  深圳市加快推动人工智能高质量发展高水平应用行动方案（2023-2024年）
    ↓         (referenced by name in Longhua doc, but not yet in corpus by 文号)
District:  深龙华府办规〔2024〕20号 — Longhua AI + robotics measures
           深南府办函〔2023〕48号 — Nanshan AI implementation plan
           深坪 — Pingshan AI + software support measures (draft, 2025)
```

### What's missing

1. Body text for 87/89 AI-titled documents — can't extract citations without it
2. The municipal-level AI plan itself (may not have a formal 文号, or may be referenced differently)
3. Central-level directives (not in our corpus, but we can identify them from citations)
4. Thematic connections between AI docs that don't cite each other explicitly

---

## Goal

Produce a complete, navigable policy chain for AI in Shenzhen — from central directives down to district implementation — as the proof of concept for the "vertical-to-horizontal translator" vision.

**Done when:** A user can visit a page on the web app, see the AI policy chain laid out hierarchically, click into any document, and understand who issued what, when, in response to which higher-level directive.

---

## Step 1: Targeted Body Text Backfill

### What

Fetch body text for all AI-related documents that are missing it. This is the foundation — we can't extract citations or build chains without body text.

### How

The crawler already has `backfill_bodies()` (crawler.py:545). But we need a more targeted approach:

1. **Identify all AI-relevant document IDs** — not just title matches but also documents that mention AI in their keywords, abstract, or classification.

2. **Write a targeted backfill script** (`scripts/backfill_ai.py`) that:
   - Queries for AI-relevant doc IDs where body_text_cn is NULL or empty
   - Fetches each document's content page
   - Extracts body text using the existing `extract_body_text()` function
   - Saves raw HTML to `raw_html/`
   - Updates the database
   - Logs success/failure for each document

3. **Run it and measure coverage.** Target: body text for >80% of the 89 AI-titled docs. Some may genuinely have no extractable body (e.g., infographics, PDFs only).

### Queries to identify the full AI-relevant set

```sql
-- Title match
SELECT id FROM documents WHERE title LIKE '%人工智能%';

-- Keyword match
SELECT id FROM documents WHERE keywords LIKE '%人工智能%';

-- Broader: "智能" (intelligent/smart) in policy docs
SELECT id FROM documents
WHERE title LIKE '%智能%'
  AND document_number IS NOT NULL AND document_number <> '';

-- Docs that cite known AI policy doc numbers
-- (run after body text extraction)
SELECT id FROM documents
WHERE body_text_cn LIKE '%龙华府办规〔2024〕20%'
   OR body_text_cn LIKE '%龙华府办规〔2021〕9%';
```

### Done when

- [x] Body text extracted for >80% of AI-titled documents (87/113 = 76%)
- [x] Success/failure logged for each document (84 succeeded, 26 failed — all external URLs)
- [x] We know how many of these contain citations to other documents (57 named + 11 formal)

---

## Step 2: Citation Extraction + Chain Construction

### What

Extract all 文号 citations from the AI-related documents, classify them by administrative level, and build the chain.

### How

1. **Run existing citation extraction** (`analyze.py` regex patterns) on the newly backfilled AI documents.

2. **Identify the municipal-level AI plan.** The Longhua 2024 doc references `《深圳市加快推动人工智能高质量发展高水平应用行动方案（2023-2024年）》` by name. We need to:
   - Search the corpus for this document (it may exist without "人工智能" in its indexed title)
   - If not in corpus, note it as an external reference and record its metadata manually

3. **Identify central-level directives.** Scan AI doc body text for central-level 文号 patterns (国发, 国办发, etc.) related to AI. Known candidates:
   - 国办发〔2025〕24号 (referenced in corpus, may be AI-related)
   - Any "人工智能+" action plan references

4. **Build a citations table** specific to the AI chain:

   | Source Doc | Source Level | Cites | Cited Level | Citation Type |
   |-----------|-------------|-------|-------------|---------------|
   | 深龙华府办规〔2024〕20号 | district | 深圳市AI行动方案 | municipal | by name |
   | 深龙华府办规〔2024〕20号 | district | 深府办规〔2022〕3号 | municipal | by 文号 |
   | ... | ... | ... | ... | ... |

### Done when

- [x] All citations extracted from AI-relevant documents (57 named + 11 formal)
- [x] Municipal-level AI plan identified (NOT in corpus — referenced by name from district docs)
- [x] Central-level AI directives identified from citations (3 central, 2 provincial)
- [x] Chain data structured and stored (`data/ai_chain.json`)

---

## Step 3: Policy Chain View in Web App

### What

A new page in the web app that visualizes the AI policy chain.

### How

1. **New route: `/chain/ai`** (or `/chain?topic=ai` if we want to generalize later)

2. **Layout:** Vertical hierarchy, top to bottom:
   - **Central level** — State Council / ministry directives (may be external links since we don't have these in corpus)
   - **Municipal level** — Shenzhen citywide AI plans
   - **District level** — Longhua, Nanshan, Pingshan, etc. implementation documents
   - **Department level** — S&T Innovation Bureau, Development & Reform Commission, etc. notices and actions

3. **Each node shows:** Title, 文号, date, issuing body, and a link to the full document detail page.

4. **Connections:** Lines between documents that cite each other, labeled with citation type (explicit 文号 vs. by-name reference).

5. **Timeline overlay:** Optional view showing when each response was published relative to the parent directive.

### Done when

- [x] `/chain/ai` page renders the hierarchy (4 levels, 40 policies, 87 source docs)
- [x] Clicking any document goes to its detail page (links to `/document/{id}`)
- [x] Central/external references are clearly marked ("external" vs "in corpus")
- [ ] Timeline view shows propagation timing (deferred — nice to have)

---

## Step 4: Translation of the AI Chain

### What

Translate the AI policy chain documents to English so the target audience (Western analysts) can actually use it.

### How

1. **LLM translation** of titles and body text for all documents in the AI chain. Start with the formal policy documents (those with 文号), then expand to supporting notices.

2. **Translation approach:** Use Claude API with a prompt tuned for Chinese government document translation. Key considerations:
   - Preserve document numbers (文号) untranslated
   - Translate official body names consistently (e.g., 龙华区科技创新局 → "Longhua District S&T Innovation Bureau" — match existing translations in the web app)
   - Include translator's notes for terms that don't have clean English equivalents

3. **Store translations** in `body_text_en` column (already exists in schema) and a new `title_en` column.

4. **Update web app** to show English translations alongside Chinese originals on the chain page and document detail pages.

### Done when

- [ ] All formal AI policy documents translated
- [ ] Translations spot-checked by a Chinese reader
- [ ] Chain page shows English titles and summaries
- [ ] Document detail page has Chinese/English toggle

---

## Step 5: Write-Up

### What

A short analytical write-up that demonstrates the insight this chain reveals. This is the artifact that makes the project legible to someone who isn't going to explore the web app themselves.

### How

Publish a page (on the site or as a standalone document) that walks through:
1. What the State Council said about AI
2. How Shenzhen translated that into a municipal plan
3. How individual districts (Longhua, Nanshan, Pingshan) implemented it differently
4. What the timing reveals about policy propagation speed
5. What Longhua's 2021→2024 revision reveals about policy evolution

This is the thing you'd send to someone at MERICS or CSIS to demonstrate the project's value.

### Done when

- [x] Write-up published on the site (`/analysis/ai`)
- [x] Includes specific document citations with links (Longhua 2021, 2024 policies, chain page)
- [x] Readable by someone with no Chinese language ability
- [x] Makes a non-obvious observation about Chinese AI governance (Longhua anomaly, subsidy specifics, policy evolution 2021→2024)

---

## Multi-Level Crawler Infrastructure (added 2026-02-28)

The AI case study depends on having documents at every level of the policy chain. Here's where the crawler infrastructure stands.

### Crawlers built

| Level | Crawler | API/Approach | Status |
|-------|---------|-------------|--------|
| **Central** | `crawlers/ndrc.py` | Static HTML, `createPageHTML()` pagination, 5 sections under `/xxgk/zcfb/` | Built. 500 docs indexed (metadata only, zero body text). |
| **Central** | `crawlers/gov.py` | JSON feed at `gov.cn/zhengce/zuixin/ZUIXINZHENGCE.json`. Two HTML templates for doc pages (Template A: formal with metadata table; Template B: article-style). Both share `#UCAP-CONTENT` for body. | Built. 1,003 docs indexed (metadata only, zero body text). |
| **Provincial** | `crawlers/gkmlpt.py` site `gd` | Same gkmlpt API as Shenzhen. SID confirmed: 2. **Requires browser User-Agent** — default crawler UA gets connection reset. | Configured, never crawled. |
| **Municipal** | `crawlers/gkmlpt.py` sites `sz` + 13 depts | gkmlpt API. 20 Shenzhen sites. | Crawled. 37,384 docs, ~5,500 with body text. |
| **Municipal (other)** | `crawlers/gkmlpt.py` sites `gz`, `zhuhai`, `huizhou`, `jiangmen` | Same gkmlpt API. SIDs confirmed: Guangzhou 200001, Zhuhai 756001, Huizhou 752001, Jiangmen 750001. | Configured, never crawled. All reachable as of 2026-02-28. |
| **District** | `crawlers/gkmlpt.py` 6 district sites | Same gkmlpt API. | Crawled. 7,746 docs, ~1,000 with body text. |

### Reachability (tested 2026-02-28)

```
Central - NDRC:          OK (41,665 bytes)
Central - Gov.cn:        OK (186,455 bytes)
Provincial - Guangdong:  OK with browser UA (28,673 bytes) — FAILS with default crawler UA
Municipal - Guangzhou:    OK (19,626 bytes)
Municipal - Zhuhai:       OK (17,851 bytes)
```

### Database inventory (updated 2026-03-02)

```
Total: 46,636 docs, 39,007 with body text (83.6%)
```

**By level:**

| Level | Sites | Docs | Body text | Coverage |
|-------|-------|------|-----------|----------|
| Central | NDRC, State Council | 1,505 | 20 | 1% |
| Municipal | Shenzhen Main Portal | 844 | 844 | 100% |
| Department | 13 Shenzhen bureaus | 33,280 | 29,650 | 89% |
| District | 6 Shenzhen districts | 10,957 | 8,998 | 82% |
| Provincial | — | 0 | 0 | — |
| Other cities | — | 0 | 0 | — |

**Per-site detail (department + district):**

| Site | Docs | Body | % | Notes |
|------|------|------|---|-------|
| Public Security Bureau (ga) | 5,010 | 4,930 | 98% | |
| Longhua District (szlhq) | 6,134 | 5,906 | 96% | AI policy hotspot |
| Health Commission (wjw) | 1,238 | 1,172 | 95% | |
| Education Bureau (szeb) | 1,999 | 1,878 | 94% | |
| Luohu District (szlh) | 759 | 705 | 93% | |
| Emergency Mgmt (yjgl) | 1,996 | 1,816 | 91% | |
| Civil Affairs (mzj) | 5,015 | 4,447 | 89% | |
| Audit Bureau (audit) | 470 | 417 | 89% | |
| Guangming District (szgm) | 905 | 804 | 89% | |
| Transport (jtys) | 2,843 | 2,543 | 89% | |
| Housing & Construction (zjj) | 2,353 | 2,081 | 88% | |
| Commerce (swj) | 2,889 | 2,530 | 88% | |
| Justice (sf) | 2,019 | 1,753 | 87% | |
| HR & Social Security (hrss) | 3,236 | 2,802 | 87% | |
| Pingshan District (szpsq) | 1,636 | 1,269 | 78% | |
| Nanshan District (szns) | 309 | 203 | 66% | Many /xxgk/ pages |
| S&T Innovation (stic) | 2,710 | 1,658 | 61% | |
| Futian District (szft) | 214 | 111 | 52% | Many external URLs |
| Dev & Reform (fgw) | 2,552 | 1,118 | 44% | DNS timeouts during backfill |

**Not yet crawled:**
- Guangdong Province (`gd.gov.cn`) — configured, needs browser UA
- Guangzhou, Zhuhai, Huizhou, Jiangmen — configured, never crawled

### Backfill history (2026-03-01 → 2026-03-02)

The gkmlpt body text backfill ran overnight on March 1-2. Key events:

1. **Parallel attempt failed** — 9 concurrent processes all hit `database is locked` (SQLite single-writer limitation)
2. **Serial backfill worked** — single process at 0.3s delay, ~0.6 docs/s
3. **URL filter fix** — original query included non-gkmlpt URLs (WeChat, NDRC, etc.). Fixed to `url LIKE '%gkmlpt%'`
4. **Surrogate crash** — `UnicodeEncodeError` on one page's invalid UTF-16 surrogates. Fixed with `.encode('utf-8', errors='replace')`
5. **Result:** 6,819 → 39,007 body texts (14.6% → 83.6%) in ~19 hours

**Code changes applied to `crawlers/gkmlpt.py`:**
- Browser UA for Guangdong Province (`SITES_NEEDING_BROWSER_UA`)
- Two fallback extraction patterns (Nanshan `tyxxy_main`, gazette `news_cont_d_wrap`)
- Better backfill logging with `--backfill-delay` CLI arg
- URL filter: only process gkmlpt URLs, skip external/non-gkmlpt
- Surrogate sanitization: `body_text.encode('utf-8', errors='replace').decode('utf-8')`

Full crawl log: `docs/log/crawl-log-mar-1.md`

### Remaining to reach ~90%+

1. **NDRC body text** — `python3 -m crawlers.ndrc` (500 docs, ~15 min). Crawler built, never fetched pages.
2. **State Council body text** — `python3 -m crawlers.gov` (985 docs, ~30 min). Crawler built, only 20/1005 have body.
3. **Dev & Reform re-try** — `python3 -m crawlers.gkmlpt --backfill-bodies --site fgw` (1,434 still missing, DNS issues during overnight run)
4. **Citation re-extraction** — `python3 scripts/extract_citations.py --force`
5. **Guangdong Province** — `python3 -m crawlers.gkmlpt --site gd` (new corpus, unknown size)

The ~5,500 external URLs (WeChat, Xinhua, CCTV, etc.) will never have body text — they represent the hard ceiling at ~88%.

---

## Build Order

```
Step 1 (backfill) → Step 2 (citations) → Step 3 (web view) → Step 4 (translation) → Step 5 (write-up)
                                            ↑ can start design in parallel
```

Step 1 is the gating task. Everything downstream depends on having body text.

Steps 3 and 4 can be worked on in parallel once step 2 is done — the chain view can initially show Chinese text, with English added later.

Step 5 depends on steps 3 and 4 being complete.
