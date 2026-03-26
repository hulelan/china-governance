#!/bin/bash
# One-time setup script for the Singapore DigitalOcean droplet.
# Run as root on the droplet after SSH'ing in.
#
# Usage:
#   ssh root@152.42.184.25
#   bash <(curl -s https://raw.githubusercontent.com/hulelan/china-governance/main/scripts/setup_droplet.sh)
#
# After this script, you need to:
#   1. rsync documents.db from your Mac
#   2. Edit .env with your API keys

set -euo pipefail

echo "=== Setting up China Governance crawler ==="

# --- System packages ---
apt-get update -qq
apt-get install -y -qq python3 python3-pip python3-venv git curl sqlite3

# --- Clone repo ---
cd /root
if [ -d china-governance ]; then
    echo "Repo exists, pulling latest..."
    cd china-governance && git pull
else
    git clone https://github.com/hulelan/china-governance.git
    cd china-governance
fi

# --- Python dependencies (in venv to avoid PEP 668) ---
python3 -m venv .venv
source .venv/bin/activate
pip install -q requests openai psycopg2-binary

# --- Create .env template ---
if [ ! -f .env ]; then
    cat > .env << 'EOF'
# DeepSeek API key (for classification)
DEEPSEEK_API_KEY=sk-YOUR_KEY_HERE

# Railway Postgres (for production sync)
DATABASE_URL=postgresql://postgres:yNpVZKsSVTBvGNozjIbgBsKsQAnrJQdF@gondola.proxy.rlwy.net:48854/railway
EOF
    echo "Created .env — edit it with your DeepSeek API key!"
else
    echo ".env already exists"
fi

# --- Create logs directory ---
mkdir -p logs

# --- Set up daily cron (6 AM SGT = 22:00 UTC previous day) ---
CRON_CMD="cd /root/china-governance && source .venv/bin/activate && source .env && ./scripts/daily_sync.sh >> logs/cron.log 2>&1"
CRON_LINE="0 6 * * * $CRON_CMD"

# Add cron if not already present
(crontab -l 2>/dev/null | grep -v 'daily_sync' ; echo "$CRON_LINE") | crontab -
echo "Cron installed: daily at 6 AM SGT"

echo ""
echo "=== Setup complete ==="
echo ""
echo "Next steps:"
echo "  1. From your Mac, rsync the database:"
echo "     rsync -avz --progress documents.db root@152.42.184.25:/root/china-governance/"
echo ""
echo "  2. Edit .env with your DeepSeek API key:"
echo "     nano /root/china-governance/.env"
echo ""
echo "  3. Test a manual run:"
echo "     cd /root/china-governance && source .venv/bin/activate && source .env"
echo "     ./scripts/daily_sync.sh --crawl"
echo ""
echo "  4. The cron job runs daily at 6 AM SGT automatically."
echo ""
