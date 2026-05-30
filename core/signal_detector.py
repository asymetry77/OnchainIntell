"""
signal_detector.py — Onchain signal detection engine.

Detects 4 key signal types from Arkham data:
1. whale_buy    — Single large transfer (>$100K) from/to labeled wallet
2. vc_movement  — VC/fund entity making notable transfers
3. accumulation — Multiple wallets buying same token within time window
4. anomaly      — Unusual volume or trending token activity
"""

import logging
from datetime import datetime, timezone
from collections import defaultdict

from config.settings import (
    WHALE_THRESHOLD_USD, BIG_WHALE_THRESHOLD_USD,
    DISCOVERY_MAX_WALLETS, DEFAULT_LIMIT,
)
from config.entities import CEX_ENTITIES, MARKET_MAKER_ENTITIES
from core.arkham_client import ArkhamClient, ArkhamAPIError

logger = logging.getLogger(__name__)


class SignalDetector:
    def __init__(self):
        self.client = ArkhamClient()

    def detect_all(self, hours: int = 24, min_usd: float = 100000) -> list[dict]:
        """Run all detectors and return combined signals sorted by score."""
        signals = []

        try:
            signals.extend(self.detect_whale_transfers(hours=hours, min_usd=min_usd))
        except Exception as e:
            logger.error(f"Whale detection failed: {e}")

        try:
            signals.extend(self.detect_vc_movements(hours=hours, min_usd=min_usd))
        except Exception as e:
            logger.error(f"VC detection failed: {e}")

        try:
            signals.extend(self.detect_accumulation(hours=hours, min_usd=min_usd))
        except Exception as e:
            logger.error(f"Accumulation detection failed: {e}")

        try:
            signals.extend(self.detect_anomalies())
        except Exception as e:
            logger.error(f"Anomaly detection failed: {e}")

        # Deduplicate by tx_hash
        seen = set()
        unique = []
        for s in signals:
            key = s.get("tx_hash") or f"{s.get('entity','')}-{s.get('token','')}-{s.get('amount_usd',0)}"
            if key not in seen:
                seen.add(key)
                unique.append(s)

        unique.sort(key=lambda s: s.get("score", 0), reverse=True)
        return unique

    def detect_whale_transfers(self, hours: int = 24, min_usd: float = 100000) -> list[dict]:
        """Detect large transfers involving labeled entities."""
        signals = []
        time_last = f"{hours}h" if hours <= 24 else "7d"

        try:
            transfers = self.client.get_transfers(
                time_last=time_last, usd_gte=min_usd, limit=DEFAULT_LIMIT
            )
        except ArkhamAPIError:
            return signals

        for tx in transfers:
            amount = tx.get("historicalUSD", 0) or 0
            if amount < min_usd:
                continue

            from_entity = tx.get("fromEntity", {})
            to_entity = tx.get("toEntity", {})
            from_name = from_entity.get("name", "") if isinstance(from_entity, dict) else ""
            to_name = to_entity.get("name", "") if isinstance(to_entity, dict) else ""
            from_type = from_entity.get("type", "") if isinstance(from_entity, dict) else ""
            to_type = to_entity.get("type", "") if isinstance(to_entity, dict) else ""

            # Determine direction and entity
            entity = to_name or from_name
            label = to_name or from_name
            flow = "in" if to_name else "out"
            action = "received" if flow == "in" else "sent"

            # Check if involves exchange (sell signal)
            goes_to_exchange = any(kw in to_type.lower() for kw in ["exchange"]) or \
                               any(kw in to_name.lower() for kw in CEX_ENTITIES)

            # Calculate score
            score = 0
            if entity:
                score += 30  # named entity
            if amount >= BIG_WHALE_THRESHOLD_USD:
                score += 25  # >$1M
            elif amount >= WHALE_THRESHOLD_USD:
                score += 15  # >$100K
            if goes_to_exchange:
                score += 20  # to exchange (potential sell)
            score = min(score, 100)

            from_addr = tx.get("fromAddress", "")
            if isinstance(from_addr, dict):
                from_addr = from_addr.get("address", "")
            to_addr = tx.get("toAddress", "")
            if isinstance(to_addr, dict):
                to_addr = to_addr.get("address", "")

            signals.append({
                "signal_type": "whale_buy",
                "entity": entity,
                "label": label,
                "action": action,
                "flow": flow,
                "amount_usd": amount,
                "token": tx.get("tokenSymbol", ""),
                "chain": tx.get("chain", ""),
                "tx_hash": tx.get("transactionHash", ""),
                "from": from_addr,
                "to": to_addr,
                "timestamp": tx.get("blockTimestamp", ""),
                "goes_to_exchange": goes_to_exchange,
                "score": score,
            })

        return signals

    def detect_vc_movements(self, hours: int = 24, min_usd: float = 100000) -> list[dict]:
        """Detect movements from tracked VC/fund entities."""
        from config.entities import NOTABLE_ENTITIES

        signals = []
        time_last = f"{hours}h" if hours <= 24 else "7d"

        for entity_slug, entity_name in list(NOTABLE_ENTITIES.items())[:10]:
            try:
                transfers = self.client.get_transfers(
                    base=entity_slug, time_last=time_last,
                    usd_gte=min_usd, limit=5
                )
            except ArkhamAPIError:
                continue

            for tx in transfers:
                amount = tx.get("historicalUSD", 0) or 0
                if amount < min_usd:
                    continue

                from_entity = tx.get("fromEntity", {})
                to_entity = tx.get("toEntity", {})
                from_name = from_entity.get("name", "") if isinstance(from_entity, dict) else ""
                to_name = to_entity.get("name", "") if isinstance(to_entity, dict) else ""

                flow = "out" if from_name == entity_name else "in"
                action = "bought" if flow == "in" else "sold"

                goes_to_exchange = any(kw in (to_name or "").lower() for kw in CEX_ENTITIES)

                score = 50  # base for known VC
                if amount >= BIG_WHALE_THRESHOLD_USD:
                    score += 25
                elif amount >= WHALE_THRESHOLD_USD:
                    score += 15
                if goes_to_exchange:
                    score += 20
                score = min(score, 100)

                from_addr = tx.get("fromAddress", "")
                if isinstance(from_addr, dict):
                    from_addr = from_addr.get("address", "")
                to_addr = tx.get("toAddress", "")
                if isinstance(to_addr, dict):
                    to_addr = to_addr.get("address", "")

                signals.append({
                    "signal_type": "vc_movement",
                    "entity": entity_name,
                    "label": entity_name,
                    "action": action,
                    "flow": flow,
                    "amount_usd": amount,
                    "token": tx.get("tokenSymbol", ""),
                    "chain": tx.get("chain", ""),
                    "tx_hash": tx.get("transactionHash", ""),
                    "from": from_addr,
                    "to": to_addr,
                    "timestamp": tx.get("blockTimestamp", ""),
                    "goes_to_exchange": goes_to_exchange,
                    "is_new_position": False,
                    "score": score,
                })

        return signals

    def detect_accumulation(self, hours: int = 24, min_usd: float = 50000) -> list[dict]:
        """Detect multiple wallets accumulating the same token."""
        signals = []
        time_last = f"{hours}h" if hours <= 24 else "7d"

        # Get trending tokens
        try:
            trending = self.client.get_trending_tokens()
        except ArkhamAPIError:
            return signals

        for tok in trending[:5]:
            ident = tok.get("identifier", {})
            slug = ident.get("pricingID", "") if isinstance(ident, dict) else ""
            sym = tok.get("symbol", "")
            if not slug:
                continue

            try:
                flows = self.client.get_token_top_flow(slug, time_last=time_last)
            except ArkhamAPIError:
                continue

            # Count wallets with net inflow (buying)
            buyers = []
            total_buy_usd = 0
            for f in flows:
                in_usd = f.get("inUSD", 0) or 0
                out_usd = f.get("outUSD", 0) or 0
                net = in_usd - out_usd
                if net > min_usd:
                    addr = f.get("address", "")
                    if isinstance(addr, dict):
                        addr = addr.get("address", "")
                    buyers.append({"address": addr, "net_usd": net})
                    total_buy_usd += net

            if len(buyers) >= 3:
                signals.append({
                    "signal_type": "accumulation",
                    "entity": "",
                    "label": "",
                    "action": "accumulating",
                    "amount_usd": total_buy_usd,
                    "token": sym.upper(),
                    "token_slug": slug,
                    "wallet_count": len(buyers),
                    "total_usd": total_buy_usd,
                    "avg_size": total_buy_usd / len(buyers) if buyers else 0,
                    "time_window": f"{hours}h",
                    "score": min(40 + len(buyers) * 5, 80),
                })

        return signals

    def detect_anomalies(self) -> list[dict]:
        """Detect tokens with unusual onchain activity."""
        signals = []

        try:
            trending = self.client.get_trending_tokens()
        except ArkhamAPIError:
            return signals

        for tok in trending[:5]:
            sym = tok.get("symbol", "")
            name = tok.get("name", "")
            if not sym:
                continue

            signals.append({
                "signal_type": "anomaly",
                "entity": "",
                "label": "",
                "action": "unusual_activity",
                "token": sym.upper(),
                "token_name": name,
                "description": f"Unusual onchain activity detected for {name} ({sym.upper()})",
                "amount_usd": 0,
                "score": 30,
            })

        return signals
