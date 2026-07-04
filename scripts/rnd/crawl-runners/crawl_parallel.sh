#!/bin/bash
# Parallel expansion crawl — 4 workers for 13 remaining sites
# SQLite WAL + busy_timeout=30000 handles concurrent writers
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

# Split 13 sites across 4 workers (~3-4 sites each)
# Roughly balance by expected size (larger cities first)
crawl_batch "W1" shantou zhanjiang chaozhou &
crawl_batch "W2" zhaoqing shaoguan yangjiang &
crawl_batch "W3" heyuan shanwei jieyang yunfu &
crawl_batch "W4" szyantian szlg szdp &

echo "All 4 workers launched. Waiting..."
wait
echo "=== All workers done at $(date) ==="
python3 -m crawlers.gkmlpt --stats
