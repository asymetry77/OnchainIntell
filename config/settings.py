"""
settings.py — Central configuration for OnchainIntell Insider Wallet Tracker.
Loads all environment variables and defines project-wide constants.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env file from project root
load_dotenv(Path(__file__).parent.parent / ".env")


# ── ARKHAM API ───────────────────────────────────────────────────────────────
ARKHAM_API_KEY   = os.getenv("ARKHAM_API_KEY", "")
ARKHAM_BASE_URL  = os.getenv("ARKHAM_BASE_URL", "https://api.arkm.com")
ARKHAM_HEADERS   = {
    "API-Key": ARKHAM_API_KEY,
    "Accept":  "application/json",
}

# ── WALLET TRACKER CONFIG ────────────────────────────────────────────────────
WALLET_MIN_BALANCE_USD  = float(os.getenv("WALLET_MIN_BALANCE_USD", "500000"))
DISCOVERY_MAX_WALLETS   = int(os.getenv("DISCOVERY_MAX_WALLETS", "15"))
ALERT_MIN_USD           = float(os.getenv("ALERT_MIN_USD", "500000"))
ALERT_MAX_WALLETS       = int(os.getenv("ALERT_MAX_WALLETS", "10"))

# ── DATA PATHS ───────────────────────────────────────────────────────────────
DATA_DIR      = Path(os.getenv("DATA_DIR", "./data"))
SNAPSHOT_DIR  = DATA_DIR / "snapshots"
WATCHLIST_PATH = DATA_DIR / "watchlist.json"
REPORTS_DIR   = Path(os.getenv("REPORTS_DIR", "./reports"))
LOGS_DIR      = Path(os.getenv("LOGS_DIR", "./logs"))

# ── HTTP CONFIG ───────────────────────────────────────────────────────────────
REQUEST_TIMEOUT_SECONDS = 30
REQUEST_MAX_RETRIES     = 3
REQUEST_RETRY_DELAY     = 2.0

# ── THRESHOLDS ────────────────────────────────────────────────────────────────
WHALE_THRESHOLD_USD     = float(os.getenv("WHALE_THRESHOLD_USD", "100000"))
BIG_WHALE_THRESHOLD_USD = float(os.getenv("BIG_WHALE_THRESHOLD_USD", "1000000"))
EXCHANGE_SURGE_MULTIPLIER = float(os.getenv("EXCHANGE_SURGE_MULTIPLIER", "2.0"))
PRE_DUMP_WINDOW_HOURS   = int(os.getenv("PRE_DUMP_WINDOW_HOURS", "6"))
MIN_ACCUMULATION_WALLETS = int(os.getenv("MIN_ACCUMULATION_WALLETS", "3"))

# ── EVIDENCE SCORING ─────────────────────────────────────────────────────────
SCORE_WEIGHT = {
    "named_entity":       30,
    "amount_over_100k":   15,
    "amount_over_1m":     10,
    "cex_destination":    20,
    "within_24h":         10,
    "volume_spike":       10,
    "multi_transaction":   5,
}

# ── SCANNING CONFIG ───────────────────────────────────────────────────────────
DEFAULT_LIMIT        = int(os.getenv("DEFAULT_LIMIT", "20"))
SCAN_INTERVAL_HOURS  = int(os.getenv("SCAN_INTERVAL_HOURS", "6"))

# ── MIMO AI ───────────────────────────────────────────────────────────────────
MIMO_API_KEY   = os.getenv("MIMO_API_KEY", "")
MIMO_BASE_URL  = os.getenv("MIMO_BASE_URL", "https://token-plan-sgp.xiaomimimo.com/v1")
MIMO_MODEL     = os.getenv("MIMO_MODEL", "mimo-v2.5")

# ── AUTO-POST ─────────────────────────────────────────────────────────────────
AUTO_POST_ENABLED   = os.getenv("AUTO_POST_ENABLED", "false").lower() == "true"
AUTO_POST_MIN_SCORE = int(os.getenv("AUTO_POST_MIN_SCORE", "85"))

# Ensure output directories exist
DATA_DIR.mkdir(parents=True, exist_ok=True)
SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
REPORTS_DIR.mkdir(parents=True, exist_ok=True)
LOGS_DIR.mkdir(parents=True, exist_ok=True)
