"""
arkham_client.py — Complete Arkham Intelligence API client.

Wraps every endpoint used in the Onchain Never Lies pipeline:
  - Entity & Address Intelligence
  - Balance & Portfolio (current + historical snapshots)
  - Transfer Tracking (the core data source)
  - Transfer Histogram
  - Token Analysis (top, holders, top_flow, trending, search)
  - Historical Portfolio & DEX swaps
  - Counterparties

All methods return parsed Python dicts/lists.
HTTP errors are retried up to MAX_RETRIES times.
"""

import time
import logging
from typing import Optional, Union

import requests
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)

from config.settings import (
    ARKHAM_BASE_URL,
    ARKHAM_HEADERS,
    REQUEST_TIMEOUT_SECONDS,
    REQUEST_MAX_RETRIES,
)

logger = logging.getLogger(__name__)


class ArkhamAPIError(Exception):
    """Raised when Arkham API returns a non-2xx status."""
    def __init__(self, status_code: int, message: str, endpoint: str):
        self.status_code = status_code
        self.endpoint    = endpoint
        super().__init__(f"[{status_code}] {endpoint}: {message}")


class ArkhamClient:
    """
    Full-featured Arkham Intelligence API client.

    Usage:
        client = ArkhamClient()
        entity = client.get_entity("a16z")
        transfers = client.get_transfers(base="a16z", flow="out", time_last="7d")
    """

    def __init__(self):
        self.base_url = ARKHAM_BASE_URL.rstrip("/")
        self.session  = requests.Session()
        self.session.headers.update(ARKHAM_HEADERS)

    # ── INTERNAL ─────────────────────────────────────────────────────────────

    @retry(
        stop=stop_after_attempt(REQUEST_MAX_RETRIES),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type(requests.RequestException),
        reraise=True,
    )
    def _get(self, endpoint: str, params: Optional[dict] = None) -> dict:
        """
        Execute a GET request against the Arkham API.
        Retries on network errors with exponential backoff.
        """
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        logger.debug(f"GET {url} params={params}")

        try:
            response = self.session.get(
                url,
                params=params,
                timeout=REQUEST_TIMEOUT_SECONDS,
            )
        except requests.ConnectionError as exc:
            logger.warning(f"Connection error to Arkham: {exc}. Retrying…")
            raise

        if not response.ok:
            raise ArkhamAPIError(
                status_code=response.status_code,
                message=response.text[:300],
                endpoint=endpoint,
            )

        return response.json()

    # ─────────────────────────────────────────────────────────────────────────
    # ENTITY & ADDRESS INTELLIGENCE
    # ─────────────────────────────────────────────────────────────────────────

    def get_entity(self, slug: str) -> dict:
        """
        GET /intelligence/entity/{slug}
        Returns entity profile: name, type, all connected wallet addresses.
        slug examples: a16z, paradigm-xyz, binance, lazarus-group
        """
        data = self._get(f"/intelligence/entity/{slug}")
        logger.info(f"Entity fetched: {slug}")
        return data

    def get_address_intelligence(self, wallet_address: str) -> dict:
        """
        GET /intelligence/address/{wallet_address}
        Returns: who owns this wallet? Arkham entity label + type.
        wallet_address: 0x... (EVM) or base58 (Solana)
        """
        data = self._get(f"/intelligence/address/{wallet_address}")
        logger.info(f"Address intelligence fetched: {wallet_address[:20]}…")
        return data

    def is_insider_wallet(self, wallet_address: str) -> tuple[bool, str]:
        """
        Check if a wallet is labeled as an insider (team, founder, treasury…).
        Returns (is_insider: bool, label: str).
        """
        from config.entities import INSIDER_LABEL_KEYWORDS

        try:
            data  = self.get_address_intelligence(wallet_address)
            label = (data.get("arkhamLabel") or "").lower()
            entity_type = (data.get("type") or "").lower()

            for keyword in INSIDER_LABEL_KEYWORDS:
                if keyword in label or keyword in entity_type:
                    return True, data.get("arkhamLabel", "")

            return False, label
        except ArkhamAPIError:
            return False, ""

    # ─────────────────────────────────────────────────────────────────────────
    # BALANCE & PORTFOLIO
    # ─────────────────────────────────────────────────────────────────────────

    def get_entity_balance(
        self,
        slug: str,
        chain: Optional[str] = None,
    ) -> dict:
        """
        GET /balances/entity/{slug}[?chain={chain}]
        Returns current portfolio across all chains (or filtered to one chain).
        Fields: totalBalance, totalBalance24hAgo, balances per chain.
        """
        params = {}
        if chain:
            params["chain"] = chain
        data = self._get(f"/balances/entity/{slug}", params=params)
        logger.info(f"Balance fetched for {slug}" + (f" on {chain}" if chain else ""))
        return data

    def get_entity_portfolio_snapshot(
        self,
        slug: str,
        days_ago: int = 0,
        unix_ms: Optional[int] = None,
    ) -> dict:
        """
        GET /portfolio/entity/{slug}?time={unix_ms}
        Returns portfolio snapshot at a past point in time.

        Pass either:
          days_ago=7   → calculates unix_ms automatically
          unix_ms=...  → exact millisecond timestamp
        """
        if unix_ms is None:
            unix_ms = int(time.time() - days_ago * 24 * 3600) * 1000

        data = self._get(f"/portfolio/entity/{slug}", params={"time": unix_ms})
        logger.info(f"Portfolio snapshot: {slug} @ {days_ago}d ago")
        return data

    def compare_portfolio(
        self,
        slug: str,
        days_ago: int = 30,
    ) -> dict:
        """
        Compare current portfolio vs N days ago.
        Returns: {current, past, delta_usd, delta_pct, reduced_tokens}
        """
        current_data = self.get_entity_balance(slug)
        past_data    = self.get_entity_portfolio_snapshot(slug, days_ago=days_ago)

        current_usd = current_data.get("totalBalance", 0) if isinstance(current_data, dict) else 0
        past_usd    = past_data.get("totalBalance", 0) if isinstance(past_data, dict) else 0
        if isinstance(current_usd, str):
            try:
                current_usd = float(current_usd)
            except (ValueError, TypeError):
                current_usd = 0
        if isinstance(past_usd, str):
            try:
                past_usd = float(past_usd)
            except (ValueError, TypeError):
                past_usd = 0
        delta_usd   = current_usd - past_usd
        delta_pct   = (delta_usd / past_usd * 100) if past_usd else 0

        return {
            "slug":         slug,
            "days_compared": days_ago,
            "current_usd":  current_usd,
            "past_usd":     past_usd,
            "delta_usd":    delta_usd,
            "delta_pct":    round(delta_pct, 2),
            "is_dumping":   delta_usd < -WHALE_THRESHOLD_FROM_SETTINGS(),
            "current_raw":  current_data,
            "past_raw":     past_data,
        }

    # ─────────────────────────────────────────────────────────────────────────
    # TRANSFER TRACKING  (CORE — most important endpoint)
    # ─────────────────────────────────────────────────────────────────────────

    def get_transfers(
        self,
        base:          Optional[str] = None,
        flow:          Optional[str] = None,       # "in" | "out"
        time_last:     Optional[str] = None,       # "24h" | "7d" | "30d"
        usd_gte:       Optional[float] = None,
        to_entity:     Optional[str] = None,
        from_entity:   Optional[str] = None,
        counterparty:  Optional[str] = None,
        chain:         Optional[str] = None,
        token:         Optional[str] = None,
        limit:         int = 20,
    ) -> list[dict]:
        """
        GET /transfers with any combination of query params.

        Core params:
          base        → entity slug or wallet address (the "subject")
          flow        → "in" (buys/receives) | "out" (sells/sends)
          time_last   → "24h", "7d", "30d"
          usd_gte     → minimum USD value filter (whale filter)
          to_entity   → only transfers going TO this exchange (sell signal)
          from_entity → only transfers coming FROM this exchange (withdraw)
          counterparty→ transfers between base and this specific entity
          chain       → filter to one blockchain
          token       → filter to one token slug
          limit       → max results

        Returns list of transfer dicts. Each has:
          id, transactionHash, blockTimestamp, historicalUSD,
          tokenSymbol, fromAddress, toAddress, fromEntity, toEntity
        """
        params = {"limit": limit}
        if base:         params["base"]          = base
        if flow:         params["flow"]          = flow
        if time_last:    params["timeLast"]       = time_last
        if usd_gte:      params["usdGte"]         = int(usd_gte)
        if to_entity:    params["toEntity"]       = to_entity
        if from_entity:  params["fromEntity"]     = from_entity
        if counterparty: params["counterparty"]   = counterparty
        if chain:        params["chain"]          = chain
        if token:        params["token"]          = token

        data = self._get("/transfers", params=params)
        if not isinstance(data, dict):
            logger.warning(f"Unexpected transfers response type: {type(data)}")
            return []
        transfers = data.get("transfers", [])
        if not isinstance(transfers, list):
            logger.warning(f"Unexpected transfers type: {type(transfers)}")
            return []
        logger.info(f"Transfers fetched: {len(transfers)} results (base={base}, flow={flow})")
        return transfers

    def get_exchange_inflows(
        self,
        exchange_slug: str,
        time_last: str = "24h",
        usd_gte: float = 500_000,
        limit: int = 20,
    ) -> list[dict]:
        """
        Convenience: get large transfers INTO a specific exchange.
        Signal: holders are about to sell (bearish warning).
        """
        return self.get_transfers(
            to_entity=exchange_slug,
            time_last=time_last,
            usd_gte=usd_gte,
            limit=limit,
        )

    def get_exchange_outflows(
        self,
        exchange_slug: str,
        time_last: str = "24h",
        usd_gte: float = 100_000,
        limit: int = 20,
    ) -> list[dict]:
        """
        Convenience: get large transfers OUT of a specific exchange.
        Signal: holders withdrawing to self-custody (bullish).
        """
        return self.get_transfers(
            from_entity=exchange_slug,
            time_last=time_last,
            usd_gte=usd_gte,
            limit=limit,
        )

    def get_entity_exchange_activity(
        self,
        entity_slug: str,
        exchanges: list[str],
        time_last: str = "30d",
    ) -> dict:
        """
        For each exchange, fetch transfers from entity → exchange.
        Returns dict keyed by exchange slug with transfer lists.
        Used in investigation Step 3: Destination Analysis.
        """
        results = {}
        for exchange in exchanges:
            try:
                transfers = self.get_transfers(
                    base=entity_slug,
                    to_entity=exchange,
                    time_last=time_last,
                    limit=50,
                )
                total_usd = sum(t.get("historicalUSD", 0) for t in transfers)
                results[exchange] = {
                    "transfers": transfers,
                    "count":     len(transfers),
                    "total_usd": total_usd,
                }
            except ArkhamAPIError as exc:
                logger.warning(f"Failed exchange activity {entity_slug}→{exchange}: {exc}")
                results[exchange] = {"transfers": [], "count": 0, "total_usd": 0}

        return results

    # ─────────────────────────────────────────────────────────────────────────
    # TRANSFER HISTOGRAM
    # ─────────────────────────────────────────────────────────────────────────

    def get_transfer_histogram(
        self,
        base: str,
        time_last: str = "30d",
        granularity: str = "day",
    ) -> list[dict]:
        """
        GET /transfers/histogram
        Returns [{time, count, usd}] — daily transfer volume breakdown.
        Used to detect volume spikes vs historical baseline.
        """
        params = {
            "base":        base,
            "timeLast":    time_last,
            "granularity": granularity,
        }
        data = self._get("/transfers/histogram", params=params)
        histogram = data.get("histogram", data if isinstance(data, list) else [])
        logger.info(f"Histogram fetched: {base}, {len(histogram)} data points")
        return histogram

    def detect_volume_surge(
        self,
        base: str,
        time_last: str = "30d",
        surge_multiplier: float = 2.0,
    ) -> dict:
        """
        Fetch histogram and compare today's volume against the historical average.
        Returns: {is_surging, today_usd, avg_usd, multiplier, histogram}
        """
        histogram = self.get_transfer_histogram(base, time_last=time_last)

        if not histogram:
            return {"is_surging": False, "today_usd": 0, "avg_usd": 0, "multiplier": 0}

        usd_values = [entry.get("usd", 0) for entry in histogram]
        today_usd  = usd_values[-1] if usd_values else 0
        avg_usd    = sum(usd_values[:-1]) / max(len(usd_values) - 1, 1)
        multiplier = (today_usd / avg_usd) if avg_usd > 0 else 0

        return {
            "is_surging": multiplier >= surge_multiplier,
            "today_usd":  today_usd,
            "avg_usd":    avg_usd,
            "multiplier": round(multiplier, 2),
            "surge_pct":  round((multiplier - 1) * 100, 1),
            "histogram":  histogram,
        }

    # ─────────────────────────────────────────────────────────────────────────
    # TOKEN ANALYSIS
    # ─────────────────────────────────────────────────────────────────────────

    def get_top_tokens(
        self,
        timeframe: str = "24h",
        order_by: str = "inflow",          # inflow | outflow | volume | netflow
        order_desc: bool = True,
        size: int = 10,
        from_index: int = 0,
    ) -> list[dict]:
        """
        GET /token/top
        Returns tokens ranked by the chosen aggregate metric.
        order_by: "inflow" (accumulation), "outflow" (distribution),
                  "volume" (activity), "netflow" (net direction)
        """
        params = {
            "timeframe":       timeframe,
            "orderByAgg":      order_by,
            "orderByDesc":     str(order_desc).lower(),
            "orderByPercent":  "false",
            "from":            from_index,
            "size":            size,
        }
        data   = self._get("/token/top", params=params)
        if not isinstance(data, dict):
            logger.warning(f"Unexpected top tokens response type: {type(data)}")
            return []
        raw = data.get("tokens", [])
        if not isinstance(raw, list):
            logger.warning(f"Unexpected tokens type: {type(raw)}")
            return []

        # Normalize: API returns nested {token: {id, symbol}, current: {inflowDexVolume, ...}}
        # but consumers expect flat {id, symbol, name, inflow, outflow}
        normalized = []
        for tok in raw:
            if not isinstance(tok, dict):
                continue
            token_info = tok.get("token", {}) if isinstance(tok.get("token"), dict) else {}
            current    = tok.get("current", {}) if isinstance(tok.get("current"), dict) else {}

            tid  = token_info.get("id", "") or tok.get("id", "")
            sym  = token_info.get("symbol", "") or tok.get("symbol", "")
            name = token_info.get("name", "") or tok.get("name", "")

            inflow  = (current.get("inflowDexVolume", 0) or 0) + (current.get("inflowCexVolume", 0) or 0)
            outflow = (current.get("outflowDexVolume", 0) or 0) + (current.get("outflowCexVolume", 0) or 0)

            normalized.append({
                "id":       tid,
                "symbol":   sym,
                "name":     name,
                "inflow":   inflow,
                "outflow":  outflow,
                "price":    current.get("price", 0),
                "marketCap": token_info.get("marketCap", 0),
            })

        logger.info(f"Top tokens ({order_by} / {timeframe}): {len(normalized)} results")
        return normalized

    def get_token_holders(
        self,
        token_slug: str,
        group_by_entity: bool = True,
    ) -> dict:
        """
        GET /token/holders/{token_slug}?groupByEntity=true
        Returns: token info + addressTopHolders + entityTopHolders
        Confirmed slugs: bitcoin, ethereum, tether, pepe, arbitrum
        """
        params = {"groupByEntity": str(group_by_entity).lower()}
        data   = self._get(f"/token/holders/{token_slug}", params=params)
        logger.info(f"Token holders fetched: {token_slug}")
        return data

    def get_token_top_flow(
        self,
        token_slug: str,
        time_last: str = "24h",
    ) -> list[dict]:
        """
        GET /token/top_flow/{token_slug}?timeLast=24h
        Returns [{address, inUSD, outUSD, inValue, outValue}]
        Who is the biggest mover of this token?
        """
        params = {"timeLast": time_last}
        data   = self._get(f"/token/top_flow/{token_slug}", params=params)
        if isinstance(data, list):
            flows = data
        else:
            flows = data.get("topFlow", [])
        logger.info(f"Token top flow fetched: {token_slug} ({time_last})")
        return flows

    def get_trending_tokens(self) -> list[dict]:
        """
        GET /token/trending
        Returns tokens with unusual onchain activity right now.
        No params needed.
        """
        data    = self._get("/token/trending")
        if isinstance(data, list):
            tokens = data
        elif isinstance(data, dict):
            tokens = data.get("tokens", [])
        else:
            logger.warning(f"Unexpected trending response type: {type(data)}")
            return []
        if not isinstance(tokens, list):
            logger.warning(f"Unexpected tokens type: {type(tokens)}")
            return []
        logger.info(f"Trending tokens: {len(tokens)} results")
        return tokens

    def search_token(self, query: str) -> list[dict]:
        """
        GET /token/search?query={name}
        Find the correct Arkham slug for a token before using other endpoints.
        """
        data    = self._get("/token/search", params={"query": query})
        if isinstance(data, list):
            results = data
        elif isinstance(data, dict):
            results = data.get("tokens", [])
        else:
            results = []
        logger.info(f"Token search '{query}': {len(results)} results")
        return results

    def resolve_token_slug(self, symbol_or_name: str) -> Optional[str]:
        """
        Resolve a token symbol (e.g. "PEPE") to its Arkham slug (e.g. "pepe").
        Checks local lookup first, then falls back to search API.
        Returns None if not found.
        """
        from config.entities import KNOWN_TOKEN_SLUGS

        # Check local lookup (fastest)
        slug = KNOWN_TOKEN_SLUGS.get(symbol_or_name.upper())
        if slug:
            return slug

        # Fall back to search API
        results = self.search_token(symbol_or_name)
        if results:
            return results[0].get("id") or results[0].get("slug")

        return None

    # ─────────────────────────────────────────────────────────────────────────
    # HISTORICAL & DEX
    # ─────────────────────────────────────────────────────────────────────────

    def get_entity_history(self, slug: str) -> list[dict]:
        """
        GET /history/entity/{slug}
        Portfolio value over time since 2021.
        Returns list of {time, value} data points.
        """
        data    = self._get(f"/history/entity/{slug}")
        history = data.get("history", data if isinstance(data, list) else [])
        logger.info(f"Entity history fetched: {slug}, {len(history)} points")
        return history

    def get_entity_swaps(
        self,
        slug: str,
        chain: Optional[str] = None,
        limit: int = 20,
    ) -> list[dict]:
        """
        GET /swaps?base={slug}&chain={chain}&limit={n}
        DEX swap activity — what are they trading on-chain?
        """
        params = {"base": slug, "limit": limit}
        if chain:
            params["chain"] = chain

        data  = self._get("/swaps", params=params)
        swaps = data.get("swaps", data if isinstance(data, list) else [])
        logger.info(f"DEX swaps fetched: {slug}, {len(swaps)} results")
        return swaps

    def get_entity_counterparties(
        self,
        slug: str,
        limit: int = 10,
        time_last: str = "7d",
    ) -> list[dict]:
        """
        GET /counterparties/entity/{slug}?limit={n}&timeLast=7d
        Who interacts with this entity most frequently?
        Useful for network analysis in Step 5 of investigation.
        """
        params = {"limit": limit, "timeLast": time_last}
        data   = self._get(f"/counterparties/entity/{slug}", params=params)
        parties = data.get("counterparties", data if isinstance(data, list) else [])
        logger.info(f"Counterparties fetched: {slug}, {len(parties)} results")
        return parties


# ── HELPER (avoids circular import) ──────────────────────────────────────────

def WHALE_THRESHOLD_FROM_SETTINGS() -> float:
    from config.settings import WHALE_THRESHOLD_USD
    return WHALE_THRESHOLD_USD
