"""
helpers.py — Shared utility functions for timestamp handling,
USD formatting, evidence scoring, and explorer link generation.
"""

import time
import math
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional

logger = logging.getLogger(__name__)


# ── TIMESTAMP UTILITIES ───────────────────────────────────────────────────────

def now_unix_ms() -> int:
    """Current UTC time in milliseconds (Arkham format)."""
    return int(time.time()) * 1000


def days_ago_unix_ms(days: int) -> int:
    """Unix timestamp in ms for N days ago."""
    return int(time.time() - days * 24 * 3600) * 1000


def hours_ago_unix_ms(hours: int) -> int:
    """Unix timestamp in ms for N hours ago."""
    return int(time.time() - hours * 3600) * 1000


def unix_ms_to_dt(unix_ms: int) -> datetime:
    """Convert Arkham unix_ms timestamp to UTC datetime."""
    return datetime.fromtimestamp(unix_ms / 1000, tz=timezone.utc)


def iso_to_unix_ms(iso_string: str) -> int:
    """
    Convert ISO 8601 string (e.g. '2024-01-15T10:30:00Z') to unix_ms.
    """
    dt = datetime.fromisoformat(iso_string.replace("Z", "+00:00"))
    return int(dt.timestamp()) * 1000


def human_time_ago(unix_ms) -> str:
    """
    Convert a unix_ms timestamp to a human-readable 'X lalu' string.
    Accepts int (unix_ms) or str (ISO 8601 format).
    Examples: "5 menit lalu", "3 jam lalu", "2 hari lalu"
    """
    if isinstance(unix_ms, str):
        try:
            unix_ms = iso_to_unix_ms(unix_ms)
        except (ValueError, TypeError):
            return "unknown time"
    if not isinstance(unix_ms, (int, float)):
        return "unknown time"
    now_ms  = int(time.time()) * 1000
    diff_s  = (now_ms - unix_ms) / 1000

    if diff_s < 60:
        return f"{int(diff_s)} detik lalu"
    elif diff_s < 3600:
        return f"{int(diff_s / 60)} menit lalu"
    elif diff_s < 86400:
        return f"{int(diff_s / 3600)} jam lalu"
    elif diff_s < 86400 * 7:
        return f"{int(diff_s / 86400)} hari lalu"
    else:
        return f"{int(diff_s / 86400 / 7)} minggu lalu"


def format_date(unix_ms: int) -> str:
    """Format unix_ms to readable date: '15 Jan 2024, 10:30 UTC'"""
    dt = unix_ms_to_dt(unix_ms)
    return dt.strftime("%d %b %Y, %H:%M UTC")


# ── USD FORMATTING ────────────────────────────────────────────────────────────

def format_usd(amount: float) -> str:
    """
    Format a USD amount to human-readable string.
    $1,234 → $1.2K
    $1,234,567 → $1.2M
    $1,234,567,890 → $1.2B
    """
    if amount is None:
        return "$0"
    abs_amount = abs(amount)
    sign = "-" if amount < 0 else ""

    if abs_amount >= 1_000_000_000:
        return f"{sign}${abs_amount / 1_000_000_000:.1f}B"
    elif abs_amount >= 1_000_000:
        return f"{sign}${abs_amount / 1_000_000:.1f}M"
    elif abs_amount >= 1_000:
        return f"{sign}${abs_amount / 1_000:.1f}K"
    else:
        return f"{sign}${abs_amount:,.0f}"


def format_pct(value: float, show_plus: bool = True) -> str:
    """Format percentage: 34.5 → '+34.5%', -12.3 → '-12.3%'"""
    prefix = "+" if value > 0 and show_plus else ""
    return f"{prefix}{value:.1f}%"


# ── EXPLORER LINKS ────────────────────────────────────────────────────────────

def get_explorer_link(tx_hash: str, chain: str = "ethereum") -> str:
    """
    Build blockchain explorer verification URL for a tx hash.
    Defaults to Etherscan for EVM transactions.
    """
    from config.entities import EXPLORERS

    base_url = EXPLORERS.get(chain, EXPLORERS["ethereum"])
    return f"{base_url}{tx_hash}"


def format_tx_for_post(tx_hash: str, chain: str = "ethereum") -> str:
    """
    Format a tx hash for inclusion in X/Twitter post.
    Returns: 'TX: 0x1a2b...9f0a\nVerify: https://etherscan.io/tx/0x...'
    """
    link = get_explorer_link(tx_hash, chain)
    short_hash = f"{tx_hash[:10]}…{tx_hash[-6:]}"
    return f"TX: {short_hash}\nVerify: {link}"


# ── EVIDENCE SCORING ──────────────────────────────────────────────────────────

def calculate_evidence_score(flags: dict) -> int:
    """
    Calculate a 0–100 evidence score based on detected signals.

    flags dict example:
    {
        "named_entity_confirmed": True,
        "amount_above_whale":     True,
        "amount_above_big_whale": False,
        "exchange_destination":   True,
        "recent_within_24h":      True,
        "histogram_surge":        True,
        "multiple_transactions":  False,
    }
    """
    from config.settings import SCORE_WEIGHT

    score = 0
    for flag, is_true in flags.items():
        if is_true and flag in SCORE_WEIGHT:
            score += SCORE_WEIGHT[flag]

    return min(score, 100)


def build_evidence_flags(
    has_named_entity:       bool = False,
    amount_usd:             float = 0,
    goes_to_exchange:       bool = False,
    hours_since_transfer:   float = 999,
    histogram_surge:        bool = False,
    transaction_count:      int = 1,
) -> dict:
    """
    Build the flags dict from raw detection values.
    Returns dict ready for calculate_evidence_score().
    """
    from config.settings import WHALE_THRESHOLD_USD, BIG_WHALE_THRESHOLD_USD

    return {
        "named_entity_confirmed": has_named_entity,
        "amount_above_whale":     amount_usd >= WHALE_THRESHOLD_USD,
        "amount_above_big_whale": amount_usd >= BIG_WHALE_THRESHOLD_USD,
        "exchange_destination":   goes_to_exchange,
        "recent_within_24h":      hours_since_transfer <= 24,
        "histogram_surge":        histogram_surge,
        "multiple_transactions":  transaction_count >= 3,
    }


# ── TRANSFER PARSING ──────────────────────────────────────────────────────────

def extract_tx_hashes(transfers: list[dict]) -> list[str]:
    """Extract all unique tx hashes from a list of Arkham transfer objects."""
    hashes = []
    for t in transfers:
        h = t.get("transactionHash")
        if h and h not in hashes:
            hashes.append(h)
    return hashes


def sum_transfers_usd(transfers: list[dict]) -> float:
    """Sum the historicalUSD value across all transfers."""
    return sum(t.get("historicalUSD", 0) for t in transfers)


def get_transfer_timestamps(transfers: list[dict]) -> list[str]:
    """Return human-readable timestamps for each transfer."""
    result = []
    for t in transfers:
        ts = t.get("blockTimestamp")
        if ts:
            result.append(human_time_ago(ts) if isinstance(ts, int) else ts)
    return result


def filter_transfers_by_entity_label(
    transfers: list[dict],
    label_keywords: list[str],
) -> list[dict]:
    """
    Filter transfers where fromEntity or toEntity label contains
    any of the given keywords (case-insensitive).
    """
    result = []
    for t in transfers:
        from_label = (t.get("fromEntity") or {}).get("arkhamLabel", "").lower()
        to_label   = (t.get("toEntity")   or {}).get("arkhamLabel", "").lower()
        for kw in label_keywords:
            if kw.lower() in from_label or kw.lower() in to_label:
                result.append(t)
                break
    return result


def get_hours_since_transfer(transfer: dict) -> float:
    """Calculate how many hours have passed since a transfer occurred."""
    ts = transfer.get("blockTimestamp")
    if not ts:
        return 9999.0
    now_ms = int(time.time()) * 1000
    if isinstance(ts, str):
        try:
            ts = iso_to_unix_ms(ts)
        except (ValueError, TypeError):
            return 9999.0
    if not isinstance(ts, (int, float)):
        return 9999.0
    diff_ms = now_ms - int(ts)
    return diff_ms / (1000 * 3600)


def group_transfers_by_wallet(transfers: list[dict]) -> dict:
    """
    Group transfers by fromAddress.
    Returns {address: [transfer, transfer, ...]}
    """
    groups = {}
    for t in transfers:
        addr = t.get("fromAddress", "unknown")
        groups.setdefault(addr, []).append(t)
    return groups


# ── REPORT UTILITIES ──────────────────────────────────────────────────────────

def generate_report_filename(event_type: str, entity: str) -> str:
    """Generate timestamped filename for saving investigation reports."""
    ts       = datetime.now(tz=timezone.utc).strftime("%Y%m%d_%H%M%S")
    safe_entity = entity.replace("/", "-").replace(" ", "_")
    return f"{ts}_{event_type}_{safe_entity}.json"


def truncate_address(address: str, chars: int = 8) -> str:
    """Shorten a wallet address for display: 0x1a2b3c4d…9f0a1b2c"""
    if not address or len(address) < chars * 2:
        return address
    return f"{address[:chars]}…{address[-6:]}"
