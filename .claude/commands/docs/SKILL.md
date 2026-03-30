---
name: docs
description: Find project information in the docs/ folder. Use when you need context about the project state, how to run crawlers, deployment steps, research plans, or any operational detail. Also use when the user says "check the docs", "look it up", "what do we know about X", or when you realize you're missing context to complete a task.
---

# Project Documentation Lookup

Project documentation lives in `docs/`. Find what you need using this strategy.

## Step 1: Orient

Read these two files first:

1. **`docs/README.md`** — folder structure and quick links
2. **`docs/STATUS.md`** — live project state: corpus size, per-crawler doc counts, droplet status, production sync state, classification progress

Read STATUS.md even if you think you know the answer — it's the source of truth.

## Step 2: Find the right file

| You need to... | Read |
|----------------|------|
| Run a crawler, debug a crawl, understand a crawler's technique | `docs/runbooks/crawling.md` |
| Build a new crawler from scratch | `docs/runbooks/new-crawler-guide.md` |
| Sync data to production or deploy | `docs/runbooks/sync-and-deploy.md` |
| Classify documents with DeepSeek | `docs/runbooks/classification.md` |
| Set up or manage the droplet | `docs/runbooks/droplet.md` |
| Know what to work on next (crawler expansion) | `docs/strategy/crawl-expansion.md` |
| Understand the research vision, audience, competitive landscape | `docs/strategy/research-vision.md` |
| Plan web app features | `docs/strategy/website-features.md` |
| Understand the system architecture or database schema | `docs/references/architecture.md` |
| Understand gkmlpt (Guangdong platform) | `docs/references/gkmlpt-survey.md` |
| Understand how APIs and web scraping work | `docs/references/apis-and-scraping.md` |
| Understand the AI policy governance chain (central to local) | `docs/references/ai-policy-vertical.md` |
| Find in-progress research or notes | `docs/working/` (list files) |
| Find completed plans or historical session logs | `docs/archive/` |

## Step 3: Report

Summarize the key information found. If no docs file has the answer, say so.
