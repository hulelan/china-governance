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
| [implementation/ai-case-study-plan.md](implementation/ai-case-study-plan.md) | AI policy case study: body text backfill, citation extraction, policy chain construction, translation | Steps 1-3,5 done; Step 4 (translation) pending | 2026-02-22 | 2026-02-22 |

## Current Status (2026-02-28)

**Live at [chinagovernance.com](https://www.chinagovernance.com)** — Railway (PostgreSQL + Docker).

**Corpus:** 46,634 documents, 22 sites, 14,834 citation edges. Only ~15% have body text — backfilling the rest is a priority.

**Recent work:**
- **Subsidies pipeline** (Sprint 1): Multi-keyword matching, subsidy amount extraction, sector attribution, report page at `/analysis/subsidies`. Awaiting full backfill to run against expanded corpus.
- **Incremental sync**: `--sync` flag on gkmlpt crawler detects new publications, metadata changes, and deletions without overwriting existing data. Change history viewable at `/changes` and via `--show-changes` CLI.
