# Annotations — feature state & how to extend (as of 2026-07-28)

"Annotated readings" of policy documents against the corpus. Replaced the Policy
Trace page in the nav. Live at **/annotations**.

## 1. What's live

- **`/annotations`** — hub, lists every annotation (currently one: AI+).
- **`/annotations/{slug}`** — a document's **coverage map**: every taxonomy item
  with its live doc count (from the DeepSeek map), grouped, bars, gaps visible.
- **`/annotations/{slug}/{item_id}`** — one item's detail. Two kinds:
  - **curated** (has `clauses` in the YAML): full apparatus — the text, a
    "where X appears" source breakdown, the reading slot, linked docs.
  - **taxonomy-only**: just the heading + its mapped documents (auto).

Current AI+ state: **6 curated/scaffolded items** of 25.
- `sci-philosophy` — CURATED (has a written reading + keyword-linked ethics catalog).
- `gov-social`, `gov-security`, `gov-eco`, `glo-inclusive`, `glo-governance` —
  SCAFFOLDED (verbatim clause text + mention stats + mapped docs; `reading:` EMPTY,
  awaiting curation).
- The other 19 items render as taxonomy-only (mapped docs) from the coverage map.

## 2. Files

- **`data/annotations.yaml`** — the curation. `annotations:` → each has slug, doc
  meta, and `items:`. Each item: `id`, `taxonomy_id` (links to the map),
  `path`/`index_label`/`heading_*`/`subhead`, `clauses` (verbatim source text;
  `{...}` marks a highlighted term), `queries` (see below), and `reading:` (curated
  HTML, may be empty). NOTE: the AI+ text uses FULLWIDTH quotes “ ” — keep them.
- **`data/aiplus_taxonomy.yaml`** — the 25 AI+ leaf items (id/group/cn/en/desc).
  Feeds both the coverage map and the DeepSeek mapping prompt.
- **`web/services/annotations.py`** — `list_annotations`, `get_overview` (coverage
  map), `get_item` (detail). Every NUMBER is computed live from the corpus.
- **`web/routers/pages.py`** — the 3 routes.
- **`web/templates/`** — `annotations.html` (hub), `annotation_overview.html`
  (coverage map), `annotation.html` (item detail).

### query spec (per curated item)
- `mentions: [{term|term_all, label}]` → doc counts for the metric strip.
- `breakdown: <term>` → the "where <term> appears" source-breakdown bars.
- `linked: {title_any, title_all_pairs, min_rank, limit}` → a keyword-defined doc
  catalog (hand-curated precision). **If present, it wins over the map.**
- If an item has `taxonomy_id` but NO `linked`, its docs come from the map.

## 3. The DeepSeek mapping (aiplus_map)

- **Table** `aiplus_map(doc_id, item_id)` in documents.db — which AI+ item(s) each
  AI-relevant doc advances. `item_id = '__none__'` is the sentinel for "no item".
- **Built by** `scripts/rnd/annotations/map_aiplus.py`: over docs with
  `ai_relevance >= 0.3` (~3,399), DeepSeek `deepseek-v4-flash` tags each against the
  25 items. Resumable, concurrency 2. Cost ~$1 (prompt-cached).
  - Run: `set -a; source .env; set +a; python3 scripts/rnd/annotations/map_aiplus.py`
    (`--limit N` for a sample). Re-run after new docs are crawled/classified to
    extend coverage (it skips already-mapped docs).
- Current: 3,399 mapped, 4,492 tags. Distribution (the finding): 算力
  `found-compute` 718 … `sci-philosophy` 6 — infra/industry-heavy, humanities sparse.

## 4. DeepSeek v4 migration (IMPORTANT)

`deepseek-chat` was RETIRED (400s). Current models: `deepseek-v4-flash` / `-pro`.
They are REASONING models — `max_tokens` must leave room for reasoning + answer or
`.content` comes back EMPTY. Fixed in both `map_aiplus.py` (max_tokens 600) and
`scripts/classify_documents.py` (model → v4-flash, max_tokens 500→2000). If either
returns empty/0, that's the symptom.

## 5. How to extend

- **Curate a reading**: set `reading:` on an item in `annotations.yaml` (HTML,
  rendered via |safe). Restart the app. Live.
- **Scaffold an AI+ item**: add an item block with `taxonomy_id`, verbatim
  `clauses`, `mentions`; leave `reading: ""`. (24 → 19 items left to do.)
- **Add a NEW source document** (other than AI+): add an `annotations:` entry.
  CAVEAT: `get_overview` currently loads the AI+ taxonomy + aiplus_map, so the
  coverage-map view is AI+-specific. Options for other docs:
  (a) **Simple annotation** (no coverage map) — a list of curated items with
      keyword `linked` queries; needs a small render path (list items, skip the
      taxonomy overview). Works for ANY document with no mapping pass.
  (b) **Full coverage map** — give the doc its own taxonomy YAML + run a mapping
      pass into a per-doc map table; generalize `get_overview`/`_load_taxonomy` to
      take the annotation's taxonomy. Heavier; worth it for structured plans.
