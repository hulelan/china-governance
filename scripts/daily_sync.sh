#!/bin/bash
# Daily crawl + classify + sync pipeline.
# Runs on both local Mac (via launchd) and Singapore droplet (via cron).
# Sends a detailed Telegram report when done.
#
# Usage:
#   ./scripts/daily_sync.sh          # Run full pipeline
#   ./scripts/daily_sync.sh --crawl  # Crawl only (no classify/sync)
#
# Required env vars: DEEPSEEK_API_KEY, DATABASE_URL
# Optional env vars: TELEGRAM_BOT_TOKEN, TELEGRAM_USER_ID

set -uo pipefail
cd "$(dirname "$0")/.."

# Load environment
source .env 2>/dev/null || true

# macOS doesn't have `timeout` — use gtimeout (from brew coreutils) or a bash fallback
if ! command -v timeout &>/dev/null; then
    if command -v gtimeout &>/dev/null; then
        timeout() { gtimeout "$@"; }
    else
        # Pure bash fallback: run command with a background watchdog
        timeout() {
            local duration="$1"; shift
            "$@" &
            local pid=$!
            ( sleep "$duration" && kill "$pid" 2>/dev/null ) &
            local watchdog=$!
            wait "$pid" 2>/dev/null
            local ret=$?
            kill "$watchdog" 2>/dev/null
            wait "$watchdog" 2>/dev/null
            # Return 124 (like GNU timeout) if the process was killed
            if [ $ret -ne 0 ] && ! kill -0 "$pid" 2>/dev/null; then
                return 124
            fi
            return $ret
        }
    fi
fi

LOGDIR="logs"
mkdir -p "$LOGDIR"
LOG="$LOGDIR/daily-$(date +%Y%m%d-%H%M).log"
HOST=$(hostname -s)
START_TIME=$(date +%s)

# Detect if we're on the dev Mac (vs droplet). Mac hostname is unstable (DHCP),
# so check the OS instead.
IS_MAC=false
if [ "$(uname)" = "Darwin" ]; then
    IS_MAC=true
fi

log() { echo "[$(date +%H:%M:%S)] $1" | tee -a "$LOG"; }

# Auto-update code on remote servers (not on dev Mac)
if [ "$IS_MAC" != "true" ]; then
    git pull --ff-only >> "$LOG" 2>&1 || echo "[$(date +%H:%M:%S)] git pull failed, continuing" >> "$LOG"
fi

send_telegram() {
    if [ -n "${TELEGRAM_BOT_TOKEN:-}" ] && [ -n "${TELEGRAM_USER_ID:-}" ]; then
        local msg="$1"
        # Try Markdown first, fall back to plain text if parsing fails
        local result
        result=$(curl -s -X POST "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" \
            -d "chat_id=${TELEGRAM_USER_ID}" \
            -d "text=${msg}" \
            -d "parse_mode=Markdown" 2>&1)
        if echo "$result" | grep -q '"ok":false'; then
            # Markdown failed (underscores, unmatched asterisks, etc.) — send as plain text
            curl -s -X POST "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" \
                -d "chat_id=${TELEGRAM_USER_ID}" \
                -d "text=${msg}" \
                > /dev/null 2>&1 || true
        fi
    fi
}

# --- Pre-flight: Save manifest + check for regressions ---
BACKUP_DIR="backups"
mkdir -p "$BACKUP_DIR"
MANIFEST="$BACKUP_DIR/manifest_$(date +%Y%m%d).csv"
PREV_MANIFEST=$(ls -t "$BACKUP_DIR"/manifest_*.csv 2>/dev/null | head -1)
if [ ! -f "$MANIFEST" ]; then
    # Lightweight manifest: id, url, site_key, body_length (~1MB for 116k docs)
    sqlite3 -csv documents.db \
        "SELECT id, url, site_key, LENGTH(COALESCE(body_text_cn,'')) FROM documents ORDER BY id" \
        > "$MANIFEST" 2>/dev/null
    log "Manifest: $MANIFEST ($(wc -l < "$MANIFEST") docs)"
    # Compare against previous manifest
    if [ -n "$PREV_MANIFEST" ] && [ "$PREV_MANIFEST" != "$MANIFEST" ]; then
        PREV_COUNT=$(wc -l < "$PREV_MANIFEST")
        CURR_COUNT=$(wc -l < "$MANIFEST")
        if [ "$CURR_COUNT" -lt "$PREV_COUNT" ]; then
            LOST=$((PREV_COUNT - CURR_COUNT))
            log "  WARNING: $LOST documents disappeared since $(basename "$PREV_MANIFEST")"
        fi
    fi
    # Keep last 14 days of manifests (tiny files)
    find "$BACKUP_DIR" -name "manifest_*.csv" -mtime +14 -delete 2>/dev/null || true
fi

# Snapshot doc count before crawl
DOC_COUNT_BEFORE=$(sqlite3 documents.db 'SELECT COUNT(*) FROM documents' 2>/dev/null || echo 0)
CLASSIFIED_BEFORE=$(sqlite3 documents.db "SELECT COUNT(*) FROM documents WHERE classified_at != '' AND classified_at IS NOT NULL" 2>/dev/null || echo 0)

log "=== Daily sync started on $HOST ==="
log "Starting state: $DOC_COUNT_BEFORE docs, $CLASSIFIED_BEFORE classified"

# Track per-crawler results
CRAWL_RESULTS=""
CRAWL_ERRORS=""
CRAWL_OK=0
CRAWL_FAIL=0

CRAWLER_TIMEOUT=1800  # 30 minutes per crawler (prevents pipeline stalls)

run_crawler() {
    local name="$1"
    shift
    local before=$(sqlite3 documents.db 'SELECT COUNT(*) FROM documents' 2>/dev/null || echo 0)
    log "  Crawling $name..."
    if timeout "$CRAWLER_TIMEOUT" "$@" >> "$LOG" 2>&1; then
        local after=$(sqlite3 documents.db 'SELECT COUNT(*) FROM documents' 2>/dev/null || echo 0)
        local new=$((after - before))
        CRAWL_RESULTS="${CRAWL_RESULTS}✅ ${name}: +${new} docs\n"
        CRAWL_OK=$((CRAWL_OK + 1))
    else
        local exit_code=$?
        local after=$(sqlite3 documents.db 'SELECT COUNT(*) FROM documents' 2>/dev/null || echo 0)
        local new=$((after - before))
        if [ "$exit_code" -eq 124 ]; then
            CRAWL_RESULTS="${CRAWL_RESULTS}⏰ ${name}: +${new} docs (timeout after ${CRAWLER_TIMEOUT}s)\n"
        else
            CRAWL_RESULTS="${CRAWL_RESULTS}⚠️ ${name}: +${new} docs (errors)\n"
        fi
        CRAWL_ERRORS="${CRAWL_ERRORS}${name}: $(tail -5 "$LOG" | grep -i 'error\|fail\|timeout' | head -2)\n"
        CRAWL_FAIL=$((CRAWL_FAIL + 1))
    fi
}

# --- Phase 1: Crawl all sources ---
log "Phase 1: Crawling..."

run_crawler "gkmlpt (40+ sites)" python3 -m crawlers.gkmlpt --sync

for crawler in gov ndrc mof mee cac nda sic samr mofcom ipc_court; do
    run_crawler "$crawler" python3 -m crawlers.$crawler
done

for crawler in beijing shanghai jiangsu chongqing wuhan suzhou heilongjiang; do
    run_crawler "$crawler" python3 -m crawlers.$crawler
done

# Research institutions
run_crawler "tsinghua_aiig" python3 -m crawlers.tsinghua_aiig

run_crawler "sz_invest (9 sections)" python3 -m crawlers.sz_invest

# Media / tech news crawlers
for crawler in 36kr latepost ifeng xinhua people stdaily; do
    run_crawler "$crawler" python3 -m crawlers.$crawler
done

# Guancha runs in --deep mode to pick up section pages + columnists
run_crawler "guancha" python3 -m crawlers.guancha --deep

# Location-specific crawlers
if [ "$IS_MAC" = "true" ]; then
    # These gkmlpt sites are unreachable from the Singapore droplet
    for site in gd huizhou yangjiang; do
        run_crawler "gkmlpt ($site)" python3 -m crawlers.gkmlpt --site $site
    done
    # These are slow/partial from US but still fetch some data (droplet assumed down)
    for crawler in miit most zhejiang hangzhou; do
        run_crawler "$crawler" python3 -m crawlers.$crawler
    done
else
    # Droplet: these APIs work well from Singapore
    for crawler in miit most zhejiang hangzhou; do
        run_crawler "$crawler" python3 -m crawlers.$crawler
    done
fi

DOC_COUNT_AFTER_CRAWL=$(sqlite3 documents.db 'SELECT COUNT(*) FROM documents' 2>/dev/null || echo 0)
NEW_DOCS=$((DOC_COUNT_AFTER_CRAWL - DOC_COUNT_BEFORE))

log "Phase 1 done. $DOC_COUNT_AFTER_CRAWL total docs (+$NEW_DOCS new)"

if [ "${1:-}" = "--crawl" ]; then
    log "=== Crawl-only mode, stopping ==="
    # Still send report for crawl-only
    ELAPSED=$(( $(date +%s) - START_TIME ))
    REPORT="🕷 *Crawl Report* ($HOST)
━━━━━━━━━━━━━━━━━━
📊 *Results:* +$NEW_DOCS new docs
📁 *Total:* $DOC_COUNT_AFTER_CRAWL docs
⏱ *Duration:* $((ELAPSED / 60))m $((ELAPSED % 60))s
✅ *OK:* $CRAWL_OK crawlers
$([ $CRAWL_FAIL -gt 0 ] && echo "⚠️ *Failed:* $CRAWL_FAIL crawlers")

*Per crawler:*
$(echo -e "$CRAWL_RESULTS")$([ -n "$CRAWL_ERRORS" ] && echo -e "\n*Errors:*\n$CRAWL_ERRORS")"
    send_telegram "$REPORT"
    exit 0
fi

# --- Phase 2: Classify new docs ---
CLASSIFIED_NEW=0
CLASSIFY_ERRORS=0
if [ -n "${DEEPSEEK_API_KEY:-}" ]; then
    UNCLASSIFIED=$(sqlite3 documents.db "SELECT COUNT(*) FROM documents WHERE classified_at = '' OR classified_at IS NULL" 2>/dev/null || echo 0)
    if [ "$UNCLASSIFIED" -gt 0 ]; then
        log "Phase 2: Classifying $UNCLASSIFIED unclassified docs..."
        CLASSIFY_OUTPUT=$(python3 scripts/classify_documents.py --concurrency 2 2>&1 | tee -a "$LOG")
        # Extract counts from output: "Done: X/Y classified, Z errors"
        CLASSIFIED_NEW=$(echo "$CLASSIFY_OUTPUT" | grep -o 'Done: [0-9,]*' | grep -o '[0-9,]*' | tr -d ',' || echo 0)
        CLASSIFY_ERRORS=$(echo "$CLASSIFY_OUTPUT" | grep -o '[0-9,]* errors' | grep -o '[0-9,]*' | tr -d ',' || echo 0)
    else
        log "Phase 2: No new docs to classify"
    fi
else
    log "Phase 2: SKIPPED (no DEEPSEEK_API_KEY)"
fi

CLASSIFIED_AFTER=$(sqlite3 documents.db "SELECT COUNT(*) FROM documents WHERE classified_at != '' AND classified_at IS NOT NULL" 2>/dev/null || echo 0)
NEWLY_CLASSIFIED=$((CLASSIFIED_AFTER - CLASSIFIED_BEFORE))

# --- Phase 3: Rsync DB to production droplet ---
RSYNC_OK=false
DROPLET_IP="104.236.88.45"
if ssh -o ConnectTimeout=5 -o BatchMode=yes root@$DROPLET_IP true 2>/dev/null; then
    log "Phase 3: Rsyncing DB to droplet ($DROPLET_IP)..."
    # Checkpoint WAL so all data is in the main DB file before rsync
    sqlite3 documents.db "PRAGMA wal_checkpoint(TRUNCATE);" >> "$LOG" 2>&1 || true
    # Also checkpoint officials.db if present
    [ -f officials.db ] && sqlite3 officials.db "PRAGMA wal_checkpoint(TRUNCATE);" >> "$LOG" 2>&1 || true
    [ -f officials.db ] && rsync -az officials.db root@$DROPLET_IP:/root/china-governance/officials.db >> "$LOG" 2>&1 || true
    if rsync -az documents.db root@$DROPLET_IP:/root/china-governance/documents.db >> "$LOG" 2>&1; then
        # Restart the web app to pick up new data
        ssh root@$DROPLET_IP 'systemctl restart chinagovernance' >> "$LOG" 2>&1 || true
        REMOTE_COUNT=$(ssh root@$DROPLET_IP 'sqlite3 /root/china-governance/documents.db "SELECT COUNT(*) FROM documents"' 2>/dev/null || echo "?")
        log "  Synced: $REMOTE_COUNT docs on droplet"
        RSYNC_OK=true
    else
        log "  ERROR: rsync failed"
    fi
else
    log "Phase 3: SKIPPED (droplet unreachable)"
fi

# Weekly VACUUM to reclaim space (droplet only, Sundays)
if [ "$(date +%u)" = "7" ] && [ "$IS_MAC" != "true" ]; then
    log "Weekly VACUUM..."
    sqlite3 documents.db "VACUUM;" >> "$LOG" 2>&1 || true
fi

# --- Phase 4: Generate report ---
ELAPSED=$(( $(date +%s) - START_TIME ))
DOC_COUNT_FINAL=$(sqlite3 documents.db 'SELECT COUNT(*) FROM documents' 2>/dev/null || echo 0)

# Get importance breakdown
HIGH=$(sqlite3 documents.db "SELECT COUNT(*) FROM documents WHERE importance = 'high'" 2>/dev/null || echo "?")
MEDIUM=$(sqlite3 documents.db "SELECT COUNT(*) FROM documents WHERE importance = 'medium'" 2>/dev/null || echo "?")
LOW=$(sqlite3 documents.db "SELECT COUNT(*) FROM documents WHERE importance = 'low'" 2>/dev/null || echo "?")

# Get per-site new doc counts (top 5 sites with most new docs today)
TOP_SITES=$(sqlite3 documents.db "SELECT site_key || ': ' || COUNT(*) FROM documents WHERE date(crawl_timestamp) = date('now') GROUP BY site_key ORDER BY COUNT(*) DESC LIMIT 5" 2>/dev/null || echo "")

# Get sample new docs with links (up to 10, prioritize high importance)
SAMPLE_DOCS=$(sqlite3 documents.db "
    SELECT id, title_en, title, importance, url FROM documents
    WHERE date(crawl_timestamp) = date('now')
    ORDER BY
        CASE importance WHEN 'high' THEN 0 WHEN 'medium' THEN 1 ELSE 2 END,
        date_written DESC
    LIMIT 10
" 2>/dev/null || echo "")

# Format sample docs with links
SAMPLE_LINES=""
if [ -n "$SAMPLE_DOCS" ]; then
    while IFS='|' read -r doc_id title_en title importance url; do
        # Use English title if available, else Chinese (truncated)
        display_title="${title_en:-${title}}"
        display_title="${display_title:0:60}"
        # Importance emoji
        case "$importance" in
            high)   imp="🔴" ;;
            medium) imp="🟡" ;;
            *)      imp="⚪" ;;
        esac
        SAMPLE_LINES="${SAMPLE_LINES}${imp} [${display_title}](https://www.chinagovernance.com/document/${doc_id})
   ↳ [source](${url})
"
    done <<< "$SAMPLE_DOCS"
fi

REPORT="📋 *Daily Sync Report* ($HOST)
━━━━━━━━━━━━━━━━━━
⏱ *Duration:* $((ELAPSED / 60))m $((ELAPSED % 60))s

📥 *Crawling:*
• New docs: +$NEW_DOCS
• Crawlers OK: $CRAWL_OK | Failed: $CRAWL_FAIL
$(echo -e "$CRAWL_RESULTS")
🤖 *Classification:*
• Newly classified: +$NEWLY_CLASSIFIED
• Classification errors: ${CLASSIFY_ERRORS:-0}
• Total classified: $CLASSIFIED_AFTER / $DOC_COUNT_FINAL

🗄 *Database:*
• SQLite total: $DOC_COUNT_FINAL docs
• Droplet: ${REMOTE_COUNT:-?} docs (rsync: $RSYNC_OK)
• 🔴 High: $HIGH | 🟡 Medium: $MEDIUM | ⚪ Low: $LOW
$([ -n "$TOP_SITES" ] && echo "
📍 *Top sites today:*
$TOP_SITES")$([ -n "$SAMPLE_LINES" ] && echo "
📄 *New docs:*
$SAMPLE_LINES")$([ -n "$CRAWL_ERRORS" ] && echo "
❗ *Errors:*
$(echo -e "$CRAWL_ERRORS")")
📁 Log: $LOG"

send_telegram "$REPORT"
log "=== Daily sync complete ==="
log "Report sent to Telegram"
