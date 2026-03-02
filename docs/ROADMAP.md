# CNGOV Roadmap

## Target Audience

**Western China analysts and researchers** — people at think tanks (MERICS, CSIS, Brookings), in academia (political science, comparative politics, development economics), and in corporate government affairs roles at multinationals operating in China.

### Their problem

They can read central government policy (State Council directives, Five-Year Plans) but have **no systematic visibility into local implementation**. When the State Council issues a directive on AI regulation, what does Shenzhen actually *do*? How does Shenzhen's implementation differ from Guangzhou's? Which districts move first? Currently, answering these questions requires manually checking dozens of Chinese government websites, reading Chinese, and mentally stitching together the connections. Researchers like David Yang et al. spent years manually linking 19,812 documents across administrative levels — work that a well-structured database could compress to weeks.

The information drought is getting worse: MERICS documents that policy transparency from the State Council peaked around 2015 and has been declining since. Archiving and contextualizing what IS published becomes more valuable as the window narrows.

### What they need

A way to see **how policy flows through China's administrative hierarchy** — from central to provincial to municipal to district — in English, searchable, with sources they can verify against the originals.

### Why us

Nobody does the multi-level mapping well. China Horizons (CBS/MERICS) covers central-level only. DigiChina (Stanford) covers tech policy only. The academic literature does one-off manual efforts. We provide the *infrastructure* for this kind of analysis: structured, searchable, linked, translated, and open.

---

## Vision (Launch State)

A public website where a Western analyst can:

1. **Search** Chinese local government documents in English
2. **Trace** a policy from its central government origin through provincial and municipal implementation down to district-level action
3. **Compare** how different departments and districts implement the same directive
4. **Discover** local policy experiments and innovations that haven't reached central-level attention

Backed by a verified, archived corpus with direct links to original government sources.

---

## What We Have Now (updated 2026-02-23)

- **46,633 documents** from 22 government sites (20 Shenzhen + 2 central: State Council, NDRC)
- **14,834 citation edges** extracted via regex (formal 文号 + named 《》 references)
- **Working web app** with 9 pages: browse, search, document detail, citation network (D3.js), dashboard, policy chains (6 topics), AI analysis write-up, side-by-side comparison
- **7 JSON API endpoints** under `/api/v1/`
- **Citation hierarchy classified** by administrative level (central/provincial/municipal/district)
- **Verification infrastructure**: SHA-256 hashes, direct links to originals, side-by-side comparison
- **Live deployment** at [chinagovernance.com](https://www.chinagovernance.com) on Railway (PostgreSQL + Docker)
- **Dual-mode database**: PostgreSQL in production, SQLite for local development
- **AI policy case study**: end-to-end proof of concept — backfill, citation extraction, chain view, analytical write-up
- **Subsidy analysis pipeline**: multi-keyword matching, regex extraction of yuan amounts, sector attribution, report page at `/analysis/subsidies`
- **Incremental sync**: `--sync` flag detects new/changed/deleted documents without overwriting originals; change history at `/changes`

See `docs/implementation/crawler-plan.md`, `docs/implementation/web-plan.md`, and `docs/implementation/ai-case-study-plan.md` for details on what's been built.

---

## MVP 1: Complete the Corpus + Explicit Policy Chains

**Goal:** Make the existing citation network *useful* by filling in body text gaps and surfacing policy chains in the UI.

**The problem right now:** Only ~15% of documents have body text extracted. Citation analysis depends on body text (that's where the 文号 references live). We're seeing the network through a keyhole.

### Tasks

1. **Backfill body text** for all 46,633 documents (or as many as have accessible content pages). This is a crawler re-run, not LLM work — just hitting content pages we skipped on the first pass.
   - **Status: NOT STARTED for full corpus.** Only done for 113 AI-related docs (87 succeeded). This is the highest-priority remaining task.

2. **Re-run citation extraction** on the expanded corpus. We should go from ~14,834 edges to potentially 50,000+.
   - **Status: PARTIALLY DONE.** Citation extraction has been run on the current corpus (14,834 edges). Needs re-run after full body text backfill.

3. ~~**Build "Policy Chain" view in the web app.**~~ **DONE.** `/chain/{topic}` shows cross-level policy chains for 6 topics (ai, digital, carbon, housing, education, health). Each shows central → municipal → district hierarchy with document links.

4. **Build "Same-Level Comparison" view.** For a given central directive, compare which districts/departments responded and which didn't.
   - **Status: NOT STARTED.** Deferred — the chain view partially covers this by grouping by level.

### Completed additions (not in original plan)

5. **AI policy case study write-up** — `/analysis/ai` — an analytical write-up demonstrating policy chain analysis. See `docs/implementation/ai-case-study-plan.md`.

6. **Production deployment** — PostgreSQL on Railway, Dockerfile, dual-mode database layer, custom domain (chinagovernance.com). See `docs/implementation/web-scratchpad.md` for deployment log.

### What this demonstrates (portfolio value)
- Data engineering at scale (corpus management, backfilling)
- Domain expertise (understanding Chinese administrative hierarchy)
- Analytical thinking (policy chain visualization)
- Production deployment (PostgreSQL, Docker, Railway, custom domain)

### What this does NOT require
- LLM API calls (all regex-based)
- Translation (still Chinese-only at this stage)

---

## MVP 2: LLM Translation + Topic Classification

**Goal:** Make the corpus accessible to people who don't read Chinese. Add structured topic tags so analysts can find what they care about.

### Tasks

1. **English translation** of document titles and body text via LLM API (Claude or GPT-4). Batch processing, decoupled from the crawler.
   - Start with documents that have body text + citations (highest value)
   - Store translations alongside originals
   - Estimate: ~6,700 documents with body text × ~500 tokens avg = ~3.4M tokens. Cost-manageable.

2. **Topic classification.** Design a taxonomy relevant to our audience (draw from UCSD's 13 S&T themes but expand beyond S&T — include housing, environment, finance, public health, education, etc.). LLM assigns 1-3 tags per document.

3. **Update the web app:**
   - Toggle between Chinese and English throughout the UI
   - Filter/browse by topic tag
   - Search works in English against translated text

4. **Quality verification:** Spot-check translations with a Chinese reader. Ensure topic tags are consistent across similar documents.

### What this demonstrates (portfolio value)
- LLM integration at scale (batch processing, prompt engineering, cost management)
- Taxonomy design and information architecture
- Bilingual data product

---

## MVP 3: Thematic Policy Matching (LLM-Powered)

**Goal:** Go beyond explicit 文号 citations to identify documents that implement the same policy *even when they don't cite each other directly*.

This is the hard version of policy tracing. Many local implementation documents don't cite the parent directive by document number — they just implement the same policy in their own words.

### Tasks

1. **Embeddings pipeline.** Generate embeddings for all documents (translated text). Store in a vector index.

2. **Thematic clustering.** Use embeddings to identify clusters of documents across departments/districts that address the same policy topic, even without shared citations.

3. **LLM-assisted policy linking.** For a given central directive, use the LLM to:
   - Identify candidate local documents (via embedding similarity)
   - Confirm whether each candidate is actually implementing that directive (vs. coincidentally similar)
   - Extract *how* the implementation differs (what was added, what was omitted, what was modified)

4. **"Policy Map" visualization.** Upgrade the chain view from MVP 1:
   - Show both explicit citations (solid lines) AND thematic matches (dashed lines)
   - Highlight implementation differences across regions/departments
   - Timeline showing propagation speed

### What this demonstrates (portfolio value)
- RAG/embeddings architecture
- LLM-as-judge pattern (confirm thematic matches)
- The core analytical thesis: making Chinese governance structure *legible* to outsiders

---

## MVP 4: RAG Q&A + Public Launch

**Goal:** Let analysts ask questions in natural language and get sourced answers from the corpus.

### Tasks

1. **RAG-based Q&A interface.** User asks "What is Shenzhen doing about AI regulation?" and gets an answer synthesized from relevant documents, with citations linking back to specific documents in the corpus.

2. **Entity extraction.** Use LLM to extract named entities (officials, organizations, companies, specific policies) and build a searchable entity index. Enables queries like "What documents mention [specific official]?"

3. **Multi-city expansion.** Extend the crawler to other Guangdong cities using gkmlpt (confirmed to be a province-wide platform). This enables the cross-regional comparison that analysts most want: "How does Shenzhen's AI policy compare to Guangzhou's?"

4. **Public launch.** Domain, documentation, methodology page, invite beta users from the research community (start with Kasper Ingeman Beck at CBS, who built China Horizons — the closest existing project).

### What this demonstrates (portfolio value)
- Full RAG pipeline (embeddings → retrieval → generation → citation)
- Production deployment of an LLM-powered application
- The complete story: "I built a system that crawls Chinese local government documents, translates them, classifies them, maps policy propagation across administrative levels, and lets you ask questions in English — with citations back to verified original sources."

---

## Future Extensions (Post-Launch)

These are ideas worth remembering but not committing to until the core product proves useful:

- **PDF/DOCX attachment extraction** — ~10% of documents have attachments we're not parsing yet. Would expand corpus significantly.
- **NFCMS parser for main portal** — the Shenzhen main portal uses a different CMS for some content. Separate parser needed for full coverage.
- **Beyond Guangdong** — other provinces use different CMS platforms. Estimated 5-15 distinct templates nationally. Each is a new crawler effort.
- **Policy contradiction detection** — LLM identifies cases where local implementation contradicts or significantly deviates from central directives.
- **Temporal analysis** — track how policy language evolves over time. When does a "pilot program" become "mandatory"?
- **Government Guidance Fund tracking** — hedge fund use case from landscape research. Track which industries are receiving state capital at the provincial level.
- **Academic API** — structured API access for researchers, enabling the "WRDS/FRED for Chinese government activity" vision from Direction 4 of our strategy docs.
- **Newsletter/alert system** — notify subscribers when new documents appear in their policy areas of interest. Foundation in place: incremental sync already detects new publications and records them in `document_changes`.

---

## Reference

- Strategic landscape analysis: `docs/strategy/landscape-overview.md`
- Competitive positioning and direction options: `docs/strategy/deep-dive-directions.md`
- Crawler implementation details: `docs/implementation/crawler-plan.md`
- Web app implementation details: `docs/implementation/web-plan.md`
