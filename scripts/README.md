# scripts/ — what runs, what's R&D

This folder is split by **whether a script is load-bearing**:

- **`scripts/*.py` / `*.sh` (flat)** — ACTIVE. Wired into the nightly pipeline
  (`daily_sync.sh`) or documented as a run command in `CLAUDE.md`. Touch with care.
- **`scripts/rnd/…`** — R&D / one-off tools. Real, re-runnable, but NOT part of the
  live pipeline. Grouped by theme. Safe to ignore for day-to-day ops.

Anything that was a completed one-time migration, a dead shim, or gitignored
scratch (`check_*.py`) has been deleted — it's in git history if ever needed.

> Path note: R&D scripts live 3 dirs below the repo root, so they resolve it via
> `Path(__file__).parents[3]`. Active (flat) scripts use `.parent.parent`. Keep
> that in mind if you move one between the two.

## ACTIVE (flat in `scripts/`)

| Script | Purpose | Wired into |
|--------|---------|-----------|
| `daily_sync.sh` | Nightly crawl → backfill → score → classify → publish. The pipeline. | droplet cron (06:00 UTC) |
| `backfill_from_html.py` | Re-extract body text from saved raw HTML. | daily_sync Phase 1b · CLAUDE.md |
| `compute_scores.py` | citation_rank, algo_doc_type, ai_relevance (no LLM). | daily_sync Phase 1b · CLAUDE.md |
| `classify_documents.py` | DeepSeek classification (title/summary/type/refs). ⚠ concurrency 2 max. | daily_sync Phase 2 · CLAUDE.md |
| `extract_pdf_text.py` | Extract text from PDF/DOC attachments. | CLAUDE.md |
| `merge_db.py` | Merge a separate SQLite DB into documents.db. | CLAUDE.md (separate-DB workflow) |
| `match_clt_translations.py` | Link China Law Translate posts to native docs by source URL. | CLAUDE.md |
| `compute_overlaps.py` | Build the `overlaps` table in **officials.db**. | CLAUDE.md (officials.db build) |
| `fix_baike_collisions.py` | Fix name-collision records in **officials.db**. | CLAUDE.md (officials.db build) |

## R&D / one-off (`scripts/rnd/`)

| Bucket | Scripts | What they're for |
|--------|---------|------------------|
| `citations/` | `extract_citations.py`, `migrate_citations.py`, `discover_citation_gaps.py`, `build_ai_chain.py`, `export_network.py` | Cross-doc citation extraction, the AI policy-chain build, network CSV export. Import `analyze.py` (repo root). |
| `references/` | `extract_references_regex.py`, `compare_references_regex_vs_deepseek.py` | Regex reference extraction + a regex-vs-DeepSeek quality comparison. |
| `translation/` | `translate_chain.py`, `translate_titles_google.py`, `translate_titles_deepseek_premium.py`, `translate_titles_compare.py` | Title/chain translation passes + a Google-vs-DeepSeek eval. |
| `subsidies/` | `extract_subsidy_data.py`, `analyze_subsidies.py` | Structured subsidy-amount extraction + aggregate stats. |
| `discovery/` | `discover_sources.py`, `probe_gkmlpt.py`, `probe_provinces.py` | Find uncrawled sites / probe for gkmlpt + provincial endpoints. |
| `backfill/` | `backfill_ai.py`, `wayback_backfill.py`, `merge_extractions.py` | Targeted body-text backfills (AI docs, Wayback) + NPC/PDF merge. |
| `eval/` | `eval_classification.py` | Test the classification prompt against an eval set. |
| `misc/` | `search_vc.py` | Ad-hoc corpus query (venture-capital content). |
| `crawl-runners/` | `crawl_expansion.sh`, `crawl_parallel.sh`, `crawl_retry.sh`, `run_remaining_crawls.sh` | One-off bulk-crawl drivers (hardcode a local path; historical). |

## Note: `analyze.py` lives at the repo root

`analyze.py` is a **shared analysis library** (citation regexes, `is_policy_document`),
not a runnable script. It's imported by `tests/test_citations.py` and the
`rnd/citations/` scripts, so it stays at the root where both can import it.
