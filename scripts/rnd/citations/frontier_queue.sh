#!/bin/bash
# One-off orchestrator: after the running State Council gw backfill finishes, run
# the queued frontier round — bm backfill (central ministries) -> rebuild citations
# (normalization v2) -> score -> publish -> print the new frontier.
#
# Holds the daily-sync lock so the 06:00 nightly skips cleanly (no write contention;
# this round does citations+scores+publish itself). One day's other-site incremental
# crawls are skipped — self-heals next night. Launch with nohup.
set -u
cd /root/china-governance || exit 1
LOG="logs/frontier_queue_$(date -u +%Y%m%d_%H%M).log"
exec >> "$LOG" 2>&1

echo "[$(date -u)] frontier_queue: waiting for gw backfill to finish..."
while pgrep -f "crawlers.gov --library --deep --categories gw" >/dev/null; do sleep 60; done
echo "[$(date -u)] gw backfill finished."

LOCK=/tmp/china-governance-daily-sync.lock.d
tries=0
until mkdir "$LOCK" 2>/dev/null; do
  sleep 30; tries=$((tries + 1))
  if [ "$tries" -gt 120 ]; then echo "[$(date -u)] lock wait >60min; proceeding anyway"; break; fi
done
trap 'rmdir "$LOCK" 2>/dev/null' EXIT
echo "[$(date -u)] lock acquired; starting queued round."

set -a; source .env; set +a

echo "[$(date -u)] === Phase A: bm backfill (central ministries: MOF/NDRC/NHC/民政/PBOC/...) ==="
timeout 21600 .venv/bin/python3 -m crawlers.gov --library --deep --categories bm || echo "  bm errors/timeout"

echo "[$(date -u)] === Phase B: rebuild citations (normalization v2 + new gw/bm docs) ==="
timeout 3600 .venv/bin/python3 scripts/rnd/citations/extract_citations.py || echo "  extract errors/timeout"

echo "[$(date -u)] === Phase C: compute scores ==="
timeout 1200 .venv/bin/python3 scripts/compute_scores.py || echo "  scores errors/timeout"

echo "[$(date -u)] === Phase D: publish (WAL checkpoint + restart web app) ==="
sqlite3 documents.db "PRAGMA wal_checkpoint(TRUNCATE);" || true
systemctl restart chinagovernance || true

echo "[$(date -u)] === Frontier after this round ==="
.venv/bin/python3 scripts/rnd/citations/cluster_frontier.py --top 18
echo "[$(date -u)] frontier_queue DONE"
