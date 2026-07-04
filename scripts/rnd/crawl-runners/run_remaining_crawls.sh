#!/bin/bash
# Run all remaining crawls sequentially (avoids SQLite locking)
# Started: 2026-03-02

LOG=docs/log/central-crawl.log

echo "========================================" >> $LOG
echo "=== State Council full crawl ===" >> $LOG
echo "========================================" >> $LOG
python3 -m crawlers.gov >> $LOG 2>&1
echo "" >> $LOG

echo "========================================" >> $LOG
echo "=== Guangdong Province metadata discovery ===" >> $LOG
echo "========================================" >> $LOG
python3 -m crawlers.gkmlpt --site gd >> $LOG 2>&1
echo "" >> $LOG

echo "========================================" >> $LOG
echo "=== Dev & Reform retry (DNS failures) ===" >> $LOG
echo "========================================" >> $LOG
python3 -m crawlers.gkmlpt --backfill-bodies --site fgw --backfill-delay 0.5 >> $LOG 2>&1
echo "" >> $LOG

echo "========================================" >> $LOG
echo "=== Citation re-extraction ===" >> $LOG
echo "========================================" >> $LOG
python3 scripts/extract_citations.py --force >> $LOG 2>&1
echo "" >> $LOG

echo "========================================" >> $LOG
echo "=== Final stats ===" >> $LOG
echo "========================================" >> $LOG
python3 -m crawlers.gkmlpt --stats >> $LOG 2>&1

echo "ALL DONE" >> $LOG
