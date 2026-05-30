"""
caption_generator.py — Generate onchain intelligence captions using MiMo AI.

Produces professional, data-driven content for different signal types:
- Whale alerts (large transfers)
- VC movements (fund activity)
- Accumulation signals (multiple wallets buying)
- Token anomalies (trending + unusual volume)
- Portfolio snapshots (wallet tracking updates)
"""

import logging
from datetime import datetime, timezone
from typing import Optional

from core.mimo_client import MiMoClient
from utils.helpers import format_usd, truncate_address, get_explorer_link

logger = logging.getLogger(__name__)


SYSTEM_PROMPT = """You are OnchainIntell — a professional onchain intelligence analyst.

Your job is to write concise, engaging, data-driven captions for onchain signal alerts.

RULES:
- Lead with the most important data point (amount, entity, token)
- Use clear, professional English
- Include tx hashes for verifiability when available
- Distinguish DATA from INTERPRETATION (use "appears to", "suggests")
- Never make price predictions
- Never call something a "scam" without evidence
- Keep under 280 characters for X/Twitter posts
- Use emoji sparingly (1-2 max)
- Always include the signal type hashtag

OUTPUT FORMAT:
Return a JSON object with:
{
  "caption": "The main caption text",
  "hashtags": ["#tag1", "#tag2"],
  "thread": ["Optional thread continuation tweets..."],
  "confidence": "high|medium|low",
  "signal_type": "whale_buy|vc_movement|accumulation|anomaly|snapshot"
}"""

WHALE_ALERT_PROMPT = """Generate a whale alert caption for this onchain data:

Entity: {entity}
Label: {label}
Action: {action}
Amount USD: {amount_usd}
Token: {token}
Chain: {chain}
TX Hash: {tx_hash}
Explorer: {explorer_url}
Time: {timestamp}

Focus on: WHO is moving WHAT amount. Include tx hash for verification."""

VC_MOVEMENT_PROMPT = """Generate a VC/fund movement caption:

Entity: {entity}
Action: {action}
Amount USD: {amount_usd}
Token: {token}
Is New Position: {is_new_position}
Previous Holdings: {previous_info}
TX Hash: {tx_hash}
Explorer: {explorer_url}

Focus on: This is a TRACKED FUND making a move. Highlight if it's a new position or adding to existing."""

ACCUMULATION_PROMPT = """Generate an accumulation signal caption:

Token: {token}
Number of Wallets: {wallet_count}
Total USD: {total_usd}
Time Window: {time_window}
Top Wallets: {wallet_list}
Average Buy Size: {avg_size}

Focus on: MULTIPLE wallets are quietly accumulating this token. This suggests coordinated buying."""

ANOMALY_PROMPT = """Generate a token anomaly caption:

Token: {token}
Signal: {signal_description}
Inflow USD: {inflow_usd}
Outflow USD: {outflow_usd}
Volume Change: {volume_change}
Top Movers: {top_movers}

Focus on: UNUSUAL onchain activity detected for this token."""

SNAPSHOT_PROMPT = """Generate a portfolio tracking update caption:

Total Wallets Tracked: {wallet_count}
Total Balance USD: {total_usd}
Biggest Gainer: {top_gainer}
Biggest Loser: {top_loser}
Notable Moves: {notable_moves}
Period: {period}

Focus on: What the tracked insider wallets did in this period."""


class CaptionGenerator:
    def __init__(self):
        self.client = MiMoClient()

    def whale_alert(self, entity: str, label: str, action: str,
                    amount_usd: float, token: str, chain: str = "",
                    tx_hash: str = "", timestamp: str = "") -> dict:
        explorer_url = get_explorer_link(tx_hash, chain) if tx_hash else ""
        prompt = WHALE_ALERT_PROMPT.format(
            entity=entity or "Unknown",
            label=label or "Unlabeled Wallet",
            action=action,
            amount_usd=format_usd(amount_usd),
            token=token,
            chain=chain,
            tx_hash=tx_hash or "N/A",
            explorer_url=explorer_url,
            timestamp=timestamp or datetime.now(timezone.utc).isoformat(),
        )
        return self.client.generate_json(SYSTEM_PROMPT, prompt)

    def vc_movement(self, entity: str, action: str, amount_usd: float,
                    token: str, is_new_position: bool = False,
                    previous_info: str = "", tx_hash: str = "",
                    chain: str = "") -> dict:
        explorer_url = get_explorer_link(tx_hash, chain) if tx_hash else ""
        prompt = VC_MOVEMENT_PROMPT.format(
            entity=entity,
            action=action,
            amount_usd=format_usd(amount_usd),
            token=token,
            is_new_position="YES" if is_new_position else "No (adding to existing)",
            previous_info=previous_info or "No prior position in 30d",
            tx_hash=tx_hash or "N/A",
            explorer_url=explorer_url,
        )
        return self.client.generate_json(SYSTEM_PROMPT, prompt)

    def accumulation(self, token: str, wallet_count: int, total_usd: float,
                     time_window: str = "24h", wallet_list: str = "",
                     avg_size: float = 0) -> dict:
        prompt = ACCUMULATION_PROMPT.format(
            token=token,
            wallet_count=wallet_count,
            total_usd=format_usd(total_usd),
            time_window=time_window,
            wallet_list=wallet_list or "Multiple unlabeled wallets",
            avg_size=format_usd(avg_size),
        )
        return self.client.generate_json(SYSTEM_PROMPT, prompt)

    def anomaly(self, token: str, signal_description: str,
                inflow_usd: float = 0, outflow_usd: float = 0,
                volume_change: str = "", top_movers: str = "") -> dict:
        prompt = ANOMALY_PROMPT.format(
            token=token,
            signal_description=signal_description,
            inflow_usd=format_usd(inflow_usd),
            outflow_usd=format_usd(outflow_usd),
            volume_change=volume_change or "N/A",
            top_movers=top_movers or "N/A",
        )
        return self.client.generate_json(SYSTEM_PROMPT, prompt)

    def snapshot_update(self, wallet_count: int, total_usd: float,
                        top_gainer: str = "", top_loser: str = "",
                        notable_moves: str = "", period: str = "24h") -> dict:
        prompt = SNAPSHOT_PROMPT.format(
            wallet_count=wallet_count,
            total_usd=format_usd(total_usd),
            top_gainer=top_gainer or "None",
            top_loser=top_loser or "None",
            notable_moves=notable_moves or "No significant moves",
            period=period,
        )
        return self.client.generate_json(SYSTEM_PROMPT, prompt)

    def generate_from_signal(self, signal: dict) -> dict:
        """Auto-generate caption from a signal dict (from signal_detector)."""
        sig_type = signal.get("signal_type", "whale_alert")

        if sig_type == "whale_buy":
            return self.whale_alert(
                entity=signal.get("entity", ""),
                label=signal.get("label", ""),
                action="bought" if signal.get("flow") == "in" else "transferred",
                amount_usd=signal.get("amount_usd", 0),
                token=signal.get("token", ""),
                chain=signal.get("chain", ""),
                tx_hash=signal.get("tx_hash", ""),
                timestamp=signal.get("timestamp", ""),
            )
        elif sig_type == "vc_movement":
            return self.vc_movement(
                entity=signal.get("entity", ""),
                action=signal.get("action", "moved"),
                amount_usd=signal.get("amount_usd", 0),
                token=signal.get("token", ""),
                is_new_position=signal.get("is_new_position", False),
                tx_hash=signal.get("tx_hash", ""),
                chain=signal.get("chain", ""),
            )
        elif sig_type == "accumulation":
            return self.accumulation(
                token=signal.get("token", ""),
                wallet_count=signal.get("wallet_count", 0),
                total_usd=signal.get("total_usd", 0),
                time_window=signal.get("time_window", "24h"),
            )
        elif sig_type == "anomaly":
            return self.anomaly(
                token=signal.get("token", ""),
                signal_description=signal.get("description", ""),
                inflow_usd=signal.get("inflow_usd", 0),
                outflow_usd=signal.get("outflow_usd", 0),
            )
        else:
            return self.whale_alert(
                entity=signal.get("entity", "Unknown"),
                label=signal.get("label", ""),
                action="moved",
                amount_usd=signal.get("amount_usd", 0),
                token=signal.get("token", ""),
                tx_hash=signal.get("tx_hash", ""),
            )
