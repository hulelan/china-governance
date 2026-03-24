#!/bin/bash
# Run all crawlers sequentially, then sync to production.
# Usage: bash scripts/run_all_crawls.sh 2>&1 | tee logs/daily-crawl-$(date +%Y%m%d).log
#
# Safe to run daily — crawlers deduplicate by URL, gkmlpt uses --sync for incremental.
# Sequential execution avoids SQLite lock contention (max 1 writer at a time).

set -e
cd "$(dirname "$0")/.."
mkdir -p logs

echo "=== $(date) Starting crawl pipeline ==="

# --- Central Ministries ---

echo ""
echo ">>> MOF: Policy Releases"
python3 -m crawlers.mof --section zcfb || echo "  [WARN] MOF zcfb failed, continuing..."
echo ""
echo ">>> MOF: Finance News"
python3 -m crawlers.mof --section czxw || echo "  [WARN] MOF czxw failed, continuing..."
echo ""
echo ">>> MOF: Finance Bulletins"
python3 -m crawlers.mof --section czwg || echo "  [WARN] MOF czwg failed, continuing..."

echo ""
echo ">>> MEE: All sections"
python3 -m crawlers.mee || echo "  [WARN] MEE failed, continuing..."

echo ""
echo ">>> NDRC: Crawl"
python3 -m crawlers.ndrc || echo "  [WARN] NDRC failed, continuing..."

echo ""
echo ">>> State Council: Crawl"
python3 -m crawlers.gov || echo "  [WARN] Gov failed, continuing..."

# --- Guangdong (gkmlpt) ---

echo ""
echo ">>> gkmlpt: Incremental sync (all sites)"
python3 -m crawlers.gkmlpt --sync || echo "  [WARN] gkmlpt sync failed, continuing..."

# --- Provinces ---

echo ""
echo ">>> Beijing: All sections"
python3 -m crawlers.beijing || echo "  [WARN] Beijing failed, continuing..."

echo ""
echo ">>> Shanghai: All sections"
python3 -m crawlers.shanghai || echo "  [WARN] Shanghai failed, continuing..."

echo ""
echo ">>> Jiangsu: zcwj section"
python3 -m crawlers.jiangsu --section zcwj || echo "  [WARN] Jiangsu failed, continuing..."

# --- Post-crawl ---

echo ""
echo ">>> PDF text extraction (new attachment-only docs)"
python3 scripts/extract_pdf_text.py || echo "  [WARN] PDF extraction failed, continuing..."

echo ""
echo ">>> Stats"
python3 -m crawlers.gkmlpt --stats

# --- Production sync ---

if [ -n "$DATABASE_URL" ]; then
    echo ""
    echo ">>> Syncing to production Postgres..."
    python3 scripts/sqlite_to_postgres.py || echo "  [WARN] Postgres sync failed"
    echo ""
    echo ">>> Verifying production..."
    curl -s "https://china-governance-production.up.railway.app/api/v1/stats" | python3 -m json.tool 2>/dev/null || echo "  [WARN] Could not verify production"
else
    echo ""
    echo ">>> Skipping production sync (DATABASE_URL not set)"
fi

echo ""
echo "=== $(date) Pipeline complete ==="
