"""
entities.py — All confirmed entity slugs, exchange lists, and blockchain references.
Keep this file updated as Arkham expands its label database.
"""

# ── VENTURE CAPITAL ───────────────────────────────────────────────────────────
VC_ENTITIES = [
    "a16z",
    "paradigm-xyz",
    "paradigm-capital",
    "multicoin-capital",
    "pantera-capital",
    "dragonfly-capital",
    "polychain-capital",
    "galaxy-digital",
]

# ── CENTRALIZED EXCHANGES ──────────────────────────────────────────────────────
CEX_ENTITIES = [
    "binance",
    "coinbase",
    "bybit",
    "okx",
    "kraken",
]

# ── PROTOCOLS / DEFI ───────────────────────────────────────────────────────────
PROTOCOL_ENTITIES = [
    "uniswap",
    "aave",
    "compound",
    "lido",
]

# ── MARKET MAKERS ─────────────────────────────────────────────────────────────
MARKET_MAKER_ENTITIES = [
    "wintermute",
    "jump-trading",
]

# ── NOTABLE / FORENSIC ────────────────────────────────────────────────────────
NOTABLE_ENTITIES = [
    "alameda-research",
    "ftx",
    "lazarus-group",
]

# ── ALL ENTITIES COMBINED ─────────────────────────────────────────────────────
ALL_ENTITIES = (
    VC_ENTITIES
    + CEX_ENTITIES
    + PROTOCOL_ENTITIES
    + MARKET_MAKER_ENTITIES
    + NOTABLE_ENTITIES
)

# ── TOKEN SLUGS (confirmed in Arkham) ─────────────────────────────────────────
KNOWN_TOKEN_SLUGS = {
    "BTC":  "bitcoin",
    "ETH":  "ethereum",
    "USDT": "tether",
    "PEPE": "pepe",
    "ARB":  "arbitrum",
    "SOL":  "solana",
    "BNB":  "binance-coin",
    "USDC": "usd-coin",
    "MATIC":"polygon",
    "LINK": "chainlink",
    "UNI":  "uniswap",
    "AAVE": "aave",
    "CRV":  "curve-dao-token",
    "LDO":  "lido-dao",
    "OP":   "optimism",
}

# ── SUPPORTED CHAINS ──────────────────────────────────────────────────────────
SUPPORTED_CHAINS = [
    "ethereum",
    "solana",
    "bitcoin",
    "base",
    "arbitrum_one",
    "bsc",
    "polygon",
    "optimism",
    "avalanche",
]

# ── BLOCKCHAIN EXPLORERS (for tx hash verification links) ─────────────────────
EXPLORERS = {
    "ethereum":     "https://etherscan.io/tx/",
    "bitcoin":      "https://mempool.space/tx/",
    "solana":       "https://solscan.io/tx/",
    "base":         "https://basescan.org/tx/",
    "arbitrum_one": "https://arbiscan.io/tx/",
    "bsc":          "https://bscscan.com/tx/",
    "polygon":      "https://polygonscan.com/tx/",
    "optimism":     "https://optimistic.etherscan.io/tx/",
    "avalanche":    "https://snowtrace.io/tx/",
}

# ── INSIDER LABEL KEYWORDS ────────────────────────────────────────────────────
# Labels in Arkham that indicate insider/team wallets
INSIDER_LABEL_KEYWORDS = [
    "team",
    "founder",
    "treasury",
    "deployer",
    "multisig",
    "vesting",
    "advisor",
    "ceo",
    "cto",
    "developer",
    "core",
    "protocol",
    "dao",
    "reserve",
    "fund",
]

# ── EVENT TYPES ───────────────────────────────────────────────────────────────
EVENT_TYPES = {
    "INSIDER_DUMP":        "insider_dump",
    "PRE_DUMP_WARNING":    "pre_dump_warning",
    "CATCH_THE_LIE":       "catch_the_lie",
    "SILENT_ACCUMULATION": "silent_accumulation",
}

# ── TIME WINDOWS ──────────────────────────────────────────────────────────────
TIME_WINDOWS = {
    "24h":  "24h",
    "7d":   "7d",
    "30d":  "30d",
}
