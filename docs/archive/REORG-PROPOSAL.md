# Documentation Reorganization

Executed 2026-03-28.

## Before: What we had

```
docs/
├── INDEX.md                              # Project overview (outdated stats)
├── ROADMAP.md                            # Strategic vision (current)
├── spec.md                               # Original project specification
├── conversation.md                       # Initial scoping transcript
│
├── implementation/                       # Mixed bag: active runbooks + completed plans + scratchpads
│   ├── ai-case-study-plan.md             # Completed
│   ├── classification-plan.md            # Completed
│   ├── crawler-plan.md                   # Completed
│   ├── crawler-scratchpad.md             # Historical session notes
│   ├── investment-data-plan.md           # In progress (low priority)
│   ├── new-province-crawler-guide.md     # Active guide
│   ├── research-views-roadmap.md         # Web feature roadmap
│   ├── sync-runbook.md                   # Active runbook
│   ├── vertical-expansion-plan.md        # Completed
│   ├── web-plan.md                       # Completed
│   └── web-scratchpad.md                 # Historical session notes
│
├── log/                                  # Session logs (5 files)
│   ├── central-crawl.log
│   ├── crawl-log-mar-1.md
│   ├── expansion-crawl-mar-12.md
│   ├── ministry-crawl-mar13.md
│   └── tier4-province-crawlers.log
│
├── references/                           # Mixed: operational docs + educational material
│   ├── ai-policy-vertical-crawl-plan.md
│   ├── apis-and-web-scraping.md
│   ├── droplet-setup-notes.md            # Operational, not reference
│   └── gkmlpt-platform-survey.md
│
└── strategy/                             # Forward-looking plans
    ├── crawl-expansion-proposal.md       # Active (updated this session)
    ├── deep-dive-directions.md           # Audience analysis
    └── landscape-overview.md             # Competitive landscape
```

### Problems

1. **implementation/** mixed active runbooks, completed plans, and scratchpads — no way to tell what's current
2. **Crawler state scattered across 5+ files** — had to read crawler-plan, vertical-expansion-plan, multiple logs, and crawl-expansion-proposal to reconstruct what exists and what works
3. **No single source of truth** — no file answered "what's the current state of the project"
4. **Completed plans cluttered the workspace** — ai-case-study-plan and classification-plan are done but sat alongside active docs
5. **Operational docs in references/** — droplet-setup-notes is a runbook, not a reference
6. **Two strategy files covered the same ground** — deep-dive-directions and landscape-overview overlap heavily

## After: What we have now

```
docs/
├── README.md                    # What this is + how docs are organized
├── ROADMAP.md                   # Project-level priorities (kept as-is)
├── STATUS.md                    # ★ Live state: corpus, crawlers, droplet, production
│
├── runbooks/                    # How to do things (kept current, actionable)
│   ├── crawling.md              # Per-crawler operating manual
│   ├── new-crawler-guide.md     # Building a new crawler from scratch
│   ├── sync-and-deploy.md       # SQLite→Postgres, Railway deploy, verification
│   ├── classification.md        # DeepSeek pipeline
│   └── droplet.md               # Droplet setup, cron, connectivity
│
├── strategy/                    # Where we're going (forward-looking)
│   ├── crawl-expansion.md       # Expansion plan with execution status
│   ├── research-vision.md       # Audience, competitive landscape, directions
│   └── website-features.md      # Web app feature roadmap
│
├── references/                  # Background knowledge (stable, educational)
│   ├── apis-and-scraping.md     # How APIs and web scraping work
│   ├── ai-policy-vertical.md    # AI governance chain central→local
│   ├── gkmlpt-survey.md         # gkmlpt platform findings
│   └── architecture.md          # System design, pipeline, schema
│
├── working/                     # ★ Wet clay — active research, in-progress notes
│   └── (empty until needed)     # Files live here while being figured out,
│                                # move to archive/ when formalized
│
└── archive/                     # Done — completed plans, historical logs, superseded docs
    ├── ai-case-study-plan.md
    ├── classification-plan.md
    ├── conversation.md
    ├── crawler-plan.md
    ├── crawler-scratchpad.md
    ├── investment-data-plan.md
    ├── vertical-expansion-plan.md
    ├── web-plan.md
    ├── web-scratchpad.md
    └── logs/
        ├── central-crawl.log
        ├── crawl-log-mar-1.md
        ├── expansion-crawl-mar-12.md
        ├── ministry-crawl-mar13.md
        └── tier4-province-crawlers.log
```

## Design Principles

### 1. STATUS.md is the single source of truth
Any agent or human reads this first. It answers: how big is the corpus, what crawlers exist, what's their state, what's deployed, what's running on the droplet. Dashboard-level — one line per crawler, not full technical detail.

### 2. Runbooks are "how," strategy is "where," archive is "was"
- **runbooks/** — Follow these to do things. Always current.
- **strategy/** — Read these for direction. Updated when priorities change.
- **archive/** — Preserved for context. Not actively maintained.

### 3. working/ is wet clay
Active research, debugging notes, in-progress plans. **One file per topic.** When the work is done, useful bits are extracted into runbooks/STATUS.md, and the whole working/ file moves to archive/ intact. No information splits across documents.

Lifecycle: `working/zhejiang-research.md` → crawler built → details go to `runbooks/crawling.md` + `STATUS.md` → whole file moves to `archive/zhejiang-research.md`

### 4. Archive is flat
No subdirectories in archive/ except logs/. Files keep their original names. Easy to find, easy to move in, never need to reorganize.

## File Movement Map

| Before | After | Why |
|--------|-------|-----|
| `INDEX.md` | `README.md` | Renamed, updated with current stats + folder guide |
| `ROADMAP.md` | `ROADMAP.md` | Kept as-is |
| `spec.md` | `references/architecture.md` | Foundational design, not active planning |
| `conversation.md` | `archive/conversation.md` | Historical |
| `implementation/sync-runbook.md` | `runbooks/sync-and-deploy.md` | Active runbook |
| `implementation/new-province-crawler-guide.md` | `runbooks/new-crawler-guide.md` | Active guide |
| `implementation/research-views-roadmap.md` | `strategy/website-features.md` | Forward-looking |
| `implementation/classification-plan.md` | `archive/classification-plan.md` | Completed |
| `implementation/crawler-plan.md` | `archive/crawler-plan.md` | Completed |
| `implementation/web-plan.md` | `archive/web-plan.md` | Completed |
| `implementation/ai-case-study-plan.md` | `archive/ai-case-study-plan.md` | Completed |
| `implementation/investment-data-plan.md` | `archive/investment-data-plan.md` | Low priority |
| `implementation/vertical-expansion-plan.md` | `archive/vertical-expansion-plan.md` | Completed |
| `implementation/crawler-scratchpad.md` | `archive/crawler-scratchpad.md` | Historical |
| `implementation/web-scratchpad.md` | `archive/web-scratchpad.md` | Historical |
| `references/droplet-setup-notes.md` | `runbooks/droplet.md` | Operational, not reference |
| `references/gkmlpt-platform-survey.md` | `references/gkmlpt-survey.md` | Renamed |
| `references/ai-policy-vertical-crawl-plan.md` | `references/ai-policy-vertical.md` | Renamed |
| `references/apis-and-web-scraping.md` | `references/apis-and-scraping.md` | Renamed |
| `strategy/crawl-expansion-proposal.md` | `strategy/crawl-expansion.md` | Renamed |
| `strategy/deep-dive-directions.md` | `strategy/research-vision.md` | Merged |
| `strategy/landscape-overview.md` | *(merged into research-vision.md)* | Merged |
| `log/*` | `archive/logs/*` | Historical |

## New Files Created

- **`README.md`** — Project overview + docs folder guide
- **`STATUS.md`** — Live project state (corpus, crawlers, droplet, production, classification)
- **`runbooks/crawling.md`** — Per-crawler operating manual (commands, techniques, known issues)
- **`runbooks/classification.md`** — DeepSeek classification pipeline runbook
- **`strategy/research-vision.md`** — Merged from deep-dive-directions + landscape-overview
