# docs/ Index

All project documentation, organized by purpose.

## Project-Level

| File | Purpose | Created | Last Updated |
|------|---------|---------|-------------|
| [ROADMAP.md](ROADMAP.md) | Vision, target audience, and phased MVP plan from current state to public launch | 2026-02-22 | 2026-02-28 |
| [spec.md](spec.md) | Original project specification — motivation, 5-stage pipeline design, scope decisions | 2026-02-14 | 2026-02-14 |
| [conversation.md](conversation.md) | Transcript of the initial scoping conversation that launched the project | 2026-02-14 | 2026-02-14 |

## Strategy

Research on the competitive landscape, potential audiences, and strategic direction.

| File | Purpose | Created | Last Updated |
|------|---------|---------|-------------|
| [strategy/landscape-overview.md](strategy/landscape-overview.md) | Who else works on Chinese governance data (academic, commercial, OSINT). Potential user groups. | 2026-02-22 | 2026-02-22 |
| [strategy/deep-dive-directions.md](strategy/deep-dive-directions.md) | Detailed gap analysis of existing efforts. Four strategic directions evaluated. Key people in the field. | 2026-02-22 | 2026-02-22 |

## Implementation Plans

Execution plans for specific workstreams. Each plan has a corresponding scratchpad for working notes.

| File | Purpose | Status | Created | Last Updated |
|------|---------|--------|---------|-------------|
| [implementation/crawler-plan.md](implementation/crawler-plan.md) | Crawler pipeline: API discovery, listing, extraction, storage, analysis. 6 goals. | Complete | 2026-02-14 | 2026-02-15 |
| [implementation/crawler-scratchpad.md](implementation/crawler-scratchpad.md) | Working log for crawler implementation sessions | — | 2026-02-14 | 2026-02-15 |
| [implementation/web-plan.md](implementation/web-plan.md) | Web frontend: FastAPI + Jinja2 + D3.js. Database prep, API, pages, deployment. | Complete | 2026-02-15 | 2026-02-15 |
| [implementation/web-scratchpad.md](implementation/web-scratchpad.md) | Working log for web app implementation sessions (includes deployment log) | — | 2026-02-15 | 2026-02-28 |
| [implementation/ai-case-study-plan.md](implementation/ai-case-study-plan.md) | AI policy case study: body text backfill, citation extraction, policy chain construction, translation | Steps 1-3,5 done; Step 4 (translation) pending | 2026-02-22 | 2026-03-01 |
| [implementation/research-views-roadmap.md](implementation/research-views-roadmap.md) | Inbox view, date filtering, doc-to-network, future feature plans | Current | 2026-03-10 | 2026-03-12 |
| [implementation/new-province-crawler-guide.md](implementation/new-province-crawler-guide.md) | Guide for writing custom crawlers for non-gkmlpt sites | Current | 2026-03-13 | 2026-03-20 |
| [implementation/vertical-expansion-plan.md](implementation/vertical-expansion-plan.md) | Crawlers package refactor, NDRC/Gov/MOF/MEE crawlers, body backfill | Complete | 2026-03-12 | 2026-03-15 |
| [implementation/classification-plan.md](implementation/classification-plan.md) | LLM classification pipeline design (DeepSeek/Ollama) | In progress | 2026-03-17 | 2026-03-17 |

## References

| File | Purpose |
|------|---------|
| [references/gkmlpt-platform-survey.md](references/gkmlpt-platform-survey.md) | Survey of which Chinese gov sites use the gkmlpt platform (Guangdong-only) |
| [references/ai-policy-vertical-crawl-plan.md](references/ai-policy-vertical-crawl-plan.md) | Ministry site crawlability assessments (NDRC, MOST, CAC, MIIT, State Council) |

## Logs

| File | Purpose | Date |
|------|---------|------|
| [log/crawl-log-mar-1.md](log/crawl-log-mar-1.md) | Body text backfill session (14% → 86% coverage) | 2026-03-01 |
| [log/expansion-crawl-mar-12.md](log/expansion-crawl-mar-12.md) | Geographic expansion: 14 new Guangdong cities + Tier 2 province probes | 2026-03-12 |
| [log/ministry-crawl-mar13.md](log/ministry-crawl-mar13.md) | MOF + MEE ministry crawler development and crawl | 2026-03-13 |
| [log/tier4-province-crawlers.log](log/tier4-province-crawlers.log) | Beijing, Shanghai, Jiangsu, Zhejiang, Sichuan, Shandong province crawlers | 2026-03-18 |

## Current Status (2026-03-20)

**Live at [chinagovernance.com](https://www.chinagovernance.com)** — Railway (PostgreSQL + Docker).

**Corpus:** 103,470+ documents across 42+ sites, ~95k with body text (92% coverage). Plus ~6,600 province docs in `documents_new.db` pending merge. See `CLAUDE.md` for operational commands.

**Recent work (March 2026):**
- **Province crawlers**: Beijing (1,781 docs, 99% body), Shanghai (3,830 docs, 99% body), Jiangsu (1,041 docs, body pending). Zhejiang/Sichuan/Shandong blocked from US.
- **PDF text extraction**: `scripts/extract_pdf_text.py` extracts text from PDF attachments for stub-body documents. ~830 PDFs extracted so far (89% success rate).
- **Merge workflow**: `scripts/merge_db.py` + `--db` flag on crawlers for writing to separate DBs to avoid SQLite lock contention.
- **Body text backfill complete**: 91% coverage (up from 15%).
- **Geographic expansion**: Added 16 Guangdong cities + 3 Shenzhen districts via gkmlpt. Probed 28 provinces — confirmed gkmlpt is Guangdong-only.
- **Ministry crawlers**: `crawlers/mof.py` (919 docs) and `crawlers/mee.py` (563 docs).
- **Research views**: Inbox/calendar view, date range filtering, mini citation network.
- **Incremental sync**: `--sync` flag on gkmlpt crawler detects new publications, metadata changes, and deletions.
