#!/bin/bash
# Run all pending crawls sequentially to avoid SQLite lock conflicts.
# Usage: bash scripts/run_all_crawls.sh 2>&1 | tee docs/log/all-crawls-$(date +%Y%m%d).log

set -e
cd "$(dirname "$0")/.."

echo "=== $(date) Starting crawl pipeline ==="

# 1. MOF — policy releases (HTML) + finance bulletins (PDF)
echo ""
echo ">>> MOF: Policy Releases (HTML)"
python3 -m crawlers.mof --section zcfb
echo ""
echo ">>> MOF: Finance News (HTML)"
python3 -m crawlers.mof --section czxw
echo ""
echo ">>> MOF: Finance Bulletins (PDF)"
python3 -m crawlers.mof --section czwg

# 2. MEE — all sections
echo ""
echo ">>> MEE: All sections"
python3 -m crawlers.mee

# 3. Resume gkmlpt sync for all sites
echo ""
echo ">>> gkmlpt: Incremental sync (all sites)"
python3 -m crawlers.gkmlpt --sync

# 4. NDRC sync
echo ""
echo ">>> NDRC: Crawl"
python3 -m crawlers.ndrc

# 5. State Council sync
echo ""
echo ">>> State Council: Crawl"
python3 -m crawlers.gov

echo ""
echo "=== $(date) All crawls complete ==="
python3 -m crawlers.gkmlpt --stats
