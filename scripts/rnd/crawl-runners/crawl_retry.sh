#!/bin/bash
# Retry failed sites with 2 workers (safer for SQLite)
set -e
cd /Users/lelan/Desktop/claude_code/china-governance

crawl_batch() {
    local batch_name=$1
    shift
    echo "[${batch_name}] Starting at $(date)"
    for site in "$@"; do
        echo "[${batch_name}] Crawling $site at $(date)"
        python3 -m crawlers.gkmlpt --site "$site" 2>&1 | sed "s/^/[${batch_name}] /" || echo "[${batch_name}] WARNING: $site failed"
        echo "[${batch_name}] Done $site at $(date)"
    done
    echo "[${batch_name}] Batch complete at $(date)"
}

# 9 failed sites split across 2 workers
crawl_batch "A" shantou zhanjiang chaozhou zhaoqing szyantian &
crawl_batch "B" shaoguan yangjiang szlg szdp &

echo "2 workers launched. Waiting..."
wait
echo "=== All done at $(date) ==="
python3 -m crawlers.gkmlpt --stats
