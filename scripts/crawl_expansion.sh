#!/bin/bash
# Crawl all 14 new gkmlpt sites sequentially
set -e
cd /Users/lelan/Desktop/claude_code/china-governance

NEW_SITES=(zhongshan shantou zhaoqing shaoguan heyuan shanwei yangjiang zhanjiang chaozhou jieyang yunfu szyantian szlg szdp)

echo "=== Starting expansion crawl: ${#NEW_SITES[@]} sites ==="
echo "Start time: $(date)"

for site in "${NEW_SITES[@]}"; do
    echo ""
    echo "--- Crawling $site at $(date) ---"
    python3 -m crawlers.gkmlpt --site "$site" 2>&1 || echo "WARNING: $site failed, continuing..."
    echo "--- Done $site at $(date) ---"
done

echo ""
echo "=== All sites done at $(date) ==="
python3 -m crawlers.gkmlpt --stats
