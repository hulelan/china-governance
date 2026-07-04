# Classification Runbook

Adds English titles, summaries, categories, importance ratings, and topics to documents via DeepSeek API.

## Quick Start

```bash
export DEEPSEEK_API_KEY="sk-..."

# Preview what will be classified
python3 scripts/classify_documents.py --dry-run --limit 5

# Run classification (keep concurrency low)
python3 scripts/classify_documents.py --concurrency 2
```

## What it adds

Each document gets these fields:
- `title_en` — English translation of the title
- `summary_en` — 1-2 sentence English summary
- `category` — one of: administrative, normative, major_policy, regulation, budget, subsidy, personnel, report, other
- `importance` — high / medium / low
- `policy_area` — topic area (e.g., "technology policy", "environmental regulation")
- `topics` — JSON array of specific topics

## Cost and performance

- ~$0.50 per 1,000 documents
- Full corpus (~110k docs) costs ~$55
- At concurrency 2, processes ~1,000 docs/hour

## Critical: Keep concurrency at 2

DeepSeek silently rate-limits at higher concurrency — returns empty responses instead of 429 errors. The classifier retries but wastes time. Concurrency 2 is the reliable maximum.

## After classification

Nothing to sync — classifications are written straight into `documents.db`, which
the web app reads directly. On the droplet, publish in place:

```bash
sqlite3 documents.db "PRAGMA wal_checkpoint(TRUNCATE);" && systemctl restart chinagovernance
```

(The nightly `daily_sync.sh` Phase 2 runs classification automatically for
unclassified docs, then publishes. See CLAUDE.md → Architecture.)
