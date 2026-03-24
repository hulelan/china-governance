#!/bin/bash
# Deploy the daily crawl pipeline to the DigitalOcean droplet.
# Run locally: bash server/deploy-crawl.sh
#
# What it does:
#   1. Clones/pulls the repo on the droplet
#   2. Installs Python dependencies (PyMuPDF for PDF extraction)
#   3. Installs systemd timer + service for daily 6am UTC crawls
#   4. Starts the timer

set -e

DROPLET="root@209.97.149.12"
REMOTE_DIR="/root/china-governance"
REPO_URL="https://github.com/hulelan/china-governance.git"

echo "=== Deploying Daily Crawl Pipeline ==="

# 1. Clone or pull repo
echo "Setting up repo..."
ssh $DROPLET "
    if [ -d $REMOTE_DIR/.git ]; then
        cd $REMOTE_DIR && git pull
    else
        git clone $REPO_URL $REMOTE_DIR
    fi
    mkdir -p $REMOTE_DIR/logs
"

# 2. Install Python dependencies
echo "Installing Python dependencies..."
ssh $DROPLET "
    pip3 install PyMuPDF psycopg2-binary --break-system-packages 2>/dev/null \
    || pip3 install PyMuPDF psycopg2-binary
"

# 3. Install systemd units
echo "Installing systemd timer + service..."
ssh $DROPLET "
    cp $REMOTE_DIR/server/daily-crawl.service /etc/systemd/system/
    cp $REMOTE_DIR/server/daily-crawl.timer /etc/systemd/system/
    systemctl daemon-reload
    systemctl enable daily-crawl.timer
    systemctl start daily-crawl.timer
"

# 4. Verify
echo ""
echo "=== Deployment Complete ==="
echo "Timer status:"
ssh $DROPLET "systemctl status daily-crawl.timer --no-pager"
echo ""
echo "Next trigger:"
ssh $DROPLET "systemctl list-timers daily-crawl.timer --no-pager"
echo ""
echo "To run manually:  ssh $DROPLET 'cd $REMOTE_DIR && bash scripts/run_all_crawls.sh'"
echo "To check logs:    ssh $DROPLET 'tail -50 $REMOTE_DIR/logs/daily-crawl.log'"
echo "To stop:          ssh $DROPLET 'systemctl stop daily-crawl.timer'"
