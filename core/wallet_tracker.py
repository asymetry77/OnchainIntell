"""
wallet_tracker.py — Insider Wallet Tracker.

Discovers high-balance wallets trading altcoins/meme coins,
maintains a watchlist, takes daily snapshots, and generates alerts.
"""

import json
import logging
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from config.settings import (
    WATCHLIST_PATH,
    SNAPSHOT_DIR,
    WALLET_MIN_BALANCE_USD,
    DISCOVERY_MAX_WALLETS,
    ALERT_MIN_USD,
    ALERT_MAX_WALLETS,
    DEFAULT_LIMIT,
)
from core.arkham_client import ArkhamClient, ArkhamAPIError
from config.entities import CEX_ENTITIES, MARKET_MAKER_ENTITIES

logger = logging.getLogger(__name__)


class WalletTracker:
    def __init__(self):
        self.client = ArkhamClient()

    # ── WATCHLIST PERSISTENCE ─────────────────────────────────────────────

    def _load_watchlist(self) -> dict:
        if WATCHLIST_PATH.exists():
            try:
                return json.loads(WATCHLIST_PATH.read_text())
            except (json.JSONDecodeError, OSError):
                pass
        return {"version": 1, "wallets": [], "last_discovery": None, "last_snapshot": None}

    def _save_watchlist(self, data: dict):
        WATCHLIST_PATH.parent.mkdir(parents=True, exist_ok=True)
        WATCHLIST_PATH.write_text(json.dumps(data, indent=2, default=str))

    # ── CRUD ──────────────────────────────────────────────────────────────

    def add_wallet(self, address: str, label: str = "", token_source: str = "", token_name: str = "") -> dict:
        data = self._load_watchlist()
        if any(w["address"] == address for w in data["wallets"]):
            logger.info(f"Wallet already tracked: {address}")
            return next(w for w in data["wallets"] if w["address"] == address)

        wallet = {
            "address": address,
            "label": label,
            "added_at": datetime.now(timezone.utc).isoformat(),
            "token_source": token_source,
            "token_name": token_name,
        }
        data["wallets"].append(wallet)
        self._save_watchlist(data)
        logger.info(f"Wallet added: {address}")
        return wallet

    def remove_wallet(self, address: str) -> bool:
        data = self._load_watchlist()
        before = len(data["wallets"])
        data["wallets"] = [w for w in data["wallets"] if w["address"] != address]
        if len(data["wallets"]) < before:
            self._save_watchlist(data)
            logger.info(f"Wallet removed: {address}")
            return True
        return False

    def get_watchlist(self) -> list[dict]:
        return self._load_watchlist()["wallets"]

    def get_wallet(self, address: str) -> Optional[dict]:
        data = self._load_watchlist()
        return next((w for w in data["wallets"] if w["address"] == address), None)

    # ── DISCOVERY ─────────────────────────────────────────────────────────

    # Skip L1s, stables, wrapped tokens — we want altcoins/meme coins
    SKIP_TOKENS = {
        # L1 native tokens
        "btc", "eth", "bnb", "sol", "xrp", "ada", "doge", "avax", "dot",
        "matic", "link", "uni", "atom", "near", "apt", "sui", "arb", "op",
        "bitcoin", "ethereum", "binance-coin", "solana", "cardano", "dogecoin",
        "avalanche", "polkadot", "polygon", "chainlink", "uniswap", "cosmos",
        # Stablecoins
        "usdt", "usdc", "dai", "tether", "usd-coin", "busd", "frax", "tusd",
        "crvusd", "usdd", "usdp", "gusd", "lusd", "susd",
        # Wrapped tokens
        "wbtc", "weth", "cbbtc", "steth", "reth", "cbeth", "wsteth",
        "l2-standard-bridged-weth-base", "l2-standard-bridged-weth-arbitrum",
    }

    def discover_wallets(self) -> list[dict]:
        """
        Auto-discover insider wallets from altcoin/meme coin flows:
        1. Get top tokens by inflow (VC/whale money entering)
        2. Get trending tokens (unusual activity)
        3. For each non-L1 token, get top flow wallets
        4. Filter out exchanges/market makers
        5. Keep wallets with significant flow
        """
        discovered = []
        existing = {w["address"] for w in self.get_watchlist()}
        seen_tokens = set()

        # Strategy 1: Top tokens by INFLOW — where whale money is going
        try:
            top_inflow = self.client.get_top_tokens(
                timeframe="24h", order_by="inflow", size=10
            )
            logger.info(f"Discovery: {len(top_inflow)} top inflow tokens")
        except ArkhamAPIError:
            top_inflow = []

        # Strategy 2: Trending tokens — unusual activity
        try:
            trending = self.client.get_trending_tokens()
            logger.info(f"Discovery: {len(trending)} trending tokens")
        except ArkhamAPIError:
            trending = []

        # Build token list: inflow tokens first (higher signal), then trending
        tokens_to_scan = []
        for tok in top_inflow:
            tid = tok.get("id") or tok.get("identifier", {}).get("pricingID")
            sym = (tok.get("symbol") or "").lower()
            name = tok.get("name", "")
            if tid and sym not in self.SKIP_TOKENS:
                tokens_to_scan.append({"id": tid, "symbol": sym, "name": name})
                seen_tokens.add(sym)

        for tok in trending:
            tid = tok.get("identifier", {}).get("pricingID") or tok.get("id")
            sym = (tok.get("symbol") or "").lower()
            name = tok.get("name", "")
            if tid and sym not in self.SKIP_TOKENS and sym not in seen_tokens:
                tokens_to_scan.append({"id": tid, "symbol": sym, "name": name})
                seen_tokens.add(sym)

        logger.info(f"Discovery: scanning {len(tokens_to_scan)} altcoin/meme tokens")

        for token in tokens_to_scan:
            if len(discovered) >= DISCOVERY_MAX_WALLETS:
                break

            try:
                flows = self.client.get_token_top_flow(token["id"], time_last="24h")
            except ArkhamAPIError:
                continue

            for flow in flows[:5]:  # Top 5 wallets per token
                if len(discovered) >= DISCOVERY_MAX_WALLETS:
                    break

                addr = flow.get("address", "")
                if isinstance(addr, dict):
                    addr = addr.get("address", "")
                if not addr or addr in existing:
                    continue

                in_usd = flow.get("inUSD", 0) or 0
                out_usd = flow.get("outUSD", 0) or 0
                # Skip tiny flows
                if max(in_usd, out_usd) < 50000:
                    continue

                try:
                    intel = self.client.get_address_intelligence(addr)
                    label = intel.get("arkhamLabel", "")
                    if isinstance(label, dict):
                        label = label.get("name", str(label))
                    elif not isinstance(label, str):
                        label = str(label) if label else ""
                    entity_type = intel.get("type", "")
                    if isinstance(entity_type, dict):
                        entity_type = entity_type.get("name", "")
                    elif not isinstance(entity_type, str):
                        entity_type = str(entity_type) if entity_type else ""
                    entity_type = entity_type.lower()

                    if any(kw in entity_type for kw in ["exchange", "market_maker"]):
                        continue
                    if any(kw in label.lower() for kw in CEX_ENTITIES + MARKET_MAKER_ENTITIES):
                        continue

                    wallet = self.add_wallet(
                        addr, label=label,
                        token_source=token["symbol"]
                    )
                    wallet["in_usd"] = in_usd
                    wallet["out_usd"] = out_usd
                    wallet["token"] = token["symbol"]
                    wallet["token_name"] = token["name"]
                    discovered.append(wallet)
                    existing.add(addr)
                except ArkhamAPIError:
                    continue

        data = self._load_watchlist()
        data["last_discovery"] = datetime.now(timezone.utc).isoformat()
        self._save_watchlist(data)
        logger.info(f"Discovery complete: {len(discovered)} new wallets")
        return discovered

    # ── WALLET DETAIL ─────────────────────────────────────────────────────

    def get_wallet_detail(self, address: str) -> Optional[dict]:
        wallet = self.get_wallet(address)
        if not wallet:
            return None

        detail = {**wallet, "balance": {}, "transfers": [], "swaps": []}

        # Try to get balance (needs entity slug)
        try:
            intel = self.client.get_address_intelligence(address)
            lbl = intel.get("arkhamLabel", wallet.get("label", ""))
            if isinstance(lbl, dict):
                lbl = lbl.get("name", str(lbl))
            detail["label"] = lbl
            entity = intel.get("arkhamEntity", {})
            slug = entity.get("slug") if isinstance(entity, dict) else None
            if slug:
                balance = self.client.get_entity_balance(slug)
                detail["balance"] = {
                    "total_usd": balance.get("totalBalance", 0),
                    "chains": balance.get("balances", []),
                }
        except ArkhamAPIError:
            pass

        try:
            raw_transfers = self.client.get_transfers(
                base=address, time_last="7d", limit=DEFAULT_LIMIT
            )
            detail["transfers"] = self._normalize_transfers(raw_transfers)
        except ArkhamAPIError:
            pass

        try:
            detail["swaps"] = self.client.get_entity_swaps(address, limit=DEFAULT_LIMIT)
        except ArkhamAPIError:
            pass

        return detail

    @staticmethod
    def _normalize_transfers(transfers: list[dict]) -> list[dict]:
        result = []
        for tx in transfers:
            from_addr = tx.get("fromAddress", "")
            if isinstance(from_addr, dict):
                from_addr = from_addr.get("address", "")
            to_addr = tx.get("toAddress", "")
            if isinstance(to_addr, dict):
                to_addr = to_addr.get("address", "")
            from_entity = tx.get("fromEntity", {})
            to_entity = tx.get("toEntity", {})
            from_name = from_entity.get("name", "") if isinstance(from_entity, dict) else ""
            to_name = to_entity.get("name", "") if isinstance(to_entity, dict) else ""
            result.append({
                **tx,
                "fromAddress": from_addr,
                "toAddress": to_addr,
                "fromName": from_name,
                "toName": to_name,
            })
        return result

    @staticmethod
    def _normalize_holder(h: dict, chain: str) -> dict:
        addr = h.get("address", "")
        if isinstance(addr, dict):
            label = addr.get("arkhamLabel", "")
            if isinstance(label, dict):
                label = label.get("name", "")
            entity = addr.get("arkhamEntity", {})
            entity_name = entity.get("name", "") if isinstance(entity, dict) else ""
            return {
                "address": addr.get("address", ""),
                "chain": addr.get("chain", chain),
                "arkhamLabel": label or entity_name or "",
                "arkhamEntity": entity_name,
                "balanceUSD": h.get("balanceUSD", 0) or h.get("holdingUSD", 0) or 0,
            }
        label = h.get("arkhamLabel", "")
        if isinstance(label, dict):
            label = label.get("name", "")
        return {
            "address": addr,
            "chain": chain,
            "arkhamLabel": label or "",
            "arkhamEntity": "",
            "balanceUSD": h.get("balanceUSD", 0) or h.get("holdingUSD", 0) or 0,
        }

    # ── SNAPSHOTS ─────────────────────────────────────────────────────────

    def take_snapshot(self) -> dict:
        wallets = self.get_watchlist()
        if not wallets:
            return {"error": "No wallets in watchlist"}

        snapshot = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "wallets": [],
        }

        for wallet in wallets[:DISCOVERY_MAX_WALLETS]:
            entry = {"address": wallet["address"], "label": wallet.get("label", "")}
            try:
                intel = self.client.get_address_intelligence(wallet["address"])
                entity = intel.get("arkhamEntity", {})
                slug = entity.get("slug") if isinstance(entity, dict) else None
                if slug:
                    balance = self.client.get_entity_balance(slug)
                    entry["total_usd"] = balance.get("totalBalance", 0)
                    entry["balances"] = balance.get("balances", [])
                else:
                    entry["total_usd"] = 0
                    entry["balances"] = []
            except ArkhamAPIError:
                entry["total_usd"] = 0
                entry["balances"] = []
            snapshot["wallets"].append(entry)

        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        path = SNAPSHOT_DIR / f"{today}.json"
        path.write_text(json.dumps(snapshot, indent=2, default=str))

        data = self._load_watchlist()
        data["last_snapshot"] = snapshot["timestamp"]
        self._save_watchlist(data)

        logger.info(f"Snapshot saved: {len(snapshot['wallets'])} wallets -> {path}")
        return {"saved": str(path), "wallets": len(snapshot["wallets"])}

    # ── ALERTS ────────────────────────────────────────────────────────────

    def get_alerts(self, min_usd: float = None) -> list[dict]:
        if min_usd is None:
            min_usd = ALERT_MIN_USD

        wallets = self.get_watchlist()
        if not wallets:
            return []

        alerts = []
        for wallet in wallets[:ALERT_MAX_WALLETS]:
            try:
                transfers = self.client.get_transfers(
                    base=wallet["address"], time_last="24h", usd_gte=min_usd, limit=10
                )
                for tx in transfers:
                    from_addr = tx.get("fromAddress", "")
                    if isinstance(from_addr, dict):
                        from_addr = from_addr.get("address", "")
                    to_addr = tx.get("toAddress", "")
                    if isinstance(to_addr, dict):
                        to_addr = to_addr.get("address", "")
                    alerts.append({
                        "address": wallet["address"],
                        "label": wallet.get("label", ""),
                        "tx_hash": tx.get("transactionHash", ""),
                        "token": tx.get("tokenSymbol", ""),
                        "amount_usd": tx.get("historicalUSD", 0),
                        "from": from_addr,
                        "to": to_addr,
                        "timestamp": tx.get("blockTimestamp", ""),
                        "chain": tx.get("chain", ""),
                    })
            except ArkhamAPIError:
                continue

        alerts.sort(key=lambda a: a.get("amount_usd", 0), reverse=True)
        return alerts

    # ── TOKEN SCANNER ─────────────────────────────────────────────────────

    def scan_token(self, token_slug: str) -> dict:
        watchlist_addrs = {w["address"] for w in self.get_watchlist()}

        try:
            holders_data = self.client.get_token_holders(token_slug)
        except ArkhamAPIError:
            holders_data = {}

        try:
            top_flow = self.client.get_token_top_flow(token_slug, time_last="24h")
        except ArkhamAPIError:
            top_flow = []

        # addressTopHolders is a dict keyed by chain, each value is a list
        raw_holders = holders_data.get("addressTopHolders", {})
        holders = []
        if isinstance(raw_holders, dict):
            for chain, chain_holders in raw_holders.items():
                if isinstance(chain_holders, list):
                    for h in chain_holders:
                        holders.append(self._normalize_holder(h, chain))
        elif isinstance(raw_holders, list):
            for h in raw_holders:
                holders.append(self._normalize_holder(h, ""))

        # Normalize top_flow addresses
        for f in top_flow:
            addr = f.get("address", "")
            if isinstance(addr, dict):
                f["address"] = addr.get("address", "")
                f["chain"] = addr.get("chain", "")
                if not f.get("arkhamLabel"):
                    f["arkhamLabel"] = addr.get("arkhamLabel", {})
                if isinstance(f.get("arkhamLabel"), dict):
                    f["arkhamLabel"] = f["arkhamLabel"].get("name", "")

        watchlist_holders = [h for h in holders if h.get("address", "") in watchlist_addrs]
        watchlist_flow = [f for f in top_flow if f.get("address", "") in watchlist_addrs]

        return {
            "token": token_slug,
            "holders": holders,
            "top_flow": top_flow,
            "watchlist_holders": watchlist_holders,
            "watchlist_flow": watchlist_flow,
        }
