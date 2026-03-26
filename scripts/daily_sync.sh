#!/bin/bash
# Daily crawl + classify + sync pipeline for the Singapore droplet.
# Designed to run via cron. Logs to /root/china-governance/logs/
#
# Usage:
#   ./scripts/daily_sync.sh          # Run full pipeline
#   ./scripts/daily_sync.sh --crawl  # Crawl only (no classify/sync)

set -euo pipefail
cd "$(dirname "$0")/.."

# Load environment
source .env 2>/dev/null || true

LOGDIR="logs"
mkdir -p "$LOGDIR"
LOG="$LOGDIR/daily-$(date +%Y%m%d-%H%M).log"

log() { echo "[$(date +%H:%M:%S)] $1" | tee -a "$LOG"; }

log "=== Daily sync started ==="

# --- Phase 1: Crawl all sources ---
log "Phase 1: Crawling..."

# gkmlpt sites (incremental — only fetches new docs)
python3 -m crawlers.gkmlpt --sync >> "$LOG" 2>&1 || log "WARN: gkmlpt sync had errors"

# Central ministries
for crawler in gov ndrc mof mee; do
    log "  Crawling $crawler..."
    python3 -m crawlers.$crawler >> "$LOG" 2>&1 || log "WARN: $crawler had errors"
done

# Province crawlers
for crawler in beijing shanghai jiangsu; do
    log "  Crawling $crawler..."
    python3 -m crawlers.$crawler >> "$LOG" 2>&1 || log "WARN: $crawler had errors"
done

# Shenzhen non-gkmlpt (investment news, DRC, etc.)
log "  Crawling sz_invest..."
python3 -m crawlers.sz_invest >> "$LOG" 2>&1 || log "WARN: sz_invest had errors"

log "Phase 1 done. Doc count: $(sqlite3 documents.db 'SELECT COUNT(*) FROM documents')"

if [ "${1:-}" = "--crawl" ]; then
    log "=== Crawl-only mode, stopping ==="
    exit 0
fi

# --- Phase 2: Classify new docs ---
if [ -n "${DEEPSEEK_API_KEY:-}" ]; then
    UNCLASSIFIED=$(sqlite3 documents.db "SELECT COUNT(*) FROM documents WHERE classified_at = '' OR classified_at IS NULL")
    if [ "$UNCLASSIFIED" -gt 0 ]; then
        log "Phase 2: Classifying $UNCLASSIFIED new docs..."
        python3 scripts/classify_documents.py --concurrency 2 >> "$LOG" 2>&1 || log "WARN: classification had errors"
    else
        log "Phase 2: No new docs to classify"
    fi
else
    log "Phase 2: SKIPPED (no DEEPSEEK_API_KEY)"
fi

# --- Phase 3: Sync to Postgres ---
if [ -n "${DATABASE_URL:-}" ]; then
    log "Phase 3: Syncing to Postgres..."
    python3 scripts/sync_classifications.py >> "$LOG" 2>&1 || log "WARN: sync had errors"
else
    log "Phase 3: SKIPPED (no DATABASE_URL)"
fi

log "=== Daily sync complete ==="
