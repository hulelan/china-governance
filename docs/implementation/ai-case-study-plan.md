# AI Policy Case Study — Implementation Plan

## Context

We're building the first end-to-end policy chain as a proof of concept for ROADMAP MVP 1. The case study: **What is Shenzhen actually doing about AI?**

### What we found in the corpus

- **89 documents** with "人工智能" in the title across 16 departments/districts
- **124 documents** mentioning AI in body text
- **3 formal policy documents** (with 文号):
  - `深龙华府办规〔2021〕9号` — Longhua AI industry promotion measures (2021)
  - `深南府办函〔2023〕48号` — Nanshan AI innovation implementation plan (2023)
  - `深龙华府办规〔2024〕20号` — Longhua AI + robotics industry measures (2024, revised)
- **Only 2 of 89** AI-titled documents have meaningful body text extracted
- **Longhua district** is the standout: 30 AI documents, two generations of formal policy, and the 2024 version explicitly references Shenzhen's municipal AI action plan

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

- [ ] Body text extracted for >80% of AI-titled documents
- [ ] Success/failure logged for each document
- [ ] We know how many of these contain citations to other documents

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

- [ ] All citations extracted from AI-relevant documents
- [ ] Municipal-level AI plan identified (in corpus or documented as external)
- [ ] Central-level AI directives identified from citations
- [ ] Chain data structured and stored (could be a JSON file or new DB table)

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

- [ ] `/chain/ai` page renders the hierarchy
- [ ] Clicking any document goes to its detail page
- [ ] Central/external references are clearly marked as "not in corpus"
- [ ] Timeline view shows propagation timing

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

- [ ] Write-up published on the site
- [ ] Includes specific document citations with links
- [ ] Readable by someone with no Chinese language ability
- [ ] Makes a non-obvious observation about Chinese AI governance

---

## Build Order

```
Step 1 (backfill) → Step 2 (citations) → Step 3 (web view) → Step 4 (translation) → Step 5 (write-up)
                                            ↑ can start design in parallel
```

Step 1 is the gating task. Everything downstream depends on having body text.

Steps 3 and 4 can be worked on in parallel once step 2 is done — the chain view can initially show Chinese text, with English added later.

Step 5 depends on steps 3 and 4 being complete.
