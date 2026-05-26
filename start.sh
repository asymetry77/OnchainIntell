#!/bin/bash
# ── OnchainIntell — Server Startup Script ─────────────────────────
# Usage: ./start.sh

set -e
cd "$(dirname "$0")"

# Colors
G='\033[0;32m'; Y='\033[1;33m'; C='\033[0;36m'; R='\033[0m'; B='\033[1m'

echo ""
echo -e "${C}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${R}"
echo -e "${B}  ⚡ OnchainIntell — Insider Wallet Tracker${R}"
echo -e "${C}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${R}"
echo ""

# Kill any existing server on port 8000
if lsof -ti:8000 >/dev/null 2>&1; then
  echo -e "${Y}  Stopping existing server on port 8000...${R}"
  kill $(lsof -ti:8000) 2>/dev/null || true
  sleep 1
fi

# Activate venv
source venv/bin/activate

# Check API key
if [ -z "$ARKHAM_API_KEY" ] && [ -f .env ]; then
  source .env 2>/dev/null || true
fi

if [ -z "$ARKHAM_API_KEY" ]; then
  echo -e "${Y}  ⚠ ARKHAM_API_KEY not set — API calls will fail${R}"
  echo ""
fi

# Stats
WALLETS=$(python3 -c "import json; d=json.load(open('data/watchlist.json')); print(len(d.get('wallets',[])))" 2>/dev/null || echo "0")
SNAPS=$(ls data/snapshots/*.json 2>/dev/null | wc -l || echo "0")

echo -e "  ${G}●${R} Wallets tracked : ${B}${WALLETS}${R}"
echo -e "  ${G}●${R} Snapshots saved : ${B}${SNAPS}${R}"
echo ""
echo -e "${C}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${R}"
echo -e "  ${G}Dashboard:${R}  ${B}http://localhost:8000${R}"
echo -e "  ${G}API Docs:${R}   ${B}http://localhost:8000/docs${R}"
echo -e "${C}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${R}"
echo ""
echo -e "  ${Y}Press Ctrl+C to stop${R}"
echo ""

# Start server with visible logs
exec uvicorn api_server:app \
  --host 0.0.0.0 \
  --port 8000 \
  --log-level info \
  --access-log
