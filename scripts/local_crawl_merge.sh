#!/bin/bash
# Local-crawl-and-merge for datacenter-IP-blocked but RESIDENTIAL-reachable Chinese gov
# sites (the `group="residential"` sites in crawlers/govcms.py — provinces the NYC
# droplet's datacenter IP cannot reach, but a residential IP can: Sichuan, Tianjin,
# Guizhou, Hainan, Xinjiang, Hebei, ...).
#
# Run this from a RESIDENTIAL machine (e.g. the Mac). It crawls those sites LOCALLY to a
# throwaway DB, ships that DB to the droplet, and merges it into the live documents.db
# (merge_db.py dedups by URL, so re-runs are idempotent — safe to cron).
#
#   ./scripts/local_crawl_merge.sh
#   DROPLET=root@1.2.3.4 ./scripts/local_crawl_merge.sh    # override target
#
# Recurring coverage: add to the residential machine's crontab, e.g. weekly:
#   0 7 * * 1  cd /path/to/china-governance && ./scripts/local_crawl_merge.sh >> logs/local_crawl.log 2>&1
#
# NOTE: only body_text_cn is merged into the corpus (raw_html files stay on the crawling
# machine — the /raw_html/ web view won't have them for these docs, but the document
# pages render from body_text_cn). citations + scores reconcile on the droplet's nightly.
set -uo pipefail
cd "$(dirname "$0")/.."
DROPLET="${DROPLET:-root@104.236.88.45}"
TMPDB="documents_residential.db"

echo "[$(date +%Y-%m-%d\ %H:%M)] crawling group=residential from $(hostname) (residential IP)…"
rm -f "$TMPDB"
python3 -m crawlers.govcms --group residential --db "$TMPDB"
N=$(sqlite3 "$TMPDB" "SELECT COUNT(*) FROM documents;" 2>/dev/null || echo 0)
echo "[$(date +%H:%M)] crawled $N docs into $TMPDB"

if [ "$N" -gt 0 ]; then
    echo "[$(date +%H:%M)] shipping to droplet + merging…"
    rsync -az "$TMPDB" "$DROPLET:/root/china-governance/$TMPDB"
    ssh "$DROPLET" "cd /root/china-governance && python3 scripts/merge_db.py $TMPDB && rm -f $TMPDB && systemctl restart chinagovernance"
    echo "[$(date +%H:%M)] merged. citations/scores reconcile on the droplet's nightly run."
else
    echo "[$(date +%H:%M)] nothing crawled — skipping merge (check residential reachability)."
fi
