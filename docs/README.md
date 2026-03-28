# China Governance Documentation

Chinese government document corpus + web app. Crawls policy documents from central through provincial to municipal and district level, plus media sources. Live at [chinagovernance.com](https://www.chinagovernance.com).

**Current corpus:** ~114,000 documents from 48 sites, ~91% body text coverage.

## How this folder is organized

| Folder | Purpose | When to read |
|--------|---------|--------------|
| **STATUS.md** | Live state of everything — corpus, crawlers, droplet, production | First thing any agent or human reads |
| **runbooks/** | How to do things — crawl, sync, deploy, classify | When you need to act |
| **strategy/** | Where we're going — expansion plans, research vision, web features | When planning priorities |
| **references/** | Background knowledge — architecture, platform surveys, educational | When you need context |
| **working/** | Wet clay — active research, in-progress notes | While figuring something out |
| **archive/** | Done — completed plans, session logs, superseded docs | When you need historical context |

## File lifecycle

```
working/some-research.md          (exploring, documenting findings)
        ↓ work completes
runbooks/ or STATUS.md            (operational details extracted)
working/some-research.md  →  archive/some-research.md  (whole file moves)
```

## Quick links

- **Run a crawler:** `runbooks/crawling.md`
- **Sync to production:** `runbooks/sync-and-deploy.md`
- **Add a new crawler:** `runbooks/new-crawler-guide.md`
- **What to work on next:** `strategy/crawl-expansion.md`
- **Research direction:** `strategy/research-vision.md`
- **System architecture:** `references/architecture.md`
